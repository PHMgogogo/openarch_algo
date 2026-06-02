from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import asyncio
from contextlib import asynccontextmanager
from manager import ProcessManager, AsyncIOWrapper
from entity import Template, Algorithm
from algorithms.openarch_gateway.entity import UrlProxyRule
from algorithms.framework.server import InferRequest,TrainRequest
import uuid
import aiohttp
aclient = aiohttp.ClientSession()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动监控循环
    task = asyncio.create_task(pm.watch_loop())
    try:
        yield
    except Exception as e:
        print(f"Lifespan error: {e}")
    finally:
        # 清理
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

# 创建ProcessManager实例
pm = ProcessManager()

# 挂载静态文件
app.mount("/static", StaticFiles(directory=".", html=True), name="static")


class CreateInstanceRequest(BaseModel):
    template_id: str
    id: Optional[str] = None
    entry: Optional[str] = None


class PathRequest(BaseModel):
    path: str | None


class CatRequest(BaseModel):
    path: str
    offset: int = 0
    length: int = 0
    encoding: Literal["b64img"] | str = "utf-8"
    fmt: Optional[str] = None


class InstanceResponse(BaseModel):
    id: str
    status: str
    template_id: str


class AlgorithmResponse(BaseModel):
    id: str
    version: str
    description: str
    tree: Optional[dict[str, dict | None]] = None


class HighLevelCreateResponse(BaseModel):
    instance_id: str
    entrance: str
    base_url: str
    doc_url: str
    index_url: str
    file_path: str
    help: str


@app.get("/algorithms/{algorithm_id}", response_model=AlgorithmResponse)
async def get_algorithm_detail(algorithm_id: str):
    algorithm = pm.get_algorithm(algorithm_id)
    if not isinstance(algorithm, Algorithm):
        if algorithm is None:
            raise HTTPException(status_code=404, detail="Algorithm not found")
        raise HTTPException(status_code=400, detail="Algorithm prefix is ambiguous")
    return AlgorithmResponse(
        id=algorithm.id,
        version=algorithm.version,
        description=algorithm.description,
        tree=algorithm.tree(),
    )


@app.get("/instances", response_model=List[InstanceResponse])
async def get_instances():
    instances = []
    for iid, instance in pm.instances.items():
        instances.append(
            InstanceResponse(
                id=iid, status=instance.status.name, template_id=instance.template.id
            )
        )
    return instances


@app.get("/algorithms")
async def list_algorithms():
    algorithms = pm.get_algorithm("")
    if isinstance(algorithms, list):
        # get_algorithm returns folder names in algorithms path
        return algorithms
    if algorithms is None:
        return []
    return [algorithms.id]


@app.post("/algorithms/upload", response_model=AlgorithmResponse)
async def upload_algorithm(
    file: UploadFile = File(...),
    version: str = Form(""),
    description: str = Form(""),
    auto_unpack_topdir: bool = Form(True),
):
    # Save the uploaded file temporarily
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
        temp_file.write(await file.read())
        temp_zip_path = temp_file.name

    try:
        # Call the upload_unzip_algorithm method
        algorithm = pm.upload_unzip_algorithm(
            temp_zip_path, version, description, auto_unpack_topdir
        )
        return AlgorithmResponse(
            id=algorithm.id,
            version=algorithm.version,
            description=algorithm.description,
            tree=algorithm.tree(),
        )
    finally:
        # Clean up the temporary file
        os.unlink(temp_zip_path)


@app.post("/algorithms/{algorithm_id}/cat")
async def cat_algorithm_file(algorithm_id: str, cat_request: CatRequest):
    return await pm.cat("algorithm", algorithm_id, **cat_request.model_dump())


@app.post("/instances/{instance_id}/cat")
async def cat_algorithm_file(instance_id: str, cat_request: CatRequest):
    return await pm.cat("instance", instance_id, **cat_request.model_dump())


@app.get("/templates")
async def list_templates():
    templates = pm.get_template("")
    if isinstance(templates, list):
        # filenames like '<id>.json', strip extension
        return [t[:-5] if t.endswith(".json") else t for t in templates]
    if templates is None:
        return []
    return [templates.id]


@app.get("/templates/{template_id}", response_model=Template)
async def get_template_detail(template_id: str):
    template = pm.get_template(template_id)
    if not isinstance(template, Template):
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=400, detail="Template prefix is ambiguous")
    return template


@app.post("/templates", response_model=Template)
async def create_template(request: Template):
    algorithm = pm.get_algorithm(request.algorithm.id)
    if not isinstance(algorithm, Algorithm):
        raise HTTPException(status_code=404, detail="Algorithm not found")
    try:
        template = pm.create_template(**request.model_dump())
    except KeyError:
        raise HTTPException(status_code=409, detail="Template ID already exists")
    return template


@app.post("/instances", response_model=dict)
async def create_instance(request: CreateInstanceRequest):
    template = pm.get_template(request.template_id)
    if not isinstance(template, Template):
        raise HTTPException(status_code=404, detail="Template not found")
    if request.entry:
        template.entry = request.entry
    try:
        instance_id = await pm.run(template, request.id)
    except KeyError:
        raise HTTPException(status_code=409, detail="Instance ID already exists")
    return {"instance_id": instance_id}


@app.get("/instances/{instance_id}", response_model=dict)
async def get_instance(instance_id: str):
    instance = pm.get_instance(instance_id)
    return {
        "id": instance.id,
        "status": instance.status.name,
        "template_id": instance.template.id,
        "logs": {"out": instance.log.out_path, "err": instance.log.err_path},
        "tree": instance.tree(),
    }


