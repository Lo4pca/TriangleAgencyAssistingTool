from pathlib import Path
import json
import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, 
    QCheckBox, QGroupBox, QTableWidget, QTableWidgetItem, QPushButton, 
    QHeaderView, QButtonGroup, QWidget, QScrollArea, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt, Signal

class MissionReportDialog(QDialog):
    report_submitted = Signal(dict)

    def __init__(self, parent=None, game_name="default", data=None, is_gm=False):
        super().__init__(parent)
        self.resize(900, 850)
        self.is_gm = is_gm
        self.game_name = game_name
        self.data = data or {}

        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.layout = QVBoxLayout(container)
        
        self._init_header()
        self._init_status_section()
        self._init_analysis_section()
        self._init_middle_section()
        self._init_objectives_section()
        self._init_footer_section()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        if self.data:
            self.load_data(self.data)

    def _init_header(self):
        title = QLabel("任务报告")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

    def _init_status_section(self):
        group = QGroupBox("异常状态")
        layout = QHBoxLayout(group)
        
        self.status_group = QButtonGroup(self)

        self.cb_neutralized = QCheckBox("中和 (无影响)")
        self.cb_captured = QCheckBox("捕获 (+3 嘉奖/人)")
        self.cb_escaped = QCheckBox("逃脱 (+3 处分/人)")
        self.cb_other = QCheckBox("其他:")
        
        self.status_group.addButton(self.cb_neutralized, 1)
        self.status_group.addButton(self.cb_captured, 2)
        self.status_group.addButton(self.cb_escaped, 3)
        self.status_group.addButton(self.cb_other, 4)
        
        self.other_input = QLineEdit()
        self.other_input.setPlaceholderText("说明...")
        
        layout.addWidget(self.cb_neutralized)
        layout.addWidget(self.cb_captured)
        layout.addWidget(self.cb_escaped)
        layout.addWidget(self.cb_other)
        layout.addWidget(self.other_input)
        
        self.layout.addWidget(group)

    def _init_analysis_section(self):
        group = QGroupBox("异常分析")
        layout = QVBoxLayout(group)
        
        self.analysis_fields = {}

        h_layout_alias = QHBoxLayout()
        lbl_alias = QLabel("代号:")
        lbl_alias.setFixedWidth(80)
        inp_alias = QLineEdit()
        h_layout_alias.addWidget(lbl_alias)
        h_layout_alias.addWidget(inp_alias)
        layout.addLayout(h_layout_alias)
        self.analysis_fields["alias"] = inp_alias

        multi_line_fields = ["行为", "焦点", "领域"]

        for label in multi_line_fields:
            h_layout = QHBoxLayout()
            
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(80)
            lbl.setAlignment(Qt.AlignTop) 
            
            inp = QTextEdit()
            inp.setMinimumHeight(70) 
            inp.setMaximumHeight(100)
            inp.setTabChangesFocus(True)
            
            h_layout.addWidget(lbl)
            h_layout.addWidget(inp)
            layout.addLayout(h_layout)
            self.analysis_fields[label.lower()] = inp
            
        self.layout.addWidget(group)

    def _init_middle_section(self):
        h_layout = QHBoxLayout()

        le_group = QGroupBox("松散端")
        le_layout = QVBoxLayout(le_group)
        self.le_table = QTableWidget(5, 3)
        self.le_table.setHorizontalHeaderLabels(["名字", "数量", "备注"])
        self.le_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.le_table.verticalHeader().setVisible(False)
        self.le_table.setAlternatingRowColors(True)
        le_layout.addWidget(self.le_table)

        btn_add_le = QPushButton("➕ 添加条目")
        btn_add_le.clicked.connect(lambda: self.add_table_row(self.le_table))
        le_layout.addWidget(btn_add_le)

        h_layout.addWidget(le_group, stretch=2)
        
        right_layout = QVBoxLayout()

        sup_group = QGroupBox("表现评估")
        sup_layout = QVBoxLayout(sup_group)
        
        self.sup_fields = {}
        for item in ["MVP","观察期"]:
            l_layout = QHBoxLayout()
            l_layout.addWidget(QLabel(f"{item}:"))
            inp = QLineEdit()
            l_layout.addWidget(inp)
            sup_layout.addLayout(l_layout)
            self.sup_fields[item.lower()] = inp
            
        sup_layout.addWidget(QLabel("参与人员:"))
        self.participation_edit = QTextEdit()
        self.participation_edit.setMaximumHeight(80)
        sup_layout.addWidget(self.participation_edit)
        right_layout.addWidget(sup_group)

        grade_group = QGroupBox("GM评分")
        grade_layout = QHBoxLayout(grade_group)
        grade_layout.addWidget(QLabel("最终等级:"))
        self.grade_input = QLineEdit()
        self.grade_input.setPlaceholderText("仅GM填写")
        if not self.is_gm:
            self.grade_input.setReadOnly(True)
        grade_layout.addWidget(self.grade_input)
        
        right_layout.addWidget(grade_group)
        
        h_layout.addLayout(right_layout, stretch=1)
        self.layout.addLayout(h_layout)

    def _init_objectives_section(self):
        group = QGroupBox("可选目标")
        layout = QVBoxLayout(group)
        
        self.obj_table = QTableWidget(3, 3)
        self.obj_table.setHorizontalHeaderLabels(["名称", "奖励", "特工"])
        self.obj_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.obj_table.verticalHeader().setVisible(False)
        self.obj_table.setAlternatingRowColors(True)
        layout.addWidget(self.obj_table)

        btn_add_obj = QPushButton("➕ 添加条目")
        btn_add_obj.clicked.connect(lambda: self.add_table_row(self.obj_table))
        layout.addWidget(btn_add_obj)
        
        self.layout.addWidget(group)

    def _init_footer_section(self):
        btn_layout = QHBoxLayout()

        import_btn = QPushButton("导入")
        import_btn.setToolTip("从本地加载保存的 JSON 报告文件")
        import_btn.clicked.connect(self.on_import_clicked)
        btn_layout.addWidget(import_btn)

        save_btn = QPushButton("保存到本地")
        save_btn.clicked.connect(self.on_save_clicked)
        btn_layout.addWidget(save_btn)

        btn_layout.addStretch()

        if self.is_gm:
            close_btn = QPushButton("关闭 / 提交更改")
            close_btn.clicked.connect(self.accept)
            btn_layout.addWidget(close_btn)
        else:
            send_btn = QPushButton("发送报告给 GM")
            send_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 15px; font-weight: bold;")
            send_btn.clicked.connect(self.on_send_clicked)
            btn_layout.addWidget(send_btn)
            
        self.layout.addLayout(btn_layout)
    
    def on_save_clicked(self):
        data = self.collect_data()

        save_dir = Path("data") / ("GM" if self.is_gm else "PL") / self.game_name / "mission_reports"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"mission_report_{timestamp}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存任务报告", str(save_dir / default_name), "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "成功", f"报告已保存至:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def on_import_clicked(self):
        target_dir = Path("data") / ("GM" if self.is_gm else "PL") / self.game_name / "mission_reports"
        if not target_dir.exists():
            target_dir = Path("data")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入任务报告", str(target_dir), "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.load_data(data)
                QMessageBox.information(self, "导入成功", f"已加载文件:\n{Path(file_path).name}")
                
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"无法读取或解析文件:\n{e}")

    def get_table_data(self, table):
        rows = []
        for r in range(table.rowCount()):
            row_data = []
            is_empty = True
            for c in range(table.columnCount()):
                item = table.item(r, c)
                text = item.text() if item else ""
                row_data.append(text)
                if text.strip(): is_empty = False
            if not is_empty:
                rows.append(row_data)
        return rows

    def set_table_data(self, table, data):
        table.setRowCount(max(len(data), 5))
        for r, row_data in enumerate(data):
            for c, text in enumerate(row_data):
                table.setItem(r, c, QTableWidgetItem(str(text)))

    def add_table_row(self, table):
        row_count = table.rowCount()
        table.insertRow(row_count)

    def on_send_clicked(self):
        reply = QMessageBox.question(self, "确认", "确定要提交此任务报告吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            data = self.collect_data()
            self.report_submitted.emit(data)
            self.accept()

    def collect_data(self):
        status_id = self.status_group.checkedId()
        status_map = {1: "Neutralized", 2: "Captured", 3: "Escaped", 4: "Other"}

        analysis_data = {}
        for k, widget in self.analysis_fields.items():
            if isinstance(widget, QLineEdit):
                analysis_data[k] = widget.text()
            else:
                analysis_data[k] = widget.toPlainText()

        return {
            "status": status_map.get(status_id, "Unknown"),
            "status_other": self.other_input.text(),
            "analysis": analysis_data,
            "loose_ends": self.get_table_data(self.le_table),
            "superlatives": {
                "mvp": self.sup_fields["mvp"].text(),
                "观察期": self.sup_fields["观察期"].text(),
                "participation": self.participation_edit.toPlainText()
            },
            "objectives": self.get_table_data(self.obj_table),
            "final_grade": self.grade_input.text()
        }

    def load_data(self, d):
        status = d.get("status", "")
        if status == "Neutralized": self.cb_neutralized.setChecked(True)
        elif status == "Captured": self.cb_captured.setChecked(True)
        elif status == "Escaped": self.cb_escaped.setChecked(True)
        elif status == "Other": 
            self.cb_other.setChecked(True)
            self.other_input.setText(d.get("status_other", ""))

        ana = d.get("analysis", {})
        for k, v in self.analysis_fields.items():
            v.setText(ana.get(k, ""))

        self.set_table_data(self.le_table, d.get("loose_ends", []))
        self.set_table_data(self.obj_table, d.get("objectives", []))

        sup = d.get("superlatives", {})
        self.sup_fields["mvp"].setText(sup.get("mvp", ""))
        self.sup_fields["观察期"].setText(sup.get("观察期", ""))
        self.participation_edit.setText(sup.get("participation", ""))

        self.grade_input.setText(d.get("final_grade", ""))