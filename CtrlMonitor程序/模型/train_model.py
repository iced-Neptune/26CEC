# -*- coding: utf-8 -*-
"""
化学小车 - VC预测模型训练脚本
输入：温度(℃) + 电脑检测的时间(秒) → 输出：VC(mL)
包含异常值自动剔除、多模型对比、最优模型保存
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import xgboost as xgb
import joblib
import os
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# ==================== 1. 数据加载 ====================
print("=" * 50)
print("步骤1：加载数据")
print("=" * 50)

data_path = r"c:\Users\ASUS\Desktop\工作\活动\化学小车\模型\小车数据1.xlsx"
df = pd.read_excel(data_path, sheet_name='Sheet1')

# 提取关键列
df_model = df[['温度（下）/℃', '电脑检测的时间', 'VC']].copy()
df_model.columns = ['温度', '时间', 'VC']
df_model = df_model.dropna()

print(f"原始数据条数：{len(df_model)}")
print(f"数据概览：\n{df_model.describe()}")
print(f"\nVC 值分布：{sorted(df_model['VC'].unique())}")

# ==================== 2. 异常值剔除（Q检验 / Dixon's Q-test） ====================
print("\n" + "=" * 50)
print("步骤2：Q检验剔除异常值（按 VC + 温度 分组）")
print("=" * 50)

# Q临界值表（90%置信度）
Q_CRITICAL = {
    3: 0.941, 4: 0.765, 5: 0.642, 6: 0.560,
    7: 0.507, 8: 0.468, 9: 0.437, 10: 0.412
}


def q_test_dixon(values, confidence=0.90):
    """
    Dixon's Q-test 检验一组数据中最小值和最大值是否为离群值。
    返回要剔除的索引列表（在原数组中的位置）。
    """
    n = len(values)
    if n < 3 or n > 10:
        return []  # Q检验适用于3-10个样本

    q_crit = Q_CRITICAL.get(n, 0.412)  # n>10时用最宽松的

    sorted_idx = np.argsort(values)
    sorted_vals = values[sorted_idx]
    data_range = sorted_vals[-1] - sorted_vals[0]
    if data_range == 0:
        return []  # 所有值相同，无法检验

    remove_local_idx = set()

    # 检验最小值（最左侧）
    q_min = (sorted_vals[1] - sorted_vals[0]) / data_range
    if q_min > q_crit:
        remove_local_idx.add(sorted_idx[0])

    # 检验最大值（最右侧）
    q_max = (sorted_vals[-1] - sorted_vals[-2]) / data_range
    if q_max > q_crit:
        remove_local_idx.add(sorted_idx[-1])

    return list(remove_local_idx)


outlier_indices = set()

# 按 (VC, 温度) 联合分组
df_model['_group_key'] = df_model['VC'].astype(str) + '_' + df_model['温度'].round(1).astype(str)
group_keys = df_model['_group_key'].unique()
print(f"分组数：{len(group_keys)}（按 VC + 温度分组）")
print(f"\n各分组样本量分布：")

for key in sorted(group_keys, key=lambda k: float(k.split('_')[0])):
    group = df_model[df_model['_group_key'] == key]
    vc, temp = key.split('_')
    n = len(group)
    
    if n < 3:
        print(f"  VC={float(vc):.1f}, 温度={float(temp):.1f}℃: {n}条 → 样本太少，跳过Q检验")
        continue

    # 对时间列执行Q检验
    time_values = group['时间'].values
    remove_local = q_test_dixon(time_values)
    
    if remove_local:
        global_indices = group.index[remove_local].tolist()
        outlier_indices.update(global_indices)
        removed_seqs = df.loc[global_indices, '序号'].tolist()
        removed_times = time_values[remove_local]
        kept_times = np.delete(time_values, remove_local)
        print(f"  VC={float(vc):.1f}, 温度={float(temp):.1f}℃: {n}条 → Q检验剔出 {len(remove_local)}条"
              f" (序号:{removed_seqs}, 时间值:{removed_times.round(2).tolist()}, "
              f"保留:{kept_times.round(2).tolist()})")
    else:
        print(f"  VC={float(vc):.1f}, 温度={float(temp):.1f}℃: {n}条 → 无异常")

# 清理辅助列
df_model.drop(columns=['_group_key'], inplace=True)

outlier_indices = sorted(outlier_indices)
if len(outlier_indices) > 0:
    print(f"\n共剔出 {len(outlier_indices)} 条异常数据")
    df_clean = df_model.drop(index=outlier_indices)  # 保留原始索引，不reset
else:
    print("未检测到异常数据")
    df_clean = df_model.copy()

print(f"清洗后数据条数：{len(df_clean)}")

# 保存被剔除的数据
if len(outlier_indices) > 0:
    df_removed = df_model.loc[outlier_indices]
    remove_path = r"c:\Users\ASUS\Desktop\工作\活动\化学小车\模型\removed_outliers.xlsx"
    df_removed.to_excel(remove_path, index=False)
    print(f"被剔除的数据已保存至：{remove_path}")

# ==================== 2.5 回归诊断 ====================
print("\n" + "=" * 50)
print("步骤2.5：回归诊断（学生化残差 + Cook距离 + 杠杆值）")
print("=" * 50)

from sklearn.pipeline import make_pipeline

# 用Q检验清洗后的数据拟合初步多项式回归（degree=3，作为诊断基准）
X_diag = df_clean[['温度', '时间']].values
y_diag = df_clean['VC'].values
n_diag = len(X_diag)

pipe_diag = make_pipeline(
    PolynomialFeatures(degree=3, include_bias=False),
    StandardScaler(),
    LinearRegression()
)
pipe_diag.fit(X_diag, y_diag)

# 获取多项式特征后的设计矩阵（make_pipeline 用索引访问）
X_poly = pipe_diag[0].transform(X_diag)
X_poly_scaled = pipe_diag[1].transform(X_poly)
# 添加截距列
X_design = np.column_stack([np.ones(n_diag), X_poly_scaled])
p_diag = X_design.shape[1]  # 特征数（含截距）

y_pred_diag = pipe_diag.predict(X_diag)
residuals = y_diag - y_pred_diag  # 普通残差
mse = np.sum(residuals**2) / (n_diag - p_diag)  # MSE

# H = X(X'X)^(-1)X' —— hat矩阵的对角线 = 杠杆值
try:
    XtX_inv = np.linalg.pinv(X_design.T @ X_design)
    H = X_design @ XtX_inv @ X_design.T
    leverage = np.diag(H)
except np.linalg.LinAlgError:
    leverage = np.full(n_diag, p_diag / n_diag)

# 学生化残差 (externally studentized)
student_resid = np.zeros(n_diag)
for i in range(n_diag):
    if leverage[i] >= 1.0:
        student_resid[i] = 99  # 标记为极端
    else:
        sigma_i = np.sqrt((mse * (n_diag - p_diag) - residuals[i]**2 / (1 - leverage[i])) / (n_diag - p_diag - 1))
        if sigma_i > 0:
            student_resid[i] = residuals[i] / (sigma_i * np.sqrt(1 - leverage[i]))
        else:
            student_resid[i] = 0

# Cook's 距离
cooks_d = (student_resid**2 / p_diag) * (leverage / (1 - leverage + 1e-10))

# 阈值
thresh_student = 3.0           # 学生化残差 |ri*| > 3
thresh_cooks = 4.0 / n_diag    # Cook's D > 4/n
thresh_leverage = 2.0 * p_diag / n_diag  # 杠杆值 > 2p/n

# 综合判定：满足 ≥2 个条件 → 标记为错误数据
flags_student = np.abs(student_resid) > thresh_student
flags_cooks = cooks_d > thresh_cooks
flags_leverage = leverage > thresh_leverage
flags_total = flags_student.astype(int) + flags_cooks.astype(int) + flags_leverage.astype(int)
reg_outlier_mask = flags_total >= 2

reg_outlier_count = np.sum(reg_outlier_mask)
print(f"  学生化残差阈值：|r*| > {thresh_student}")
print(f"  Cook's D 阈值：> {thresh_cooks:.6f}")
print(f"  杠杆值阈值：> {thresh_leverage:.4f}")
print(f"  回归诊断检出：{reg_outlier_count} 条（同时满足 ≥2 个条件）")

if reg_outlier_count > 0:
    reg_outlier_idx = df_clean.index[reg_outlier_mask].tolist()
    print(f"  剔出序号：{df.loc[reg_outlier_idx, '序号'].tolist()}")
    for i in reg_outlier_idx:
        idx_in_df = df_clean.index.get_loc(i)
        print(f"    → 原始序号={df.loc[i, '序号']}, VC={df_clean.loc[i, 'VC']:.1f}, "
              f"温度={df_clean.loc[i, '温度']:.1f}℃, 时间={df_clean.loc[i, '时间']:.2f}s, "
              f"学生化残差={student_resid[idx_in_df]:.3f}, CookD={cooks_d[idx_in_df]:.5f}, 杠杆={leverage[idx_in_df]:.4f}")

    # 合并Q检验和回归诊断的异常索引
    all_outlier = set(outlier_indices) | set(reg_outlier_idx)
    df_clean = df_model.drop(index=sorted(all_outlier)).reset_index(drop=True)
    print(f"\n  Q检验剔出 {len(outlier_indices)} 条 + 回归诊断剔出 {reg_outlier_count} 条 = 共 {len(all_outlier)} 条")
else:
    print("  回归诊断未发现异常数据")

print(f"最终清洗后数据条数：{len(df_clean)}")

# 更新被剔除数据的保存（合并两个阶段）
if reg_outlier_count > 0:
    from datetime import datetime
    all_outlier_indices = sorted(set(outlier_indices) | set(reg_outlier_idx))
    df_all_removed = df_model.loc[all_outlier_indices].copy()
    # 标注来源
    df_all_removed['剔除阶段'] = 'Q检验'
    df_all_removed.loc[df_all_removed.index.isin(reg_outlier_idx), '剔除阶段'] = '回归诊断'
    # 双重标记
    both_idx = set(reg_outlier_idx) & set(outlier_indices)
    if both_idx:
        df_all_removed.loc[df_all_removed.index.isin(both_idx), '剔除阶段'] = 'Q检验+回归诊断'
    remove_path = r"c:\Users\ASUS\Desktop\工作\活动\化学小车\模型\removed_outliers.xlsx"
    df_all_removed.to_excel(remove_path, index=False)
    print(f"被剔除的数据已更新保存至：{remove_path}")

outlier_indices = sorted(set(outlier_indices) | (set(reg_outlier_idx) if reg_outlier_count > 0 else set()))

# ==================== 3. 准备训练数据 ====================
print("\n" + "=" * 50)
print("步骤3：划分训练集/测试集")
print("=" * 50)

X = df_clean[['温度', '时间']].values
y = df_clean['VC'].values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"训练集：{len(X_train)} 条")
print(f"测试集：{len(X_test)} 条")

# ==================== 4. 多模型训练 ====================
print("\n" + "=" * 50)
print("步骤4：训练多个模型")
print("=" * 50)

models = {}
results = {}

# 4.1 多项式回归 (degree 2, 3, 4)
for degree in [2, 3, 4]:
    name = f'PolyReg(deg={degree})'
    print(f"\n--- 训练 {name} ---")
    pipeline = Pipeline([
        ('poly', PolynomialFeatures(degree=degree, include_bias=False)),
        ('scaler', StandardScaler()),
        ('reg', LinearRegression())
    ])
    pipeline.fit(X_train, y_train)
    models[name] = pipeline

# 4.2 随机森林
print("\n--- 训练 RandomForest ---")
rf = RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
models['RandomForest'] = rf

# 4.3 XGBoost
print("\n--- 训练 XGBoost ---")
xgb_model = xgb.XGBRegressor(
    n_estimators=200, max_depth=8, learning_rate=0.1,
    random_state=42, verbosity=0
)
xgb_model.fit(X_train, y_train)
models['XGBoost'] = xgb_model

# ==================== 5. 模型评估 ====================
print("\n" + "=" * 50)
print("步骤5：模型评估对比")
print("=" * 50)

print(f"\n{'模型名称':<25} {'R²':>8} {'MAE':>8} {'RMSE':>8}")
print("-" * 50)

for name, model in models.items():
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    results[name] = {'R²': r2, 'MAE': mae, 'RMSE': rmse, 'model': model}
    print(f"{name:<25} {r2:>8.4f} {mae:>8.4f} {rmse:>8.4f}")

# 选最优模型（按 R² 最高）
best_name = max(results, key=lambda k: results[k]['R²'])
best_model = results[best_name]['model']
best_r2 = results[best_name]['R²']
print(f"\n🏆 最优模型：{best_name} (R² = {best_r2:.4f})")

# ==================== 6. 保存最优模型 ====================
print("\n" + "=" * 50)
print("步骤6：保存模型")
print("=" * 50)

model_dir = r"c:\Users\ASUS\Desktop\工作\活动\化学小车\模型"
model_path = os.path.join(model_dir, "vc_model.pkl")
scaler_path = os.path.join(model_dir, "vc_scaler.pkl")

joblib.dump(best_model, model_path)
print(f"模型已保存至：{model_path}")

# 保存模型元信息
meta = {
    'model_name': best_name,
    'R²': best_r2,
    'MAE': results[best_name]['MAE'],
    'RMSE': results[best_name]['RMSE'],
    'train_size': len(X_train),
    'test_size': len(X_test),
    'outliers_removed': len(outlier_indices),
    'features': ['温度（℃）', '电脑检测的时间（秒）'],
    'target': 'VC (mL)'
}
joblib.dump(meta, os.path.join(model_dir, "vc_model_meta.pkl"))
print(f"模型元信息已保存")

# ==================== 7. 可视化 ====================
print("\n" + "=" * 50)
print("步骤7：生成可视化图表")
print("=" * 50)

fig_dir = os.path.join(model_dir, "charts")
os.makedirs(fig_dir, exist_ok=True)

# 7.1 模型性能对比柱状图
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
metric_names = ['R²', 'MAE', 'RMSE']
for idx, metric in enumerate(metric_names):
    ax = axes[idx]
    names = list(results.keys())
    values = [results[n][metric] for n in names]
    colors = ['#2ecc71' if n == best_name else '#3498db' for n in names]
    bars = ax.bar(range(len(names)), values, color=colors)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=9)
    ax.set_title(f'{metric} 对比', fontsize=14)
    ax.set_ylabel(metric)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val:.4f}', ha='center', va='bottom', fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, 'model_comparison.png'), dpi=150)
plt.close()
print("  ✓ 模型对比图已保存")

# 7.2 预测值 vs 真实值散点图
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
axes = axes.flatten()
model_list = list(models.items())

for idx, (name, model) in enumerate(model_list):
    if idx >= 6:
        break
    ax = axes[idx]
    y_pred = model.predict(X_test)
    ax.scatter(y_test, y_pred, alpha=0.6, edgecolors='k', linewidth=0.3)
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
            'r--', lw=2, label='y=x')
    ax.set_xlabel('真实 VC (mL)')
    ax.set_ylabel('预测 VC (mL)')
    ax.set_title(f'{name} (R²={results[name]["R²"]:.4f})')
    ax.legend()
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, 'prediction_vs_true.png'), dpi=150)
plt.close()
print("  ✓ 预测vs真实对比图已保存")

# 7.3 3D曲面图（最优模型）
fig = plt.figure(figsize=(12, 5))

# 训练数据分布
ax1 = fig.add_subplot(121, projection='3d')
ax1.scatter(df_clean['温度'], df_clean['时间'], df_clean['VC'],
            c=df_clean['VC'], cmap='viridis', alpha=0.7, s=15)
ax1.set_xlabel('温度 (℃)')
ax1.set_ylabel('时间 (秒)')
ax1.set_zlabel('VC (mL)')
ax1.set_title('训练数据 3D 分布', fontsize=14)

# 预测曲面
ax2 = fig.add_subplot(122, projection='3d')
temp_range = np.linspace(df_clean['温度'].min(), df_clean['温度'].max(), 50)
time_range = np.linspace(df_clean['时间'].min(), df_clean['时间'].max(), 50)
T, S = np.meshgrid(temp_range, time_range)
grid_points = np.c_[T.ravel(), S.ravel()]
pred_grid = best_model.predict(grid_points).reshape(T.shape)

surf = ax2.plot_surface(T, S, pred_grid, cmap='plasma', alpha=0.85, edgecolor='none')
ax2.set_xlabel('温度 (℃)')
ax2.set_ylabel('时间 (秒)')
ax2.set_zlabel('VC 预测 (mL)')
ax2.set_title(f'{best_name} 预测曲面', fontsize=14)
fig.colorbar(surf, ax=ax2, shrink=0.5, aspect=10)

plt.tight_layout()
plt.savefig(os.path.join(fig_dir, '3d_surface.png'), dpi=150)
plt.close()
print("  ✓ 3D曲面图已保存")

# 7.4 异常值筛选前后对比
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].scatter(df_model['温度'], df_model['时间'], c=df_model['VC'],
                cmap='viridis', alpha=0.6, s=20)
axes[0].set_xlabel('温度 (℃)')
axes[0].set_ylabel('时间 (秒)')
axes[0].set_title(f'原始数据 ({len(df_model)} 条)', fontsize=13)
axes[0].grid(True, alpha=0.3)

if len(outlier_indices) > 0:
    outlier_data = df_model.loc[outlier_indices]
    axes[0].scatter(outlier_data['温度'], outlier_data['时间'],
                    facecolors='none', edgecolors='red', s=60, linewidth=1.5,
                    label=f'异常值 ({len(outlier_indices)}条)')
    axes[0].legend()

scatter = axes[1].scatter(df_clean['温度'], df_clean['时间'], c=df_clean['VC'],
                          cmap='viridis', alpha=0.6, s=20)
axes[1].set_xlabel('温度 (℃)')
axes[1].set_ylabel('时间 (秒)')
axes[1].set_title(f'清洗后数据 ({len(df_clean)} 条)', fontsize=13)
axes[1].grid(True, alpha=0.3)
plt.colorbar(scatter, ax=axes[1], label='VC (mL)')
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, 'outlier_removal.png'), dpi=150)
plt.close()
print("  ✓ 异常值剔出对比图已保存")

# ==================== 8. 预测示例 ====================
print("\n" + "=" * 50)
print("步骤8：预测示例")
print("=" * 50)

# 随机抽取几个测试样本进行演示
demo_indices = np.random.choice(len(X_test), min(5, len(X_test)), replace=False)
print(f"\n{'温度':>6} {'时间':>8} {'真实VC':>8} {'预测VC':>8} {'误差':>8}")
print("-" * 42)
for idx in demo_indices:
    temp, sec = X_test[idx]
    true_vc = y_test[idx]
    pred_vc = best_model.predict([[temp, sec]])[0]
    error = abs(true_vc - pred_vc)
    print(f"{temp:>6.1f} {sec:>8.2f} {true_vc:>8.2f} {pred_vc:>8.2f} {error:>8.4f}")

print("\n" + "=" * 50)
print("✅ 全部完成！")
print(f"  - 最优模型：{best_name}")
print(f"  - R² 分数：{best_r2:.4f}")
print(f"  - 模型文件：{model_path}")
print(f"  - 图表目录：{fig_dir}")
print("=" * 50)

# ==================== 9. 保存完整评估结果 ====================
results_df = pd.DataFrame([
    {'模型': name, 'R²': info['R²'], 'MAE': info['MAE'], 'RMSE': info['RMSE']}
    for name, info in results.items()
])
results_df = results_df.sort_values('R²', ascending=False)
results_path = os.path.join(model_dir, "model_results.xlsx")
results_df.to_excel(results_path, index=False)
print(f"评估结果已保存至：{results_path}")