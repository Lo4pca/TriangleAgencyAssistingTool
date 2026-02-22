import json
import random
from pathlib import Path
from typing import Dict, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QGroupBox, QTextEdit, 
    QMessageBox, QProgressBar, QWidget
)
from PySide6.QtCore import Qt, Signal

from models.static_data import WEATHER_EFFECTS

# ==========================================
# 业务逻辑层 (Model / Engine)
# ==========================================
class WeatherEngine:
    """处理天气系统相关的核心业务逻辑与数据持久化"""
    
    def __init__(self, game_name: str):
        self.save_file: Path = Path("data") / "GM" / game_name / "weather_state.json"
        self.loose_ends: int = 0
        self.weather_history: Dict[str, int] = {}
        self.session_rolls: int = 0
        self.load_state()

    def load_state(self) -> None:
        """从本地加载天气与松散端状态"""
        if self.save_file.exists():
            try:
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.loose_ends = data.get("loose_ends", 0)
                    self.weather_history = data.get("weather_history", {})
            except Exception as e:
                print(f"Error loading weather state: {e}")

    def save_state(self) -> None:
        """保存当前状态到本地"""
        self.save_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = {
                "loose_ends": self.loose_ends,
                "weather_history": self.weather_history
            }
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving weather state: {e}")

    def set_loose_ends(self, val: int) -> None:
        """更新松散端数值并保存"""
        self.loose_ends = max(0, val)
        self.save_state()

    def get_tier_info(self) -> Tuple[int, int]:
        """计算当前的阶段 (tier) 和进度余数 (remainder)"""
        tier = self.loose_ends // 11
        remainder = self.loose_ends % 11
        return tier, remainder

    def reset_history(self) -> None:
        """清空天气掷骰历史"""
        self.weather_history.clear()
        self.save_state()

    def record_roll(self, roll_val: int) -> int:
        """记录掷骰次数，并返回该数字出现的总次数"""
        self.session_rolls += 1
        str_roll = str(roll_val)
        self.weather_history[str_roll] = self.weather_history.get(str_roll, 0) + 1
        self.save_state()
        return self.weather_history[str_roll]

    def process_special_roll_rule(self, roll_val: int) -> int:
        """处理特殊规则：掷出3的倍数时，减少对应的松散端"""
        if roll_val % 3 == 0:
            reduction = roll_val // 3
            self.set_loose_ends(self.loose_ends - reduction)
            return reduction
        return 0


