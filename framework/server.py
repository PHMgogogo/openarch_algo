try:
    from . import base
except ImportError:
    import base
import fastapi
import torch
import enum
from torch import nn, optim
import asyncio
import typing


class State(str, enum.Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

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

    async def load(self, path: str | None = None) -> None:
        if self.state != State.UNLOADED:
            raise RuntimeError(f"Cannot load from state {self.state}")
        self.model = base.Model()
        if path is not None:
            self.model.load_state_dict(path)
        self.state = State.LOADED

    async def unload(self) -> None:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot unload from state {self.state}")
        _m = self.model
        self.model = None
        del _m
        torch.cuda.empty_cache()
        self.state = State.UNLOADED

    async def save(self, path: str) -> None:
        if self.state != State.LOADED:
            raise RuntimeError(f"Cannot save from state {self.state}")
        torch.save(self.model.state_dict(), path)

    def set_criterion(self, criterion: nn.Module) -> None:
        self.criterion = criterion

    def epoch_callback(self, *args, **kwargs) -> None:
        self.epoch_progress = kwargs

    def batch_callback(self, *args, **kwargs) -> None:
        self.batch_progress = kwargs

    def result_callback(self, *args, **kwargs) -> None:
        if "result" in kwargs:
            self.result.append(kwargs["result"])
        if kwargs.get("done", False):
            self.state = State.LOADED

    def set_optimzer(self, optimzer: optim.Optimizer) -> None:
        self.optimizer = self.optimizer

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

    async def wait(self):
        if self.task is not None:
            await self.task

    def done(self) -> bool:
        if self.task is not None:
            return self.task.done()
        else:
            return True


app = fastapi.FastAPI()


async def main():

    c = Container()
    await c.load()
    data = base.TableByRowDataset("../example/sqrt.csv", label_cols=["y"])
    await c.train(data, base.TrainArgs(epoch=100), detach=True)
    while not c.done():
        print(c.batch_progress)
        print(c.epoch_progress)
        print()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
