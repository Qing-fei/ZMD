"""
程序入口文件。

作用：
1. 创建 QApplication 应用对象。
2. 创建并显示主窗口 MainWindow。
3. 启动 Qt 事件循环。

说明：
- 这个文件只负责启动程序，不写具体业务逻辑。
- 所有界面逻辑和功能实现都应放到其他模块中。
"""

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


if __name__ == "__main__":
    app = QApplication([])

    window = MainWindow()
    window.ui.show()

    app.exec_()
