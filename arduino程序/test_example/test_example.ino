// 碘钟反应上位机测试专用 - 模拟信号发射器
// 采样频率: 100Hz (10ms)
// 模拟流程: 标定环境 -> 加入溶液 -> 反应进行 -> 颜色突变 -> 测量完成

unsigned long startTime = 0;
bool waitSent = false;
bool startSent = false;
bool timeSent = false;
bool completeSent = false;

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0)); // 初始化随机噪声种子
  startTime = millis();
}

void loop() {
  // 监听来自 Python 上位机的复位指令
  if (Serial.available() > 0) {
    String msg = Serial.readString();
    if (msg.indexOf("RESET") >= 0) {
      startTime = millis();
      waitSent = false;
      startSent = false;
      timeSent = false;
      completeSent = false;
      Serial.println("SYSTEM_RESET");
    }
  }

  unsigned long now = millis() - startTime;
  int lightValue = 850;

  // ---------------- 模拟反应时间轴 ----------------
  
  if (now < 1000) {
    // 阶段 0: 启动初期，维持高光强
    lightValue = 850 + random(-5, 6);
  } 
  else if (now < 4000) {
    // 阶段 1: 发送标定信号，继续维持高光强让上位机收集基准
    if (!waitSent) {
      Serial.println("WAITING_REACTION");
      waitSent = true;
    }
    lightValue = 850 + random(-5, 6);
  } 
  else if (now < 4500) {
    // 阶段 2: 模拟加入溶液，光强在 0.5 秒内斜坡下降
    lightValue = map(now, 4000, 4500, 850, 600) + random(-5, 6);
  } 
  else if (now < 15000) {
    // 阶段 3: 反应进行期 (约 10.5 秒)。光强微幅下降
    if (!startSent) {
      Serial.print("REACTION_START:");
      Serial.println(millis());
      startSent = true;
    }
    lightValue = 600 - map(now, 4500, 15000, 0, 50) + random(-5, 6);
  } 
  else if (now < 16000) {
    // 阶段 4: 模拟碘钟颜色突变（1秒内断崖式下跌）
    lightValue = 550 - map(now, 15000, 16000, 0, 450) + random(-5, 6);
  } 
  else if (now < 17000) {
    // 阶段 5: 变色完成，发送结束指令和计算耗时 (11.5秒)
    if (!timeSent) {
      Serial.print("REACTION_TIME:");
      Serial.print(16000 - 4500); // 模拟耗时 11500 ms
      Serial.println("ms");
      timeSent = true;
    }
    lightValue = 100 + random(-2, 3);
  } 
  else {
    // 阶段 6: 彻底结束，输出数据保存信号
    if (!completeSent) {
      Serial.println("MEASUREMENT_COMPLETE");
      completeSent = true;
    }
    lightValue = 100 + random(-2, 3);
  }

  // ---------------- 数据发送区 ----------------
  
  Serial.println(lightValue);
  delay(100); // 严格维持 100Hz 的发送频率
}