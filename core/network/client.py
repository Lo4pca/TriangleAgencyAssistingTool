import struct
from PySide6.QtNetwork import QTcpSocket
from PySide6.QtCore import QObject, Signal
from .protocol import unpack_msg, pack_msg, HEADER_SIZE,MsgType

class PLClient(QObject):
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    chaos_updated = Signal(int)
    log_updated = Signal(str)
    file_received = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.socket = QTcpSocket()
        self.socket.connected.connect(self.connected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.readyRead.connect(self.read_data)
        self.socket.errorOccurred.connect(self.handle_error)

        self._buffer = b""

    def connect_to_host(self, host, port):
        self.socket.abort()
        self._buffer = b""
        self.socket.connectToHost(host, int(port))
    
    def disconnect_from_host(self):
        if self.socket.state() == QTcpSocket.ConnectedState:
            self.socket.disconnectFromHost()

    def handle_error(self):
        if self.socket.error() == QTcpSocket.RemoteHostClosedError:
            return
        self.error_occurred.emit(self.socket.errorString())

    def read_data(self):
        data = self.socket.readAll().data()
        self._buffer += data
        
        while True:
            if len(self._buffer) < HEADER_SIZE:
                break

            body_length = struct.unpack('!I', self._buffer[:HEADER_SIZE])[0]

            if len(self._buffer) < HEADER_SIZE + body_length:
                break

            body_data = self._buffer[HEADER_SIZE : HEADER_SIZE + body_length]
            self._buffer = self._buffer[HEADER_SIZE + body_length :]

            self.process_message(body_data)

    def process_message(self, body_data):
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

    def send(self, msg_type, data):
        if self.socket.state() == QTcpSocket.ConnectedState:
            payload = pack_msg(msg_type, data)
            self.socket.write(payload)
            self.socket.flush()