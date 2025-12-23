import json
import struct
from enum import Enum

class MsgType(str, Enum):
    CHAOS_SYNC = "chaos"        # 同步混沌值
    LOG_SYNC = "log"            # 同步日志文本
    SHEET_UPDATE = "sheet"      # PL 推送角色卡给 GM
    FILE_SEND = "file"          # GM 发送文件给 PL

HEADER_SIZE = 4 

def pack_msg(msg_type, data):
    """
    将消息打包成：[4字节长度][JSON数据]
    """
    msg_dict = {"type": msg_type, "data": data}
    json_bytes = json.dumps(msg_dict, ensure_ascii=False).encode('utf-8')
    header = struct.pack('!I', len(json_bytes))
    return header + json_bytes

def unpack_msg(data_bytes):
    try:
        return json.loads(data_bytes.decode('utf-8'))
    except Exception as e:
        print(f"Protocol Decode Error: {e}")
        return None