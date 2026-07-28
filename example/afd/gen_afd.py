import pandas as pd
import numpy as np


def generate_data():
    n = 10000

    np.random.seed(42)

    # 时间序列
    time = pd.date_range(
        start="2025-01-01 00:00:00",
        periods=n,
        freq="s"
    )

    x = np.arange(n)

    # 基础趋势
    temperature = 25 + 3 * np.sin(x / 150)
    humidity = 60 + 8 * np.cos(x / 200)

    A = 100 + 5 * np.sin(x / 80)
    B = 50 + 2 * np.cos(x / 60)
    C = 80 + 4 * np.sin(x / 100)

    label = np.zeros(n, dtype=int)

    # 异常区间
    abnormal_ranges = [
        (1000, 1020),
        (3000, 3020),
        (5000, 5020),
        (7000, 7020),
        (9000, 9020),
    ]

    for start, end in abnormal_ranges:

        label[start:end] = 1

        temperature[start:end] += 10
        humidity[start:end] -= 20

        A[start:end] += 30
        B[start:end] -= 15
        C[start:end] += 25


    # 原始完整数据
    df = pd.DataFrame({
        "time": time,
        "温度": temperature,
        "湿度": humidity,
        "A": A,
        "B": B,
        "C": C,
        "label": label
    })


    # =========================
    # 1. 保存完整时序数据
    # =========================

    df_full = df.copy()

    # 增加测量小误差，使真实采集更自然
    noise = np.random.normal(0, 0.05, size=(len(df_full), 5))

    df_full[["温度", "湿度", "A", "B", "C"]] += noise

    df_full[["温度", "湿度", "A", "B", "C"]] = \
        df_full[["温度", "湿度", "A", "B", "C"]].round(2)


    df_full.to_csv(
        "timeseries_data.csv",
        index=False,
        encoding="utf-8-sig"
    )


    # =========================
    # 2. 保存异常数据
    # =========================

    abnormal_df = df[df["label"] == 1].copy()


    # 异常数据增加不同测量扰动
    abnormal_noise = np.random.normal(
        0,
        0.2,
        size=(len(abnormal_df), 5)
    )

    abnormal_df[["温度", "湿度", "A", "B", "C"]] += abnormal_noise

    abnormal_df[["温度", "湿度", "A", "B", "C"]] = \
        abnormal_df[["温度", "湿度", "A", "B", "C"]].round(2)


    abnormal_df.to_csv(
        "abnormal_data.csv",
        index=False,
        encoding="utf-8-sig"
    )


    # =========================
    # 3. 保存AFD数据
    # =========================

    # 随机选择部分异常，不全部复制
    afd_abnormal = abnormal_df.sample(
        frac=0.8,
        random_state=10
    )


    # 加入正常数据
    normal_df = df[df["label"] == 0].sample(
        n=20,
        random_state=20
    )


    afd_df = pd.concat(
        [afd_abnormal, normal_df],
        ignore_index=True
    )


    # AFD再次加入不同噪声
    afd_noise = np.random.normal(
        0,
        0.1,
        size=(len(afd_df), 5)
    )

    afd_df[["温度", "湿度", "A", "B", "C"]] += afd_noise

    afd_df[["温度", "湿度", "A", "B", "C"]] = \
        afd_df[["温度", "湿度", "A", "B", "C"]].round(2)


    # 打乱
    afd_df = afd_df.sample(
        frac=1,
        random_state=30
    ).reset_index(drop=True)


    afd_df.to_csv(
        "afd_data.csv",
        index=False,
        encoding="utf-8-sig"
    )


    print("生成完成")
    print(f"完整数据: {len(df_full)}")
    print(f"异常数据: {len(abnormal_df)}")
    print(f"AFD数据: {len(afd_df)}")


if __name__ == "__main__":
    generate_data()