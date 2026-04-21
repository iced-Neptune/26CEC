"""
绘图管理模块——负责波形图的绘制和更新

本模块包含：
- 后台线程定期触发绘图更新
- 实际执行绘图的方法（绘制曲线、基准线、垂直线）
- 坐标轴范围管理（动态/冻结模式）

【类比解释】这个模块就像“心电图机的显示屏”——它把数据处理器算出来的
数值画成一条随时间变化的曲线，让你一眼就能看出光强是上升还是下降。
"""

import time


class PlotManager:
    """
    绘图管理器——负责所有与 matplotlib 绘图相关的逻辑。
    """

    # 触发百分比常量（与 DataProcessor 保持一致）
    TRIGGER_PERCENT = 0.20

    def __init__(self, app):
        """
        [置信度: 高]
        输入参数详解:
            app: ArduinoSerialMonitor 主应用实例
        返回值详解:
            无
        """
        self.app = app

    def update_plot_loop(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            在 while 循环中每隔 0.1 秒检查是否需要刷新波形图
        边界条件与限制:
            - 循环条件为 self.app.is_connected
            - 仅在 show_plot_var 为 True 时执行重绘
        """
        while self.app.is_connected:
            if self.app.show_plot_var.get():
                self._redraw_plot()
            time.sleep(0.1)

    def _redraw_plot(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            获取当前冻结状态和坐标轴范围，从数据缓存中取出数据，
            执行绘图，应用坐标轴范围，最后刷新画布
        边界条件与限制:
            - 使用线程锁保护对数据缓存的访问
            - 如果数据缓存为空，跳过本次重绘
        """
        is_frozen = self.app.is_frozen_var.get()
        current_xlim = None
        current_ylim = None

        if is_frozen:
            current_xlim = self.app.plot.get_xlim()
            current_ylim = self.app.plot.get_ylim()

        with self.app.lock:
            x_data = list(self.app.time_data)
            y_data = list(self.app.data_buffer)

        if x_data:
            self._draw_plot_elements(x_data, y_data)
            self._apply_axis_limits(x_data, is_frozen, current_xlim, current_ylim)
            self.app.canvas.draw_idle()

    def _draw_plot_elements(self, x_data, y_data):
        """
        [置信度: 高]
        输入参数详解:
            x_data: 时间数据列表
            y_data: 光强数据列表
        返回值详解:
            无
        主要算法逻辑简述:
            - 清空画布
            - 绘制实时光强曲线（蓝色实线）
            - 如果已标定，绘制环境基准线（绿色虚线）和触发阈值线（红色点划线）
            - 如果已记录，绘制反应开始线（橙色竖线）和反应结束线（紫色竖线）
            - 添加图例
        边界条件与限制:
            - 触发阈值线仅在 baseline_light 存在时绘制
        """
        self.app.plot.clear()
        self.app.plot.plot(x_data, y_data, 'b-', label='实时光强')
        self.app.plot.set_xlabel("时间 (秒)")
        self.app.plot.set_ylabel("光敏传感器读数")
        self.app.plot.grid(True, linestyle=':', alpha=0.6)

        if self.app.baseline_light is not None:
            self.app.plot.axhline(
                y=self.app.baseline_light, color='green', linestyle='--',
                alpha=0.8, label=f'环境基准 ({self.app.baseline_light})'
            )
            threshold = self.app.baseline_light * (1 - self.TRIGGER_PERCENT)
            self.app.plot.axhline(
                y=threshold, color='red', linestyle='-.', alpha=0.8,
                label=f'触发线 (-{int(self.TRIGGER_PERCENT * 100)}%)'
            )

        if self.app.reaction_start_marker:
            self.app.plot.axvline(
                x=self.app.reaction_start_marker, color='orange',
                linewidth=2, label='反应开始'
            )

        if self.app.reaction_end_marker:
            self.app.plot.axvline(
                x=self.app.reaction_end_marker, color='purple',
                linewidth=2, label='确认结束'
            )

        self.app.plot.legend(loc='upper right')

    def _apply_axis_limits(self, x_data, is_frozen, current_xlim, current_ylim):
        """
        [置信度: 高]
        输入参数详解:
            x_data: 时间数据列表
            is_frozen: 是否处于冻结模式
            current_xlim: 冻结前的 X 轴范围（仅在 is_frozen=True 时有效）
            current_ylim: 冻结前的 Y 轴范围（仅在 is_frozen=True 时有效）
        返回值详解:
            无
        主要算法逻辑简述:
            - 冻结模式：恢复之前保存的坐标轴范围
            - 动态模式：根据最新数据时间和用户设置的窗口宽度自动调整 X 轴；
              Y 轴根据基准光强自动适应
        边界条件与限制:
            - 窗口宽度读取失败时默认使用 60 秒
            - 无基准光强时 Y 轴固定为 [0, 1100]
        """
        if is_frozen:
            self.app.plot.set_xlim(current_xlim)
            self.app.plot.set_ylim(current_ylim)
        else:
            try:
                window_size = float(self.app.window_var.get())
                if window_size <= 0:
                    window_size = 60
            except ValueError:
                window_size = 60

            latest_time = x_data[-1]
            if latest_time < window_size:
                self.app.plot.set_xlim(0, window_size)
            else:
                self.app.plot.set_xlim(latest_time - window_size, latest_time + 2)

            if self.app.baseline_light:
                self.app.plot.set_ylim(0, max(1100, self.app.baseline_light + 100))
            else:
                self.app.plot.set_ylim(0, 1100)