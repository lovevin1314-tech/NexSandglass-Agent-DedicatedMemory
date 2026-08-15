"""NexSandglass Hermes 适配层——薄转发（熔炼任务 B）。

核心实现唯一来源：`sandglass_core/memory_provider.py`。
本文件只负责把核心目录放进 import 路径，并把 Hermes 的
`register(ctx)` 转发给核心 `register()`。任何业务逻辑都不得落在这里。
"""
from __future__ import annotations

import os
import sys

# 让 Hermes 加载根目录 __init__.py 时也能命中 sandglass_core 内的模块。
# plugin.py 已单独做过一次 sys.path 准备，这里再保证一次，幂等。
_CORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandglass_core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from memory_provider import NexSandglassProvider  # noqa: E402
from memory_provider import register as _core_register  # noqa: E402
from memory_provider import __version__  # noqa: E402

__all__ = ["NexSandglassProvider", "register", "__version__"]


def register(ctx) -> None:
    """Hermes 插件入口：仅转发核心注册，不在此组装业务逻辑。"""
    _core_register(ctx)
