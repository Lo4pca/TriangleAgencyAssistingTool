import random
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QMessageBox, QFrame,
    QGridLayout, QInputDialog, QWidget, QSpinBox
)
from PySide6.QtCore import Qt, Signal

from models.static_data import QUALITY_ASSURANCES

class DiceButton(QPushButton):
    def __init__(self, index, value=0, is_burned=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(50, 50)
        self.update_state(value, is_burned)
        
    def update_state(self, value, is_burned=False):
        self.value = value
        self.is_burned = is_burned
        self.setText(str(value) if value > 0 else "?")

        base_style = """
            border-radius: 5px; font-size: 18pt; font-weight: bold; border: 2px solid #555;
        """

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

class QADistributionDialog(QDialog):
    def __init__(self, qa_data, total_points=3, parent=None):
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
            if can_add > 0:
                spin.setMaximum(min(self.total_points, can_add))
            
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

    def get_distribution(self):
        return {k: s.value() for k, s in self.spinboxes.items() if s.value() > 0}

class DiceTool(QDialog):
    dataChanged = Signal()
    log_signal = Signal(str)
    chaosSignal = Signal(int)

    def __init__(self, game_name, character_data, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.data = character_data
        self.setWindowTitle("掷骰工具")
        self.resize(500, 700)
        
        self.current_rolls = [0] * 6
        self.unused_burnout = 0
        self.is_triscendence = False 

        self.pending_log = False
        self.roll_history = {}
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self._init_settings(layout)
        self._init_dice(layout)
        self._init_results(layout)

        self.update_burnout_display()

    def _init_results(self, parent_layout):
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet("border: 1px solid #CCCCCC; border-radius: 8px; background-color: #FAFAFA;")
        self.result_frame.setVisible(False) 
        vbox = QVBoxLayout(self.result_frame)
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 18pt; font-weight: bold;") 
        vbox.addWidget(self.status_label)
        
        self.chaos_label = QLabel()
        self.chaos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chaos_label.setStyleSheet("font-size: 14pt; color: #555555;")
        vbox.addWidget(self.chaos_label)

        self.details_btn = QPushButton("查看详情")
        self.details_btn.setStyleSheet("""
            QPushButton {
                color: #555; background: transparent; border: 1px solid #AAA; 
                border-radius: 15px; padding: 5px 15px; font-size: 10pt;
            }
            QPushButton:hover { background: #EEE; color: #000; }
        """)
        self.details_btn.clicked.connect(self.show_details)
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
        
        vbox.addWidget(self.triscendence_widget)
        
        parent_layout.addWidget(self.result_frame)
        parent_layout.addStretch()

    def _init_dice(self, parent_layout):
        dice_frame = QFrame()
        dice_layout = QHBoxLayout(dice_frame)
        dice_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dice_buttons = []
        for i in range(6):
            btn = DiceButton(i)
            btn.clicked.connect(lambda _, idx=i: self.on_die_clicked(idx))
            dice_layout.addWidget(btn)
            self.dice_buttons.append(btn)
        parent_layout.addWidget(dice_frame)

        self.roll_btn = QPushButton("掷 骰 (6d4)")
        self.roll_btn.setMinimumHeight(50)
        self.roll_btn.setStyleSheet("""
            QPushButton {
                background-color: #0055AA; color: white; 
                font-size: 16pt; font-weight: bold; border-radius: 8px;
            }
            QPushButton:hover { background-color: #0066CC; }
        """)
        self.roll_btn.clicked.connect(self.roll_dice)
        parent_layout.addWidget(self.roll_btn)
    
    def _init_settings(self, parent_layout):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background-color: #F5F5F5; border-radius: 8px; }
            QLabel { color: #333333; font-size: 11pt; }
        """)
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
    
    def get_current_qa(self):
        idx = self.qa_combo.currentIndex()
        if idx < 0: return None, 0
        key = self.qa_keys[idx]
        val = self.data.get("quality_assurances", {}).get(key, {}).get("current", 0)
        return key, val

    def update_burnout_display(self):
        key,val=self.get_current_qa()
        base = self.data.get("additional_burnout", 0)
        extra = 1 if val <= 0 else 0
        self.burnout_label.setText(f"下次掷骰时的燃尽: {base + extra} {'(缺少素质【'+QUALITY_ASSURANCES[key]+'】)' if extra else ''}")

    def refresh_ui_dice(self, burned_indices):
        for i, btn in enumerate(self.dice_buttons):
            val = self.current_rolls[i]
            is_burned = i in burned_indices
            btn.update_state(val, is_burned)

    def roll_dice(self):
        self.commit_log()
        
        key, val = self.get_current_qa()
        base_burn = self.data.get("additional_burnout", 0)
        has_qa = val > 0
        total_burn = base_burn + (1 if not has_qa else 0)

        self.current_rolls = [random.randint(1, 4) for _ in range(6)]
        
        threes_indices = [i for i, x in enumerate(self.current_rolls) if x == 3]
        total_threes = len(threes_indices)
        self.is_triscendence = (total_threes == 3)

        burned_indices = set()
        if not self.is_triscendence:
            num_to_burn = min(total_threes, total_burn)
            for i in range(num_to_burn):
                burned_indices.add(threes_indices[i])
        self.unused_burnout=total_burn-len(burned_indices)
        
        self.roll_history = {
            "qa_name": QUALITY_ASSURANCES.get(key, "未知"),
            "base_burnout": base_burn,
            "missing_qa": not has_qa,
            "total_burnout": total_burn,
            "burned_indices": list(burned_indices),
            "modifications": [],
            "triscendence_choice": None,
            "chaos_growth": 0
        }
        self.pending_log = True

        self.refresh_ui_dice(burned_indices)
        self.calculate_result()

    def calculate_result(self):
        burned_set = set(self.roll_history["burned_indices"])
        effective_threes = 0
        for i, val in enumerate(self.current_rolls):
            if val == 3 and i not in burned_set:
                effective_threes += 1

        is_success = effective_threes > 0

        if self.is_triscendence:
            chaos_growth = 0
            status_text = f"成功 ({effective_threes}) - 三重升华!"
            status_style = "color: #E6B422;"
        elif is_success:
            chaos_growth = 0 if effective_threes==3 else (6 - effective_threes) + self.unused_burnout
            status_text = f"成功 ({effective_threes})"
            status_style = "color: #4CAF50;"
        else:
            chaos_growth = 6 + self.unused_burnout
            status_text = "失败"
            status_style = "color: #C41E3A;"
        
        self.result_frame.setVisible(True)
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"font-size: 18pt; font-weight: bold; {status_style}")
        self.chaos_label.setText(f"混沌增长: {chaos_growth}")
        self.triscendence_widget.setVisible(self.is_triscendence)
        
        self.roll_history["chaos_growth"] = chaos_growth

    def on_die_clicked(self, index):
        val = self.current_rolls[index]
        if (val == 3 and not self.dice_buttons[index].is_burned) or self.dice_buttons[index].value==0: return

        qa_data = self.data.get("quality_assurances", {})
        available_qas = [k for k in self.qa_keys if qa_data.get(k, {}).get("current", 0) > 0]
        
        if not available_qas:
            QMessageBox.warning(self, "无法修改", "你没有可用的QA")
            return
            
        item, ok = QInputDialog.getItem(
            self, "消耗 QA", "选择要消耗的素质保障来将此骰子改为3:",
            [QUALITY_ASSURANCES[k] for k in available_qas], 0, False
        )
        
        if ok and item:
            selected_key = next(k for k in available_qas if QUALITY_ASSURANCES[k] == item)
            qa_data[selected_key]['current'] -= 1
            self.refresh_qa_combo()
            self.dataChanged.emit()
            
            self.current_rolls[index] = 3
            
            if self.dice_buttons[index].is_burned:
                self.roll_history['burned_indices'].remove(index)

            self.dice_buttons[index].update_state(3,False)

            self.roll_history["modifications"].append(f"消耗 {item} 将第{index+1}枚骰子改为3")
            self.calculate_result()

    def apply_triscendence(self, effect_type):
        if effect_type == "more_3":
            self.triscendence_selection = "叙事效果 (增加3的数量)"
            self.roll_history["triscendence_choice"] = f"增加3的数量(叙事效果)"
            QMessageBox.information(self, "叙事", "此为叙事效果")
            
        elif effect_type == "restore_qa":
            qa_data = self.data.get("quality_assurances", {})
            dlg = QADistributionDialog(qa_data, total_points=3, parent=self)
            if dlg.exec():
                distribution = dlg.get_distribution()
                for key, added_val in distribution.items():
                    qa_data[key]['current'] += added_val

                self.refresh_qa_combo()
                self.dataChanged.emit()
                QMessageBox.information(self, "成功", "QA点数已回复")
                info = ", ".join([f"{QUALITY_ASSURANCES[k]}+{v}" for k,v in distribution.items()])
                self.roll_history["triscendence_choice"] = f"回复QA ({info})"
            else:
                return

        elif effect_type == "commendation":
            self.data['commendations'] = self.data.get('commendations', 0) + 3
            self.dataChanged.emit()
            self.roll_history["triscendence_choice"] = "获得3点嘉奖"
            QMessageBox.information(self, "成功", "已获得3点嘉奖")
            
        self.triscendence_widget.setVisible(False)
    
    def build_html_report(self):
        h = self.roll_history
        if not h: return ""

        html = f"<h3>掷骰 (6d4) - {h['qa_name']}</h3>"

        html += f"<div style='color:#666; font-size:9pt'>燃尽: {h['total_burnout']} (额外燃尽{h['base_burnout']}点 + 缺少QA{1 if h['missing_qa'] else 0}点)</div>"

        dice_html = ""
        burned_set = set(h['burned_indices'])
        
        for i, val in enumerate(self.current_rolls):
            style = "font-weight:bold;"
            if i in burned_set:
                style += "text-decoration:line-through; color:#C41E3A;"
            elif val == 3:
                style += "color:#4CAF50;"
            
            dice_html += f"<span style='{style}'>{val}</span> "
        html += f"<div style='font-size:14pt; margin:5px 0'>[{dice_html}]</div>"

        if h['modifications']:
            html += "<ul>" + "".join([f"<li>{m}</li>" for m in h['modifications']]) + "</ul>"

        if h['triscendence_choice']:
            html += f"<div style='color:#E6B422; font-weight:bold'>✨ 三重升华: {h['triscendence_choice']}</div>"

        html += f"<hr><div>混沌增长: <b>{h['chaos_growth']}</b></div>"
        return html

    def show_details(self):
        QMessageBox.information(self, "详情", self.build_html_report())
    
    def commit_log(self):
        if self.pending_log:
            html = self.build_html_report()
            self.log_signal.emit(html)
            growth = self.roll_history.get("chaos_growth", 0)
            if growth != 0:
                self.chaosSignal.emit(growth)
                
            self.pending_log = False
            self.roll_history = {}
    
    def closeEvent(self, event):
        self.commit_log()
        super().closeEvent(event)