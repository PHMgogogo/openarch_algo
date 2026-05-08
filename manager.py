from entity import (
    Template,
    Instance,
    InstanceStatus,
    Algorithm,
    ProcessConnection,
    FileMetaInfo,
)
import asyncio
import os
from config import Config
import zipfile
from datetime import datetime
from algorithms.openarch_gateway.entity import UrlProxyRule
import uuid
import psutil
from client import service
import typing
import base64
import traceback


def unsafe_peek(stream_reader: asyncio.StreamReader) -> int:
    if stream_reader and stream_reader._buffer:
        return len(stream_reader._buffer)
    return -1


class ServiceHelper:
    rules_tobe_add: asyncio.Queue[tuple[str, UrlProxyRule, BaseException, int]]
    interval: float = 1
    counter: float = 0
    task: asyncio.Task

    def __init__(self, interval: float = 1):
        self.rules_tobe_add = asyncio.Queue[
            tuple[str, UrlProxyRule, BaseException, int]
        ]()
        self.interval = interval
        self.task = None

    def add(self, instance_id: str, upr: UrlProxyRule):
        self.rules_tobe_add.put_nowait((instance_id, upr, None, 0))

    async def _watch(self):
        l = self.rules_tobe_add.qsize()
        for _ in range(l):
            iid, upr, e, retry = await self.rules_tobe_add.get()
            try:
                await asyncio.to_thread(service.add, **upr.model_dump())
            except BaseException as e:
                self.rules_tobe_add.put_nowait((iid, upr, e, retry + 1))
                # traceback.print_exc()
                print(e)

    async def watch(self, interval: float = 0.04):
        self.counter += interval
        if self.counter > self.interval:
            self.counter = 0
            if self.task is not None and not self.task.done():
                return
            else:
                self.task = asyncio.create_task(self._watch())


class AsyncIOWrapper:
    output: bytearray
    output_ready: asyncio.Event
    MAX_OUTPUT_LENGTH: int = 20480
    _task: asyncio.Task
    id: str

    def __init__(self, id: str = None):
        self.output = bytearray()
        self.output_ready = asyncio.Event()
        if id is None:
            id = str(uuid.uuid4())
        self.id = id

    async def read(self) -> bytes:
        await self.output_ready.wait()
        _output = self.output.copy()
        self.output.clear()
        self.output_ready.clear()
        return _output

    async def read_from_proc(self, data: bytes) -> None:
        self.output.extend(data)
        self.output = self.output[-self.MAX_OUTPUT_LENGTH :]
        self.output_ready.set()


