from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt

from ui.common.widgets import RelationshipCard

class RelationshipsTab(QWidget):
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
        self.content_layout.addLayout(self._create_header())
        
        # 黄色分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #E6B422; min-height: 2px;")
        self.content_layout.addWidget(sep)
        
        # --- 卡片区域 ---
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(15)
        self.content_layout.addLayout(self.cards_grid)
        
        # 加载数据
        saved_rels = self.data.get("relationships", [])
        if saved_rels:
            for rel_data in saved_rels:
                self.add_card(rel_data, refresh=False)
        else:
            for _ in range(4):
                self.add_card({}, refresh=False)
        self.refresh_grid()
            
        self.add_btn = QPushButton("+ 添加关系")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setStyleSheet("""
            QPushButton {
                border: 2px dashed #E6B422; color: #E6B422; 
                font-weight: bold; border-radius: 10px; font-size: 11pt;
            }
            QPushButton:hover { background-color: #F0EFF5; }
        """)
        self.add_btn.clicked.connect(lambda: self.add_card({}))
        self.content_layout.addWidget(self.add_btn)
        
        self.content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        self.update_network_count()

    def _create_header(self):
        layout = QHBoxLayout()
        
        # 左侧标题块
        title_box = QVBoxLayout()
        title_lbl = QLabel("人际关系")
        title_lbl.setStyleSheet("font-size: 24pt; font-weight: bold; color: #E6B422;")
        title_box.addWidget(title_lbl)
        
        # 计数器
        count_frame = QFrame()
        count_frame.setStyleSheet("QFrame { border: 2px solid #000044; border-radius: 5px; background: white; }QLabel { border: none; }")
        c_layout = QHBoxLayout(count_frame)
        c_layout.setContentsMargins(10, 5, 10, 5)
        
        c_layout.addWidget(QLabel("🌐", styleSheet="font-size:14pt; color:#E6B422;"))
        c_layout.addWidget(QLabel("网络化的人际关系", styleSheet="color:#E6B422; font-weight:bold; font-size:12pt;"))
        c_layout.addStretch()
        self.count_label = QLabel("0", styleSheet="color:#333; font-weight:bold; font-size:14pt;")
        c_layout.addWidget(self.count_label)
        
        title_box.addWidget(count_frame)
        layout.addLayout(title_box)
        layout.addStretch()
        
        # 右侧 R 标志
        r_box = QVBoxLayout()
        r_header = QHBoxLayout()
        r_icon = QLabel("R")
        r_icon.setStyleSheet("background-color:#E6B422;color:white;font-size:30pt;font-weight:bold;padding:5px 25px;border-radius:20px;")
        
        self.reality_name_label = QLabel(self.data.get("reality", "未选择"))
        self.reality_name_label.setStyleSheet("color:#E6B422; font-weight:bold; font-size: 14pt; margin-left: 10px;")
        
        r_header.addWidget(r_icon)
        r_header.addWidget(self.reality_name_label)
        
        r_box.addWidget(QLabel("现实身份", styleSheet="color:#E6B422; font-weight:bold; font-size:10pt;"), 0, Qt.AlignmentFlag.AlignRight)
        r_box.addLayout(r_header)
        layout.addLayout(r_box)
        
        return layout

    def add_card(self, data, refresh=True):
        card = RelationshipCard(data)
        card.deleteRequested.connect(self.remove_card)
        card.stateChanged.connect(self.update_network_count)
        self.cards.append(card)
        if refresh:
            self.refresh_grid()
            self.update_network_count()
        
    def remove_card(self, card_widget):
        if card_widget in self.cards:
            self.cards.remove(card_widget)
            card_widget.deleteLater()
            self.refresh_grid()
            self.update_network_count()

    def refresh_grid(self):
        while self.cards_grid.count():
            self.cards_grid.takeAt(0)

        for i, card in enumerate(self.cards):
            self.cards_grid.addWidget(card, i // 2, i % 2)

    def update_reality_name(self, name):
        if hasattr(self, 'reality_name_label'):
            self.reality_name_label.setText(name)

    def update_network_count(self):
        count = sum(1 for card in self.cards if card.is_networked())
        self.count_label.setText(str(count))

    def get_data(self):
        return {"relationships": [card.get_data() for card in self.cards]}