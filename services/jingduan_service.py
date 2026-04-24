
"""
自动精锻业务服务。

作用：
1. 管理自动精锻完整流程。
2. 优先通过图像识别查找“装备”和“精锻键”。
3. 识别失败时可回退到手动定位坐标。
4. 调用 ClickService 执行点击和等待操作。

说明：
- 这个模块只负责“自动精锻”业务。
- 不负责界面按钮绑定，也不直接处理 UI 控件。
"""


class JingduanService:
    def __init__(self, window_manager, click_service, image_matcher, logger=None):
        self.window_manager = window_manager
        self.click_service = click_service
        self.image_matcher = image_matcher
        self.logger = logger

        self.equipment_template_yellow = "assets/templates/jingduan/equipment_yellow.png"
        self.equipment_template_white = "assets/templates/jingduan/equipment_white.png"
        self.forge_button_template = "assets/templates/jingduan/forge_button.png"

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    # ===================== 装备识别 =====================
    def find_equipment(self, manual_pos=None):
        rect = self.get_equipment_search_rect()

        for _ in range(2):
            result = self.image_matcher.find_in_window(
                rect,
                self.equipment_template_yellow,
                threshold=0.7
            )
            if result:
                self.log(f"识别到【较好适配(黄)】，置信度：{result['confidence']:.2f}")
                return result["screen_center"]

            if not self.click_service.safe_sleep(0.15):
                return None

        for _ in range(2):
            result = self.image_matcher.find_in_window(
                rect,
                self.equipment_template_white,
                threshold=0.7
            )
            if result:
                self.log(f"识别到【标准适配(白)】，置信度：{result['confidence']:.2f}")
                return result["screen_center"]

            if not self.click_service.safe_sleep(0.15):
                return None

        if manual_pos is not None:
            self.log("装备识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log("装备识别失败，且没有手动定位兜底")
        return None

    # ===================== 精锻按钮识别 =====================
    def find_forge_button(self, manual_pos=None):
        rect = self.get_forge_button_search_rect()

        for _ in range(3):
            result = self.image_matcher.find_in_window(
                rect,
                self.forge_button_template,
                threshold=0.7
            )
            if result:
                self.log(f"识别到精锻键，置信度：{result['confidence']:.2f}")
                return result["screen_center"]

            if not self.click_service.safe_sleep(0.15):
                return None

        if manual_pos is not None:
            self.log("精锻键识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log("精锻键识别失败，且没有手动定位兜底")
        return None

    # ===================== 主流程 =====================
    def run(self, count, manual_equipment=None, manual_forge_button=None):
        if not self.window_manager.is_bound():
            self.log("未绑定窗口")
            return

        if count <= 0:
            self.log("精锻次数不能小于1")
            return

        self.click_service.start()

        if not self.window_manager.activate_window():
            self.log("激活目标窗口失败")
            self.click_service.stop()
            return

        for i in range(count):
            if not self.click_service.is_running():
                self.log("精锻流程已中止")
                self.click_service.stop()
                return

            self.log(f"开始第 {i + 1} 次精锻")

            # 1. 先找装备
            equipment_pos = self.find_equipment(manual_equipment)
            if equipment_pos is None:
                self.click_service.stop()
                self.log("找不到装备，流程终止")
                return

            # 2. 先点装备，让“开始精锻键”出现
            self.click_service.click_screen(equipment_pos)
            if not self.click_service.safe_sleep(0.25):
                self.log("精锻流程已中止")
                self.click_service.stop()
                return

            # 3. 再找精锻键
            forge_pos = self.find_forge_button(manual_forge_button)
            if forge_pos is None:
                self.click_service.stop()
                self.log("找不到精锻键，流程终止")
                return

            # 4. 点击精锻
            self.click_service.click_screen(forge_pos)
            if not self.click_service.safe_sleep(0.15):
                self.log("精锻流程已中止")
                self.click_service.stop()
                return

            # 5. 再点一次取消后摇
            self.click_service.click_screen(forge_pos)
            if not self.click_service.safe_sleep(0.25):
                self.log("精锻流程已中止")
                self.click_service.stop()
                return

            self.log(f"第 {i + 1} 次精锻完成")

        self.click_service.stop()
        self.log("全部精锻完成")

    #精锻识别区

    def get_equipment_search_rect(self):
        rect = self.window_manager.get_window_rect()
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # 左侧约 3/8 区域，覆盖整个高度
        return (
            left,
            top,
            left + int(width * 0.375),
            bottom,
        )

    def get_forge_button_search_rect(self):
        rect = self.window_manager.get_window_rect()
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # 右下角区域，先给大一点，后续再缩
        return (
            left + int(width * 0.60),
            top + int(height * 0.60),
            right,
            bottom,
        )

    def _manual_pos_to_screen(self, manual_pos):
        if manual_pos is None:
            return None

        if isinstance(manual_pos, dict):
            if manual_pos.get("ratio") is not None:
                return self.window_manager.to_screen_ratio(manual_pos["ratio"])
            if manual_pos.get("rel") is not None:
                return self.window_manager.to_screen(manual_pos["rel"])
            return None

        return self.window_manager.to_screen(manual_pos)