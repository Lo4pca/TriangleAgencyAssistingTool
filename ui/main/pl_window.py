import json
import datetime
import base64
import subprocess
import shlex
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QTextBrowser, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QHBoxLayout, QSpinBox, QTabWidget,
    QMessageBox, QFileDialog, QTextEdit,QDialog, QFormLayout, 
    QLineEdit, QDialogButtonBox, QGroupBox
)
from PySide6.QtGui import QAction,QDesktopServices
from PySide6.QtCore import Qt,QTimer,QUrl,QFileInfo,QFile,QIODevice,QSettings

from ui.character.editor import CharacterEditor
from ui.tools.dice_tool import DiceTool
from core.network.client import PLClient

class PLMainWindow(QMainWindow):
    def __init__(self, game_name):
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
        self.proxy_process = None
        self.setup_network()
    
    def close_doc_tab(self, index):
        if self.doc_tabs.count() > 0:
            self.doc_tabs.removeTab(index)
    
    def setup_network(self):
        self.client.chaos_updated.connect(self.on_server_chaos_sync)
        self.client.log_updated.connect(self.append_log)
        self.client.file_received.connect(self.on_file_received)
        self.client.connected.connect(self.on_connected_success)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.error_occurred.connect(self.on_connection_error)
    
    def update_connection_ui(self, is_connected):
        if is_connected:
            self.conn_status_lbl.setText("🟢 已连接 GM")
            self.conn_status_lbl.setStyleSheet("color: #55FF55; font-weight: bold;")
            self.disconnect_btn.setEnabled(True)
        else:
            self.conn_status_lbl.setText("🔴 未连接")
            self.conn_status_lbl.setStyleSheet("color: #FF5555; font-weight: bold;")
            self.disconnect_btn.setEnabled(False)

    def on_server_chaos_sync(self, absolute_val):
        self.chaos_spin.blockSignals(True)
        self.chaos_spin.setValue(absolute_val)
        self.chaos_spin.blockSignals(False)
    
    def save_file(self,fname,content):
        download_dir = Path("data") / "PL" / self.game_name / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        file_path = download_dir / fname
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path
    
    def render_file(self, uri):
        if isinstance(uri, QUrl):
            file_path = uri.toLocalFile()
            uri_str = uri.toString()
        else:
            uri_str = str(uri)
            file_path = QUrl(uri_str).toLocalFile()
        file_info = QFileInfo(file_path)
        ext = file_info.suffix().lower()
        fname = file_info.fileName()
        preview_successful=True

        if ext == 'jpg':
            ext = 'jpeg'

        image_types = {'png', 'jpeg', 'gif', 'bmp', 'svg'}
        text_types = {'txt', 'md', 'json', 'log', 'csv', 'py', 'ini', 'xml', 'yaml', 'yml'}

        file = QFile(file_path)
        if not file.open(QIODevice.ReadOnly):
            self.append_log(f"<span style='color:red'>无法打开文件: {fname}</span>")
            return

        raw = file.readAll()
        file.close()

        viewer = QTextBrowser()
        viewer.setOpenLinks(False)
        viewer.anchorClicked.connect(self.open_local_link)

        if ext in image_types:
            b64 = base64.b64encode(bytes(raw)).decode('ascii')
            html_content = f"""
            <div style="text-align:center; margin-top:10px;">
                <img src="data:image/{ext};base64,{b64}" style="max-width:100%;" />
                <p style="color:gray;">{fname}</p>
            </div>
            """

        elif ext in text_types:
            try:
                text_content = bytes(raw).decode('utf-8', errors='ignore')
            except Exception:
                text_content = str(raw)
            import html
            safe = html.escape(text_content)
            html_content = f"""
            <div style="line-height:1.4; padding:10px;">
                <pre>{safe}</pre>
            </div>
            """

        else:
            html_content = f"""
            <div style="padding:20px; text-align:center;">
                <h3>无法预览此文件类型 ({ext})</h3>
                <p>请点击日志中的URL，使用系统程序打开</p>
            </div>
            """
            preview_successful=False

        viewer.setHtml(html_content)

        def add_tab():
            idx = self.doc_tabs.addTab(viewer, fname)
            self.doc_tabs.setCurrentIndex(idx)
            self.doc_tabs.setTabToolTip(idx, file_path)

        QTimer.singleShot(0, add_tab)
        return preview_successful

    def on_file_received(self, fname, b64_content):
        try:
            data_bytes = base64.b64decode(b64_content)

            file_path = self.save_file(fname, data_bytes)
            file_uri = file_path.absolute().as_uri()

            self.append_log(f"📥 收到文件: <a href='{file_uri}'>{fname}</a> (已保存)")
            self.render_file(file_uri)

        except Exception as e:
            self.append_log(f"<span style='color:red'>文件处理失败: {e}</span>")

    def _init_menu(self):
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
        
        self.view_menu = menubar.addMenu("视图")

        net_menu = self.menuBar().addMenu("联机")
        conn_action = QAction("连接到 GM", self)
        conn_action.triggered.connect(self.show_connect_dialog)
        net_menu.addAction(conn_action)
    
    def show_connect_dialog(self):
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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

    def start_proxy_connection(self, cmd_template, port):
        final_cmd = cmd_template.replace("{port}", str(port))
        
        self.append_log(f"正在启动代理命令: <code>{final_cmd}</code>")
        
        try:
            import platform
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            args = shlex.split(final_cmd)
            self.pf_process = subprocess.Popen(args, creationflags=creation_flags)

            self.append_log("正在等待 gsocket 建立隧道 (约 2 秒)...")
            from PySide6.QtWidgets import QApplication
            
            t_end = time.time() + 2
            while time.time() < t_end:
                QApplication.processEvents()
                time.sleep(0.1)

            self.append_log(f"正在通过隧道连接 localhost:{port}...")
            self.client.connect_to_host("127.0.0.1", port)
            
        except Exception as e:
            self.append_log(f"<span style='color:red'>代理启动失败: {e}</span>")
            self.stop_proxy()
    
    def on_connected_success(self):
        self.update_connection_ui(True)
        self.append_log("<b>✅ 已成功连接到 GM 服务器！</b>")
        self.push_character_sheet()
    
    def on_disconnected(self):
        self.update_connection_ui(False)
        self.append_log("<span style='color:gray'>连接已断开</span>")

    def on_connection_error(self, error_msg):
        self.update_connection_ui(False)
        self.append_log(f"<span style='color:red'>❌ 连接错误: {error_msg}</span>")

    def push_character_sheet(self):
        name = self.character_data.get("name", "Unknown PL")
        self.client.send("sheet", {"name": name, "sheet": self.character_data})

    def _init_docks(self):
        # 1. Log Dock
        self.log_dock = QDockWidget("游戏日志 & 控制台", self)
        self.log_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(5, 5, 5, 5)
        log_layout.setSpacing(5)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        
        self.conn_status_lbl = QLabel("🔴 未连接")

        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.setFixedSize(80, 24)
        self.disconnect_btn.setEnabled(False) 
        self.disconnect_btn.clicked.connect(self.manual_disconnect)
        
        toolbar_layout.addWidget(self.conn_status_lbl)
        toolbar_layout.addWidget(self.disconnect_btn)
        toolbar_layout.addSpacing(10)
        
        toolbar_layout.addStretch()
        
        chaos_lbl = QLabel("混沌:")
        chaos_lbl.setStyleSheet("color: #FF5555; font-weight: bold;")
        self.chaos_spin = QSpinBox()
        self.chaos_spin.setRange(0, 999)
        self.chaos_spin.setStyleSheet("color: white; background: transparent; border: none; font-weight: bold; font-size: 11pt;")
        self.chaos_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.chaos_spin.setFixedWidth(40)
        self.chaos_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        dice_btn = QPushButton("🎲 掷骰")
        dice_btn.clicked.connect(self.open_dice_tool)

        toolbar_layout.addWidget(chaos_lbl)
        toolbar_layout.addWidget(self.chaos_spin)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(dice_btn)
        
        log_layout.addLayout(toolbar_layout)
        
        self.log_widget = QTextBrowser()
        self.log_widget.setOpenLinks(False)  
        self.log_widget.setOpenExternalLinks(False)
        self.log_widget.anchorClicked.connect(self.open_local_link)
        
        log_layout.addWidget(self.log_widget)
        
        self.log_dock.setWidget(log_container)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        # 2. Notes Dock
        self.notes_dock = QDockWidget("额外笔记", self)
        self.notes_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
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
        self.addDockWidget(Qt.RightDockWidgetArea, self.notes_dock)
        self.view_menu.addAction(self.notes_dock.toggleViewAction())
    
    def open_local_link(self, url):
        if not self.render_file(url):
            QDesktopServices.openUrl(url)

    def export_text(self, content, suffix, ext):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{self.game_name}_{suffix}_{timestamp}.{ext}"

        save_dir = Path("data") / "PL" / self.game_name / "exported"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"保存 {suffix}", 
            str(save_dir / default_name),
            f"{ext.upper()} Files (*.{ext});;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))

    def handle_dice_chaos(self, growth_value):
        current = self.chaos_spin.value()
        self.chaos_spin.setValue(current + growth_value)
        self.client.send("chaos", growth_value)

    def handle_dice_log(self, html_content):
        name = self.character_data.get("name", "Unknown PL")
        full_log = f"<div style='border-left: 4px solid #0055AA; padding-left: 5px; margin: 5px 0;'><b>{name}</b> 进行了掷骰:<br>{html_content}</div>"
        self.append_log(full_log)
        self.client.send("log", full_log)

    def open_character_editor(self):
        editor = CharacterEditor(self.game_name)
        if editor.exec():
            self.character_data = self.load_character()
            self.push_character_sheet()
            self.append_log("<i>角色卡已更新并同步。</i>")

    def open_dice_tool(self):
        self.character_data = self.load_character()
        
        dialog = DiceTool(self.game_name, self.character_data, self)
        dialog.dataChanged.connect(self.save_character)

        dialog.log_signal.connect(self.handle_dice_log)
        
        dialog.chaosSignal.connect(self.handle_dice_chaos) 
        dialog.show()

    def append_log(self, html_content):
        if hasattr(self, 'log_widget'):
            self.log_widget.append(html_content)
    
    def manual_open_local_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", 
            "All Files (*)"
        )
        if path_str:
            file_url = QUrl.fromLocalFile(path_str)
            self.render_file(file_url)
    
    def stop_proxy(self):
        if self.proxy_process:
            try:
                self.proxy_process.terminate()
                self.proxy_process = None
                self.append_log("<i>已关闭本地代理进程</i>")
            except Exception:
                pass
    
    def manual_disconnect(self):
        self.stop_proxy()
        self.client.disconnect_from_host()
        self.conn_status_lbl.setText("🔴 未连接")
        self.conn_status_lbl.setStyleSheet("color: red; font-weight: bold;")
        self.disconnect_btn.setEnabled(False)
        self.append_log("<i>已手动断开连接。</i>")

    def load_character(self):
        if not self.char_file.exists():
            return {}
        try:
            with open(self.char_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_character(self):
        self.char_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.char_file, "w", encoding="utf-8") as f:
            json.dump(self.character_data, f, ensure_ascii=False, indent=4)
        self.push_character_sheet()
    
    def closeEvent(self, event):
        self.stop_proxy()
        self.client.disconnect_from_host()
        super().closeEvent(event)