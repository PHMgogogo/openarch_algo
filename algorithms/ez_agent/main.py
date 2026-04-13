from __future__ import annotations
import urllib.request
from typing import Any, TypeAlias, Literal, AsyncGenerator
import os
from dotenv import load_dotenv
import openai
import asyncio
from dataclasses import dataclass
from rich.live import Live
from rich.markdown import Markdown
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json
from typing_extensions import TypedDict

EXECUTE_OUTPUT_MAX_LEN = 10240


def dynamic_load_client(
    url: str = "http://127.0.0.1:8000/static/client.py",
    save_path: str = "./client.py",
):
    try:
        response = urllib.request.urlopen(url)
        script_content = response.read().decode("utf-8")

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(script_content.replace("\r\n", "\n"))
    except Exception as e:
        raise RuntimeError(f"Failed to load client from {url}: {str(e)}")


dynamic_load_client()
import client


class LLMConfig:
    instance: LLMConfig

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.model_name = os.getenv("OPENAI_MODEL_NAME")


LLMConfig.instance = LLMConfig()


@dataclass
class ContextItem(TypedDict):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_name: str | None = None
    tool_call_id: str | None = None


Context: TypeAlias = list[ContextItem]


class EzcliParams(BaseModel):
    args: str = "-h"


class OpenAITool(BaseModel):
    type: Literal["function"] = "function"
    function: openai.types.FunctionDefinition


class Function(BaseModel):
    arguments: dict | str | None = None
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    index: int | None = 0
    id: str | None = None
    function: Function
    type: Literal["function"] = "function"


tool = OpenAITool(
    function=openai.types.FunctionDefinition(
        name="ezcli",
        description="ezcli",
        parameters=EzcliParams().model_json_schema(),
        strict=True,
    )
)


async def llm_response(
    context: Context = [ContextItem(role="user", content="hello")],
    extra_body: dict[str, Any] = {"thinking": {"type": "disabled"}},
    llm_config: LLMConfig = LLMConfig.instance,
) -> AsyncGenerator[str | Function, None]:
    client = openai.AsyncOpenAI(
        api_key=llm_config.api_key, base_url=llm_config.base_url
    )

    stream = await client.chat.completions.create(
        model=llm_config.model_name,
        messages=context,
        stream=True,
        extra_body=extra_body,
        tools=[tool.model_dump()],
        tool_choice="auto",
    )
    tool_call_result = dict[int, Function]()
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.tool_calls is not None and len(delta.tool_calls) > 0:
            for item in delta.tool_calls:
                item: ToolCall = item
                if item.index not in tool_call_result:
                    tool_call_result[item.index] = Function(
                        name=item.function.name,
                        arguments=item.function.arguments,
                        tool_call_id=item.id,
                    )
                else:
                    if item.function.name != None:
                        tool_call_result[item.index].name += item.function.name
                    tool_call_result[item.index].arguments += item.function.arguments
        elif delta.content:
            yield delta.content
        else:
            for fn in tool_call_result.values():
                fn.arguments = json.loads(fn.arguments)
            yield list(tool_call_result.values())


def add_context_to(
    context: Context = None,
    role: str = Literal["system", "assistant", "user", "tool"],
    content: str = "",
    tool_call_id: str = None,
    copy: bool = False,
) -> Context:
    if context is None:
        context = []
    elif copy:
        context = context.copy()
    citem = ContextItem(role=role, content=content)
    citem["tool_call_id"] = tool_call_id
    context.append(citem)
    return context


def load_prompt_to(
    context: Context = None, path: str = "./PROMPT.md", ezcli_doc: str = None
) -> Context:
    prompt = open(path, encoding="utf-8").read()
    prompt = prompt.replace("{{EZCLI_DOC}}", ezcli_doc)
    return add_context_to(context, "system", prompt)


async def _single_progress(
    user_input: str, context: Context = None
) -> AsyncGenerator[tuple[str, str, Context], None]:
    dump = True
    context = add_context_to(context, "user", user_input)
    yield None, None, context
    output_str: str = ""
    while True:
        tool_output: str = ""
        delta_str: str = ""
        should_response_again: bool = False
        async for delta in llm_response(context):
            if isinstance(delta, list):
                for func in delta:
                    if not isinstance(func, Function) or not func.name == "ezcli":
                        continue
                    args = EzcliParams.model_validate(func.arguments).args
                    should_response_again = True
                    raw_cmd = func.name + " " + args
                    cmd = "python client.py " + args
                    invoked_str = f"\n**已调用** `{raw_cmd}`\n\n"
                    delta_str = invoked_str
                    output_str += delta_str
                    env = os.environ.copy()
                    env.update({"PYTHONENCODING": "utf-8", "PYTHONUTF8": "1"})
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    stdout_data, stderr_data = await proc.communicate()
                    if proc.returncode == 0:
                        # tool_output += f"\n```{raw_cmd}\n"
                        if stdout_data is not None:
                            stdout_str = stdout_data.decode("utf-8")
                            tool_output += stdout_str[-EXECUTE_OUTPUT_MAX_LEN:]
                        # tool_output += "```\n"
                    else:
                        tool_output += f"\n```{raw_cmd}\n"
                        if stderr_data is not None:
                            stderr_str = stderr_data.decode("utf-8")
                            tool_output += stderr_str[-EXECUTE_OUTPUT_MAX_LEN:]
                        tool_output += "```\n"
                    add_context_to(
                        context,
                        "tool",
                        tool_output,
                        func.tool_call_id,
                    )
                    add_context_to(context, "system", "继续")
            else:
                delta_str = delta
                output_str += delta_str
                yield output_str, delta_str, context
            if should_response_again:
                break
        context = add_context_to(context, "assistant", output_str)
        yield None, None, context
        if not should_response_again:
            break
    if dump:
        with open("dump.md", "w", encoding="utf-8") as f:
            for item in context:
                f.write(f"# {item['role']}\n")
                f.write(item["content"])
                f.write("\n")
    return


async def single_progress(user_input: str, context: Context = None) -> None:
    live = Live(refresh_per_second=20)
    with live:
        async for output, delta, context in _single_progress(
            user_input=user_input, context=context
        ):
            if output:
                live.update(Markdown(output))
            else:
                pass

        # elif context[-1]["role"] == "assistant":
        #     live.console.print(context[-1]["content"])


def single_progress_headless(user_input: str, context: Context = None):
    return _single_progress(user_input=user_input, context=context)


async def cli():
    dump = False
    context = load_prompt_to(ezcli_doc=client.doc("ezcli"))
    while True:
        user_input = input("\nUser: ")
        await single_progress(user_input, context)
        if dump:
            md = open("context.md", "w", encoding="utf-8")
            for item in context:
                md.write(f"# {item['role']}\n")
                md.write(f"{item['content']}\n")


app = FastAPI()


class InteractRequest(BaseModel):
    context: Context = []
    user_input: str


@app.post("/interact")
async def interact(i_request: InteractRequest):
    if len(i_request.context) <= 0:
        i_request.context = load_prompt_to(ezcli_doc=client.doc("ezcli"))

    async def generator():
        async for output, delta, ctx in single_progress_headless(
            i_request.user_input, i_request.context
        ):
            payload = ctx if not output else {"output": output}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/")
@app.get("/index")
@app.get("/index.html")
async def index():
    return FileResponse("./index.html")


if __name__ == "__main__":
    asyncio.run(cli())
