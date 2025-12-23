from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QPushButton, QVBoxLayout, 
    QHBoxLayout, QGridLayout, QLineEdit, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal

def create_label(text, class_name=None, style=None):
    lbl = QLabel(text)
    if class_name:
        lbl.setProperty("class", class_name)
    if style:
        lbl.setStyleSheet(style)
    return lbl

def create_icon_button(text, color_bg, color_text, tooltip=""):
    btn = QPushButton(text)
    btn.setFixedSize(20, 20)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {color_bg}; color: {color_text}; 
            border-radius: 10px; border: none; font-weight: bold;
        }}
        QPushButton:hover {{ background: {color_text}; color: {color_bg}; }}
    """)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn

# --- 基础组件 ---

class HLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setStyleSheet("background-color: #CCCCCC; max-height: 2px;")

class TrackNode(QPushButton):
    """
    自定义轨道节点按钮 (0:空 -> 1:实心 -> 2:划掉)
    """
    stateChanged = Signal(int)

    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.setFixedSize(35, 35)
        self.setText(label_text)
        self.setProperty("class", "TrackNode")
        self._state = 0 
        self.update_style()
        self.clicked.connect(self.cycle_state)

    def cycle_state(self):
        self._state = (self._state + 1) % 3
        self.update_style()
        self.stateChanged.emit(self._state)

    def set_state(self, state):
        self._state = state
        self.update_style()

    def get_state(self):
        return self._state

    def update_style(self):
        self.setProperty("state", str(self._state))
        self.style().unpolish(self)
        self.style().polish(self)

# --- 卡片基类 ---

class BaseCard(QFrame):
    """
    所有卡片的基类，提供公共信号和基础方法
    """
    deleteRequested = Signal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)

    def request_delete(self):
        self.deleteRequested.emit(self)

# --- 具体卡片实现 ---

class AbilityCard(BaseCard):
    def __init__(self, ability_data, parent=None):
        super().__init__(parent)
        self.data = ability_data
        self.init_ui()

    def init_ui(self):
        self.setObjectName("AbilityCard")
        self.setStyleSheet("""
            #AbilityCard { background-color: #F0F4F8; border: 2px solid #0055AA; border-radius: 10px; }
            QLineEdit, QTextEdit { background: white; color: #333; border: 1px solid #BDC3C7; border-radius: 3px; padding: 2px; }
            .BlueLabel { color: #0055AA; font-weight: bold; font-size: 10pt; }
            .RedLabel { color: #C41E3A; font-weight: bold; font-size: 10pt; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Top Grid
        top_grid = QGridLayout()
        top_grid.setVerticalSpacing(5)
        
        top_grid.addWidget(QLabel("技能", styleSheet="color:#0055AA; font-weight:bold;"), 0, 0)
        self.name_edit = QLineEdit(self.data.get("name", ""))
        self.name_edit.setPlaceholderText("输入技能名称")
        self.name_edit.setStyleSheet("font-size: 12pt; font-weight: bold; color: #0055AA; border:none; background:transparent;")
        top_grid.addWidget(self.name_edit, 1, 0)

        top_grid.addWidget(QLabel("触发", styleSheet="color:#555;"), 0, 1)
        self.trigger_edit = QTextEdit()
        self.trigger_edit.setPlainText(self.data.get("trigger", ""))
        self.trigger_edit.setFixedHeight(45)
        top_grid.addWidget(self.trigger_edit, 1, 1)

        top_grid.addWidget(QLabel("素质", styleSheet="color:#555;"), 0, 2)
        self.quality_edit = QLineEdit(self.data.get("quality", ""))
        self.quality_edit.setFixedHeight(45) 
        top_grid.addWidget(self.quality_edit, 1, 2)

        # 删除按钮
        del_btn = create_icon_button("×", "#FFCCCC", "red", "删除此能力")
        del_btn.clicked.connect(self.request_delete)
        top_grid.addWidget(del_btn, 0, 3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        top_grid.setColumnStretch(0, 2)
        top_grid.setColumnStretch(1, 4)
        top_grid.setColumnStretch(2, 1)
        
        layout.addLayout(top_grid)
        layout.addWidget(HLine())

        # 2. Result Grid
        res_grid = QGridLayout()
        res_grid.setVerticalSpacing(5)
        
        # Success
        res_grid.addWidget(create_label("▲", style="color:#0055AA; font-size:14pt;"), 0, 0)
        res_grid.addWidget(create_label("成功时，", class_name="BlueLabel"), 0, 1)
        self.success_edit = QTextEdit()
        self.success_edit.setPlainText(self.data.get("success", ""))
        self.success_edit.setFixedHeight(60)
        res_grid.addWidget(self.success_edit, 0, 2)
        
        # Fail
        res_grid.addWidget(create_label("✖", style="color:#C41E3A; font-size:14pt;"), 0, 3)
        res_grid.addWidget(create_label("失败时，", class_name="RedLabel"), 0, 4)
        self.fail_edit = QTextEdit()
        self.fail_edit.setPlainText(self.data.get("fail", ""))
        self.fail_edit.setFixedHeight(60)
        res_grid.addWidget(self.fail_edit, 0, 5)
        
        layout.addLayout(res_grid)
        
        # 3. Extra
        extra_layout = QHBoxLayout()
        extra_layout.addWidget(create_label("★", style="color:#0055AA; font-size:14pt;"))
        self.cost_effect_edit = QTextEdit()
        self.cost_effect_edit.setPlainText(self.data.get("cost_effect", ""))
        self.cost_effect_edit.setStyleSheet("border: 1px solid #0055AA; background:white; border-radius:3px;") 
        self.cost_effect_edit.setFixedHeight(60)
        extra_layout.addWidget(self.cost_effect_edit)
        layout.addLayout(extra_layout)
        layout.addWidget(HLine())

        # 4. QA Area
        self._init_qa_area(layout)

    def _init_qa_area(self, parent_layout):
        qa_frame = QFrame()
        qa_frame.setStyleSheet("background-color: #E8F0F8; border-radius: 6px;")
        qa_layout = QVBoxLayout(qa_frame)
        
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Q:", styleSheet="color:#0055AA; font-weight:bold; font-size:12pt;"))
        self.question_edit = QLineEdit(self.data.get("question", ""))
        self.question_edit.setStyleSheet("background: transparent; border: none; border-bottom: 1px solid #AAC; font-size: 11pt;")
        q_row.addWidget(self.question_edit)
        
        self.practiced_cb = QCheckBox("已练习？")
        self.practiced_cb.setChecked(self.data.get("practiced", False))
        self.practiced_cb.setStyleSheet("""
            QCheckBox { 
                color: #333333;
                spacing: 5px;
            }
            QCheckBox::indicator { 
                width: 18px; 
                height: 18px; 
                border: 1px solid #999; 
                background: white; 
                border-radius: 2px;
            }
            QCheckBox::indicator:checked { 
                background: #0055AA;
            }
        """)
        q_row.addWidget(self.practiced_cb)
        qa_layout.addLayout(q_row)

        self.answers_widgets = []
        answers_data = self.data.get("answers", [{}, {}])
        for i in range(2):
            self._add_answer_row(qa_layout, answers_data[i] if i < len(answers_data) else {})
            
        parent_layout.addWidget(qa_frame)

    def _add_answer_row(self, layout, ans_data):
        row = QHBoxLayout()
        row.addWidget(QLabel("A:", styleSheet="color:#0055AA; font-weight:bold;"))
        
        ans_edit = QLineEdit(ans_data.get("text", ""))
        ans_edit.setStyleSheet("background: transparent; border: none; border-bottom: 1px solid #AAC;")
        row.addWidget(ans_edit)
        
        row.addWidget(QLabel("➡", styleSheet="color:#0055AA; font-weight:bold; font-size:14pt;"))
        
        boxes = []
        track_states = ans_data.get("track", [False]*3)
        for i in range(3):
            cb = QCheckBox()
            cb.setStyleSheet("""
                QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #999; background: white; border-radius: 2px;}
                QCheckBox::indicator:checked { background: #333; }
            """)
            if i < len(track_states): cb.setChecked(track_states[i])
            row.addWidget(cb)
            boxes.append(cb)
        
        doc_edit = QLineEdit(ans_data.get("doc", ""))
        doc_edit.setPlaceholderText("PAGE #")
        doc_edit.setFixedWidth(60)
        row.addWidget(doc_edit)
        
        layout.addLayout(row)
        self.answers_widgets.append({"text": ans_edit, "boxes": boxes, "doc": doc_edit})

    def get_data(self):
        answers = []
        for item in self.answers_widgets:
            answers.append({
                "text": item["text"].text(),
                "track": [b.isChecked() for b in item["boxes"]],
                "doc": item["doc"].text()
            })
        return {
            "name": self.name_edit.text(),
            "trigger": self.trigger_edit.toPlainText(),
            "quality": self.quality_edit.text(),
            "success": self.success_edit.toPlainText(),
            "fail": self.fail_edit.toPlainText(),
            "cost_effect": self.cost_effect_edit.toPlainText(),
            "question": self.question_edit.text(),
            "practiced": self.practiced_cb.isChecked(),
            "answers": answers
        }

class RequisitionCard(BaseCard):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        self.setObjectName("RequisitionCard")
        self.setStyleSheet("""
            #RequisitionCard { background-color: #FFF0F0; border: 2px solid #C41E3A; border-radius: 10px; }
            QLineEdit, QTextEdit { background: white; color: #333; border: 1px solid #E6B4B4; border-radius: 3px; padding: 2px; }
            QLabel { color: #C41E3A; font-weight: bold; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # 1. Header
        top = QHBoxLayout()
        top.addWidget(QLabel("名称"))
        self.name_edit = QLineEdit(self.data.get("name", ""))
        self.name_edit.setStyleSheet("font-size: 11pt; font-weight: bold; border:none; background:transparent; border-bottom: 1px solid #C41E3A;")
        top.addWidget(self.name_edit, 2)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("color: #E6B4B4;")
        top.addWidget(line)

        top.addWidget(QLabel("页码/受限文档代码"))
        self.code_edit = QLineEdit(self.data.get("code", ""))
        self.code_edit.setPlaceholderText("#")
        self.code_edit.setFixedWidth(80)
        top.addWidget(self.code_edit)

        # 删除
        del_btn = create_icon_button("×", "#FFCCCC", "red", "删除")
        del_btn.clicked.connect(self.request_delete)
        top.addWidget(del_btn)
        
        layout.addLayout(top)

        # 2. Effect
        layout.addWidget(QLabel("效果"))
        self.effect_edit = QTextEdit()
        self.effect_edit.setPlainText(self.data.get("effect", ""))
        self.effect_edit.setStyleSheet("border: 1px solid #C41E3A; background: white;")
        self.effect_edit.setFixedHeight(80)
        layout.addWidget(self.effect_edit)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "code": self.code_edit.text(),
            "effect": self.effect_edit.toPlainText()
        }

class RelationshipCard(BaseCard):
    stateChanged = Signal()

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.track_nodes = []
        self.init_ui()

    def init_ui(self):
        self.setObjectName("RelationshipCard")
        self.setStyleSheet("""
            #RelationshipCard { background-color: #FFFDF0; border: 2px solid #E6B422; border-radius: 10px; }
            QLineEdit { background: white; color: #333; border: 1px solid #E6B422; padding: 2px; }
            QLabel { color: #E6B422; font-weight: bold; }
            .SmallNum { color: #333; font-size: 8pt; font-weight: normal; }
            .NetworkLabel { color: #E6B422; font-size: 7pt; font-weight: bold; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. Header
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("名称"))
        self.name_edit = QLineEdit(self.data.get("name", ""))
        self.name_edit.setStyleSheet("font-size: 11pt; font-weight: bold; border:none; background:transparent; border-bottom: 1px solid #E6B422;")
        row1.addWidget(self.name_edit, 2)
        
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("color: #E6B422;")
        row1.addWidget(line)

        row1.addWidget(QLabel("扮演者"))
        self.player_edit = QLineEdit(self.data.get("player", ""))
        self.player_edit.setStyleSheet("border:none; background:transparent; border-bottom: 1px solid #E6B422;")
        row1.addWidget(self.player_edit, 1)

        del_btn = create_icon_button("×", "#FFE0B2", "#E65100")
        del_btn.clicked.connect(self.request_delete)
        row1.addWidget(del_btn)
        layout.addLayout(row1)

        # 2. Desc
        layout.addWidget(QLabel("描述"))
        self.desc_edit = QLineEdit(self.data.get("desc", ""))
        self.desc_edit.setStyleSheet("border:none; background:transparent; border-bottom: 1px solid #E6B422;")
        layout.addWidget(self.desc_edit)

        # 3. Track
        self._init_track(layout)

        # 4. Bottom
        bottom = QHBoxLayout()
        
        bonus_box = QVBoxLayout()
        bonus_box.addWidget(QLabel("网络化加成"))
        self.bonus_edit = QLineEdit(self.data.get("bonus", ""))
        self.bonus_edit.setStyleSheet("border:none; background:transparent; border-bottom: 1px solid #E6B422;")
        bonus_box.addWidget(self.bonus_edit)
        bottom.addLayout(bonus_box, 4)

        active_box = QVBoxLayout()
        active_box.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self.active_cb = QCheckBox("激活")
        self.active_cb.setChecked(self.data.get("active", False))
        self.active_cb.setStyleSheet("""
            QCheckBox { color: #E6B422; font-weight: bold; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #E6B422; border-radius: 4px; background: white;}
            QCheckBox::indicator:checked { background: #E6B422; }
        """)
        active_box.addWidget(self.active_cb)
        bottom.addLayout(active_box, 1)

        layout.addLayout(bottom)

    def _init_track(self, layout):
        container = QHBoxLayout()
        container.setSpacing(2)
        container.addWidget(QLabel("▶", styleSheet="color:#E6B422; font-size:14pt;"))
        
        saved = self.data.get("track", [0]*10)
        for i in range(10):
            box = QVBoxLayout()
            box.setSpacing(2)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            box.addWidget(create_label(str(i), class_name="SmallNum"))
            
            node = TrackNode()
            if i < len(saved): node.set_state(saved[i])
            node.stateChanged.connect(lambda: self.stateChanged.emit())
            self.track_nodes.append(node)
            box.addWidget(node)

            lbl_text = "网络化▲" if i == 9 else " "
            box.addWidget(create_label(lbl_text, class_name="NetworkLabel"))
            
            container.addLayout(box)
        layout.addLayout(container)

    def is_networked(self):
        if self.track_nodes and len(self.track_nodes) >= 10:
            return self.track_nodes[9].get_state() > 0
        return False

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "player": self.player_edit.text(),
            "desc": self.desc_edit.text(),
            "bonus": self.bonus_edit.text(),
            "active": self.active_cb.isChecked(),
            "track": [n.get_state() for n in self.track_nodes]
        }

class CustomTrackCard(BaseCard):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.track_nodes = []
        self.length = self.data.get("length", 15)
        self.init_ui()

    def init_ui(self):
        self.setObjectName("CustomTrackCard")
        self.setStyleSheet("""
            #CustomTrackCard { background-color: #FAFAFC; border: 2px solid #554477; border-radius: 15px; }
            QLabel { color: #554477; font-weight: bold; }
            QLineEdit { border: 1px solid #554477; border-radius: 5px; padding: 2px; color: #333; background: white; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. Header
        header = QHBoxLayout()
        header.addWidget(QLabel("NAME"))
        self.name_edit = QLineEdit(self.data.get("name", ""))
        self.name_edit.setFixedHeight(30)
        header.addWidget(self.name_edit, 3)

        header.addWidget(QLabel("MAX"))
        self.max_edit = QLineEdit(self.data.get("max", ""))
        self.max_edit.setFixedHeight(30)
        header.addWidget(self.max_edit, 1)

        del_btn = create_icon_button("×", "#E0E0E0", "#555")
        del_btn.clicked.connect(self.request_delete)
        header.addWidget(del_btn)
        
        layout.addLayout(header)

        # 2. Grid
        grid_w = QWidget()
        self.track_grid = QGridLayout(grid_w)
        self.track_grid.setSpacing(4)
        self.track_grid.setContentsMargins(0, 0, 0, 0)
        self._generate_snake_track()
        layout.addWidget(grid_w)

    def _generate_snake_track(self):
        COLS = 15
        saved = self.data.get("track", [])
        if len(saved) < self.length:
            saved.extend([0] * (self.length - len(saved)))

        for i in range(self.length):
            row = i // COLS
            col_in_row = i % COLS
            
            # Snake Logic
            if row % 2 == 0:
                col = col_in_row + 1
                if col_in_row == 0: 
                    self.track_grid.addWidget(create_label("▶", style="font-size:16pt;color:#554477;"), row, 0)
            else:
                col = COLS - col_in_row
                if col_in_row == 0:
                    self.track_grid.addWidget(create_label("◀", style="font-size:16pt;color:#554477;"), row, 0)

            node = TrackNode(str(i + 1))
            if i < len(saved): node.set_state(saved[i])
            self.track_nodes.append(node)
            self.track_grid.addWidget(node, row, col)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "max": self.max_edit.text(),
            "length": self.length,
            "track": [n.get_state() for n in self.track_nodes]
        }