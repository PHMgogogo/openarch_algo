from torch import nn
from torch import optim
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import typing
from tqdm import tqdm
import inspect
from pydantic import BaseModel
import os
from contextlib import nullcontext
import math
from sklearn.ensemble import RandomForestClassifier
import pickle
import io

class TableByRowDataset(Dataset):
    df: pd.DataFrame
    label_cols: list[str]
    data_cols: list[str]
    use_cache: bool
    _cache: dict[int, tuple[torch.Tensor, torch.Tensor]]

    def __init__(
        self,
        csv_path: str,
        data_cols: list[str],
        label_cols: list[str] | None = None,
        use_cache: bool = True,
    ) -> None:
        self.df = pd.read_csv(csv_path)
        self.label_cols = label_cols
        self.data_cols = data_cols
        self.use_cache = use_cache
        self._cache = {}  # idx -> (data, label)

    def __len__(self) -> int:
        return len(self.df)

    def _load_row(
        self, idx: int, device: str = "cpu"
    ) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.df.iloc[idx]
        data = torch.tensor(
            row[self.data_cols].values.astype(float), dtype=torch.float32, device=device
        )
        if self.label_cols is None:
            label = data
        else:
            label = torch.tensor(
                row[self.label_cols].values.astype(float),
                dtype=torch.float32,
                device=device,
            )
        return data, label

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, int]:
        if self.use_cache and idx in self._cache:
            return *self._cache[idx], idx
        item = self._load_row(idx)
        if self.use_cache:
            self._cache[idx] = item
        return *item, idx

    def warmup(self, device: str = "cpu") -> None:
        for idx in range(len(self)):
            if idx not in self._cache:
                self._cache[idx] = self._load_row(idx, device)
        return self

    def clear(self) -> None:
        self._cache.clear()


class ModelResult(BaseModel):
    loss: float
    outputs: list[list[float]]
    ids: list[int]
    description: str = ""

    def code(self) -> str:
        return inspect.getsource(self.__class__)


# <model-content>
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.rf = RandomForestClassifier(
            n_estimators=100, max_depth=None, random_state=0
        )

    def fit(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        self.rf.fit(x.cpu().numpy(), y.cpu().numpy().ravel())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        result = self.rf.predict(x.cpu().numpy())
        result = torch.as_tensor(result, dtype=torch.float32).unsqueeze(-1)
        return result

    def state_dict(self, *args, **kwargs):
        buf = io.BytesIO()
        pickle.dump(self.rf, buf)
        return {"rf_pickle": buf.getvalue()}

    def load_state_dict(self, state_dict, strict=True):
        self.rf = pickle.loads(state_dict["rf_pickle"])


# </model-content>


class TrainOrEvalArgs(BaseModel):
    batch_size: int = 1
    device: typing.Literal["cpu", "cuda"] | str = "cpu"
    progress: bool = False
    mode: typing.Literal["train", "eval"]
    shuffle: bool = True


class TrainArgs(TrainOrEvalArgs):
    epoch: int = 1
    learning_rate: float = 1e-3
    mode: typing.Literal["train"] = "train"
    shuffle: bool = True


class EvalArgs(TrainOrEvalArgs):
    mode: typing.Literal["eval"] = "eval"
    shuffle: bool = False


# <train-or-eval-content>
def train_or_eval(
    model: Model,
    data: torch.utils.data.Dataset,
    mode: typing.Literal["train", "eval"] = "eval",
    epoch: int = 10,
    batch_size: int = 1,
    learning_rate: float = 1e-3,
    device: str = "cpu",
    shuffle: bool = True,
    criterion: nn.Module = None,
    optimizer: optim.Optimizer = None,
    progress: bool = True,
    epoch_callback: typing.Callable[..., None] = lambda *args, **kwargs: None,
    batch_callback: typing.Callable[..., None] = lambda *args, **kwargs: None,
    result_callback: typing.Callable[..., None] = lambda *args, **kwargs: None,
    interrupt_signal: typing.Callable[[], bool] = lambda: False,
) -> list[ModelResult]:
    model_result = []
    train = mode == "train"
    device = "cpu"
    if train:
        data_loader = DataLoader(data, len(data), shuffle=shuffle)
        batch_data, batch_labels, batch_ids = next(iter(data_loader))
        model.fit(batch_data, batch_labels)
        epoch = 1
    else:
        epoch = 1
        model.eval()
    if criterion is None:
        criterion = nn.MSELoss()

    model = model.to(device)
    data_loader = DataLoader(data, batch_size, shuffle=shuffle)
    null_f = None if progress else open(os.devnull, "w")
    epoch_progress = tqdm(range(epoch), file=null_f)
    with torch.no_grad() if not train else nullcontext():
        for ep in epoch_progress:
            epoch_callback(**epoch_progress.format_dict)
            total_loss = 0
            outputs_list = list[list[float]]()
            ids_list = list[int]()
            batch_progress = tqdm(data_loader, file=null_f)
            for item in batch_progress:
                batch_data, batch_labels, batch_ids = item
                ids_list.extend(batch_ids)
                if interrupt_signal():
                    result_callback(done=True)
                    return model_result
                batch_callback(**batch_progress.format_dict)
                batch_data = batch_data.to(device)
                batch_labels = batch_labels.to(device)
                outputs: torch.Tensor = model(batch_data)
                outputs_list.extend(outputs.nan_to_num(0).tolist())
                loss: torch.Tensor = criterion(outputs, batch_labels)
                total_loss += loss.item()
            avg_loss = total_loss / len(data)
            if math.isnan(avg_loss):
                avg_loss = 0
            r = ModelResult(loss=avg_loss, outputs=outputs_list, ids=ids_list)
            if mode == "eval":
                r.description = "Eval loss is computed with label = 0 while label cols were not specified."
            model_result.append(r)
            result_callback(result=r)
            batch_callback(**batch_progress.format_dict)
            tqdm.write(f"Epoch {ep}: Loss {avg_loss}", null_f)
    epoch_callback(**epoch_progress.format_dict)
    result_callback(done=True)
    return model_result


# </train-or-eval-content>
