import os
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QMessageBox
)
from ui.common.styles import GLOBAL_STYLE_SHEET
from ui.character.tabs.basic import BasicInfoTab
from ui.character.tabs.balance import WorkLifeBalanceTab
from ui.character.tabs.abilities import AbilitiesTab
from ui.character.tabs.requisitions import RequisitionsTab
from ui.character.tabs.relationships import RelationshipsTab
from ui.character.tabs.custom_tracks import CustomTracksTab

class CharacterEditor(QDialog):
    def __init__(self, game_name):
        super().__init__()
        self.game_name = game_name
        self.setWindowTitle(f"为 {game_name} 创建角色卡")
        self.setStyleSheet(GLOBAL_STYLE_SHEET)
        self.setMinimumWidth(1100)
        self.setMinimumHeight(800)

        self.SAVE_BTN_STYLE = """
            QPushButton {
                background-color: #0055AA; color: white; 
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0066CC; }
            QPushButton:pressed { background-color: #004488; }
        """
        
        self.character_data = self.load_character()
        self.tabs = QTabWidget()
        
        # 初始化 Tabs
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

        self.basic_tab.anomaly_combo.currentTextChanged.connect(self.on_anomaly_changed)
        self.basic_tab.competency_combo.currentTextChanged.connect(self.on_competency_changed)
        self.basic_tab.reality_combo.currentTextChanged.connect(self.on_reality_changed)
        
        # 主布局
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("保存角色卡")
        save_btn.setFixedSize(120, 40)
        save_btn.setStyleSheet(self.SAVE_BTN_STYLE)
        save_btn.clicked.connect(self.save_character)
        
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

        if not self.character_data.get("abilities"):
            current_anomaly = self.basic_tab.anomaly_combo.currentText()
            self.abilities_tab.reset_to_anomaly(current_anomaly)
        
        if not self.character_data.get("requisitions"):
            current_competency = self.basic_tab.competency_combo.currentText()
            self.requisitions_tab.reset_to_competency(current_competency)
    
    def _get_char_file_path(self) -> Path:
        return Path("data") / "pl" / self.game_name / "character.json"

    def on_anomaly_changed(self, new_anomaly_name):
        self.abilities_tab.reset_to_anomaly(new_anomaly_name)
    
    def on_competency_changed(self, new_competency_name):
        self.requisitions_tab.reset_to_competency(new_competency_name)
    
    def on_reality_changed(self, new_val):
        self.relationships_tab.update_reality_name(new_val)

    def save_character(self):
        data_basic = self.basic_tab.get_data()
        data_balance = self.balance_tab.get_data()
        data_abilities = self.abilities_tab.get_data()
        data_requisitions = self.requisitions_tab.get_data()
        data_relationships = self.relationships_tab.get_data()
        data_custom = self.custom_tracks_tab.get_data()
        
        full_data = {
            **data_basic, 
            **data_balance, 
            **data_abilities, 
            **data_requisitions,
            **data_relationships,
            **data_custom
        }

        try:
            path = self._get_char_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(full_data, f, ensure_ascii=False, indent=4)
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def load_character(self):
        path = self._get_char_file_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading character: {e}")
            return {}