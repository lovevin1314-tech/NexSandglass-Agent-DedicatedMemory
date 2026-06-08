"""
NexSandglass — 第二层：米粒索引 + 解密读取
===========================================
import sandglass_vault
results = sandglass_vault.search("关键词")
latest = sandglass_vault.recent(5)
"""

import base64
import logging
import os
import re

_SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
_IDX = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.idx")

logger = logging.getLogger(__name__)

try:
    from win32crypt import CryptUnprotectData
except ImportError:
    CryptUnprotectData = None

# ── idx 内存缓存（偷师 memory-os：O(1) 查 token）──
_idx_cache: dict | None = None


# ═══════════════════════════════════════════════
# 米粒索引
# ═══════════════════════════════════════════════

def _tokenize(text: str) -> set:
    """通用分词：中文2字词+英文2+字母。不索引单汉字（高频噪音）。"""
    tokens = set()
    tokens.update(re.findall(r"[a-zA-Z0-9_]{2,}", text.lower()))
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    for i in range(len(chars) - 1):
        tokens.add(chars[i : i + 2])
    return {t for t in tokens if t}


def _query_tokens(text: str) -> set:
    """搜索分词：和_tokenize相同，但单字仅当输入只有一个中文字时才保留。"""
    tokens = _tokenize(text)
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    if len(chars) != 1:
        tokens -= set(chars)  # 去单字
    return tokens


def _decrypt(text: str) -> str:
    """DPAPI 解密。失败返回原文。"""
    text = text.strip()
    if not text.startswith("AQAA"):
        return text
    if not CryptUnprotectData:
        return text
    try:
        raw = base64.b64decode(text)
        return CryptUnprotectData(raw, None, None, None, 0)[1].decode("utf-8")
    except Exception:
        return text


def _parse_line(line: str) -> tuple:
    """返回 (ts, sender, decrypted_text) 或 (None, None, None)。"""
    if " | " not in line:
        return None, None, None
    parts = line.strip().split(" | ", 2)
    if len(parts) < 3:
        return None, None, None
    return parts[0], parts[1], _decrypt(parts[2])


def rebuild_index() -> int:
    """全量重建米粒索引（基于解密后文本）。原子写。返回词条数。"""
    global _idx_cache
    _idx_cache = None
    try:
        if not os.path.exists(_SANDGLASS):
            return 0
        idx = {}
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                ts, sender, text = _parse_line(line)
                if not ts:
                    continue
                for token in _tokenize(text):
                    idx.setdefault(token, []).append(n)

        tmp = _IDX + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for token in sorted(idx):
                f.write(f"{token}:{','.join(map(str, sorted(set(idx[token]))))}\n")
        os.replace(tmp, _IDX)
        return len(idx)
    except Exception:
        logger.warning("sandglass: rebuild_index() failed", exc_info=True)
        return 0


