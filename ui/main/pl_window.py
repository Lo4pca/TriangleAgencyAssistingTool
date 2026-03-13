import json
import datetime
import base64
import subprocess
import shlex
import time
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QTextBrowser, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QHBoxLayout, QSpinBox, QTabWidget,
    QMessageBox, QFileDialog, QTextEdit, QDialog, QFormLayout, 
    QLineEdit, QDialogButtonBox, QGroupBox, QApplication, QComboBox, QStackedWidget,
    QScrollArea, QMenu
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import Qt, QTimer, QUrl, QFileInfo, QFile, QIODevice, QSettings

from ui.character.editor import CharacterEditor
from ui.tools.dice_tool import DiceTool
from ui.tools.mission_report import MissionReportDialog
from ui.common.widgets import TeammateStatusWidget
from ui.common.dialogs import show_silent_info
from core.network.client import PLClient
from core.network.protocol import MsgType


class PLMainWindow(QMainWindow):
    """玩家端主控台窗口"""
    def __init__(self, game_name: str):
        super().__init__()
        self.game_name = game_name
        self.setWindowTitle(f"TA Assistant - PL - {game_name}")
        self.resize(1200, 800)

        self.game_dir = Path("data") / "PL" / self.game_name
        self.char_file = self.game_dir / "character.json"

        self.character_data = self.load_character()

        self._init_menu()

        self.doc_tabs = QTabWidget()
        self.doc_tabs.setTabsClosable(True)
        self.doc_tabs.tabCloseRequested.connect(self.close_doc_tab)
        self.home_page = QTextBrowser()
        self.home_page.setHtml("<div style='text-align:center; margin-top:50px; color:gray'><h3>等待接收文件...</h3></div>")
        self.doc_tabs.addTab(self.home_page, "文件接收")
        self.setCentralWidget(self.doc_tabs)

        self._init_docks()
        self.update_connection_ui(False)

        self.client = PLClient()
        self.pf_process: Optional[subprocess.Popen] = None
        self.setup_network()

        self.players: Dict[str, str] = {}
        self.full_players_list = []
        self.unread_uids = set()

        self._default_layout_state = self.saveState()
        self._default_geometry = self.saveGeometry()
        self.restore_window_layout()
    
    # ==========================
    # 网络协议处理与状态同步
    # ==========================
    def setup_network(self) -> None:
        self.client.chaos_updated.connect(self.on_server_chaos_sync)
        self.client.log_updated.connect(self.append_log)
        self.client.file_received.connect(self.on_file_received)
        self.client.loose_ends_updated.connect(self.on_loose_ends_sync)
        self.client.mission_report_sync.connect(self.on_report_sync)
        self.client.chat_received.connect(self.on_client_chat_received)
        self.client.players_updated.connect(self.on_players_updated)

        self.client.connected.connect(self.on_connected_success)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.error_occurred.connect(self.on_connection_error)
    
    def on_connected_success(self) -> None:
        self.update_connection_ui(True)
        self.append_log("<b>✅ 已成功连接到 GM 服务器！</b>")
        self.push_character_sheet()
    
    def on_disconnected(self) -> None:
        self.update_connection_ui(False)
        self.append_log("<span style='color:gray'>连接已断开</span>")

    def on_connection_error(self, error_msg: str) -> None:
        self.update_connection_ui(False)
        self.append_log(f"<span style='color:red'>❌ 连接错误: {error_msg}</span>")

    def push_character_sheet(self) -> None:
        name = self.character_data.get("name", "Unknown PL")
        self.client.send(MsgType.SHEET_UPDATE, {"name": name, "sheet": self.character_data})

    def on_server_chaos_sync(self, absolute_val: int) -> None:
        self.chaos_spin.blockSignals(True)
        self.chaos_spin.setValue(absolute_val)
        self.chaos_spin.blockSignals(False)
    
    def on_loose_ends_sync(self, val: int) -> None:
        self.le_display.setText(str(val))
    
    def on_report_sync(self, data: Dict[str, Any]) -> None:
        grade = data.get("final_grade", "")
        status = data.get("status", "Unknown")

        self.append_log(
            f"<div style='background-color:#222; border:1px solid #4CAF50; padding:5px; margin:5px 0;'>"
            f"<b>📨 收到 GM 返回的任务报告</b><br>"
            f"状态: {status} | 最终评级: <span style='color:#FFD700; font-weight:bold;'>{grade}</span><br>"
            f"</div>"
        )
        
        view_dialog = MissionReportDialog(self, game_name=self.game_name, data=data, is_gm=False)
        view_dialog.setWindowTitle("任务报告(已评级)")
        view_dialog.exec()

    def update_connection_ui(self, is_connected: bool) -> None:
        if is_connected:
            self.conn_status_lbl.setText("🟢 已连接 GM")
            self.conn_status_lbl.setStyleSheet("color: #55FF55; font-weight: bold;")
            self.disconnect_btn.setEnabled(True)
        else:
            self.conn_status_lbl.setText("🔴 未连接")
            self.conn_status_lbl.setStyleSheet("color: #FF5555; font-weight: bold;")
            self.disconnect_btn.setEnabled(False)

    # ==========================
    # 工具栏及组件调用
    # ==========================
    def open_character_editor(self) -> None:
        editor = CharacterEditor(self.game_name)
        if editor.exec():
            self.character_data = self.load_character()
            self.push_character_sheet()
            self.append_log("<i>角色卡已更新并同步。</i>")

    def open_dice_tool(self) -> None:
        self.character_data = self.load_character()
        dialog = DiceTool(self.game_name, self.character_data, self)
        dialog.dataChanged.connect(self.save_character)
        dialog.log_signal.connect(self.handle_dice_log)
        dialog.chaosSignal.connect(self.handle_dice_chaos) 
        dialog.show()

    def handle_dice_chaos(self, growth_value: int) -> None:
        self.chaos_spin.setValue(self.chaos_spin.value() + growth_value)
        self.client.send(MsgType.CHAOS_SYNC, growth_value)

    def handle_dice_log(self, html_content: str) -> None:
        name = self.character_data.get("name", "Unknown PL")
        full_log = f"<div style='border-left: 4px solid #0055AA; padding-left: 5px; margin: 5px 0;'><b>{name}</b> 进行了掷骰:<br>{html_content}</div>"
        self.append_log(full_log)
        self.client.send(MsgType.LOG_SYNC, full_log)

    def open_mission_report(self) -> None:
        dialog = MissionReportDialog(self, game_name=self.game_name)
        dialog.report_submitted.connect(self.send_mission_report)
        dialog.exec()

    def send_mission_report(self, data: Dict[str, Any]) -> None:
        self.client.send(MsgType.MISSION_REPORT, data)
        self.append_log("<b>已发送任务报告</b>")
    
    # ==========================================
    # 聊天系统 UI 与逻辑
    # ==========================================
    def _init_chat_dock(self):
        self.chat_dock = QDockWidget("文字聊天", self)
        self.chat_dock.setObjectName("PL_text_chat")
        self.chat_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 使用 QStackedWidget 管理多聊天浏览器
        self.chat_stack = QStackedWidget()
        self.chat_browsers: Dict[str, QTextBrowser] = {}

        # 公共聊天
        public_browser = QTextBrowser()
        public_browser.setOpenLinks(False)
        self.chat_browsers["ALL"] = public_browser
        self.chat_stack.addWidget(public_browser)
        layout.addWidget(self.chat_stack)
        
        input_layout = QHBoxLayout()
        self.chat_target_combo = QComboBox()
        self.chat_target_combo.addItem("ALL", "ALL")
        self.chat_target_combo.addItem("GM", "GM")
        self.chat_target_combo.currentIndexChanged.connect(self.on_chat_target_changed)
        input_layout.addWidget(self.chat_target_combo)

        self.export_chat_btn = QPushButton("导出")
        self.export_chat_btn.clicked.connect(self.show_chat_export_menu)
        input_layout.addWidget(self.export_chat_btn)
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入聊天内容...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.chat_input)
        
        self.send_chat_btn = QPushButton("发送")
        self.send_chat_btn.clicked.connect(self.send_chat_message)
        input_layout.addWidget(self.send_chat_btn)
        
        layout.addLayout(input_layout)
        self.chat_dock.setWidget(container)
        self.splitDockWidget(self.log_dock, self.chat_dock, Qt.Horizontal)
    
    def show_chat_export_menu(self):
        menu = QMenu(self)
        cur_act = menu.addAction("导出当前频道记录")
        all_act = menu.addAction("导出所有频道记录")
        
        action = menu.exec(self.export_chat_btn.mapToGlobal(self.export_chat_btn.rect().bottomLeft()))
        self.export_chat_history(all_channels=(action == all_act))
    
    def export_chat_history(self, all_channels: bool):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        if all_channels:
            content = ""
            for key, browser in self.chat_browsers.items():
                content += f"=== 频道: {key} ===\n"
                content += browser.toPlainText() + "\n\n"
            default_name = f"{self.game_name}_all_chats_{timestamp}.txt"
        else:
            browser = self.chat_stack.currentWidget()
            key_name = self.chat_target_combo.currentText().replace(" [未读]", "")
            content = f"=== 频道: {key_name} ===\n" + browser.toPlainText()
            default_name = f"{self.game_name}_{key_name}_chat_{timestamp}.txt"
            
        if not content.strip():
            show_silent_info(self, "提示", "聊天记录为空，无需导出。")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "导出聊天记录", default_name, "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.append_log(f"聊天记录已导出至: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))
    
    def jump_to_chat(self, target_uid: str):
        """从队友列表点击新消息后，自动跳转并聚焦"""
        idx = self.chat_target_combo.findData(target_uid)
        if idx >= 0:
            self.chat_target_combo.setCurrentIndex(idx)
        self.chat_dock.raise_()
        self.chat_input.setFocus()

    def on_chat_target_changed(self, idx: int) -> None:
        key_data = self.chat_target_combo.itemData(idx)
        if key_data in self.unread_uids:
            self.unread_uids.remove(key_data)
            self.refresh_teammate_and_dock_ui()
            
        key_name = self.chat_target_combo.itemText(idx).replace(" [未读]", "")
        browser = self._ensure_chat_browser_for_key(key_name)
        self.chat_stack.setCurrentWidget(browser)

    def _ensure_chat_browser_for_key(self, key: str) -> QTextBrowser:
        """确保存在以 key 标识的 QTextBrowser，PL 端 key 为 'ALL','GM' 或者对方名字"""
        if key in self.chat_browsers:
            return self.chat_browsers[key]
        browser = QTextBrowser()
        browser.setOpenLinks(False)
        self.chat_browsers[key] = browser
        self.chat_stack.addWidget(browser)
        return browser

    def refresh_teammate_and_dock_ui(self):
        """统一更新 UI，保持数据和视图同步"""
        my_name = self.character_data.get("name", "Unknown PL")
        # 1. 更新队友面板红点
        self.teammate_status_widget.update_status(self.full_players_list, my_name, self.unread_uids)
        
        # 2. 更新 Dock 标题 (处理 GM 发来的消息或被折叠的情况)
        if self.unread_uids:
            self.chat_dock.setWindowTitle("文字聊天 🔴 有新消息")
        else:
            self.chat_dock.setWindowTitle("文字聊天")
            
        # 3. 更新下拉框里的文本
        current_data = self.chat_target_combo.currentData()
        self.chat_target_combo.blockSignals(True)
        self.chat_target_combo.clear()
        
        gm_label = "GM [未读]" if "GM" in self.unread_uids else "GM"
        self.chat_target_combo.addItem("ALL", "ALL")
        self.chat_target_combo.addItem(gm_label, "GM")
        
        for uid, name in sorted(self.players.items(), key=lambda t: t[1].lower()):
            if name != my_name:
                display_name = f"{name} [未读]" if uid in self.unread_uids else name
                self.chat_target_combo.addItem(display_name, uid)
                
        idx = self.chat_target_combo.findData(current_data)
        self.chat_target_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.chat_target_combo.blockSignals(False)

    def on_players_updated(self, payload: dict) -> None:
        self.full_players_list = payload.get("players", []) if isinstance(payload, dict) else [] #full_players_list是完整的玩家列表，带有public_status，用于给widgets渲染状态
        new_map = {}
        for entry in self.full_players_list:
            uid = entry.get("uid")
            if uid: new_map[uid] = entry.get("name", "Unknown")
        self.players = new_map #而players只有uid与name的映射
        #但是似乎将两者合并也可以？
        my_name = self.character_data.get("name", "Unknown PL")
        for name in self.players.values():
            if name!="Unknown" and name!=my_name:
                self._ensure_chat_browser_for_key(name)

        self.refresh_teammate_and_dock_ui()

    def send_chat_message(self):
        text = self.chat_input.text().strip()
        if not text: return
        
        target = self.chat_target_combo.currentData()
        if target is None:
            target = "ALL"
        sender_name = self.character_data.get("name", "Player")
        
        msg_data = {
            "sender": sender_name,
            "target": target,
            "text": text
        }

        browser = self._ensure_chat_browser_for_key(self.chat_target_combo.currentText())
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        html = f"<span style='color:#888;'>[{time_str}]</span> <b style='color:#5DB7D7;'>{sender_name}</b>: {text}"
        browser.append(html)

        # 通过网络发送给服务端（服务器会负责把消息发送到目标或广播）
        self.client.send(MsgType.CHAT, msg_data)
        self.chat_input.clear()

    def on_client_chat_received(self, data: dict) -> None:
        """
        处理来自服务器的聊天消息。
        公共消息 target == "ALL" -> 显示在公共浏览器。
        私有消息（target != "ALL"） -> 在 PL 端以 sender 名字为 key 建立独立浏览器并显示。
        """
        target = data.get("target", "ALL")
        sender = data.get("sender", "Unknown")
        text = data.get("text", "")
        from_uid = data.get("from_uid", None)

        if from_uid and sender:
            self.players[from_uid] = sender
            self._ensure_chat_browser_for_key(sender)
        
        sender_data_key = "GM" if sender == "GM" else from_uid
        if target != "ALL" and self.chat_target_combo.currentData() != sender_data_key:
            self.unread_uids.add(sender_data_key)
            self.refresh_teammate_and_dock_ui()

        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        if target == "ALL":
            key="ALL"
        else:
            key=sender
        browser = self._ensure_chat_browser_for_key(key)
        if sender == "GM":
            color = "#C41E3A"
        else:
            color = "#F3A455"
        html = f"<span style='color:#888;'>[{time_str}]</span> <b style='color:{color};'>{sender}</b>: {text}"
        browser.append(html)
    
    # ==========================
    # 布局持久化
    # ==========================
    def save_window_layout(self):
        settings = QSettings("TA_Assistant", "PL_Layouts")
        settings.setValue("dock_state", self.saveState())
        settings.setValue("window_geometry", self.saveGeometry())
        show_silent_info(self, "布局已保存", "下次启动时将自动恢复目前的窗口布局。")

    def reset_window_layout(self):
        self.restoreState(self._default_layout_state)
        self.restoreGeometry(self._default_geometry)
        settings = QSettings("TA_Assistant", "PL_Layouts")
        settings.remove("dock_state")
        settings.remove("window_geometry")

    def restore_window_layout(self):
        settings = QSettings("TA_Assistant", "PL_Layouts")
        state = settings.value("dock_state")
        geo = settings.value("window_geometry")
        if state: self.restoreState(state)
        if geo: self.restoreGeometry(geo)

    # ==========================
    # UI 初始化
    # ==========================
    def _init_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开本地文件", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.manual_open_local_file)
        file_menu.addAction(open_action)
        
        tools_menu = menubar.addMenu("工具")
        char_action = QAction("角色卡编辑器", self)
        char_action.triggered.connect(self.open_character_editor)
        tools_menu.addAction(char_action)
        
        dice_action = QAction("掷骰工具", self)
        dice_action.triggered.connect(self.open_dice_tool)
        tools_menu.addAction(dice_action)

        report_action = QAction("填写任务报告", self)
        report_action.triggered.connect(self.open_mission_report)
        tools_menu.addAction(report_action)
        
        self.view_menu = menubar.addMenu("视图")
        self.view_menu.addSeparator()
        save_layout_act = QAction("保存当前布局", self)
        save_layout_act.triggered.connect(self.save_window_layout)
        self.view_menu.addAction(save_layout_act)
        
        reset_layout_act = QAction("重置为默认布局", self)
        reset_layout_act.triggered.connect(self.reset_window_layout)
        self.view_menu.addAction(reset_layout_act)

        net_menu = self.menuBar().addMenu("联机")
        conn_action = QAction("连接到 GM", self)
        conn_action.triggered.connect(self.show_connect_dialog)
        net_menu.addAction(conn_action)
        
    def _init_docks(self) -> None:
        # --- 1. Log Dock and Chat Dock ---
        self.log_dock = QDockWidget("游戏日志 & 控制台", self)
        self.log_dock.setObjectName("PL_public_logs")
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(5, 5, 5, 5)
        log_layout.setSpacing(5)
        
        toolbar_layout = QHBoxLayout()
        self.conn_status_lbl = QLabel("🔴 未连接")

        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.setFixedSize(80, 24)
        self.disconnect_btn.setEnabled(False) 
        self.disconnect_btn.clicked.connect(self.manual_disconnect)
        
        toolbar_layout.addWidget(self.conn_status_lbl)
        toolbar_layout.addWidget(self.disconnect_btn)
        toolbar_layout.addSpacing(10)

        prep_btn = QPushButton("重置状态")
        prep_btn.setToolTip("恢复所有 QA 至上限并清空燃尽")
        prep_btn.clicked.connect(self.do_mission_prep)
        toolbar_layout.addWidget(prep_btn)
        toolbar_layout.addStretch()

        le_lbl = QLabel("松散端:")
        le_lbl.setStyleSheet("color: #AAAAAA; font-weight: bold;")
        self.le_display = QLabel("0")
        self.le_display.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11pt; border: 1px solid #555; padding: 2px 6px; border-radius: 4px;")
        
        toolbar_layout.addWidget(le_lbl); toolbar_layout.addWidget(self.le_display); toolbar_layout.addSpacing(15)
        
        chaos_lbl = QLabel("混沌:")
        chaos_lbl.setStyleSheet("color: #FF5555; font-weight: bold;")
        self.chaos_spin = QSpinBox()
        self.chaos_spin.setRange(0, 999)
        self.chaos_spin.setStyleSheet("color: #FF5555; background: transparent; border: none; font-weight: bold; font-size: 11pt;")
        self.chaos_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.chaos_spin.setFixedWidth(40)
        self.chaos_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        dice_btn = QPushButton("🎲 掷骰")
        dice_btn.clicked.connect(self.open_dice_tool)

        toolbar_layout.addWidget(chaos_lbl); toolbar_layout.addWidget(self.chaos_spin); toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(dice_btn)
        
        log_layout.addLayout(toolbar_layout)
        
        self.log_widget = QTextBrowser()
        self.log_widget.setOpenLinks(False)  
        self.log_widget.setOpenExternalLinks(False)
        self.log_widget.anchorClicked.connect(self.open_local_link)
        log_layout.addWidget(self.log_widget)
        
        self.log_dock.setWidget(log_container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        self._init_chat_dock()

        # --- 2. Notes Dock ---
        self.notes_dock = QDockWidget("额外笔记", self)
        self.notes_dock.setObjectName("PL_notes")
        self.notes_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        notes_container = QWidget()
        notes_layout = QVBoxLayout(notes_container)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(2)
        
        self.notes_widget = QTextEdit()
        self.notes_widget.setPlaceholderText("笔记区域 (仅保存在本地)...")
        notes_layout.addWidget(self.notes_widget)

        export_btn = QPushButton("💾 导出笔记")
        export_btn.clicked.connect(lambda: self.export_text(self.notes_widget.toPlainText(), "notes", "txt"))
        notes_layout.addWidget(export_btn)
        
        self.notes_dock.setWidget(notes_container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.notes_dock)
        self.view_menu.addAction(self.notes_dock.toggleViewAction())

        # --- 3. Teammate Status Dock ---
        self.teammate_dock = QDockWidget("队友状态", self)
        self.teammate_dock.setObjectName("PL_teammates")
        self.teammate_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.teammate_dock.setMinimumWidth(120)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.teammate_status_widget = TeammateStatusWidget()
        self.teammate_status_widget.jump_chat_signal.connect(self.jump_to_chat)
        scroll.setWidget(self.teammate_status_widget)
        
        self.teammate_dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.teammate_dock)
        self.view_menu.addAction(self.teammate_dock.toggleViewAction())

    # ==========================
    # 文件 I/O 与 本地代理
    # ==========================
    def show_connect_dialog(self) -> None:
        settings = QSettings("TA_Assistant", "PL_Config")
        last_ip = settings.value("last_ip", "localhost")
        last_port = settings.value("last_port", 12345)
        use_gs = settings.value("use_gs", "false") == "true"
        gs_cmd_template = settings.value("gs_cmd", "gs-netcat -s TriangleAgency -p {port}")

        dialog = QDialog(self)
        dialog.setWindowTitle("连接服务器")
        dialog.setFixedWidth(400)
        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()
        ip_input = QLineEdit(last_ip)
        ip_input.setPlaceholderText("GM 的 IP 地址 (gsocket模式下忽略)")
        port_input = QSpinBox()
        port_input.setRange(1024, 65535)
        port_input.setValue(int(last_port))
        
        form_layout.addRow("服务器 IP:", ip_input)
        form_layout.addRow("端口号:", port_input)
        layout.addLayout(form_layout)

        gs_group = QGroupBox("高级 / 内网穿透")
        gs_group.setCheckable(True)
        gs_group.setChecked(use_gs)
        gs_layout = QVBoxLayout(gs_group)
        gs_layout.addWidget(QLabel("启动命令 ({port} 将被替换为上方端口):"))
        
        cmd_input = QLineEdit(gs_cmd_template)
        gs_layout.addWidget(cmd_input)
        gs_hint = QLabel("勾选此项后，将启动上述命令建立隧道，\n并尝试连接到 localhost:{port}")
        gs_hint.setStyleSheet("color: gray; font-size: 0.9em;")
        gs_layout.addWidget(gs_hint)
        layout.addWidget(gs_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec():
            ip = ip_input.text().strip()
            port = port_input.value()
            is_gs_mode = gs_group.isChecked()
            cmd_str = cmd_input.text().strip()
            
            settings.setValue("last_ip", ip)
            settings.setValue("last_port", port)
            settings.setValue("use_gs", "true" if is_gs_mode else "false")
            settings.setValue("gs_cmd", cmd_str)

            self.stop_proxy()
            self.client.disconnect_from_host()

            if is_gs_mode:
                self.start_proxy_connection(cmd_str, port)
            else:
                if not ip:
                    QMessageBox.warning(self, "错误", "IP 地址不能为空")
                    return
                self.append_log(f"正在尝试直连 {ip}:{port}...")
                self.client.connect_to_host(ip, port)

    def start_proxy_connection(self, cmd_template: str, port: int) -> None:
        final_cmd = cmd_template.replace("{port}", str(port))
        self.append_log(f"正在启动代理命令: <code>{final_cmd}</code>")
        
        try:
            import platform
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            self.pf_process = subprocess.Popen(shlex.split(final_cmd), creationflags=creation_flags)

            self.append_log("正在等待 gsocket 建立隧道 (约 2 秒)...")
            
            # 使用简单的事件循环阻塞等待
            t_end = time.time() + 2
            while time.time() < t_end:
                QApplication.processEvents()
                time.sleep(0.1)

            self.append_log(f"正在通过隧道连接 localhost:{port}...")
            self.client.connect_to_host("127.0.0.1", port)
            
        except Exception as e:
            self.append_log(f"<span style='color:red'>代理启动失败: {e}</span>")
            self.stop_proxy()

    def stop_proxy(self) -> None:
        if self.pf_process:
            try:
                self.pf_process.terminate()
                self.pf_process = None
                self.append_log("<i>已关闭本地代理进程</i>")
            except Exception as e:
                self.append_log(f"<span style='color:red'>关闭本地代理进程时出错: {e}</span>")
    
    def manual_disconnect(self) -> None:
        self.stop_proxy()
        self.client.disconnect_from_host()
        self.conn_status_lbl.setText("🔴 未连接")
        self.conn_status_lbl.setStyleSheet("color: red; font-weight: bold;")
        self.disconnect_btn.setEnabled(False)
        self.append_log("<i>已手动断开连接。</i>")

    def save_file(self, fname: str, content: bytes) -> Path:
        download_dir = Path("data") / "PL" / self.game_name / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        file_path = download_dir / fname
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path
    
    def on_file_received(self, fname: str, b64_content: str) -> None:
        try:
            data_bytes = base64.b64decode(b64_content)
            file_path = self.save_file(fname, data_bytes)
            file_uri = file_path.absolute().as_uri()

            self.append_log(f"📥 收到文件: <a href='{file_uri}'>{fname}</a> (已保存)")
            self.render_file(file_uri)
        except Exception as e:
            self.append_log(f"<span style='color:red'>文件处理失败: {e}</span>")

    def render_file(self, uri: Any) -> bool:
        if isinstance(uri, QUrl):
            file_path = uri.toLocalFile()
        else:
            file_path = QUrl(str(uri)).toLocalFile()
            
        file_info = QFileInfo(file_path)
        ext = file_info.suffix().lower()
        fname = file_info.fileName()

        if ext == 'jpg': ext = 'jpeg'

        image_types = {'png', 'jpeg', 'gif', 'bmp', 'svg'}
        text_types = {'txt', 'md', 'json', 'log', 'csv', 'py', 'ini', 'xml', 'yaml', 'yml'}

        file = QFile(file_path)
        if not file.open(QIODevice.OpenModeFlag.ReadOnly):
            self.append_log(f"<span style='color:red'>无法打开文件: {fname}</span>")
            return False

        raw = file.readAll()
        file.close()

        viewer = QTextBrowser()
        viewer.setOpenLinks(False)
        viewer.anchorClicked.connect(self.open_local_link)

        preview_successful = True
        if ext in image_types:
            b64 = base64.b64encode(bytes(raw)).decode('ascii')
            html_content = f"<div style='text-align:center; margin-top:10px;'><img src='data:image/{ext};base64,{b64}' style='max-width:100%;' /><p style='color:gray;'>{fname}</p></div>"
        elif ext in text_types:
            text_content = bytes(raw).decode('utf-8', errors='ignore')
            import html
            safe = html.escape(text_content)
            html_content = f"<div style='line-height:1.4; padding:10px;'><pre>{safe}</pre></div>"
        else:
            html_content = f"<div style='padding:20px; text-align:center;'><h3>无法预览此文件类型 ({ext})</h3><p>请点击日志中的URL，使用系统程序打开</p></div>"
            preview_successful = False

        viewer.setHtml(html_content)

        def add_tab():
            idx = self.doc_tabs.addTab(viewer, fname)
            self.doc_tabs.setCurrentIndex(idx)
            self.doc_tabs.setTabToolTip(idx, file_path)

        QTimer.singleShot(0, add_tab)
        return preview_successful

    def manual_open_local_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "打开文件", "", "All Files (*)")
        if path_str:
            self.render_file(QUrl.fromLocalFile(path_str))

    def export_text(self, content: str, suffix: str, ext: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{self.game_name}_{suffix}_{timestamp}.{ext}"
        save_dir = Path("data") / "PL" / self.game_name / "exported"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        file_path, _ = QFileDialog.getSaveFileName(self, f"保存 {suffix}", str(save_dir / default_name), f"{ext.upper()} Files (*.{ext});;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))

    def append_log(self, html_content: str) -> None:
        self.log_widget.append(html_content)

    def do_mission_prep(self) -> None:
        reply = QMessageBox.question(
            self, "确认准备", "这将把所有 QA 恢复到最大值，\n并清零'额外燃尽'。\n是否继续？", QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No: return

        qas = self.character_data["quality_assurances"]
        for key in qas:
            qas[key]["current"] = qas[key]["max"]
        self.character_data["additional_burnout"] = 0

        self.save_character()
        self.append_log("<i>已回满QA并清空燃尽</i>")

    def open_local_link(self, url: QUrl) -> None:
        if not self.render_file(url):
            QDesktopServices.openUrl(url)

    def close_doc_tab(self, index: int) -> None:
        if self.doc_tabs.count() > 0:
            self.doc_tabs.removeTab(index)

    # ==========================
    # 数据存取
    # ==========================
    def load_character(self) -> Dict[str, Any]:
        if not self.char_file.exists():
            return {}
        try:
            with open(self.char_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_character(self) -> None:
        self.char_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.char_file, "w", encoding="utf-8") as f:
            json.dump(self.character_data, f, ensure_ascii=False, indent=4)
        self.push_character_sheet()
    
    def closeEvent(self, event) -> None:
        self.stop_proxy()
        self.client.disconnect_from_host()
        super().closeEvent(event)