"""
配置文件管理模块——负责 JSON 配置文件的读写
"""
import os
import json
from pathlib import Path

from src.utils.path_helper import get_app_root


class ConfigManager:
    """配置管理器——负责读写 monitor_config.json 配置文件。"""

    def __init__(self, app):
        self.app = app
        # 配置文件统一放在应用根目录下的 config/ 中
        self.config_dir = get_app_root() / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "monitor_config.json"

    def load_config(self) -> dict:
        """
        读取配置字典，至少包含 "last_file" 键
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_file": ""}

    def save_config(self, config: dict) -> None:
        """保存配置字典（自动创建目录）"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)