# CHEM_E_CAR 比赛增强版 – 状态机说明文档

## 1. 状态机总览

系统包含 6 个状态，按顺序流转。状态定义如下：

| 状态名                 | 枚举值 | 描述                                |
| ---------------------- | ------ | ----------------------------------- |
| `STATE_CALIBRATING`    | 0      | 开机/重置后自动标定环境光基准       |
| `STATE_WAITING_START`  | 1      | 等待溶液加入（光强跌破阈值即开始）  |
| `STATE_REACTING`       | 2      | 反应进行中（保护期 + 监测结束条件） |
| `STATE_CONFIRMING_END` | 3      | 确认反应结束（滤波防误判）          |
| `STATE_FINISHED`       | 4      | 测量完成，延时停车                  |
| `STATE_IDLE`           | 5      | 闲置状态，等待 `RESET` 命令         |

## 2. 状态切换流程与判断逻辑

### 状态 0: `STATE_CALIBRATING`
- **进入条件**：系统启动或收到 `RESET` 命令。
- **执行逻辑**：
  1. 检测当前光强是否 **> 800**（防止在暗环境错误标定）。
  2. 若满足，则持续采样 3000 ms，跳过前 500 ms 不稳定数据。
  3. 计算平均光强作为 `baselineLight`。
  4. 根据 `START_PERCENT` 和 `END_PERCENT` 计算：
     - `startThreshold = baselineLight * (1 - START_PERCENT)`
     - `endThreshold   = baselineLight * (1 - END_PERCENT)`
  5. 标定完成后蜂鸣一声，切换至 `STATE_WAITING_START`。
- **不满足光强 > 800**：重置标定计时器，继续等待强光。

### 状态 1: `STATE_WAITING_START`
- **进入条件**：标定完成。
- **执行逻辑**：
  - 实时监测光强是否 **< startThreshold**。
  - 为避免抖动，要求连续 **2 帧**（200 ms）均低于阈值才触发。
- **切换条件**：满足上述条件 → 调用 `startReaction()`，切换至 `STATE_REACTING`。

### 状态 2: `STATE_REACTING`
- **进入条件**：检测到开始反应。
- **执行逻辑**：
  - **小车控制**：进入状态后延迟 `CAR_DELAY_MS`（默认 1000 ms）启动小车（`CAR_PIN = HIGH`）。
  - **保护期**：进入后的前 `PROTECTION_TIME_MS`（默认 10000 ms）内，**不检测结束条件**，避免刚加入溶液时光强波动导致误停车。
  - **结束检测**：保护期过后，实时判断 `light < endThreshold` 是否成立。若成立，则立即进入 `STATE_CONFIRMING_END` 进行确认。
- **切换条件**：光强跌破 `endThreshold` → `STATE_CONFIRMING_END`。

### 状态 3: `STATE_CONFIRMING_END`
- **进入条件**：保护期后检测到光强低于 `endThreshold`。
- **执行逻辑**：
  - 确认期时长 `CONFIRM_TIME_MS`（默认 800 ms）。
  - 在此窗口内统计“有效低点”次数：若 `light < endThreshold * 1.1`（容错系数 `END_CONFIRM_TOLERANCE = 1.1`）则计为有效。
  - 确认期结束后，若有效低点比例 ≥ 50%，则确认真结束；否则判为误报。
- **切换条件**：
  - 确认成功 → `STATE_FINISHED`，并打印反应时间。
  - 误报 → 返回 `STATE_REACTING`，继续监测。
- **安全锁**：若在确认期停留超过 `2 * CAR_DELAY_MS`，强制停车并进入 `STATE_IDLE`。

### 状态 4: `STATE_FINISHED`
- **进入条件**：确认反应真实结束。
- **执行逻辑**：
  - 等待 `CAR_DELAY_MS`（默认 1000 ms）后，关闭小车（`CAR_PIN = LOW`）。
  - 通过串口打印 `MEASUREMENT_COMPLETE`。
- **切换条件**：延时结束 → `STATE_IDLE`。

### 状态 5: `STATE_IDLE`
- **进入条件**：测量完成或安全锁触发。
- **执行逻辑**：
  - 无任何动作，仅等待外部 `RESET` 命令（通过串口发送 `"RESET"`）。
- **切换条件**：收到 `RESET` → 调用 `resetSystem()` → 回到 `STATE_CALIBRATING`。

