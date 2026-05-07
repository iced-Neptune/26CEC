// CHEM_E_CAR - 比赛增强版 (动态基准线 + 见好就收)
// MODIFIED: 重构状态机，统一命名风格，删除串口屏，提取常量

/* ========== 用户可调参数区 ========== */
// 触发开始的下降比例（光强比环境基准下降 15% 判定为加入溶液）
const float START_PERCENT = 0.15;
// 触发结束的下降比例（"见好就收"，下降 25% 立即停车）
const float END_PERCENT = 0.25;
// 小车延迟启动/停止时间 (毫秒)
const uint32_t CAR_DELAY_MS = 1000;
// 反应保护期 (10秒内忽略光强变化)
const uint32_t PROTECTION_TIME_MS = 10000;
// 结束确认时间 (防误触，毫秒)
const uint32_t CONFIRM_TIME_MS = 800;
// 标定采样总时长 (毫秒)
const uint32_t CALIBRATION_DURATION_MS = 3000;
// 标定初始跳过时间 (避开通电不稳定，毫秒)
const uint32_t CALIBRATION_SKIP_MS = 500;
// 光强采样周期 (毫秒)
const uint32_t SAMPLING_INTERVAL_MS = 100;
// 滑动平均滤波窗口大小
const uint8_t FILTER_WINDOW_SIZE = 5;
// 开始触发确认帧数 (连续低于阈值的次数)
const uint8_t START_CONFIRM_FRAMES = 2;
// 结束确认容错系数 (允许光强低于 endThreshold * 1.1 就算有效)
const float END_CONFIRM_TOLERANCE = 1.1;
/* ========== 引脚定义区 ========== */
const int PIN_BUZZER = 2;
const int PIN_LIGHT = A4;
const int PIN_CAR = 12;

/* ========== 全局变量区 ========== */
// 状态机枚举
enum SystemState {
  STATE_CALIBRATING,       // 0: 标定环境光
  STATE_WAITING_START,     // 1: 等待溶液加入
  STATE_REACTING,          // 2: 反应进行中
  STATE_CONFIRMING_END,    // 3: 确认反应结束
  STATE_FINISHED,          // 4: 测量完成
  STATE_IDLE               // 5: 闲置
};
SystemState g_state = STATE_CALIBRATING;

// 时间相关
uint32_t g_calibStartTime = 0;
uint32_t g_startTime = 0;
uint32_t g_confirmStart = 0;
uint32_t g_lastSampleTime = 0;

// 传感器与基准
int g_lightRaw = 0;
float g_baselineLight = 0.0;
int g_startThreshold = 0;
int g_endThreshold = 0;

// 滑动平均滤波缓冲区
int g_filterReadings[FILTER_WINDOW_SIZE];
int g_filterTotal = 0;
uint8_t g_filterIndex = 0;

// 状态机辅助变量
bool g_carOn = false;
int g_confirmLowCount = 0;
int g_confirmTotalCount = 0;

// 标定辅助
long g_calibSum = 0;
int g_calibCount = 0;

/* ========== 函数声明 ========== */
void handleStateMachine(uint32_t now);
void handleStateCalibrating(uint32_t now);
void handleStateWaitingStart(uint32_t now);
void handleStateReacting(uint32_t now);
void handleStateConfirmingEnd(uint32_t now);
void handleStateFinished(uint32_t now);
void handleStateIdle(uint32_t now);
void startCalibration(uint32_t now);
void startReaction(uint32_t now);
void resetSystem();
void updateLightSensor();

/* ========== setup & loop ========== */
void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_CAR, OUTPUT);

  // 初始化滑动平均滤波器
  for (int i = 0; i < FILTER_WINDOW_SIZE; i++) {
    g_filterReadings[i] = analogRead(PIN_LIGHT);
    g_filterTotal += g_filterReadings[i];
  }
  g_lightRaw = g_filterTotal / FILTER_WINDOW_SIZE;

  Serial.println("SYSTEM_READY");
  startCalibration(millis());
}

void loop() {
  uint32_t now = millis();

  // 每 100ms 采样一次
  if (now - g_lastSampleTime >= SAMPLING_INTERVAL_MS) {
    g_lastSampleTime = now;
    updateLightSensor();               // 更新 g_lightRaw
    Serial.println(g_lightRaw);        // 向上位机发送实时光强（格式不变）
    handleStateMachine(now);           // 状态机处理
  }

  // 监听来自上位机的重置指令（删除 TJC 部分）
  if (Serial.available()) {
    String cmd = Serial.readString();
    if (cmd.indexOf("RESET") >= 0) {
      resetSystem();
    }
  }
}

/* ========== 状态机实现 ========== */
void handleStateMachine(uint32_t now) {
  switch (g_state) {
    case STATE_CALIBRATING:
      handleStateCalibrating(now);
      break;
    case STATE_WAITING_START:
      handleStateWaitingStart(now);
      break;
    case STATE_REACTING:
      handleStateReacting(now);
      break;
    case STATE_CONFIRMING_END:
      handleStateConfirmingEnd(now);
      break;
    case STATE_FINISHED:
      handleStateFinished(now);
      break;
    case STATE_IDLE:
      handleStateIdle(now);
      break;
  }
}

