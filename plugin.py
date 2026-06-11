"""NeuroBase Sandglass Plugin — 全平台消息拦截落沙。V2.4.0: 明文存储。"""
import logging
import os
from sandglass_paths import _NB
from datetime import datetime

logger = logging.getLogger(__name__)

_SANDGLASS = os.path.join(_NB, "sandglass.txt")
_ERRFLAG = os.path.join(_NB, ".sandglass_error")


def _on_message(event, **_kw) -> None:
    """pre_gateway_dispatch 钩子——所有平台消息到达时落沙。"""
    try:
        os.makedirs(os.path.dirname(_SANDGLASS), exist_ok=True)
        sender = getattr(event.source, "user_id", "") or ""
        if not sender: return  # 只记用户消息——AI回复不落沙
        text = getattr(event, "text", "") or "(media)"
        with open(_SANDGLASS, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {text}\n")
    except Exception:
        logger.exception("sandglass: FAILED")
        try:
            with open(_ERRFLAG, "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_message)
