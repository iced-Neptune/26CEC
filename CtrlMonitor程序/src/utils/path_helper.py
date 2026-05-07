"""
路径辅助模块：统一计算应用程序根目录
"""
import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    返回应用程序根目录（exe 所在目录或开发时的项目根目录）
    """
    if getattr(sys, 'frozen', False):
        # 打包后，exe 位于 dist/ArduinoMonitor/ 下
        return Path(sys.executable).parent
    else:
        # 开发环境：本文件在 src/utils/ 下，向上两级到 src/，再向上一级到项目根
        return Path(__file__).resolve().parent.parent.parent