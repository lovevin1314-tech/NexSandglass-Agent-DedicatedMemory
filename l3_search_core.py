#!/usr/bin/env python3
"""
NexSandglass L3 — 搜索核心模块
_synonym_expand / _tfidf_search / composite_rerank / _search_with_fallback
_sentiment_wind / sentiment_rerank / simhash / simhash_search + _SYNONYMS 词表

V2.0.1: +SimHash语义搜索(零依赖纯Python)
"""

import re
import math
import os
import hashlib

# ═══════════════════════════════════════════════════════
# SimHash 语义哈希（Google 2007，纯stdlib，零依赖）
# 文本→128bit指纹，汉明距离越小=语义越近
# ═══════════════════════════════════════════════════════

_SIMHASH_BITS = 128


def _tokenize_simhash(text: str) -> list:
    """中文2-gram + 英文分词"""
    tokens = []
    chars = re.findall(r'[\u4e00-\u9fff]', text)
    for i in range(len(chars) - 1):
        tokens.append(''.join(chars[i:i+2]))
    tokens.extend(re.findall(r'[a-zA-Z]{2,}', text.lower()))
    return tokens


def simhash(text: str, bits: int = _SIMHASH_BITS) -> int:
    """文本→SimHash指纹。零依赖。空文本返回-1。"""
    tokens = _tokenize_simhash(text)
    if not tokens:
        return -1  # 空文本标记，避免碰撞为0
    v = [0] * bits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(bits):
            if (h >> (i % 128)) & 1:
                v[i] += 1
            else:
                v[i] -= 1
    fp = 0
    for i in range(bits):
        if v[i] > 0:
            fp |= (1 << i)
    return fp


def _hamming(a: int, b: int) -> int:
    """汉明距离。任一为-1(空文本)返回MAX。"""
    if a == -1 or b == -1:
        return _SIMHASH_BITS  # 最大距离=完全不同
    return (a ^ b).bit_count()


def simhash_search(query: str, candidates: list, limit: int = 20, threshold: int = None) -> list:
    """SimHash语义搜索——从候选文档中返回最相似的limit条。
    candidates: [(line_no, timestamp, text), ...]
    threshold: 自适应——短查询(≤5 tokens)用30, 长查询用50
    """
    if not candidates:
        return []
    q_fp = simhash(query)
    if q_fp == -1:  # 空文本查询，无法语义搜索
        return []
    
    # 自适应阈值：token太少时较严(但不过严)，token多时宽松
    q_tokens = _tokenize_simhash(query)
    if threshold is None:
        threshold = 40 if len(q_tokens) <= 5 else 55
    
    scored = []
    for ln, ts, text in candidates:
        d_fp = simhash(text[:500])
        if d_fp == -1:
            continue
        dist = _hamming(q_fp, d_fp)
        if dist <= threshold:
            scored.append((dist, ln, ts, text))
    scored.sort(key=lambda x: x[0])
    return [(ln, ts, text) for _, ln, ts, text in scored[:limit]]

