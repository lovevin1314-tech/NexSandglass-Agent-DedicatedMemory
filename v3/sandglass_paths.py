"""NexSandglass v3 路径配置 — 与 sandglass_core 保持一致（V2.20.5）"""
import os, logging
_logger = logging.getLogger(__name__)

def _resolve_nb() -> str:
    nb = os.environ.get("NEXSANDBASE_HOME")
    if nb and os.path.isdir(nb):
        return nb
    cfg = os.path.expanduser("~/.neurobase")
    os.makedirs(cfg, exist_ok=True)
    return cfg

_NB = _resolve_nb()
__version__ = "3.1.1"

_REQUIRED_DIRS = [_NB, os.path.join(_NB, "persona"), os.path.join(_NB, "archive")]

def validate() -> dict:
    """启动时路径验证——创建缺失目录，返回状态报告（与 sandglass_core 版一致）。"""
    created = []
    existed = []
    for d in _REQUIRED_DIRS:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
        else:
            existed.append(d)
    return {"nb": _NB, "created": created, "existed": existed, "ok": True}
