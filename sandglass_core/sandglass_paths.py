"""
NexSandglass 路径配置 — 单一真相来源 V2.2
===========================================
所有模块从这里获取 _NB，不再各自计算。
用法: from sandglass_paths import _NB, _SCRIPTS, _PERSONA, ... 
"""

import os, logging
_logger = logging.getLogger(__name__)

def _resolve_nb() -> str:
    """V2.10.29: 多级fallback——环境变量→config.yaml→默认。含路径诊断日志。"""
    # 1. 环境变量优先
    nb = os.environ.get("NEXSANDBASE_HOME")
    if nb and os.path.isdir(nb):
        _logger.info(f"NexSandglass: 路径=环境变量 {nb}")
        return nb
    
    # 2. Hermes config.yaml
    for cfg_path in [
        os.path.join(os.path.expanduser("~"), ".hermes", "config.yaml"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "config.yaml"),
    ]:
        try:
            import yaml
            with open(cfg_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            nb = cfg.get("memory", {}).get("nexsandglass", {}).get("home")
            if nb and os.path.isdir(nb):
                _logger.info(f"NexSandglass: 路径=config.yaml {nb}")
                return nb
        except ImportError:
            _logger.debug("yaml未安装,跳过config.yaml解析")
        except Exception as e:
            _logger.warning(f"config.yaml解析失败: {e}")
    
    # 3. 默认
    default = os.path.join(os.path.expanduser("~"), ".neurobase")
    _logger.warning(f"NexSandglass: 路径=默认 {default} (检查NEXSANDBASE_HOME或config.yaml)")
    return default

_NB = _resolve_nb()
__version__ = "2.10.29"
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
_EMOTION_VOCAB = os.path.join(_NB, "emotion_vocab.json")
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