# ═══════════════════════════════════════════════════════
# 通用技术同义词（模块级常量）
# ═══════════════════════════════════════════════════════
_SYNONYMS = {
    # 技术
    "加密": ["DPAPI", "保护", "安全", "隐私", "密钥", "密文"],
    "安全": ["保护", "加密", "隐私", "防护", "DPAPI"],
    "搜索": ["检索", "查询", "查找", "定位", "seek", "find"],
    "记忆": ["存储", "持久化", "memory", "记录", "存档", "回忆"],
    "画像": ["人格", "persona", "profile", "特征", "用户"],
    "偏移": ["变化", "漂移", "shift", "偏移率", "改变", "转向"],
    "索引": ["index", "目录", "倒排", "检索", "关键词"],
    "阶段": ["stage", "时期", "phase", "周期", "时间段"],
    "决策": ["选择", "决定", "判断", "decision", "判断力"],
    "语义": ["含义", "意思", "semantic", "理解", "上下文"],
    "系统": ["框架", "platform", "平台", "架构", "体系"],
    "代理": ["agent", "AI", "助手", "助理", "机器人"],
    "安装": ["部署", "配置", "setup", "install", "搭建"],
    "错误": ["bug", "问题", "异常", "error", "故障", "失败"],
    "优化": ["改进", "提升", "加速", "性能", "效率"],
    "配置": ["设置", "config", "参数", "选项", "环境"],
    "权限": ["保护", "隔离", "sandbox", "限制", "访问"],
    "数据": ["信息", "data", "内容", "记录", "文件"],
    "本地": ["local", "离线", "本地化", "客户端", "本机"],
    "云端": ["cloud", "远程", "在线", "服务器", "SaaS"],
    # 成本/价值（V2.0.1扩）
    "免费": ["不花钱", "开源", "无需付费", "free"],
    "付费": ["花钱", "购买", "订阅", "买", "收费", "pay"],
    "便宜": ["低价", "实惠", "划算", "廉价", "低成本"],
    "省钱": ["节约", "性价比", "经济", "节省", "省"],
    "效率": ["快速", "省事", "高效", "方便", "自动化"],
    "质量": ["好用", "稳定", "可靠", "精准", "准确"],
    # 行为/偏好（V2.0.1扩）
    "喜欢": ["偏好", "倾向", "习惯", "爱", "常用"],
    "讨厌": ["反感", "不喜欢", "烦", "受不了", "拒绝"],
    "自己": ["DIY", "手工", "亲自", "独立", "自主"],
    "外包": ["委托", "找人", "代劳", "付费做", "服务"],
    "简单": ["容易", "轻松", "不复杂", "直接", "快"],
    "复杂": ["麻烦", "困难", "繁琐", "难搞", "折腾"],
}


def _synonym_expand(query: str) -> list:
    """本地同义词扩展——零 LLM 消耗，覆盖 80% 语义搜索场景。
    返回 [原词, 同义词1, 同义词2, ...]"""
    keywords = [query]
    seen = {query}
    # 2-gram 滑窗分词（和 _tokenize 一致）
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", query))
    for i in range(len(chars) - 1):
        word = chars[i:i + 2]
        for syn in _SYNONYMS.get(word, []):
            if syn not in seen:
                keywords.append(syn)
                seen.add(syn)
    return keywords


def _tfidf_search(query: str, limit: int = 10) -> list:
    """本地 TF-IDF 语义搜索——纯 stdlib，零外部依赖。
    作为语义搜索的第三条 fallback 路径。"""
    from sandglass_vault import recent, search as vs, _tokenize

    candidates = {}
    for ln, ts, text in recent(200):
        candidates[ln] = text
    for ln, ts, text in vs(query, limit=50):
        candidates[ln] = text
    if not candidates:
        return []

    docs = {ln: _tokenize(text) for ln, text in candidates.items()}
    qt = _tokenize(query)
    N = len(docs)
    df = {}
    for tokens in docs.values():
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
    q_tf = {}
    for t in qt: q_tf[t] = q_tf.get(t, 0) + 1
    q_vec = {t: (q_tf[t] / max(len(qt), 1)) * idf.get(t, 0) for t in q_tf}

    results = []
    for ln, tokens in docs.items():
        d_tf = {}
        for t in tokens: d_tf[t] = d_tf.get(t, 0) + 1
        d_vec = {t: (d_tf[t] / max(len(tokens), 1)) * idf.get(t, 0) for t in d_tf}
        dot = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in set(list(q_vec.keys()) + list(d_vec.keys())))
        q_norm = math.sqrt(sum(v**2 for v in q_vec.values())) or 1
        d_norm = math.sqrt(sum(v**2 for v in d_vec.values())) or 1
        sim = dot / (q_norm * d_norm) if (q_norm * d_norm) > 0 else 0
        if sim > 0.05:
            results.append((ln, candidates[ln][:100], round(sim, 3)))
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:limit]


