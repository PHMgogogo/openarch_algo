from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager
from manager import ProcessManager
from entity import Template, Algorithm
from algorithms.openarch_gateway.entity import UrlProxyRule

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


class CreateTemplateRequest(BaseModel):
    algorithm_id: str
    id: Optional[str] = None
    entry: Optional[str] = "python main.py"
    restart_always: bool = False
    is_temporary: bool = False
    volume: bool = False
    restart_interval_seconds: Optional[float] = 10
    rules: Optional[List[UrlProxyRule]] = None


class CreateInstanceRequest(BaseModel):
    template_id: str
    id: Optional[str] = None
    entry: Optional[str] = None


class InstanceResponse(BaseModel):
    id: str
    status: str
    template_id: str


class TemplateResponse(BaseModel):
    id: str
    algorithm_id: str
    entry: str
    restart_always: bool
    is_temporary: bool
    volume: bool
    restart_interval_seconds: float


class AlgorithmResponse(BaseModel):
    id: str
    version: str
    description: str
    tree: Optional[dict[str, dict | None]] = None


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


@app.get("/templates")
async def list_templates():
    templates = pm.get_template("")
    if isinstance(templates, list):
        # filenames like '<id>.json', strip extension
        return [t[:-5] if t.endswith(".json") else t for t in templates]
    if templates is None:
        return []
    return [templates.id]


@app.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template_detail(template_id: str):
    template = pm.get_template(template_id)
    if not isinstance(template, Template):
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=400, detail="Template prefix is ambiguous")
    return TemplateResponse(
        id=template.id,
        algorithm_id=template.algorithm.id,
        entry=template.entry,
        restart_always=template.restart_always,
        is_temporary=template.is_temporary,
        volume=template.volume,
        restart_interval_seconds=template.restart_interval_seconds,
    )


@app.post("/templates", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest):
    algorithm = pm.get_algorithm(request.algorithm_id)
    if not isinstance(algorithm, Algorithm):
        raise HTTPException(status_code=404, detail="Algorithm not found")
    try:
        template = pm.create_template(
            algorithm=algorithm,
            id=request.id,
            entry=request.entry,
            restart_always=request.restart_always,
            is_temporary=request.is_temporary,
            volume=request.volume,
            restart_interval_seconds=request.restart_interval_seconds,
        )
    except KeyError:
        raise HTTPException(status_code=409, detail="Template ID already exists")
    return TemplateResponse(
        id=template.id,
        algorithm_id=template.algorithm.id,
        entry=template.entry,
        restart_always=template.restart_always,
        is_temporary=template.is_temporary,
        volume=template.volume,
        restart_interval_seconds=template.restart_interval_seconds,
    )


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
    }


@app.get("/instances/{instance_id}/logs/out")
async def get_instance_logs_out(instance_id: str):
    logs = await pm.get_log_out(instance_id)
    return {"logs": logs}


@app.get("/instances/{instance_id}/logs/err")
async def get_instance_logs_err(instance_id: str):
    logs = await pm.get_log_err(instance_id)
    return {"logs": logs}


@app.post("/instances/{instance_id}/stop")
async def stop_instance(instance_id: str, force: bool = False):
    await pm.stop(instance_id, force)
    return {"message": "Instance stopped"}


@app.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, force: bool = False):
    await pm.remove_instance(instance_id, force)
    return {"message": "Instance deleted"}


@app.get("/")
async def read_root():
    return FileResponse("index.html")
