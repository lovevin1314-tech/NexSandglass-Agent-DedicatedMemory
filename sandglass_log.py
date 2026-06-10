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
import tempfile
import shutil
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
        # 净化器插件
        sanitizer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "sanitize.py")
        if os.path.exists(sanitizer):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("sanitize", sanitizer)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                text = mod.sanitize(text)
            except Exception:
                pass

        os.makedirs(os.path.dirname(_SANDGLASS), exist_ok=True)
        encrypted = _encrypt(text)
        # 原子写入——临时文件+替换，防并发冲突
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {encrypted}\n"
        tmpfd, tmpname = tempfile.mkstemp(suffix='.tmp', dir=os.path.dirname(_SANDGLASS))
        try:
            if os.path.exists(_SANDGLASS):
                with open(_SANDGLASS, 'rb') as src:
                    os.write(tmpfd, src.read())
            os.write(tmpfd, line.encode('utf-8'))
            os.close(tmpfd)
            shutil.move(tmpname, _SANDGLASS)
        except Exception:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
            os.close(tmpfd) if 'tmpfd' in dir() else None
            raise
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
