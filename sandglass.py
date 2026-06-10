"""
NeuroBase Sandglass — 插件源码备份 + 解密工具
==============================================
部署位置：
  - plugins/sandglass/__init__.py  ← Gateway 插件（主实现）
  - .neurobase/scripts/sandglass.py ← vault 备份（此文件，含 read/count）

用法：
  from sandglass import read, count
  read(10)   # 解密读取最近10条
  count()    # 总行数
"""
import base64
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
_ERRFLAG = os.path.join(os.path.expanduser("~"), ".neurobase", ".sandglass_error")

try:
    from win32crypt import CryptProtectData, CryptUnprotectData
except ImportError:
    CryptProtectData = None
    CryptUnprotectData = None


# ── 插件核心（与 plugins/sandglass/__init__.py 同步） ──

def _on_message(event, **_kw) -> None:
    """pre_gateway_dispatch 钩子——所有平台消息到达时落沙。"""
    try:
        os.makedirs(os.path.dirname(_SANDGLASS), exist_ok=True)
        sender = getattr(event.source, "user_id", "?") or "?"
        text = getattr(event, "text", "") or ""
        raw = (text or "(media)").encode("utf-8")
        if CryptProtectData:
            try:
                raw = base64.b64encode(
                    CryptProtectData(raw, None, None, None, None, 0)
                ).decode()
            except Exception:
                raw = text or "(media)"
        with open(_SANDGLASS, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {raw}\n")
    except Exception:
        logger.exception("sandglass: FAILED")
        try:
            with open(_ERRFLAG, "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_message)


# ── 解密工具 ──

def read(limit: int = 10) -> list:
    """解密读取最近 N 条沙漏消息。返回 [(时间戳, 发送人, 明文), ...]"""
    path = _SANDGLASS
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    results = []
    for line in lines:
        line = line.strip()
        if not line or " | " not in line:
            continue
        parts = line.split(" | ", 2)
        if len(parts) != 3:
            continue
        ts, sender, ciphertext = parts
        try:
            if CryptUnprotectData:
                encrypted = base64.b64decode(ciphertext.strip())
                plaintext = CryptUnprotectData(encrypted, None, None, None, 0)[1].decode("utf-8", errors="replace")
            else:
                plaintext = ciphertext  # 无 DPAPI 时直接返回（已是明文或 base64）
        except Exception:
            plaintext = ciphertext  # 解密失败返回原始内容
        results.append((ts, sender, plaintext))
    return results


def count() -> int:
    """沙漏总行数。"""
    path = _SANDGLASS
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)
