from typing import Any
from entity import Template, Instance, InstanceStatus, Algorithm
import asyncio
import os
from config import Config
import zipfile
import json


def unsafe_peek(stream_reader: asyncio.StreamReader) -> int:
    if stream_reader._buffer:
        return len(stream_reader._buffer)
    return -1


class ProcessManager:
    instances: dict[str, Instance] = None
    processes: dict[str, dict[str, asyncio.subprocess.Process]] = None

    def __init__(self):
        self.processes = dict[str, dict[str, asyncio.subprocess.Process]]()
        self.instances = dict[str, Instance]()

    async def run(self, template: Template) -> str:
        instance = Instance(template)
        self.instances[instance.id] = instance
        self.processes[instance.id] = dict[str, asyncio.subprocess.Process]()
        instance.get_ready()
        await self.exec(instance.id)
        instance.status = InstanceStatus.RUNNING
        return instance.id

    async def exec(self, id: str, entrys: list[str] = None) -> None:
        instance = self.instances[id]
        if entrys is None:
            entrys = instance.template.entry.split(" ")
        process = await asyncio.create_subprocess_exec(
            *entrys,
            cwd=instance.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if len(self.processes[id]) == 0:
            self.processes[id]["0"] = process
        else:
            raise NotImplementedError()

    async def watch(self):
        keys = list(self.processes.keys())
        for iid in keys:
            if iid in self.processes:
                if "0" not in self.processes[iid]:
                    if self.instances[iid].template.restart_always:
                        await self.exec(iid)
                    continue
                proc = self.processes[iid]["0"]
                out_peek_n = unsafe_peek(proc.stdout)
                if out_peek_n > 0:
                    self.instances[iid].log.log_out(await proc.stdout.read(out_peek_n))
                err_peek_n = unsafe_peek(proc.stderr)
                if err_peek_n > 0:
                    self.instances[iid].log.log_err(await proc.stdout.read(err_peek_n))
                if proc.returncode is not None:
                    del self.processes[iid]["0"]
                    self.instances[iid].status = InstanceStatus.EXITED
                self.instances[iid].log.flush_all()

    async def watch_loop(self, interval: float = 0.1):
        while True:
            try:
                await asyncio.sleep(interval)
                await self.watch()
            except KeyboardInterrupt:
                break

    def create_template(
        self,
        algorithm: Algorithm,
        entry: str = "python main.py",
        restart_always: bool = False,
        is_temporary: bool = True,
    ) -> Template:
        template = Template(
            algorithm=algorithm,
            entry=entry,
            restart_always=restart_always,
            is_temporary=is_temporary,
        )
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

    def upload_unzip_algorithm(
        self, zipfile_path: str, version: str = "", description: str = ""
    ) -> Algorithm:
        algorithm = Algorithm(version=version, description=description)
        path = algorithm.path
        os.makedirs(path, exist_ok=True)
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            zip_ref.extractall(path)
        algorithm.save()
        return algorithm


if __name__ == "__main__":

    async def main():
        pm = ProcessManager()
        algo = pm.get_algorithm("yolo")
        print(json.dumps(algo.tree(), indent=4, ensure_ascii=False))
        print(algo.model_dump_json(indent=4))
        template = pm.get_template("yolo")
        print(template.model_dump_json(indent=4))
        id = await pm.run(template)
        await pm.watch_loop()

    asyncio.run(main())
