import os
import uuid
from config import Config
from enum import Enum, auto
import shutil
from pydantic import BaseModel, Field


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
    def __init__(self, id: str = None):
        if id is None:
            id = str(uuid.uuid4())
        self.id = id

        self.err_dir = os.path.join(Config.log_root_path, self.id)
        self.out_dir = os.path.join(Config.log_root_path, self.id)
        os.makedirs(self.err_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)

        self.err_file_index = 0
        self.out_file_index = 0

        self.err_buffer = bytearray()
        self.out_buffer = bytearray()

        self.err_path = self._next_err_path()
        self.out_path = self._next_out_path()

    def _next_err_path(self):
        return os.path.join(self.err_dir, f"error_{self.err_file_index}.log")

    def _next_out_path(self):
        return os.path.join(self.out_dir, f"output_{self.out_file_index}.log")

    def _write_file(self, path, data):
        with open(path, "ab") as f:
            f.write(data)

    def _flush_buffer(self, buffer, path, file_index_attr):
        while len(buffer) >= Config.log_buffer_size:
            to_write = buffer[: Config.log_buffer_size]
            buffer[: Config.log_buffer_size] = b""
            self._write_file(path, to_write)
            if os.path.getsize(path) >= Config.log_max_file_size:
                setattr(self, file_index_attr, getattr(self, file_index_attr) + 1)
                if file_index_attr == "err_file_index":
                    self.err_path = self._next_err_path()
                else:
                    self.out_path = self._next_out_path()

    def log_out(self, data: bytes) -> None:
        self.out_buffer.extend(data)
        self._flush_buffer(self.out_buffer, self.out_path, "out_file_index")

    def log_err(self, data: bytes) -> None:
        self.err_buffer.extend(data)
        self._flush_buffer(self.err_buffer, self.err_path, "err_file_index")

    def flush_all(self):
        if self.out_buffer:
            self._write_file(self.out_path, self.out_buffer)
            self.out_buffer.clear()
        if self.err_buffer:
            self._write_file(self.err_path, self.err_buffer)
            self.err_buffer.clear()


class Template(BaseModel):
    algorithm: Algorithm
    entry: str = "python main.py"
    restart_always: bool = False
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_temporary: bool = False

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
    path: str
    id: str = None
    status: InstanceStatus = InstanceStatus.NOT_READY
    template: Template
    log: Log

    def __init__(self, template: Template, id: str = None):
        if id is None:
            id = str(uuid.uuid4())
        self.id = id
        self.template = template

    def get_ready(self):
        self.log = Log(self.id)
        self.path = os.path.join(Config.instance_root_path, self.id)
        os.makedirs(self.path, exist_ok=True)
        self.template.algorithm.copy_to(self.path)
        self.status = InstanceStatus.STOP
