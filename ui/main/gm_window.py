import subprocess
import shlex
import base64
import html
from pathlib import Path
import datetime

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QTextEdit, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QHBoxLayout, QListWidget, QSpinBox, 
    QTabWidget, QFileDialog, QMessageBox, QSplitter,
    QDialog, QListWidgetItem,QMenu, QInputDialog
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QFileInfo,QSettings
from core.network.server import GMServer

from ui.character.tabs.basic import BasicInfoTab
from ui.character.tabs.balance import WorkLifeBalanceTab
from ui.character.tabs.abilities import AbilitiesTab
from ui.character.tabs.requisitions import RequisitionsTab
from ui.character.tabs.relationships import RelationshipsTab
from ui.character.tabs.custom_tracks import CustomTracksTab
from ui.common.styles import GLOBAL_STYLE_SHEET

class DragDropEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("主文档区域\n\n您可以直接将图片、文本文件拖入此处查看...")
        
    def canInsertFromMimeData(self, source):
        if source.hasUrls() or source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        mime_data = event.mimeData()
        
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if file_path:
                    self.process_file(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def process_file(self, file_path):
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
            </div>
            <br>
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
                </div>
                <br>
                """
                self.insertHtml(html_txt)
                self.append("")
            except Exception as e:
                self.append(f"[读取文件失败: {filename} - {e}]")

        else:
            self.append(f"无法识别的文件格式: {file_path}")

class CharacterViewerDialog(QDialog):
    def __init__(self, char_name, char_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"角色卡查看: {char_name}")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        self.setStyleSheet(GLOBAL_STYLE_SHEET)
        self.tabs = QTabWidget()

        self.tabs.addTab(BasicInfoTab(char_data, self), "基本信息")
        self.tabs.addTab(WorkLifeBalanceTab(char_data, self), "平衡")
        self.tabs.addTab(AbilitiesTab(char_data, self), "能力")
        self.tabs.addTab(RequisitionsTab(char_data, self), "补给")
        self.tabs.addTab(RelationshipsTab(char_data, self), "关系")
        self.tabs.addTab(CustomTracksTab(char_data, self), "自定义")
        
        layout.addWidget(self.tabs)

class GMMainWindow(QMainWindow):
    def __init__(self, game_name):
        super().__init__()
        self.game_name = game_name
        self.setWindowTitle(f"TA Assistant - GM Control - {game_name}")
        self.resize(1400, 900)
        
        self.server = GMServer()

        # key: uid (str) -> value: {"name": str, "sheet": dict, "item": QListWidgetItem}
        self.players_data = {} 
        self.doc_window_count = 0

        self.pf_process = None

        self._init_menu()
        self._init_ui()
        self.setup_server_signals()

        self.net_update=True

    def setup_server_signals(self):
        self.server.log_received.connect(self.append_log)
        self.server.chaos_received.connect(self.sync_chaos)

        self.server.player_connected.connect(self.on_player_connected)
        self.server.player_disconnected.connect(self.on_player_disconnected)
        self.server.sheet_received.connect(self.update_pl_sheet)

    def on_player_connected(self, uid, ip):
        self.log_system(f"新连接: {ip} (ID: {uid})")

        item_text = f"⏳ 连接中... ({ip})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, uid) 
        
        self.pl_list.addItem(item)

        self.players_data[uid] = {
            "name": "Unknown",
            "sheet": {},
            "item": item
        }

    def on_player_disconnected(self, uid):
        self.log_system(f"❌ 玩家断开: {self.players_data[uid]['name']} ({uid})")
        
        if uid in self.players_data:
            row = self.pl_list.row(self.players_data[uid]['item'])
            if row != -1:
                self.pl_list.takeItem(row)

    def update_pl_sheet(self, uid, name, sheet_data):
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

    def on_pl_double_clicked(self, item):
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

    def _init_menu(self):
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

    def _init_ui(self):
        # 1. Main Doc
        self.main_doc_viewer = DragDropEditor()
        self.setCentralWidget(self.main_doc_viewer)

        # 2. Left Dock
        self.left_dock = QDockWidget("GM 控制台", self)
        self.left_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Vertical)
        
        # Top: Network
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
        
        top_layout.addWidget(QLabel("在线玩家 (双击查看):"))
        self.pl_list = QListWidget()
        self.pl_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pl_list.customContextMenuRequested.connect(self.show_pl_context_menu)
        self.pl_list.itemDoubleClicked.connect(self.on_pl_double_clicked)
        top_layout.addWidget(self.pl_list)
        
        send_file_btn = QPushButton("向所有 PL 发送文件")
        send_file_btn.clicked.connect(self.send_file_to_all)
        top_layout.addWidget(send_file_btn)
        
        # Bottom: Notes
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
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)

        # 3. Right Dock
        self.log_dock = QDockWidget("公共日志 & 混沌", self)
        self.log_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        
        chaos_layout = QHBoxLayout()
        chaos_layout.addWidget(QLabel("当前混沌:"))
        self.chaos_spin = QSpinBox()
        self.chaos_spin.setRange(0, 999)
        self.chaos_spin.valueChanged.connect(self.broadcast_chaos)
        chaos_layout.addWidget(self.chaos_spin)
        log_layout.addLayout(chaos_layout)
        
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        log_layout.addWidget(self.log_widget)
        
        self.log_dock.setWidget(log_container)
        self.addDockWidget(Qt.RightDockWidgetArea, self.log_dock)

    def create_doc_window(self):
        self.doc_window_count += 1
        dock_title = f"文档查看器 {self.doc_window_count}"
        new_dock = QDockWidget(dock_title, self)
        new_dock.setAttribute(Qt.WA_DeleteOnClose)
        new_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        editor = DragDropEditor()
        editor.setPlaceholderText(f"{dock_title}")
        new_dock.setWidget(editor)
        self.addDockWidget(Qt.RightDockWidgetArea, new_dock)

    def toggle_server(self):
        if self.btn_server.text() == "启动服务器":
            port = self.port_spin.value()
            self.server.port = port 
            
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

    def log_system(self, msg):
        self.append_log(f"<span style='color:gray'>[SYSTEM] {msg}</span>")
    def append_log(self, html):
        self.log_widget.append(html)

    def sync_chaos(self, val):
        self.net_update=True
        self.chaos_spin.blockSignals(True)
        self.chaos_spin.setValue(self.chaos_spin.value() + val)
        self.chaos_spin.blockSignals(False)
        self.broadcast_chaos()
        self.net_update=False

    def broadcast_chaos(self):
        self.server.send_to_all("chaos", self.chaos_spin.value())
        if not self.net_update:
            log_msg = f"<span style='color: #FF5722;'>⚠️ GM 修改了混沌值 -> {self.chaos_spin.value()}</span>"
            self.append_log(log_msg) 
            self.server.send_to_all("log", log_msg)
    
    def prepare_sending_file(self,prompt):
        path_str, _ = QFileDialog.getOpenFileName(self, prompt)
        if not path_str:
            return
            
        path = Path(path_str)
        try:
            with open(path, "rb") as f:
                content = f.read()
            
            if len(content) > 10 * 1024 * 1024:
                reply = QMessageBox.question(self, "文件过大", "文件超过10MB，发送可能会导致卡顿。是否继续？", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return

            b64_str = base64.b64encode(content).decode('utf-8')
            return path,b64_str
        except Exception as e:
            QMessageBox.critical(self, "打开文件时发生错误", str(e))

    def send_file_to_all(self):
        try:
            path,b64_str = self.prepare_sending_file("选择文件")
            self.server.send_to_all("file", {"name": path.name, "content": b64_str})
            self.log_system(f"已发送文件: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "发送文件时发生错误", str(e))
    
    def send_file_private(self, target_uid, target_name):
        try:
            path,b64_str = self.prepare_sending_file(f"选择文件发送给 {target_name}")
            self.server.send_to(target_uid,"file",{"name": path.name, "content": b64_str})
            self.log_system(f"已向 {target_name} 发送文件: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "发送错误", str(e))
    
    def manual_open_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", 
            "All Files (*);;Images (*.png *.jpg *.jpeg *.gif);;Text (*.txt *.md *.json)"
        )
        if path_str:
            self.main_doc_viewer.process_file(path_str)

    def export_gm_notes(self):
        content = self.gm_notes.toPlainText()
        if not content:
            QMessageBox.information(self, "提示", "笔记内容为空。")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{self.game_name}_gm_notes_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出笔记", default_name, "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log_system(f"笔记已导出至: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def show_pl_context_menu(self, pos):
        item = self.pl_list.itemAt(pos)
        if not item:
            return
            
        uid = item.data(Qt.UserRole)
        name = item.text()
        
        menu = QMenu()
        send_action = menu.addAction(f"📤 发送文件给: {name}")
        send_action.triggered.connect(lambda: self.send_file_private(uid, name))
        
        menu.exec(self.pl_list.mapToGlobal(pos))

    def set_port_forwarding_cmd(self):
        settings = QSettings("TA_Assistant", "GM_Config")
        current_cmd = settings.value("pf_cmd", "")

        default_gs_cmd = "gs-netcat -s TriangleAgency -l -p {port}"
        
        if not current_cmd:
            current_cmd = default_gs_cmd
        
        info_text = (
            "设置服务器启动时自动运行的命令。\n"
            "使用 {port} 作为当前服务器端口的占位符。\n\n"
            "默认使用gsocket:\n"
            f"{default_gs_cmd}\n\n"
            "注意：请确保已安装 gs-netcat 并将其添加到了系统环境变量中。"
        )
        
        cmd, ok = QInputDialog.getText(self, "端口转发 / gsocket 设置", info_text, text=current_cmd)
        if ok:
            settings.setValue("pf_cmd", cmd.strip())
            self.log_system(f"启动命令已更新: {cmd}")

    def start_port_forwarding(self):
        settings = QSettings("TA_Assistant", "GM_Config")
        cmd_template = settings.value("pf_cmd", "")
        
        if not cmd_template:
            return

        port = self.port_spin.value()
        cmd_str = cmd_template.replace("{port}", str(port))
        
        try:
            args = shlex.split(cmd_str)

            import platform
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NEW_CONSOLE

            self.pf_process = subprocess.Popen(args, creationflags=creation_flags)
            self.log_system(f"已启动外部命令: {cmd_str}")
            
        except Exception as e:
            self.log_system(f"<span style='color:red'>启动外部命令失败: {e}</span>")

    def stop_port_forwarding(self):
        if self.pf_process:
            self.log_system("正在关闭外部端口转发服务...")
            try:
                self.pf_process.terminate()
                self.pf_process = None
            except Exception as e:
                self.log_system(f"关闭外部进程出错: {e}")
    
    def closeEvent(self, event):
        self.stop_port_forwarding()
        self.server.stop()
        super().closeEvent(event)