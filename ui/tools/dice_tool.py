import random
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QMessageBox, QFrame,
    QGridLayout, QInputDialog, QWidget, QSpinBox,
    QTabWidget, QTextEdit, QListWidget, QListWidgetItem,
    QLineEdit, QGroupBox, QButtonGroup, QRadioButton,
    QScrollArea
)
from PySide6.QtCore import Qt, Signal

from models.static_data import QUALITY_ASSURANCES, HIDDEN_DICE_DB

# ==========================================
# 核心规则引擎
# 不包含任何 UI 依赖，负责规则计算与日志生成
# ==========================================
class DiceEngine:
    
    @staticmethod
    def evaluate_scenario(rolls: List[int], burn_pool: int, hidden_data: Dict[str, Any], override_6d4: bool, has_modifications: bool = False) -> Dict[str, Any]:
        """
        计算单次判定的核心逻辑（成功数、混沌、燃尽、是否升华）
        """
        burned_indices_6d4 = []
        base_successes = 0
        base_chaos = 0

        # 获取十面骰数据（判断是否失败）
        n1_data = next((d for d in hidden_data.values() if d['key'] == '10-sided'), None)
        is_fail_flag = n1_data.get('is_fail', False) if n1_data else False

        if not override_6d4:
            # 标准 6d4 判定
            for i, val in enumerate(rolls):
                if val == 3:
                    if burn_pool > 0:
                        burn_pool -= 1
                        burned_indices_6d4.append(i)
                    else:
                        base_successes += 1
            if base_successes == 3: 
                base_chaos = 0
            else: 
                base_chaos = 6 - base_successes
        else:
            # 异常能力 (十面骰) 覆盖判定
            res = n1_data['res'] if n1_data else 0
            base_successes = 0 if is_fail_flag else res
            
            # 燃尽优先消耗成功数
            cnt = min(base_successes, burn_pool)
            base_successes -= cnt
            burn_pool -= cnt
            base_chaos = res + cnt #每个被烧掉的3都会额外贡献一点混沌

        # 计算暗骰贡献
        hidden_success_contrib = 0
        hidden_chaos_contrib = 0
        hidden_tri_helpers = 0

        for code, d in hidden_data.items():
            key, res, alloc = d['key'], d['res'], d['allocation']

            if override_6d4 and key == '10-sided': 
                continue

            local_success, local_chaos = 0, 0
            
            if key == "sponsorship":
                if res % 3 == 0: local_success = res // 3
            elif key == "6-sided":
                if res % 3 == 0: local_success = res // 3
                else: local_chaos += 1
            elif key == "10-sided":
                local_success = 0 if d.get('is_fail') else res
                local_chaos += res
            
            hidden_chaos_contrib += local_chaos
            
            # 暗骰的成功数也会被燃尽消耗
            if local_success != 0 and burn_pool > 0:
                cnt = min(local_success, burn_pool)
                local_success -= cnt
                burn_pool -= cnt
                hidden_chaos_contrib += cnt

            if alloc == 1: # 计入 (+)
                hidden_success_contrib += local_success
                if d.get('can_tricendence'): hidden_tri_helpers += local_success
            elif alloc == 2: # 抵消 (-)
                hidden_success_contrib -= local_success
                if d.get('can_tricendence'): hidden_tri_helpers -= local_success

        total_successes = max(0, base_successes + hidden_success_contrib)
        base_chaos += burn_pool
        final_chaos = base_chaos + hidden_chaos_contrib
        
        # 三重升华判定：必须是第一次自然计算（未经过任何人为修改）
        is_triscendence = not n1_data and not has_modifications and ((base_successes + hidden_tri_helpers) == 3)
        if is_triscendence:
            final_chaos = 0

        return {
            "final_successes": total_successes,
            "chaos_growth": final_chaos,
            "is_fail": is_fail_flag,
            "burned_indices": burned_indices_6d4,
            "unused_burnout_val": burn_pool,
            "is_triscendence": is_triscendence
        }

    @staticmethod
    def generate_html_report(h: Dict[str, Any], current_rolls: List[int]) -> str:
        """根据记录生成用于展示的 HTML 日志"""
        if not h: return ""
        hidden_data = h.get("hidden_dice", {})
        burned_indices = set(h.get('burned_indices', []))
        is_override = h.get('is_override_mode', False)
        
        html = f"<h3>掷骰结果 - {h.get('qa_name', '未知')}</h3>"

        if is_override:
            html += "<div style='font-weight:bold; margin-bottom:5px;'>[使用异常能力]</div>"
            
        html += f"<div style='color:#666; font-size:9pt'>燃尽: {h.get('total_burnout', 0)}<br>额外燃尽{h.get('base_burnout', 0)}点 + 缺少QA{1 if h.get('missing_qa') else 0}点<br>直接转化为混沌的燃尽数量: {h.get('unused_burnout_val', 0)}</div>"
        
        if is_override:
            html += "<div style='padding: 8px; border: 1px dashed #0097A7; margin-bottom: 10px; color: #777;'><span style='text-decoration:line-through'>已忽略 6d4 掷骰结果</span></div>"
        else:
            dice_html = ""
            for i, val in enumerate(current_rolls):
                style = "font-weight:bold;"
                if i in burned_indices: style += "text-decoration:line-through; color:#C41E3A;"
                elif val == 3: style += "color:#4CAF50;"
                dice_html += f"<span style='{style}'>{val}</span> "
            html += f"<div style='font-size:14pt; margin:5px 0'>[{dice_html}]</div>"

        html += f"<div style='margin-bottom:5px;'>最终结果: <b>{h.get('final_successes', 0)}</b> 个成功</div>"

        if h.get('modifications'):
            html += "<ul>" + "".join([f"<li>{m}</li>" for m in h['modifications']]) + "</ul>"

        if h.get('triscendence_choice'):
            html += f"<div style='color:#E6B422; font-weight:bold'>✨ 三重升华: {h['triscendence_choice']}</div>"

        if hidden_data:
            html += "<div style='font-weight: bold; margin-bottom: 4px;'>暗骰详情:</div><ul style='margin: 0; padding-left: 20px;'>"
            for code, d in hidden_data.items():
                name, res, key = d['name'], d['res'], d['key']
                li_style = "font-weight:bold;" if (is_override and key == '10-sided') else ""
                name_addon = " (覆盖6d4)" if (is_override and key == '10-sided') else ""
                
                note = ""
                history_html = ""
                if d.get('mod_history'):
                    note += " <span style='color:orange; font-size:0.9em'>(已修改)</span>"
                    history_items = "".join([f"<li style='color:#666; font-size:0.9em;'>{record}</li>" for record in d['mod_history']])
                    history_html = f"<ul style='margin-top:2px; margin-bottom:5px; padding-left:15px;'>{history_items}</ul>"
                
                alloc = d.get('allocation', 1)
                if alloc == 2: note += " <span style='color:red'>[抵消]</span>"
                elif alloc == 3: note += " <span style='color:gray'>[忽略]</span>"

                html += f"<li style='{li_style}'>{name}: {res}{name_addon}{note}{history_html}</li>"
            html += "</ul>"

            if h.get('is_fail'):
                html += "<div style='color:red; font-weight:bold; margin-top:4px;'>十面骰失败</div>"
            html += "</div>"

        html += f"<hr><div>混沌增长: <b>{h.get('chaos_growth', 0)}</b></div>"
        return html


