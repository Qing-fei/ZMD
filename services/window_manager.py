import time
import win32gui
import win32con


class WindowManager:
    def __init__(self, logger=None):
        self.hwnd = None
        self.logger = logger

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def bind_window(self, title):
        title = title.strip() or "Endfield"
        self.hwnd = win32gui.FindWindow(None, title)

        if not self.hwnd:
            self.log(f"未找到窗口：{title}")
            return False

        rect = win32gui.GetWindowRect(self.hwnd)
        self.log(f"窗口绑定成功：{title} {rect}")
        return True

    def activate_window(self):
        if not self.hwnd:
            self.log("未绑定窗口，无法激活")
            return False

        try:
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.2)
            return True
        except Exception as e:
            self.log(f"激活窗口失败：{e}")
            return False

    def get_window_rect(self):
        if not self.hwnd:
            return None
        try:
            return win32gui.GetWindowRect(self.hwnd)
        except Exception as e:
            self.log(f"获取窗口坐标失败：{e}")
            return None

    def get_window_size(self):
        rect = self.get_window_rect()
        if not rect:
            return None
        left, top, right, bottom = rect
        return right - left, bottom - top

    def to_screen(self, rel_pos):
        rect = self.get_window_rect()
        if not rect:
            raise ValueError("窗口未绑定，无法转换坐标")

        left, top, _, _ = rect
        return left + rel_pos[0], top + rel_pos[1]

    def to_screen_ratio(self, ratio_pos):
        rect = self.get_window_rect()
        if not rect:
            raise ValueError("窗口未绑定，无法转换比例坐标")

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        rx, ry = ratio_pos
        return left + int(rx * width), top + int(ry * height)

    def rel_to_ratio(self, rel_pos):
        size = self.get_window_size()
        if not size:
            raise ValueError("窗口未绑定，无法转换比例坐标")

        width, height = size
        x, y = rel_pos
        return x / width, y / height

    def ratio_to_rel(self, ratio_pos):
        size = self.get_window_size()
        if not size:
            raise ValueError("窗口未绑定，无法转换相对坐标")

        width, height = size
        rx, ry = ratio_pos
        return int(rx * width), int(ry * height)

    def is_bound(self):
        return self.hwnd is not None