import pandas as pd
import numpy as np


def generate_health_data():
    train_n = 10000
    valid_n = 200

    # 保证训练集和验证集时间不重合
    train_time = pd.date_range(start="2025-01-01 00:00:00", periods=train_n, freq="s")

    valid_time = pd.date_range(start="2025-02-01 00:00:00", periods=valid_n, freq="s")

    rng = np.random.default_rng(42)

    # ------------------------
    # 生成一批数据
    # ------------------------
    def build_dataset(time):
        n = len(time)
        x = np.arange(n)

        # 五个输入指标
        temperature = 25 + 2 * np.sin(x / 120) + rng.normal(0, 0.5, n)
        humidity = 60 + 5 * np.cos(x / 150) + rng.normal(0, 1.0, n)

        A = 100 + 8 * np.sin(x / 90) + rng.normal(0, 1.0, n)
        B = 50 + 4 * np.cos(x / 70) + rng.normal(0, 0.8, n)
        C = 80 + 6 * np.sin(x / 110) + rng.normal(0, 1.2, n)

        # ------------------------
        # 构造健康度
        # 先标准化
        # ------------------------
        t = (temperature - 25) / 2
        h = (humidity - 60) / 5
        a = (A - 100) / 8
        b = (B - 50) / 4
        c = (C - 80) / 6

        # 一个固定线性模型
        score = 0.35 - 0.18 * t + 0.15 * h + 0.25 * a - 0.12 * b + 0.20 * c

        # sigmoid压缩到0~1
        health = 1 / (1 + np.exp(-score))

        df = pd.DataFrame(
            {
                "time": time,
                "温度": temperature.round(3),
                "湿度": humidity.round(3),
                "A": A.round(3),
                "B": B.round(3),
                "C": C.round(3),
                "health": health.round(6),
            }
        )

        return df

    train_df = build_dataset(train_time)
    valid_df = build_dataset(valid_time)

    train_df.to_csv("health_train.csv", index=False, encoding="utf-8-sig")

    valid_df.to_csv("health_valid.csv", index=False, encoding="utf-8-sig")

    print(f"训练集：{len(train_df)}")
    print(f"验证集：{len(valid_df)}")


if __name__ == "__main__":
    generate_health_data()
