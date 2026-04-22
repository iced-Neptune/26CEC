"""
绘图管理模块——负责波形图的绘制和更新

本模块包含：
- 后台线程定期触发绘图更新
- 实际执行绘图的方法（绘制曲线、基准线、垂直线）
- 坐标轴范围管理（动态/冻结模式）

【类比解释】这个模块就像“心电图机的显示屏”——它把数据处理器算出来的
数值画成一条随时间变化的曲线，让你一眼就能看出光强是上升还是下降。
"""

"""
绘图管理模块（增强版）——负责波形图的绘制和更新

新增功能：多图层管理、滑块控制支持、十字线数据联动。
"""

import time
import numpy as np


class PlotManager:
    """
    [置信度: 高]
    输入参数详解:
        app: 主应用实例
    返回值详解:
        无
    主要算法逻辑简述:
        在后台线程中定期刷新绘图，支持动态滚动/冻结/滑块回看模式。
    """

    TRIGGER_PERCENT = 0.20
    DEFAULT_WINDOW_SIZE = 60

    def __init__(self, app):
        self.app = app

    def update_plot_loop(self):
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            每隔 60ms 检查是否需要重绘（连接状态下持续重绘）。
        边界条件与限制:
            重绘频率与系统性能相关，60ms 为经验值。
        """
        while self.app.is_connected:
            self._redraw_plot()
            time.sleep(0.06)

    def _redraw_plot(self):
        """执行一次完整的绘图刷新"""
        with self.app.lock:
            x_data = list(self.app.time_data)
            y_data = list(self.app.data_buffer)

        if not x_data:
            return

        # 更新主曲线
        self.app.line_main.set_data(x_data, y_data)

        # 更新基准线和阈值线
        if self.app.baseline_light is not None:
            self.app.line_base.set_ydata([self.app.baseline_light, self.app.baseline_light])
            thresh = self.app.baseline_light * (1 - self.TRIGGER_PERCENT)
            self.app.line_thresh.set_ydata([thresh, thresh])
        else:
            self.app.line_base.set_ydata([np.nan, np.nan])
            self.app.line_thresh.set_ydata([np.nan, np.nan])

        # 更新竖线
        if self.app.reaction_start_marker:
            self.app.vline_start.set_xdata([self.app.reaction_start_marker, self.app.reaction_start_marker])
        else:
            self.app.vline_start.set_xdata([np.nan, np.nan])

        if self.app.reaction_end_marker:
            self.app.vline_end.set_xdata([self.app.reaction_end_marker, self.app.reaction_end_marker])
        else:
            self.app.vline_end.set_xdata([np.nan, np.nan])

        # 坐标轴范围管理
        try:
            window_size = float(self.app.window_var.get())
            if window_size <= 0:
                window_size = self.DEFAULT_WINDOW_SIZE
        except ValueError:
            window_size = self.DEFAULT_WINDOW_SIZE

        latest_time = x_data[-1]
        max_start_time = max(0, latest_time - window_size)

        is_receiving = self.app.is_receiving_var.get()
        is_frozen = self.app.is_frozen_var.get()

        if is_receiving and not is_frozen:
            # 动态滚动模式
            self.app.time_slider.config(state='disabled')
            self.app.time_slider.configure(to=max_start_time)
            self.app.time_slider.set(max_start_time)

            if latest_time < window_size:
                self.app.plot.set_xlim(0, window_size)
            else:
                self.app.plot.set_xlim(max_start_time, latest_time + 2)
        else:
            # 冻结或停止接收模式：启用滑块
            self.app.time_slider.config(state='normal')
            self.app.time_slider.configure(to=max_start_time)
            slider_val = self.app.time_slider.get()
            self.app.plot.set_xlim(slider_val, slider_val + window_size)

        # Y轴自适应
        if self.app.baseline_light:
            self.app.plot.set_ylim(0, max(1100, self.app.baseline_light + 100))
        else:
            self.app.plot.set_ylim(0, 1100)

        self.app.canvas.draw_idle()