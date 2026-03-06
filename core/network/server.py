import struct
from typing import Dict, Any, Optional, Tuple, List
from PySide6.QtNetwork import QTcpServer, QHostAddress, QTcpSocket, QAbstractSocket
from PySide6.QtCore import QObject, Signal

from .protocol import unpack_msg, pack_msg, HEADER_SIZE, MsgType, HEADER_FORMAT, MAGIC, MAGIC_LENGTH

class GMServer(QObject):
    """处理GM的 TCP 服务端逻辑"""
    
    log_received = Signal(str)
    chaos_received = Signal(int)
    sheet_received = Signal(str, str, dict)  # uid, name, sheet_content
    player_connected = Signal(str, str)      # uid, ip
    player_disconnected = Signal(str)        # uid
    mission_report_received = Signal(str, dict) # uid, data
    chat_received = Signal(dict)             # chat data
    players_updated = Signal(list)           # list of {"uid":..., "name":...}

    def __init__(self, port: int = 12345, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self.handle_new_connection)

        # Socket对象映射到上下文信息
        self.clients: Dict[QTcpSocket, Dict[str, Any]] = {}
        self.port = port

    def start(self) -> Tuple[bool, str]:
        """启动 TCP 服务端监听"""
        if not self.server.listen(QHostAddress.SpecialAddress.Any, self.port):
            return False, self.server.errorString()
        # 广播当前玩家列表（如果有的话）
        self._broadcast_player_list()
        return True, f"Server listening on port {self.port}"

    def stop(self) -> None:
        """断开所有客户端并关闭服务器"""
        for client_socket in list(self.clients.keys()):
            if client_socket.state() != QAbstractSocket.SocketState.UnconnectedState:
                client_socket.disconnectFromHost()
        self.server.close()
        self.clients.clear()
    
    def handle_new_connection(self) -> None:
        """处理新接入的 TCP 客户端"""
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
            # 通知上层有新连接
            self.player_connected.emit(uid, peer_ip)
            # 广播更新后的在线玩家列表
            self._broadcast_player_list()

    def on_disconnected(self) -> None:
        """处理客户端断开，安全回收资源"""
        sender_socket = self.sender()
        if not isinstance(sender_socket, QTcpSocket):
            return

        if sender_socket in self.clients:
            ctx = self.clients[sender_socket]
            uid = ctx["uid"]
            del self.clients[sender_socket]
            self.player_disconnected.emit(uid)
            # 广播更新后的在线玩家列表
            self._broadcast_player_list()

        # 延迟销毁底层 C++ 对象，防止在此事件循环中出错
        sender_socket.deleteLater()

    def on_ready_read(self) -> None:
        """读取客户端发送的数据并处理 TCP 粘包/分包"""
        sender_socket = self.sender()
        if not isinstance(sender_socket, QTcpSocket) or sender_socket not in self.clients:
            return
        
        ctx = self.clients[sender_socket]
        new_data = sender_socket.readAll().data()
        ctx["buffer"] += new_data

        while len(ctx["buffer"]) >= HEADER_SIZE:
            magic_pos = ctx["buffer"].find(MAGIC)

            if magic_pos == -1:
                ctx["buffer"] = b""
                return
            if magic_pos > 0:
                ctx["buffer"] = ctx["buffer"][magic_pos:]
            if len(ctx["buffer"]) < HEADER_SIZE:
                return
            body_length = struct.unpack(HEADER_FORMAT, ctx["buffer"][MAGIC_LENGTH:HEADER_SIZE])[0]
            
            if len(ctx["buffer"]) < HEADER_SIZE + body_length:
                break 

            body_data = ctx["buffer"][HEADER_SIZE : HEADER_SIZE + body_length]
            ctx["buffer"] = ctx["buffer"][HEADER_SIZE + body_length :]

            self.process_message(body_data, sender_socket)

    def process_message(self, body_data: bytes, sender_socket: QTcpSocket) -> None:
        """解析 JSON 并分发信号或执行广播"""
        msg = unpack_msg(body_data)
        if not msg: return

        m_type = msg.get("type")
        data = msg.get("data")
        sender_uid = self.clients[sender_socket]["uid"]

        if m_type == MsgType.CHAOS_SYNC:
            self.chaos_received.emit(data)
            
        elif m_type == MsgType.LOG_SYNC:
            self.log_received.emit(data)
            self.broadcast(MsgType.LOG_SYNC, data, exclude=sender_socket)
            
        elif m_type == MsgType.SHEET_UPDATE:
            new_name = data.get("name", "Unknown")
            sheet_content = data.get("sheet", {})
            self.clients[sender_socket]["name"] = new_name

            qas = sheet_content.get("quality_assurances", {})
            public_status = {
                "qas": {k: f"{v.get('current', 0)}/{v.get('max', 0)}" for k, v in qas.items()},
                "anomaly": sheet_content.get("anomaly", "未知的异常能力"),
                "reality": sheet_content.get("reality","未知的现实身份"),
                "competency": sheet_content.get("competency","未知的职能")
            }
            self.clients[sender_socket]["public_status"] = public_status
            self.sheet_received.emit(sender_uid, new_name, sheet_content)
            # 广播最新在线玩家列表（用于 PL 更新下拉列表）
            self._broadcast_player_list()
        
        elif m_type == MsgType.MISSION_REPORT:
            self.mission_report_received.emit(sender_uid, data)
        
        elif m_type == MsgType.CHAT:
            target = data.get("target", "ALL")
            data["from_uid"] = sender_uid
            if target != "GM" and target!='ALL':
                self.send_to(target, MsgType.CHAT, data)
                return
            if target == "ALL":
                self.broadcast(MsgType.CHAT, data, exclude=sender_socket)
            self.chat_received.emit(data)

    def _broadcast_player_list(self) -> None:
        """将当前在线玩家 uid/name 列表广播给所有连接的 PL"""
        lst: List[Dict[str, str]] = []
        for ctx in self.clients.values():
            lst.append({
                "uid": ctx.get("uid"), 
                "name": ctx.get("name", "Unknown"),
                "public_status": ctx.get("public_status", {})
            })
        payload = {"players": lst}
        self.broadcast(MsgType.PLAYER_LIST, payload)

    def broadcast(self, msg_type: MsgType, data: Any, exclude: Optional[QTcpSocket] = None) -> None:
        """向指定的或所有的活跃客户端广播消息"""
        payload = pack_msg(msg_type, data)
        for sock in self.clients:
            if sock != exclude and sock.state() == QAbstractSocket.SocketState.ConnectedState:
                sock.write(payload)
                sock.flush()
    
    def send_to_all(self, msg_type: MsgType, data: Any) -> None:
        """广播给所有 PL"""
        self.broadcast(msg_type, data, exclude=None)
    
    def send_to(self, uid: str, msg_type: MsgType, content: Any) -> None:
        """私信给特定的 PL"""
        payload = pack_msg(msg_type, content)
        for socket, ctx in self.clients.items():
            if ctx.get("uid") == uid:
                if socket.state() == QAbstractSocket.SocketState.ConnectedState:
                    socket.write(payload)
                    socket.flush()
                break