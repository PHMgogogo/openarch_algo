from torch.utils.data import Dataset
import pandas as pd
import torch
import math
import os


def generate_simple_csv(output_path: str = "../example/sqrt.csv") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    data = []
    for i in range(1000):
        data.append([i / 1000**0.5, i / 1000])

    df = pd.DataFrame(data, columns=["y", "x"])
    df.to_csv(output_path, index=False)


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

    def _load_row(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.df.iloc[idx]

        data = torch.tensor(row[self.data_cols].values, dtype=torch.float32)
        label = torch.tensor(row[self.label_cols].values, dtype=torch.float32)

        return data, label

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        if self.use_cache and idx in self._cache:
            return self._cache[idx]

        item = self._load_row(idx)

        if self.use_cache:
            self._cache[idx] = item

        return item

    # 2. warmup
    def warmup(self) -> None:
        """
        预加载所有数据到缓存
        """
        for idx in range(len(self)):
            if idx not in self._cache:
                self._cache[idx] = self._load_row(idx)

    # 3. clear
    def clear(self) -> None:
        """
        清空缓存
        """
        self._cache.clear()


if __name__ == "__main__":
    generate_simple_csv()