# ==========================================
# UI 组件层
# ==========================================
class DiceButton(QPushButton):
    def __init__(self, index: int, value: int = 0, is_burned: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(50, 50)
        self.update_state(value, is_burned)
        
    def update_state(self, value: int, is_burned: bool = False):
        self.value = value
        self.is_burned = is_burned
        self.setText(str(value) if value > 0 else "?")

        base_style = "border-radius: 5px; font-size: 18pt; font-weight: bold; border: 2px solid #555;"

        if is_burned:
            style = f"{base_style} background-color: #555; color: #AAA; text-decoration: line-through; border-color: #333;"
            self.setToolTip(f"点数 {value} (已被燃尽烧毁)")
        elif value == 3:
            style = f"{base_style} background-color: #4CAF50; color: #FFF; border-color: #388E3C;"
            self.setToolTip("成功")
        elif value == 0:
            style = f"{base_style} background-color: #EEE; color: #BBB;"
        else:
            style = f"{base_style} background-color: #FFF; color: #333;"
            self.setToolTip("点击消耗QA修改为3")

        self.setStyleSheet(f"QPushButton {{ {style} }}")


class HiddenDiceConfigDialog(QDialog):
    def __init__(self, current_unlocked: List[str], current_enabled: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("配置暗骰")
        self.resize(400, 500)
        self.unlocked = set(current_unlocked) 
        self.enabled = set(current_enabled)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        input_group = QGroupBox("解锁新暗骰")
        ig_layout = QHBoxLayout(input_group)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("输入受限文档代码...")
        self.code_input.returnPressed.connect(self.try_unlock)

        self.unlock_btn = QPushButton("解锁")
        self.unlock_btn.setAutoDefault(False)
        self.unlock_btn.setDefault(False)
        self.unlock_btn.clicked.connect(self.try_unlock)
        
        ig_layout.addWidget(self.code_input)
        ig_layout.addWidget(self.unlock_btn)
        layout.addWidget(input_group)

        layout.addWidget(QLabel("已解锁的暗骰 (右键查看详情):"))
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.refresh_list()
        layout.addWidget(self.list_widget)

        btn_box = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True) 
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def try_unlock(self):
        code = self.code_input.text().strip().upper()
        if not code: return
        
        if code in HIDDEN_DICE_DB:
            if code not in self.unlocked:
                self.unlocked.add(code)
                self.enabled.add(code)
                self.refresh_list()
                QMessageBox.information(self, "访问许可", f"暗骰 [{HIDDEN_DICE_DB[code]['name']}] 已解锁")
                self.code_input.clear()
            else:
                QMessageBox.information(self, "提示", "该内容已解锁")
        else:
            QMessageBox.warning(self, "拒绝访问", "无效的代码")

    def refresh_list(self):
        self.list_widget.clear()
        for code in self.unlocked:
            data = HIDDEN_DICE_DB[code]
            item = QListWidgetItem(f"{data['name']}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if code in self.enabled else Qt.Unchecked)
            item.setData(Qt.UserRole, code)
            self.list_widget.addItem(item)

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item:
            code = item.data(Qt.UserRole)
            info = HIDDEN_DICE_DB.get(code)
            if info:
                box = QMessageBox(self)
                box.setAttribute(Qt.WA_DeleteOnClose)
                box.setWindowTitle(info['name'])
                box.setText(f"【此为原说明的简化版，具体请见规则书】\n\n{info['desc']}")
                box.setStandardButtons(QMessageBox.Ok)
                box.open()

    def get_results(self) -> Tuple[List[str], List[str]]:
        final_enabled = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                final_enabled.append(item.data(Qt.UserRole))
        return list(self.unlocked), final_enabled


class HiddenDiceWindow(QDialog):
    data_confirmed = Signal(dict)
    
    def __init__(self, selected_codes: List[str], char_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)  # 修复内存泄漏
        self.setWindowTitle("暗骰结果")
        self.resize(600, 500)

        self.selected_codes = selected_codes
        self.char_data = char_data
        self.dice_states = {} 
        
        self._initial_roll()
        self.init_ui()

    def _initial_roll(self):
        for code in self.selected_codes:
            info = HIDDEN_DICE_DB.get(code, {})
            key = info.get('key', 'unknown')
            name = info.get('name', '未知暗骰')

            state = {
                "key": key, "name": name, "res": 0,
                "can_tricendence": False, "manual_allocation": False,
                "allocation": 1, "is_fail": False, "mod_history": []
            }

            if key == "sponsorship":
                state["res"] = random.randint(1, 8)
                state["can_tricendence"] = True
                state["manual_allocation"] = True
            elif key == "10-sided": 
                state["res"] = random.randint(1, 10)
                if state["res"] == 3: state["is_fail"] = True
            elif key == "6-sided": 
                state["res"] = random.randint(1, 6)
                state["can_tricendence"] = True

            self.dice_states[code] = state

    def init_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        
        for code, data in self.dice_states.items():
            self.list_layout.addWidget(self._create_row(code, data))
            
        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_box = QHBoxLayout()
        calc_btn = QPushButton("确认并计算结果")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("font-weight: bold; font-size: 11pt;")
        calc_btn.clicked.connect(self.on_confirm_clicked)
        btn_box.addWidget(calc_btn)
        layout.addLayout(btn_box)

    def _create_row(self, code: str, data: Dict[str, Any]) -> QGroupBox:
        group = QGroupBox(data['name'])
        g_layout = QVBoxLayout(group)

        row_top = QHBoxLayout()
        res_lbl = QLabel(f"结果: <b style='font-size:16pt; color:#1976D2'>{data['res']}</b>")
        data['widget_res_lbl'] = res_lbl 
        row_top.addWidget(res_lbl)
        row_top.addStretch()
        
        dice_type = data['key']
        if dice_type == "10-sided":
            btn_minus, btn_plus = QPushButton("-1"), QPushButton("+1")
            btn_minus.setFixedSize(40, 30); btn_plus.setFixedSize(40, 30)
            btn_minus.clicked.connect(lambda _, c=code: self.modify_d10(c, -1))
            btn_plus.clicked.connect(lambda _, c=code: self.modify_d10(c, 1))
            row_top.addWidget(QLabel("修改(1QA/3处分):"))
            row_top.addWidget(btn_minus); row_top.addWidget(btn_plus)

        elif dice_type == "6-sided":
            spin = QSpinBox()
            spin.setRange(1, 6)
            spin.setValue(data['res'])
            btn_set = QPushButton("修改")
            btn_set.clicked.connect(lambda _, c=code, s=spin: self.modify_d6(c, s.value()))
            row_top.addWidget(QLabel("指定(1QA/3处分):"))
            row_top.addWidget(spin); row_top.addWidget(btn_set)

        g_layout.addLayout(row_top)

        row_bot = QHBoxLayout()
        if data['manual_allocation']:
            row_bot.addWidget(QLabel("生效方式:"))
            bg = QButtonGroup(group)
            r1, r2, r3 = QRadioButton("计入 (+)"), QRadioButton("抵消 (-)"), QRadioButton("忽略 (0)")
            bg.addButton(r1, 1); bg.addButton(r2, 2); bg.addButton(r3, 3)
            
            if data['allocation'] == 1: r1.setChecked(True)
            elif data['allocation'] == 2: r2.setChecked(True)
            else: r3.setChecked(True)
            
            bg.idClicked.connect(lambda val, c=code: self.update_allocation(c, val))
            row_bot.addWidget(r1); row_bot.addWidget(r2); row_bot.addWidget(r3)
        else:
            info_txt = "投到三为失败" if data['key'] == '10-sided' else "投到三的倍数为成功"
            row_bot.addWidget(QLabel(f"<span style='color:gray'>{info_txt}</span>"))
            
        row_bot.addStretch()
        g_layout.addLayout(row_bot)
        return group

    def try_pay_cost(self) -> bool:
        if not self.char_data: return False

        qa_data = self.char_data.get("quality_assurances", {})
        current_demerits = self.char_data.get("demerits", 0)
        available_qas = [k for k, v in qa_data.items() if v.get("current", 0) > 0]

        options = []
        if available_qas: options.append("消耗 1 点 QA")
        if current_demerits >= 3: options.append(f"消耗 3 点处分 (当前: {current_demerits})")
        
        item, ok = QInputDialog.getItem(self, "修改暗骰结果", "选择修改方式:", options, 0, False)
        if not ok: return False
            
        if "QA" in item:
            qa_names = [QUALITY_ASSURANCES[k] for k in available_qas]
            q_item, q_ok = QInputDialog.getItem(self, "选择 QA", "扣除哪个 QA?", qa_names, 0, False)
            if q_ok:
                target_key = next(k for k in available_qas if QUALITY_ASSURANCES[k] == q_item)
                qa_data[target_key]['current'] -= 1
                return True
        else:
            self.char_data["demerits"] = current_demerits - 3
            return True
        return False

    def modify_d10(self, code: str, delta: int):
        data = self.dice_states[code]
        new_val = data['res'] + delta
        if not (1 <= new_val <= 10):
            QMessageBox.warning(self, "无效", "点数超出范围 (1-10)")
            return
            
        if self.try_pay_cost():
            data['res'] = new_val
            data['is_fail'] = (new_val == 3)
            op_str = "+1" if delta > 0 else "-1"
            data['mod_history'].append(f"十面骰点数{op_str}")
            self.refresh_ui_value(data)

    def modify_d6(self, code: str, target_val: int):
        data = self.dice_states[code]
        if target_val == data['res']: return

        if self.try_pay_cost():
            data['res'] = target_val
            data['mod_history'].append(f"修改六面骰的点数为{target_val}")
            self.refresh_ui_value(data)

    def refresh_ui_value(self, data: Dict[str, Any]):
        lbl = data.get('widget_res_lbl')
        if lbl: lbl.setText(f"结果: <b style='font-size:16pt; color:#4CAF50'>{data['res']}</b> (已修改)")

    def update_allocation(self, code: str, val: int):
        self.dice_states[code]['allocation'] = val
    
    def on_confirm_clicked(self):
        self.data_confirmed.emit(self.dice_states)
        self.close()


class QADistributionDialog(QDialog):
    def __init__(self, qa_data: Dict[str, Any], total_points: int = 3, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.qa_data = qa_data
        self.total_points = total_points
        self.spinboxes = {}
        self.setWindowTitle(f"回复 QA (可用点数: {total_points})")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"请分配 {self.total_points} 点数到下列 QA 中："))
        
        grid = QGridLayout()
        for row, (key, name) in enumerate(QUALITY_ASSURANCES.items()):
            current = self.qa_data.get(key, {}).get("current", 0)
            max_val = self.qa_data.get(key, {}).get("max", 0)
            grid.addWidget(QLabel(f"{name} ({current}/{max_val})"), row, 0)
            
            spin = QSpinBox()
            spin.setRange(0, self.total_points)
            can_add = max_val - current
            spin.setEnabled(can_add > 0)
            if can_add > 0: spin.setMaximum(min(self.total_points, can_add))
            
            spin.valueChanged.connect(self.update_limits)
            self.spinboxes[key] = spin
            grid.addWidget(spin, row, 1)
            
        layout.addLayout(grid)
        self.remaining_label = QLabel(f"剩余点数: {self.total_points}")
        layout.addWidget(self.remaining_label)
        
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)
        self.update_limits()

    def update_limits(self):
        used = sum(spin.value() for spin in self.spinboxes.values())
        rem = self.total_points - used
        self.remaining_label.setText(f"剩余点数: {rem}")
        if rem < 0:
            self.remaining_label.setText(f"超额分配{-rem}点")
            self.remaining_label.setStyleSheet("color: red; font-weight: bold;")
            self.btn_ok.setEnabled(False)
        else:
            self.remaining_label.setStyleSheet("color: green; font-weight: bold;")
            self.btn_ok.setEnabled(True)

    def get_distribution(self) -> Dict[str, int]:
        return {k: s.value() for k, s in self.spinboxes.items() if s.value() > 0}


