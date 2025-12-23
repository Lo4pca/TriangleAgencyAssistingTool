from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame,
    QInputDialog
)

from ui.common.widgets import CustomTrackCard

class CustomTracksTab(QWidget):
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
        title_box = QVBoxLayout()
        l1 = QLabel("自定义轨道")
        l1.setStyleSheet("font-size: 24pt; font-weight: bold; color: #554477;")
        l2 = QLabel("使用此页来创造特工或分部需要的额外轨道")
        l2.setStyleSheet("font-size: 10pt; color: #666;")
        title_box.addWidget(l1)
        title_box.addWidget(l2)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)
        
        # 紫色分割线
        purple_line = QFrame()
        purple_line.setFrameShape(QFrame.HLine)
        purple_line.setFrameShadow(QFrame.Plain)
        purple_line.setStyleSheet("background-color: #554477; min-height: 2px;")
        self.content_layout.addWidget(purple_line)

        self.add_btn = QPushButton("+ 添加自定义轨道")
        self.add_btn.setFixedHeight(45)
        self.add_btn.setStyleSheet("""
            QPushButton {
                border: 2px dashed #554477; color: #554477; 
                font-weight: bold; border-radius: 10px; font-size: 11pt;
            }
            QPushButton:hover { background-color: #F0EFF5; }
        """)
        self.add_btn.clicked.connect(self.prompt_add_card)
        self.content_layout.addWidget(self.add_btn)
        
        # --- 卡片区域 ---
        # 优先加载存档
        saved_tracks = self.data.get("custom_tracks", [])
        
        if saved_tracks:
            for track_data in saved_tracks:
                self.add_card(track_data)
        else:
            # 如果没有存档，初始化默认的几个轨道
            # 2个 15格，1个 30格
            defaults = [
                {"length": 15, "name": "", "max": ""},
                {"length": 15, "name": "", "max": ""},
                {"length": 30, "name": "", "max": ""},
                {"length": 5, "name": "", "max": ""}
            ]
            for d in defaults:
                self.add_card(d)
        
        self.content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def prompt_add_card(self):
        """弹出对话框询问轨道长度"""
        length, ok = QInputDialog.getInt(
            self, "添加轨道", 
            "请输入轨道格数 (例如 15, 30, 5):", 
            value=15, minValue=1, maxValue=100
        )
        if ok:
            self.add_card({"length": length})

    def add_card(self, data):
        card = CustomTrackCard(data)
        card.deleteRequested.connect(self.remove_card)
        self.cards.append(card)
        
        # 插入到按钮之前
        idx = self.content_layout.indexOf(self.add_btn)
        if idx != -1:
            self.content_layout.insertWidget(idx, card)
        else:
            self.content_layout.addWidget(card)
        
    def remove_card(self, card_widget):
        if card_widget in self.cards:
            self.cards.remove(card_widget)
            card_widget.deleteLater()

    def get_data(self):
        return {
            "custom_tracks": [card.get_data() for card in self.cards]
        }