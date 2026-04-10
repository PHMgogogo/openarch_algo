from __future__ import annotations
import urllib.request
from typing import Any, TypeAlias, Literal, AsyncIterator
import os
from dotenv import load_dotenv
import openai
import asyncio
import re
from dataclasses import dataclass
import subprocess
from rich.live import Live
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json

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


Context: TypeAlias = list[dict[str, str]]


async def llm_response(
    context: Context = [{"role": "user", "content": "hello"}],
    extra_body: dict[str, Any] = {"thinking": {"type": "disabled"}},
    llm_config: LLMConfig = LLMConfig.instance,
) -> AsyncIterator[str]:
    client = openai.AsyncOpenAI(
        api_key=llm_config.api_key, base_url=llm_config.base_url
    )

    stream = await client.chat.completions.create(
        model=llm_config.model_name,
        messages=context,
        stream=True,
        extra_body=extra_body,
    )

    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content is not None:
                yield delta.content


async def test():
    async for content in llm_response():
        print(content, end="")


def add_context_to(
    context: Context = None,
    role: str = Literal["system", "assistant", "user"],
    content: str = "",
    copy: bool = False,
) -> Context:
    if context is None:
        context = []
    elif copy:
        context = context.copy()
    context.append({"role": role, "content": content})
    return context


def load_prompt_to(
    context: Context = None, path: str = "./PROMPT.md", ezcli_doc: str = None
) -> Context:
    prompt = open(path, encoding="utf-8").read()
    prompt = prompt.replace("{{EZCLI_DOC}}", ezcli_doc)
    return add_context_to(context, "system", prompt)


@dataclass
class MatchGroup:
    match_group_1: str
    match_group_start: int
    match_group_end: int


TOOL_INVOKE_PATTERN = r"<ez-agent-tool>([\s\S]*?)</ez-agent-tool>"
NO_RENDER_PATTERN = r"```ezcli(.*?)```"


def check_if_cmd(
    output: str,
    pattern: str = TOOL_INVOKE_PATTERN,
) -> list[MatchGroup]:
    try:
        if output.startswith("```ezcli"):
            return []
        if not output.strip().endswith(
            "</ez-agent-tool>"
        ) or not output.strip().startswith("<ez-agent-tool>"):
            return []
        matches = list(re.finditer(pattern, output, re.DOTALL))
        if not matches:
            return []
        return [
            MatchGroup(
                match_group_1=match.group(1).strip(),
                match_group_start=match.start(),
                match_group_end=match.end(),
            )
            for match in matches
        ]
    except:
        return []


class HeadlessConsole:
    def print(*args, **kwargs):
        pass


class HeadlessLive:
    console = HeadlessConsole

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc, tb):
        pass

    def update(self, *args, **kwargs):
        pass

    def console(self, *args, **kwargs):
        pass


async def _single_progress(
    user_input: str, context: Context = None, headless: bool = False
):
    if not headless:
        live = Live(refresh_per_second=25)
    else:
        live = HeadlessLive()
    refresh = False
    rewritable_output: str = ""
    renderable_output: str = ""
    context = add_context_to(context, "user", user_input)
    if headless:
        yield "", True, context
    while True:
        should_response_again: bool = False
        with live:
            async for delta in llm_response(context):
                rewritable_output += delta
                renderable_output += delta
                cic = check_if_cmd(rewritable_output)
                if len(cic) <= 0:
                    pass
                else:
                    should_response_again = True
                    raw_cmd = cic[0].match_group_1
                    cmd = cic[0].match_group_1.replace("ezcli", "python client.py")
                    rewritable_output = rewritable_output[: cic[0].match_group_start]
                    render_cic = check_if_cmd(renderable_output)
                    if len(render_cic) > 0:
                        renderable_output = renderable_output[
                            : check_if_cmd(renderable_output)[0].match_group_start
                        ]
                    renderable_output += f"已调用 `{raw_cmd}`\n"
                    process_result = subprocess.run(
                        cmd,
                        text=True,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if process_result.returncode == 0:
                        rewritable_output += f"\n```{raw_cmd}\n"
                        if process_result.stdout is not None:
                            rewritable_output += process_result.stdout[
                                -EXECUTE_OUTPUT_MAX_LEN:
                            ]
                        rewritable_output += "```\n"
                    else:
                        rewritable_output += f"\n```{raw_cmd}\n"
                        if process_result.stderr is not None:
                            rewritable_output += process_result.stderr[
                                -EXECUTE_OUTPUT_MAX_LEN:
                            ]
                        rewritable_output += "```\n"
                live.update(
                    # re.sub(NO_RENDER_PATTERN, "", rewritable_output, flags=re.DOTALL),
                    renderable_output,
                    refresh=refresh,
                )
                if headless:
                    yield renderable_output, False, context
                if should_response_again:
                    break
        context = add_context_to(context, "assistant", rewritable_output)
        if should_response_again:
            context = add_context_to(
                context,
                "system",
                f"你的上一次工具调用已被替换成了调用结果，如果你认为足以回答问题，你应该不再调用工具，直接回答问题，否则你可以继续调用工具",
            )
        if headless:
            yield "", True, context
        if not should_response_again:
            break
    return


async def single_progress(user_input: str, context: Context = None) -> None:
    await single_progress(user_input=user_input, context=context)


async def single_progress_headless(
    user_input: str, context: Context = None
) -> AsyncIterator[tuple[str, bool, Context]]:
    async for item in _single_progress(
        user_input=user_input, context=context, headless=True
    ):
        yield item


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
        async for output, ctx_change, ctx in single_progress_headless(
            i_request.user_input, i_request.context
        ):
            payload = ctx if ctx_change else {"output": output}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/")
@app.get("/index")
@app.get("/index.html")
async def index():
    return FileResponse("./index.html")


if __name__ == "__main__":
    asyncio.run(cli())
