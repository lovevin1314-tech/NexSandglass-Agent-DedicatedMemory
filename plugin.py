"""NeuroBase Sandglass Plugin — 消息落沙 + 记忆提供者。V2.11.1"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sandglass_core"))

import logging
from datetime import datetime
logger = logging.getLogger(__name__)

def _get_sandglass_path():
    from sandglass_paths import _NB
    return os.path.join(_NB, "sandglass.txt")

def _on_message(event, **_kw) -> None:
    try:
        sandglass_path = _get_sandglass_path()
        os.makedirs(os.path.dirname(sandglass_path), exist_ok=True)
        sender = getattr(event.source, "user_id", "") or ""
        if not sender: return
        text = getattr(event, "text", "") or "(media)"
        with open(sandglass_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {text}\n")
    except Exception:
        logger.exception("sandglass: FAILED")

def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_message)
    from memory_provider import NexSandglassProvider
    ctx.register_memory_provider(NexSandglassProvider())
