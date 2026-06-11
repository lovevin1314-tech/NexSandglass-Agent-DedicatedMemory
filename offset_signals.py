"""NexSandglass 偏移信号词库 — 单一真相来源。
sandglass_think 和 decision_particles 都从这里导入，消除循环依赖。"""

import os
import logging

# ── 偏移信号词库 ──
_OFFSET_SIGNALS = {
    "frugal": ["免费", "不花钱", "自己搞", "本地", "省钱", "性价比", "开源"],
    "spend": ["花钱", "省事", "买", "付费", "订阅", "不值", "效率优先"],
    "drift_放弃": ["不管了", "放弃", "不搞了", "不做了", "算了不弄", "不想管", "懒得弄", "不折腾了"],
    "drift_妥协": ["能用就行", "不纠结", "就那样", "将就", "凑合", "差不多得了", "无所谓了", "先这样吧"],
    "drift_烦躁": ["随便", "算了", "就这样", "烦死了", "受不了", "太麻烦", "真无语", "够了"],
}

# ── LLM 配置（单一来源）──
_LLM_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
_deepseek_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
_LLM_ENDPOINT = "https://api.deepseek.com/v1/chat/completions" if _deepseek_key else "https://openrouter.ai/api/v1/chat/completions"
_LLM_MODEL = "deepseek-v4-flash" if _deepseek_key else "deepseek/deepseek-v4-flash"


def _fail_open(default):
    """装饰器：任何异常返回 default 值并 log warning。"""
    logger = logging.getLogger(__name__)
    def deco(func):
        def wrapper(*a, **kw):
            try:
                return func(*a, **kw)
            except Exception as e:
                logger.warning(f"{func.__name__} failed, returning default: {e}")
                return default
        return wrapper
    return deco