// 状态0：标定环境光（要求光强 > 800 才开始）
void handleStateCalibrating(uint32_t now) {
  // 只有光强大于 800 才允许标定（避免暗环境误标定）
  if (g_lightRaw > 800) {
    if (now - g_calibStartTime < CALIBRATION_DURATION_MS) {
      // 跳过前 500ms 不稳定数据
      if (now - g_calibStartTime > CALIBRATION_SKIP_MS) {
        g_calibSum += g_lightRaw;
        g_calibCount++;
      }
    } else {
      // 标定结束，计算基准线
      if (g_calibCount > 0) {
        g_baselineLight = (float)g_calibSum / g_calibCount;
        g_startThreshold = (int)(g_baselineLight * (1.0 - START_PERCENT));
        g_endThreshold = (int)(g_baselineLight * (1.0 - END_PERCENT));
        Serial.println("WAITING_REACTION");
        tone(PIN_BUZZER, 500, 200);
        g_state = STATE_WAITING_START;
      } else {
        // 极小概率错误，重新标定
        startCalibration(now);
      }
    }
  } else {
    // 光强不足 800，重置标定计时器，等待强光
    g_calibStartTime = now;
    g_calibSum = 0;
    g_calibCount = 0;
  }
}

// 状态1：等待溶液加入（检测光强跌破开始阈值）
void handleStateWaitingStart(uint32_t now) {
  static int stableCount = 0;   // 局部静态变量，保持连续计数
  if (g_lightRaw < g_startThreshold) {
    if (++stableCount >= START_CONFIRM_FRAMES) {
      startReaction(now);
      stableCount = 0;
    }
  } else {
    stableCount = 0;
  }
}

// 状态2：反应中（保护期 + 延时发车 + 监测结束条件）
void handleStateReacting(uint32_t now) {
  // 延时1秒后启动小车
  if (!g_carOn && (now - g_startTime) >= CAR_DELAY_MS) {
    digitalWrite(PIN_CAR, HIGH);
    g_carOn = true;
  }

  // 10秒保护期结束后，监测是否跌破结束阈值
  if ((now - g_startTime) > PROTECTION_TIME_MS) {
    if (g_lightRaw < g_endThreshold) {
      g_confirmStart = now;
      g_confirmLowCount = 0;
      g_confirmTotalCount = 0;
      g_state = STATE_CONFIRMING_END;
      tone(PIN_BUZZER, 1000, 100);
      Serial.println("END_DETECTED");
    }
  }
}

// 状态3：确认期（防误触，800ms 滤波）
void handleStateConfirmingEnd(uint32_t now) {
  g_confirmTotalCount++;
  // 容错：光强低于 endThreshold * 1.1 即算有效低点（原逻辑保留）
  if (g_lightRaw < (int)(g_endThreshold * END_CONFIRM_TOLERANCE)) {
    g_confirmLowCount++;
  }

  if (now - g_confirmStart >= CONFIRM_TIME_MS) {
    if (g_confirmLowCount >= (g_confirmTotalCount / 2)) {
      // 确认真实变色
      g_state = STATE_FINISHED;
      Serial.print("REACTION_TIME:");
      Serial.print(g_confirmStart - g_startTime);
      Serial.println("ms");
    } else {
      // 误报，返回反应中状态
      Serial.println("FALSE_ALARM");
      g_state = STATE_REACTING;
    }
  }

  // 安全锁：若卡在确认期超过 2*CAR_DELAY_MS，强行停车并进入闲置
  if (now - g_confirmStart >= (CAR_DELAY_MS * 2)) {
    digitalWrite(PIN_CAR, LOW);
    g_carOn = false;
    if (g_state == STATE_CONFIRMING_END) {
      g_state = STATE_IDLE;
    }
  }
}

// 状态4：测量完成，延时停车
void handleStateFinished(uint32_t now) {
  if (now - g_confirmStart >= CAR_DELAY_MS) {
    digitalWrite(PIN_CAR, LOW);
    g_carOn = false;
    Serial.println("MEASUREMENT_COMPLETE");
    // 删除所有串口屏代码（原 sprintf + TJC.print 已移除）
    g_state = STATE_IDLE;
  }
}

// 状态5：闲置状态，等待 RESET 命令
void handleStateIdle(uint32_t now) {
  // 无动作，仅等待 resetSystem() 被外部调用
  (void)now; // 避免未使用参数警告
}

/* ========== 辅助函数 ========== */
void startCalibration(uint32_t now) {
  g_state = STATE_CALIBRATING;
  g_calibStartTime = now;
  g_calibSum = 0;
  g_calibCount = 0;
  g_baselineLight = 0.0;
}

void startReaction(uint32_t now) {
  g_startTime = now;
  g_state = STATE_REACTING;
  tone(PIN_BUZZER, 1000, 100);
  Serial.print("REACTION_START:");
  Serial.println(now);
}

void resetSystem() {
  startCalibration(millis());
  g_carOn = false;
  digitalWrite(PIN_CAR, LOW);

  // 重置滤波器历史
  g_filterTotal = 0;
  for (int i = 0; i < FILTER_WINDOW_SIZE; i++) {
    g_filterReadings[i] = analogRead(PIN_LIGHT);
    g_filterTotal += g_filterReadings[i];
  }
  g_filterIndex = 0;
  g_lightRaw = g_filterTotal / FILTER_WINDOW_SIZE;

  Serial.println("SYSTEM_RESET");
}

void updateLightSensor() {
  // 滑动平均滤波，与原始逻辑完全一致
  g_filterTotal -= g_filterReadings[g_filterIndex];
  g_filterReadings[g_filterIndex] = analogRead(PIN_LIGHT);
  g_filterTotal += g_filterReadings[g_filterIndex];
  g_filterIndex = (g_filterIndex + 1) % FILTER_WINDOW_SIZE;
  g_lightRaw = g_filterTotal / FILTER_WINDOW_SIZE;
}