@app.get("/instances/{instance_id}/logs/out")
async def get_instance_logs_out(instance_id: str):
    logs = await pm.get_log_out(instance_id)
    return {"logs": logs}


@app.get("/instances/{instance_id}/logs/err")
async def get_instance_logs_err(instance_id: str):
    logs = await pm.get_log_err(instance_id)
    return {"logs": logs}


@app.get("/instances/{instance_id}/connections")
async def get_instance_connections(instance_id: str):
    pcs = await pm.get_process_connections(instance_id)
    return {"connections": pcs}


@app.post("/instances/{instance_id}/stop")
async def stop_instance(instance_id: str, force: bool = False):
    await pm.stop(instance_id, force)
    return {"message": "Instance stopped"}


@app.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, force: bool = True):
    await pm.remove_instance(instance_id, force)
    return {"message": "Instance deleted"}


@app.get("/highlevel")
async def highlevel_create():
    uid = str(uuid.uuid4())
    template = await get_template_detail("framework")
    template.is_temporary = True
    template.id = uid
    if template.rules is None:
        template.rules = []
    template.rules.append(
        UrlProxyRule(
            name=uid,
            order=-1,
            rule_type="PREFIX",
            pattern=f"/{uid}",
            dest_index=[1],
            dest_format="/%s",
            rewrite_host="127.0.0.1:0",
            default_entrance=f"/{uid}/?prefix={uid}",
        )
    )
    entry = template.entry + f" --root-path /{uid}"
    r = await create_template(template)
    await create_instance(CreateInstanceRequest(template_id=uid, id=uid, entry=entry))
    instance = pm.get_instance(uid)
    return HighLevelCreateResponse(
        instance_id=uid,
        entrance=f"./{uid}/openapi.json",
        base_url=f"./{uid}",
        doc_url=f"./{uid}/docs",
        index_url=f"./{uid}?prefix={uid}",
        help=(
            "Algorithm service is now online. "
            "POST {base_url}/load to load a model, "
            "GET {base_url}/openapi.json to learn about other interfaces."
        ),
        file_path=instance.path
    )
@app.delete("/highlevel/{instance_id_or_prefix}")
async def highlevel_delete(instance_id_or_prefix:str):
    return await delete_instance(instance_id=instance_id_or_prefix)

@app.post("/highlevel/{instance_id_or_prefix}/load")
async def highlevel_load(instance_id_or_prefix:str,path_request:PathRequest):
    instance = pm.get_instance(instance_id_or_prefix)
    load_url = f"http://{instance.template.rules[-1].rewrite_host}/load"
    async with aclient.post(load_url,json=path_request.model_dump()) as r:
        await r.text()
    async with aclient.get(f"http://{instance.template.rules[-1].rewrite_host}/state") as r:
        return await r.json()

@app.get("/highlevel/{instance_id_or_prefix}/restart")
async def highlevel_restart(instance_id_or_prefix:str):
    return await pm.stop(instance_id_or_prefix)
@app.post("/highlevel/{instance_id_or_prefix}/infer")
async def highlevel_infer(instance_id_or_prefix:str,infer_request:InferRequest):
    instance = pm.get_instance(instance_id_or_prefix)
    async with aclient.post(f"http://{instance.template.rules[-1].rewrite_host}/infer",json=infer_request.model_dump()) as r:
        await r.text()
    async with aclient.get(f"http://{instance.template.rules[-1].rewrite_host}/wait") as r:
        await r.text()
    async with aclient.get(f"http://{instance.template.rules[-1].rewrite_host}/state") as r:
        return await r.json()
@app.post("/highlevel/{instance_id_or_prefix}/train")
async def highlevel_train(instance_id_or_prefix:str,train_request:TrainRequest):
    instance = pm.get_instance(instance_id_or_prefix)
    async with aclient.post(f"http://{instance.template.rules[-1].rewrite_host}/train",json=train_request.model_dump()) as r:
        await r.text()
    async with aclient.get(f"http://{instance.template.rules[-1].rewrite_host}/wait") as r:
        await r.text()
    async with aclient.get(f"http://{instance.template.rules[-1].rewrite_host}/state") as r:
        return await r.json()
async def attach_ws_recv_loop(instance_id: str, websocket: WebSocket):
    while True:
        data = await websocket.receive_bytes()
        await pm.write_to_proc(instance_id, data)


async def attach_ws_send_loop(
    instance_id: str, iowrapper_id: str, websocket: WebSocket
):
    while True:
        data = await pm.iowrappers[instance_id]["0"][iowrapper_id].read()
        await websocket.send_bytes(data)


@app.websocket("/instances/{instance_id}/attach/{iowrapper_id}")
async def attach_instance(instance_id: str, iowrapper_id: str, websocket: WebSocket):
    iid = pm.get_instance(instance_id).id
    if not iowrapper_id in pm.iowrappers[iid]["0"]:
        pm.iowrappers[iid]["0"][iowrapper_id] = AsyncIOWrapper(iowrapper_id)
    await websocket.accept()
    await asyncio.gather(
        attach_ws_recv_loop(instance_id, websocket),
        attach_ws_send_loop(instance_id, iowrapper_id, websocket),
    )
    return


@app.get("/console")
async def get_console():
    return FileResponse("console.html")


@app.get("{path:path}")
async def read_root():
    return FileResponse("index.html")