# ==========================================
# UI 表现层 (View / Controller)
# ==========================================
class WeatherTool(QDialog):
    """松散端与天气管理窗口"""
    
    broadcast_signal = Signal(str) 
    local_log_signal = Signal(str)
    loose_ends_signal = Signal(int) 

    def __init__(self, game_name: str, parent: QWidget = None):
        super().__init__(parent)
        self.game_name = game_name
        
        self.setWindowTitle("松散端与天气")
        self.resize(550, 750)

        self.engine = WeatherEngine(self.game_name)
        self.current_report_html: str = ""
        
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- 1. 松散端区域 ---
        le_group = QGroupBox("松散端")
        le_layout = QVBoxLayout(le_group)
        
        top_h = QHBoxLayout()
        self.le_spin = QSpinBox()
        self.le_spin.setRange(0, 999)
        self.le_spin.setValue(self.engine.loose_ends)
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

        # --- 2. 天气事件区域 ---
        weather_group = QGroupBox("天气事件")
        w_layout = QVBoxLayout(weather_group)
        
        btn_layout = QHBoxLayout()
        self.roll_btn = QPushButton("🎲 掷骰 (d20)")
        self.roll_btn.setMinimumHeight(40)
        self.roll_btn.setStyleSheet("background-color: #0055AA; color: white; font-weight: bold; font-size: 12pt;")
        self.roll_btn.clicked.connect(self.handle_weather_roll)

        self.list_btn = QPushButton("查看天气列表")
        self.list_btn.setMinimumHeight(40)
        self.list_btn.clicked.connect(self.show_full_list)
        
        self.reset_btn = QPushButton("重置历史")
        self.reset_btn.clicked.connect(self.handle_reset_history)
        
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
        
        # 初始化 UI 状态
        self.refresh_le_ui()

    def refresh_le_ui(self) -> None:
        """根据当前松散端数值刷新 UI 表现"""
        tier, remainder = self.engine.get_tier_info()
        
        self.le_progress.setValue(remainder)
        
        info_text = f"当前阶段: {tier}\n"
        if tier == 0:
            info_text += "• 无特殊天气\n• 无特殊限制"
        else:
            info_text += f"• 需激活 {tier} 个天气事件\n• 需应用 {tier} 个特殊限制"
            
        self.status_label.setText(info_text)
        self.update_roll_button_state(tier)

    def update_roll_button_state(self, current_tier: int) -> None:
        """更新掷骰按钮的可用状态与文本"""
        remaining = max(0, current_tier - self.engine.session_rolls)
        
        if current_tier == 0:
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

    def on_le_changed(self, val: int) -> None:
        """响应 SpinBox 数值改变"""
        self.engine.set_loose_ends(val)
        self.refresh_le_ui()
        self.loose_ends_signal.emit(val)

    def handle_weather_roll(self) -> None:
        """处理天气掷骰点击事件"""
        roll = random.randint(1, 20)
        
        # 1. 规则判断：3的倍数减少松散端
        reduction = self.engine.process_special_roll_rule(roll)
        if reduction > 0:
            self.le_spin.setValue(self.engine.loose_ends)

        # 2. 记录历史
        current_count = self.engine.record_roll(roll)
        
        # 3. 获取天气数据
        weather_data = WEATHER_EFFECTS.get(roll, {"description": "数据缺失"})
        is_single_stage = "description" in weather_data
        
        effect_text = ""
        stage_label = ""
        is_overflow = False

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
        
        # 4. 溢出抉择弹窗
        if not is_single_stage and is_overflow:
            final_choice_text = self.prompt_overflow_choice(roll, current_count)

        # 5. 更新状态与 UI
        self.refresh_le_ui()

        full_log = display_html + (f"<p>{final_choice_text}</p>" if final_choice_text else "")
        self.result_display.setHtml(full_log)
        self.current_report_html = full_log
        
        self.broadcast_btn.setEnabled(True)
        self.broadcast_btn.setText("广播此结果给所有玩家")
        self.local_log_signal.emit(f"<b>[仅自己可见]</b><br>{full_log}")

    def prompt_overflow_choice(self, roll: int, current_count: int) -> str:
        """处理溢出时的 GM 抉择"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("选择重复出现的天气效果")
        msg_box.setText(f"数字 {roll} 已经是第 {current_count} 次出现了。")
        msg_box.setInformativeText("请选择执行效果：")
        
        btn_effect = msg_box.addButton("激活效果 C", QMessageBox.AcceptRole)
        btn_loose = msg_box.addButton("松散端 +3", QMessageBox.ActionRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_effect:
            return "<span style='color:green'>(GM 选择了激活天气效果)</span>"
        else:
            # 增加松散端，SpinBox 改变会自动保存并刷新 UI
            self.le_spin.setValue(self.le_spin.value() + 3)
            return "<span style='color:red'>(GM 选择了增加 3 个松散端)</span>"

    def broadcast_current_report(self) -> None:
        """广播日志给所有 PL"""
        if self.current_report_html:
            public_html = f"<div style='border: 2px solid #0055AA; padding: 5px; border-radius: 4px;'>{self.current_report_html}</div>"
            self.broadcast_signal.emit(public_html)
            self.broadcast_btn.setText("已广播")
            self.broadcast_btn.setEnabled(False)

    def handle_reset_history(self) -> None:
        """处理历史重置事件"""
        reply = QMessageBox.question(self, "确认", "确定要重置所有天气的掷骰历史吗？\n(不会重置松散端数量)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.engine.reset_history()
            self.result_display.setText("历史已重置。")

    def show_full_list(self) -> None:
        """展示完整的天气列表对话框"""
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