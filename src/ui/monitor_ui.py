"""
UI 布局与组件创建模块（增强版）

本模块包含所有与界面显示相关的代码，新增功能包括：
- 历史回看时间轴滑块
- 光标十字线与悬浮气泡
- 更细致的状态监控面板

【类比解释】这个模块就像“汽车的中控台”——它不仅把按钮、仪表盘画出来，
还增加了“倒车影像”（滑块回看）和“倒车雷达”（气泡提示）。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# 配置全局中文字体
mpl.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
mpl.rcParams['axes.unicode_minus'] = False


class MonitorUI:
    """
    [置信度: 高]
    输入参数详解:
        app: ArduinoSerialMonitor 主应用实例
    返回值详解:
        无
    主要算法逻辑简述:
        作为 UI 管理器，负责创建所有界面元素并将控件变量挂载到 app 实例上。
        新增了滑块、十字线图层、气泡等高级交互组件。
    边界条件与限制:
        必须在主应用实例完成属性初始化后调用。
    """

    def __init__(self, app):
        self.app = app
        self._init_styles()

    def _init_styles(self):
        """初始化 ttk 高级样式（白话：让界面不那么“Windows 95 风格”）"""
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TLabelframe', borderwidth=1, relief='solid')
        style.configure('TLabelframe.Label', font=('Microsoft YaHei', 10, 'bold'),
                        foreground='#2C3E50', background='#ecf0f1')
        style.configure('TButton', font=('Microsoft YaHei', 10), padding=4)
        style.configure('Header.TLabel', font=('Microsoft YaHei', 12, 'bold'),
                        foreground='#34495E')
        style.configure('Stop.TButton', font=('Microsoft YaHei', 10, 'bold'),
                        foreground='#C0392B')

    def setup_ui(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            创建主框架并依次调用四个子面板的创建方法，完成整体布局。
        边界条件与限制:
            必须在 tkinter 根窗口创建后调用。
        """
        self.app.main_frame = ttk.Frame(self.app.root)
        self.app.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.app.left_main_frame = ttk.Frame(self.app.main_frame)
        self.app.left_main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.app.right_main_frame = ttk.Frame(self.app.main_frame, width=320)
        self.app.right_main_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        self.app.top_frame = ttk.Frame(self.app.left_main_frame)
        self.app.top_frame.pack(fill=tk.X)

        self._build_control_panel()
        self._build_log_panel()
        self._build_plot_panel()
        self._build_status_panel()
        self._build_analysis_panel()

    def _build_control_panel(self):
        """
        [置信度: 高]
        构建左上角：硬件互联与控制面板。
        新增“允许接收传感器数据”复选框和“锁定视窗”复选框。
        """
        self.app.left_frame = ttk.LabelFrame(self.app.top_frame, text="硬件互联与控制")
        self.app.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(self.app.left_frame, text="端口:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.port_var = tk.StringVar()
        self.app.port_combo = ttk.Combobox(self.app.left_frame, textvariable=self.app.port_var,
                                           width=12, state="readonly")
        self.app.port_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.app.left_frame, text="刷新", command=self.app.refresh_ports).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.app.left_frame, text="波特率:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.baud_var = tk.StringVar(value="115200")
        self.app.baud_combo = ttk.Combobox(self.app.left_frame, textvariable=self.app.baud_var,
                                           width=12, state="readonly")
        self.app.baud_combo['values'] = ('9600', '19200', '38400', '57600', '115200')
        self.app.baud_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5)

        self.app.connect_button = ttk.Button(self.app.left_frame, text="▶ 连接设备",
                                             command=self.app.toggle_connection)
        self.app.connect_button.grid(row=2, column=0, columnspan=3, padx=5, pady=8, sticky="we")

        ttk.Label(self.app.left_frame, text="滚动视窗(秒):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.window_var = tk.StringVar(value="60")
        ttk.Entry(self.app.left_frame, textvariable=self.app.window_var, width=12).grid(
            row=3, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)

        self.app.is_receiving_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.app.left_frame, text="✅ 允许接收传感器数据",
                        variable=self.app.is_receiving_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        self.app.is_frozen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.app.left_frame, text="🔒 锁定视窗(停止滚动)",
                        variable=self.app.is_frozen_var).grid(row=4, column=2, sticky=tk.W, padx=5, pady=5)

        self.app.status_var = tk.StringVar(value="状态: 离线")
        ttk.Label(self.app.left_frame, textvariable=self.app.status_var,
                  foreground="#7F8C8D").grid(row=5, column=0, columnspan=3, padx=5, pady=5)

    def _build_log_panel(self):
        """构建右上角：底层通信流水日志"""
        self.app.right_frame = ttk.LabelFrame(self.app.top_frame, text="底层通信流水")
        self.app.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.app.text_display = scrolledtext.ScrolledText(self.app.right_frame, wrap=tk.WORD, height=6)
        self.app.text_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_plot_panel(self):
        """
        [置信度: 高]
        构建左下角：高频数据观测窗，含滑块、matplotlib画布、十字线图层。
        """
        self.app.bottom_frame = ttk.LabelFrame(self.app.left_main_frame, text="高频数据观测窗")
        self.app.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 滑块区域
        self.app.slider_frame = ttk.Frame(self.app.bottom_frame)
        self.app.slider_frame.pack(fill=tk.X, side=tk.TOP, pady=(5, 0), padx=10)

        ttk.Label(self.app.slider_frame, text="⏪ 历史回看时间轴 (冻结或停止接收时可用):",
                  font=("Microsoft YaHei", 9, "bold"), foreground="#D35400").pack(side=tk.LEFT)
        self.app.time_slider = ttk.Scale(self.app.slider_frame, from_=0, to=100,
                                         orient='horizontal', state='disabled',
                                         command=self.app.on_slider_move)
        self.app.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        # Matplotlib 画布
        self.app.fig = Figure(figsize=(8, 3.5), dpi=100)
        self.app.fig.subplots_adjust(bottom=0.15, left=0.08, right=0.75, top=0.92)
        self.app.plot = self.app.fig.add_subplot(111)
        self.app.plot.set_xlabel("反应时间流逝 (秒)", fontdict={'family': 'Microsoft YaHei', 'size': 10})
        self.app.plot.set_ylabel("光强数值 (0-1023)", fontdict={'family': 'Microsoft YaHei', 'size': 10})
        self.app.plot.grid(True, linestyle=':', alpha=0.6, color='#BDC3C7')
        self.app.plot.set_facecolor('#F8F9F9')

        # 预加载图层（绘图管理器会更新它们的数据）
        self.app.line_main, = self.app.plot.plot([], [], color='#2980B9', linewidth=1.5, label='实时光强轨迹')
        self.app.line_base = self.app.plot.axhline(y=np.nan, color='#27AE60', linestyle='--', linewidth=1.5, label='环境基准')
        self.app.line_thresh = self.app.plot.axhline(y=np.nan, color='#C0392B', linestyle='-.', linewidth=1.5, label='触发阈值')
        self.app.vline_start = self.app.plot.axvline(x=np.nan, color='#F39C12', linewidth=2, label='反应起始点')
        self.app.vline_end = self.app.plot.axvline(x=np.nan, color='#8E44AD', linewidth=2, label='判定停车点')

        # 十字线与气泡
        self.app.crosshair_v = self.app.plot.axvline(x=np.nan, color='#E67E22', linestyle=':', linewidth=1.5)
        self.app.crosshair_h = self.app.plot.axhline(y=np.nan, color='#E67E22', linestyle=':', linewidth=1.5)

        self.app.tooltip = self.app.plot.annotate(
            "", xy=(0, 0), xytext=(15, 15), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="#FFFDE7", ec="#E67E22", lw=1, alpha=0.95),
            fontsize=10, fontname="Microsoft YaHei", color="#2C3E50",
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0", color="#E67E22")
        )
        self.app.tooltip.set_alpha(0)
        self.app.plot.legend(loc='upper left', bbox_to_anchor=(1.02, 1), framealpha=0.9)

        self.app.canvas = FigureCanvasTkAgg(self.app.fig, master=self.app.bottom_frame)
        self.app.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.app.canvas.mpl_connect("motion_notify_event", self.app.on_mouse_move)

    def _build_status_panel(self):
        """构建右中侧：核心逻辑侦测台"""
        self.app.reaction_display_frame = ttk.LabelFrame(self.app.right_main_frame, text="核心逻辑侦测台")
        self.app.reaction_display_frame.pack(fill=tk.X, expand=False, pady=(5, 10))

        self.app.experiment_status_var = tk.StringVar(value="状态: 等待启动...")
        ttk.Label(self.app.reaction_display_frame, textvariable=self.app.experiment_status_var,
                  font=("Microsoft YaHei", 12, "bold"), foreground='#2980B9').pack(pady=10, padx=10, anchor=tk.W)

        self.app.reaction_time_var = tk.StringVar(value="-- 秒")
        ttk.Label(self.app.reaction_display_frame, textvariable=self.app.reaction_time_var,
                  font=("Arial", 28, "bold")).pack(pady=5, padx=10)

        ttk.Button(self.app.reaction_display_frame, text="♻ 重新标定环境光 (同步开始新JSON)",
                   command=self.app.restart_measurement).pack(fill=tk.X, pady=5, padx=15)
        ttk.Button(self.app.reaction_display_frame, text="⏹ 强制结束并导出当前 JSON",
                   command=self.app.serial.stop_json_recording, style='Stop.TButton').pack(fill=tk.X, pady=5, padx=15)

    def _build_analysis_panel(self):
        """构建右下侧：光电特征追踪"""
        self.app.realtime_data_frame = ttk.LabelFrame(self.app.right_main_frame, text="光电特征追踪")
        self.app.realtime_data_frame.pack(fill=tk.X, expand=False, pady=5)

        self.app.rt_baseline_var = tk.StringVar(value="环境基准: --")
        ttk.Label(self.app.realtime_data_frame, textvariable=self.app.rt_baseline_var,
                  font=("Microsoft YaHei", 11), foreground="#27AE60").pack(anchor=tk.W, padx=15, pady=4)

        self.app.rt_current_var = tk.StringVar(value="当前光强: --")
        ttk.Label(self.app.realtime_data_frame, textvariable=self.app.rt_current_var,
                  font=("Arial", 16, "bold"), foreground="#2C3E50").pack(anchor=tk.W, padx=15, pady=8)

        self.app.rt_avg_var = tk.StringVar(value="反应期平均: --")
        ttk.Label(self.app.realtime_data_frame, textvariable=self.app.rt_avg_var,
                  font=("Microsoft YaHei", 11), foreground="#2980B9").pack(anchor=tk.W, padx=15, pady=4)

        self.app.rt_min_var = tk.StringVar(value="探测最低点: --")
        ttk.Label(self.app.realtime_data_frame, textvariable=self.app.rt_min_var,
                  font=("Microsoft YaHei", 11), foreground="#8E44AD").pack(anchor=tk.W, padx=15, pady=4)

    def on_mouse_move(self, event):
        """
        [置信度: 高]
        输入参数详解:
            event: matplotlib 鼠标事件对象
        返回值详解:
            无
        主要算法逻辑简述:
            当鼠标在图上移动时，找到最近的数据点并显示十字线和气泡。
            如果鼠标离开绘图区，隐藏十字线和气泡。
        边界条件与限制:
            需要数据队列非空，否则不显示。
        """
        if event.inaxes == self.app.plot and event.xdata and event.ydata:
            with self.app.lock:
                x_list = list(self.app.time_data)
                y_list = list(self.app.data_buffer)

            if x_list:
                idx = (np.abs(np.array(x_list) - event.xdata)).argmin()
                # 判断距离是否在合理范围内（避免显示太远的数据点）
                if abs(x_list[idx] - event.xdata) < max((x_list[-1] - x_list[0]) * 0.05, 1.0):
                    x_val = x_list[idx]
                    y_val = y_list[idx]
                    self.app.crosshair_v.set_xdata([x_val, x_val])
                    self.app.crosshair_h.set_ydata([y_val, y_val])
                    self.app.tooltip.set_text(f"T: {x_val:.2f}s\nL: {y_val}")
                    self.app.tooltip.xy = (x_val, y_val)
                    self.app.tooltip.set_alpha(1)
                else:
                    self._hide_crosshairs()
        else:
            self._hide_crosshairs()
        self.app.canvas.draw_idle()

    def _hide_crosshairs(self):
        """隐藏十字线和气泡（白话：把尺子和标签收起来）"""
        self.app.crosshair_v.set_xdata([np.nan, np.nan])
        self.app.crosshair_h.set_ydata([np.nan, np.nan])
        self.app.tooltip.set_alpha(0)

    def on_slider_move(self, val):
        """
        [置信度: 高]
        输入参数详解:
            val: 滑块当前值（字符串形式，需转换为 float）
        返回值详解:
            无
        主要算法逻辑简述:
            当用户拖动滑块时，更新绘图区的 X 轴范围以回看历史数据。
            仅在“停止接收”或“锁定视窗”状态下生效。
        边界条件与限制:
            窗口宽度可能因用户输入无效而回退到默认值60。
        """
        if not self.app.is_receiving_var.get() or self.app.is_frozen_var.get():
            try:
                window_size = float(self.app.window_var.get())
            except ValueError:
                window_size = 60
            start_x = float(val)
            self.app.plot.set_xlim(start_x, start_x + window_size)
            self.app.canvas.draw_idle()