# ==========================================
# 主窗口控制层
# ==========================================
class DiceTool(QDialog):
    dataChanged = Signal()
    log_signal = Signal(str)
    chaosSignal = Signal(int)

    def __init__(self, game_name: str, character_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose) # 修复内存泄漏
        
        self.game_name = game_name
        self.data = character_data if character_data else {}
        self.setWindowTitle("掷骰工具")
        self.resize(550, 750)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.current_rolls = [0] * 6
        self.is_triscendence = False 
        self.pending_log = False
        self.roll_history = {}

        dice_conf = self.load_dice_config()
        self.unlocked_hidden_codes = list(set(dice_conf.get("unlocked", [])))
        self.enabled_hidden_codes = list(set(dice_conf.get("enabled", [])))
        self.current_hidden_window = None
        
        self.init_ui()

    def get_config_path(self) -> Path:
        return Path("data") / "PL" / self.game_name / "hidden_dice.json"

    def load_dice_config(self) -> Dict[str, Any]:
        path = self.get_config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_dice_config(self, config_data: Dict[str, Any]):
        path = self.get_config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.agency_tab = QWidget()
        self.init_agency_tab(self.agency_tab)
        tab1_name = "机构掷骰" if self.data else "机构掷骰 (无角色数据)"
        self.tabs.addTab(self.agency_tab, tab1_name)

        self.custom_tab = QWidget()
        self.init_custom_tab(self.custom_tab)
        self.tabs.addTab(self.custom_tab, "自定义掷骰")

        if not self.data:
            self.tabs.setCurrentIndex(1)

    def init_agency_tab(self, parent_widget: QWidget):
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        cfg_layout = QHBoxLayout()
        cfg_layout.addStretch()
        self.hidden_cfg_btn = QPushButton("配置暗骰")
        self.hidden_cfg_btn.clicked.connect(self.open_hidden_config)
        cfg_layout.addWidget(self.hidden_cfg_btn)
        layout.addLayout(cfg_layout)

        self._init_settings(layout)
        self._init_dice(layout)
        self._init_results(layout)

        self.hidden_list_frame = QFrame()
        self.hidden_list_frame.setVisible(False)
        hl_layout = QVBoxLayout(self.hidden_list_frame)
        hl_layout.addWidget(QLabel("<b>特殊暗骰 (勾选以在掷骰时生效):</b>"))
        
        self.hidden_list = QListWidget()
        self.hidden_list.setFixedHeight(100)
        self.hidden_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hidden_list.customContextMenuRequested.connect(self.show_hidden_context_menu)
        hl_layout.addWidget(self.hidden_list)
        layout.addWidget(self.hidden_list_frame)
        
        self.refresh_hidden_area()
        self.update_burnout_display()
    
    def show_hidden_context_menu(self, pos):
        item = self.hidden_list.itemAt(pos)
        if not item: return
        code = item.data(Qt.UserRole)
        info = HIDDEN_DICE_DB.get(code)
        if info:
            box = QMessageBox(self)
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.setWindowTitle(info['name'])
            box.setText(f"【此为原说明的简化版，具体请见规则书】\n\n{info['desc']}")
            box.setStandardButtons(QMessageBox.Ok)
            #避免使用QMessageBox.information()，因其内部用的是exec
            box.open() #open() 是非阻塞的，不会启动嵌套事件循环导致外层UI卡死

    def open_hidden_config(self):
        dlg = HiddenDiceConfigDialog(self.unlocked_hidden_codes, self.enabled_hidden_codes, self)
        if dlg.exec() == QDialog.Accepted:
            self.unlocked_hidden_codes, self.enabled_hidden_codes = dlg.get_results()
            self.save_dice_config({
                "unlocked": self.unlocked_hidden_codes,
                "enabled": self.enabled_hidden_codes
            })
            self.refresh_hidden_area()
        self.activateWindow()
    
    def refresh_hidden_area(self):
        self.hidden_list.clear()
        if not self.enabled_hidden_codes:
            self.hidden_list_frame.setVisible(False)
            return
            
        self.hidden_list_frame.setVisible(True)
        for code in self.enabled_hidden_codes:
            info = HIDDEN_DICE_DB.get(code)
            if not info: continue
            item = QListWidgetItem(f"🎲 {info['name']}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, code)
            self.hidden_list.addItem(item)
    
    def _init_results(self, parent_layout: QVBoxLayout):
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet("border: 1px solid #CCCCCC; border-radius: 8px; background-color: #FAFAFA;")
        self.result_frame.setVisible(False) 
        vbox = QVBoxLayout(self.result_frame)

        self.mode_switcher_frame = QFrame()
        self.mode_switcher_frame.setVisible(False)
        ms_layout = QHBoxLayout(self.mode_switcher_frame)
        ms_layout.addWidget(QLabel("十面骰使用场景:", styleSheet="font-weight:bold; color:#006064;"))
        self.mode_group = QButtonGroup(self)
        self.rb_addon = QRadioButton("其他")
        self.rb_override = QRadioButton("异常能力")
        self.rb_addon.setStyleSheet("QRadioButton { color: black; }")
        self.rb_override.setStyleSheet("QRadioButton { color: black; }")
        self.rb_override.setChecked(True)
        
        self.mode_group.addButton(self.rb_override, 1)
        self.mode_group.addButton(self.rb_addon, 2)
        self.mode_group.idClicked.connect(self.refresh_display_from_cache)
        
        ms_layout.addWidget(self.rb_addon); ms_layout.addWidget(self.rb_override)
        ms_layout.addStretch()
        vbox.addWidget(self.mode_switcher_frame)
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.status_label)
        
        self.chaos_label = QLabel()
        self.chaos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chaos_label.setStyleSheet("font-size: 14pt; color: #555555;")
        vbox.addWidget(self.chaos_label)

        self.details_btn = QPushButton("查看详情")
        self.details_btn.setStyleSheet("""
            QPushButton { color: #555; background: transparent; border: 1px solid #AAA; 
                          border-radius: 15px; padding: 5px 15px; font-size: 10pt; }
            QPushButton:hover { background: #EEE; color: #000; }
        """)
        self.details_btn.clicked.connect(lambda: QMessageBox.information(self, "详情", DiceEngine.generate_html_report(self.roll_history, self.current_rolls)))
        vbox.addWidget(self.details_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.triscendence_widget = QWidget()
        tri_layout = QVBoxLayout(self.triscendence_widget)
        tri_layout.addWidget(QLabel("三重升华!", styleSheet="color:#E6B422; font-weight:bold; font-size:16pt;"), 0, Qt.AlignmentFlag.AlignCenter)
        tri_layout.addWidget(QLabel("请选择一项奖励:", styleSheet="color: #333333;", alignment=Qt.AlignmentFlag.AlignCenter))

        for label, code in [("增加 3 的数量 (叙事)", "more_3"), ("回复 3 点 QA", "restore_qa"), ("获得 3 点嘉奖", "commendation")]:
            btn = QPushButton(label)
            btn.setStyleSheet("color: #333; background: #FFF; border: 1px solid #CCC; padding: 5px;")
            btn.clicked.connect(lambda _, c=code: self.apply_triscendence(c))
            tri_layout.addWidget(btn)
        
        self.triscendence_widget.setVisible(False)
        vbox.addWidget(self.triscendence_widget)
        
        parent_layout.addWidget(self.result_frame)
        parent_layout.addStretch()

    def _init_dice(self, parent_layout: QVBoxLayout):
        dice_frame = QFrame()
        dice_layout = QHBoxLayout(dice_frame)
        self.dice_buttons = []
        for i in range(6):
            btn = DiceButton(i)
            btn.clicked.connect(lambda _, idx=i: self.on_die_clicked(idx))
            dice_layout.addWidget(btn)
            self.dice_buttons.append(btn)
        parent_layout.addWidget(dice_frame)

        self.roll_btn = QPushButton("掷 骰")
        self.roll_btn.setMinimumHeight(50)
        self.roll_btn.setStyleSheet("QPushButton { background-color: #0055AA; color: white; font-size: 16pt; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #0066CC; }")
        self.roll_btn.clicked.connect(self.roll_dice)
        parent_layout.addWidget(self.roll_btn)
    
    def _init_settings(self, parent_layout: QVBoxLayout):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #F5F5F5; border-radius: 8px; } QLabel { color: #333333; font-size: 11pt; }")
        grid = QGridLayout(frame)
        
        self.burnout_label = QLabel("下次掷骰时的燃尽: 0")
        self.burnout_label.setStyleSheet("color: #C41E3A; font-weight: bold; font-size: 12pt;")
        grid.addWidget(self.burnout_label, 1, 0, 1, 2)
        
        grid.addWidget(QLabel("检定素质 (QA):"), 0, 0)
        self.qa_combo = QComboBox()
        self.qa_combo.setStyleSheet("color: #333333; background: white;")
        self.qa_keys = list(QUALITY_ASSURANCES.keys())
        self.refresh_qa_combo()
        self.qa_combo.currentIndexChanged.connect(self.update_burnout_display)
        grid.addWidget(self.qa_combo, 0, 1)
        parent_layout.addWidget(frame)

    def refresh_qa_combo(self):
        cur_idx = self.qa_combo.currentIndex()
        self.qa_combo.blockSignals(True)
        self.qa_combo.clear()
        qa = self.data.get("quality_assurances", {})
        for k in self.qa_keys:
            d = qa.get(k, {})
            self.qa_combo.addItem(f"{QUALITY_ASSURANCES[k]} ({d.get('current',0)}/{d.get('max',0)})")
        if cur_idx >= 0: self.qa_combo.setCurrentIndex(cur_idx)
        self.qa_combo.blockSignals(False)
        self.update_burnout_display()
    
    def get_current_qa(self) -> Tuple[Optional[str], int]:
        idx = self.qa_combo.currentIndex()
        if idx < 0: return None, 0
        key = self.qa_keys[idx]
        val = self.data.get("quality_assurances", {}).get(key, {}).get("current", 0)
        return key, val

    def update_burnout_display(self):
        key, val = self.get_current_qa()
        base = self.data.get("additional_burnout", 0)
        extra = 1 if val <= 0 else 0
        txt = f"下次掷骰时的燃尽: {base + extra}"
        if extra: txt += f" (缺少素质【{QUALITY_ASSURANCES[key]}】)"
        self.burnout_label.setText(txt)

    def refresh_ui_dice(self, burned_indices: List[int], enabled: bool = True):
        for i, btn in enumerate(self.dice_buttons):
            val = self.current_rolls[i]
            btn.update_state(val, is_burned=(i in burned_indices))
            btn.setEnabled(enabled)
            if not enabled:
                btn.setStyleSheet("background-color: #EEE; color: #AAA; border: 1px dashed #CCC;")

    def roll_dice(self):
        self.commit_log()
        self.current_rolls = [random.randint(1, 4) for _ in range(6)]
        
        key, val = self.get_current_qa()
        base_burn = self.data.get("additional_burnout", 0)
        has_qa = val > 0
        total_burn = base_burn + (1 if not has_qa else 0)
        
        self.roll_history = {
            "qa_name": QUALITY_ASSURANCES.get(key, "未知"),
            "base_burnout": base_burn,
            "missing_qa": not has_qa,
            "total_burnout": total_burn,
            "burned_indices": [],
            "modifications": [],
            "triscendence_choice": None,
            "chaos_growth": 0
        }
        self.pending_log = True

        selected_codes = [self.hidden_list.item(i).data(Qt.UserRole) 
                          for i in range(self.hidden_list.count()) if self.hidden_list.item(i).checkState() == Qt.Checked]
        
        if selected_codes:
            if self.current_hidden_window: self.current_hidden_window.close()
            self.current_hidden_window = HiddenDiceWindow(selected_codes, self.data, self)
            self.current_hidden_window.data_confirmed.connect(self.finalize_with_hidden_dice)
            self.current_hidden_window.show()
        
        #计算并显示结果，允许玩家根据结果调整暗骰的值
        self.calculate_result()
        self.result_frame.setVisible(True)
    
    def finalize_with_hidden_dice(self, hidden_data: Dict[str, Any]):
        self.roll_history["hidden_dice"] = hidden_data
        self.refresh_qa_combo()
        self.dataChanged.emit()
        self.calculate_result()
        self.current_hidden_window = None
        self.result_frame.setVisible(True)

    def calculate_result(self):
        h = self.roll_history
        hidden_data = h.get("hidden_dice", {})
        has_n1 = any(d['key'] == '10-sided' for d in hidden_data.values())
        has_mods = len(h.get("modifications", [])) > 0 or any(len(d.get("mod_history", [])) > 0 for d in hidden_data.values())
        
        # 依赖 DiceEngine 核心计算
        self.scenario_addon = DiceEngine.evaluate_scenario(self.current_rolls, h['total_burnout'], hidden_data, False, has_mods)
        self.scenario_override = DiceEngine.evaluate_scenario(self.current_rolls, h['total_burnout'], hidden_data, True, has_mods) if has_n1 else None

        if has_n1:
            self.mode_switcher_frame.setVisible(True)
            if not self.mode_group.checkedButton(): self.rb_override.setChecked(True)
        else:
            self.mode_switcher_frame.setVisible(False)
            self.rb_addon.setChecked(True)

        self.refresh_display_from_cache()

    def refresh_display_from_cache(self, _=None):
        is_override = self.rb_override.isChecked() and self.scenario_override is not None
        result = self.scenario_override if is_override else self.scenario_addon

        self.roll_history.update(result)
        self.roll_history['is_override_mode'] = is_override

        ui_burned = [] if is_override else result['burned_indices']
        self.refresh_ui_dice(ui_burned, enabled=not is_override)

        self.is_triscendence = result['is_triscendence']
        
        status_text, status_style = "", ""
        if result['is_fail']:
            status_text = "十面骰失败"
            status_style = "color: red; font-weight:900;"
        elif self.is_triscendence:
            status_text = f"成功 ({result['final_successes']}) - 三重升华!"
            status_style = "color: #E6B422;"
        elif result['final_successes'] > 0:
            status_text = f"成功 ({result['final_successes']})"
            status_style = "color: #4CAF50;"
        else:
            status_text = "失败"
            status_style = "color: #C41E3A;"
            
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"font-size: 18pt; font-weight: bold; {status_style}")
        self.chaos_label.setText(f"混沌增长: {result['chaos_growth']}")
        self.triscendence_widget.setVisible(self.is_triscendence)

    def on_die_clicked(self, index: int):
        if not self.data: return
        val = self.current_rolls[index]
        if (val == 3 and not self.dice_buttons[index].is_burned) or self.dice_buttons[index].value == 0: return

        qa_data = self.data.get("quality_assurances", {})
        available_qas = [k for k in self.qa_keys if qa_data.get(k, {}).get("current", 0) > 0]
        
        if not available_qas:
            QMessageBox.warning(self, "无法修改", "你没有可用的QA")
            return
            
        item, ok = QInputDialog.getItem(self, "消耗 QA", "选择要消耗的素质保障来将此骰子改为3:", [QUALITY_ASSURANCES[k] for k in available_qas], 0, False)
        if ok and item:
            selected_key = next(k for k in available_qas if QUALITY_ASSURANCES[k] == item)
            qa_data[selected_key]['current'] -= 1
            self.refresh_qa_combo()
            self.dataChanged.emit()
            
            self.current_rolls[index] = 3
            if self.dice_buttons[index].is_burned: self.roll_history['burned_indices'].remove(index)
            self.dice_buttons[index].update_state(3, False)
            self.roll_history["modifications"].append(f"消耗 {item} 将第{index+1}枚骰子改为3")
            self.calculate_result()

    def apply_triscendence(self, effect_type: str):
        if effect_type == "more_3":
            self.roll_history["triscendence_choice"] = "增加3的数量(叙事效果)"
            QMessageBox.information(self, "叙事", "此为叙事效果")
        elif effect_type == "restore_qa":
            qa_data = self.data.get("quality_assurances", {})
            #Qt.WA_DeleteOnClose不应该用在需要后续获取资源的dialog上。python GC会自行处理
            dlg = QADistributionDialog(qa_data, total_points=3, parent=self)
            if dlg.exec():
                distribution = dlg.get_distribution()
                for key, added_val in distribution.items(): qa_data[key]['current'] += added_val
                self.refresh_qa_combo()
                self.dataChanged.emit()
                QMessageBox.information(self, "成功", "QA点数已回复")
                info = ", ".join([f"{QUALITY_ASSURANCES[k]}+{v}" for k, v in distribution.items()])
                self.roll_history["triscendence_choice"] = f"回复QA ({info})"
            else: return
        elif effect_type == "commendation":
            self.data['commendations'] = self.data.get('commendations', 0) + 3
            self.dataChanged.emit()
            self.roll_history["triscendence_choice"] = "获得3点嘉奖"
            QMessageBox.information(self, "成功", "已获得3点嘉奖")
            
        self.triscendence_widget.setVisible(False)
    
    def commit_log(self):
        if self.pending_log:
            html = DiceEngine.generate_html_report(self.roll_history, self.current_rolls)
            self.log_signal.emit(html)
            growth = self.roll_history.get("chaos_growth", 0)
            if growth != 0: self.chaosSignal.emit(growth)
            self.pending_log = False
            self.roll_history = {}
    
    # ---------- 自定义掷骰相关代码 ----------
    
    def init_custom_tab(self, parent_widget: QWidget):
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        quick_layout = QGridLayout()
        quick_dice = [(4, "d4"), (6, "d6"), (8, "d8"), (10, "d10"), (12, "d12"), (20, "d20"), (100, "d100")]
        
        layout.addWidget(QLabel("快速投掷:"))
        row, col = 0, 0
        for faces, label in quick_dice:
            btn = QPushButton(label)
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda _, f=faces: self.set_custom_dice(1, f))
            quick_layout.addWidget(btn, row, col)
            col += 1
            if col > 3: col, row = 0, row + 1
        layout.addLayout(quick_layout)
        
        layout.addSpacing(10)
        layout.addWidget(QFrame(frameShape=QFrame.HLine))
        layout.addSpacing(10)

        custom_form = QHBoxLayout()
        self.custom_count = QSpinBox()
        self.custom_count.setRange(1, 100); self.custom_count.setValue(1)
        self.custom_count.setPrefix("数量: "); self.custom_count.setStyleSheet("font-size: 12pt;")
        
        self.custom_faces = QSpinBox()
        self.custom_faces.setRange(2, 1000); self.custom_faces.setValue(20)
        self.custom_faces.setPrefix("面数: d"); self.custom_faces.setStyleSheet("font-size: 12pt;")
        
        custom_form.addWidget(self.custom_count); custom_form.addWidget(self.custom_faces)
        layout.addLayout(custom_form)

        self.custom_roll_btn = QPushButton("投掷自定义骰子")
        self.custom_roll_btn.setMinimumHeight(50)
        self.custom_roll_btn.setStyleSheet("background-color: #6A1B9A; color: white; font-weight: bold; font-size: 14pt; border-radius: 8px;")
        self.custom_roll_btn.clicked.connect(self.roll_custom)
        layout.addWidget(self.custom_roll_btn)

        layout.addWidget(QLabel("结果预览:"))
        self.custom_result_display = QTextEdit()
        self.custom_result_display.setReadOnly(True)
        self.custom_result_display.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.custom_result_display)

        self.custom_send_btn = QPushButton("发送结果到个人日志")
        self.custom_send_btn.setMinimumHeight(40)
        self.custom_send_btn.setEnabled(False)
        self.custom_send_btn.clicked.connect(self.send_custom_log)
        layout.addWidget(self.custom_send_btn)

    def set_custom_dice(self, count: int, faces: int):
        self.custom_count.setValue(count)
        self.custom_faces.setValue(faces)
        self.roll_custom()

    def roll_custom(self):
        count, faces = self.custom_count.value(), self.custom_faces.value()
        rolls = [random.randint(1, faces) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(map(str, rolls))
        
        self.custom_last_html = f"<div style='font-size: 1.1em;'>投掷 <b>{count}d{faces}</b>:<br>结果: [{rolls_str}]<br><hr>总计: <b style='font-size:1.4em;'>{total}</b></div>"
        self.custom_result_display.setHtml(self.custom_last_html)
        self.custom_send_btn.setEnabled(True)
        self.custom_send_btn.setText("发送结果到个人日志")
        
    def send_custom_log(self):
        if hasattr(self, 'custom_last_html'):
            self.log_signal.emit(self.custom_last_html)
            self.custom_send_btn.setText("已发送")
            self.custom_send_btn.setEnabled(False)
    
    def closeEvent(self, event):
        self.commit_log()
        super().closeEvent(event)