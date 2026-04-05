import os
import uuid
from config import Config
from enum import Enum, auto
import shutil
from pydantic import BaseModel, Field
import asyncio
import aiofiles
from datetime import datetime, timedelta


def folder_to_list(path: str):
    result = []
    for entry in sorted(os.listdir(path)):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            # 文件夹用字典表示，递归获取子内容
            result.append({entry: folder_to_list(full_path)})
        else:
            # 文件直接用字符串
            result.append(entry)
    return result


class InstanceStatus(Enum):
    NOT_READY = auto()
    STOP = auto()
    RUNNING = auto()
    EXITED = auto()


class Algorithm(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = ""
    description: str = ""

    def copy_to(self, target_path: str):
        os.makedirs(target_path, exist_ok=True)
        shutil.copytree(self.path, target_path, dirs_exist_ok=True)

    def tree(self):
        return folder_to_list(self.path)

    @property
    def path(self):
        return os.path.join(Config.algorithm_root_path, self.id)

    def copy_into(self, from_path: str):
        target_path = os.path.join(Config.algorithm_root_path, self.id)
        os.makedirs(target_path, exist_ok=True)
        shutil.copytree(from_path, target_path, dirs_exist_ok=True)

    def save(self):
        os.makedirs(Config.algorithm_root_path, exist_ok=True)
        open(
            os.path.join(
                Config.algorithm_root_path, self.id, Config.algorithm_info_path
            ),
            "w",
            encoding="utf-8",
        ).write(self.model_dump_json(indent=4, ensure_ascii=False))


class Log:
    err_path: str = None
    out_path: str = None
    rotation_bytes: int = Config.log_max_file_size

    def __init__(self, id: str = None):
        if id is None:
            id = str(uuid.uuid4())
        self.id = id
        self.err_path = os.path.join(Config.log_root_path, self.id, Config.log_err_path)
        self.out_path = os.path.join(Config.log_root_path, self.id, Config.log_out_path)
        self.out_file = None
        self.err_file = None
        self.out_inode = None
        self.err_inode = None
        os.makedirs(os.path.dirname(self.err_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)

    async def check_log_err(self):
        if self.err_file is None:
            self.err_file = await aiofiles.open(self.err_path, "ab")
            self.err_inode = os.stat(self.err_path).st_ino
            return

        try:
            current_inode = os.stat(self.err_path).st_ino
        except FileNotFoundError:
            current_inode = None

        if current_inode != self.err_inode:
            await self.err_file.close()
            self.err_file = await aiofiles.open(self.err_path, "ab")
            self.err_inode = os.stat(self.err_path).st_ino
            return

        self.err_file = await self._rotation(self.err_path, self.err_file)

    async def check_log_out(self):
        if self.out_file is None:
            self.out_file = await aiofiles.open(self.out_path, "ab")
            self.out_inode = os.stat(self.out_path).st_ino
            return
        try:
            current_inode = os.stat(self.out_path).st_ino
        except FileNotFoundError:
            current_inode = None
        if current_inode != self.out_inode:
            await self.out_file.close()
            self.out_file = await aiofiles.open(self.out_path, "ab")
            self.out_inode = os.stat(self.out_path).st_ino
            return

        self.out_file = await self._rotation(self.out_path, self.out_file)

    async def _rotation(
        self, path: str, f: aiofiles.threadpool.binary.AsyncBufferedIOBase
    ) -> aiofiles.threadpool.binary.AsyncBufferedIOBase:
        try:
            log_size = await f.tell()
        except FileNotFoundError:
            log_size = 0

        if log_size > self.rotation_bytes:
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d%H%M%S%f")

            await f.close()
            os.rename(path, path + "." + timestamp)

            new_f = await aiofiles.open(path, "ab")

            if path == self.out_path:
                self.out_inode = os.stat(path).st_ino
            elif path == self.err_path:
                self.err_inode = os.stat(path).st_ino

            return new_f

        return f

    async def log_out(self, data: bytes, flush_now: bool = False):
        await self.check_log_out()
        await self.out_file.write(data)
        if flush_now:
            await self.out_file.flush()

    async def log_err(self, data: bytes, flush_now: bool = False):
        await self.check_log_err()
        await self.err_file.write(data)
        if flush_now:
            await self.err_file.flush()

    async def get_out(self, n: int = -1) -> bytes:
        f = await aiofiles.open(self.out_path, "rb")
        return await f.read(n)

    async def get_err(self, n: int = -1) -> bytes:
        f = await aiofiles.open(self.err_path, "rb")
        return await f.read(n)

    async def flush_all(self):
        await self.check_log_out()
        await self.check_log_err()
        await self.out_file.flush()
        await self.err_file.flush()


class Template(BaseModel):
    algorithm: Algorithm
    entry: str = "python main.py"
    restart_always: bool = False
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_temporary: bool = False
    restart_interval_seconds: float = 10

    def save(self):
        if self.is_temporary:
            raise AttributeError()
        os.makedirs(Config.template_root_path, exist_ok=True)
        open(
            os.path.join(Config.template_root_path, self.id + ".json"),
            "w",
            encoding="utf-8",
        ).write(self.model_dump_json(indent=4, ensure_ascii=False))


class Instance:
    id: str = None
    status: InstanceStatus = InstanceStatus.NOT_READY
    start_time: datetime
    template: Template
    log: Log

    def __init__(self, template: Template, id: str = None):
        if id is None:
            id = str(uuid.uuid4())
        self.id = id
        self.template = template.model_copy()
        self.log = Log(id=self.id)
        self.start_time = None

    def restart_check(self) -> bool:
        if not self.template.restart_always:
            return False
        if self.start_time is None:
            return True
        if datetime.now() - self.start_time > timedelta(
            seconds=self.template.restart_interval_seconds
        ):
            return True
        return False

    @property
    def path(self) -> str:
        return os.path.join(Config.instance_root_path, self.id)

    def get_ready(self):
        os.makedirs(self.path, exist_ok=True)
        self.template.algorithm.copy_to(self.path)
        self.status = InstanceStatus.STOP

    def save(self):
        open(
            os.path.join(Config.instance_root_path, self.id, Config.instance_info_path),
            "w",
            encoding="utf-8",
        ).write(self.template.model_dump_json(indent=4, ensure_ascii=False))
