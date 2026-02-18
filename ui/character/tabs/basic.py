from typing import Dict, Any, Tuple, Optional, List, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt

from models.static_data import (
    REALITY_DATA, COMPETENCY_DATA, ANOMALY_NAMES, QUALITY_ASSURANCES
)
from ui.common.widgets import create_label, HLine

class BasicInfoTab(QWidget):
    """基本信息与状态管理标签页"""

    def __init__(self, character_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data = character_data

        # 缓存动态标签组件引用，便于后续更新数据
        self.dynamic_labels: Dict[str, QLabel] = {}
        self.sanctioned_behavior_labels: List[QLabel] = []
        self.quality_assurances: Dict[str, Tuple[QSpinBox, QSpinBox]] = {}
        self.track_boxes: List[QCheckBox] = []
        
        self.init_ui()

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. 头部信息
        header_layout = QHBoxLayout()
        header_layout.addLayout(self._init_header_left(), 5)
        header_layout.addLayout(self._init_header_right(), 3)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(HLine())

        # 2. 中间内容区
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)
        content_layout.addLayout(self._init_content_left(), 4)
        content_layout.addLayout(self._init_content_right(), 3)
        main_layout.addLayout(content_layout)

        # 强制触发一次同步
        self._update_identity_fields()
        self._update_behavior_fields()

    def _init_header_left(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("角色名"), 0, Qt.AlignmentFlag.AlignBottom)
        self.name_input = QLineEdit(self.data.get("name", ""))
        self.name_input.setProperty("class", "UnderlineInput")
        row1.addWidget(self.name_input, 1)
        
        row1.addSpacing(20)
        
        row1.addWidget(QLabel("代号"), 0, Qt.AlignmentFlag.AlignBottom)
        self.pronouns_input = QLineEdit(self.data.get("pronouns", ""))
        self.pronouns_input.setProperty("class", "UnderlineInput")
        row1.addWidget(self.pronouns_input, 1)
        layout.addLayout(row1)

        def add_row(label: str, key: str) -> QLineEdit:
            r = QHBoxLayout()
            r.addWidget(QLabel(label), 0, Qt.AlignmentFlag.AlignBottom)
            inp = QLineEdit(self.data.get(key, ""))
            inp.setProperty("class", "UnderlineInput")
            r.addWidget(inp, 1)
            layout.addLayout(r)
            return inp

        self.title_input = add_row("特工职称", "title")
        self.standing_input = add_row("特工信誉", "standing")
        return layout

    def _init_header_right(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(10)

        def add_arc_row(row_idx: int, label_char: str, label_text: str, data_key: str, source_list: List[str], signal: Optional[Callable] = None) -> QComboBox:
            lbl_char = create_label(label_char, class_name=f"Label{label_char}")
            grid.addWidget(lbl_char, row_idx, 0, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(create_label(label_text, class_name=f"Label{label_char}"), row_idx, 1)
            
            combo = QComboBox()
            combo.addItems(source_list)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            
            current_val = self.data.get(data_key)
            if current_val in source_list:
                combo.setCurrentText(current_val)
                
            if signal:
                combo.currentIndexChanged.connect(signal)
            grid.addWidget(combo, row_idx, 2)
            return combo

        self.anomaly_combo = add_arc_row(0, "A", "异常共鸣", "anomaly", ANOMALY_NAMES)
        self.reality_combo = add_arc_row(1, "R", "现实身份", "reality", list(REALITY_DATA.keys()), self._update_identity_fields)
        self.competency_combo = add_arc_row(2, "C", "公司职能", "competency", list(COMPETENCY_DATA.keys()), self._update_behavior_fields)
        
        return grid

    def _init_content_left(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 1. 顶部统计
        top_stats = QHBoxLayout()
        
        # 轨道复选框
        track_layout = QVBoxLayout()
        track_layout.setSpacing(5)
        self.dynamic_labels["track_desc"] = QLabel()
        self.dynamic_labels["track_desc"].setWordWrap(True)
        self.dynamic_labels["track_desc"].setProperty("class", "TrackDesc")
        self.dynamic_labels["track_name"] = QLabel()
        self.dynamic_labels["track_name"].setProperty("class", "TrackName")
        
        track_layout.addWidget(self.dynamic_labels["track_desc"])
        track_layout.addWidget(self.dynamic_labels["track_name"])
        
        track_boxes_layout = QHBoxLayout()
        track_boxes_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        saved_tracks = self.data.get("track_states", [False] * 4)
        for i in range(4):
            box = QCheckBox()
            box.setProperty("class", "TrackBox")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            if i < len(saved_tracks): box.setChecked(saved_tracks[i])
            self.track_boxes.append(box)
            track_boxes_layout.addWidget(box)
            
        track_layout.addLayout(track_boxes_layout)
        track_layout.addStretch()

        # 数值统计框
        stats_layout = QVBoxLayout()
        def add_stat(icon: str, title: str, val: int) -> QSpinBox:
            r = QHBoxLayout()
            r.addWidget(create_label(icon, style="color:#C41E3A; font-size:14pt;"))
            r.addWidget(create_label(title, class_name="StatLabelRed"))
            s = QSpinBox()
            s.setValue(val)
            s.setFixedWidth(60)
            r.addWidget(s)
            r.addStretch()
            stats_layout.addLayout(r)
            return s

        self.commendations_input = add_stat("★", "嘉奖", self.data.get("commendations", 0))
        self.demerits_input = add_stat("🔨", "处分", self.data.get("demerits", 0))
        self.additional_burnout_input = add_stat("🔥", "额外力竭", self.data.get("additional_burnout", 0))

        top_stats.addLayout(stats_layout, 2)
        top_stats.addLayout(track_layout, 3)
        layout.addLayout(top_stats)
        layout.addSpacing(20)

        # 2. 动态信息块
        layout.addLayout(self._create_info_block("现实触发", "HeaderYellow", "reality_trigger", "你的GM可以消耗3点混沌触发"))
        layout.addLayout(self._create_info_block("力竭释放", "HeaderYellow", "burnout_release", "检查此处来看你是否能取消力竭"))
        layout.addLayout(self._create_info_block("最高原则", "HeaderRed", "prime_directive", "执行以下行为将获得1次处分"))

        # 3. 授权行为区
        actions_block = QVBoxLayout()
        actions_block.setSpacing(2)
        h_row = QHBoxLayout()
        h_row.addWidget(create_label("▶", class_name="HeaderRed"))
        h_row.addWidget(create_label("授权行为", class_name="BlockHeader HeaderRed"))
        h_row.addStretch()
        actions_block.addLayout(h_row)
        
        actions_block.addWidget(create_label("执行以下行为将获得1次嘉奖", class_name="BlockDesc"))
        
        for _ in range(3):
            row = QHBoxLayout()
            row.setContentsMargins(15, 0, 0, 0)
            row.addWidget(create_label("▷", style="color: #C41E3A; font-size: 12pt;"))
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setProperty("class", "BlockValueTitle")
            self.sanctioned_behavior_labels.append(lbl)
            row.addWidget(lbl, 1)
            actions_block.addLayout(row)
            
        actions_block.addWidget(create_label("若单次任务中执行全部三个行为，获得额外3嘉奖", class_name="BlockDesc"))
        layout.addLayout(actions_block)
        layout.addStretch()
        
        return layout

    def _create_info_block(self, title: str, style_class: str, key_prefix: str, static_desc: str) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(2)
        
        h_row = QHBoxLayout()
        h_row.addWidget(create_label("▶", class_name=style_class))
        h_row.addWidget(create_label(title, class_name=f"BlockHeader {style_class}"))
        h_row.addStretch()
        block.addLayout(h_row)
        
        lbl_static = QLabel(static_desc)
        lbl_static.setWordWrap(True)
        lbl_static.setProperty("class", "BlockDesc")
        block.addWidget(lbl_static)
        
        lbl_title = QLabel()
        lbl_title.setWordWrap(True)
        lbl_title.setProperty("class", "BlockValueTitle")
        self.dynamic_labels[f"{key_prefix}_title"] = lbl_title
        block.addWidget(lbl_title)
        
        lbl_desc = QLabel()
        lbl_desc.setWordWrap(True)
        lbl_desc.setProperty("class", "BlockValueDesc")
        self.dynamic_labels[f"{key_prefix}_desc"] = lbl_desc
        block.addWidget(lbl_desc)
        
        return block

    def _init_content_right(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.addWidget(create_label("素质保障(当前/最大)", class_name="QualityMainHeader"), 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(20)

        grid = QGridLayout()
        grid.setVerticalSpacing(15)
        self.qa_values = self.data.get("quality_assurances", {})

        for i, (key, cn) in enumerate(QUALITY_ASSURANCES.items()):
            grid.addWidget(create_label(cn, class_name="QualityName"), i, 1)
            
            row = QHBoxLayout()
            cur = QSpinBox()
            cur.setFixedWidth(50)
            mx = QSpinBox()
            mx.setFixedWidth(50)
            mx.setMaximum(9)
            
            saved = self.qa_values.get(key, {})
            mx.setValue(saved.get('max', 0))
            cur.setMaximum(mx.value())
            cur.setValue(saved.get('current', 0))

            mx.valueChanged.connect(lambda v, c=cur: c.setMaximum(v))
            
            self.quality_assurances[key] = (cur, mx)
            
            row.addStretch()
            row.addWidget(cur)
            row.addWidget(QLabel("/", styleSheet="font-size:12pt; color:#999;"))
            row.addWidget(mx)
            grid.addLayout(row, i, 2)
            
        layout.addLayout(grid)
        layout.addStretch()
        return layout

    def _update_identity_fields(self) -> None:
        """更新受现实身份(Reality)影响的动态文本"""
        identity = self.reality_combo.currentText()
        data = REALITY_DATA.get(identity, {})

        self.dynamic_labels["reality_trigger_title"].setText(data.get("trigger", ""))
        self.dynamic_labels["reality_trigger_desc"].setText(data.get("trigger_desc", ""))
        self.dynamic_labels["burnout_release_title"].setText(data.get("burnout", ""))
        self.dynamic_labels["burnout_release_desc"].setText(data.get("burnout_desc", ""))
        self.dynamic_labels["track_name"].setText(data.get("track_name", "轨道名称"))
        self.dynamic_labels["track_desc"].setText(data.get("track_desc", "轨道描述文本..."))

    def _update_behavior_fields(self) -> None:
        """更新受公司职能(Competency)影响的动态文本"""
        func = self.competency_combo.currentText()
        data = COMPETENCY_DATA.get(func, {})
        
        self.dynamic_labels["prime_directive_title"].setText(data.get("directive", ""))
        self.dynamic_labels["prime_directive_desc"].setText(data.get("directive_desc", ""))
        
        behaviors = data.get("behaviors", [])
        for i, label in enumerate(self.sanctioned_behavior_labels):
            label.setText(behaviors[i] if i < len(behaviors) else "")

    def get_data(self) -> Dict[str, Any]:
        """序列化收集当前表单数据"""
        qa_data = {k: {"current": c.value(), "max": m.value()} for k, (c, m) in self.quality_assurances.items()}
        return {
            "name": self.name_input.text(),
            "pronouns": self.pronouns_input.text(),
            "title": self.title_input.text(),
            "standing": self.standing_input.text(),
            "commendations": self.commendations_input.value(),
            "demerits": self.demerits_input.value(),
            "additional_burnout": self.additional_burnout_input.value(),
            "track_states": [b.isChecked() for b in self.track_boxes],
            "anomaly": self.anomaly_combo.currentText(),
            "reality": self.reality_combo.currentText(),
            "competency": self.competency_combo.currentText(),
            "quality_assurances": qa_data
        }