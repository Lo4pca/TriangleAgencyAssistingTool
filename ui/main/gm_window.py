import subprocess
import shlex
import base64
import html
import time
from pathlib import Path
import datetime
from typing import Dict, Any, Optional, Tuple

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QTextEdit, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QHBoxLayout, QListWidget, QSpinBox, 
    QTabWidget, QFileDialog, QMessageBox, QSplitter,
    QDialog, QListWidgetItem, QMenu, QInputDialog, QTextBrowser,
    QComboBox, QLineEdit
)
from PySide6.QtGui import QAction, QDropEvent, QDragEnterEvent
from PySide6.QtCore import Qt, QFileInfo, QSettings, QUrl

from core.network.server import GMServer
from core.network.protocol import MsgType

from ui.character.tabs.basic import BasicInfoTab
from ui.character.tabs.balance import WorkLifeBalanceTab
from ui.character.tabs.abilities import AbilitiesTab
from ui.character.tabs.requisitions import RequisitionsTab
from ui.character.tabs.relationships import RelationshipsTab
from ui.character.tabs.custom_tracks import CustomTracksTab
from ui.common.styles import GLOBAL_STYLE_SHEET

from ui.tools.weather_tool import WeatherTool
from ui.tools.dice_tool import DiceTool
from ui.tools.mission_report import MissionReportDialog


