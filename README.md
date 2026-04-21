# 26CEC 碘钟反应光敏监测系统

> 一个用于采集 Arduino 光敏传感器数据、实时监测化学反应进程的桌面工具。
> 传承于22届太阳学长（beautiful forever）让我们在整个项目最开始对崇高的太阳kami展示敬意好吗（bushi

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)


##  项目目的

本软件是为**碘钟实验**（一种经典的化学振荡反应）设计的配套数据采集工具。实验中，溶液颜色会随时间发生变化，光敏传感器能够捕捉这种变化并将其转化为电信号。本软件通过串口连接 Arduino，实时读取光强数据，并完成以下任务：

1. **自动标定环境光强**：在反应开始前，自动采集 20 个数据点计算基准值。
2. **精准计时**：当光强骤降超过 20% 时自动触发计时，记录反应持续时间。
3. **数据可视化**：实时绘制光强-时间曲线，支持冻结画面以便截图。
4. **数据归档**：自动将汇总数据追加至 CSV 表格，同时保存每一次反应的原始数据为 JSON 文件。

##  目标人群

- 非计算机专业的工科本科生（化学、生物、物理等实验课程）
- 需要快速上手数据采集的科研新人
- 对 Python 和 Arduino 有兴趣的入门学习者

**不需要任何编程基础**，只要会用鼠标和键盘，按照下面的指南操作即可。

##  如何让代码跑起来（零基础~~草履虫级~~指南）

### 第一步：安装 Python 3.12

