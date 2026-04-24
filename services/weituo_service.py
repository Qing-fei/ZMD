from pathlib import Path
import re
import time

import cv2
import numpy as np



class WeituoService:
    def __init__(self, window_manager, click_service, image_matcher=None, logger=None):
        self.window_manager = window_manager
        self.click_service = click_service
        self.image_matcher = image_matcher
        self.logger = logger

        base_dir = Path("assets/templates/weituo")
        self.templates = {
            "refresh_button": str(base_dir / "refresh_button.png"),
            "accept_button": str(base_dir / "accept_button.png"),
            "reward_header": str(base_dir / "reward_header.png"),
            "refresh_cooldown": str(base_dir / "refresh_cooldown.png"),
            "commission_icon": str(base_dir / "commission_icon.png"),
        }
        self.thresholds = {
            "refresh_button": 0.72,
            "accept_button": 0.72,
            "reward_header": 0.72,
            "refresh_cooldown": 0.68,
            "commission_icon": 0.70,
        }

        from paddleocr import PaddleOCR

        self.ocr = PaddleOCR(
            use_textline_orientation=False,
            lang='ch'
        )

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def _visual_enabled(self):
        return self.image_matcher is not None

    def _safe_sleep(self, seconds):
        if self.click_service.is_running():
            return self.click_service.safe_sleep(seconds)
        time.sleep(seconds)
        return True

    def _find_template(self, template_key, threshold=None, rect=None, retries=2, sleep_seconds=0.12):
        if not self._visual_enabled():
            return None

        search_rect = rect or self.window_manager.get_window_rect()
        if not search_rect:
            return None

        if threshold is None:
            threshold = self.thresholds.get(template_key, 0.72)

        template_path = self.templates.get(template_key)
        if not template_path:
            return None

        for _ in range(max(retries, 1)):
            result = self.image_matcher.find_in_window(
                search_rect,
                template_path,
                threshold=threshold,
            )
            if result:
                return result
            if not self._safe_sleep(sleep_seconds):
                return None
        return None

    def _capture(self, rect):
        return self.image_matcher.capture_region(rect)

    def _load_template(self, template_key):
        path = self.templates.get(template_key)
        if not path:
            return None
        img = cv2.imread(path)
        if img is None:
            self.log(f"模板加载失败：{path}")
        return img

    def _find_all_template(self, rect, template_key, threshold=None, max_results=10):
        if not self._visual_enabled():
            return []

        template = self._load_template(template_key)
        if template is None:
            return []

        screenshot = self._capture(rect)
        if screenshot is None:
            return []

        if threshold is None:
            threshold = self.thresholds.get(template_key, 0.72)

        src = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        tpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= threshold)

        h, w = tpl.shape[:2]
        left, top, _, _ = rect
        hits = []
        for x, y in zip(xs, ys):
            conf = float(result[y, x])
            hits.append({
                "confidence": conf,
                "top_left": (int(x), int(y)),
                "window_center": (int(x + w // 2), int(y + h // 2)),
                "screen_center": (int(left + x + w // 2), int(top + y + h // 2)),
                "size": (int(w), int(h)),
                "screen_top_left": (int(left + x), int(top + y)),
            })

        hits.sort(key=lambda item: item["confidence"], reverse=True)

        deduped = []
        for item in hits:
            cx, cy = item["screen_center"]
            too_close = False
            for exist in deduped:
                ex, ey = exist["screen_center"]
                if abs(cx - ex) <= max(10, w // 2) and abs(cy - ey) <= max(10, h // 2):
                    too_close = True
                    break
            if too_close:
                continue
            deduped.append(item)
            if len(deduped) >= max_results:
                break

        deduped.sort(key=lambda item: item["screen_center"][1])
        return deduped

    def _parse_commission_text(self, text):
        if not text:
            return None

        cleaned = text.replace(" ", "").replace("O", "0").replace("o", "0")
        cleaned = cleaned.replace("。", ".").replace("，", ".").replace(",", ".")
        cleaned = cleaned.replace("..", ".")

        match = re.search(r"(\d{1,2}\.\d)", cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        match = re.search(r"(\d{1,3})", cleaned)
        if match:
            raw = match.group(1)
            if len(raw) >= 2:
                try:
                    return float(f"{raw[:-1]}.{raw[-1]}")
                except ValueError:
                    return None
        return None

    def _ocr_commission_value(self, rect):
        img = self._capture(rect)
        if img is None or img.size == 0:
            return None, ""

        # 预处理（你刚测试成功那套）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        _, binary = cv2.threshold(enlarged, 160, 255, cv2.THRESH_BINARY)

        # ⚠️ 转回三通道（否则会报你刚才那个错）
        binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        try:
            result = self.ocr.predict(binary_bgr)
        except Exception as e:
            self.log(f"OCR异常：{e}")
            return None, ""

        if not result:
            return None, ""

        try:
            rec_texts = result[0].get("rec_texts", [])
        except Exception:
            return None, ""

        if not rec_texts:
            return None, ""

        raw_text = rec_texts[0]
        value = self._parse_commission_text(raw_text)

        return value, raw_text

    def _build_commission_ocr_rect(self, icon_result):
        x, y = icon_result["screen_center"]
        w, h = icon_result["size"]
        left = int(x - w * 1.0)
        top = int(y + h * 0.5)
        right = int(x + w * 1.2)
        bottom = int(y + h * 1.4)
        return (left, top, right, bottom)

    def _build_accept_search_rect(self, icon_result):
        x, y = icon_result["screen_center"]
        w, h = icon_result["size"]
        window_rect = self.window_manager.get_window_rect()
        if not window_rect:
            return None
        _, _, win_right, _ = window_rect
        left = int(x + w * 0.5)
        top = int(y - h * 1.2)
        right = int(min(win_right, x + w * 10))
        bottom = int(y + h * 1.8)
        return (left, top, right, bottom)

    def find_reward_header(self):
        result = self._find_template("reward_header", threshold=self.thresholds["reward_header"], retries=3)
        if result:
            self.log(f"识别到报酬栏，置信度：{result['confidence']:.2f}")
        else:
            self.log("未识别到报酬栏")
        return result

    def _build_commission_search_rect(self, reward_header_result):
        window_rect = self.window_manager.get_window_rect()
        if not window_rect or reward_header_result is None:
            return None

        left, top, right, bottom = window_rect
        header_x, header_y = reward_header_result["screen_center"]
        header_w, header_h = reward_header_result["size"]

        search_left = int(max(left, header_x - header_w * 1.25))
        search_right = int(min(right, header_x + header_w * 1.25))
        search_top = int(header_y + header_h * 0.55)
        search_bottom = int(min(bottom, search_top + header_h * 9.0))
        return (search_left, search_top, search_right, search_bottom)

    def find_commission_candidates(self):
        header = self.find_reward_header()
        if header is None:
            return []

        search_rect = self._build_commission_search_rect(header)
        if search_rect is None:
            return []

        icon_results = self._find_all_template(
            search_rect,
            "commission_icon",
            threshold=self.thresholds["commission_icon"],
            max_results=8,
        )
        if not icon_results:
            self.log("未识别到佣金锚点")
            return []

        candidates = []
        for idx, icon in enumerate(icon_results[:3], start=1):
            ocr_rect = self._build_commission_ocr_rect(icon)
            value, raw_text = self._ocr_commission_value(ocr_rect)
            if value is None:
                self.log(f"第{idx}条佣金识别失败，OCR原文：{raw_text or '[空]'}")
                continue

            candidates.append({
                "value": value,
                "icon": icon,
                "ocr_rect": ocr_rect,
                "ocr_text": raw_text,
            })
            self.log(f"第{idx}条佣金识别：{value:.1f}万（OCR：{raw_text or '[空]'}）")

        return candidates

    def find_best_candidate(self, min_value):
        candidates = self.find_commission_candidates()
        if not candidates:
            return None

        filtered = [item for item in candidates if item["value"] >= float(min_value)]
        if not filtered:
            self.log(f"当前无满足最低佣金 {float(min_value):.1f}万 的委托")
            return None

        best = max(filtered, key=lambda item: item["value"])
        self.log(f"选中最高佣金委托：{best['value']:.1f}万")
        return best

    def find_accept_button_for_candidate(self, candidate):
        rect = self._build_accept_search_rect(candidate["icon"])
        if rect is None:
            return None

        result = self._find_template(
            "accept_button",
            threshold=self.thresholds["accept_button"],
            rect=rect,
            retries=1,
            sleep_seconds=0.08,
        )
        if result:
            self.log(f"识别到接取按钮，置信度：{result['confidence']:.2f}")
            return result["screen_center"]

        self.log("未识别到接取按钮")
        return None

    def find_refresh_button(self):
        result = self._find_template(
            "refresh_button",
            threshold=self.thresholds["refresh_button"],
            retries=2,
        )
        if result:
            self.log(f"识别到刷新按钮，置信度：{result['confidence']:.2f}")
        return result

    def in_refresh_cooldown(self):
        result = self._find_template(
            "refresh_cooldown",
            threshold=self.thresholds["refresh_cooldown"],
            retries=1,
            sleep_seconds=0.05,
        )
        if result:
            self.log("当前处于刷新冷却")
            return True
        return False

    def _click_screen_pos(self, screen_pos, label=None):
        if screen_pos is None:
            return False
        if label:
            self.log(f"点击：{label}")
        self.click_service.click_screen(screen_pos)
        return True

    def run(self, min_commission):
        if not self.window_manager.is_bound():
            self.log("未绑定窗口")
            return False

        if not self._visual_enabled():
            self.log("未启用图像识别，无法自动接取委托")
            return False

        if not self.window_manager.activate_window():
            self.log("激活目标窗口失败")
            return False

        self.click_service.start()
        self.log(f"开始自动接取委托，最低佣金：{float(min_commission):.1f}万")

        try:
            while self.click_service.is_running():
                best = self.find_best_candidate(min_commission)
                if best is not None:
                    accept_pos = self.find_accept_button_for_candidate(best)
                    if accept_pos is not None:
                        self._click_screen_pos(accept_pos, label=f"接取 {best['value']:.1f}万 委托")
                        self.log("已接取满足条件的委托，停止刷新")
                        self.click_service.stop()
                        return True

                    self.log("已找到合适佣金，但未找到接取按钮，本轮跳过")

                if self.in_refresh_cooldown():
                    if not self._safe_sleep(0.5):
                        return False
                    continue

                refresh_result = self.find_refresh_button()
                if refresh_result is not None:
                    self._click_screen_pos(refresh_result["screen_center"], label="刷新")
                    if not self._safe_sleep(0.35):
                        return False
                    continue

                self.log("既未识别到可接委托，也未识别到刷新按钮，等待后重试")
                if not self._safe_sleep(0.5):
                    return False

            self.log("自动接取委托已中止")
            return False
        finally:
            self.click_service.stop()