def composite_rerank(results, weights, text_w=0.6, ext_w=0.4):
    """Composite Linear + Min-Max：多信号归一化→加权求和重排。
    results: [(ln, ts, text, kw), ...] | weights: {kw: w, ...}"""
    if not results or not weights:
        return sorted(results, key=lambda x: x[0], reverse=True)

    # 文本相关性proxy：关键词命中次数（越长≠越相关）
    keywords = list(weights.keys()) if weights else []
    scores = []
    for item in results:
        kw = item[3] if len(item) > 3 else ""
        text = item[2].lower() if len(item) > 2 else ""
        hit_count = sum(1 for k in keywords if k.lower() in text) if keywords else 1
        ext_w_val = weights.get(kw, 1.0)
        scores.append((hit_count, ext_w_val, item))

    # Min-Max归一化
    t_vals = [s[0] for s in scores]
    w_vals = [s[1] for s in scores]
    t_min, t_max = min(t_vals), max(t_vals)
    w_min, w_max = min(w_vals), max(w_vals)

    def norm(v, lo, hi):
        return (v - lo) / (hi - lo) if hi > lo else 0.5

    composites = [(norm(t, t_min, t_max) * text_w + norm(w, w_min, w_max) * ext_w, item)
                  for t, w, item in scores]
    composites.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in composites]


def _search_with_fallback(expanded, vs, limit=10, weights=None):
    """用扩展关键词搜索，去重排序。weights 可选 {kw: multiplier}。"""
    seen = set()
    results = []
    for kw in expanded[:8]:
        hits = vs(kw, limit=limit * 2)
        for ln, ts, text in hits:
            if ln not in seen:
                seen.add(ln)
                results.append((ln, ts, text, kw))
    if results:
        if weights:
            results = composite_rerank(results, weights)
        else:
            results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]
    return []


def _sentiment_wind() -> float:
    """20条EMA加权情绪风向。越近权重越高。>0正面 <0负面。"""
    from sandglass_vault import recent
    from emotion_vocab import detect as emotion_detect
    sands = recent(20)
    if not sands: return 0.0
    mood_scores = {"开心": 1, "意外": 0.5, "困惑": -0.5,
                   "悲伤": -1, "焦虑": -1, "愤怒": -1, "放弃": -1}
    scores = []
    for i, (_, _, text) in enumerate(sands):
        det = emotion_detect(text)
        if det.get("mood"):
            weight = (i + 1) / len(sands)  # 最近权重最高
            scores.append(mood_scores.get(det["mood"], 0) * weight)
    return round(sum(scores) / max(len(scores), 1), 2)


def sentiment_rerank(results, wind: float):
    """情感重排——正面风推正面内容，负面风推中性内容。"""
    if abs(wind) < 0.3 or not results: return results
    from emotion_vocab import load_vocab
    vocab = load_vocab()
    positive_words = set(vocab.get("开心", {}).get("zh", []) + vocab.get("开心", {}).get("en", []))
    negative_words = set()
    for mood in ["悲伤", "焦虑", "愤怒", "放弃"]:
        negative_words.update(vocab.get(mood, {}).get("zh", []))
        negative_words.update(vocab.get(mood, {}).get("en", []))

    scored = []
    for item in results:
        text = item[2] if len(item) > 2 else ""
        pos = sum(1 for w in positive_words if w in text)
        neg = sum(1 for w in negative_words if w in text)
        sentiment_score = (pos - neg) / max(len(text.split()), 1)
        if wind > 0:
            boost = sentiment_score * wind * 0.2
        elif wind < 0:
            if sentiment_score > 0:
                boost = -sentiment_score * abs(wind) * 0.2  # 负面风压正面
            elif sentiment_score < 0:
                boost = sentiment_score * abs(wind) * 0.1   # 轻微压负面
            else:
                boost = abs(wind) * 0.15  # 中性浮上来
        else:
            boost = 0
        scored.append((boost, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]
