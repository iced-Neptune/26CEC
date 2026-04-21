"""
配置文件管理模块——负责 JSON 配置文件的读写

【类比解释】这个模块就像“手机的设置存储”——它帮你记住上次实验
把数据存在哪个文件里，下次打开程序时自动帮你填好。
"""

import os
import json

CONFIG_FILE = "monitor_config.json"


class ConfigManager:
    """
    配置管理器——负责读写 monitor_config.json 配置文件。
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

    def load_config(self) -> dict:
        """
        [置信度: 高]
        输入参数详解:
            无
        返回值详解:
            配置字典，至少包含 "last_file" 键
        主要算法逻辑简述:
            如果配置文件存在，尝试读取 JSON 内容；
            任何错误（文件不存在、格式错误等）都返回默认配置
        边界条件与限制:
            - 默认配置为 {"last_file": ""}
        """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_file": ""}

    def save_config(self, config: dict) -> None:
        """
        [置信度: 高]
        输入参数详解:
            config: 要保存的配置字典
        返回值详解:
            无
        主要算法逻辑简述:
            将配置字典以 JSON 格式写入配置文件
        边界条件与限制:
            - 使用 ensure_ascii=False 支持中文
            - 缩进为 4 个空格，便于人工阅读
        """
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)