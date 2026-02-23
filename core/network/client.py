import struct
from typing import Any, Optional
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import QObject, Signal

from .protocol import unpack_msg, pack_msg, HEADER_SIZE, MsgType, HEADER_FORMAT, MAGIC

class PLClient(QObject):
    """处理PL的 TCP 网络通信逻辑"""
    
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    chaos_updated = Signal(int)
    log_updated = Signal(str)
    file_received = Signal(str, str) # file_name, base64_content
    loose_ends_updated = Signal(int)
    mission_report_sync = Signal(dict)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)  # 将 socket 挂载在当前 QObject 树下
        self.socket.connected.connect(self.connected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.readyRead.connect(self.read_data)
        self.socket.errorOccurred.connect(self.handle_error)

        self._buffer: bytes = b""

    def connect_to_host(self, host: str, port: int) -> None:
        """中止现有连接并尝试连接到新目标"""
        self.socket.abort()
        self._buffer = b""
        self.socket.connectToHost(host, int(port))
    
    def disconnect_from_host(self) -> None:
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            self.socket.disconnectFromHost()

    def handle_error(self) -> None:
        """处理 Socket 错误，忽略正常的远端关闭"""
        if self.socket.error() == QAbstractSocket.SocketError.RemoteHostClosedError:
            return
        self.error_occurred.emit(self.socket.errorString())

    def read_data(self) -> None:
        """读取数据包并处理 TCP 粘包/分包"""
        new_data = self.socket.readAll().data()
        self._buffer += new_data
        
        while len(self._buffer) >= HEADER_SIZE:
            magic_pos = self._buffer.find(MAGIC)

            if magic_pos == -1:
                self._buffer = b""
                return
            if magic_pos > 0:
                self._buffer = self._buffer[magic_pos:]
            if len(self._buffer) < HEADER_SIZE:
                return
            body_length = struct.unpack(HEADER_FORMAT, self._buffer[len(MAGIC):HEADER_SIZE])[0]

            # 检查缓冲区是否已包含完整的 Body
            if len(self._buffer) < HEADER_SIZE + body_length:
                break 

            # 提取 Body 并裁切缓冲区
            body_data = self._buffer[HEADER_SIZE : HEADER_SIZE + body_length]
            self._buffer = self._buffer[HEADER_SIZE + body_length :]

            self.process_message(body_data)

    def process_message(self, body_data: bytes) -> None:
        """解析 JSON Body 并分发给对应的 Qt 信号"""
        msg = unpack_msg(body_data)
        if not msg: return

        m_type = msg.get("type")
        val = msg.get("data")
        
        if m_type == MsgType.CHAOS_SYNC:
            self.chaos_updated.emit(val)
        elif m_type == MsgType.LOG_SYNC:
            self.log_updated.emit(val)
        elif m_type == MsgType.FILE_SEND:
            self.file_received.emit(val.get("name"), val.get("content"))
        elif m_type == MsgType.LOOSE_ENDS:
            self.loose_ends_updated.emit(val)
        elif m_type == MsgType.MISSION_REPORT:
            self.mission_report_sync.emit(val)

    def send(self, msg_type: MsgType, data: Any) -> None:
        """将数据打包并发送给 GM 服务端"""
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            payload = pack_msg(msg_type, data)
            self.socket.write(payload)
            self.socket.flush()