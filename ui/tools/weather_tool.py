import json
import random
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QGroupBox, QTextEdit, 
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Signal

from models.static_data import WEATHER_EFFECTS

class WeatherTool(QDialog):
    broadcast_signal = Signal(str) 
    local_log_signal = Signal(str)
    loose_ends_signal = Signal(int) 

    def __init__(self, game_name, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.setWindowTitle("松散端与天气")
        self.resize(550, 750)
        
        self.save_file = Path("data") / "GM" / self.game_name / "weather_state.json"
        
        self.state = {
            "loose_ends": 0,
            "weather_history": {}
        }

        self.session_rolls = 0

        self.current_report_html = ""
        
        self.load_state()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        le_group = QGroupBox("松散端")
        le_layout = QVBoxLayout(le_group)
        
        top_h = QHBoxLayout()
        self.le_spin = QSpinBox()
        self.le_spin.setRange(0, 999)
        self.le_spin.setValue(self.state["loose_ends"])
        self.le_spin.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.le_spin.valueChanged.connect(self.on_le_changed)
        
        top_h.addWidget(QLabel("当前累计:"))
        top_h.addWidget(self.le_spin)
        le_layout.addLayout(top_h)

        self.le_progress = QProgressBar()
        self.le_progress.setRange(0, 11)
        self.le_progress.setFormat("距离下一阶段: %v / 11")
        le_layout.addWidget(self.le_progress)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #C41E3A; font-weight: bold; background: #FFEEEE; padding: 5px; border-radius: 4px;")
        self.status_label.setWordWrap(True)
        le_layout.addWidget(self.status_label)
        
        layout.addWidget(le_group)

        weather_group = QGroupBox("天气事件")
        w_layout = QVBoxLayout(weather_group)
        
        btn_layout = QHBoxLayout()
        self.roll_btn = QPushButton("🎲 掷骰 (d20)")
        self.roll_btn.setMinimumHeight(40)
        self.roll_btn.setStyleSheet("background-color: #0055AA; color: white; font-weight: bold; font-size: 12pt;")
        self.roll_btn.clicked.connect(self.roll_weather)

        self.list_btn = QPushButton("查看天气列表")
        self.list_btn.setMinimumHeight(40)
        self.list_btn.clicked.connect(self.show_full_list)
        
        self.reset_btn = QPushButton("重置历史")
        self.reset_btn.clicked.connect(self.reset_history)
        
        btn_layout.addWidget(self.roll_btn, 2)
        btn_layout.addWidget(self.list_btn, 1)
        btn_layout.addWidget(self.reset_btn, 1)
        w_layout.addLayout(btn_layout)
        
        w_layout.addWidget(QLabel("当前效果预览:"))
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        w_layout.addWidget(self.result_display)

        self.broadcast_btn = QPushButton("广播此结果给所有玩家")
        self.broadcast_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        self.broadcast_btn.setEnabled(False)
        self.broadcast_btn.clicked.connect(self.broadcast_current_report)
        w_layout.addWidget(self.broadcast_btn)
        
        layout.addWidget(weather_group)
        
        self.update_le_ui()

    def update_le_ui(self):
        count = self.le_spin.value()

        tier = count // 11
        remainder = count % 11
        
        self.le_progress.setValue(remainder)
        
        info_text = f"当前阶段: {tier}\n"
        if tier == 0:
            info_text += "• 无特殊天气\n• 无特殊限制"
        else:
            info_text += f"• 需激活 {tier} 个天气事件\n• 需应用 {tier} 个特殊限制"
            
        self.status_label.setText(info_text)
        
        self.state["loose_ends"] = count
        self.save_state()
        self.check_roll_limit()

    def check_roll_limit(self):
        tier = self.le_spin.value() // 11
        remaining = max(0, tier - self.session_rolls)
        if tier == 0:
            self.roll_btn.setEnabled(False)
            self.roll_btn.setText("🎲 掷骰 (无天气事件)")
            self.roll_btn.setStyleSheet("background-color: #888; color: white;")
        elif remaining > 0:
            self.roll_btn.setEnabled(True)
            self.roll_btn.setText(f"🎲 掷骰 (d20) [本轮剩余: {remaining}]")
            self.roll_btn.setStyleSheet("background-color: #0055AA; color: white; font-weight: bold; font-size: 12pt;")
        else:
            self.roll_btn.setEnabled(False)
            self.roll_btn.setText("🎲 掷骰 (次数用尽)")
            self.roll_btn.setStyleSheet("background-color: #888; color: white;")

    def on_le_changed(self, val):
        self.update_le_ui()
        self.loose_ends_signal.emit(val)

    def show_full_list(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("完整天气列表 (1-20)")
        dialog.resize(600, 800)
        
        d_layout = QVBoxLayout(dialog)
        
        text_viewer = QTextEdit()
        text_viewer.setReadOnly(True)

        html = "<h2 style='text-align:center'>天气效果总览</h2><hr>"

        for i in sorted(WEATHER_EFFECTS.keys()):
            data = WEATHER_EFFECTS[i]
            
            html += f"<h3 style='color:#0055AA; margin-bottom:2px;'>{i}</h3>"
            
            if "description" in data:
                html += f"<div style='margin-left:20px;'>{data['description']}</div>"
            else:
                html += (
                    f"<div style='margin-left:20px;'>"
                    f"<b>A:</b> {data.get('a','-')}<br>"
                    f"<b>B:</b> {data.get('b','-')}<br>"
                    f"<b>C:</b> {data.get('c','-')}"
                    f"</div>"
                )
            html += "<hr style='border-top: 1px dashed #CCC;'>"
            
        text_viewer.setHtml(html)
        d_layout.addWidget(text_viewer)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        d_layout.addWidget(close_btn)
        
        dialog.exec()

    def roll_weather(self):
        self.session_rolls += 1
        roll = random.randint(1, 20)
        str_roll = str(roll)

        current_count = self.state["weather_history"].get(str_roll, 0) + 1
        weather_data = WEATHER_EFFECTS.get(roll, {"description": "数据缺失"})
        is_single_stage = "description" in weather_data
        
        effect_text = ""
        stage_label = ""
        is_overflow = False

        if roll%3==0:
            self.le_spin.setValue(self.le_spin.value()-roll//3)
        
        if is_single_stage:
            stage_label = "效果"
            effect_text = weather_data["description"]
        else:
            if current_count == 1:
                stage_label = "效果 A"
                effect_text = weather_data.get('a', '无描述')
            elif current_count == 2:
                stage_label = "效果 B"
                effect_text = weather_data.get('b', '无描述')
            elif current_count == 3:
                stage_label = "效果 C"
                effect_text = weather_data.get('c', '无描述')
            else:
                is_overflow = True
                stage_label = "效果 C"
                effect_text = weather_data.get('c', '无描述')

        display_html = (
            f"<h3 style='color:#0055AA'>🎲 天气检定: {roll}</h3>"
            f"<p>这是第 <b>{current_count}</b> 次掷出此点数。</p>"
            f"<hr>"
            f"<p><b>{stage_label}:</b> {effect_text}</p>"
        )

        final_choice_text = ""
        if not is_single_stage and is_overflow:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("选择重复出现的天气效果")
            msg_box.setText(f"数字 {roll} 已经是第 {current_count} 次出现了。")
            msg_box.setInformativeText("请选择执行效果：")
            
            btn_effect = msg_box.addButton("激活效果 C", QMessageBox.AcceptRole)
            btn_loose = msg_box.addButton("松散端 +3", QMessageBox.ActionRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_effect:
                final_choice_text = "<span style='color:green'>(GM 选择了激活天气效果)</span>"
            else:
                final_choice_text = "<span style='color:red'>(GM 选择了增加 3 个松散端)</span>"
                self.le_spin.setValue(self.le_spin.value() + 3)

        self.state["weather_history"][str_roll] = current_count

        self.save_state()
        self.check_roll_limit()

        full_log = display_html + (f"<p>{final_choice_text}</p>" if final_choice_text else "")
        self.result_display.setHtml(full_log)

        self.current_report_html = full_log
        self.broadcast_btn.setEnabled(True)
        self.broadcast_btn.setText("广播此结果给所有玩家")

        self.local_log_signal.emit(f"<b>[仅自己可见]</b><br>{full_log}")

    def broadcast_current_report(self):
        if self.current_report_html:
            public_html = f"<div style='border: 2px solid #0055AA; padding: 5px; border-radius: 4px;'>{self.current_report_html}</div>"
            self.broadcast_signal.emit(public_html)
            self.broadcast_btn.setText("已广播")
            self.broadcast_btn.setEnabled(False)

    def reset_history(self):
        reply = QMessageBox.question(self, "确认", "确定要重置所有天气的掷骰历史吗？\n(不会重置松散端数量)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.state["weather_history"] = {}
            self.save_state()
            self.result_display.setText("历史已重置。")

    def load_state(self):
        if self.save_file.exists():
            try:
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.state.update(data)
            except Exception:
                pass 

    def save_state(self):
        self.save_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=4)