def _sync_index() -> dict:
    """增量更新索引并返回内存 dict。利用缓存避免重复读盘。"""
    global _idx_cache

    try:
        if not os.path.exists(_SANDGLASS):
            _idx_cache = {}
            return {}

        total = 0
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)

        # 缓存命中：缓存非空且 idx 文件未变（通过检查已有缓存的最大行号）
        if _idx_cache is not None:
            cached_max = 0
            for lines in _idx_cache.values():
                if lines:
                    cached_max = max(cached_max, max(lines))
            # idx 文件最后一行号 ≥ total 且缓存覆盖了它 → 缓存有效
            if cached_max >= total and total > 0:
                return _idx_cache

        # 读 idx
        idx = {}
        idx_max = 0
        if os.path.exists(_IDX):
            with open(_IDX, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    t, rest = line.strip().split(":", 1)
                    nums = [int(x) for x in rest.split(",") if x]
                    idx[t] = nums
                    if nums:
                        idx_max = max(idx_max, max(nums))

        if idx_max >= total:
            _idx_cache = idx
            return idx

        # 增量：追加新行
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if n <= idx_max:
                    continue
                ts, sender, text = _parse_line(line)
                if not ts:
                    continue
                for token in _tokenize(text):
                    idx.setdefault(token, []).append(n)

        # 原子写
        tmp = _IDX + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for token in sorted(idx):
                f.write(f"{token}:{','.join(map(str, sorted(set(idx[token]))))}\n")
        os.replace(tmp, _IDX)

        _idx_cache = idx
        return idx

    except Exception:
        logger.warning("sandglass: _sync_index() failed", exc_info=True)
        return _idx_cache if _idx_cache else {}


# ═══════════════════════════════════════════════
# 搜索 + 读取
# ═══════════════════════════════════════════════

def search(query: str, limit: int = 10, month: str = "") -> list:
    """搜索沙漏。返回 [(行号, 时间, 明文), ...]。month 可选 '2026-06'。"""
    try:
        if not os.path.exists(_SANDGLASS):
            return []
        if not os.path.exists(_IDX):
            rebuild_index()

        tokens = _query_tokens(query)
        if not tokens:
            return []

        # ── 增量同步 + 内存 idx（一次读盘，缓存命中零读盘）──
        idx = _sync_index()
        if not idx:
            return []

        # OR 语义：每个匹配 token 的行都加入，记录匹配 token 数用于排序
        line_scores: dict = {}  # line_num → match_count
        for token in tokens:
            for ln in idx.get(token, []):
                line_scores[ln] = line_scores.get(ln, 0) + 1

        if not line_scores:
            return []

        results = []
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if n not in line_scores:
                    continue
                ts, sender, text = _parse_line(line)
                if not ts:
                    continue
                if month and not ts.startswith(month):
                    continue
                results.append((n, ts, text, line_scores[n]))

        # ── 匹配数降序 → 行号降序（最新优先）──
        results.sort(key=lambda x: (x[3], x[0]), reverse=True)
        return [(n, ts, text) for n, ts, text, _ in results[:limit]]

    except Exception:
        logger.warning("sandglass: search(%r) failed", query, exc_info=True)
        return []


def recent(n: int = 10) -> list:
    """最近 N 条。[(行号, 时间, 明文), ...]"""
    try:
        if n <= 0 or not os.path.exists(_SANDGLASS):
            return []
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)
        n = min(n, total)
        results = []
        for i, line in enumerate(lines[-n:]):
            ts, sender, text = _parse_line(line)
            if not ts:
                continue
            ln = total - n + i + 1
            results.append((ln, ts, text))
        return results
    except Exception:
        logger.warning("sandglass: recent(%d) failed", n, exc_info=True)
        return []


def count() -> int:
    try:
        if not os.path.exists(_SANDGLASS):
            return 0
        with open(_SANDGLASS, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        logger.warning("sandglass: count() failed", exc_info=True)
        return 0


# ═══════════════════════════════════════════════
# 时间回溯
# ═══════════════════════════════════════════════

def timeline(query: str) -> dict:
    """时间回溯——按年份分层返回关键词的演变轨迹。"""
    try:
        all_results = search(query, limit=10000)
        if not all_results:
            return {}
        # 按行号升序（时间顺序），而非 reverse search 的匹配数排序
        all_results.sort(key=lambda x: x[0])

        years = {}
        for ln, ts, text in all_results:
            year = ts[:4]
            if year not in years:
                years[year] = {"count": 0, "earliest": text, "earliest_at": ts, "latest": text, "latest_at": ts}
            years[year]["count"] += 1
            years[year]["latest"] = text
            years[year]["latest_at"] = ts

        result = {}
        for year in sorted(years):
            y = years[year]
            result[year] = {"count": y["count"], "earliest": y["earliest"], "earliest_at": y["earliest_at"],
                            "latest": y["latest"], "latest_at": y["latest_at"]}
        return result
    except Exception:
        logger.warning("sandglass: timeline(%r) failed", query, exc_info=True)
        return {}
