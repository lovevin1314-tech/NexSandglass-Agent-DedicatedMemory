"""NexSandglass MemoryProvider — Hermes Memory Plugin.

纯本地零依赖。四路并发搜索 + 偏移率感知 + 管道聚合画像 + 三块式轮次注入。
"""
from memory_provider import NexSandglassProvider, MemoryProvider

def register(ctx) -> None:
    """Hermes插件入口 — 注册 MemoryProvider 到记忆体选择列表。"""
    provider = NexSandglassProvider()
    ctx.register_memory_provider(provider)
