from __future__ import annotations
import requests
from typing import Any, TypeAlias, Literal, AsyncGenerator
import os
from dotenv import load_dotenv
import openai
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
from pydantic import BaseModel
import json
from typing_extensions import TypedDict

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


class LLMConfig:
    instance: LLMConfig

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.model_name = os.getenv("OPENAI_MODEL_NAME")


LLMConfig.instance = LLMConfig()


class TextContent(TypedDict):
    text: str = ""
    type: Literal["input_text"] = "input_text"


class ImageContent(TypedDict):
    image_url: str = ""
    type: Literal["input_image"] = "input_image"


def text_content(item) -> TextContent:
    return TextContent(text=item, type="input_text")


def image_content(item) -> ImageContent:
    return ImageContent(image_url=item, type="input_image")


class ContextItem(TypedDict):
    role: Literal["user", "assistant", "system"] = "system"
    content: list[TextContent | ImageContent] = None


class FunctionCallContextItem(TypedDict):
    type: Literal["function_call"] = "function_call"
    name: str
    arguments: str | dict
    call_id: str


class FunctionCallOutputContextItem(TypedDict):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str


Context: TypeAlias = list[
    ContextItem | FunctionCallContextItem | FunctionCallOutputContextItem
]


class EzcliParams(BaseModel):
    args: str = "-h"


def dump_to(context: Context, path: str = "dump.md"):
    f = open(path, "w")

    def tostr(obj):
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, list):
            return "\n".join([tostr(item) for item in obj])
        elif isinstance(obj, dict):
            return "\n".join([k + ": " + tostr(v) for k, v in obj.items()])

    for item in context:
        f.write("---\n")
        f.write(tostr(item))
        f.write("\n")


class Function(BaseModel):
    arguments: dict | str | None = None
    name: str | None = None
    call_id: str | None = None


class ToolCall(BaseModel):
    index: int | None = 0
    id: str | None = None
    function: Function
    type: Literal["function"] = "function"


class OpenAITool(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str
    parameters: openai.types.FunctionParameters
    strict: bool = True


class CallRequest(BaseModel):
    args: str


class CallResponse(BaseModel):
    output: str
    cat_content: TextContent | ImageContent | None


tool = OpenAITool(
    name="ezcli",
    description="ezcli",
    parameters=EzcliParams().model_json_schema(),
)


async def llm_response(
    context: Context = None,
    extra_body: dict[str, Any] = {"thinking": {"type": "disabled"}},
    llm_config: LLMConfig = LLMConfig.instance,
) -> AsyncGenerator[str | Function, None]:
    if context is None:
        context = [ContextItem("user", [text_content("hello")])]
    oclient = openai.AsyncOpenAI(
        api_key=llm_config.api_key, base_url=llm_config.base_url
    )
    stream = await oclient.responses.create(
        model=llm_config.model_name,
        input=context,
        stream=True,
        extra_body=extra_body,
        tools=[tool.model_dump()],
        tool_choice="auto",
    )
    async for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta
        elif event.type == "response.output_item.done":
            if event.item.type == "function_call":
                yield Function(
                    name=event.item.name,
                    call_id=event.item.call_id,
                    arguments=json.loads(event.item.arguments),
                )


def add_context_to(
    context: Context = None,
    role: Literal["system", "assistant", "user", "tool"] = "system",
    content: list[TextContent | ImageContent] = None,
    copy: bool = False,
) -> Context:
    if context is None:
        context = []
    elif copy:
        context = context.copy()
    citem = ContextItem(role=role, content=content)
    context.append(citem)
    return context


def add_f_context_to(
    context: Context = None,
    name: str = "",
    arguments: str = "",
    call_id: str = "",
    content: str = "",
    copy: bool = False,
) -> Context:
    if context is None:
        context = []
    elif copy:
        context = context.copy()
    citem = FunctionCallContextItem(
        type="function_call", name=name, arguments=arguments, call_id=call_id
    )
    context.append(citem)
    citem = FunctionCallOutputContextItem(
        type="function_call_output", call_id=call_id, output=content
    )
    context.append(citem)
    return context


def load_prompt_to(
    context: Context = None, path: str = "./PROMPT.md", ezcli_doc: str = None
) -> Context:
    prompt = open(path, encoding="utf-8").read()
    prompt = prompt.replace("{{EZCLI_DOC}}", ezcli_doc)
    open("ezcli_doc.md", "w", encoding="utf-8").write(ezcli_doc)
    return add_context_to(context, "system", [text_content(prompt)])


async def _ezcli_call(name: str, args: str) -> tuple[str, TextContent | ImageContent]:
    cat_content = None
    tool_output = ""
    cmd = f"python client.py {args}"
    env = os.environ.copy()
    env.update({"PYTHONENCODING": "utf-8", "PYTHONUTF8": "1"})
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=1024 * 1024 * 20,  # 20MB
        env=env,
    )
    stdout_data, stderr_data = await proc.communicate()
    if proc.returncode == 0:
        if stdout_data is not None:
            stdout_str = stdout_data.decode("utf-8")
            is_cat = False
            try:
                out_obj = json.loads(stdout_str)
                file_type = out_obj.get("file_type")
                if file_type in ["image", "text"]:
                    is_cat = True
                    data = out_obj["chunk_content"]
                    del out_obj["chunk_content"]
                    tool_output += json.dumps(out_obj)
                    if file_type == "image":
                        cat_content = image_content(data)
                    else:
                        cat_content = text_content(data[-EXECUTE_OUTPUT_MAX_LEN:])
            except:
                pass
            if not is_cat:
                tool_output += stdout_str[-EXECUTE_OUTPUT_MAX_LEN:]
    else:
        if stderr_data is not None:
            stderr_str = stderr_data.decode("utf-8")
            tool_output += stderr_str[-EXECUTE_OUTPUT_MAX_LEN:]
    return tool_output, cat_content


