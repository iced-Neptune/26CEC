"""
数据处理模块——负责光强数据的数学计算和状态判定

本模块包含所有与数据计算相关的函数，例如：
- 从串口原始行解析数据值
- 计算反应过程中的平均光强、最低光强
- 处理标定阶段的数据收集
- 生成 JSON 原始数据点

【类比解释】这个模块就像“实验记录本上的计算器”——你给它一串光强数字，
它帮你算出平均值、最小值，并判断当前处于实验的哪个阶段。
"""

import time
import re


class DataProcessor:
    """
    数据处理器——负责所有与数值计算和状态判定相关的逻辑。

    所有方法都不涉及 UI 更新，只做纯数据计算，结果通过修改 app 的属性来传递。
    """

    # 触发反应的光强下降比例（20%）
    TRIGGER_PERCENT = 0.20

    def __init__(self, app):
        """
        [置信度: 高]
        输入参数详解:
            app: ArduinoSerialMonitor 主应用实例
        返回值详解:
            无
        主要算法逻辑简述:
            保存 app 引用，供后续方法访问共享数据
        """
        self.app = app

    def parse_serial_line(self, line: str) -> None:
        """
        [置信度: 高]
        输入参数详解:
            line: 从串口读取的一行原始字符串（已去除首尾空白）
        返回值详解:
            无
        主要算法逻辑简述:
            根据字符串内容分发到不同的处理分支：
            - "WAITING_REACTION" → 进入环境标定状态
            - "REACTION_START:" → 标记反应开始
            - "REACTION_TIME:xxxms" → 记录反应耗时
            - "MEASUREMENT_COMPLETE" → 触发数据导出
            - "SYSTEM_RESET" → 重置所有状态
            - 其他 → 尝试解析为光强数值
        边界条件与限制:
            - 数值解析失败时静默忽略（保持程序稳定）
            - 依赖 self.app 上的各种状态变量
        """
        if line == "WAITING_REACTION":
            self.app.experiment_status_var.set("状态: 正在标定环境光强...")
            self.app.calibration_data.clear()

        elif line.startswith("REACTION_START:"):
            self._handle_reaction_start()

        elif line.startswith("REACTION_TIME:") and line.endswith("ms"):
            self._handle_reaction_end(line)

        elif line == "MEASUREMENT_COMPLETE":
            self.app.experiment_status_var.set("状态: 小车已停止，导出数据")
            # 注意：这些方法属于 core 模块的其他类，通过 app 访问
            self.app.serial.extract_and_save_data()
            self.app.serial.save_json_raw_data()

        elif line == "SYSTEM_RESET":
            self.app.experiment_status_var.set("状态: 系统重置，等待强光")
            self.app.baseline_light = None
            self.app.rt_baseline_var.set("环境基准: --")
            self.app.rt_avg_var.set("反应平均: --")
            self.app.rt_min_var.set("反应最低: --")

        else:
            # 尝试从字符串中提取数值
            try:
                value = int(re.findall(r'-?\d+', line)[0])
                self.process_data_point(value)
            except IndexError:
                # 无法解析为数值的行，静默忽略
                pass

    def _handle_reaction_start(self):
        """
        [置信度: 高]
        输入参数详解:
            无（通过 self.app 访问共享数据）
        返回值详解:
            无
        主要算法逻辑简述:
            - 更新 UI 状态为“反应进行中”
            - 设置 is_reacting = True
            - 记录反应开始时刻的 X 轴位置和光强值
            - 重置累加器和最低光强记录
            - 清空原始数据缓存
        边界条件与限制:
            - 如果此时尚无环境基准光强，则用开始瞬间的光强作为基准
        """
        self.app.experiment_status_var.set("状态: 反应进行中...")
        self.app.is_reacting = True
        self.app.pending_json_state = "反应开始"
        self.app.min_light = 9999
        self.app.react_sum = 0
        self.app.react_count = 0
        self.app.reaction_raw_data.clear()

        with self.app.lock:
            if self.app.time_data:
                self.app.reaction_start_marker = self.app.time_data[-1]
            if self.app.data_buffer:
                self.app.start_light = self.app.data_buffer[-1]
                if not self.app.baseline_light:
                    self.app.baseline_light = self.app.start_light

    def _handle_reaction_end(self, line: str):
        """
        [置信度: 高]
        输入参数详解:
            line: 格式为 "REACTION_TIME:xxxms" 的字符串
        返回值详解:
            无
        主要算法逻辑简述:
            - 从字符串中提取毫秒数，转换为秒
            - 更新 UI 显示的反应耗时
            - 计算反应过程中的平均光强
            - 记录反应结束时刻的 X 轴位置和光强值
        边界条件与限制:
            - 如果 react_count == 0（没有收集到数据点），平均光强保持为 None
        """
        self.app.experiment_status_var.set("状态: 反应结束，正在记录...")
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

    def process_data_point(self, value: int):
        """
        [置信度: 高]
        输入参数详解:
            value: 解析出的光强数值（整数）
        返回值详解:
            无
        主要算法逻辑简述:
            1. 计算相对时间，将数据追加到 data_buffer 和 time_data
            2. 更新当前光强显示
            3. 如果处于标定阶段，收集标定数据；收集满20个点后计算环境基准
            4. 如果处于反应阶段，收集反应数据，更新最低光强和平均光强
        边界条件与限制:
            - 标定阶段的数据收集使用简单平均，未做异常值剔除
            - 线程安全：对 data_buffer 和 time_data 的写入使用锁保护
        """
        current_time = time.time() - self.app.absolute_start_time

        with self.app.lock:
            self.app.data_buffer.append(value)
            self.app.time_data.append(current_time)

        self.app.rt_current_var.set(f"当前光强: {value}")

        # 标定阶段处理
        if self.app.experiment_status_var.get() == "状态: 正在标定环境光强...":
            self.app.calibration_data.append(value)
            if len(self.app.calibration_data) > 20:
                self.app.baseline_light = int(
                    sum(self.app.calibration_data) / len(self.app.calibration_data)
                )
                self.app.rt_baseline_var.set(f"环境基准: {self.app.baseline_light}")
                self.app.experiment_status_var.set("状态: 标定完成，等待溶液加入")

        # 反应中数据收集
        if self.app.is_reacting or self.app.pending_json_state == "反应结束":
            self._append_json_data_point(current_time, value)

            if value < self.app.min_light:
                self.app.min_light = value
                self.app.rt_min_var.set(f"反应最低: {self.app.min_light}")

            self.app.react_sum += value
            self.app.react_count += 1
            current_avg = int(self.app.react_sum / self.app.react_count)
            self.app.rt_avg_var.set(f"反应平均: {current_avg}")

    def _append_json_data_point(self, current_time: float, value: int):
        """
        [置信度: 高]
        输入参数详解:
            current_time: 当前数据点的相对时间（秒）
            value: 当前光强数值
        返回值详解:
            无
        主要算法逻辑简述:
            - 根据 pending_json_state 确定当前点的状态标签
            - 计算相对于反应开始时刻的时间偏移
            - 将数据点以字典形式追加到 reaction_raw_data 列表
        边界条件与限制:
            - 依赖 reaction_start_marker 不为 None
            - pending_json_state 在消费后立即置为 None，防止重复标记
        """
        current_state_label = "反应中"

        if self.app.pending_json_state == "反应开始":
            current_state_label = "反应开始"
            self.app.pending_json_state = None
        elif self.app.pending_json_state == "反应结束":
            current_state_label = "反应结束"
            self.app.pending_json_state = None
            self.app.is_reacting = False

        relative_time = round(current_time - self.app.reaction_start_marker, 2)

        self.app.reaction_raw_data.append({
            "time": relative_time,
            "light": value,
            "状态": current_state_label
        })

    def calculate_trigger_threshold(self) -> float:
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            触发阈值（float），即 baseline_light * (1 - TRIGGER_PERCENT)
        主要算法逻辑简述:
            如果 baseline_light 存在，返回其 80%；否则返回 0
        边界条件与限制:
            - 若 baseline_light 为 None，返回 0 作为安全默认值
        """
        if self.app.baseline_light is not None:
            return self.app.baseline_light * (1 - self.TRIGGER_PERCENT)
        return 0.0