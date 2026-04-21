"""
UI 布局与组件创建模块

本模块包含所有与界面显示相关的代码，包括：
- 控制面板（端口选择、连接按钮等）
- 日志面板（串口原始数据显示）
- 波形图面板（matplotlib 画布）
- 右侧状态监控面板（实验状态、实时光强追踪）

【类比解释】这个模块就像“汽车的中控台”——它只负责把按钮、仪表盘、屏幕画出来，
至于按了按钮之后车怎么跑，那是“发动机”（core 模块）的事情。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class MonitorUI:
    """
    UI 布局管理器——负责创建和排列所有界面元素。

    所有控件的创建都在此类的方法中完成，控件变量会赋值到主应用实例（app）上。
    """

    def __init__(self, app):
        """
        [置信度: 高]
        输入参数详解:
            app: ArduinoSerialMonitor 主应用实例，包含所有共享数据属性
        返回值详解:
            无
        主要算法逻辑简述:
            将 app 实例保存为 self.app，后续所有方法通过 self.app 访问共享数据
        边界条件与限制:
            必须在主应用实例完成属性初始化后再创建本模块实例
        """
        self.app = app

    def setup_ui(self):
        """
        [置信度: 高]
        输入参数详解:
            无（通过 self.app 访问主应用实例）
        返回值详解:
            无
        主要算法逻辑简述:
            创建主框架，依次调用四个子面板的创建方法，完成整体界面布局
        边界条件与限制:
            必须在 tkinter 根窗口创建后调用
        """
        self.app.main_frame = ttk.Frame(self.app.root)
        self.app.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧主区域（包含控制面板、日志、波形图）
        self.app.left_main_frame = ttk.Frame(self.app.main_frame)
        self.app.left_main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧主区域（状态监控面板）
        self.app.right_main_frame = ttk.Frame(self.app.main_frame, width=350)
        self.app.right_main_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # 顶部区域（控制面板 + 日志面板）
        self.app.top_frame = ttk.Frame(self.app.left_main_frame)
        self.app.top_frame.pack(fill=tk.BOTH, expand=True)

        self._create_control_panel()
        self._create_log_panel()
        self._create_plot_panel()
        self._create_right_panels()

    def _create_control_panel(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            创建左侧控制面板，包含端口选择、波特率选择、连接按钮、
            X轴宽度设置、显示波形/冻结图像复选框、状态显示标签。
        边界条件与限制:
            依赖 self.app 上的 port_var、baud_var 等变量尚未被赋值
        """
        self.app.left_frame = ttk.LabelFrame(self.app.top_frame, text="控制面板")
        self.app.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # 端口选择行
        ttk.Label(self.app.left_frame, text="端口:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.app.port_var = tk.StringVar()
        self.app.port_combo = ttk.Combobox(
            self.app.left_frame, textvariable=self.app.port_var,
            width=12, state="readonly"
        )
        self.app.port_combo.grid(row=0, column=1, padx=5, pady=5)

        self.app.refresh_button = ttk.Button(
            self.app.left_frame, text="刷新",
            command=self.app.refresh_ports
        )
        self.app.refresh_button.grid(row=0, column=2, padx=5, pady=5)

        # 波特率选择行
        ttk.Label(self.app.left_frame, text="波特率:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.app.baud_var = tk.StringVar(value="115200")
        self.app.baud_combo = ttk.Combobox(
            self.app.left_frame, textvariable=self.app.baud_var,
            width=12, state="readonly"
        )
        self.app.baud_combo['values'] = ('9600', '19200', '38400', '57600', '115200')
        self.app.baud_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5)

        # 连接/断开按钮
        self.app.connect_button = ttk.Button(
            self.app.left_frame, text="连接",
            command=self.app.toggle_connection
        )
        self.app.connect_button.grid(row=2, column=0, columnspan=3, padx=5, pady=5)

        # X轴宽度设置
        ttk.Label(self.app.left_frame, text="X轴宽度(秒):").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.app.window_var = tk.StringVar(value="60")
        self.app.window_entry = ttk.Entry(
            self.app.left_frame, textvariable=self.app.window_var, width=12
        )
        self.app.window_entry.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # 复选框行
        self.app.show_plot_var = tk.BooleanVar(value=True)
        self.app.show_plot_check = ttk.Checkbutton(
            self.app.left_frame, text="显示波形", variable=self.app.show_plot_var
        )
        self.app.show_plot_check.grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)

        self.app.is_frozen_var = tk.BooleanVar(value=False)
        self.app.frozen_check = ttk.Checkbutton(
            self.app.left_frame, text="冻结图像", variable=self.app.is_frozen_var
        )
        self.app.frozen_check.grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # 状态显示
        self.app.status_var = tk.StringVar(value="未连接")
        ttk.Label(self.app.left_frame, textvariable=self.app.status_var).grid(
            row=5, column=0, columnspan=3, padx=5, pady=5
        )

    def _create_log_panel(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            创建右侧日志面板，使用 ScrolledText 显示串口原始数据日志
        边界条件与限制:
            文本区域需要通过 self.app.text_display 供其他模块写入
        """
        self.app.right_frame = ttk.LabelFrame(self.app.top_frame, text="串口数据日志")
        self.app.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.app.text_display = scrolledtext.ScrolledText(
            self.app.right_frame, wrap=tk.WORD, width=40, height=8
        )
        self.app.text_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_plot_panel(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            创建底部波形图面板，包含 matplotlib Figure 画布和光标位置显示标签
        边界条件与限制:
            需要 matplotlib 已正确安装；画布创建后需绑定鼠标移动事件
        """
        self.app.bottom_frame = ttk.LabelFrame(self.app.left_main_frame, text="实时光强波形图")
        self.app.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 光标位置信息显示
        self.app.hover_info_var = tk.StringVar(value="光标位置: 移入波形图查看")
        ttk.Label(
            self.app.bottom_frame, textvariable=self.app.hover_info_var,
            font=("SimHei", 11), foreground="#d9534f"
        ).pack(anchor=tk.E, padx=10, pady=2)

        # matplotlib 画布
        self.app.fig = Figure(figsize=(5, 4), dpi=100)
        self.app.plot = self.app.fig.add_subplot(111)
        self.app.canvas = FigureCanvasTkAgg(self.app.fig, master=self.app.bottom_frame)
        self.app.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.app.canvas.mpl_connect("motion_notify_event", self.app.on_mouse_move)

    def _create_right_panels(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            创建最右侧的两个面板：实验状态监控面板和实时光强追踪面板
        边界条件与限制:
            这些面板中的变量会在数据处理过程中被更新
        """
        # 实验状态监控面板
        self.app.reaction_display_frame = ttk.LabelFrame(
            self.app.right_main_frame, text="实验状态监控"
        )
        self.app.reaction_display_frame.pack(fill=tk.X, expand=False, pady=(5, 10))

        self.app.experiment_status_var = tk.StringVar(value="等待启动...")
        ttk.Label(
            self.app.reaction_display_frame, textvariable=self.app.experiment_status_var,
            font=("SimHei", 12)
        ).pack(pady=10, padx=10, anchor=tk.W)

        self.app.reaction_time_var = tk.StringVar(value="-- 秒")
        ttk.Label(
            self.app.reaction_display_frame, textvariable=self.app.reaction_time_var,
            font=("SimHei", 24, "bold")
        ).pack(pady=5, padx=10)

        ttk.Button(
            self.app.reaction_display_frame, text="重新开始测量(标定环境光)",
            command=self.app.restart_measurement
        ).pack(pady=(10, 10), padx=10)

        # 实时光强追踪面板
        self.app.realtime_data_frame = ttk.LabelFrame(
            self.app.right_main_frame, text="实时光强追踪"
        )
        self.app.realtime_data_frame.pack(fill=tk.X, expand=False, pady=5)

        self.app.rt_baseline_var = tk.StringVar(value="环境基准: --")
        ttk.Label(
            self.app.realtime_data_frame, textvariable=self.app.rt_baseline_var,
            font=("SimHei", 12), foreground="green"
        ).pack(anchor=tk.W, padx=15, pady=2)

        self.app.rt_current_var = tk.StringVar(value="当前光强: --")
        ttk.Label(
            self.app.realtime_data_frame, textvariable=self.app.rt_current_var,
            font=("SimHei", 14, "bold")
        ).pack(anchor=tk.W, padx=15, pady=5)

        self.app.rt_avg_var = tk.StringVar(value="反应平均: --")
        ttk.Label(
            self.app.realtime_data_frame, textvariable=self.app.rt_avg_var,
            font=("SimHei", 12), foreground="blue"
        ).pack(anchor=tk.W, padx=15, pady=2)

        self.app.rt_min_var = tk.StringVar(value="反应最低: --")
        ttk.Label(
            self.app.realtime_data_frame, textvariable=self.app.rt_min_var,
            font=("SimHei", 12), foreground="purple"
        ).pack(anchor=tk.W, padx=15, pady=2)

    def on_mouse_move(self, event):
        """
        [置信度: 高]
        输入参数详解:
            event: matplotlib 的鼠标事件对象，包含 xdata 和 ydata 属性
        返回值详解:
            无
        主要算法逻辑简述:
            当鼠标在波形图上移动时，找到最接近光标位置的数据点，
            并在界面上显示该点的时间和光强值。
        边界条件与限制:
            - 仅在鼠标位于坐标轴内（event.inaxes == self.app.plot）时处理
            - 如果数据队列为空，则显示默认提示文字
        """
        if event.inaxes == self.app.plot and event.xdata and event.ydata:
            with self.app.lock:
                x_list = list(self.app.time_data)
                y_list = list(self.app.data_buffer)
                if x_list:
                    import numpy as np
                    idx = (np.abs(np.array(x_list) - event.xdata)).argmin()
                    if abs(x_list[idx] - event.xdata) < 2:
                        self.app.hover_info_var.set(
                            f" 光标位置 >> 时间: {x_list[idx]:.2f} 秒 | "
                            f"传感器光强: {y_list[idx]}"
                        )
                    else:
                        self.app.hover_info_var.set("光标位置: 移入波形图查看")
                else:
                    self.app.hover_info_var.set("光标位置: 移入波形图查看")
        else:
            self.app.hover_info_var.set("光标位置: 移入波形图查看")