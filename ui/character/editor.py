import json
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QMessageBox, QWidget
)
from PySide6.QtCore import Qt

from ui.common.styles import GLOBAL_STYLE_SHEET
from ui.character.tabs.basic import BasicInfoTab
from ui.character.tabs.balance import WorkLifeBalanceTab
from ui.character.tabs.abilities import AbilitiesTab
from ui.character.tabs.requisitions import RequisitionsTab
from ui.character.tabs.relationships import RelationshipsTab
from ui.character.tabs.custom_tracks import CustomTracksTab

class CharacterDataManager:
    """角色卡数据管理器，负责文件的读取与保存"""
    
    @staticmethod
    def get_char_file_path(game_name: str) -> Path:
        return Path("data") / "pl" / game_name / "character.json"

    @classmethod
    def load_character(cls, game_name: str) -> Dict[str, Any]:
        path = cls.get_char_file_path(game_name)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading character: {e}")
            return {}

    @classmethod
    def save_character(cls, game_name: str, full_data: Dict[str, Any]) -> None:
        path = cls.get_char_file_path(game_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)


class CharacterEditor(QDialog):
    """角色卡综合编辑器窗口"""
    
    SAVE_BTN_STYLE = """
        QPushButton { background-color: #0055AA; color: white; font-weight: bold; border-radius: 4px; }
        QPushButton:hover { background-color: #0066CC; }
        QPushButton:pressed { background-color: #004488; }
    """

    def __init__(self, game_name: str, parent: QWidget = None):
        super().__init__(parent)
        
        self.game_name = game_name
        self.setWindowTitle(f"为 {game_name} 创建角色卡")
        self.setStyleSheet(GLOBAL_STYLE_SHEET)
        self.setMinimumSize(1100, 800)
        
        self.character_data = CharacterDataManager.load_character(self.game_name)
        self.init_ui()
        self._initialize_default_data_if_needed()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # 初始化各个 Tab
        self.basic_tab = BasicInfoTab(self.character_data)
        self.balance_tab = WorkLifeBalanceTab(self.character_data)
        self.abilities_tab = AbilitiesTab(self.character_data)
        self.requisitions_tab = RequisitionsTab(self.character_data)
        self.relationships_tab = RelationshipsTab(self.character_data)
        self.custom_tracks_tab = CustomTracksTab(self.character_data)
        
        self.tabs.addTab(self.basic_tab, "基本信息")
        self.tabs.addTab(self.balance_tab, "平衡工作/生活")
        self.tabs.addTab(self.abilities_tab, "异常技能")
        self.tabs.addTab(self.requisitions_tab, "补给与收益")
        self.tabs.addTab(self.relationships_tab, "人际关系")
        self.tabs.addTab(self.custom_tracks_tab, "自定义轨道")

        # 跨 Tab 联动信号绑定
        self.basic_tab.anomaly_combo.currentTextChanged.connect(self.abilities_tab.reset_to_anomaly)
        self.basic_tab.competency_combo.currentTextChanged.connect(self.requisitions_tab.reset_to_competency)
        self.basic_tab.reality_combo.currentTextChanged.connect(self.relationships_tab.update_reality_name)
        
        layout.addWidget(self.tabs)
        
        # 底部按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("保存角色卡")
        save_btn.setFixedSize(120, 40)
        save_btn.setStyleSheet(self.SAVE_BTN_STYLE)
        save_btn.clicked.connect(self.save_character)
        
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _initialize_default_data_if_needed(self) -> None:
        """如果角色是新建的（缺乏列表数据），根据当前选择加载默认模版"""
        if not self.character_data.get("abilities"):
            current_anomaly = self.basic_tab.anomaly_combo.currentText()
            self.abilities_tab.reset_to_anomaly(current_anomaly)
        
        if not self.character_data.get("requisitions"):
            current_competency = self.basic_tab.competency_combo.currentText()
            self.requisitions_tab.reset_to_competency(current_competency)

    def save_character(self) -> None:
        """收集所有 Tab 的数据并持久化"""
        full_data = {
            **self.basic_tab.get_data(), 
            **self.balance_tab.get_data(), 
            **self.abilities_tab.get_data(), 
            **self.requisitions_tab.get_data(),
            **self.relationships_tab.get_data(),
            **self.custom_tracks_tab.get_data()
        }

        try:
            CharacterDataManager.save_character(self.game_name, full_data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")