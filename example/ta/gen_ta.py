import pandas as pd
import numpy as np


def generate_prediction_data():
    """
    生成预测数据集（仅含特征，无标签）
    - 训练集：prediction_train.csv
    - 验证集：prediction_valid.csv
    每个特征采用不同分布，时间不重合。
    """
    train_n = 10000  # 训练样本数
    valid_n = 2000  # 验证样本数

    # 训练集时间：2025-04-01 开始
    train_time = pd.date_range(start="2025-04-01 00:00:00", periods=train_n, freq="s")
    # 验证集时间：2025-05-01 开始，与训练集不重叠
    valid_time = pd.date_range(start="2025-05-01 00:00:00", periods=valid_n, freq="s")

    rng = np.random.default_rng(2024)

    def build_features(time, rng):
        n = len(time)
        x = np.arange(n)

        # ----- 温度：线性上升 + 正弦周期 + 噪声 -----
        temperature = (
            22.0
            + 0.0008 * x  # 缓慢上升
            + 1.5 * np.sin(2 * np.pi * x / 200)  # 周期
            + rng.normal(0, 0.3, n)  # 噪声
        )

        # ----- 湿度：缓慢下降 + 余弦波动 + 噪声 -----
        humidity = (
            70.0
            - 0.0006 * x  # 下降趋势
            + 4.0 * np.cos(2 * np.pi * x / 250)  # 余弦周期
            + rng.normal(0, 0.8, n)
        )

        # ----- A：随机游走 + 短周期 + 噪声 -----
        steps = rng.normal(0, 0.5, n)
        random_walk = np.cumsum(steps)  # 非平稳过程
        A = (
            100.0
            + random_walk
            + 2.0 * np.sin(2 * np.pi * x / 80)  # 高频周期
            + rng.normal(0, 0.4, n)
        )

        # ----- B：指数衰减 + 余弦波动 + 噪声 -----
        B = (
            80.0 * np.exp(-x / 2500)  # 指数衰减
            + 1.5 * np.cos(2 * np.pi * x / 150)  # 中等周期
            + rng.normal(0, 0.5, n)
        )

        # ----- C：趋势 + 振幅衰减正弦 + 噪声 -----
        C = (
            75.0
            + 0.0015 * x  # 缓慢上升
            + 10.0 * np.sin(2 * np.pi * x / 180) * np.exp(-x / 5000)  # 衰减正弦
            + rng.normal(0, 1.0, n)
        )

        df = pd.DataFrame(
            {
                "time": time,
                "温度": temperature.round(3),
                "湿度": humidity.round(3),
                "A": A.round(3),
                "B": B.round(3),
                "C": C.round(3),
            }
        )
        return df

    train_df = build_features(train_time, rng)
    valid_df = build_features(valid_time, rng)

    train_df.to_csv("prediction_train.csv", index=False, encoding="utf-8-sig")
    valid_df.to_csv("prediction_valid.csv", index=False, encoding="utf-8-sig")

    print(f"预测训练集样本数：{len(train_df)}")
    print(f"预测验证集样本数：{len(valid_df)}")
    print("已保存文件：prediction_train.csv, prediction_valid.csv")


if __name__ == "__main__":
    generate_prediction_data()
