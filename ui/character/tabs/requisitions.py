from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt

from models.static_data import COMPETENCY_REQUISITIONS_DATA
from ui.common.widgets import RequisitionCard

class RequisitionsTab(QWidget):
    """补给与收益管理标签页"""

    def __init__(self, character_data: Dict[str, Any], parent: QWidget = None):
        super().__init__(parent)
        self.data = character_data
        self.cards: List[RequisitionCard] = []
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
        
        red_line = QFrame()
        red_line.setFrameShape(QFrame.HLine)
        red_line.setStyleSheet("background-color: #C41E3A; min-height: 2px;")
        self.content_layout.addWidget(red_line)
        
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(15)
        self.content_layout.addLayout(self.cards_grid)

        saved_requisitions = self.data.get("requisitions", [])
        for req_data in saved_requisitions:
            self.add_card(req_data, refresh=False)
        self.refresh_grid_layout()

        self.add_btn = QPushButton("+ 添加补给项")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setStyleSheet("""
            QPushButton { border: 2px dashed #C41E3A; color: #C41E3A; font-weight: bold; border-radius: 10px; font-size: 11pt; }
            QPushButton:hover { background-color: #F0EFF5; }
        """)
        self.add_btn.clicked.connect(lambda: self.add_card({}))
        self.content_layout.addWidget(self.add_btn)
        
        self.content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _init_header(self) -> None:
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        l1 = QLabel("补给")
        l1.setStyleSheet("font-size: 24pt; font-weight: bold; color: #C41E3A;")
        l2 = QLabel("以及工作/生活收益")
        l2.setStyleSheet("font-size: 18pt; font-weight: bold; color: #C41E3A;")
        title_box.addWidget(l1); title_box.addWidget(l2)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        c_icon = QLabel("C")
        c_icon.setStyleSheet("background-color: #C41E3A; color: white; font-size: 30pt; font-weight: bold; padding: 5px 25px; border-top-left-radius: 20px; border-top-right-radius: 20px;")
        
        current_competency = self.data.get("competency", "未选择")
        self.competency_name_label = QLabel(current_competency)
        self.competency_name_label.setStyleSheet("color:#C41E3A; font-weight:bold; font-size: 14pt; margin-left: 10px;")

        header_right_box = QHBoxLayout()
        header_right_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        header_right_box.addWidget(c_icon); header_right_box.addWidget(self.competency_name_label)
        
        header_right_container = QVBoxLayout()
        header_right_container.addWidget(QLabel("公司职能", styleSheet="color:#C41E3A; font-weight:bold; font-size: 10pt;"), 0, Qt.AlignmentFlag.AlignRight)
        header_right_container.addLayout(header_right_box)
        
        header_layout.addLayout(header_right_container)
        self.content_layout.addLayout(header_layout)

    def add_card(self, data: Dict[str, Any], refresh: bool = True) -> None:
        card = RequisitionCard(data)
        card.deleteRequested.connect(self.remove_card)
        self.cards.append(card)
        if refresh:
            self.refresh_grid_layout()
        
    def remove_card(self, card_widget: QWidget) -> None:
        if card_widget in self.cards:
            self.cards.remove(card_widget)
            self.cards_grid.removeWidget(card_widget)
            card_widget.deleteLater()
            self.refresh_grid_layout()

    def remove_all_cards(self) -> None:
        for card in self.cards:
            self.cards_grid.removeWidget(card)
            card.deleteLater()
        self.cards.clear()

    def refresh_grid_layout(self) -> None:
        """排列网格中的卡片"""
        for i, card in enumerate(self.cards):
            self.cards_grid.addWidget(card, i // 2, i % 2)

    def load_defaults_for(self, competency_name: str) -> None:
        """加载指定职能的补给"""
        requisitions = self.data.get("requisitions", [])
        if self.data.get("competency") != competency_name or not requisitions:
            requisitions = COMPETENCY_REQUISITIONS_DATA.get(competency_name, COMPETENCY_REQUISITIONS_DATA.get("default", []))
        for req_data in requisitions:
            self.add_card(req_data)

    def reset_to_competency(self, competency_name: str) -> None:
        if hasattr(self, 'competency_name_label'):
            self.competency_name_label.setText(competency_name)
        self.remove_all_cards()
        self.load_defaults_for(competency_name)

    def get_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return {"requisitions": [card.get_data() for card in self.cards]}