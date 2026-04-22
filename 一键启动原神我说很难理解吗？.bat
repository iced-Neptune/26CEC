@echo off
chcp 65001 > nul
echo 正在启动程序，本窗口5s后关闭
start "" pythonw -m src.main
timeout /t 5 /nobreak > nul
exit