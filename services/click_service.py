import time
import pyautogui



"""
鼠标操作服务。

作用：
1. 执行点击、拖动等鼠标操作。
2. 提供可中断的等待函数 safe_sleep。
3. 管理运行状态 running 和停止请求 stop_requested。

说明：
- 这个模块只负责“执行动作”，不负责决定“什么时候执行什么动作”。
- 业务流程应由其他 service 调用本类完成具体点击。
"""
class ClickService:
    def __init__(self, window_manager, logger=None):
        self.window_manager = window_manager
        self.logger = logger
        self.running = False
        self.stop_requested = False

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def start(self):
        self.running = True
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True
        self.running = False

    def is_running(self):
        return self.running and not self.stop_requested

    def safe_sleep(self, seconds):
        interval = 0.05
        elapsed = 0

        while elapsed < seconds:
            if self.stop_requested or not self.running:
                return False
            time.sleep(interval)
            elapsed += interval

        return True

    def click_rel(self, rel_pos):
        x, y = self.window_manager.to_screen(rel_pos)
        pyautogui.moveTo(x, y)
        pyautogui.click()

    def click_screen(self, screen_pos):
        x, y = screen_pos
        pyautogui.moveTo(x, y)
        pyautogui.click()

    def drag_rel(self, start_rel, end_rel, duration=0.2):
        start_x, start_y = self.window_manager.to_screen(start_rel)
        end_x, end_y = self.window_manager.to_screen(end_rel)

        pyautogui.moveTo(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=duration, button="left")