# -*- coding: utf-8 -*-
"""
VC 预测脚本 —— 使用已训练的模型进行预测
输入：温度(℃) + 时间(秒) → 输出：VC(mL)

用法：
  python predict.py                          # 交互式输入
  python predict.py 22.5 85.6                # 命令行直接预测
  python predict.py --batch predictions.csv  # 批量预测
"""

import joblib
import sys
import os
import pandas as pd
import numpy as np

MODEL_DIR = r"c:\Users\ASUS\Desktop\工作\活动\化学小车\模型"
MODEL_PATH = os.path.join(MODEL_DIR, "vc_model.pkl")
META_PATH = os.path.join(MODEL_DIR, "vc_model_meta.pkl")


def load_model():
    """加载模型和元信息"""
    if not os.path.exists(MODEL_PATH):
        print(f"❌ 模型文件不存在：{MODEL_PATH}")
        print("请先运行 train_model.py 训练模型")
        sys.exit(1)

    model = joblib.load(MODEL_PATH)
    meta = joblib.load(META_PATH) if os.path.exists(META_PATH) else {}
    return model, meta


def predict_single(model, temp, time_sec):
    """单次预测"""
    input_data = np.array([[temp, time_sec]])
    vc = model.predict(input_data)[0]
    return vc


def predict_batch(model, csv_path):
    """批量预测 CSV 文件需包含「温度」和「时间」列"""
    df = pd.read_csv(csv_path)
    if '温度' not in df.columns or '时间' not in df.columns:
        print("❌ CSV 文件必须包含「温度」和「时间」列")
        sys.exit(1)
    X = df[['温度', '时间']].values
    predictions = model.predict(X)
    df['预测VC'] = predictions
    df['预测VC'] = df['预测VC'].round(4)
    output_path = csv_path.replace('.csv', '_predicted.csv')
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 批量预测完成，结果保存至：{output_path}")
    print(df.to_string(index=False))


def interactive_mode(model, meta):
    """交互式预测模式"""
    print("=" * 50)
    print("  🔬 VC 浓度预测系统")
    print("=" * 50)

    if meta:
        print(f"  模型类型：{meta.get('model_name', 'Unknown')}")
        print(f"  R² 分数：{meta.get('R²', 'N/A'):.4f}" if isinstance(meta.get('R²'), float) else f"  R² 分数：{meta.get('R²', 'N/A')}")
        print(f"  输入特征：温度(℃) + 时间(秒)")
        print(f"  预测目标：VC (mL)")
        print("-" * 50)

    while True:
        print("\n请输入参数（输入 q 退出）：")
        try:
            temp_input = input("  温度 (℃)：").strip()
            if temp_input.lower() == 'q':
                break
            temp = float(temp_input)

            time_input = input("  时间 (秒)：").strip()
            if time_input.lower() == 'q':
                break
            time_sec = float(time_input)

        except ValueError:
            print("  ⚠ 请输入有效数字")
            continue

        vc = predict_single(model, temp, time_sec)
        print(f"\n  📊 预测结果：VC = {vc:.4f} mL")
        print("-" * 40)


def main():
    model, meta = load_model()

    if len(sys.argv) == 3:
        # 命令行模式：python predict.py 22.5 85.6
        try:
            temp = float(sys.argv[1])
            time_sec = float(sys.argv[2])
        except ValueError:
            print("用法：python predict.py <温度℃> <时间秒>")
            sys.exit(1)
        vc = predict_single(model, temp, time_sec)
        print(f"温度={temp}℃, 时间={time_sec}秒 → 预测 VC = {vc:.4f} mL")

    elif len(sys.argv) >= 2 and sys.argv[1] == '--batch':
        # 批量模式：python predict.py --batch data.csv
        if len(sys.argv) < 3:
            print("用法：python predict.py --batch <csv文件路径>")
            sys.exit(1)
        predict_batch(model, sys.argv[2])

    else:
        # 交互模式
        interactive_mode(model, meta)


if __name__ == '__main__':
    main()