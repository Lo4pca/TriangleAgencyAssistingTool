from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt

from models.static_data import COMPETENCY_REQUISITIONS_DATA
from ui.common.widgets import RequisitionCard

class RequisitionsTab(QWidget):
    def __init__(self, character_data, parent=None):
        super().__init__(parent)
        self.data = character_data
        self.cards = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(20)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        # --- 标题区 ---
        header_layout = QHBoxLayout()
        
        # 左侧标题
        title_box = QVBoxLayout()
        l1 = QLabel("补给")
        l1.setStyleSheet("font-size: 24pt; font-weight: bold; color: #C41E3A;")
        l2 = QLabel("以及工作/生活收益")
        l2.setStyleSheet("font-size: 18pt; font-weight: bold; color: #C41E3A;")
        title_box.addWidget(l1)
        title_box.addWidget(l2)
        header_layout.addLayout(title_box)
        
        header_layout.addStretch()
        
        # 右侧标志
        c_icon = QLabel("C")
        c_icon.setStyleSheet("""
            background-color: #C41E3A; color: white; 
            font-size: 30pt; font-weight: bold; 
            padding: 5px 25px;
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
        """)
        
        # 公司职能名称
        current_competency = self.data.get("competency", "未选择")
        self.competency_name_label = QLabel(current_competency)
        self.competency_name_label.setStyleSheet("color:#C41E3A; font-weight:bold; font-size: 14pt; margin-left: 10px;")

        header_right_box = QHBoxLayout()
        header_right_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        header_right_box.addWidget(c_icon)
        header_right_box.addWidget(self.competency_name_label)
        
        header_right_container = QVBoxLayout()
        header_right_container.addWidget(QLabel("公司职能", styleSheet="color:#C41E3A; font-weight:bold; font-size: 10pt;"), 0, Qt.AlignmentFlag.AlignRight)
        header_right_container.addLayout(header_right_box)
        
        header_layout.addLayout(header_right_container)
        
        self.content_layout.addLayout(header_layout)
        
        # 红色的分割线
        red_line = QFrame()
        red_line.setFrameShape(QFrame.HLine)
        red_line.setFrameShadow(QFrame.Plain)
        red_line.setStyleSheet("background-color: #C41E3A; min-height: 2px;")
        self.content_layout.addWidget(red_line)
        
        # --- 卡片区域 ---
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(15)
        self.content_layout.addLayout(self.cards_grid)

        saved_requisitions = self.data.get("requisitions", [])
        if saved_requisitions:
            for req_data in saved_requisitions:
                self.add_card(req_data, refresh=False)
        
        self.refresh_grid()

        self.add_btn = QPushButton("+ 添加补给项")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setStyleSheet("""
            QPushButton {
                border: 2px dashed #C41E3A; color: #C41E3A; 
                font-weight: bold; border-radius: 10px; font-size: 11pt;
            }
            QPushButton:hover { background-color: #F0EFF5; }
        """)
        self.add_btn.clicked.connect(lambda: self.add_card({}))
        self.content_layout.addWidget(self.add_btn)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def add_card(self, data, refresh=True):
        card = RequisitionCard(data)
        card.deleteRequested.connect(self.remove_card)
        self.cards.append(card)
        if refresh:
            self.refresh_grid()
        
    def remove_card(self, card_widget):
        if card_widget in self.cards:
            self.cards.remove(card_widget)
            card_widget.deleteLater()
            self.refresh_grid()

    def remove_all_cards(self):
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()
        self.refresh_grid()

    def refresh_grid(self):
        while self.cards_grid.count():
            self.cards_grid.takeAt(0)
            
        for i, card in enumerate(self.cards):
            self.cards_grid.addWidget(card, i // 2, i % 2)

    def load_defaults_for(self, competency_name):
        """加载指定职能的补给"""
        requisitions=self.data.get("requisitions",[])
        if self.data.get("competency")!=competency_name or not requisitions:
            requisitions = COMPETENCY_REQUISITIONS_DATA.get(competency_name, COMPETENCY_REQUISITIONS_DATA.get("default", []))
        for req_data in requisitions:
            self.add_card(req_data)

    def reset_to_competency(self, competency_name):
        """
        切换职能时调用：
        1. 更新标题
        2. 清空当前列表
        3. 加载新职能的默认补给或用户保存的内容
        """
        if hasattr(self, 'competency_name_label'):
            self.competency_name_label.setText(competency_name)
        
        self.remove_all_cards()
        self.load_defaults_for(competency_name)

    def get_data(self):
        return {
            "requisitions": [card.get_data() for card in self.cards]
        }