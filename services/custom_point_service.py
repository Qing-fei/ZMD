import time


class CustomPointService:
    def __init__(self, logger=None):
        self.custom_points = []
        self.custom_point_counter = 1
        self.logger = logger

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    # ===================== 自定义点位管理 =====================
    def add_point(self):
        name = f"pos{self.custom_point_counter}"
        point = {
            "id": f"point_{int(time.time() * 1000)}_{self.custom_point_counter}",
            "name": name,
            "x": None,
            "y": None
        }
        self.custom_points.append(point)
        self.custom_point_counter += 1
        return point

    def delete_point(self, point_id, custom_actions=None):
        point = self.find_custom_point_by_id(point_id)
        if point is None:
            self.log("要删除的点位不存在")
            return False, "要删除的点位不存在"

        if self.is_point_used_in_actions(point_id, custom_actions):
            msg = f"点位 {point['name']} 正在被动作流程使用，不能删除"
            self.log(msg)
            return False, msg

        self.custom_points = [p for p in self.custom_points if p["id"] != point_id]
        msg = f"已删除自定义点位：{point['name']}"
        self.log(msg)
        return True, msg

    def rename_point(self, point_id, new_name):
        point = self.find_custom_point_by_id(point_id)
        if point is None:
            self.log("要重命名的点位不存在")
            return False, "要重命名的点位不存在"

        new_name = (new_name or "").strip()
        if not new_name:
            self.log("点位名称不能为空")
            return False, "点位名称不能为空"

        if self.is_custom_point_name_exists(new_name, exclude_id=point_id):
            self.log("点位名称已存在，请换一个")
            return False, "点位名称已存在，请换一个"

        old_name = point["name"]
        point["name"] = new_name
        msg = f"点位已重命名：{old_name} → {new_name}"
        self.log(msg)
        return True, msg

    def update_point_position(self, point_id, x, y):
        point = self.find_custom_point_by_id(point_id)
        if point is None:
            self.log("当前自定义点位不存在")
            return False, None

        point["x"] = x
        point["y"] = y
        self.log(f"自定义点位 {point['name']} 已记录: {x}, {y}")
        return True, point

    def clear_point_positions(self):
        for point in self.custom_points:
            point["x"] = None
            point["y"] = None
        self.log("已清空所有自定义点位坐标")

    def set_points(self, custom_points, counter=None):
        self.custom_points = custom_points or []
        if counter is None:
            self.custom_point_counter = len(self.custom_points) + 1
        else:
            self.custom_point_counter = counter

    def find_custom_point_by_id(self, point_id):
        for point in self.custom_points:
            if point["id"] == point_id:
                return point
        return None

    def find_custom_point_by_name(self, name):
        for point in self.custom_points:
            if point["name"] == name:
                return point
        return None

    def is_custom_point_name_exists(self, name, exclude_id=None):
        for point in self.custom_points:
            if point["name"] == name and point["id"] != exclude_id:
                return True
        return False

    def is_point_used_in_actions(self, point_id, custom_actions=None):
        actions = custom_actions or []
        for action in actions:
            if action.get("target_id") == point_id:
                return True
            if action.get("start_id") == point_id:
                return True
            if action.get("end_id") == point_id:
                return True
        return False
