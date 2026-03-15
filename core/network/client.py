import struct
from typing import Any, Optional
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import QObject, Signal

from .protocol import unpack_msg, pack_msg, HEADER_SIZE, MsgType, HEADER_FORMAT, MAGIC, MAGIC_LENGTH

class PLClient(QObject):
    """处理PL的 TCP 网络通信逻辑"""
    
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    chaos_updated = Signal(int)
    log_updated = Signal(str)
    file_received = Signal(str, str)
    loose_ends_updated = Signal(int)
    mission_report_sync = Signal(dict)
    chat_received = Signal(dict)
    players_updated = Signal(dict)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.errorOccurred.connect(lambda: self.error_occurred.emit(self.socket.errorString()))
        self._buffer = b""

    def connect_to_host(self, host: str, port: int) -> None:
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            self.socket.disconnectFromHost()
        self.socket.connectToHost(host, port)

    def disconnect_from_host(self) -> None:
        if self.socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self.socket.disconnectFromHost()

    def _on_connected(self) -> None:
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self.disconnected.emit()

    def _on_ready_read(self) -> None:
        data = self.socket.readAll().data()
        self._buffer += data

        while len(self._buffer) >= HEADER_SIZE:
            magic_pos = self._buffer.find(MAGIC)
            if magic_pos == -1:
                self._buffer = b""
                return
            if magic_pos > 0:
                self._buffer = self._buffer[magic_pos:]
            if len(self._buffer) < HEADER_SIZE:
                return
            body_len = struct.unpack(HEADER_FORMAT, self._buffer[MAGIC_LENGTH:HEADER_SIZE])[0]
            if len(self._buffer) < HEADER_SIZE + body_len:
                break
            body = self._buffer[HEADER_SIZE: HEADER_SIZE + body_len]
            self._buffer = self._buffer[HEADER_SIZE + body_len:]
            self._dispatch_msg(body)

    def _dispatch_msg(self, body: bytes) -> None:
        msg = unpack_msg(body)
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
        elif m_type == MsgType.CHAT:
            self.chat_received.emit(val)
        elif m_type == MsgType.PLAYER_LIST:
            self.players_updated.emit(val)

    def send(self, msg_type: MsgType, data: Any) -> None:
        """将数据打包并发送给 GM 服务端"""
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            payload = pack_msg(msg_type, data)
            self.socket.write(payload)
            self.socket.flush()