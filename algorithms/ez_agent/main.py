from __future__ import annotations
import requests
from typing import Any, TypeAlias, Literal, AsyncGenerator
import os
from dotenv import load_dotenv
import asyncio
from rich.live import Live
from rich.text import Text
from fastapi import FastAPI
from fastapi.responses import (
    StreamingResponse,
    FileResponse,
    JSONResponse,
    PlainTextResponse,
)
from pydantic import BaseModel, Field
from agents import (
    OpenAIProvider,
    TResponseInputItem,
    FunctionTool,
    Agent,
    Runner,
    RunConfig,
    ModelSettings,
    AgentsException,
    function_tool,
    RunContextWrapper,
)
from openai.types.shared.reasoning import Reasoning
import traceback
from typing import Annotated, Union
from dataclasses import dataclass

EXECUTE_OUTPUT_MAX_LEN = 10240


def dynamic_load_client(
    url: str = "http://127.0.0.1:8000/static/client.py",
    save_path: str = "./client.py",
):
    try:
        response = requests.get(url)
        response.raise_for_status()
        script_content = response.text

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(script_content.replace("\r\n", "\n"))
    except Exception as e:
        raise RuntimeError(f"Failed to load client from {url}: {str(e)}")


dynamic_load_client()
import client

load_dotenv()


class LLMConfig:
    model: str
    provider: OpenAIProvider

    def __init__(
        self,
        model: str = os.getenv("OPENAI_DEFAULT_MODEL", os.getenv("OPENAI_MODEL_NAME")),
        api_key: str = os.getenv("OPENAI_API_KEY"),
        base_url: str = os.getenv("OPENAI_BASE_URL"),
    ):
        self.model = model
        self.provider = OpenAIProvider(api_key=api_key, base_url=base_url)

    def reasoning_settings(self) -> ModelSettings | None:
        effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        if effort == "none":
            return None
        return ModelSettings(reasoning=Reasoning(effort=effort))


DEFAULT_LLM_CONFIG = LLMConfig()


class OutputEvent(BaseModel):
    event: Literal["output"]
    data_type: str
    value: str


class ReasoningEvent(BaseModel):
    event: Literal["reasoning"]
    data_type: str
    value: str


class ContentEvent(BaseModel):
    event: Literal["content"]
    data_type: str
    value: dict


class HistoryEvent(BaseModel):
    event: Literal["history"]
    data_type: str
    value: list[dict]


@dataclass
class AgentContext:
    value: list | dict | None = None
    changed: bool = False


class ContextEvent(BaseModel):
    event: Literal["context"]
    data_type: str
    value: Any


RunEvent = Annotated[
    Union[OutputEvent, ReasoningEvent, ContentEvent, HistoryEvent, ContextEvent],
    Field(discriminator="event"),
]


EVENT_TYPE: TypeAlias = Literal["output", "reasoning", "content", "history", "context"]


def run_event(
    event: EVENT_TYPE,
    data_type: str,
    value: Any,
) -> RunEvent:
    cls = {
        "output": OutputEvent,
        "reasoning": ReasoningEvent,
        "content": ContentEvent,
        "history": HistoryEvent,
        "context": ContextEvent,
    }[event]
    return cls(event=event, data_type=data_type, value=value)


async def run_agent(
    history: list[TResponseInputItem] = [{"role": "user", "content": "hello"}],
    agent_name: str = "agent",
    instructions: str = "",
    tools: list[FunctionTool] = [],
    agent_context: AgentContext = None,
    ignore_events: set[EVENT_TYPE] = set(),
    model: str = DEFAULT_LLM_CONFIG.model,
    provider: OpenAIProvider = DEFAULT_LLM_CONFIG.provider,
    output_type: type[BaseModel] = None,
) -> AsyncGenerator[RunEvent, None]:
    agent = Agent(
        agent_name, instructions=instructions, tools=tools, output_type=output_type
    )
    if agent_context is None:
        agent_context = AgentContext()
    result = Runner().run_streamed(
        agent,
        history,
        run_config=RunConfig(
            tracing_disabled=True,
            model=model,
            model_provider=provider,
            model_settings=DEFAULT_LLM_CONFIG.reasoning_settings(),
        ),
        context=agent_context,
    )
    try:
        async for event in result.stream_events():
            if event.type == "raw_response_event":
                data = event.data
                if data.type in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
                    if "reasoning" in ignore_events:
                        continue
                    event = run_event("reasoning", event.data.type, data.delta)
                    yield event
                elif data.type == "response.output_text.delta":
                    if "output" in ignore_events:
                        continue
                    event = run_event("output", event.data.type, data.delta)
                    yield event
            elif event.type == "run_item_stream_event":
                data = event.item.to_input_item()
                if "content" in ignore_events:
                    continue
                event = run_event("content", event.name, data)
                yield event
            if agent_context.changed:
                agent_context.changed = False
                if "context" in ignore_events:
                    continue
                event = run_event("context", "context", agent_context.value)
                yield event
    except AgentsException:
        exception_content = {
            "role": "system",
            "content": f"Agent Exception:\n{traceback.format_exc()}",
        }
        final_history = result.to_input_list()
        final_history.append(exception_content)
        event = run_event("content", "exception", exception_content)
        if "content" not in ignore_events:
            yield event
    else:
        final_history = result.to_input_list()
    if "history" not in ignore_events:
        event = run_event("history", "done", final_history)
        yield event


