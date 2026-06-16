"""NexSandglass MemoryProvider — Hermes Memory Plugin.

纯本地零依赖。四路并发搜索 + 偏移率感知 + 管道聚合画像 + 三块式轮次注入。
"""

def register(ctx) -> None:
    """Hermes插件入口 — 延迟导入避免dashboard死锁。防重复注册。"""
    from memory_provider import NexSandglassProvider
    provider = NexSandglassProvider()
    # 防重复：发现阶段plugin.py可能已意外注册
    try:
        ctx.register_memory_provider(provider)
    except Exception:
        pass  # 已注册则忽略
