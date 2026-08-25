from agents import (
    Agent,
    Runner,
    RunConfig,
    ModelSettings,
    TResponseInputItem,
    AgentsException,
    FunctionTool,
    OpenAIProvider,
)
from openai.types.shared.reasoning import Reasoning
import traceback
from typing import Any, Literal, Annotated, AsyncGenerator, Union, TypeAlias
from pydantic import BaseModel, Field
from dataclasses import dataclass
import os
from dotenv import load_dotenv

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
