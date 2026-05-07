"""
数据处理模块——负责光强数据的数学计算和状态判定

本模块包含所有与数据计算相关的函数，例如：
- 从串口原始行解析数据值
- 计算反应过程中的平均光强、最低光强
- 处理标定阶段的数据收集
- 生成 JSON 原始数据点

【类比解释】这个模块就像“实验记录本上的计算器”——你给它一串光强数字，
它帮你算出平均值、最小值，并判断当前处于实验的哪个阶段。

【新增功能】
本模块新增了 pending_json_state 状态机，用于精确标记 JSON 数据点的事件类型。
"""

import time
import re


class DataProcessor:
    """
    [置信度: 高]
    输入参数详解:
        app: ArduinoSerialMonitor 主应用实例
    返回值详解:
        无
    主要算法逻辑简述:
        负责解析串口指令、处理数值数据、更新反应状态。
        所有方法不直接操作 UI，仅修改 app 属性。
    """

    TRIGGER_PERCENT = 0.20

    def __init__(self, app):
        self.app = app

    def parse_serial_line(self, line: str) -> None:
        """
        [置信度: 高]
        输入参数详解:
            line: 串口原始行字符串
        返回值详解:
            无
        主要算法逻辑简述:
            根据字符串内容分发到不同的状态处理方法。
        边界条件与限制:
            数值解析失败时静默忽略。
        """
        if line == "WAITING_REACTION":
            self.app.experiment_status_var.set("状态: 正在标定环境光强...")
            self.app.calibration_data.clear()
            self.app.serial.start_json_recording()

        elif line.startswith("REACTION_START:"):
            self._handle_reaction_start()

        elif line.startswith("REACTION_TIME:") and line.endswith("ms"):
            self._handle_reaction_end(line)

        elif line == "MEASUREMENT_COMPLETE":
            self.app.experiment_status_var.set("状态: 小车已停止，导出数据")
            self.app.serial.extract_and_save_data()
            self.app.serial.save_json_raw_data()

        elif line == "SYSTEM_RESET":
            self.app.experiment_status_var.set("状态: 待命准备重置")
            self.app.baseline_light = None
            self.app.rt_baseline_var.set("环境基准: --")
            self.app.rt_avg_var.set("反应期平均: --")
            self.app.rt_min_var.set("探测最低点: --")

        else:
            try:
                value = int(re.findall(r'-?\d+', line)[0])
                self._process_raw_light_data(value)
            except IndexError:
                pass  # 非数值行，忽略

    def _handle_reaction_start(self):
        """处理 REACTION_START 指令"""
        self.app.experiment_status_var.set("状态: 反应进行中...")
        self.app.is_reacting = True
        self.app.pending_json_state = "反应开始"
        self.app.min_light = 9999
        self.app.react_sum = 0
        self.app.react_count = 0

        with self.app.lock:
            if self.app.time_data:
                self.app.reaction_start_marker = self.app.time_data[-1]
            if self.app.data_buffer:
                self.app.start_light = self.app.data_buffer[-1]
                if not self.app.baseline_light:
                    self.app.baseline_light = self.app.start_light

    def _handle_reaction_end(self, line: str):
        """处理 REACTION_TIME:xxxms 指令"""
        self.app.experiment_status_var.set("状态: 反应结束，正在确认...")
        self.app.pending_json_state = "反应结束"

        ms = int(line.replace("REACTION_TIME:", "").replace("ms", ""))
        self.app.reaction_duration = ms / 1000.0
        self.app.reaction_time_var.set(f"{self.app.reaction_duration:.2f} 秒")

        if self.app.react_count > 0:
            self.app.avg_light = int(self.app.react_sum / self.app.react_count)

        with self.app.lock:
            if self.app.time_data:
                self.app.reaction_end_marker = self.app.time_data[-1]
            if self.app.data_buffer:
                self.app.end_light = self.app.data_buffer[-1]

    def _process_raw_light_data(self, value: int):
        """
        [置信度: 高]
        输入参数详解:
            value: 解析出的光强数值
        返回值详解:
            无
        主要算法逻辑简述:
            1. 更新数据缓存与当前光强显示
            2. 标定阶段：收集数据并计算环境基准
            3. 反应阶段：更新最低光强、平均光强，并记录 JSON 数据点
        边界条件与限制:
            线程安全：对 data_buffer/time_data 的写入使用锁保护。
        """
        current_time = time.time() - self.app.absolute_start_time

        with self.app.lock:
            self.app.data_buffer.append(value)
            self.app.time_data.append(current_time)

        self.app.rt_current_var.set(f"当前光强: {value}")

        # 标定阶段
        if self.app.experiment_status_var.get() == "状态: 正在标定环境光强...":
            self.app.calibration_data.append(value)
            if len(self.app.calibration_data) > 20:
                self.app.baseline_light = int(sum(self.app.calibration_data) / len(self.app.calibration_data))
                self.app.rt_baseline_var.set(f"环境基准: {self.app.baseline_light}")
                self.app.experiment_status_var.set("状态: 标定完成，等待加入")

        # JSON 录制（只要录制开关打开就记录）
        if self.app.is_json_recording:
            current_gui_status = self.app.experiment_status_var.get()
            relative_json_time = round(current_time - self.app.json_start_time, 2)
            self.app.reaction_raw_data.append({
                "plot_time": round(current_time, 2),
                "relative_time": relative_json_time,
                "light": value,
                "状态": current_gui_status
            })

        # 反应中数据统计
        if self.app.is_reacting:
            if value < self.app.min_light:
                self.app.min_light = value
                self.app.rt_min_var.set(f"探测最低点: {self.app.min_light}")
            self.app.react_sum += value
            self.app.react_count += 1
            self.app.rt_avg_var.set(f"反应期平均: {int(self.app.react_sum / self.app.react_count)}")