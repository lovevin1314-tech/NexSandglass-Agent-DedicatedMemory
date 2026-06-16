"""NexSandglass MemoryProvider — Hermes Memory Plugin.

纯本地零依赖。四路并发搜索 + 偏移率感知 + 管道聚合画像 + 三块式轮次注入。

LazyProvider: 发现阶段零导入→不死锁；激活时首次调用→加载完整功能。
"""

class LazyNexSandglassProvider:
    """懒加载代理——发现阶段零开销，首次调用时才导入真实实现。"""
    _real = None

    def _get_real(self):
        if self._real is None:
            from memory_provider import NexSandglassProvider
            self._real = NexSandglassProvider()
        return self._real

    @property
    def name(self): return "nexsandglass"

    def is_available(self): return True

    def initialize(self, *args, **kwargs):
        return self._get_real().initialize(*args, **kwargs)

    def shutdown(self):
        if self._real:
            self._real.shutdown()

    def prefetch(self, query):
        return self._get_real().prefetch(query)

    def queue_prefetch(self, query):
        return self._get_real().queue_prefetch(query)

    def sync_turn(self, user_msg, assistant_msg, **kwargs):
        return self._get_real().sync_turn(user_msg, assistant_msg, **kwargs)

    def system_prompt_block(self):
        return self._get_real().system_prompt_block()

    def get_tool_schemas(self):
        return self._get_real().get_tool_schemas()

    def handle_tool_call(self, name, args):
        return self._get_real().handle_tool_call(name, args)


def register(ctx) -> None:
    """Hermes插件入口。LazyProvider: 发现阶段零导入，激活后按需加载。"""
    ctx.register_memory_provider(LazyNexSandglassProvider())
