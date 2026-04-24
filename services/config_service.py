import json
import os


class ConfigService:
    def __init__(self, logger=None):
        self.logger = logger

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    # ===================== 保存 =====================
    def save_config(self, pos_dict, custom_points, custom_actions, counter):
        data = {
            "fixed_pos": pos_dict,
            "custom_points": custom_points,
            "custom_actions": custom_actions,
            "custom_point_counter": counter
        }

        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.log("配置已保存")

    # ===================== 加载 =====================
    def load_config(self):
        if not os.path.exists("config.json"):
            self.log("没有配置文件")
            return None

        with open("config.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # 兼容旧版
        if isinstance(data, dict) and "fixed_pos" in data:
            result = {
                "pos_dict": data.get("fixed_pos", {}),
                "custom_points": data.get("custom_points", []),
                "custom_actions": data.get("custom_actions", []),
                "custom_point_counter": data.get("custom_point_counter", 1)
            }
        else:
            result = {
                "pos_dict": data,
                "custom_points": [],
                "custom_actions": [],
                "custom_point_counter": 1
            }

        self.log("配置已加载")
        return result

    # ===================== 清空 =====================
    def clear_pos(self, pos_dict, custom_points):
        # 清空固定点位
        for k in pos_dict:
            pos_dict[k] = None

        # 清空自定义点位坐标
        for point in custom_points:
            point["x"] = None
            point["y"] = None

        self.log("已清空所有定位")