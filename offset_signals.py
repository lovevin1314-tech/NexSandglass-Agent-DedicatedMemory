"""NexSandglass 偏移信号词库 — 单一真相来源。
sandglass_think 和 decision_particles 都从这里导入，消除循环依赖。"""

import logging

_OFFSET_SIGNALS = {
    "frugal": ["免费", "不花钱", "自己搞", "本地", "省钱", "性价比", "开源"],
    "spend": ["花钱", "省事", "买", "付费", "订阅", "不值", "效率优先"],
    "drift_放弃": ["不管了", "放弃", "不搞了"],
    "drift_妥协": ["能用就行", "不纠结", "就那样", "将就"],
    "drift_烦躁": ["随便", "算了", "就这样"],
}


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
