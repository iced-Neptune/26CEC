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

"""
串口通信模块（增强版）——负责串口连接、数据读取、数据导出

新增功能：JSON 录制的手动开始/结束控制。
"""

import threading
import time
import csv
import os
import json
import tkinter as tk
from tkinter import messagebox

import numpy as np
import serial
import serial.tools.list_ports


class SerialHandler:
    """
    [置信度: 高]
    输入参数详解:
        app: 主应用实例
    返回值详解:
        无
    主要算法逻辑简述:
        处理串口 IO、数据持久化（CSV/JSON）、测量重置。
    """

    def __init__(self, app):
        self.app = app

    def refresh_ports(self):
        """刷新可用串口列表"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.app.port_combo['values'] = ports
        if ports:
            self.app.port_var.set(ports[0])

    def toggle_connection(self):
        """连接/断开串口"""
        if not self.app.is_connected:
            try:
                self.app.serial_port = serial.Serial(
                    self.app.port_var.get(),
                    int(self.app.baud_var.get()),
                    timeout=0.1
                )
                self.app.is_connected = True
                self.app.connect_button.config(text="⏹ 断开连接")
                self.app.status_var.set(f"状态: 已连接至 {self.app.port_var.get()}")

                threading.Thread(target=self._read_serial_loop, daemon=True).start()
                threading.Thread(target=self.app.plotter.update_plot_loop, daemon=True).start()

                self.restart_measurement()
            except Exception:
                self.app.status_var.set("连接失败: 检查端口占用")
        else:
            self.app.serial_port.close()
            self.app.is_connected = False
            self.app.connect_button.config(text="▶ 连接设备")
            self.app.status_var.set("状态: 离线")

    def _read_serial_loop(self):
        """串口读取后台循环"""
        while self.app.is_connected:
            try:
                if not self.app.is_receiving_var.get():
                    # 如果不允许接收，清空缓冲区并跳过
                    if self.app.serial_port.in_waiting > 0:
                        self.app.serial_port.read(self.app.serial_port.in_waiting)
                    time.sleep(0.1)
                    continue

                line = self.app.serial_port.readline().decode('utf-8', errors='replace').strip()
                if not line:
                    continue

                # 日志显示
                self.app.text_display.insert(tk.END, f"{line}\n")
                self.app.text_display.see(tk.END)

                # 交给数据处理器
                self.app.processor.parse_serial_line(line)

            except Exception:
                time.sleep(0.05)

    def start_json_recording(self):
        """手动开始 JSON 录制"""
        with self.app.lock:
            self.app.reaction_raw_data.clear()
            self.app.is_json_recording = True
            self.app.json_start_time = time.time() - self.app.absolute_start_time
        self.app.text_display.insert(tk.END, "▶ [启动] 已开始录制全新 JSON 轨迹...\n")
        self.app.text_display.see(tk.END)

    def stop_json_recording(self):
        """手动停止 JSON 录制并保存"""
        if self.app.is_json_recording:
            self.app.is_json_recording = False
            self.app.text_display.insert(tk.END, "⏹ [中止] 手动截断记录，准备导出...\n")
            self.save_json_raw_data()
        else:
            messagebox.showinfo("提示", "当前并未在记录新的 JSON 数据。")

    def restart_measurement(self):
        """重置测量状态"""
        self.app.reaction_start_marker = None
        self.app.reaction_end_marker = None
        self.app.reaction_time_var.set("-- 秒")
        self.app.experiment_status_var.set("状态: 准备就绪...")
        self.app.pending_json_state = None
        self.app.is_reacting = False

        if self.app.is_connected and self.app.serial_port:
            self.app.serial_port.write(b"RESET\n")

    def extract_and_save_data(self):
        """提取汇总数据并写入 CSV"""
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
        except Exception:
            self.app.text_display.insert(tk.END, "❌ CSV 保存失败，表格正在被占用。\n")

    def _find_closest_value(self, time_list, value_list, target_time):
        if not time_list:
            return "N/A"
        idx = (np.abs(np.array(time_list) - target_time)).argmin()
        return value_list[idx]

    def save_json_raw_data(self):
        """保存 JSON 原始数据"""
        if not self.app.json_dir or not self.app.reaction_raw_data:
            return

        file_name = f"RawData_{time.strftime('%Y%m%d_%H%M')}.json"
        full_path = os.path.join(self.app.json_dir, file_name)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("[\n")
                total_items = len(self.app.reaction_raw_data)
                for i, data_point in enumerate(self.app.reaction_raw_data):
                    line_str = json.dumps(data_point, ensure_ascii=False, separators=(', ', ': '))
                    if i < total_items - 1:
                        f.write(f"  {line_str},\n")
                    else:
                        f.write(f"  {line_str}\n")
                f.write("]\n")
            self.app.text_display.insert(tk.END, f"✅ JSON 已成功导出: {file_name}\n")
            self.app.text_display.see(tk.END)
        except Exception as e:
            self.app.text_display.insert(tk.END, f"❌ JSON保存失败: {e}\n")