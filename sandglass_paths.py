"""
NexSandglass 路径配置 — 单一真相来源 V2.2
===========================================
所有模块从这里获取 _NB，不再各自计算。
用法: from sandglass_paths import _NB, _SCRIPTS, _PERSONA, ... 
"""

import os

_NB = os.environ.get("NEXSANDBASE_HOME") or os.path.join(os.path.expanduser("~"), ".neurobase")
__version__ = "2.6.17"
_SCRIPTS = os.path.join(_NB, "scripts")
_PERSONA = os.path.join(_NB, "persona")
_ARCHIVE = os.path.join(_NB, "archive")

# 常用文件路径
_SANDGLASS = os.path.join(_NB, "sandglass.txt")
_SANDGLASS_DB = os.path.join(_NB, "sandglass.db")
_SANDGLASS_IDX = os.path.join(_NB, "sandglass.idx")
_SHADOW_DB = os.path.join(_NB, "shadow_sand.db")
_DECISION_PARTICLES = os.path.join(_NB, "decision_particles.txt")
_DECISION_VOCAB = os.path.join(_NB, "decision_vocab.txt")
_ECHO_WIND = os.path.join(_NB, "echo_wind.jsonl")
_EMOTION_VOCAB = os.path.join(_NB, "emotion_vocab.jsonl")
_IRON_RULES = os.path.join(_NB, "iron_rules.txt")

# 启动时必须存在的目录
_REQUIRED_DIRS = [_NB, _SCRIPTS, _PERSONA, _ARCHIVE]


def validate() -> dict:
    """启动时路径验证——创建缺失目录，返回状态报告。"""
    created = []
    existed = []
    for d in _REQUIRED_DIRS:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
        else:
            existed.append(d)
    return {"nb": _NB, "created": created, "existed": existed, "ok": True}
