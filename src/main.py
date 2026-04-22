"""
Arduino 光敏传感器监测系统 - 主入口模块

运行此文件即可启动整个监测应用程序。
用法：python -m src.main  或  python src/main.py
"""

import tkinter as tk
import time
import threading
from collections import deque

# 导入各功能模块
from src.ui.monitor_ui import MonitorUI
from src.core.serial_handler import SerialHandler
from src.core.data_processor import DataProcessor
from src.core.plot_manager import PlotManager
from src.utils.config_manager import ConfigManager
from src.utils.file_dialog import FileDialogManager


class ArduinoSerialMonitor:
    """
    主监测器类——通过组合方式整合各功能模块。

    将原有多重继承改为组合模式，每个模块作为独立的实例属性。
    这样做的好处是：
    1. 模块边界清晰，新人一眼就能看出“谁负责什么”
    2. 避免多重继承带来的方法查找顺序困惑
    3. 便于单元测试时单独替换某个模块
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self._initialize_attributes()
        self._init_modules()
        self.ui.setup_ui()
        self.serial.refresh_ports()
        self.root.after(100, self.file_dialog.ask_save_preference)

    def _initialize_attributes(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            初始化所有实例变量，包括文件路径、串口状态、数据缓存、反应标记等。
            所有属性集中在此，便于统一管理和查阅。
        边界条件与限制:
            变量数量较多，新增时需同步更新 UI 模块的引用。
        """
        # ===== 文件路径相关 =====
        self.csv_filepath = None
        self.json_dir = None

        # ===== 串口连接相关 =====
        self.serial_port = None
        self.is_connected = False

        # ===== 数据缓存 =====
        self.data_buffer = deque(maxlen=8000)      # 光强数据队列
        self.time_data = deque(maxlen=8000)        # 时间戳队列
        self.absolute_start_time = time.time()     # 程序启动时刻（用于计算相对时间）

        # ===== 线程安全 =====
        self.lock = threading.Lock()

        # ===== 反应状态标记 =====
        self.reaction_start_marker = None           # 反应开始的时刻（X轴坐标）
        self.reaction_end_marker = None             # 反应结束的时刻（X轴坐标）
        self.is_reacting = False                    # 是否正在反应中
        self.baseline_light = None                  # 环境基准光强
        self.start_light = None                     # 反应开始瞬间的光强
        self.min_light = 9999                       # 反应过程中的最低光强
        self.end_light = None                       # 反应结束瞬间的光强
        self.avg_light = None                       # 反应过程中的平均光强
        self.react_sum = 0                          # 累加器：反应过程中的光强总和
        self.react_count = 0                        # 计数器：反应过程中的数据点个数
        self.reaction_duration = None               # 反应耗时（秒）
        self.calibration_data = []                  # 标定阶段收集的数据

        # ===== JSON 专用缓存与状态 =====
        self.reaction_raw_data = []                 # 单次反应的原始数据点列表
        self.pending_json_state = None              # 待处理的JSON状态标记（'反应开始'/'反应结束'）
        self.is_json_recording = False              # 是否正在录制JSON数据
        self.json_start_time = 0.0                  # JSON录制的起始相对时间

        # ===== UI 变量占位（将在 MonitorUI.setup_ui() 中被赋值）=====
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
        # 新增绘图图层变量
        self.line_main = None
        self.line_base = None
        self.line_thresh = None
        self.vline_start = None
        self.vline_end = None
        self.crosshair_v = None
        self.crosshair_h = None
        self.tooltip = None
        # 右侧面板变量
        self.experiment_status_var = None
        self.reaction_time_var = None
        self.rt_baseline_var = None
        self.rt_current_var = None
        self.rt_avg_var = None
        self.rt_min_var = None
        # 框架变量（用于布局管理）
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

    def _init_modules(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            实例化各功能模块，并建立方法绑定，使主类对外暴露统一的接口。
        边界条件与限制:
            模块间通过 app 参数相互引用，初始化顺序无严格要求。
        """
        # UI 模块：负责所有界面元素的创建和布局
        self.ui = MonitorUI(self)

        # 数据处理模块：负责光强数据的数学计算和状态判定
        self.processor = DataProcessor(self)

        # 串口处理模块：负责串口连接、数据读取和指令解析
        self.serial = SerialHandler(self)

        # 绘图模块：负责波形图的绘制和更新
        self.plotter = PlotManager(self)

        # 配置管理模块：负责 JSON 配置文件的读写
        self.config = ConfigManager(self)

        # 文件对话框模块：负责文件/目录选择交互
        self.file_dialog = FileDialogManager(self)

        # 将各模块的关键方法绑定到主类，保持对外接口不变
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