@function_tool
async def ezcli(rcw: RunContextWrapper[AgentContext], command: str) -> str:
    """
    Invoke ezcli tool to interact with platform.

    The command is the arguments after ezcli,
    e.g. root@SOME_PLATFORM:~/# ezcli {{command}}
    """
    cmd = f"python client.py {command}"
    env = os.environ.copy()
    env.update({"PYTHONENCODING": "utf-8", "PYTHONUTF8": "1"})
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        limit=EXECUTE_OUTPUT_MAX_LEN,
        env=env,
    )
    stdout_data, _ = await proc.communicate()
    stdout_str = stdout_data.decode("utf-8") if stdout_data is not None else ""
    return stdout_str


def get_instructions(path: str = "./PROMPT.md") -> str:
    prompt = open(path, encoding="utf-8").read()
    prompt = prompt.replace("{{EZCLI_DOC}}", client.doc("ezcli"))
    return prompt


INSTRUCTIONS = get_instructions()


def ez_run_agent(user_input: str, history: list[dict] = None):
    if history is None:
        history = []
    return run_agent(
        history=history + [{"role": "user", "content": user_input}],
        agent_name="ezagent",
        instructions=INSTRUCTIONS,
        tools=[ezcli],
        model=DEFAULT_LLM_CONFIG.model,
        provider=DEFAULT_LLM_CONFIG.provider,
    )


async def single_process(
    user_input: str, history: list[TResponseInputItem] = None
) -> list[TResponseInputItem]:
    term_history = []
    reasoning_history = []
    tail = []
    reasoning_tail = []
    printed_lines = 0
    reasoning_printed_lines = 0
    TAIL_LINES = 20

    live = Live(refresh_per_second=20)
    with live:
        async for event in ez_run_agent(user_input, history):
            if event.event == "output":
                term_history.append(event.value)
                lines = "".join(term_history).splitlines()
                if len(lines) > TAIL_LINES:
                    new_history = lines[:-TAIL_LINES]
                    if len(new_history) > printed_lines:
                        for line in new_history[printed_lines:]:
                            live.console.print(line)
                    printed_lines = len(new_history)
                    tail = lines[-TAIL_LINES:]
                else:
                    tail = lines
            elif event.event == "reasoning":
                reasoning_history.append(event.value)
                reasoning_lines = "".join(reasoning_history).splitlines()
                if len(reasoning_lines) > TAIL_LINES:
                    new_reasoning = reasoning_lines[:-TAIL_LINES]
                    if len(new_reasoning) > reasoning_printed_lines:
                        for line in new_reasoning[reasoning_printed_lines:]:
                            live.console.print(f"[dim]{line}[/dim]")
                    reasoning_printed_lines = len(new_reasoning)
                    reasoning_tail = reasoning_lines[-TAIL_LINES:]
                else:
                    reasoning_tail = reasoning_lines
            elif event.event == "content":
                item = event.value
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "function_call":
                        name = item.get("name", "")
                        args = item.get("arguments", "")
                        live.console.print(f"[cyan]调用工具: {name}({args})[/cyan]")
                    elif item_type == "function_call_output":
                        output = item.get("output", "")
                        live.console.print(f"[cyan]工具返回: {output}[/cyan]")
            elif event.event == "history":
                history = event.value
            display = Text()
            if reasoning_tail:
                display.append("\n".join(reasoning_tail), style="dim")
                display.append("\n")
            if tail:
                display.append("\n".join(tail))
            live.update(display)
    return history


async def cli():
    history = []
    while True:
        user_input = input("\nUser: ")
        history = await single_process(user_input, history)


app = FastAPI()


class InteractRequest(BaseModel):
    context: list[dict] = Field(default_factory=list)
    user_input: str


@app.post("/interact")
async def interact(i_request: InteractRequest):
    async def generator():
        async for event in ez_run_agent(i_request.user_input, i_request.context):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/interact/tool")
async def interact_tool(i_request: InteractRequest) -> dict:
    history = []
    async for event in ez_run_agent(i_request.user_input, i_request.context):
        if event.event == "history":
            history = event.value
    return JSONResponse(content=history[-1])


@app.get("/ezcli/doc")
async def ezcli_doc() -> str:
    return PlainTextResponse(client.doc("ezcli"))


@app.get("/")
@app.get("/index")
@app.get("/index.html")
async def index():
    return FileResponse("./index.html")


@app.get("/marked.min.js")
async def marked_js():
    return FileResponse("./marked.min.js")


if __name__ == "__main__":
    asyncio.run(cli())
