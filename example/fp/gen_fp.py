import pandas as pd
import numpy as np


def generate_fault_prediction_data():
    """
    生成故障预测数据集

    输出：
    - fault_train.csv
    - fault_valid.csv

    特征：
    time
    温度
    湿度
    A
    B
    C

    标签：
    是否故障
        0: 正常
        1: 故障
    """

    train_n = 10000
    valid_n = 2000

    # 时间不重叠
    train_time = pd.date_range(
        start="2025-04-01 00:00:00",
        periods=train_n,
        freq="s"
    )

    valid_time = pd.date_range(
        start="2025-05-01 00:00:00",
        periods=valid_n,
        freq="s"
    )

    rng = np.random.default_rng(2024)


    def build_features(time, rng):

        n = len(time)
        x = np.arange(n)


        # ============================
        # 正常状态数据
        # ============================

        temperature = (
            22
            + 0.0008*x
            + 1.5*np.sin(2*np.pi*x/200)
            + rng.normal(0,0.3,n)
        )


        humidity = (
            70
            -0.0006*x
            +4*np.cos(2*np.pi*x/250)
            +rng.normal(0,0.8,n)
        )


        steps = rng.normal(0,0.5,n)
        random_walk = np.cumsum(steps)

        A = (
            100
            + random_walk
            +2*np.sin(2*np.pi*x/80)
            +rng.normal(0,0.4,n)
        )


        B = (
            80*np.exp(-x/2500)
            +1.5*np.cos(2*np.pi*x/150)
            +rng.normal(0,0.5,n)
        )


        C = (
            75
            +0.0015*x
            +10*np.sin(2*np.pi*x/180)*np.exp(-x/5000)
            +rng.normal(0,1,n)
        )


        # 默认全部正常
        fault = np.zeros(n,dtype=int)



        # ==================================================
        # 注入故障
        # ==================================================

        fault_count = int(n*0.08)  # 8%的数据为故障


        fault_positions = rng.choice(
            np.arange(500,n-500),
            size=fault_count,
            replace=False
        )


        for pos in fault_positions:


            # 故障持续时间
            length = rng.integers(20,100)

            end = min(pos+length,n)


            fault[pos:end]=1


            fault_type = rng.integers(0,5)


            # ----------------------------
            # 1. 温度过热故障
            # ----------------------------
            if fault_type == 0:

                temperature[pos:end] += (
                    rng.uniform(8,15)
                )



            # ----------------------------
            # 2. 湿度异常下降
            # ----------------------------
            elif fault_type == 1:

                humidity[pos:end] -= (
                    rng.uniform(15,30)
                )



            # ----------------------------
            # 3. A传感器漂移
            # ----------------------------
            elif fault_type == 2:

                drift = np.linspace(
                    0,
                    rng.uniform(10,30),
                    end-pos
                )

                A[pos:end]+=drift



            # ----------------------------
            # 4. B突然衰减
            # ----------------------------
            elif fault_type == 3:

                B[pos:end] *= rng.uniform(
                    0.4,
                    0.7
                )



            # ----------------------------
            # 5. C随机震荡异常
            # ----------------------------
            else:

                C[pos:end]+=(
                    rng.normal(
                        0,
                        8,
                        end-pos
                    )
                )



            # 所有故障增加噪声
            temperature[pos:end]+=rng.normal(
                0,1,length
            )

            A[pos:end]+=rng.normal(
                0,2,length
            )



        df = pd.DataFrame(
            {
                "time":time,

                "温度":temperature.round(3),

                "湿度":humidity.round(3),

                "A":A.round(3),

                "B":B.round(3),

                "C":C.round(3),

                "是否故障":fault
            }
        )


        return df



    train_df = build_features(
        train_time,
        rng
    )

    valid_df = build_features(
        valid_time,
        rng
    )


    train_df.to_csv(
        "fault_train.csv",
        index=False,
        encoding="utf-8-sig"
    )


    valid_df.to_csv(
        "fault_valid.csv",
        index=False,
        encoding="utf-8-sig"
    )


    print("训练集:")
    print(train_df["是否故障"].value_counts())

    print("\n验证集:")
    print(valid_df["是否故障"].value_counts())


    print(
        "\n生成完成:"
        "fault_train.csv, fault_valid.csv"
    )



if __name__=="__main__":
    generate_fault_prediction_data()