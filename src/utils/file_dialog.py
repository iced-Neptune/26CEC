"""
文件对话框模块——负责文件/目录选择交互

【类比解释】这个模块就像“打开文件的窗口”——当你需要选择
保存位置时，它弹出系统自带的文件夹选择对话框，让你点几下鼠标就行。
"""

import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog


class FileDialogManager:
    """
    文件对话框管理器——负责所有与用户文件选择相关的交互。
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

    def ask_json_dir(self) -> None:
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            弹出文件夹选择对话框，让用户选择 JSON 原始数据的保存目录；
            如果用户取消选择，则使用当前程序目录作为默认值
        边界条件与限制:
            - 选择结果会保存到 self.app.json_dir
            - 会在日志中显示选择结果
        """
        self.app.json_dir = filedialog.askdirectory(
            title="选择存放〖单次反应原始JSON数据〗的文件夹"
        )

        if not self.app.json_dir:
            self.app.text_display.insert(
                tk.END, "⚠️ 未选择JSON保存目录，JSON数据将默认保存在当前程序目录下。\n"
            )
            self.app.json_dir = os.getcwd()
        else:
            self.app.text_display.insert(
                tk.END, f"系统已就绪，JSON原始数据将保存在: {self.app.json_dir}\n"
            )
        self.app.text_display.see(tk.END)

    def create_new_csv(self) -> None:
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            弹出“另存为”对话框，让用户选择 CSV 文件的保存位置；
            如果是新文件，自动写入表头；
            将文件路径保存到配置文件中，并自动触发 JSON 目录选择
        边界条件与限制:
            - 如果用户取消选择，self.app.csv_filepath 保持原值
        """
        filepath = filedialog.asksaveasfilename(
            title="选择新的比赛数据保存位置 (CSV表格)",
            initialfile="碘钟实验记录_新.csv",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")]
        )

        if filepath:
            self.app.csv_filepath = filepath
            if not os.path.exists(self.app.csv_filepath):
                with open(self.app.csv_filepath, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "实验时间", "环境基准光强", "开始瞬间光强", "反应中平均光强",
                        "反应中最低光强", "结束瞬间光强", "结束+0.5s光强", "结束+1.0s光强",
                        "反应耗时(秒)"
                    ])

            config = self.app.config.load_config()
            config["last_file"] = self.app.csv_filepath
            self.app.config.save_config(config)

            self.app.root.after(300, self.ask_json_dir)

    def ask_save_preference(self) -> None:
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            无
        主要算法逻辑简述:
            弹出对话框询问用户是追加到上次的 CSV 文件还是创建新文件；
            根据用户选择调用相应的方法
        边界条件与限制:
            - 如果上次的文件不存在，则禁用“追加”按钮
        """
        config = self.app.config.load_config()
        last_file = config.get("last_file", "")

        dialog = tk.Toplevel(self.app.root)
        dialog.title("实验数据存储设置 (第一步：主表格)")
        dialog.geometry("420x220")
        dialog.transient(self.app.root)
        dialog.grab_set()

        ttk.Label(
            dialog, text="请选择本次实验〖汇总表格〗的记录方式：",
            font=("SimHei", 12)
        ).pack(pady=15)

        def choose_append():
            self.app.csv_filepath = last_file
            self.app.text_display.insert(
                tk.END, f"系统已就绪，汇总数据将追加至: {os.path.basename(last_file)}\n"
            )
            dialog.destroy()
            self.app.root.after(300, self.ask_json_dir)

        def choose_new():
            self.create_new_csv()
            dialog.destroy()

        append_btn = ttk.Button(
            dialog,
            text=f"记录在上一次的表格里\n({os.path.basename(last_file) if last_file else '无记录'})",
            command=choose_append
        )
        append_btn.pack(fill=tk.X, padx=40, pady=5)

        if not last_file or not os.path.exists(last_file):
            append_btn.state(['disabled'])

        ttk.Button(
            dialog, text="记录在新的表格里", command=choose_new
        ).pack(fill=tk.X, padx=40, pady=5)

        self.app.root.wait_window(dialog)