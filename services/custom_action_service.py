class CustomActionService:
    def __init__(self, custom_point_service, logger=None):
        self.custom_point_service = custom_point_service
        self.logger = logger
        self.custom_actions = []

    def log(self, msg):
        if self.logger:
            self.logger(msg)

    def add_click_action(self, point_id):
        point = self.custom_point_service.find_point_by_id(point_id)
        if point is None:
            self.log("选择的点位不存在")
            return False

        self.custom_actions.append({
            "type": "click",
            "target_id": point_id
        })
        return True

    def add_delay_action(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            self.log("延时秒数格式不正确")
            return False

        if value < 0:
            self.log("延时秒数不能小于 0")
            return False

        self.custom_actions.append({
            "type": "delay",
            "value": value
        })
        return True

    def add_drag_action(self, start_id, end_id, duration):
        if start_id == end_id:
            self.log("起点和终点不能相同")
            return False

        start_point = self.custom_point_service.find_point_by_id(start_id)
        end_point = self.custom_point_service.find_point_by_id(end_id)

        if start_point is None or end_point is None:
            self.log("选择的点位不存在")
            return False

        try:
            duration = float(duration)
        except (TypeError, ValueError):
            self.log("拖动时长格式不正确")
            return False

        if duration < 0:
            self.log("拖动时长不能小于 0")
            return False

        self.custom_actions.append({
            "type": "drag",
            "start_id": start_id,
            "end_id": end_id,
            "duration": duration
        })
        return True

    def delete_action(self, row):
        if row is None or row < 0 or row >= len(self.custom_actions):
            self.log("请先选中要删除的动作")
            return None

        action = self.custom_actions.pop(row)
        return action

    def move_action_up(self, row):
        if row is None or row < 0 or row >= len(self.custom_actions):
            self.log("请先选中要上移的动作")
            return None
        if row == 0:
            self.log("已经是第一条动作")
            return row

        self.custom_actions[row - 1], self.custom_actions[row] = self.custom_actions[row], self.custom_actions[row - 1]
        return row - 1

    def move_action_down(self, row):
        if row is None or row < 0 or row >= len(self.custom_actions):
            self.log("请先选中要下移的动作")
            return None
        if row == len(self.custom_actions) - 1:
            self.log("已经是最后一条动作")
            return row

        self.custom_actions[row + 1], self.custom_actions[row] = self.custom_actions[row], self.custom_actions[row + 1]
        return row + 1

    def action_to_text(self, action):
        if action["type"] == "click":
            point = self.custom_point_service.find_point_by_id(action.get("target_id"))
            return f"点击 {point['name']}" if point else "点击 [点位不存在]"

        if action["type"] == "delay":
            return f"延时 {action.get('value', 0)} 秒"

        if action["type"] == "drag":
            start_point = self.custom_point_service.find_point_by_id(action.get("start_id"))
            end_point = self.custom_point_service.find_point_by_id(action.get("end_id"))
            start_name = start_point["name"] if start_point else "[起点不存在]"
            end_name = end_point["name"] if end_point else "[终点不存在]"
            duration = action.get("duration", 0.2)
            return f"拖动 {start_name} → {end_name} ({duration} 秒)"

        return str(action)
