"""
文件对话框模块——负责文件/目录选择交互
"""
import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog

from src.utils.path_helper import get_app_root


class FileDialogManager:
    """文件对话框管理器——负责所有与用户文件选择相关的交互。"""

    def __init__(self, app):
        self.app = app

    def ask_json_dir(self) -> None:
        """
        弹出文件夹选择对话框，让用户选择 JSON 原始数据的保存目录；
        取消选择时默认使用 data/json_raw/ 文件夹。
        """
        initial_dir = get_app_root() / "data" / "json_raw"

        if not self.app.json_dir:
            self.app.json_dir = str(initial_dir)
            self.app.text_display.insert(
                tk.END, "⚠️ 未选择JSON保存目录，JSON数据将默认保存在 data/json_raw/ 文件夹下。\n"
            )
        else:
            self.app.text_display.insert(
                tk.END, f"系统已就绪，JSON原始数据将保存在: {self.app.json_dir}\n"
            )
        self.app.text_display.see(tk.END)

    def create_new_csv(self) -> None:
        """
        弹出“另存为”对话框，让用户选择 CSV 文件的保存位置；
        默认建议保存在 data/csv_records/ 目录。
        """
        initial_dir = get_app_root() / "data" / "csv_records"
        initial_dir.mkdir(parents=True, exist_ok=True)

        filepath = filedialog.asksaveasfilename(
            title="选择新的比赛数据保存位置 (CSV表格)",
            initialdir=str(initial_dir),
            initialfile="碘钟实验记录.csv",
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
                        "反应耗时(秒)", "vc含量","溶液温度"
                    ])

            config = self.app.config.load_config()
            config["last_file"] = self.app.csv_filepath
            self.app.config.save_config(config)

            self.app.root.after(300, self.ask_json_dir)

    def ask_save_preference(self) -> None:
        """
        弹出对话框询问用户是追加到上次的 CSV 文件还是创建新文件。
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