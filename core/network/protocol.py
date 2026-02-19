import json
import struct
from enum import Enum
from typing import Any, Dict, Optional

class MsgType(str, Enum):
    """定义网络通信中的所有消息类型"""
    CHAOS_SYNC = "chaos"            # 同步混沌值
    LOG_SYNC = "log"                # 同步日志文本
    SHEET_UPDATE = "sheet"          # PL 推送角色卡给 GM
    FILE_SEND = "file"              # GM 发送文件给 PL/全部
    LOOSE_ENDS = "loose_ends"       # 松散端数值同步
    MISSION_REPORT = "mission_report" # 任务报告同步

HEADER_SIZE = 4 
HEADER_FORMAT = '!I'

def pack_msg(msg_type: MsgType, data: Any) -> bytes:
    """
    将消息打包成二进制流。
    格式：[4字节大端无符号整数表示Body长度] + [JSON 编码的 UTF-8 字节数据]
    """
    # 确保传入的是枚举，但序列化时取其字符串值
    msg_dict = {"type": msg_type.value if isinstance(msg_type, MsgType) else msg_type, "data": data}
    json_bytes = json.dumps(msg_dict, ensure_ascii=False).encode('utf-8')
    header = struct.pack(HEADER_FORMAT, len(json_bytes))
    return header + json_bytes

def unpack_msg(body_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    将 JSON 字节流解析为 Python 字典。
    注意：传入的参数应当仅包含 Body 部分，不包含 4 字节的 Header。
    """
    try:
        return json.loads(body_bytes.decode('utf-8'))
    except Exception as e:
        print(f"Protocol Decode Error: {e}")
        return None