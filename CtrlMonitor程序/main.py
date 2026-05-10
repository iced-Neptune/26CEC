"""
Arduino 光敏传感器监测系统 - 主入口模块
现在你可以直接用：python main.py 启动程序。
"""
import matplotlib
matplotlib.use('TkAgg')          # 必须在这之前锁定后端，避免引入 Qt

import tkinter as tk

from src.ui.monitor_ui import MonitorUI
from src.core.serial_handler import SerialHandler
from src.core.data_processor import DataProcessor
from src.core.plot_manager import PlotManager
from src.utils.config_manager import ConfigManager
from src.utils.file_dialog import FileDialogManager


class ArduinoSerialMonitor:
    """主监测器类——通过组合方式整合各功能模块。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._initialize_attributes()
        self._init_modules()
        self.ui.setup_ui()
        self.serial.refresh_ports()
        self.root.after(100, self.file_dialog.ask_save_preference)

    def _initialize_attributes(self):
        # 所有属性初始化
        self.csv_filepath = None
        self.json_dir = None
        self.serial_port = None
        self.is_connected = False
        from collections import deque
        import time
        import threading
        self.data_buffer = deque(maxlen=8000)
        self.time_data = deque(maxlen=8000)
        self.absolute_start_time = time.time()
        self.lock = threading.Lock()
        self.reaction_start_marker = None
        self.reaction_end_marker = None
        self.is_reacting = False
        self.baseline_light = None
        self.start_light = None
        self.min_light = 9999
        self.end_light = None
        self.avg_light = None
        self.react_sum = 0
        self.react_count = 0
        self.reaction_duration = None
        self.calibration_data = []
        self.reaction_raw_data = []
        self.pending_json_state = None
        self.is_json_recording = False
        self.json_start_time = 0.0
        self.port_var = None
        self.port_combo = None
        self.baud_var = None
        self.baud_combo = None
        self.connect_button = None
        self.window_var = None
        self.is_receiving_var = None
        self.is_frozen_var = None
        self.status_var = None
        self.text_display = None
        self.time_slider = None
        self.fig = None
        self.plot = None
        self.canvas = None
        self.line_main = None
        self.line_base = None
        self.line_thresh = None
        self.vline_start = None
        self.vline_end = None
        self.crosshair_v = None
        self.crosshair_h = None
        self.tooltip = None
        self.experiment_status_var = None
        self.reaction_time_var = None
        self.rt_baseline_var = None
        self.rt_current_var = None
        self.rt_avg_var = None
        self.rt_min_var = None
        self.main_frame = None
        self.left_main_frame = None
        self.right_main_frame = None
        self.top_frame = None
        self.left_frame = None
        self.right_frame = None
        self.bottom_frame = None
        self.slider_frame = None
        self.reaction_display_frame = None
        self.realtime_data_frame = None
        self.vc_var = None
        self.tem_var = None
        self.TRIGGER_PERCENT = 0.02  # 反应触发阈值百分比（相对于基准光强）

    def _init_modules(self):
        self.ui = MonitorUI(self)
        self.processor = DataProcessor(self)
        self.serial = SerialHandler(self)
        self.plotter = PlotManager(self)
        self.config = ConfigManager(self)
        self.file_dialog = FileDialogManager(self)
        self.refresh_ports = self.serial.refresh_ports
        self.toggle_connection = self.serial.toggle_connection
        self.restart_measurement = self.serial.restart_measurement
        self.on_mouse_move = self.ui.on_mouse_move
        self.on_slider_move = self.ui.on_slider_move


if __name__ == "__main__":
    root = tk.Tk()
    app = ArduinoSerialMonitor(root)
    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.mainloop()