class DragDropEditor(QTextEdit):
    """支持拖拽本地文件进行预览的文档编辑器"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("主文档区域\n\n您可以直接将图片、文本文件拖入此处查看...")
        
    def canInsertFromMimeData(self, source) -> bool:
        if source.hasUrls() or source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if file_path:
                    self.process_file(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def process_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists(): return

        info = QFileInfo(file_path)
        ext = info.suffix().lower()
        filename = info.fileName()

        img_exts = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp'}
        txt_exts = {'txt', 'md', 'json', 'py', 'log', 'ini', 'yaml'}

        if ext in img_exts:
            html_img = f"""
            <div style='margin: 10px 0;'>
                <img src='{path.as_uri()}' style='max-width: 100%; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.3);'>
                <div style='color: gray; font-size: 0.8em; text-align: center;'>{filename}</div>
            </div><br>
            """
            self.insertHtml(html_img)
            self.append("")

        elif ext in txt_exts:
            try:
                content = path.read_text(encoding='utf-8', errors='replace')
                safe_content = html.escape(content)
                html_txt = f"""
                <div style='background-color: #333; color: #eee; padding: 10px; border-radius: 5px; margin: 10px 0;'>
                    <div style='border-bottom: 1px solid #555; margin-bottom: 5px; font-weight: bold;'>📄 {filename}</div>
                    <pre style='white-space: pre-wrap;'>{safe_content}</pre>
                </div><br>
                """
                self.insertHtml(html_txt)
                self.append("")
            except Exception as e:
                self.append(f"[读取文件失败: {filename} - {e}]")
        else:
            self.append(f"无法识别的文件格式: {file_path}")


class CharacterViewerDialog(QDialog):
    """供 GM 实时查看玩家角色卡的只读窗口"""
    def __init__(self, char_name: str, char_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.setWindowTitle(f"角色卡查看: {char_name}")
        self.resize(1000, 700)
        self.setStyleSheet(GLOBAL_STYLE_SHEET)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # 复用 PL 端的 Tab 组件，但不对外暴露保存功能
        self.tabs.addTab(BasicInfoTab(char_data, self), "基本信息")
        self.tabs.addTab(WorkLifeBalanceTab(char_data, self), "平衡")
        self.tabs.addTab(AbilitiesTab(char_data, self), "能力")
        self.tabs.addTab(RequisitionsTab(char_data, self), "补给")
        self.tabs.addTab(RelationshipsTab(char_data, self), "关系")
        self.tabs.addTab(CustomTracksTab(char_data, self), "自定义")
        
        layout.addWidget(self.tabs)


class GMMainWindow(QMainWindow):
    """GM 主控台窗口"""
    
    def __init__(self, game_name: str):
        super().__init__()
        self.game_name = game_name
        self.setWindowTitle(f"TA Assistant - GM Control - {game_name}")
        self.resize(1400, 900)
        
        self.server = GMServer()

        # 缓存系统
        self.players_data: Dict[str, Dict[str, Any]] = {} 
        self.mission_reports_cache: Dict[str, Dict[str, Any]] = {}
        
        self.doc_window_count = 0
        self.pf_process: Optional[subprocess.Popen] = None

        self._init_menu()
        self._init_ui()
        self.setup_server_signals()

        self.net_update = True

    # ==========================
    # 网络层信号处理
    # ==========================
    def setup_server_signals(self) -> None:
        self.server.log_received.connect(self.append_log)
        self.server.chaos_received.connect(self.sync_chaos)
        self.server.player_connected.connect(self.on_player_connected)
        self.server.player_disconnected.connect(self.on_player_disconnected)
        self.server.sheet_received.connect(self.update_pl_sheet)
        self.server.mission_report_received.connect(self.on_mission_report_received)
        self.server.chat_received.connect(lambda data: self.append_chat_message(data["sender"], data["text"]))

    def on_player_connected(self, uid: str, ip: str) -> None:
        self.log_system(f"新连接: {ip} (ID: {uid})")
        item = QListWidgetItem(f"⏳ 连接中... ({ip})")
        item.setData(Qt.UserRole, uid) 
        self.pl_list.addItem(item)

        self.players_data[uid] = {
            "name": "Unknown",
            "sheet": {},
            "item": item
        }

    def on_player_disconnected(self, uid: str) -> None:
        self.log_system(f"❌ 玩家断开: {self.players_data[uid]['name']} ({uid})")
        if uid in self.players_data:
            row = self.pl_list.row(self.players_data[uid]['item'])
            if row != -1:
                self.pl_list.takeItem(row)
            # 注意：故意不在此处删除数据，以保留玩家离线时的最后状态

    def update_pl_sheet(self, uid: str, name: str, sheet_data: Dict[str, Any]) -> None:
        if uid not in self.players_data:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, uid)
            self.pl_list.addItem(item)
            self.players_data[uid] = {"item": item}

        player_record = self.players_data[uid]
        old_name = player_record.get("name", "Unknown")
        item = player_record["item"]

        player_record["name"] = name
        player_record["sheet"] = sheet_data
        item.setText(name)

        if old_name == "Unknown":
            self.log_system(f"接收到新角色卡: {name}")
        elif old_name != name:
            self.log_system(f"玩家 {old_name} 改名为 {name}")
        else:
            self.log_system(f"{name} 更新了角色卡数据")

    # ==========================
    # UI 初始化与交互
    # ==========================
    def _init_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开文件 (插入主文档)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.manual_open_file)
        file_menu.addAction(open_action)

        view_menu = menubar.addMenu("视图")
        new_doc_action = QAction("新建文档窗口", self)
        new_doc_action.setShortcut("Ctrl+N")
        new_doc_action.triggered.connect(self.create_doc_window)
        view_menu.addAction(new_doc_action)

        config_menu = menubar.addMenu("配置")
        pf_action = QAction("设置端口转发命令...", self)
        pf_action.setStatusTip("设置服务器启动时自动运行的外部命令")
        pf_action.triggered.connect(self.set_port_forwarding_cmd)
        config_menu.addAction(pf_action)

        tools_menu = menubar.addMenu("工具")
        dice_action = QAction("掷骰工具", self)
        dice_action.setShortcut("Ctrl+D")
        dice_action.triggered.connect(self.open_dice_tool)
        tools_menu.addAction(dice_action)

        weather_action = QAction("松散端与天气", self)
        weather_action.triggered.connect(self.open_weather_tool)
        tools_menu.addAction(weather_action)

    def _init_ui(self) -> None:
        self.main_doc_viewer = DragDropEditor()
        self.setCentralWidget(self.main_doc_viewer)

        self.left_dock = QDockWidget("GM 控制台", self)
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- Top: Network ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 5, 5, 5)
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(12345)
        h_layout.addWidget(self.port_spin)
        
        self.btn_server = QPushButton("启动服务器")
        self.btn_server.clicked.connect(self.toggle_server)
        h_layout.addWidget(self.btn_server)
        top_layout.addLayout(h_layout)

        weather_btn = QPushButton("松散端与天气")
        weather_btn.clicked.connect(self.open_weather_tool)
        top_layout.addWidget(weather_btn)
        
        top_layout.addWidget(QLabel("在线玩家 (双击查看):"))
        self.pl_list = QListWidget()
        self.pl_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pl_list.customContextMenuRequested.connect(self.show_pl_context_menu)
        self.pl_list.itemDoubleClicked.connect(self.on_pl_double_clicked)
        top_layout.addWidget(self.pl_list)
        
        send_file_btn = QPushButton("向所有 PL 发送文件")
        send_file_btn.clicked.connect(self.send_file_to_all)
        top_layout.addWidget(send_file_btn)
        
        # --- Bottom: Notes ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        
        bottom_layout.addWidget(QLabel("GM 笔记:"))
        self.gm_notes = QTextEdit()
        self.gm_notes.setPlaceholderText("在此记录任何有用的信息...")
        bottom_layout.addWidget(self.gm_notes)

        export_btn = QPushButton("💾 导出笔记")
        export_btn.clicked.connect(self.export_gm_notes)
        bottom_layout.addWidget(export_btn)
        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        left_layout.addWidget(splitter)
        self.left_dock.setWidget(left_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)

        # --- Right Dock: Logs ---
        self.log_dock = QDockWidget("公共日志 & 混沌", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        
        chaos_layout = QHBoxLayout()
        chaos_layout.addWidget(QLabel("当前混沌:"))
        self.chaos_spin = QSpinBox()
        self.chaos_spin.setRange(0, 999)
        self.chaos_spin.valueChanged.connect(self.broadcast_chaos)
        chaos_layout.addWidget(self.chaos_spin)
        log_layout.addLayout(chaos_layout)
        
        self.log_widget = QTextBrowser()
        self.log_widget.setOpenLinks(False)
        self.log_widget.anchorClicked.connect(self.on_log_link_clicked)
        log_layout.addWidget(self.log_widget)
        
        self.log_dock.setWidget(log_container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_dock)

        self._init_chat_dock()

    def on_pl_double_clicked(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        if uid in self.players_data:
            p_data = self.players_data[uid]
            name = p_data["name"]
            sheet = p_data["sheet"]
            if sheet:
                viewer = CharacterViewerDialog(name, sheet, self)
                viewer.show()
            else:
                self.log_system("该玩家尚未发送角色卡数据。")

    def create_doc_window(self) -> None:
        self.doc_window_count += 1
        dock_title = f"文档查看器 {self.doc_window_count}"
        new_dock = QDockWidget(dock_title, self)
        new_dock.setAttribute(Qt.WA_DeleteOnClose)
        new_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        editor = DragDropEditor()
        editor.setPlaceholderText(f"{dock_title}")
        new_dock.setWidget(editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, new_dock)

    def log_system(self, msg: str) -> None:
        self.append_log(f"<span style='color:gray'>[SYSTEM] {msg}</span>")
        
    def append_log(self, html_msg: str) -> None:
        self.log_widget.append(html_msg)

    # ==========================
    # 业务广播与状态同步
    # ==========================
    def sync_chaos(self, val: int) -> None:
        self.net_update = True
        self.chaos_spin.blockSignals(True)
        self.chaos_spin.setValue(self.chaos_spin.value() + val)
        self.chaos_spin.blockSignals(False)
        self.broadcast_chaos()
        self.net_update = False

    def broadcast_chaos(self) -> None:
        self.server.send_to_all(MsgType.CHAOS_SYNC, self.chaos_spin.value())
        if not self.net_update:
            log_msg = f"<span style='color: #FF5722;'>⚠️ GM 修改了混沌值 -> {self.chaos_spin.value()}</span>"
            self.append_log(log_msg) 
            self.server.send_to_all(MsgType.LOG_SYNC, log_msg)
    
    def prepare_sending_file(self, prompt: str) -> Tuple[Optional[Path], Optional[str]]:
        path_str, _ = QFileDialog.getOpenFileName(self, prompt)
        if not path_str:
            return None, None
            
        path = Path(path_str)
        try:
            with open(path, "rb") as f:
                content = f.read()
            
            if len(content) > 10 * 1024 * 1024:
                reply = QMessageBox.question(self, "文件过大", "文件超过10MB，发送可能会导致卡顿。是否继续？", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return None, None

            b64_str = base64.b64encode(content).decode('utf-8')
            return path, b64_str
        except Exception as e:
            QMessageBox.critical(self, "打开文件时发生错误", str(e))
            return None, None

    def send_file_to_all(self) -> None:
        try:
            path, b64_str = self.prepare_sending_file("选择文件")
            if path and b64_str:
                self.server.send_to_all(MsgType.FILE_SEND, {"name": path.name, "content": b64_str})
                self.log_system(f"已发送文件: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "发送文件时发生错误", str(e))
    
    def send_file_private(self, target_uid: str, target_name: str) -> None:
        try:
            path, b64_str = self.prepare_sending_file(f"选择文件发送给 {target_name}")
            if path and b64_str:
                self.server.send_to(target_uid, MsgType.FILE_SEND, {"name": path.name, "content": b64_str})
                self.log_system(f"已向 {target_name} 发送文件: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "发送错误", str(e))
    
    def manual_open_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", 
            "All Files (*);;Images (*.png *.jpg *.jpeg *.gif);;Text (*.txt *.md *.json)"
        )
        if path_str:
            self.main_doc_viewer.process_file(path_str)

    def export_gm_notes(self) -> None:
        content = self.gm_notes.toPlainText()
        if not content:
            QMessageBox.information(self, "提示", "笔记内容为空。")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{self.game_name}_gm_notes_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(self, "导出笔记", default_name, "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log_system(f"笔记已导出至: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def show_pl_context_menu(self, pos) -> None:
        item = self.pl_list.itemAt(pos)
        if not item: return
            
        uid = item.data(Qt.UserRole)
        name = item.text()
        
        menu = QMenu()
        send_action = menu.addAction(f"📤 发送文件给: {name}")
        send_action.triggered.connect(lambda: self.send_file_private(uid, name))
        menu.exec(self.pl_list.mapToGlobal(pos))

    # ==========================
    # 工具栏及组件调用
    # ==========================
    def open_weather_tool(self) -> None:
        self.weather_tool = WeatherTool(self.game_name, self)
        self.weather_tool.broadcast_signal.connect(self.broadcast_weather_log)
        self.weather_tool.local_log_signal.connect(self.append_log)
        self.weather_tool.loose_ends_signal.connect(self.broadcast_loose_ends)
        self.weather_tool.show()

    def broadcast_weather_log(self, html_content: str) -> None:
        self.append_log(f"<span style='color:blue'>[已广播天气日志]</span><br>")
        self.server.send_to_all(MsgType.LOG_SYNC, html_content)
    
    def broadcast_loose_ends(self, val: int) -> None:
        self.server.send_to_all(MsgType.LOOSE_ENDS, val)
    
    def open_dice_tool(self) -> None:
        dialog = DiceTool(self.game_name, {}, self)
        dialog.log_signal.connect(lambda html_content: self.append_log(f"<b>[GM]</b> 进行了掷骰:<br>{html_content}</div>"))
        dialog.show()

    def on_mission_report_received(self, uid: str, data: Dict[str, Any]) -> None:
        player_name = self.players_data.get(uid, {}).get("name", "Unknown Agent")
        report_id = f"rep_{uid}_{int(time.time())}"

        self.mission_reports_cache[report_id] = {
            "uid": uid,
            "name": player_name, 
            "data": data
        }
        
        self.log_system(f"收到来自 {player_name} 的任务报告")

        status = data.get('status', 'N/A')
        grade = data.get('final_grade', '未评分')
        
        html_link = f"""
        <div style='background-color: #3d3d3d; border-left: 5px solid #673AB7; padding: 8px; margin: 5px 0; color: #EEE;'>
            <b>📄 任务报告 ({player_name})</b><br>
            <span style='font-size:0.9em; color: #AAA;'>状态: {status} | 当前评级: {grade}</span><br>
            <a href='report:{report_id}' style='color: #81C784; font-weight:bold; text-decoration: none;'>
               [点击查看详情 & 评分]
            </a>
        </div>
        """
        self.append_log(html_link)
    
    def on_log_link_clicked(self, url: QUrl) -> None:
        if url.scheme() == "report":
            report_id = url.path()
            if report_id in self.mission_reports_cache:
                info = self.mission_reports_cache[report_id]
                self.open_mission_report_viewer(report_id, info)

    def open_mission_report_viewer(self, report_id: str, info: Dict[str, Any]) -> None:
        dialog = MissionReportDialog(self, game_name=self.game_name, data=info["data"], is_gm=True)
        dialog.setWindowTitle(f"任务报告评分 - {info['name']}")

        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.collect_data()
            self.mission_reports_cache[report_id]["data"] = updated_data

            reply = QMessageBox.question(self, "同步", f"是否将评分后的报告发回给 {info['name']}?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                target_uid = info["uid"]
                self.server.send_to(target_uid, MsgType.MISSION_REPORT, updated_data)
                self.log_system(f"已更新报告并发送给 {info['name']} (评级: {updated_data.get('final_grade', '无')})")
    
    # ==========================================
    # 聊天系统 UI 与逻辑
    # ==========================================
    def _init_chat_dock(self):
        """初始化右下角的聊天窗口"""
        self.chat_dock = QDockWidget("文字聊天", self)
        self.chat_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)

        self.chat_history = QTextBrowser()
        layout.addWidget(self.chat_history)
        
        input_layout = QHBoxLayout()
        self.chat_target_combo = QComboBox()
        self.chat_target_combo.addItem("所有人 (公共)", "ALL") 
        input_layout.addWidget(self.chat_target_combo)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入聊天内容...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.chat_input)

        self.send_chat_btn = QPushButton("发送")
        self.send_chat_btn.clicked.connect(self.send_chat_message)
        input_layout.addWidget(self.send_chat_btn)
        
        layout.addLayout(input_layout)
        self.chat_dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.chat_dock)

    def send_chat_message(self):
        text = self.chat_input.text().strip()
        if not text: return
        
        target = self.chat_target_combo.currentData()
        sender_name = "GM"
        
        msg_data = {
            "sender": sender_name,
            "target": target,
            "text": text
        }

        self.append_chat_message(sender_name, text)
        self.server.broadcast(MsgType.CHAT, msg_data)
        
        self.chat_input.clear()

    def append_chat_message(self, sender: str, text: str):
        """将聊天信息渲染到面板上"""
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        color = "#C41E3A" if sender == "GM" else "#E9E1E1"
        
        html = f"<span style='color:#888;'>[{time_str}]</span> <b style='color:{color};'>{sender}</b>: {text}"
        self.chat_history.append(html)

    # ==========================
    # 代理与生命周期管理
    # ==========================
    def toggle_server(self) -> None:
        if self.btn_server.text() == "启动服务器":
            self.server.port = self.port_spin.value()
            ok, msg = self.server.start()
            if ok:
                self.log_system(msg)
                self.btn_server.setText("停止服务器")
                self.btn_server.setStyleSheet("background-color: #FFCCCC;")
                self.port_spin.setEnabled(False)
                self.start_port_forwarding()
            else:
                QMessageBox.critical(self, "Error", msg)
        else:
            self.stop_port_forwarding()
            self.server.stop()
            self.log_system("Server stopped.")
            self.btn_server.setText("启动服务器")
            self.btn_server.setStyleSheet("")
            self.port_spin.setEnabled(True)

    def set_port_forwarding_cmd(self) -> None:
        settings = QSettings("TA_Assistant", "GM_Config")
        current_cmd = settings.value("pf_cmd", "")
        default_gs_cmd = "gs-netcat -s TriangleAgency -l -p {port}"
        if not current_cmd: current_cmd = default_gs_cmd
        
        info_text = (
            "设置服务器启动时自动运行的命令。\n使用 {port} 作为当前服务器端口的占位符。\n\n"
            f"默认使用gsocket:\n{default_gs_cmd}\n\n注意：请确保已安装 gs-netcat 并将其添加到了系统环境变量中。"
        )
        cmd, ok = QInputDialog.getText(self, "端口转发 / gsocket 设置", info_text, text=current_cmd)
        if ok:
            settings.setValue("pf_cmd", cmd.strip())
            self.log_system(f"启动命令已更新: {cmd}")

    def start_port_forwarding(self) -> None:
        settings = QSettings("TA_Assistant", "GM_Config")
        cmd_template = settings.value("pf_cmd", "")
        if not cmd_template: return

        cmd_str = cmd_template.replace("{port}", str(self.port_spin.value()))
        try:
            import platform
            creation_flags = subprocess.CREATE_NEW_CONSOLE if platform.system() == "Windows" else 0
            self.pf_process = subprocess.Popen(shlex.split(cmd_str), creationflags=creation_flags)
            self.log_system(f"已启动外部命令: {cmd_str}")
        except Exception as e:
            self.log_system(f"<span style='color:red'>启动外部命令失败: {e}</span>")

    def stop_port_forwarding(self) -> None:
        if self.pf_process:
            self.log_system("正在关闭外部端口转发服务...")
            try:
                self.pf_process.terminate()
                self.pf_process = None
            except Exception as e:
                self.log_system(f"关闭外部进程出错: {e}")
    
    def closeEvent(self, event) -> None:
        self.stop_port_forwarding()
        self.server.stop()
        super().closeEvent(event)