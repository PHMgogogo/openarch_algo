from torch import nn
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import typing
from tqdm import tqdm
import matplotlib.pyplot as plt
import inspect
from dataclasses import dataclass
from pydantic import BaseModel


class TableByRowDataset(Dataset):
    df: pd.DataFrame
    label_cols: list[str]
    data_cols: list[str]
    use_cache: bool
    _cache: dict[int, tuple[torch.Tensor, torch.Tensor]]

    def __init__(
        self, csv_path: str, label_cols: list[str], use_cache: bool = True
    ) -> None:
        self.df = pd.read_csv(csv_path)
        self.label_cols = label_cols
        self.data_cols = [c for c in self.df.columns if c not in set(label_cols)]
        self.use_cache = use_cache
        self._cache = {}  # idx -> (data, label)

    def __len__(self) -> int:
        return len(self.df)

    def _load_row(
        self, idx: int, device: str = "cpu"
    ) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.df.iloc[idx]
        data = torch.tensor(
            row[self.data_cols].values, dtype=torch.float32, device=device
        )
        label = torch.tensor(
            row[self.label_cols].values, dtype=torch.float32, device=device
        )
        return data, label

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        if self.use_cache and idx in self._cache:
            return self._cache[idx]
        item = self._load_row(idx)
        if self.use_cache:
            self._cache[idx] = item
        return item

    def warmup(self, device: str = "cpu") -> None:
        for idx in range(len(self)):
            if idx not in self._cache:
                self._cache[idx] = self._load_row(idx, device)
        return self

    def clear(self) -> None:
        self._cache.clear()


class ModelResult(BaseModel):
    def code(self) -> str:
        return inspect.getsource(self.__class__)


# <result-content>
class LossModelResult(ModelResult):
    loss: float


# <result-content>


# <model-content>
class Model(nn.Module):
    def __init__(self, input_size: int = 1, hidden_size: int = 4, output_size: int = 1):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


# </model-content>

# <train-or-eval-content>
def train_or_eval(
    model: Model,
    data: torch.utils.data.Dataset,
    mode: typing.Literal["train", "eval"] = "eval",
    epoch: int = 10,
    batch_size: int = 1,
    learning_rate: float = 1e-3,
    device: str = "cpu",
    criterion_cls: nn.Module = nn.MSELoss,
    optimizer_cls: torch.optim.Optimizer = torch.optim.SGD,
    progress: bool = True,
) -> list[ModelResult]:
    train = mode == "train"
    if train:
        criterion: nn.Module = criterion_cls()
        model.train()
    else:
        epoch = 1
        model.eval()
        torch_no_grad = torch.no_grad()
        torch_no_grad.__enter__()
    optimizer: torch.optim.Optimizer = optimizer_cls(model.parameters(), learning_rate)
    model = model.to(device)
    data_loader = torch.utils.data.DataLoader(data, batch_size, shuffle=True)
    avg_loss_per_epoch: list[LossModelResult] = []
    for ep in tqdm(range(epoch), disable=not progress):
        total_loss = 0
        for batch_data, batch_labels in data_loader:
            batch_data = batch_data.to(device)
            batch_labels = batch_labels.to(device)
            if train:
                optimizer.zero_grad()
            outputs = model(batch_data)
            loss: torch.Tensor = criterion(outputs, batch_labels)
            if train:
                loss.backward()
                optimizer.step()
            total_loss += loss.item()
        avg_loss = total_loss / len(data)
        avg_loss_per_epoch.append(LossModelResult(data=avg_loss))
        if progress:
            tqdm.write(f"Epoch {ep}: Loss {avg_loss}")
    if not train:
        torch_no_grad.__exit__(None, None, None)
    return avg_loss_per_epoch
# </train-or-eval-content>

def split_dataset(
    dataset: Dataset,
    ratios: list[float],
    generator: typing.Optional[torch.Generator] = None,
) -> list[Dataset]:
    total_size = len(dataset)
    ratios_sum = sum(ratios)
    ratios = [r / ratios_sum for r in ratios]
    sizes = [int(total_size * r) for r in ratios]
    sizes[-1] = total_size - sum(sizes[:-1])

    return torch.utils.data.random_split(dataset, sizes, generator=generator)


def split_dataloader(
    dataset: Dataset,
    ratios: list[float],
    batch_size: int = 1,
    shuffle: bool = True,
    generator: typing.Optional[torch.Generator] = None,
) -> list[DataLoader]:
    subsets = split_dataset(dataset, ratios, generator)
    dataloaders = [
        DataLoader(subset, batch_size=batch_size, shuffle=shuffle) for subset in subsets
    ]
    return dataloaders


if __name__ == "__main__":
    # <main-content>
    model = Model()
    dataset = TableByRowDataset("../example/sqrt.csv", ["y"]).warmup("cuda:0")
    generator = torch.Generator()
    train_dataset, eval_dataset = split_dataset(dataset, [0.8, 0.2], generator)
    train_result = train_or_eval(
        model, train_dataset, "train", epoch=30, batch_size=10, device="cuda:0"
    )
    print(train_result[-1].model_dump_json())
    model.eval()
    x_list = []
    pred_list = []
    label_list = []
    with torch.no_grad():
        for i in range(len(eval_dataset)):
            data, label = eval_dataset[i]
            data = data.to("cuda:0")
            prediction = model(data)
            x_list.append(data[0].item())
            pred_list.append(prediction.item())
            label_list.append(label.item())

    plt.figure(figsize=(10, 6))
    plt.scatter(x_list, label_list, label="Label", color="blue", alpha=0.6, s=10)
    plt.scatter(x_list, pred_list, label="Prediction", color="red", alpha=0.6, s=10)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Prediction vs Label")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig("output.png")
    # </main-content>
