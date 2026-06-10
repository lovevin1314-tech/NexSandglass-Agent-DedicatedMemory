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
import logging
import os
import platform
import time as _time
from datetime import datetime

logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.error(f"DPAPI加密失败，降级base64: {e}")
    return base64.b64encode(raw).decode()


def log_message(text: str, sender: str = "agent") -> bool:
    """写入一条消息到沙漏。任何 Agent 调用此函数落沙。
    返回 True 表示写入成功。"""
    try:
        # 净化器插件（可选）
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
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {encrypted}\n"

        # 简单文件锁——轮询 .lock 最多 5 秒
        lock = _SANDGLASS + ".lock"
        deadline = _time.time() + 5
        while _time.time() < deadline:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                _time.sleep(0.01)
        else:
            pass  # 锁超时，裸写

        try:
            with open(_SANDGLASS, "a", encoding="utf-8") as f:
                f.write(line)
        finally:
            try:
                os.unlink(lock)
            except OSError as e:
                logger.warning(f"锁文件清理失败（可能残留，下次会超时自愈）: {e}")
                # 二次尝试——强制删除
                try:
                    if os.path.exists(lock):
                        os.remove(lock)
                except Exception as e:
                    logger.warning(f"锁文件二次删除也失败: {e}")

        # 影子沙——落沙后同步索引（自增ID，不读文件）
        try:
            from shadow_sand import shadow_index
            shadow_index(text)
        except Exception as e:
            logger.error(f"影子沙索引同步失败: {e}")

        return True
    except Exception as e:
        logger.error(f"沙漏写入失败: {e}")
        return False


def log_conversation(user_msg: str, agent_msg: str) -> int:
    """写入一轮对话（用户+Agent）。返回新写入的行数。"""
    count = 0
    if user_msg:
        if log_message(user_msg, sender="user"): count += 1
    if agent_msg:
        if log_message(agent_msg, sender="agent"): count += 1
    return count
