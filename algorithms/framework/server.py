try:
    from . import base
except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(__file__))
    import base
import fastapi
from fastapi.responses import FileResponse
import torch
import enum
from torch import nn, optim
import asyncio
import typing
import tempfile
import os
import csv
from pydantic import BaseModel
from fastapi import FastAPI


class State(str, enum.Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    def __str__(self):
        return self.name

    UNLOADED = enum.auto()
    LOADED = enum.auto()
    TRAINING = enum.auto()
    INFERRING = enum.auto()


class Container:
    model: base.Model = None
    state: State = State.UNLOADED
    criterion: nn.Module = None
    optimizer: optim.Optimizer = None
    epoch_progress: typing.Any = None
    batch_progress: typing.Any = None
    result: list[base.ModelResult] = None
    interrupt: bool = False
    task: asyncio.Task = None

    def __init__(self):
        self.result = []
        self._load()

    def _load(self, path: str | None = "./model.pth") -> None:
        if self.state != State.UNLOADED:
            raise RuntimeError(f"Cannot load from state {self.state}")
        self.model = base.Model()
        if path is not None and os.path.exists(path):
            self.model.load_state_dict(torch.load(path))
        self.state = State.LOADED

    async def load(self, path: str | None = "./model.pth") -> None:
        self._load(path)

    async def unload(self) -> None:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot unload from state {self.state}")
        _m = self.model
        self.model = None
        _c = self.criterion
        self.criterion = None
        _o = self.optimizer
        self.optimizer = None
        del _m, _c, _o
        torch.cuda.empty_cache()
        self.state = State.UNLOADED

    async def save(self, path: str = "./model.pth") -> None:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot save from state {self.state}")
        torch.save(self.model.state_dict(), path)

    def set_criterion(self, criterion: nn.Module) -> None:
        self.criterion = criterion

    def set_optimzer(self, optimizer: optim.Optimizer) -> None:
        self.optimizer = optimizer

    def epoch_callback(self, *args, **kwargs) -> None:
        self.epoch_progress = kwargs

    def batch_callback(self, *args, **kwargs) -> None:
        self.batch_progress = kwargs

    def result_callback(self, *args, **kwargs) -> None:
        if "result" in kwargs:
            self.result.append(kwargs["result"])
        if kwargs.get("done", False):
            self.state = State.LOADED

    def interrupt_signal(self, reset: bool = False) -> bool:
        _i = self.interrupt
        if reset:
            self.interrupt = False
        return _i

    def prepare(self) -> None:
        self.result.clear()
        self.epoch_progress = None
        self.batch_progress = None
        self.interrupt = False

    async def train(
        self,
        data: torch.utils.data.Dataset,
        train_args: base.TrainArgs = base.TrainArgs(),
        detach: bool = False,
    ) -> list[base.ModelResult]:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot start training from state {self.state}")
        self.prepare()
        self.task = asyncio.create_task(
            asyncio.to_thread(
                base.train_or_eval,
                model=self.model,
                data=data,
                criterion=self.criterion,
                optimizer=self.optimizer,
                epoch_callback=self.epoch_callback,
                batch_callback=self.batch_callback,
                result_callback=self.result_callback,
                interrupt_signal=self.interrupt_signal,
                **train_args.model_dump(),
            )
        )
        self.state = State.TRAINING
        if detach:
            return []
        else:
            return await self.task

    async def infer(
        self,
        data: torch.utils.data.Dataset,
        eval_args: base.EvalArgs = base.EvalArgs(),
        detach: bool = False,
    ) -> list[base.ModelResult]:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot start inferring from state {self.state}")
        self.prepare()
        self.task = asyncio.create_task(
            asyncio.to_thread(
                base.train_or_eval,
                model=self.model,
                data=data,
                epoch_callback=self.epoch_callback,
                batch_callback=self.batch_callback,
                result_callback=self.result_callback,
                interrupt_signal=self.interrupt_signal,
                **eval_args.model_dump(),
            )
        )
        self.state = State.INFERRING
        if detach:
            return []
        else:
            return await self.task

    async def wait(self):
        if self.task is not None:
            await self.task

    def done(self) -> bool:
        if self.task is not None:
            return self.task.done()
        else:
            return True


class PathRequest(BaseModel):
    path: str | None = None


class JsonCSV(BaseModel):
    rows: list[list[typing.Any]]

    def write_to_tmp(self) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", newline="", encoding="utf-8", delete=False
        )
        writer = csv.writer(f)
        writer.writerows(self.rows)
        f.close()
        return f.name


class DatasetRequest(BaseModel):
    content_type: typing.Literal["path_csv", "json_csv", "text_csv"]
    content: str | JsonCSV | typing.Any
    data_cols: list[str]
    label_cols: list[str] | None = None

    def get(self) -> base.TableByRowDataset:
        if self.content_type == "path_csv":
            return base.TableByRowDataset(self.content, self.data_cols, self.label_cols)
        elif self.content_type == "json_csv":
            return base.TableByRowDataset(
                self.content.write_to_tmp(), self.data_cols, self.label_cols
            )
        elif self.content_type == "text_csv":
            f = tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", newline="", encoding="utf-8", delete=False
            )
            f.write(self.content)
            f.close()
            return base.TableByRowDataset(f.name, self.data_cols, self.label_cols)


class TrainRequest(BaseModel):
    dataset: DatasetRequest
    args: base.TrainArgs
    detach: bool = False


class InferRequest(BaseModel):
    dataset: DatasetRequest
    args: base.EvalArgs = base.EvalArgs()
    detach: bool = False


class ProgressResponse(BaseModel):
    state: str
    epoch_progress: dict | None
    batch_progress: dict | None
    result: list[base.ModelResult] | None


def create_app() -> FastAPI:
    app = fastapi.FastAPI()
    c = Container()

    @app.exception_handler(Exception)
    async def exception_handler(request: fastapi.Request, exc: Exception):
        return fastapi.responses.JSONResponse(
            status_code=500, content={"detail": str(exc), "type": type(exc).__name__}
        )

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

    @app.post("/save")
    async def save(path_request: PathRequest):
        return await c.save(path_request.path)

    @app.post("/load")
    async def load(path_request: PathRequest):
        return await c.load(path_request.path)

    @app.get("/unload")
    async def unload():
        return await c.unload()

    @app.post("/train")
    async def train(train_request: TrainRequest):
        return await c.train(
            train_request.dataset.get(), train_request.args, train_request.detach
        )

    @app.post("/infer")
    async def infer(infer_request: InferRequest):
        return await c.infer(
            infer_request.dataset.get(), infer_request.args, infer_request.detach
        )

    @app.get("/state/{n}")
    async def state(n: int = 1):
        return ProgressResponse(
            state=str(c.state),
            epoch_progress=c.epoch_progress,
            batch_progress=c.batch_progress,
            result=c.result[-n:],
        )

    @app.get("/wait")
    async def wait():
        return await c.wait()

    @app.get("/stop")
    async def stop():
        c.interrupt = True
        return

    @app.options("/")
    async def options_root_handler():
        return fastapi.responses.Response(status_code=200)

    @app.options("{path:path}", include_in_schema=False)
    async def options_catchall_handler():
        return fastapi.responses.Response(status_code=200)

    return app


# uvicorn server:create_app --factory --port 0