class ProcessManager:
    instances: dict[str, Instance] = None
    processes: dict[str, dict[str, asyncio.subprocess.Process]] = None
    iowrappers: dict[str, dict[str, dict[str, AsyncIOWrapper]]] = None  # iid,"0",uid
    lateload_instance_names: set[str] = None
    service_helper: ServiceHelper

    def __init__(self):
        self.processes = dict[str, dict[str, asyncio.subprocess.Process]]()
        self.instances = dict[str, Instance]()
        self.iowrappers = dict[str, dict]()
        self.lateload_instance_names = set[str]()
        self.service_helper = ServiceHelper()
        self.load_instances_from_path()

    def load_instance_from_path(self, instance_name: str) -> None:
        if instance_name not in self.instances:
            instance_info_path = os.path.join(
                Config.instance_root_path,
                instance_name,
                Config.instance_info_path,
            )
            if not os.path.exists(instance_info_path):
                return
            else:
                instance_template = Template.model_validate_json(
                    open(
                        os.path.join(
                            Config.instance_root_path,
                            instance_name,
                            Config.instance_info_path,
                        ),
                        encoding="utf-8",
                    ).read()
                )
                self.create_instance(instance_template, instance_name)

    def load_instances_from_path(self) -> None:
        os.makedirs(Config.instance_root_path, exist_ok=True)
        instances = os.listdir(Config.instance_root_path)
        for instance_name in instances:
            self.load_instance_from_path(instance_name)

    def create_instance(self, template: Template, id: str = None) -> str:
        if id is not None and id in self.instances:
            raise KeyError()
        instance = Instance(template, id)
        for rule in template.rules:
            self.service_helper.add(instance.id, rule)
        self.instances[instance.id] = instance
        self.processes[instance.id] = dict[str, asyncio.subprocess.Process]()
        self.iowrappers[instance.id] = dict[str, dict[str, dict[str, AsyncIOWrapper]]]()
        instance.status = InstanceStatus.STOP
        return instance.id

    async def remove_instance(self, id_or_prefix: str, force: bool = False) -> None:
        instance = self.get_instance(id_or_prefix)
        await self.stop(instance.id, force)
        for rule in instance.template.rules:
            try:
                service.delete(rule.name)
            except:
                pass
        await instance.clear()
        del self.instances[instance.id]
        del self.processes[instance.id]
        del self.iowrappers[instance.id]

    async def stop(self, id_or_prefix: str, force: bool = False) -> str:
        instance = self.get_instance(id_or_prefix)
        if "0" in self.processes[instance.id]:
            proc = self.processes[instance.id]["0"]
            if force:
                proc.kill()
            else:
                proc.terminate()
            await proc.wait()
        return instance.id

    async def run(self, template: Template, id: str = None) -> str:
        instance = self.instances[self.create_instance(template, id)]
        instance.save()
        await self.exec(instance.id)
        await instance.get_ready()
        return instance.id

    async def cat(
        self,
        type: typing.Literal["algorithm", "instance"],
        id: str,
        path: str,
        offset: int = 0,
        length: int = 1024,
        encoding: typing.Literal["b64img"] | str = "utf-8",
        fmt: str = None,
    ) -> FileMetaInfo:
        target = self.get_instance if type == "instance" else self.get_algorithm
        if fmt is not None:
            encoding = "b64img"
        if encoding == "b64img":
            length = -1
        data, fmi = await target(id).cat(path, offset, length)
        if encoding == "b64img":
            fmi.file_type = "image"
            ext = os.path.splitext(path)[1].lower()
            if (fmt is not None) and (not fmt.startswith(".")):
                ext = "." + fmt
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
                ".ico": "image/ico",
                ".dib": "image/bmp",
                ".icns": "image/icns",
                ".sgi": "image/sgi",
                ".j2c": "image/jp2",
                ".j2k": "image/jp2",
                ".jp2": "image/jp2",
                ".jpc": "image/jp2",
                ".jpf": "image/jp2",
                ".jpx": "image/jp2",
            }
            b64_data = base64.b64encode(data).decode("ascii")
            fmi.chunk_content = f"data:{mime_type[ext]};base64,{b64_data}"
        else:
            fmi.chunk_content = data.decode(encoding=encoding, errors="ignore")
        return fmi

    async def exec(self, id: str, entrys: list[str] = None) -> None:
        instance = self.instances[id]
        if entrys is None:
            entrys = instance.template.entry.split(" ")
        if "0" in self.processes[id]:
            raise KeyError()
        process = await asyncio.create_subprocess_exec(
            *entrys,
            cwd=instance.path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self.processes[id]["0"] = process
        self.iowrappers[id]["0"] = dict[str, AsyncIOWrapper]()
        instance.status = InstanceStatus.RUNNING
        instance.start_time = datetime.now()

    async def get_log_out(
        self, instance_id_or_prefix: str, encoding: str = "utf-8"
    ) -> str:
        instance = self.get_instance(instance_id_or_prefix)
        out_bytes = await instance.log.get_out()
        return out_bytes.decode(encoding, errors="ignore")

    async def get_log_err(
        self, instance_id_or_prefix: str, encoding: str = "utf-8"
    ) -> str:
        instance = self.get_instance(instance_id_or_prefix)
        out_bytes = await instance.log.get_err()
        return out_bytes.decode(encoding, errors="ignore")

    async def watch(self):
        keys = list(self.processes.keys())
        for iid in keys:
            if iid in self.processes:
                if "0" not in self.processes[iid]:
                    if self.instances[iid].restart_check():
                        await self.exec(iid)
                    continue
                proc = self.processes[iid]["0"]
                # log out data
                if (out_peek_n := unsafe_peek(proc.stdout)) > 0:
                    data = await proc.stdout.read(out_peek_n)
                    await self.instances[iid].log.log_out(data)
                    for wrapper in self.iowrappers[iid]["0"].values():
                        await wrapper.read_from_proc(data)
                # log err data
                if (err_peek_n := unsafe_peek(proc.stderr)) > 0:
                    data = await proc.stderr.read(err_peek_n)
                    await self.instances[iid].log.log_err(data)
                    for wrapper in self.iowrappers[iid]["0"].values():
                        await wrapper.read_from_proc(data)
                if proc.returncode is not None:
                    del self.processes[iid]["0"]
                    del self.iowrappers[iid]["0"]
                    self.instances[iid].status = InstanceStatus.EXITED
                await self.instances[iid].log.flush_all()

    async def write_to_proc(self, instance_id: str, data: bytes, flush: bool = True):
        self.processes[instance_id]["0"].stdin.write(data)
        if flush:
            await self.processes[instance_id]["0"].stdin.drain()

    async def watch_loop(self, interval: float = 0.04):
        while True:
            try:
                await asyncio.sleep(interval)
                await self.watch()
                await self.service_helper.watch(interval)
            except KeyboardInterrupt:
                break

    def delete_template(self, id_or_prefix: str) -> Template:
        template = self.get_template(id_or_prefix)
        if not isinstance(template, Template):
            raise KeyError(template)
        template.delete()
        return template

    def create_template(
        self,
        algorithm: Algorithm,
        id: str = None,
        entry: str = "python main.py",
        restart_always: bool = False,
        is_temporary: bool = True,
        volume: bool = False,
        restart_interval_seconds: float = 10,
        rules: list[UrlProxyRule] = [],
    ) -> Template:
        if id is not None:
            existing = self.get_template(id)
            if isinstance(existing, Template):
                raise KeyError()
        template = Template(
            algorithm=algorithm,
            entry=entry,
            restart_always=restart_always,
            is_temporary=is_temporary,
            volume=volume,
            restart_interval_seconds=restart_interval_seconds,
            rules=rules,
        )
        if id is not None:
            template.id = id
        if not is_temporary:
            template.save()
        return template

    def get_template(self, id_or_prefix: str) -> list[str] | Template | None:
        starts_with = list[str]()
        filenames = os.listdir(Config.template_root_path)
        for fn in filenames:
            if fn.startswith(id_or_prefix):
                starts_with.append(fn)
        if len(starts_with) == 1:
            f_path = os.path.join(Config.template_root_path, starts_with[0])
            return Template.model_validate_json(
                open(
                    f_path,
                    encoding="utf-8",
                ).read()
            )
        elif len(starts_with) < 1:
            return None
        else:
            return starts_with

    def get_algorithm(self, id_or_prefix: str) -> list[str] | Algorithm | None:
        starts_with = list[str]()
        filenames = os.listdir(Config.algorithm_root_path)
        for fn in filenames:
            if fn.startswith(id_or_prefix):
                starts_with.append(fn)
        if len(starts_with) == 1:
            f_path = os.path.join(
                Config.algorithm_root_path, starts_with[0], Config.algorithm_info_path
            )
            if not os.path.exists(f_path):
                algo = Algorithm(id=starts_with[0])
                algo.save()
            return Algorithm.model_validate_json(open(f_path, encoding="utf-8").read())
        elif len(starts_with) < 1:
            return None
        else:
            return starts_with

    def get_instance(self, id_or_prefix: str) -> list[str] | Instance | None:
        starts_with = list[str]()
        filenames = os.listdir(Config.instance_root_path)
        for fn in filenames:
            if fn.startswith(id_or_prefix):
                starts_with.append(fn)
        if len(starts_with) == 1:
            return self.instances[starts_with[0]]
        elif len(starts_with) < 1:
            return None
        else:
            return starts_with

    async def get_process_connections(
        self, instance_id_or_prefix: str
    ) -> list[ProcessConnection] | None:
        instance = self.get_instance(instance_id_or_prefix)
        if not isinstance(instance, Instance):
            return None
        if "0" not in self.processes[instance.id]:
            return None
        pid = self.processes[instance.id]["0"].pid
        p = psutil.Process(pid)
        children = [p] + p.children(True)
        result = []
        for child in children:
            conns = []
            for conn in child.net_connections("all"):
                conn_dict = conn._asdict()
                for k, v in conn_dict.items():
                    if hasattr(v, "name"):
                        conn_dict[k] = v.name
                    elif hasattr(v, "_asdict"):
                        conn_dict[k] = v._asdict()
                    elif isinstance(v, tuple):
                        conn_dict[k] = None
                conns.append(conn_dict)
            result.append(
                ProcessConnection(pid=child.pid, name=child.name(), conns=conns)
            )
        return result

    def upload_unzip_algorithm(
        self,
        zipfile_path: str,
        version: str = "",
        description: str = "",
        auto_unpack_topdir: bool = True,
    ) -> Algorithm:
        algorithm = Algorithm(version=version, description=description)
        path = algorithm.path
        os.makedirs(path, exist_ok=True)
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            zip_ref.extractall(path)

        if auto_unpack_topdir:
            items = os.listdir(path)
            if len(items) == 1:
                single_item = items[0]
                single_item_path = os.path.join(path, single_item)
                if os.path.isdir(single_item_path):
                    for item in os.listdir(single_item_path):
                        src = os.path.join(single_item_path, item)
                        dst = os.path.join(path, item)
                        if os.path.isdir(src):
                            os.rename(src, dst)
                        else:
                            os.rename(src, dst)
                    os.rmdir(single_item_path)

        algorithm.save()
        return algorithm


if __name__ == "__main__":

    async def main():
        pm = ProcessManager()
        # algo = pm.get_algorithm("yolo")
        # print(json.dumps(algo.tree(), indent=4, ensure_ascii=False))
        # print(algo.model_dump_json(indent=4))
        # template = pm.get_template("yolo")
        # print(template.model_dump_json(indent=4))
        # id = await pm.run(template)
        # await pm.run(pm.get_template("yolo"))
        # await pm.run(pm.get_template("hello"))
        await pm.watch_loop()

    asyncio.run(main())
