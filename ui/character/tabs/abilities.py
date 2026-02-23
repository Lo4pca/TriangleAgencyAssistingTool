from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt

from models.static_data import ANOMALY_ABILITIES_DATA, EMPTY_ABILITY_TEMPLATE
from ui.common.widgets import HLine, AbilityCard

class AbilitiesTab(QWidget):
    """异常技能管理标签页"""

    def __init__(self, character_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data = character_data
        self.cards: List[AbilityCard] = []
        self.init_ui()

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(20)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        self._init_header()
        self.content_layout.addWidget(HLine())

        self.add_btn = QPushButton("+ 添加新能力")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setStyleSheet("""
            QPushButton { border: 2px dashed #0055AA; color: #0055AA; font-weight: bold; border-radius: 10px; font-size: 11pt; }
            QPushButton:hover { background-color: #F0EFF5; }
        """)
        self.add_btn.clicked.connect(lambda: self.add_card(EMPTY_ABILITY_TEMPLATE))
        
        # 加载初始卡片
        saved_abilities = self.data.get("abilities", [])
        for ab_data in saved_abilities:
            self.add_card(ab_data)

        self.content_layout.addWidget(self.add_btn)
        self.content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _init_header(self) -> None:
        """初始化顶部标题区域"""
        header_layout = QHBoxLayout()
        title_lbl = QLabel("异常技能")
        title_lbl.setStyleSheet("font-size: 24pt; font-weight: bold; color: #0055AA;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        a_icon = QLabel("A")
        a_icon.setStyleSheet("background-color: #0055AA; color: white; font-size: 30pt; font-weight: bold; padding: 5px 25px; border-top-left-radius: 20px; border-top-right-radius: 20px;")

        current_anomaly_name = self.data.get("anomaly", "未选择")
        self.anomaly_name_label = QLabel(current_anomaly_name)
        self.anomaly_name_label.setStyleSheet("color:#0055AA; font-weight:bold; font-size: 18pt; margin-left: 10px;")
        
        header_right_box = QHBoxLayout()
        header_right_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        header_right_box.addWidget(a_icon)
        header_right_box.addWidget(self.anomaly_name_label)

        header_layout_container = QVBoxLayout()
        header_layout_container.addWidget(QLabel("异常共鸣", styleSheet="color:#0055AA; font-weight:bold; font-size: 10pt;"), 0, Qt.AlignmentFlag.AlignRight)
        header_layout_container.addLayout(header_right_box)
        
        header_layout.addLayout(header_layout_container)
        self.content_layout.addLayout(header_layout)

    def remove_all_cards(self) -> None:
        """清空当前所有技能卡片"""
        for card in self.cards[:]:
            self.remove_card(card)

    def load_defaults_for(self, anomaly_name: str) -> None:
        """根据异常名称加载默认的技能模版"""
        abilities = self.data.get("abilities", [])
        if self.data.get("anomaly") != anomaly_name or not abilities:
            abilities = ANOMALY_ABILITIES_DATA.get(anomaly_name, ANOMALY_ABILITIES_DATA.get("default", []))
        for ab_data in abilities:
            self.add_card(ab_data)

    def reset_to_anomaly(self, anomaly_name: str) -> None:
        """响应跨 Tab 联动的异常名称更新"""
        if hasattr(self, 'anomaly_name_label'):
            self.anomaly_name_label.setText(anomaly_name)
        self.remove_all_cards()
        self.load_defaults_for(anomaly_name)

    def add_card(self, data: Dict[str, Any]) -> None:
        card = AbilityCard(data)
        card.deleteRequested.connect(self.remove_card)
        self.cards.append(card)
        
        idx = self.content_layout.indexOf(self.add_btn)
        self.content_layout.insertWidget(idx, card)
        
    def remove_card(self, card_widget: QWidget) -> None:
        if card_widget in self.cards:
            self.cards.remove(card_widget)
            self.content_layout.removeWidget(card_widget)
            card_widget.deleteLater()

    def get_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return {"abilities": [card.get_data() for card in self.cards]}