"""NeuroBase Sandglass Plugin — 消息落沙 + 记忆提供者。V2.10.10"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_sandglass_path():
    """延迟获取沙漏路径——避免模块加载时导入依赖。"""
    import os
    from sandglass_paths import _NB
    return os.path.join(_NB, "sandglass.txt")

def _on_message(event, **_kw) -> None:
    """pre_gateway_dispatch 钩子——所有平台消息到达时落沙。"""
    try:
        import os
        sandglass_path = _get_sandglass_path()
        os.makedirs(os.path.dirname(sandglass_path), exist_ok=True)
        sender = getattr(event.source, "user_id", "") or ""
        if not sender: return
        text = getattr(event, "text", "") or "(media)"
        with open(sandglass_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {text}\n")
    except Exception:
        logger.exception("sandglass: FAILED")
        try:
            import os
            from sandglass_paths import _NB
            with open(os.path.join(_NB, ".sandglass_error"), "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

def register(ctx) -> None:
    """Hermes插件入口。发现阶段安全退避——memory_provider延迟至激活时加载。"""
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    # Gateway: 消息落沙（轻量，永远安全）
    ctx.register_hook("pre_gateway_dispatch", _on_message)
    # Memory: 发现阶段不加载——等用户激活时由Hermes调__init__.py的register()
    try:
        from memory_provider import NexSandglassProvider
        ctx.register_memory_provider(NexSandglassProvider())
    except Exception:
        pass  # 发现阶段死锁→静默跳过；激活时会重试