1. 访问 [Python 官网](https://www.python.org/downloads/)。
2. 下载 **Python 3.12** 版本的安装包。
3. **重要**：安装时务必勾选 **“Add Python to PATH”**（把 Python 加到系统路径），否则后续命令会报错。
4. 安装完成后，按 `Win + R`，输入 `cmd`，在弹出的黑色窗口中输入：`python --version`，如果显示 `Python 3.12.x`，说明安装成功。

### 第二步：下载本项目代码

```bash
git clone https://github.com/your-team/iodine-clock-monitor.git
cd iodine-clock-monitor
```
如果没有安装 Git，也可以直接点击 GitHub 页面上的 “Code → Download ZIP”，解压到任意文件夹。
_来都来了star一下谢谢啦_

### 第三步：安装必需的第三方库
在项目根目录下，打开命令行窗口，输入：
```bash
pip install pyserial numpy matplotlib
```
这三样东西分别是：

- pyserial：让 Python 能和 Arduino 串口“对话”。

- numpy：做快速数值计算（比如找最接近的数据点）。

- matplotlib：画波形图。

### 第四步：运行程序
在命令行中输入以下命令（确保当前路径在项目根目录）：
```bash
python -m src.main
```
或者直接双击 src/main.py 文件（如果系统关联了 Python）。

### 第五步：连接 Arduino
1. 用 USB 线将 Arduino 连接到电脑。

2. 在软件左上角的“端口”下拉框中选择对应的串口（通常是 COM3、COM4 或 /dev/ttyUSB0）。

3. 波特率保持默认的 115200。

4. 点击 “连接” 按钮。

连接成功后，状态栏会显示“已连接”，波形图区域会开始显示实时数据。

### 一个具体的命令行示例
假设你的项目放在 D:\MyProjects\iodine-clock-monitor，操作流程如下：
```text
D:
cd D:\MyProjects\iodine-clock-monitor
python -m src.main
```
程序启动后，会弹出一个图形界面窗口，按上述第五步操作即可开始采集数据。

## 文件结构说明书
```text
project_root/
│
├── src/                              # 所有源代码都在这里
│   ├── main.py                       # 入口文件，从这里启动程序
│   │
│   ├── ui/                           # 界面模块（管“画什么”）
│   │   └── monitor_ui.py             # 窗口、按钮、波形图的所有布局代码
│   │
│   ├── core/                         # 核心模块（管“算什么”）
│   │   ├── data_processor.py         # 光强数值的计算和状态判断
│   │   ├── serial_handler.py         # 串口通信、数据读写、文件保存
│   │   └── plot_manager.py           # 波形图的绘制和刷新
│   │
│   ├── utils/                        # 工具模块（管“辅助功能”）
│   │   ├── config_manager.py         # 读取/保存配置文件
│   │   └── file_dialog.py            # 弹窗让用户选择文件保存位置
│   │
│   └── __init__.py                   # 包标识文件（不用管它）
│
├── data/                             # 实验数据默认保存位置
│   ├── csv_records/                  # CSV 汇总表格（每次实验一行）
│   └── json_raw/                     # JSON 原始数据（每次实验一个文件）
│
├── monitor_config.json               # 软件配置文件（保存软件设置）
├── README.md                         # 你正在读的这份文档
├── requirements.txt                  # 依赖库清单
└── .gitignore                        # Git 忽略文件配置
```

新人看代码的建议顺序：
1. 先看 src/main.py，了解程序是怎么“组装”起来的。
2. 然后看 src/ui/monitor_ui.py，看看界面是怎么画出来的。
3. 再看 src/core/data_processor.py，理解光强数据是怎么被处理的。
4. 其他文件按需查阅。

## 核心函数速查表
| 函数名                    | 所在文件          | 类比解释           | 主要作用                                                 |
| ------------------------- | ----------------- | ------------------ | -------------------------------------------------------- |
| `parse_serial_line()`     | data_processor.py | 像一个“翻译官”     | 把 Arduino 发来的文字指令翻译成程序能理解的动作          |
| `process_data_point()`    | data_processor.py | 像一个“计算器”     | 你给它一个光强数字，它帮你算出当前是标定阶段还是反应阶段 |
| `_read_serial_loop()`     | serial_handler.py | 像一个“收件箱”     | 不断检查串口有没有新数据，有就拿进来                     |
| `extract_and_save_data()` | serial_handler.py | 像一个“实验记录员” | 把这次反应的关键数据（基准光强、反应时间等）记到总表格里 |
| `save_json_raw_data()`    | serial_handler.py | 像一个“录像机”     | 把反应过程中的每一个数据点都存下来，方便以后回看         |
| `update_plot_loop()`      | plot_manager.py   | 像一个“心电图机”   | 每隔 0.1 秒刷新一次屏幕上的波形图                        |
| `_draw_plot_elements()`   | plot_manager.py   | 像一个“画师”       | 实际画出蓝色的曲线、绿色的基准线、红色的触发线           |
| `refresh_ports()`         | serial_handler.py | 像一个“设备扫描器” | 点“刷新”按钮时，帮你找电脑上插了哪些 Arduino             |
| `toggle_connection()`     | serial_handler.py | 像一个“电源开关”   | 点击“连接/断开”按钮时，接通或切断与 Arduino 的通信       |
| `on_mouse_move()`         | monitor_ui.py     | 像一个“放大镜”     | 鼠标在波形图上移动时，显示该点的时间和光强值             |

## 常见问题 FAQ
### Q1：双击 main.py 闪退，什么都看不到？
原因：Python 环境没有正确配置，或者缺少依赖库。

解决方法：

1. 按 Win + R，输入 cmd，打开命令行。

2. 用 cd 命令进入项目文件夹。

3. 手动执行 python -m src.main，这样能看到具体的错误提示。

4. 根据提示安装缺失的库（通常是 pip install pyserial numpy matplotlib）。

### Q2：连接 Arduino 时报“无法打开端口”或“拒绝访问”？
原因：端口被其他软件占用（比如 Arduino IDE 的串口监视器没关）。

解决方法：

1. 关闭所有可能占用串口的软件（Arduino IDE、Putty 等）。

2. 拔掉 Arduino 的 USB 线，重新插上。

3. 点击软件上的“刷新”按钮，重新选择端口。

4. 再次点击“连接”。

### Q3：波形图不更新，但日志区域有数据在滚动？
原因：“显示波形”复选框可能被误点了。

解决方法：检查控制面板上的 “显示波形” 是否处于勾选状态。如果没勾，波形图不会刷新（这是为了省电/省资源的设计）。

### Q4：CSV 文件打开后中文乱码？
原因：Excel 默认用 ANSI 编码打开 UTF-8 文件。

解决方法：

1. 打开 Excel，点击“数据” → “从文本/CSV”。

2. 选择 CSV 文件，在导入向导中将“文件原始格式”选为 “65001: Unicode (UTF-8)”。

3. 或者直接用 记事本 打开 CSV 文件，中文显示正常。

### Q5：程序提示“No module named 'serial'”？
原因：pyserial 没有安装。

解决方法：在命令行执行 pip install pyserial。

### Q6：想修改触发反应的阈值（比如从 20% 改成 15%）？
解决方法：打开 src/core/data_processor.py，找到第 14 行左右的：
```python
TRIGGER_PERCENT = 0.20
```
把 0.20 改成你想要的数值（例如 0.15 代表 15%），保存后重新运行程序即可。

## 最后更新：2026 年 4 月 22 日 01：31