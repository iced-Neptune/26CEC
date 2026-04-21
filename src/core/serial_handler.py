"""
串口通信模块——负责串口连接、数据读取、数据导出等功能

本模块包含：
- 串口连接/断开控制
- 后台线程持续读取串口数据
- CSV 汇总数据导出
- JSON 原始数据导出
- 测量状态重置

【类比解释】这个模块就像“实验室设备的数据线”——它负责把 Arduino
传过来的数字信号接收下来，交给“计算器”（DataProcessor）去处理，
同时也负责把实验结果保存成文件。
"""

import threading
import time
import csv
import os
import json

import numpy as np


class SerialHandler:
    """
    串口处理器——负责所有与串口通信和数据持久化相关的逻辑。
    """

    def __init__(self, app):
        """
        [置信度: 高]
        输入参数详解:
            app: ArduinoSerialMonitor 主应用实例
        返回值详解:
            无
        """
        self.app = app

    def refresh_ports(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            使用 pyserial 的 list_ports 获取系统可用串口列表，
            更新下拉框的选项，并自动选中第一个
        边界条件与限制:
            - 如果没有可用串口，下拉框保持为空
        """
        import serial.tools.list_ports
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.app.port_combo['values'] = ports
        if ports:
            self.app.port_var.set(ports[0])

    def toggle_connection(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            如果当前未连接，则尝试打开串口，启动后台读取线程和绘图线程，
            并调用 restart_measurement 初始化测量状态；
            如果已连接，则关闭串口并更新 UI 状态。
        边界条件与限制:
            - 串口打开失败时会捕获异常并在状态栏显示“连接失败”
            - 后台线程均为 daemon 线程，主程序退出时自动结束
        """
        if not self.app.is_connected:
            try:
                import serial
                self.app.serial_port = serial.Serial(
                    self.app.port_var.get(),
                    int(self.app.baud_var.get()),
                    timeout=0.1
                )
                self.app.is_connected = True
                self.app.connect_button.config(text="断开")
                self.app.status_var.set(f"已连接 {self.app.port_var.get()}")

                threading.Thread(target=self._read_serial_loop, daemon=True).start()
                threading.Thread(target=self.app.plotter.update_plot_loop, daemon=True).start()

                self.restart_measurement()
            except Exception as e:
                self.app.status_var.set("连接失败")
        else:
            self.app.serial_port.close()
            self.app.is_connected = False
            self.app.connect_button.config(text="连接")
            self.app.status_var.set("已断开")

    def _read_serial_loop(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            在 while 循环中持续检查串口是否有数据到达，
            每读到一行就交给 DataProcessor 解析
        边界条件与限制:
            - 循环条件为 self.app.is_connected，断开时自动退出
            - 解码失败时使用 errors='replace' 防止程序崩溃
        """
        while self.app.is_connected:
            try:
                if self.app.serial_port.in_waiting > 0:
                    line = self.app.serial_port.readline().decode(
                        'utf-8', errors='replace'
                    ).strip()
                    if line:
                        # 在日志中显示原始数据
                        self.app.text_display.insert(tk.END, f"{line}\n")
                        self.app.text_display.see(tk.END)
                        # 交给数据处理器解析
                        self.app.processor.parse_serial_line(line)
            except Exception:
                time.sleep(0.1)

    def restart_measurement(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            重置所有与反应测量相关的状态变量，并通过串口发送 RESET 指令
        边界条件与限制:
            - 仅在已连接状态下发送 RESET 指令
        """
        self.app.reaction_start_marker = None
        self.app.reaction_end_marker = None
        self.app.reaction_time_var.set("-- 秒")
        self.app.experiment_status_var.set("状态: 等待启动...")

        if self.app.is_connected and self.app.serial_port:
            self.app.serial_port.write(b"RESET\n")

    def extract_and_save_data(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            从数据缓存中提取汇总数据（基准光强、开始/结束/最低/平均光强、
            结束后0.5s和1.0s的光强值、反应耗时），以追加模式写入 CSV 文件
        边界条件与限制:
            - 如果 csv_filepath 未设置或 reaction_end_marker 为 None，则跳过
            - CSV 写入失败时在日志中显示错误提示
        """
        if not self.app.csv_filepath or not self.app.reaction_end_marker:
            return

        with self.app.lock:
            times = list(self.app.time_data)
            lights = list(self.app.data_buffer)

        target_05s = self.app.reaction_end_marker + 0.5
        target_10s = self.app.reaction_end_marker + 1.0

        light_05s = self._find_closest_value(times, lights, target_05s)
        light_10s = self._find_closest_value(times, lights, target_10s)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(self.app.csv_filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    self.app.baseline_light,
                    self.app.start_light,
                    self.app.avg_light,
                    self.app.min_light,
                    self.app.end_light,
                    light_05s,
                    light_10s,
                    self.app.reaction_duration
                ])
            self.app.text_display.insert(tk.END, "✅ CSV 汇总数据已安全追加！\n")
        except Exception as e:
            self.app.text_display.insert(tk.END, "❌ CSV 保存失败，表格可能正在被占用。\n")

    def _find_closest_value(self, time_list, value_list, target_time):
        """
        [置信度: 高]
        输入参数详解:
            time_list: 时间戳列表
            value_list: 对应的数值列表
            target_time: 要查找的目标时间点
        返回值详解:
            最接近目标时间点的数值；如果列表为空，返回 "N/A"
        主要算法逻辑简述:
            使用 numpy 计算绝对差最小的索引，返回对应的数值
        边界条件与限制:
            - 时间列表和数值列表长度应相同（由调用方保证）
        """
        if not time_list:
            return "N/A"
        idx = (np.abs(np.array(time_list) - target_time)).argmin()
        return value_list[idx]

    def save_json_raw_data(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            将 reaction_raw_data 列表序列化为 JSON 文件，保存到用户指定的目录
        边界条件与限制:
            - 如果 json_dir 未设置或 raw_data 为空，则跳过
            - JSON 文件命名格式：RawData_YYYYMMDD_HHMM.json
        """
        if not self.app.json_dir or not self.app.reaction_raw_data:
            return

        file_name = f"RawData_{time.strftime('%Y%m%d_%H%M')}.json"
        full_path = os.path.join(self.app.json_dir, file_name)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("[\n")
                total_items = len(self.app.reaction_raw_data)
                for i, data_point in enumerate(self.app.reaction_raw_data):
                    line_str = json.dumps(
                        data_point, ensure_ascii=False, separators=(', ', ': ')
                    )
                    if i < total_items - 1:
                        f.write(f"  {line_str},\n")
                    else:
                        f.write(f"  {line_str}\n")
                f.write("]\n")
            self.app.text_display.insert(tk.END, f"✅ JSON源数据已导出: {file_name}\n")
            self.app.text_display.see(tk.END)
        except Exception as e:
            self.app.text_display.insert(tk.END, f"❌ JSON文件保存失败: {e}\n")

# 在模块末尾添加 tk 的导入（用于日志写入）
import tkinter as tk