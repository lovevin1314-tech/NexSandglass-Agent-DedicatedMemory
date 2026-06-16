"""NexSandglass MemoryProvider — Hermes Memory Plugin.

纯本地零依赖。四路并发搜索 + 偏移率感知 + 管道聚合画像 + 三块式轮次注入。
"""

def register(ctx) -> None:
    """Hermes插件入口 — 延迟导入避免dashboard死锁。"""
    from memory_provider import NexSandglassProvider
    provider = NexSandglassProvider()
    ctx.register_memory_provider(provider)
