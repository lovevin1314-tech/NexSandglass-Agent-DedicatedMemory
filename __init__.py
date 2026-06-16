"""NexSandglass MemoryProvider — Hermes Memory Plugin."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sandglass_core"))

from memory_provider import NexSandglassProvider

def register(ctx) -> None:
    ctx.register_memory_provider(NexSandglassProvider())
