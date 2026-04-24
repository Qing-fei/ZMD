import json
import math
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt
import keyboard
import pyautogui
import win32gui
import win32con

from utils.signal_bus import SignalBus
from services.window_manager import WindowManager
from services.click_service import ClickService
from services.image_matcher import ImageMatcher
from services.jingduan_service import JingduanService
from services.cangku_service import CangkuService

from services.weituo_service import WeituoService


class MainWindow:
    def __init__(self):
        ui_path = Path(__file__).resolve().parent / "chuangkou.ui"
        self.ui = uic.loadUi(str(ui_path))

        self.ui.label_bangdingzhuangtai.setText("未绑定")
        self.ui.label_bangdingzhuangtai.setStyleSheet("color: red;")
        self.ui.lineEdit_chuangkouming.setText("Endfield")

        self.original_key_press_event = self.ui.keyPressEvent
        self.ui.keyPressEvent = self.ui_key_press_event

        self.current_locate = None
        self.current_custom_point_id = None
        self.last_calc_times = None
        self.stop_requested = False

        self.current_log_channel = "cangku"

        self.pos_dict = {
            "确认键": None,
            "仓库切换": None,
            "背包": None,
            "武陵": None,
            "谷地": None,
            "物品": None,
            "装备": None,
            "精锻键": None,
        }

        self.cangku_keys = ["确认键", "仓库切换", "背包", "武陵", "谷地", "物品"]
        self.jingduan_keys = ["装备", "精锻键"]

        self.custom_points = []
        self.custom_actions = []
        self.custom_point_counter = 1

        self.signals = SignalBus()
        self.signals.k_pressed.connect(self.record_mouse_pos)

        keyboard.add_hotkey("k", lambda: self.signals.k_pressed.emit())
        keyboard.add_hotkey("l", self.request_stop)

        self.window_manager = WindowManager(logger=self.log)
        self.click_service = ClickService(self.window_manager, logger=self.log)
        self.image_matcher = ImageMatcher(logger=self.log)
        self.jingduan_service = JingduanService(
            self.window_manager,
            self.click_service,
            self.image_matcher,
            logger=self.log,
        )

        self.weituo_service = WeituoService(
            self.window_manager,
            self.click_service,
            self.image_matcher,
            logger=self.log_weituo,
        )

        self.cangku_service = CangkuService(
            self.window_manager,
            self.click_service,
            self.image_matcher,
            logger=self.log,
        )

        self.bind_signals()
        self.init_custom_tables()
        self.update_text()
        self.refresh_custom_point_table()
        self.refresh_custom_action_table()
        self.update_current_point_labels(None)
        self.calc_transport_times()
        self.init_fold_panels()

    def activate_ui_window(self):
        try:
            ui_hwnd = int(self.ui.winId())
            win32gui.ShowWindow(ui_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(ui_hwnd)
        except Exception as e:
            self.log(f"激活程序窗口失败: {e}")
    def init_fold_panels(self):
        self.ui.groupBox_cangku_dingwei.setVisible(False)
        self.ui.btn_toggle_cangku_dingwei.setText("展开手动定位")
#上下两个是关于手动定位键折叠的
    def toggle_cangku_dingwei(self):
        visible = self.ui.groupBox_cangku_dingwei.isVisible()
        self.ui.groupBox_cangku_dingwei.setVisible(not visible)

        if visible:
            self.ui.btn_toggle_cangku_dingwei.setText("展开手动定位")
        else:
            self.ui.btn_toggle_cangku_dingwei.setText("收起手动定位")

    def log(self, msg):
        if self.current_log_channel == "jingduan":
            self.ui.textEdit_2.append(str(msg))
        elif self.current_log_channel == "weituo":
            self.ui.textEdit_3.append(str(msg))
        else:
            self.ui.textEdit.append(str(msg))

    def log_weituo(self, msg):
        self.ui.textEdit_3.append(str(msg))

    def ui_key_press_event(self, event):
        if event.key() == Qt.Key_Escape:
            self.log("Esc 已屏蔽，不再关闭程序")
            event.ignore()
            return
        self.original_key_press_event(event)

    def request_stop(self):
        self.stop_requested = True
        try:
            self.click_service.stop()
        except Exception:
            pass
        self.set_ui_topmost(True)
        self.log("已请求停止")

    def reset_stop_flag(self):
        self.stop_requested = False

    def bind_signals(self):
        # 通用按钮
        self.ui.bangdingyouxichuangkou.clicked.connect(self.bind_window)
        # self.ui.baocunpeizhi.clicked.connect(self.save_config)
        # self.ui.jiazaipeizhi.clicked.connect(self.load_config)
        # self.ui.qingkongdingwei.clicked.connect(self.clear_all_positions)
        self.ui.zhongzhizhixing.clicked.connect(self.request_stop)

        # 仓库搬运定位
        self.ui.dw_queren.clicked.connect(lambda: self.start_locate("确认键"))
        self.ui.dw_cangkuqiehuan.clicked.connect(lambda: self.start_locate("仓库切换"))
        self.ui.dw_beibao.clicked.connect(lambda: self.start_locate("背包"))
        self.ui.dw_wuling.clicked.connect(lambda: self.start_locate("武陵"))
        self.ui.dw_gudi.clicked.connect(lambda: self.start_locate("谷地"))
        self.ui.dw_wuping.clicked.connect(lambda: self.start_locate("物品"))
        self.ui.zhixingdongzuoxulie.clicked.connect(self.run_transport_sequence)

        # 精锻
        self.ui.dw_zhuangbei.clicked.connect(lambda: self.start_locate("装备"))
        self.ui.dw_jingduanjian.clicked.connect(lambda: self.start_locate("精锻键"))
        self.ui.kaishijingduan.clicked.connect(self.run_jingduan_sequence)

        # 搬运计算
        self.ui.spinBox_x.valueChanged.connect(self.calc_transport_times)
        self.ui.spinBox_y.valueChanged.connect(self.calc_transport_times)

        # 点位管理
        self.ui.btn_xinzengdianwei.clicked.connect(self.add_custom_point)
        self.ui.btn_shanchudianwei.clicked.connect(self.delete_custom_point)
        self.ui.btn_chongmingmingdianwei.clicked.connect(self.rename_custom_point)
        self.ui.btn_kaishidingwei.clicked.connect(self.start_custom_point_locate)
        self.ui.tableWidget_dianwei.itemSelectionChanged.connect(self.on_custom_point_selected)

        # 动作安排
        self.ui.btn_tianjiajidian.clicked.connect(self.add_click_action)
        self.ui.btn_tianjiayanshi.clicked.connect(self.add_delay_action)
        self.ui.btn_tianjiatuodong.clicked.connect(self.add_drag_action)
        self.ui.btn_shanchudongzuo.clicked.connect(self.delete_action)
        self.ui.btn_shangyidongzuo.clicked.connect(self.move_action_up)
        self.ui.btn_xiayidongzuo.clicked.connect(self.move_action_down)
        self.ui.btn_zhixingzidingyi.clicked.connect(self.run_custom_actions)

        self.ui.btn_toggle_cangku_dingwei.clicked.connect(self.toggle_cangku_dingwei)

        # 菜单栏（配置）
        self.ui.action_baocunpeizhi.triggered.connect(self.save_config)
        self.ui.action_jiazaipeizhi.triggered.connect(self.load_config)
        self.ui.action_qingkongdingwei.triggered.connect(self.clear_all_positions)
        #委托
        self.ui.kaishizidongjietuo.clicked.connect(self.run_weituo_sequence)

    def run_weituo_sequence(self):
        min_commission = self.ui.doubleSpinBox_zuidiyongjin.value()
        self.reset_stop_flag()
        self.current_log_channel = "weituo"
        self.set_ui_topmost(False)
        try:
            self.weituo_service.run(min_commission=min_commission)
        finally:
            self.set_ui_topmost(True)
            self.activate_ui_window()
            self.current_log_channel = "cangku"
    def bind_window(self):
        title = self.ui.lineEdit_chuangkouming.text().strip()
        ok = self.window_manager.bind_window(title)
        if ok:
            self.ui.label_bangdingzhuangtai.setText("已绑定")
            self.ui.label_bangdingzhuangtai.setStyleSheet("color: green;")
            self.log(f"窗口绑定成功：{title}")
        else:
            self.ui.label_bangdingzhuangtai.setText("绑定失败")
            self.ui.label_bangdingzhuangtai.setStyleSheet("color: red;")
            self.log(f"窗口绑定失败：{title}")

    def set_ui_topmost(self, topmost=True):
        try:
            ui_hwnd = int(self.ui.winId())
            flag = win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST
            win32gui.SetWindowPos(
                ui_hwnd,
                flag,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
            )
        except Exception as e:
            self.log(f"置顶失败: {e}")

    def start_locate(self, name):
        self.current_locate = name
        self.current_custom_point_id = None
        self.log(f"开始定位：{name}，按K记录")

    def start_custom_point_locate(self):
        row = self.get_selected_custom_point_row()
        if row is None:
            self.log("请先在点位表中选中一个点位")
            return
        point = self.custom_points[row]
        self.current_custom_point_id = point["id"]
        self.current_locate = None
        self.log(f"开始定位自定义点位：{point['name']}，按K记录")

    def record_mouse_pos(self):
        rect = self.window_manager.get_window_rect()
        if not rect:
            self.log("请先绑定窗口")
            return

        x, y = pyautogui.position()
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        rel_x = x - left
        rel_y = y - top

        ratio_x = rel_x / width if width else 0
        ratio_y = rel_y / height if height else 0

        if self.current_locate:
            self.pos_dict[self.current_locate] = {
                "rel": (rel_x, rel_y),
                "ratio": (ratio_x, ratio_y),
            }
            self.update_text()
            self.log(f"{self.current_locate} 已记录: rel=({rel_x}, {rel_y}), ratio=({ratio_x:.4f}, {ratio_y:.4f})")
            self.current_locate = None
            return

        if self.current_custom_point_id:
            point = self.find_custom_point_by_id(self.current_custom_point_id)
            if point is None:
                self.log("当前自定义点位不存在")
                self.current_custom_point_id = None
                return

            point["x"] = rel_x
            point["y"] = rel_y
            point["ratio_x"] = ratio_x
            point["ratio_y"] = ratio_y

            self.refresh_custom_point_table()
            self.select_custom_point_by_id(point["id"])
            self.update_current_point_labels(point)
            self.log(f"自定义点位 {point['name']} 已记录: rel=({rel_x}, {rel_y}), ratio=({ratio_x:.4f}, {ratio_y:.4f})")
            self.current_custom_point_id = None

    def run_jingduan_sequence(self):
        count = self.ui.spinBox_jingduan.value()
        self.reset_stop_flag()
        self.current_log_channel = "jingduan"
        self.set_ui_topmost(False)
        try:
            self.jingduan_service.run(
                count=count,
                manual_equipment=self.pos_dict.get("装备"),
                manual_forge_button=self.pos_dict.get("精锻键"),
            )
        finally:
            self.set_ui_topmost(True)
            self.activate_ui_window()
            self.current_log_channel = "cangku"

    def update_text(self):
        cangku_lines = []
        for name in self.cangku_keys:
            pos = self.pos_dict.get(name)
            if not pos:
                text = "未记录"
            elif isinstance(pos, dict):
                text = f"rel={pos.get('rel')} ratio={pos.get('ratio')}"
            else:
                text = str(pos)  # 兼容旧数据
            cangku_lines.append(f"{name}: {text}")
        self.ui.textEdit.setPlainText("\n".join(cangku_lines))

        jingduan_lines = []
        for name in self.jingduan_keys:
            pos = self.pos_dict.get(name)
            if not pos:
                text = "未记录"
            elif isinstance(pos, dict):
                text = f"rel={pos.get('rel')} ratio={pos.get('ratio')}"
            else:
                text = str(pos)
            jingduan_lines.append(f"{name}: {text}")
        self.ui.textEdit_2.setPlainText("\n".join(jingduan_lines))

    def calc_transport_times(self):
        x = self.ui.spinBox_x.value()
        y = self.ui.spinBox_y.value()
        if x >= 35:
            self.ui.spinBox_cishu.setValue(0)
            self.last_calc_times = 0
            return
        capacity = (35 - x) * 50
        if capacity <= 0:
            self.ui.spinBox_cishu.setValue(0)
            self.last_calc_times = 0
            return
        times = math.ceil(y / capacity) if y > 0 else 0
        if times != self.last_calc_times:
            self.last_calc_times = times
            self.ui.spinBox_cishu.setValue(times)

    def init_custom_tables(self):
        self.ui.tableWidget_dianwei.setColumnCount(3)
        self.ui.tableWidget_dianwei.setHorizontalHeaderLabels(["名称", "坐标", "状态"])
        self.ui.tableWidget_dianwei.setSelectionBehavior(self.ui.tableWidget_dianwei.SelectRows)
        self.ui.tableWidget_dianwei.setSelectionMode(self.ui.tableWidget_dianwei.SingleSelection)
        self.ui.tableWidget_dianwei.setEditTriggers(self.ui.tableWidget_dianwei.NoEditTriggers)
        self.ui.tableWidget_dianwei.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.ui.tableWidget_dongzuo.setColumnCount(4)
        self.ui.tableWidget_dongzuo.setHorizontalHeaderLabels(["顺序", "动作类型", "目标", "参数"])
        self.ui.tableWidget_dongzuo.setSelectionBehavior(self.ui.tableWidget_dongzuo.SelectRows)
        self.ui.tableWidget_dongzuo.setSelectionMode(self.ui.tableWidget_dongzuo.SingleSelection)
        self.ui.tableWidget_dongzuo.setEditTriggers(self.ui.tableWidget_dongzuo.NoEditTriggers)
        self.ui.tableWidget_dongzuo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def refresh_custom_point_table(self):
        table = self.ui.tableWidget_dianwei
        table.setRowCount(len(self.custom_points))
        for row, point in enumerate(self.custom_points):
            coord_text = "未记录" if point["x"] is None or point["y"] is None else f"({point['x']}, {point['y']})"
            status_text = "未定位" if point["x"] is None or point["y"] is None else "已定位"
            table.setItem(row, 0, QTableWidgetItem(point["name"]))
            table.setItem(row, 1, QTableWidgetItem(coord_text))
            table.setItem(row, 2, QTableWidgetItem(status_text))
        table.clearSelection()

    def refresh_custom_action_table(self):
        table = self.ui.tableWidget_dongzuo
        table.setRowCount(len(self.custom_actions))
        for row, action in enumerate(self.custom_actions):
            target_name = "-"
            param_text = "-"
            action_type_text = "未知"
            if action["type"] == "click":
                point = self.find_custom_point_by_id(action.get("target_id"))
                target_name = point["name"] if point else "[点位不存在]"
                action_type_text = "点击"
            elif action["type"] == "delay":
                action_type_text = "延时"
                param_text = f"{action.get('value', 0)}秒"
            elif action["type"] == "drag":
                start_point = self.find_custom_point_by_id(action.get("start_id"))
                end_point = self.find_custom_point_by_id(action.get("end_id"))
                start_name = start_point["name"] if start_point else "[起点不存在]"
                end_name = end_point["name"] if end_point else "[终点不存在]"
                action_type_text = "拖动"
                target_name = f"{start_name} → {end_name}"
                param_text = f"{action.get('duration', 0.2)}秒"
            table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            table.setItem(row, 1, QTableWidgetItem(action_type_text))
            table.setItem(row, 2, QTableWidgetItem(target_name))
            table.setItem(row, 3, QTableWidgetItem(param_text))
        table.clearSelection()

    def update_current_point_labels(self, point=None):
        if point is None:
            self.ui.label_dangqiandianwei.setText("当前点位：无")
            self.ui.label_dangqianzuobiao.setText("当前坐标：未定位")
            return
        self.ui.label_dangqiandianwei.setText(f"当前点位：{point['name']}")
        if point["x"] is None or point["y"] is None:
            self.ui.label_dangqianzuobiao.setText("当前坐标：未定位")
        else:
            self.ui.label_dangqianzuobiao.setText(f"当前坐标：({point['x']}, {point['y']})")

    def on_custom_point_selected(self):
        row = self.get_selected_custom_point_row()
        if row is None:
            self.update_current_point_labels(None)
            return
        self.update_current_point_labels(self.custom_points[row])

    def get_selected_custom_point_row(self):
        row = self.ui.tableWidget_dianwei.currentRow()
        if row < 0 or row >= len(self.custom_points):
            return None
        return row

    def get_selected_action_row(self):
        row = self.ui.tableWidget_dongzuo.currentRow()
        if row < 0 or row >= len(self.custom_actions):
            return None
        return row

    def find_custom_point_by_id(self, point_id):
        for point in self.custom_points:
            if point["id"] == point_id:
                return point
        return None

    def _get_custom_point_names(self, positioned_only=False):
        names = []
        for point in self.custom_points:
            if positioned_only and (point["x"] is None or point["y"] is None):
                continue
            names.append(point["name"])
        return names

    def _get_point_by_name(self, name):
        for point in self.custom_points:
            if point["name"] == name:
                return point
        return None

    def _get_point_display_names(self, positioned_only=False):
        names = []
        for point in self.custom_points:
            if positioned_only and (point["x"] is None or point["y"] is None):
                continue
            suffix = "（未定位）" if point["x"] is None or point["y"] is None else ""
            names.append(f"{point['name']}{suffix}")
        return names

    def _choose_point(self, title, label, positioned_only=False, exclude_point_id=None):
        candidates = []
        display_names = []
        for point in self.custom_points:
            if exclude_point_id is not None and point["id"] == exclude_point_id:
                continue
            if positioned_only and (point["x"] is None or point["y"] is None):
                continue
            candidates.append(point)
            suffix = "（未定位）" if point["x"] is None or point["y"] is None else ""
            display_names.append(f"{point['name']}{suffix}")

        if not candidates:
            self.log("没有可选点位")
            return None

        display_name, ok = QInputDialog.getItem(self.ui, title, label, display_names, 0, False)
        if not ok:
            return None

        index = display_names.index(display_name)
        return candidates[index]

    def select_custom_point_by_id(self, point_id):
        for row, point in enumerate(self.custom_points):
            if point["id"] == point_id:
                self.ui.tableWidget_dianwei.selectRow(row)
                self.ui.tableWidget_dianwei.setCurrentCell(row, 0)
                return

    def select_action_row(self, row):
        if 0 <= row < len(self.custom_actions):
            self.ui.tableWidget_dongzuo.selectRow(row)
            self.ui.tableWidget_dongzuo.setCurrentCell(row, 0)

    # 点位管理
    def add_custom_point(self):
        name, ok = QInputDialog.getText(
            self.ui,
            "新增点位",
            "请输入点位名称：",
            text=f"pos{self.custom_point_counter}",
        )
        if not ok:
            return

        name = name.strip()
        if not name:
            self.log("点位名称不能为空")
            return
        if any(point["name"] == name for point in self.custom_points):
            self.log("点位名称重复")
            return

        point = {
            "id": self.custom_point_counter,
            "name": name,
            "x": None,
            "y": None,
        }
        self.custom_point_counter += 1
        self.custom_points.append(point)
        self.refresh_custom_point_table()
        self.select_custom_point_by_id(point["id"])
        self.update_current_point_labels(point)
        self.log(f"已新增点位：{name}")

    def delete_custom_point(self):
        row = self.get_selected_custom_point_row()
        if row is None:
            self.log("请先选中要删除的点位")
            return

        point = self.custom_points[row]
        point_id = point["id"]
        point_name = point["name"]
        self.custom_points.pop(row)

        self.custom_actions = [
            action
            for action in self.custom_actions
            if action.get("target_id") != point_id
            and action.get("start_id") != point_id
            and action.get("end_id") != point_id
        ]

        self.refresh_custom_point_table()
        self.refresh_custom_action_table()

        if self.custom_points:
            next_row = min(row, len(self.custom_points) - 1)
            next_point = self.custom_points[next_row]
            self.select_custom_point_by_id(next_point["id"])
            self.update_current_point_labels(next_point)
        else:
            self.update_current_point_labels(None)

        self.log(f"已删除点位：{point_name}")

    def rename_custom_point(self):
        row = self.get_selected_custom_point_row()
        if row is None:
            self.log("请先选中一个点位")
            return

        point = self.custom_points[row]
        new_name, ok = QInputDialog.getText(
            self.ui,
            "重命名点位",
            "请输入新名称：",
            text=point["name"],
        )
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name:
            self.log("点位名称不能为空")
            return
        if any(p["name"] == new_name and p["id"] != point["id"] for p in self.custom_points):
            self.log("点位名称重复")
            return

        old_name = point["name"]
        point["name"] = new_name
        self.refresh_custom_point_table()
        self.refresh_custom_action_table()
        self.select_custom_point_by_id(point["id"])
        self.update_current_point_labels(point)
        self.log(f"点位已重命名：{old_name} → {new_name}")

    # 动作安排
    def add_click_action(self):
        if not self.custom_points:
            self.log("请先新增点位")
            return

        point = self._choose_point("添加点击", "选择点击点位：", positioned_only=False)
        if point is None:
            return

        self.custom_actions.append({"type": "click", "target_id": point["id"]})
        self.refresh_custom_action_table()
        self.select_custom_point_by_id(point["id"])
        self.select_action_row(len(self.custom_actions) - 1)
        self.log(f"已添加点击动作：{point['name']}")

    def add_delay_action(self):
        value, ok = QInputDialog.getDouble(
            self.ui,
            "添加延时",
            "请输入延时秒数：",
            1.0,
            0.01,
            9999.0,
            2,
        )
        if not ok:
            return

        self.custom_actions.append({"type": "delay", "value": float(value)})
        self.refresh_custom_action_table()
        self.select_action_row(len(self.custom_actions) - 1)
        self.log(f"已添加延时动作：{value}秒")

    def add_drag_action(self):
        if len(self.custom_points) < 2:
            self.log("至少需要两个点位才能添加拖动动作")
            return

        start_point = self._choose_point("添加拖动", "选择起点：", positioned_only=False)
        if start_point is None:
            return

        end_point = self._choose_point(
            "添加拖动",
            "选择终点：",
            positioned_only=False,
            exclude_point_id=start_point["id"],
        )
        if end_point is None:
            return

        duration, ok = QInputDialog.getDouble(
            self.ui,
            "添加拖动",
            "请输入拖动时长（秒）：",
            0.2,
            0.01,
            9999.0,
            2,
        )
        if not ok:
            return

        self.custom_actions.append(
            {
                "type": "drag",
                "start_id": start_point["id"],
                "end_id": end_point["id"],
                "duration": float(duration),
            }
        )
        self.refresh_custom_action_table()
        self.select_action_row(len(self.custom_actions) - 1)
        self.log(f"已添加拖动动作：{start_point['name']} → {end_point['name']}")

    def delete_action(self):
        row = self.get_selected_action_row()
        if row is None:
            self.log("请先选中一个动作")
            return

        self.custom_actions.pop(row)
        self.refresh_custom_action_table()

        if self.custom_actions:
            next_row = min(row, len(self.custom_actions) - 1)
            self.select_action_row(next_row)

        self.log("已删除动作")

    def move_action_up(self):
        row = self.get_selected_action_row()
        if row is None:
            self.log("请先选中一个动作")
            return
        if row <= 0:
            return

        self.custom_actions[row - 1], self.custom_actions[row] = (
            self.custom_actions[row],
            self.custom_actions[row - 1],
        )
        self.refresh_custom_action_table()
        self.select_action_row(row - 1)

    def move_action_down(self):
        row = self.get_selected_action_row()
        if row is None:
            self.log("请先选中一个动作")
            return
        if row >= len(self.custom_actions) - 1:
            return

        self.custom_actions[row + 1], self.custom_actions[row] = (
            self.custom_actions[row],
            self.custom_actions[row + 1],
        )
        self.refresh_custom_action_table()
        self.select_action_row(row + 1)

    def _get_window_rect(self):
        rect = self.window_manager.get_window_rect()
        if not rect:
            self.log("请先绑定窗口")
            return None
        return rect

    def _move_and_click_relative(self, pos):
        rect = self._get_window_rect()
        if not rect or not pos:
            return False

        left, top, _, _ = rect
        x = left + pos[0]
        y = top + pos[1]
        self.click_service.click_screen((x, y))
        return True

    def _drag_relative(self, start_pos, end_pos, duration):
        rect = self._get_window_rect()
        if not rect or not start_pos or not end_pos:
            return False

        left, top, _, _ = rect
        sx = left + start_pos[0]
        sy = top + start_pos[1]
        ex = left + end_pos[0]
        ey = top + end_pos[1]

        pyautogui.moveTo(sx, sy)
        pyautogui.dragTo(ex, ey, duration=duration, button="left")
        return True

    def run_custom_actions(self):
        if not self.custom_actions:
            self.log("当前没有可执行的自定义动作")
            return

        repeat = self.ui.spinBox_zidingyicishu.value()
        if repeat <= 0:
            self.log("执行次数必须大于 0")
            return

        if not self.window_manager.is_bound():
            self.log("请先绑定窗口")
            return

        self.reset_stop_flag()
        self.click_service.start()
        self.set_ui_topmost(False)

        try:
            if not self.window_manager.activate_window():
                self.log("激活目标窗口失败，自定义动作执行终止")
                return

            for round_index in range(repeat):
                if self.stop_requested or not self.click_service.is_running():
                    break

                self.log(f"开始执行自定义动作，第 {round_index + 1}/{repeat} 次")

                for action in self.custom_actions:
                    if self.stop_requested or not self.click_service.is_running():
                        break

                    if action["type"] == "click":
                        point = self.find_custom_point_by_id(action.get("target_id"))
                        if not point or point["x"] is None or point["y"] is None:
                            self.log("存在未定位的点击点位，执行终止")
                            return
                        if not self._move_and_click_relative((point["x"], point["y"])):
                            self.log("点击动作执行失败，执行终止")
                            return
                        if not self.click_service.safe_sleep(0.15):
                            return

                    elif action["type"] == "delay":
                        if not self.click_service.safe_sleep(float(action.get("value", 0))):
                            return

                    elif action["type"] == "drag":
                        start_point = self.find_custom_point_by_id(action.get("start_id"))
                        end_point = self.find_custom_point_by_id(action.get("end_id"))

                        if not start_point or not end_point:
                            self.log("存在无效拖动点位，执行终止")
                            return

                        if None in (start_point["x"], start_point["y"], end_point["x"], end_point["y"]):
                            self.log("存在未定位的拖动点位，执行终止")
                            return

                        if not self._drag_relative(
                            (start_point["x"], start_point["y"]),
                            (end_point["x"], end_point["y"]),
                            float(action.get("duration", 0.2)),
                        ):
                            self.log("拖动动作执行失败，执行终止")
                            return

                        if not self.click_service.safe_sleep(0.15):
                            return

            self.log("自定义动作执行结束")
        finally:
            self.click_service.stop()
            self.set_ui_topmost(True)
            self.activate_ui_window()

    def run_transport_sequence(self):
        direction = self.ui.comboBox_fangxiang.currentText().strip()

        context = self.cangku_service.prepare_visual_context()
        if context and context.get("direction"):
            detected_direction = context["direction"]
            index = self.ui.comboBox_fangxiang.findText(detected_direction)
            if index >= 0:
                self.ui.comboBox_fangxiang.setCurrentIndex(index)
            direction = detected_direction

        count = self.ui.spinBox_cishu.value()

        self.set_ui_topmost(False)
        try:
            self.cangku_service.run(
                count=count,
                direction=direction,
                pos_dict=self.pos_dict,
            )
        finally:
            self.set_ui_topmost(True)
            self.activate_ui_window()

    def clear_all_positions(self):
        for key in self.pos_dict:
            self.pos_dict[key] = None

        for point in self.custom_points:
            point["x"] = None
            point["y"] = None

        self.current_locate = None
        self.current_custom_point_id = None

        self.update_text()
        self.refresh_custom_point_table()
        self.refresh_custom_action_table()

        row = self.get_selected_custom_point_row()
        if row is None:
            self.update_current_point_labels(None)
        else:
            self.update_current_point_labels(self.custom_points[row])

        self.log("已清空全部定位")

    def _collect_config_data(self):
        return {
            "window_title": self.ui.lineEdit_chuangkouming.text().strip(),
            "pos_dict": self.pos_dict,
            "custom_points": self.custom_points,
            "custom_actions": self.custom_actions,
            "custom_point_counter": self.custom_point_counter,
            "combo_direction": self.ui.comboBox_fangxiang.currentText(),
            "transport_times": self.ui.spinBox_cishu.value(),
            "transport_x": self.ui.spinBox_x.value(),
            "transport_y": self.ui.spinBox_y.value(),
            "jingduan_count": self.ui.spinBox_jingduan.value(),
            "custom_repeat": self.ui.spinBox_zidingyicishu.value(),
            "weituo_min_commission": self.ui.doubleSpinBox_zuidiyongjin.value(),
        }

    def save_config(self):
        default_path = str(Path(__file__).resolve().parent / "config.json")
        path, _ = QFileDialog.getSaveFileName(
            self.ui,
            "保存配置",
            default_path,
            "JSON Files (*.json)",
        )
        if not path:
            return

        data = self._collect_config_data()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.log(f"配置已保存：{path}")

    def load_config(self):
        default_path = str(Path(__file__).resolve().parent / "config.json")
        path, _ = QFileDialog.getOpenFileName(
            self.ui,
            "加载配置",
            default_path,
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self.ui, "加载失败", f"配置读取失败：{e}")
            self.log(f"配置读取失败：{e}")
            return

        self.ui.lineEdit_chuangkouming.setText(data.get("window_title", "Endfield"))

        loaded_pos = data.get("pos_dict", {})
        for key in self.pos_dict:
            value = loaded_pos.get(key)

            if isinstance(value, dict):
                rel = value.get("rel")
                ratio = value.get("ratio")
                self.pos_dict[key] = {
                    "rel": tuple(rel) if isinstance(rel, list) else rel,
                    "ratio": tuple(ratio) if isinstance(ratio, list) else ratio,
                }
            elif isinstance(value, list):
                # 兼容旧版 [x, y]
                self.pos_dict[key] = tuple(value)
            else:
                self.pos_dict[key] = value
        self.custom_points = []
        max_point_id = 0
        for point in data.get("custom_points", []):
            point_id = int(point.get("id", 0))
            max_point_id = max(max_point_id, point_id)
            self.custom_points.append(
                {
                    "id": point_id,
                    "name": point.get("name", "未命名点位"),
                    "x": point.get("x"),
                    "y": point.get("y"),
                }
            )

        self.custom_actions = data.get("custom_actions", [])
        saved_counter = int(data.get("custom_point_counter", 1))
        self.custom_point_counter = max(saved_counter, max_point_id + 1, 1)

        self.ui.spinBox_x.setValue(int(data.get("transport_x", 0)))
        self.ui.spinBox_y.setValue(int(data.get("transport_y", 0)))
        self.ui.spinBox_cishu.setValue(int(data.get("transport_times", 0)))
        self.ui.spinBox_jingduan.setValue(int(data.get("jingduan_count", 1)))
        self.ui.spinBox_zidingyicishu.setValue(int(data.get("custom_repeat", 1)))
        #委托
        self.ui.doubleSpinBox_zuidiyongjin.setValue(float(data.get("weituo_min_commission", 0.0)))

        combo_text = data.get("combo_direction")
        if combo_text:
            index = self.ui.comboBox_fangxiang.findText(combo_text)
            if index >= 0:
                self.ui.comboBox_fangxiang.setCurrentIndex(index)

        self.update_text()
        self.refresh_custom_point_table()
        self.refresh_custom_action_table()

        if self.custom_points:
            self.select_custom_point_by_id(self.custom_points[0]["id"])
            self.update_current_point_labels(self.custom_points[0])
        else:
            self.update_current_point_labels(None)

        self.log(f"配置已加载：{path}")


