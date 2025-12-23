import struct
from PySide6.QtNetwork import QTcpServer, QHostAddress, QTcpSocket, QAbstractSocket
from PySide6.QtCore import QObject, Signal, QTimer
from .protocol import unpack_msg, pack_msg, HEADER_SIZE, MsgType

class GMServer(QObject):
    log_received = Signal(str)
    chaos_received = Signal(int)
    sheet_received = Signal(str, str, dict)
    player_connected = Signal(str, str)
    player_disconnected = Signal(str)

    def __init__(self, port=12345):
        super().__init__()
        self.server = QTcpServer()
        self.server.newConnection.connect(self.handle_new_connection)

        self.clients = {}
        
        self.port = port

    def start(self):
        if not self.server.listen(QHostAddress.Any, self.port):
            return False, self.server.errorString()
        return True, f"Server listening on port {self.port}"

    def stop(self):
        for client_socket in list(self.clients.keys()):
            if client_socket.state() != QAbstractSocket.UnconnectedState:
                client_socket.disconnectFromHost()
        self.server.close()
        self.clients.clear()
    
    def handle_new_connection(self):
        while self.server.hasPendingConnections():
            client_socket = self.server.nextPendingConnection()
            peer_ip = client_socket.peerAddress().toString()
            peer_port = client_socket.peerPort()
            uid = f"{peer_ip}:{peer_port}"
            self.clients[client_socket] = {
                "uid": uid,
                "buffer": b"",
                "name": "Unknown"

            }
            client_socket.readyRead.connect(self.on_ready_read)
            client_socket.disconnected.connect(self.on_disconnected)
            self.player_connected.emit(uid, peer_ip)

    def on_disconnected(self):
        sender_socket = self.sender()

        if sender_socket in self.clients:
            ctx = self.clients[sender_socket]
            uid = ctx["uid"]
            del self.clients[sender_socket]
            self.player_disconnected.emit(uid)

        sender_socket.deleteLater()

    def on_ready_read(self):
        sender_socket = self.sender()
        
        if sender_socket not in self.clients:
            return

        
        ctx = self.clients[sender_socket]
        new_data = sender_socket.readAll().data()
        ctx["buffer"] += new_data

        while True:
            buffer = ctx["buffer"]
            if len(buffer) < HEADER_SIZE:
                break
            
            body_length = struct.unpack('!I', buffer[:HEADER_SIZE])[0]
            if len(buffer) < HEADER_SIZE + body_length:
                break

            body_data = buffer[HEADER_SIZE : HEADER_SIZE + body_length]
            ctx["buffer"] = buffer[HEADER_SIZE + body_length :]

            self.process_message(body_data, sender_socket)

    def process_message(self, body_data, sender_socket):
        msg = unpack_msg(body_data)
        if not msg: return

        m_type = msg.get("type")
        data = msg.get("data")
        sender_uid = self.clients[sender_socket]["uid"]

        if m_type == MsgType.CHAOS_SYNC:
            self.chaos_received.emit(data)
            self.broadcast(MsgType.CHAOS_SYNC, data, exclude=sender_socket)
            
        elif m_type == MsgType.LOG_SYNC:
            self.log_received.emit(data)
            self.broadcast(MsgType.LOG_SYNC, data, exclude=sender_socket)
            
        elif m_type == MsgType.SHEET_UPDATE:
            new_name = data.get("name", "Unknown")
            sheet_content = data.get("sheet", {})
            self.clients[sender_socket]["name"] = new_name
            self.sheet_received.emit(sender_uid, new_name, sheet_content)
    
    def broadcast(self, msg_type, data, exclude=None):
        payload = pack_msg(msg_type, data)
        for sock in self.clients:
            if sock != exclude and sock.state() == QTcpSocket.ConnectedState:
                sock.write(payload)
                sock.flush()
    
    def send_to_all(self, msg_type, data):
        self.broadcast(msg_type, data, exclude=None)
    
    def send_to(self, uid, msg_type, content):
        for socket, data in self.clients.items():
            if data.get("uid") == uid:
                if socket.state() == QTcpSocket.ConnectedState:
                    socket.write(pack_msg(msg_type, content))
                    socket.flush()
                break