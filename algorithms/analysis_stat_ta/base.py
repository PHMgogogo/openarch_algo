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
import numpy as np
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
    """多维时序傅里叶级数预测模型。

    训练时对整条序列的每个维度独立拟合一个傅里叶级数
    （以时间索引 0..N-1 为自变量），基函数为：
        1, t, sin(2πt/p), cos(2πt/p)  （p 遍历一组固定周期）
    并把拟合系数保存到模型参数中。推理时直接根据下标用拟合好的傅里叶级数
    预测未来数据（与输入序列等长），不依赖模型自身的输出（非自回归）。

    相比多项式回归，傅里叶基函数能捕捉周期/振荡信号，拟合贴合数据，
    外推时周期性自然延续，预测起点与真实数据连续衔接。
    """

    # 覆盖常见周期的固定周期组（单位：样本数）
    PERIODS = [40, 60, 80, 100, 120, 150, 180, 200, 250, 300, 400, 500, 800, 1000, 2000]

    def __init__(self):
        super().__init__()
        # 每个维度的傅里叶系数，shape (D, n_basis)。
        # 基函数顺序：1, t, 然后每个周期 p 的 sin(2πt/p), cos(2πt/p)。
        n_basis = 2 + 2 * len(self.PERIODS)
        self.register_buffer("coeffs", torch.zeros(0, n_basis))
        self._fitted = False
        self._fit_len = 0

    def _design_matrix(self, t: "np.ndarray") -> "np.ndarray":
        """构造傅里叶设计矩阵。

        Args:
            t: (M, 1) 时间索引。

        Returns:
            (M, n_basis) 设计矩阵。
        """
        cols = [np.ones_like(t), t]
        for p in self.PERIODS:
            cols.append(np.sin(2 * np.pi * t / p))
            cols.append(np.cos(2 * np.pi * t / p))
        return np.hstack(cols)

    def fit(self, x: torch.Tensor) -> None:
        """对整条序列逐维度拟合傅里叶级数。

        Args:
            x: (N, D) 整条时序数据，N 为序列长度，D 为维度数。
        """
        N, D = x.shape
        t = np.arange(N, dtype=np.float64).reshape(-1, 1)
        design = self._design_matrix(t)  # (N, n_basis)
        coeffs = []
        for d in range(D):
            y = x[:, d].cpu().numpy().astype(np.float64)  # (N,)
            lr = LinearRegression(fit_intercept=False)
            lr.fit(design, y)
            coeffs.append(lr.coef_)
        self.coeffs = torch.tensor(np.array(coeffs), dtype=torch.float32)  # (D, n_basis)
        self._fitted = True
        self._fit_len = N

    def predict(self, n_steps: int) -> torch.Tensor:
        """根据下标用拟合好的傅里叶级数预测未来 n_steps 步。

        Args:
            n_steps: 预测步数。

        Returns:
            (n_steps, D) 每个维度未来 n_steps 步的预测值。
        """
        if not self._fitted or self.coeffs.numel() == 0:
            raise RuntimeError("Model has not been fitted yet.")
        # 预测下标从 N 开始（N 为训练序列长度），连续外推 n_steps 步
        start = self._fit_len
        t = np.arange(start, start + n_steps, dtype=np.float64).reshape(-1, 1)
        design = self._design_matrix(t)  # (n_steps, n_basis)
        coeffs = self.coeffs.cpu().numpy()  # (D, n_basis)
        preds = design @ coeffs.T  # (n_steps, D)
        return torch.tensor(preds, dtype=torch.float32)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """兼容接口：对输入序列逐维度拟合线性回归并预测下一时刻。

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
        return {"coeffs": self.coeffs, "fit_len": self._fit_len}

    def load_state_dict(self, state_dict, strict=True):
        if "coeffs" in state_dict:
            self.coeffs = state_dict["coeffs"].clone()
            self._fitted = True
        if "fit_len" in state_dict:
            self._fit_len = state_dict["fit_len"]


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
    interrupt_signal: typing.Callable[[], bool] = lambda: False,
    pred_len: int | None = None,
) -> list[ModelResult]:
    model_result = []
    device = "cpu"
    train = mode == "train"
    seq_len = 16
    if isinstance(data, TableByRowDataset):
        data = _TableAsSequenceWrapper(data, seq_len=seq_len)
    model = model.to(device)
    null_f = None if progress else open(os.devnull, "w")

    if isinstance(data, _TableAsSequenceWrapper):
        table = data.table
        # 整条序列数据 (N, D)
        series = torch.tensor(
            table.df[table.data_cols].values.astype(float),
            dtype=torch.float32,
        ).to(device)
        if train:
            # 训练：对整条序列逐维度拟合傅里叶级数，系数保存在模型中
            model.fit(series)
            r = ModelResult(
                loss=0.0,
                outputs=[],
                ids=[],
                description=(
                    f"Fitted a Fourier series per dimension on the full sequence "
                    f"of {len(table.df)} rows."
                ),
            )
            model_result.append(r)
            result_callback(result=r)
            result_callback(done=True)
            return model_result
        else:
            # 推理：用拟合好的傅里叶级数直接按下标预测未来 n_steps 步（与输入序列等长）
            n_steps = pred_len if pred_len is not None else len(table.df)
            if n_steps <= 0:
                result_callback(done=True)
                return model_result
            epoch = 1
            model.eval()
            epoch_progress = tqdm(range(epoch), file=null_f)
            with torch.no_grad():
                for ep in epoch_progress:
                    epoch_callback(**epoch_progress.format_dict)
                    if interrupt_signal():
                        result_callback(done=True)
                        return model_result
                    batch_callback(**epoch_progress.format_dict)
                    preds = model.predict(n_steps)  # (n_steps, D)
                    r = ModelResult(
                        loss=0.0,
                        outputs=preds.nan_to_num(0).tolist(),
                        ids=list(range(len(table.df), len(table.df) + n_steps)),
                    )
                    r.description = (
                        f"Fourier forecast: predicted {n_steps} steps "
                        f"(pred_len = original sequence length)."
                    )
                    model_result.append(r)
                    result_callback(result=r)
                    tqdm.write(
                        f"Epoch {ep}: Fourier forecast {n_steps} steps", null_f
                    )
            epoch_callback(**epoch_progress.format_dict)
            result_callback(done=True)
            return model_result

    data_loader = DataLoader(data, batch_size, shuffle=shuffle)
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