async def _single_progress(
    user_input: str, context: Context = None
) -> AsyncGenerator[tuple[str, str, Context], None]:
    context = add_context_to(context, "user", [text_content(user_input)])
    dump_to(context)
    yield None, None, context
    output_str: str = ""
    should_response_again: bool = True
    while should_response_again:
        context_str: str = ""
        delta_str: str = ""
        should_response_again = False
        async for delta in llm_response(context):
            if isinstance(delta, Function):
                func = delta
                if not func.name == "ezcli":
                    continue
                tool_output: str = ""
                args = EzcliParams.model_validate(func.arguments).args
                should_response_again = True
                raw_cmd = func.name + " " + args
                delta_str = f"\n**已调用** `{raw_cmd}`\n\n"
                output_str += delta_str
                yield output_str, delta_str, context
                add_context_to(context, "assistant", [text_content(context_str)])
                tool_output, cat_content = await _ezcli_call(func.name, args)
                add_f_context_to(
                    context, func.name, func.arguments, func.call_id, tool_output
                )
                yield None, None, context
                if cat_content is not None:
                    add_context_to(
                        context,
                        "system",
                        [text_content("所查看的文件内容如下："), cat_content],
                    )
            else:
                delta_str = delta
                context_str += delta_str
                output_str += delta_str
                yield output_str, delta_str, context
        if not should_response_again:
            context = add_context_to(context, "assistant", [text_content(output_str)])
            yield None, None, context
        dump_to(context)


async def single_progress(user_input: str, context: Context = None) -> None:
    history = []
    tail = []
    TAIL_LINES = 20
    live = Live(refresh_per_second=20)

    with live:
        async for output, delta, context in _single_progress(
            user_input=user_input,
            context=context,
        ):
            if not output:
                continue

            lines = output.splitlines()
            if len(lines) > TAIL_LINES:
                new_history = lines[:-TAIL_LINES]
                if len(new_history) > len(history):
                    for line in new_history[len(history) :]:
                        live.console.print(line)

                history = new_history
                tail = lines[-TAIL_LINES:]
            else:
                tail = lines

            live.update(Text("\n".join(tail)))


def single_progress_headless(user_input: str, context: Context = None):
    return _single_progress(user_input=user_input, context=context)


async def cli():
    context = load_prompt_to(ezcli_doc=client.doc("ezcli"))
    while True:
        user_input = input("\nUser: ")
        await single_progress(user_input, context)


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


@app.post("/interact/tool")
async def interact_tool(i_request: InteractRequest) -> ContextItem:
    if len(i_request.context) <= 0:
        i_request.context = load_prompt_to(ezcli_doc=client.doc("ezcli"))
    async for output, delta, ctx in single_progress_headless(
        i_request.user_input, i_request.context
    ):
        pass
    return JSONResponse(content=ctx[-1])


@app.get("/ezcli/doc")
async def ezcli_doc() -> str:
    return PlainTextResponse(client.doc("ezcli"))


@app.post("/ezcli/call")
async def ezcli_call(creq: CallRequest) -> CallResponse:
    output, content = await _ezcli_call("ezcli", creq.args)
    return CallResponse(output=output, cat_content=content)


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
