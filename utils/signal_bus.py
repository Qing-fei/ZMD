from PyQt5.QtCore import pyqtSignal, QObject


"""
信号总线模块。

作用：
1. 定义程序中需要跨模块使用的 Qt 信号。
2. 用于将全局热键或其他事件安全地传递到主线程中处理。

说明：
- 当前主要用于热键触发，例如按 K 记录鼠标位置。
- 后续如果增加更多全局信号，也可以继续放在这里统一管理。
"""

class SignalBus(QObject):
    k_pressed = pyqtSignal()
    p_pressed = pyqtSignal()