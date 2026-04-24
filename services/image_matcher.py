import cv2
import numpy as np
import mss


class ImageMatcher:
    def __init__(self, logger=None):
        self.logger = logger

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def capture_region(self, rect):
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        with mss.mss() as sct:
            shot = sct.grab({
                "left": left,
                "top": top,
                "width": width,
                "height": height
            })

            img = np.array(shot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img

    def _to_gray(self, img):
        if img is None:
            return None
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def match_template_multiscale(
        self,
        screenshot,
        template_path,
        threshold=0.8,
        scales=None,
        use_gray=True,
    ):
        template = cv2.imread(template_path)
        if template is None:
            self.log(f"模板加载失败：{template_path}")
            return None

        if scales is None:
            scales = [0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.25, 1.35]

        src = self._to_gray(screenshot) if use_gray else screenshot
        tpl_src = self._to_gray(template) if use_gray else template

        sh, sw = src.shape[:2]
        best = None

        for scale in scales:
            new_w = max(1, int(tpl_src.shape[1] * scale))
            new_h = max(1, int(tpl_src.shape[0] * scale))

            if new_w > sw or new_h > sh:
                continue

            resized = cv2.resize(tpl_src, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            result = cv2.matchTemplate(src, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if best is None or max_val > best["confidence"]:
                center_x = max_loc[0] + new_w // 2
                center_y = max_loc[1] + new_h // 2
                best = {
                    "confidence": float(max_val),
                    "top_left": max_loc,
                    "center": (center_x, center_y),
                    "size": (new_w, new_h),
                    "scale": scale,
                }

        if best is None or best["confidence"] < threshold:
            return None

        return best

    def find_in_window(
        self,
        window_rect,
        template_path,
        threshold=0.8,
        scales=None,
        use_gray=True,
    ):
        screenshot = self.capture_region(window_rect)
        match = self.match_template_multiscale(
            screenshot,
            template_path,
            threshold=threshold,
            scales=scales,
            use_gray=use_gray,
        )

        if match is None:
            return None

        left, top, _, _ = window_rect
        screen_center = (
            left + match["center"][0],
            top + match["center"][1]
        )

        return {
            "confidence": match["confidence"],
            "screen_center": screen_center,
            "window_center": match["center"],
            "top_left": match["top_left"],
            "size": match["size"],
            "scale": match["scale"],
        }