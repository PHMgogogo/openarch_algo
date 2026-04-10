import os
import uuid
from config import Config
from enum import Enum, auto
import shutil
from pydantic import BaseModel, Field
import asyncio
import aiofiles
from datetime import datetime, timedelta
import shutil
import sys
import re
from algorithms.openarch_gateway.entity import UrlProxyRule
from client import service


def folder_to_list(path: str):
    result = {}
    for entry in sorted(os.listdir(path)):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            result[entry] = folder_to_list(full_path)
        else:
            result[entry] = None
    return result


class InstanceStatus(Enum):
    NOT_READY = auto()
    STOP = auto()
    RUNNING = auto()
    EXITED = auto()


class Algorithm(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), pattern=r"^[A-Za-z0-9_-]+$"
    )
    version: str = ""
    description: str = ""

    async def copy_to(self, target_path: str):
        os.makedirs(target_path, exist_ok=True)
        await asyncio.to_thread(
            shutil.copytree, self.path, target_path, dirs_exist_ok=True
        )

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

    async def cat(self, path: str, max_len: int = 20480) -> bytes:
        f = await aiofiles.open(os.path.join(self.path, path), "rb")
        return await f.read(max_len)


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

    @property
    def path(self) -> str:
        return os.path.join(Config.log_root_path, self.id)

    async def clear(self):
        if self.out_file is not None:
            await self.out_file.close()
        if self.err_file is not None:
            await self.err_file.close()
        shutil.rmtree(self.path)


class Template(BaseModel):
    algorithm: Algorithm
    entry: str = "python main.py"
    restart_always: bool = False
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), pattern=r"^[A-Za-z0-9_-]+$"
    )
    is_temporary: bool = False
    restart_interval_seconds: float = 10
    volume: bool = False
    rules: list[UrlProxyRule] = []

    def save(self):
        if self.is_temporary:
            raise AttributeError()
        os.makedirs(Config.template_root_path, exist_ok=True)
        open(
            os.path.join(Config.template_root_path, self.id + ".json"),
            "w",
            encoding="utf-8",
        ).write(self.model_dump_json(indent=4, ensure_ascii=False))


async def softlink_dir_platform(src_dir: str, dst_dir: str):
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)
    if not os.path.isdir(src_dir):
        raise ValueError(f"src_dir does not exist or is not a directory: {src_dir}")

    if os.path.exists(dst_dir):
        raise FileExistsError(f"dst_dir already exists: {dst_dir}")
    parent = os.path.dirname(dst_dir)
    if not os.path.isdir(parent):
        raise FileNotFoundError(f"Parent directory does not exist: {parent}")
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "mklink", "/J", dst_dir, src_dir]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"mklink failed: {stderr.decode().strip()}")
    else:
        os.symlink(src_dir, dst_dir, target_is_directory=True)


async def unlink_dir_platform(path: str):
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"path does not exist: {path}")

    if os.path.islink(path):
        os.unlink(path)
        return
    if sys.platform == "win32":
        proc = await asyncio.create_subprocess_exec(
            *["cmd", "/c", "rmdir", path],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to remove junction: {stderr.decode().strip()}")
    else:
        raise ValueError(f"Path is not a symlink: {path}")


class Instance:
    id: str = None
    status: InstanceStatus = InstanceStatus.NOT_READY
    start_time: datetime
    template: Template
    log: Log

    def __init__(self, template: Template, id: str = None):
        pattern = r"^[A-Za-z0-9_-]+$"
        if id is None:
            id = str(uuid.uuid4())
        if not re.match(pattern, id):
            raise ValueError(
                f"Invalid id '{id}', only letters, numbers, underscore and hyphen are allowed (pattern: {pattern})"
            )
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

    async def get_ready(self):
        for rule in self.template.rules:
            service.add(
                name=rule.name,
                order=rule.order,
                rule_type=rule.rule_type,
                pattern=rule.pattern,
                dest_index=rule.dest_index,
                rewrite_host=rule.rewrite_host,
                editable=rule.editable,
                timeout=rule.timeout,
                enable=rule.enable,
                file_serve_root_path=rule.file_serve_root_path,
            )
        if self.template.volume:
            await softlink_dir_platform(self.template.algorithm.path, self.path)
        else:
            os.makedirs(self.path, exist_ok=True)
            await self.template.algorithm.copy_to(self.path)
        self.status = InstanceStatus.STOP

    def save(self):
        open(
            os.path.join(Config.instance_root_path, self.id, Config.instance_info_path),
            "w",
            encoding="utf-8",
        ).write(self.template.model_dump_json(indent=4, ensure_ascii=False))

    async def clear(self):
        await self.log.clear()
        for rule in self.template.rules:
            try:
                service.delete(rule.name)
            except:
                pass
        if self.template.volume:
            await unlink_dir_platform(self.path)
        else:
            shutil.rmtree(self.path)
