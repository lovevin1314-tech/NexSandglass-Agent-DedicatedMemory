"""NexSandglass Plugin — 全平台消息拦截落沙。"""
import base64
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
_ERRFLAG = os.path.join(os.path.expanduser("~"), ".neurobase", ".sandglass_error")

try:
    from win32crypt import CryptProtectData
except ImportError:
    CryptProtectData = None


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
