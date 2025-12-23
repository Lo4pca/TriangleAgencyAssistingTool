import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QPushButton, 
    QHBoxLayout, QInputDialog, QMessageBox, QLabel
)

class GameSelectDialog(QDialog):
    def __init__(self, role, parent=None):
        super().__init__(parent)
        self.role = role
        self.selected_game = None
        self.GAMES_DIR = Path("data") / self.role
        
        self.setWindowTitle(f"选择游戏 ({self.role})")
        self.resize(450, 350)

        self._init_ui()
        self.refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(f"当前身份: {self.role}"))
        
        self.game_list = QListWidget()
        self.game_list.itemDoubleClicked.connect(self.on_confirm)
        layout.addWidget(self.game_list)

        btn_layout = QHBoxLayout()
        
        self.btn_new = QPushButton("新建游戏")
        self.btn_new.clicked.connect(self.create_game)
        
        self.btn_del = QPushButton("删除游戏")
        self.btn_del.setStyleSheet("color: red;")
        self.btn_del.clicked.connect(self.delete_game)
        
        self.btn_enter = QPushButton("进入游戏")
        self.btn_enter.setDefault(True)
        self.btn_enter.setStyleSheet("font-weight: bold;")
        self.btn_enter.clicked.connect(self.on_confirm)

        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_enter)
        
        layout.addLayout(btn_layout)

        self.btn_switch = QPushButton("← 返回切换身份")
        self.btn_switch.setFlat(True)
        self.btn_switch.clicked.connect(self.reject)
        layout.addWidget(self.btn_switch)

    def refresh_list(self):
        self.game_list.clear()
        if not self.GAMES_DIR.exists():
            self.GAMES_DIR.mkdir(parents=True, exist_ok=True)
        if self.GAMES_DIR.exists():
            for item in self.GAMES_DIR.iterdir():
                if item.is_dir():
                    self.game_list.addItem(item.name)

    def create_game(self):
        name, ok = QInputDialog.getText(self, "新建游戏", "请输入游戏名称:")
        if ok and name:
            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
            if not safe_name:
                QMessageBox.warning(self, "无效名称", "游戏名包含非字母数字字符或为空。")
                return

            path = self.GAMES_DIR / safe_name
            if path.exists():
                QMessageBox.warning(self, "错误", "该游戏名称已存在")
            else:
                path.mkdir(parents=True)
                self.refresh_list()

    def delete_game(self):
        item = self.game_list.currentItem()
        if not item: return
        
        game_name = item.text()
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要永久删除游戏 '{game_name}' 及其所有存档吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            path = self.GAMES_DIR / game_name
            try:
                shutil.rmtree(path)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "删除失败", str(e))

    def on_confirm(self):
        item = self.game_list.currentItem()
        if item:
            self.selected_game = item.text()
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请先选择一个游戏。")