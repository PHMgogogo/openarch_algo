from __future__ import annotations

import os
import sys
import typing
import uvicorn
import json
import inspect
import openai
import asyncio
import traceback
import dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from agents import TResponseInputItem

dotenv.load_dotenv()
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from .manager import PipelineManager
    from .base import Node, Pipeline, get_all_node_cls, client
    from .agent import run_agent
    from .tools import patch,view,format,get_instructions,PipelineAgentContext
except ImportError:
    from manager import PipelineManager
    from base import Node, Pipeline, get_all_node_cls, client
    from agent import run_agent
    from tools import patch,view,format,get_instructions,PipelineAgentContext

pm = PipelineManager()
_cron_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cron_task
    _cron_task = asyncio.create_task(pm.cron_loop())
    yield
    if _cron_task:
        _cron_task.cancel()
        try:
            await _cron_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

_frontend_dir = os.path.join(_current_dir, "frontend", "dist")


@app.get("/pipeline")
async def list_pipelines():
    return {"data": pm.list_pipeline()}

@app.get("/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    try:
        pipeline = pm.get_pipeline(pipeline_id)
        return pipeline
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pipeline not found")


@app.post("/pipeline")
async def create_pipeline(pipeline: Pipeline):
    pm.save_pipeline(pipeline)
    return {"id": pipeline.id}


@app.put("/pipeline/{pipeline_id}")
async def update_pipeline(pipeline_id: str, pipeline: Pipeline):
    if pipeline.id != pipeline_id:
        raise HTTPException(status_code=400, detail="Pipeline ID mismatch")
    pm.save_pipeline(pipeline)
    return {"id": pipeline.id}


@app.delete("/pipeline/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    try:
        pm.del_pipeline(pipeline_id)
        return {"ok": True}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pipeline not found")


class RenameRequest(BaseModel):
    new_id: str


@app.put("/{pipeline_id}/rename")
async def rename_pipeline(pipeline_id: str, req: RenameRequest):
    try:
        pm.rename_pipeline(pipeline_id, req.new_id)
        return {"id": req.new_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pipeline not found")


class RunRequest(BaseModel):
    init_data: typing.Optional[dict[str, list[typing.Any]]] = None
    init_state: typing.Optional[dict[str, typing.Any]] = None
    return_data_names: typing.Optional[list[str]] = None
    return_state_names: typing.Optional[list[str]] = None
    framework_format: bool = False
    pipeline: typing.Optional[Pipeline] = None


@app.post("/{pipeline_id}/run")
async def run_pipeline_with_id(pipeline_id: str, rreq: RunRequest):
    try:
        pipeline: Pipeline = pm.get_pipeline(pipeline_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    try:
        ctx = await pipeline.arun(init_data=rreq.init_data, init_state=rreq.init_state)
        return ctx.dump(
            return_data=rreq.return_data_names,
            return_state=rreq.return_state_names,
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        )


@app.post("/run")
async def run_pipeline(rreq: RunRequest):
    try:
        ctx = await rreq.pipeline.arun(
            init_data=rreq.init_data, init_state=rreq.init_state
        )
        return ctx.dump(
            return_data=rreq.return_data_names,
            return_state=rreq.return_state_names,
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        )


class CronGenerateRequest(BaseModel):
    prompt: str


class CronGenerateResponse(BaseModel):
    cron: str


@app.post("/cron/generate")
async def cron_generate(req: CronGenerateRequest) -> CronGenerateResponse:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME")
    oclient = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    response = await oclient.responses.create(
        model=model_name,
        input=req.prompt,
        instructions="你是一个 cron 表达式生成助手。根据用户的自然语言需求，生成对应的 cron 表达式。",
        text={
            "format": {
                "type": "json_schema",
                "name": "cron_expression",
                "schema": {
                    "type": "object",
                    "properties": {
                        "cron": {
                            "type": "string",
                            "description": "cron 表达式，由5个字段组成：分 时 日 月 周",
                        }
                    },
                    "required": ["cron"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        },
    )

    try:
        result = json.loads(response.output_text)
        return CronGenerateResponse(cron=result.get("cron", ""))
    except (json.JSONDecodeError, AttributeError):
        return CronGenerateResponse(cron="")


@app.get("/node/types")
def list_node_types():
    node_cls_list = get_all_node_cls()
    return [
        {
            "node_type": cls.__name__,
            "category": (
                cls.model_fields["category"].default
                if "category" in cls.model_fields
                else ""
            ),
        }
        for cls in node_cls_list
    ]


@app.get("/node/schema/{type}")
def node_schema(type: str):
    node_cls = Node._node_registry.get(type)
    if node_cls is None:
        raise HTTPException(status_code=404, detail=f"Node type '{type}' not found")
    return node_cls.model_json_schema()


@app.get("/node/help/{type}")
async def node_help(type: str):
    node_cls = Node._node_registry.get(type)
    if node_cls is None:
        raise HTTPException(status_code=404, detail=f"Node type '{type}' not found")

    source_code = inspect.getsource(node_cls)
    base_source = inspect.getsource(Node)

    params_cls = getattr(node_cls, "Parameters", None)
    try:
        params_schema = json.dumps(
            params_cls.model_json_schema(), ensure_ascii=False, indent=2
        )
    except Exception:
        params_schema = "{}"

    prompt = f"""你是一个节点使用文档生成助手。请根据以下节点的源代码和参数 Schema，生成Help文档：

1. **节点功能**：这个节点是做什么的，在什么场景下使用
2. **使用方法**：如何在流水线中使用这个节点
3. **参数说明**：每个参数的含义、类型和如何填写

---
基类 Node 源代码（所有节点的公共父类）：
```python
{base_source}
```

节点类型：{type}

节点源代码：
```python
{source_code}
```

参数 Schema：
```json
{params_schema}
```

请用中文回答，条理清晰，简洁明了。"""

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME")

    oclient = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generator():
        full_text = ""
        stream = await oclient.responses.create(
            model=model_name,
            input=prompt,
            stream=True,
        )
        async for event in stream:
            if event.type == "response.output_text.delta":
                delta = event.delta
                full_text += delta
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'full': full_text}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


class AgentChatRequest(BaseModel):
    user_input: str
    history: list[dict] = []
    pipeline: Pipeline


@app.post("/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """Stateless agent chat endpoint.

    Frontend sends the full conversation context and pipeline with each request.
    Response is an SSE stream of RunEvent objects (see agent.py).
    """

    async def generator():
        async for event in run_agent(
            history=req.history + [{"role": "user", "content": req.user_input}],
            instructions=get_instructions(),
            tools=[patch,view,format],
            agent_context=PipelineAgentContext(req.pipeline),
        ):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/instance/list")
async def instances():
    return await asyncio.to_thread(client.process.instances.get)


@app.get("/{pipeline_id}/cron/contexts")
async def list_cron_contexts(pipeline_id: str):
    return {"data": pm.list_cron_contexts(pipeline_id)}


@app.get("/{pipeline_id}/cron/contexts/{filename:path}")
async def get_cron_context(pipeline_id: str, filename: str):
    try:
        return pm.get_cron_context(pipeline_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cron context not found")


@app.get("/cron/status")
async def cron_status():
    return {"data": pm.get_cron_status()}


@app.get("/{pipeline_id}/cron/next")
async def cron_next(pipeline_id: str):
    try:
        return pm.get_next_cron_time(pipeline_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pipeline not found")


@app.get("/")
def serve_index():
    index_path = os.path.join(_frontend_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(
        status_code=404, detail="Frontend not built. Run cd frontend && npm run build"
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8008))
    uvicorn.run("asgi:app", host="0.0.0.0", port=port)
