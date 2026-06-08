"""
NexSandglass 通用落沙 — 任何 Agent 都能用
==========================================
不依赖 Hermes plugin。任何 Python 脚本 import 即可。

用法：
  from sandglass_log import log_message
  log_message("用户：今天天气真好")
  log_message("Assistant：明天有雨，记得带伞")
"""

import base64
import hashlib
import os
import platform
from datetime import datetime

_SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")

# Windows DPAPI
try:
    from win32crypt import CryptProtectData
except ImportError:
    CryptProtectData = None


def _encrypt(plaintext: str) -> str:
    """加密：Windows=DPAPI，其他=base64混淆。"""
    raw = plaintext.encode("utf-8")
    if CryptProtectData:
        try:
            return base64.b64encode(
                CryptProtectData(raw, None, None, None, None, 0)
            ).decode()
        except Exception:
            pass
    return base64.b64encode(raw).decode()


def log_message(text: str, sender: str = "agent") -> bool:
    """写入一条消息到沙漏。任何 Agent 调用此函数落沙。
    返回 True 表示写入成功。"""
    try:
        os.makedirs(os.path.dirname(_SANDGLASS), exist_ok=True)
        encrypted = _encrypt(text)
        with open(_SANDGLASS, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {encrypted}\n")
        return True
    except Exception:
        return False


def log_conversation(user_msg: str, agent_msg: str) -> int:
    """写入一轮对话（用户+Agent）。返回新写入的行数。"""
    count = 0
    if user_msg:
        if log_message(user_msg, sender="user"): count += 1
    if agent_msg:
        if log_message(agent_msg, sender="agent"): count += 1
    return count
