"""
仓库搬运业务服务（视觉版）。

作用：
1. 优先通过模板匹配识别当前仓库、仓库切换、选择仓库、确认、已连接、背包空格。
2. 保留手动坐标作为兜底，避免模板还没截全时流程完全不可用。
3. 根据当前显示仓库图标自动判断方向，并可回传给 UI。
4. 等待“已连接”状态，而不是纯固定延时。

模板命名约定：
- current_icon_wuling.png / current_icon_gudi.png   当前仓库显示图标（不可点击）
- sort_button.png                                   仓库界面右下整理图标（定位锚点）
- switch_button.png                                 仓库切换按钮
- select_wuling.png / select_gudi.png               切换弹窗里的可点击仓库选项
- confirm_button.png                                确认按钮
- connected_state.png                               “已连接”状态
- backpack_empty_slot.png                           背包空格
"""

from pathlib import Path
import time
import pyautogui


class CangkuService:
    def __init__(self, window_manager, click_service, image_matcher=None, logger=None):
        self.window_manager = window_manager
        self.click_service = click_service
        self.image_matcher = image_matcher
        self.logger = logger
        self.required_keys = ["物品"]

        base_dir = Path("assets/templates/cangku")
        self.templates = {
            "current_icon_wuling": str(base_dir / "current_icon_wuling.png"),
            "current_icon_gudi": str(base_dir / "current_icon_gudi.png"),
            "sort_button": str(base_dir / "sort_button.png"),
            "switch_button": str(base_dir / "switch_button.png"),
            "select_wuling": str(base_dir / "select_wuling.png"),
            "select_gudi": str(base_dir / "select_gudi.png"),
            "confirm_button": str(base_dir / "confirm_button.png"),
            "connected_state": str(base_dir / "connected_state.png"),
            "backpack_empty_slot": str(base_dir / "backpack_empty_slot.png"),
        }

        self.thresholds = {
            "current_icon": 0.75,
            "sort_button": 0.75,
            "switch_button": 0.72,
            "select_button": 0.72,
            "confirm_button": 0.72,
            "connected_state": 0.72,
            "backpack_empty_slot": 0.70,
        }

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def _manual_pos_to_screen(self, manual_pos):
        if manual_pos is None:
            return None

        if isinstance(manual_pos, dict):
            if manual_pos.get("ratio") is not None:
                return self.window_manager.to_screen_ratio(manual_pos["ratio"])
            if manual_pos.get("rel") is not None:
                return self.window_manager.to_screen(manual_pos["rel"])
            return None

        # 兼容旧格式：(x, y)
        return self._manual_pos_to_screen(manual_pos)

    def check_cangku_ready(self, pos_dict):
        if not self.window_manager.is_bound():
            self.log("未绑定窗口")
            return False

        for key in self.required_keys:
            if pos_dict.get(key) is None:
                self.log(f"{key} 未定位")
                return False

        return True

    def _visual_enabled(self):
        return self.image_matcher is not None

    def _find_template(self, template_key, threshold=None, rect=None, retries=2, sleep_seconds=0.15):
        if not self._visual_enabled():
            return None

        window_rect = rect or self.window_manager.get_window_rect()
        if not window_rect:
            return None

        if threshold is None:
            threshold = self.thresholds.get(template_key, 0.72)

        template_path = self.templates.get(template_key)
        if not template_path:
            return None

        for _ in range(max(retries, 1)):
            result = self.image_matcher.find_in_window(window_rect, template_path, threshold=threshold)
            if result:
                return result
            if self.click_service.is_running():
                if not self.click_service.safe_sleep(sleep_seconds):
                    return None
            else:
                time.sleep(sleep_seconds)

        return None

    def detect_current_warehouse(self):
        result = self._find_template(
            "current_icon_wuling",
            threshold=self.thresholds["current_icon"],
            retries=2,
        )
        if result:
            return {
                "warehouse": "武陵",
                "icon_result": result,
            }

        result = self._find_template(
            "current_icon_gudi",
            threshold=self.thresholds["current_icon"],
            retries=2,
        )
        if result:
            return {
                "warehouse": "谷地",
                "icon_result": result,
            }

        return None

    def detect_panel_anchors(self):
        current = self.detect_current_warehouse()
        if current is None:
            self.log("未识别到当前仓库图标")
            return None

        sort_result = self._find_template(
            "sort_button",
            threshold=self.thresholds["sort_button"],
            retries=2,
        )
        if sort_result is None:
            self.log("未识别到整理图标")
            return None

        current["sort_result"] = sort_result
        return current

    def infer_direction_from_current(self, current_warehouse):
        if current_warehouse == "武陵":
            return "武陵→谷地"
        if current_warehouse == "谷地":
            return "谷地→武陵"
        return None

    def prepare_visual_context(self):
        anchors = self.detect_panel_anchors()
        if anchors is None:
            return None

        direction = self.infer_direction_from_current(anchors["warehouse"])
        self.log(f"识别到当前仓库：{anchors['warehouse']}")
        self.log(f"已识别到整理图标，方向建议：{direction}")
        anchors["direction"] = direction
        return anchors

    def _click_screen_pos(self, screen_pos, label=None):
        if not screen_pos:
            return False
        if label:
            self.log(f"点击：{label}")
        self.click_service.click_screen(screen_pos)
        return True

    def click_by_name(self, name, pos_dict):
        pos = pos_dict.get(name)
        if pos is None:
            self.log(f"{name} 未定位")
            return False

        if isinstance(pos, dict):
            if pos.get("ratio") is not None:
                x, y = self.window_manager.to_screen_ratio(pos["ratio"])
            elif pos.get("rel") is not None:
                x, y = self.window_manager.to_screen(pos["rel"])
            else:
                self.log(f"{name} 坐标数据无效")
                return False
        else:
            # 兼容旧配置 (x, y)
            x, y = self.window_manager.to_screen(pos)

        self.click_service.click_screen((x, y))
        return True

    def ctrl_click_screen(self, screen_pos, label=None):
        if screen_pos is None:
            return False

        if label:
            self.log(f"Ctrl+左键：{label}")

        x, y = screen_pos
        pyautogui.moveTo(x, y)
        pyautogui.keyDown("ctrl")
        pyautogui.sleep(0.05)
        pyautogui.click()
        pyautogui.sleep(0.05)
        pyautogui.keyUp("ctrl")
        return True

    def ctrl_click_by_name(self, name, pos_dict):
        pos = pos_dict.get(name)
        if pos is None:
            self.log(f"{name} 未定位")
            return False

        if isinstance(pos, dict):
            if pos.get("ratio") is not None:
                x, y = self.window_manager.to_screen_ratio(pos["ratio"])
            elif pos.get("rel") is not None:
                x, y = self.window_manager.to_screen(pos["rel"])
            else:
                self.log(f"{name} 坐标数据无效")
                return False
        else:
            # 兼容旧配置：(x, y)
            x, y = self.window_manager.to_screen(pos)

        return self.ctrl_click_screen((x, y), label=name)

    def find_switch_button(self, manual_pos=None):
        result = self._find_template(
            "switch_button",
            threshold=self.thresholds["switch_button"],
            retries=3,
        )
        if result:
            self.log(f"识别到仓库切换按钮，置信度：{result['confidence']:.2f}")
            return result["screen_center"]

        if manual_pos is not None:
            self.log("仓库切换按钮识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log("仓库切换按钮识别失败")
        return None

    def find_confirm_button(self, manual_pos=None):
        result = self._find_template(
            "confirm_button",
            threshold=self.thresholds["confirm_button"],
            retries=3,
        )
        if result:
            self.log(f"识别到确认按钮，置信度：{result['confidence']:.2f}")
            return result["screen_center"]

        if manual_pos is not None:
            self.log("确认按钮识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log("确认按钮识别失败")
        return None

    def find_connected_state(self, timeout=5.0):
        start_time = time.time()
        hit_count = 0

        while time.time() - start_time < timeout:
            result = self._find_template(
                "connected_state",
                threshold=self.thresholds["connected_state"],
                retries=1,
                sleep_seconds=0.1,
            )
            if result:
                hit_count += 1
                if hit_count >= 2:
                    self.log(f"检测到已连接，置信度：{result['confidence']:.2f}")
                    return result["screen_center"]
            else:
                hit_count = 0

            if not self.click_service.safe_sleep(0.15):
                return None

        self.log("等待已连接超时")
        return None

    def wait_until_main_warehouse_ready(self, timeout=5.0):
        start_time = time.time()
        esc_sent_twice = False

        while time.time() - start_time < timeout:
            current = self.detect_current_warehouse()
            if current is not None:
                self.log(f"主仓库界面已恢复：{current['warehouse']}")
                return current

            # 过了 1 秒还没回主界面，就补一次 Esc
            if not esc_sent_twice and time.time() - start_time > 1.0:
                self.log("主仓库界面未恢复，补发一次 Esc")
                self.press_esc()
                esc_sent_twice = True

            if not self.click_service.safe_sleep(0.15):
                return None

        self.log("等待主仓库界面恢复超时")
        return None

    def find_select_target(self, target_name, manual_pos=None):
        template_key = "select_wuling" if target_name == "武陵" else "select_gudi"
        result = self._find_template(
            template_key,
            threshold=self.thresholds["select_button"],
            retries=3,
        )
        if result:
            self.log(f"识别到可点击仓库：{target_name}，置信度：{result['confidence']:.2f}")
            return result["screen_center"]

        if manual_pos is not None:
            self.log(f"选择{target_name}识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log(f"选择{target_name}识别失败")
        return None

    def find_backpack_empty_slot(self, manual_pos=None):
        result = self._find_template(
            "backpack_empty_slot",
            threshold=self.thresholds["backpack_empty_slot"],
            retries=3,
        )
        if result:
            self.log(f"识别到背包空格，置信度：{result['confidence']:.2f}")
            return result["screen_center"]

        if manual_pos is not None:
            self.log("背包空格识别失败，改用手动定位坐标")
            return self._manual_pos_to_screen(manual_pos)

        self.log("背包空格识别失败")
        return None

    def resolve_direction(self, direction):
        if direction in ("武陵→谷地", "谷地→武陵"):
            return direction

        context = self.prepare_visual_context()
        if context and context.get("direction"):
            return context["direction"]

        return None

    def _open_switch_dialog(self, switch_pos):
        if switch_pos is None:
            self.click_service.stop()
            return False

        if not self._click_screen_pos(switch_pos, label="仓库切换"):
            self.click_service.stop()
            return False

        return self.click_service.safe_sleep(0.2)

    def press_esc(self):
        if not self.window_manager.activate_window():
            self.log("激活目标窗口失败，Esc 未发送")
            return False

        pyautogui.keyDown("esc")
        pyautogui.sleep(0.05)
        pyautogui.keyUp("esc")
        return True

    def _select_and_confirm(self, target_name, pos_dict):
        target_pos = self.find_select_target(target_name, manual_pos=pos_dict.get(target_name))
        if target_pos is None:
            self.click_service.stop()
            return False

        if not self._click_screen_pos(target_pos, label=f"选择{target_name}"):
            self.click_service.stop()
            return False

        if not self.click_service.safe_sleep(0.2):
            return False

        confirm_pos = self.find_confirm_button(manual_pos=pos_dict.get("确认键"))
        if confirm_pos is None:
            self.click_service.stop()
            return False

        if not self._click_screen_pos(confirm_pos, label="确认"):
            self.click_service.stop()
            return False

        # 先给界面反应时间，避免把“确认按钮”误识别成“已连接”
        if not self.click_service.safe_sleep(0.35):
            return False

        if self.find_connected_state(timeout=5.0) is None:
            self.click_service.stop()
            return False

        self.log("检测到已连接，按 Esc 返回主仓库界面")
        if not self.press_esc():
            self.click_service.stop()
            return False

        if not self.click_service.safe_sleep(0.25):
            return False

        if self.wait_until_main_warehouse_ready(timeout=5.0) is None:
            self.click_service.stop()
            return False

        return True

    def run(self, count, direction, pos_dict):
        self.log("开始检查仓库搬运流程")

        if count <= 0:
            self.log("执行次数不能小于 1")
            return False

        if not self.check_cangku_ready(pos_dict):
            return False

        if not self.window_manager.activate_window():
            self.log("激活目标窗口失败，流程终止")
            return False

        resolved_direction = self.resolve_direction(direction)
        if resolved_direction is None:
            self.log("无法确定搬运方向，流程终止")
            return False

        if resolved_direction == "武陵→谷地":
            first_target = "谷地"
            second_target = "武陵"
        else:
            first_target = "武陵"
            second_target = "谷地"

        self.log(f"本次搬运方向：{resolved_direction}")

        self.click_service.start()

        backpack_slot_pos = self.find_backpack_empty_slot(manual_pos=pos_dict.get("背包"))
        if backpack_slot_pos is None:
            self.click_service.stop()
            return False

        # ===== 提前识别（避免提示文字干扰）=====
        switch_pos = self.find_switch_button(manual_pos=pos_dict.get("仓库切换"))
        if switch_pos is None:
            self.log("找不到仓库切换按钮")
            self.click_service.stop()
            return False

        for i in range(count):
            if not self.click_service.is_running():
                self.log("执行已中止")
                return False

            self.log(f"开始第 {i + 1} 次")

            if not self.ctrl_click_by_name("物品", pos_dict):
                self.click_service.stop()
                return False
            if not self.click_service.safe_sleep(0.5):
                self.log("执行已中止")
                return False

            if not self._open_switch_dialog(switch_pos):
                self.log("打开仓库切换失败")
                return False

            if not self._select_and_confirm(first_target, pos_dict):
                self.log("切换到目标仓库失败")
                return False

            self.log(f"准备 Ctrl+左键背包目标格：{backpack_slot_pos}")
            if not self.ctrl_click_screen(backpack_slot_pos, label="背包目标格"):
                self.click_service.stop()
                return False
            if not self.click_service.safe_sleep(0.4):
                self.log("执行已中止")
                return False
            self.log("背包目标格 Ctrl+左键已执行")

            if not self._open_switch_dialog(switch_pos):
                self.log("打开仓库切换失败")
                return False

            if not self._select_and_confirm(second_target, pos_dict):
                self.log("返回原仓库失败")
                return False

            self.log(f"第 {i + 1} 次执行完成")

        self.click_service.stop()
        self.log("全部执行完成")
        return True
