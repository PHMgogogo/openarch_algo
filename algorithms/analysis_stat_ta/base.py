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
from sklearn.linear_model import LinearRegression


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
    """多维时序线性回归预测模型。

    不进行训练。推理时对输入的 seq_len 条时序数据，每个维度独立拟合一个
    线性回归模型（以时间索引 0..seq_len-1 为自变量），预测下一时刻的值。
    """

    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """逐维度拟合线性回归并预测下一时刻。

        Args:
            x: (batch_size, seq_len, D) 多维时序输入。

        Returns:
            (batch_size, D) 每个维度下一时刻的预测值。
        """
        batch_size, seq_len, D = x.shape
        t = torch.arange(seq_len, dtype=torch.float32).reshape(-1, 1).cpu().numpy()
        t_next = torch.tensor([[seq_len]], dtype=torch.float32).cpu().numpy()
        preds = []
        for b in range(batch_size):
            sample = x[b].cpu().numpy()  # (seq_len, D)
            sample_preds = []
            for d in range(D):
                y = sample[:, d]  # (seq_len,)
                lr = LinearRegression()
                lr.fit(t, y)
                pred = lr.predict(t_next)[0]
                sample_preds.append(float(pred))
            preds.append(sample_preds)
        return torch.tensor(preds, dtype=torch.float32)

    def state_dict(self, *args, **kwargs):
        return {}

    def load_state_dict(self, state_dict, strict=True):
        pass


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


class _TableAsSequenceWrapper(Dataset):
    """将 TableByRowDataset 包装为滑动窗口序列数据集。"""

    def __init__(self, table: TableByRowDataset, seq_len: int):
        self.table = table
        self.seq_len = seq_len

    def __len__(self) -> int:
        return max(0, len(self.table.df) - self.seq_len)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, int]:
        actual_idx = idx + self.seq_len  # idx 指向被预测的那一行
        input_rows = self.table.df.iloc[actual_idx - self.seq_len : actual_idx]
        data = torch.tensor(
            input_rows[self.table.data_cols].values.astype(float),
            dtype=torch.float32,
        )  # (seq_len, D)
        label_row = self.table.df.iloc[actual_idx]
        label_cols = (
            self.table.label_cols
            if self.table.label_cols is not None
            else self.table.data_cols
        )
        label = torch.tensor(
            label_row[label_cols].values.astype(float),
            dtype=torch.float32,
        )  # (D,)
        return data, label, actual_idx


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
    interrupt_signal: typing.Callable[[], bool] = lambda: True,
) -> list[ModelResult]:
    model_result = []
    device = "cpu"
    train = mode == "train"
    if isinstance(data, TableByRowDataset):
        data = _TableAsSequenceWrapper(data, seq_len=16)
    if train:
        return model_result
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
