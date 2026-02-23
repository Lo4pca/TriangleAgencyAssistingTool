from typing import Optional
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QWidget
from PySide6.QtCore import Qt

class RoleSelectDialog(QDialog):
    """启动时的身份选择弹窗 (GM / PL)"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("欢迎")
        self.selected_role: Optional[str] = None
        
        self.setFixedSize(300, 200)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("请选择你的身份:"))

        btn_pl = QPushButton("PL")
        btn_pl.clicked.connect(lambda: self.confirm_role("PL"))
        
        btn_gm = QPushButton("GM")
        btn_gm.clicked.connect(lambda: self.confirm_role("GM"))

        layout.addWidget(btn_pl)
        layout.addWidget(btn_gm)

    def confirm_role(self, role: str) -> None:
        self.selected_role = role
        self.accept()