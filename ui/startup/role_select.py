from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel

class RoleSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎")
        self.selected_role = None
        self.setFixedSize(300, 200)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("请选择你的身份:"))

        btn_pl = QPushButton("PL")
        btn_pl.clicked.connect(lambda: self.confirm_role("PL"))
        
        btn_gm = QPushButton("GM")
        btn_gm.clicked.connect(lambda: self.confirm_role("GM"))

        layout.addWidget(btn_pl)
        layout.addWidget(btn_gm)

    def confirm_role(self, role):
        self.selected_role = role
        self.accept()