## 3. 可修改参数与影响范围

下表列出所有用户可调整的参数，并注明每个参数影响哪个状态的哪个判断逻辑。参数均位于代码开头的 **“用户可调参数区”**。

| 参数名                    | 默认值 | 单位 | 影响的状态                                  | 影响的具体逻辑                                                                   |
| ------------------------- | ------ | ---- | ------------------------------------------- | -------------------------------------------------------------------------------- |
| `START_PERCENT`           | 0.15   | 无   | `STATE_CALIBRATING` → `STATE_WAITING_START` | 计算 `startThreshold`，决定开始反应的触发光强阈值。值越大越敏感（易触发）。      |
| `END_PERCENT`             | 0.25   | 无   | `STATE_REACTING` → `STATE_CONFIRMING_END`   | 计算 `endThreshold`，决定结束反应的触发光强阈值。值越大，反应更早结束。          |
| `CAR_DELAY_MS`            | 1000   | 毫秒 | `STATE_REACTING`、`STATE_FINISHED`          | 1) 启动小车前的延迟；2) 测量完成后关闭小车前的延迟。                             |
| `PROTECTION_TIME_MS`      | 10000  | 毫秒 | `STATE_REACTING`                            | 保护期长度，此期间忽略光强变化，不检测结束条件。                                 |
| `CONFIRM_TIME_MS`         | 800    | 毫秒 | `STATE_CONFIRMING_END`                      | 确认期的窗口长度，用于滤波防误判。                                               |
| `CALIBRATION_DURATION_MS` | 3000   | 毫秒 | `STATE_CALIBRATING`                         | 标定环境光的总采样时长。                                                         |
| `CALIBRATION_SKIP_MS`     | 500    | 毫秒 | `STATE_CALIBRATING`                         | 标定开始时跳过前 `SKIP_MS` 毫秒的数据（避开通电不稳定）。                        |
| `SAMPLING_INTERVAL_MS`    | 100    | 毫秒 | 所有状态（全局采样）                        | 光强传感器的采样周期。修改后会影响所有状态的反应速度。                           |
| `FILTER_WINDOW_SIZE`      | 5      | 个   | 所有状态（全局滤波）                        | 滑动平均滤波的窗口大小。值越大光强曲线越平滑，但响应变慢。                       |
| `START_CONFIRM_FRAMES`    | 2      | 帧   | `STATE_WAITING_START`                       | 开始触发所需连续低于阈值的帧数（每帧100ms）。防止瞬间干扰。                      |
| `END_CONFIRM_TOLERANCE`   | 1.1    | 无   | `STATE_CONFIRMING_END`                      | 结束确认时的容错系数：光强 < `endThreshold * 1.1` 即视为有效低点。值越大越宽容。 |

### 其他固定数值（非用户可调，但可手动修改代码）

- **光强标定启动阈值 `800`**：硬编码在 `handleStateCalibrating` 中。若环境光线较弱，可降低此值；但若低于此值标定可能不准确。
- **安全锁倍数 `2 * CAR_DELAY_MS`**：强制退出确认期的保护机制，通常无需修改。

## 4. 使用建议

- **调节触发灵敏度**：优先修改 `START_PERCENT` 和 `END_PERCENT`。数值越小越敏感。
- **抗干扰**：增大 `FILTER_WINDOW_SIZE` 或 `START_CONFIRM_FRAMES` 可减少误触发。
- **调整反应总时长**：修改 `PROTECTION_TIME_MS` 和 `CONFIRM_TIME_MS` 的组合。
- **上位机兼容性**：`Serial.println(g_lightRaw)` 每 100 ms 输出一次，格式与原始代码完全一致，无需修改 Python 端。

## 5. 注意事项

- 标定时光强必须 **> 800**，否则系统会一直等待强光。请确保反应容器放置在光源下。
- 保护期内即使光强远低于 `endThreshold` 也不会停车，这是为了防止溶液加入瞬间的抖动导致过早结束。
- 确认期采用比例滤波（≥50% 有效低点），可有效避免飞虫、灰尘等短暂遮挡造成的误停车。
- 所有状态均非阻塞（无 `delay`），不影响采样精度。

---

*文档版本：1.0*  
*对应代码：重构后 `hym-2.ino`（已删除串口屏）*