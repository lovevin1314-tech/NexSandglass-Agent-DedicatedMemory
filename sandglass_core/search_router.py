"""
NexSandglass SearchRouter V2.8.6 — 四路并发搜索架构（统一入口）
==================================================================
影子沙 + FTS5 + IDX + TF-IDF 四路并发 → 沙子密度融合(trust+simhash) → mmap兜底

V2.8.6: 统一搜索入口 — search_semantic 委托 SearchRouter
       density×trust+simhash_bonus 统一公式
       SimHash 统一为 l3_search_core 128-bit
       密度计算与IDX/TF-IDF同源(_query_tokens)
       删除重复 _simhash / _simhash_density_decay
"""
import os, mmap, re, concurrent.futures, math
from sandglass_vault import _SANDGLASS, _parse_line
from sandglass_paths import _NB
import statistics
import logging

# V2.11.1: 本地 stub——避免循环导入 memory_provider
def _pipe_warn(name, e):
    logging.getLogger(__name__).warning(f"管道 [{name}] 降级: {e}")
from l3_search_core import simhash as _l3_simhash
from sandglass_vault import _query_tokens

# V2.9.9.8: 语义信号缓存
_tagged_cache = None
_tag_idf = None  # V2.9.9.8: IDF标签稀有度缓存

def _load_tag_idf():
    global _tag_idf
    import math, sqlite3, os
    db_path = os.path.join(_NB, "shadow_sand.db")
    if not os.path.exists(db_path): return {}
    db = sqlite3.connect(db_path, check_same_thread=False)
    freq = {}
    for r in db.execute("SELECT tags FROM fact_tags WHERE tags != '' AND tags != '未分类'"):
        for t in r[0].split(','):
            t = t.strip()
            if t: freq[t] = freq.get(t, 0) + 1
    db.close()
    total = sum(freq.values())
    _tag_idf = {t: math.log(total / max(v, 1)) for t, v in freq.items()}
    return _tag_idf
_tagged_mtime = 0
_offset_vocab = None


def _detect_lang(text: str) -> str:
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    eng = sum(1 for c in text if c.isascii() and c.isalpha())
    if cjk and eng: return "mixed"
    return "zh" if cjk >= eng else "en"


def simhash_rerank(candidates, query) -> list:
    q_fp = _l3_simhash(query)
    if q_fp == -1:
        return candidates
    def hamming(item):
        text = item[2] if len(item) > 2 else ""
        fp = _l3_simhash(text[:500])
        if fp == -1: return 999
        return bin(fp ^ q_fp).count('1')
    return sorted(candidates, key=hamming)


def sand_density(candidates, query_tokens, query) -> list:
    """V2.9.9.11r: 回归ratio + trust + SimHash — 对语义理解更精准"""
    q_fp = _l3_simhash(query)
    if q_fp == -1: q_fp = 0
    trust_scores = {}
    try:
        from shadow_sand import shadow_boost
        line_nums = {c[0] for c in candidates if len(c) > 0}
        boosted = shadow_boost(line_nums, limit=len(candidates))
        trust_scores = {ln: score for score, ln in boosted}
    except Exception as e:
        _pipe_warn("search_router_L71", e)

    q_len = max(len(query_tokens), 1)
    scored = []
    for item in candidates:
        ln = item[0]; text = item[2] if len(item) > 2 else ""
        text_tokens = _query_tokens(text)
        # ratio: matched/query — 一眼看懂,0=无关,1=完全匹配
        matched = len(query_tokens & text_tokens)
        ratio = matched / q_len
        trust = trust_scores.get(ln, 0.5)
        # SimHash bonus
        fp = _l3_simhash(text[:500])
        if fp == -1: sim_bonus = 0
        else:
            dist = bin(q_fp ^ fp).count('1')
            sim_bonus = 0.5 * (1 - dist / 128)  # V2.9.27: 线性映射,d=0→0.5,d=128→0
        final = ratio * trust + sim_bonus
        scored.append((final, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


def dynamic_expand(candidates, tokens, limit: int) -> list:
    if len(candidates) >= limit:
        return candidates[:limit]
    expanded = candidates[:]
    seen = {c[0] if len(c) > 0 else 0 for c in expanded}
    for item in candidates[limit:]:
        text = item[2] if len(item) > 2 else ""
        if any(t.lower() in text.lower() for t in tokens):
            if item[0] not in seen:
                expanded.append(item)
                seen.add(item[0])
                if len(expanded) >= limit * 2:
                    break
    return expanded[:limit * 2]


class ShadowSearch:
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS
    def search(self, query: str, limit: int = 30) -> list:
        try:
            from shadow_sand import shadow_search
            return shadow_search(query, limit)
        except Exception:
            return []


class Fts5Search:
    def search(self, query: str, limit: int = 30) -> list:
        try:
            from sandglass_sqlite import search as fts5_search, sync_incremental
            sync_incremental()
            return fts5_search(query, limit)
        except Exception:
            return []


class IdxSearch:
    """IDX倒排索引搜索—中文子串+英文模糊。独立可测。"""
    def __init__(self, sandfile=None, idx_path=None):
        self.sandfile = sandfile
        self.idx_path = idx_path

    def search(self, query: str, limit: int = 30) -> list:
        try:
            from sandglass_vault import _sync_index, _query_tokens
            idx = _sync_index()
            if not idx:
                try:
                    from sandglass_vault import rebuild_index
                    rebuild_index()
                    idx = _sync_index()
                except Exception:
                    return []
            if not idx: return []
            tokens = _query_tokens(query)
            candidates = {}
            for token in tokens:
                if token in idx:
                    for ln in idx[token]:
                        candidates[ln] = candidates.get(ln, 0) + 1
            if not candidates: return []
            results = []
            with open(_SANDGLASS, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if n in candidates:
                        ts, sender, text = _parse_line(line)
                        if ts and text:
                            results.append((n, ts, text, candidates[n]))
            results.sort(key=lambda x: x[3], reverse=True)
            return [(r[0], r[1], r[2]) for r in results[:limit]]
        except Exception:
            return []


class TfidfSearch:
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS
    def search(self, query: str, limit: int = 30) -> list:
        try:
            from sandglass_vault import _query_tokens
            tokens = _query_tokens(query)
            if not tokens: return []
            all_lines = []
            with open(self.sandfile, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if " | " in line:
                        ts, sender, text = _parse_line(line)
                        if ts and text:
                            all_lines.append((n, ts, text))
            if not all_lines: return []
            N = len(all_lines)
            df = {}
            for token in tokens:
                df[token] = sum(1 for _, _, text in all_lines if token in text.lower())
            scored = []
            for ln, ts, text in all_lines:
                score = 0
                for token in tokens:
                    if token in text.lower():
                        tf = text.lower().count(token) / max(len(text), 1)
                        idf = math.log((N + 1) / (df.get(token, 0) + 1))
                        score += tf * idf
                if score > 0:
                    scored.append((score, ln, ts, text))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [(ln, ts, text) for _, ln, ts, text in scored[:limit]]
        except Exception:
            return []


class MmapFallback:
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS
    def search(self, query: str, limit: int = 30) -> list:
        results = []
        results_token = []
        try:
            from sandglass_vault import _query_tokens
            tokens = _query_tokens(query)
            has_tokens = bool(tokens)
            with open(self.sandfile, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    ln = 0
                    for line in iter(mm.readline, b""):
                        ln += 1
                        try:
                            decoded = line.decode("utf-8", errors="ignore").strip()
                            if " | " not in decoded: continue
                            parts = decoded.split(" | ", 2)
                            if len(parts) < 3: continue
                            ts, sender, text = parts
                            if query.lower() in text.lower():
                                results.append((ln, ts, text[:300]))
                                if len(results) >= limit: break
                            elif has_tokens and any(tk in text.lower() for tk in tokens):
                                if len(results_token) < limit:
                                    results_token.append((ln, ts, text[:300]))
                        except: pass
            if not results and results_token:
                results = results_token[:limit]
            if results:
                from sandglass_sqlite import search_in, sync_incremental
                lns = [r[0] for r in results[:500]]
                sync_incremental()
                ranked = search_in(lns, query)
                if ranked:
                    return [(r[0], r[1], r[2]) for r in ranked[:limit]]
            return results[:limit]
        except Exception:
            return []


class SearchRouter:
    """搜索路由器——四路并发 + 沙子密度融合(density×trust+simhash) + 动态扩窗 + mmap兜底。
    V2.8.6: 统一为唯一搜索入口。
    """
    def __init__(self, shadow=None, fts5=None, idx=None, tfidf=None, mmap_fb=None):
        self.shadow = shadow or ShadowSearch()
        self.fts5 = fts5 or Fts5Search()
        self.idx = idx or IdxSearch()
        self.tfidf = tfidf or TfidfSearch()
        self.mmapfallback = mmap_fb or MmapFallback()

    def search(self, query: str, limit: int = 30) -> list:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            fut_shadow = ex.submit(self.shadow.search, query, limit)
            fut_fts5 = ex.submit(self.fts5.search, query, max(limit * 2, 30))
            fut_idx = ex.submit(self.idx.search, query, max(limit * 2, 30))
            fut_tfidf = ex.submit(self.tfidf.search, query, max(limit * 2, 30))
        shadow_hits = fut_shadow.result() or []
        fts5_hits = fut_fts5.result() or []
        idx_hits = fut_idx.result() or []
        tfidf_hits = fut_tfidf.result() or []
        if shadow_hits:
            try:
                from shadow_sand import shadow_retrieval_bump
                shadow_retrieval_bump([ln for _, ln in shadow_hits[:limit]])
            except: pass
        all_candidates = []
        seen = set()
        for hits in [fts5_hits, idx_hits, tfidf_hits]:
            for item in hits:
                ln = item[0]
                if ln not in seen:
                    seen.add(ln)
                    all_candidates.append(item)
        if shadow_hits:
            with open(_SANDGLASS, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for score, ln in shadow_hits[:limit]:
                if ln not in seen and 0 < ln <= len(lines):
                    ts, sender, text = _parse_line(lines[ln - 1])
                    if ts and text:
                        seen.add(ln)
                        all_candidates.append((ln, ts, text))
        if all_candidates:
            # V2.9.19: 中英文停用词过滤 — 防虚词稀释ratio
            lang = _detect_lang(query)
            if lang == "en" or lang == "mixed":
                EN_STOP = r'\b(first|last|when|time|the|a|an|is|are|was|were|been|being|have|has|had|do|does|did|will|would|can|could|should|may|might|if|then|else|that|this|these|those|it|its|not|but|or|and|for|nor|so|yet|to|of|in|on|at|by|from|with|how|what|where|who|why|her|his|their|our)\b'
                query = re.sub(EN_STOP, '', query, flags=re.IGNORECASE).strip()
            if lang == "zh" or lang == "mixed":
                ZH_STOP = r'(上次|那个|这个|一下|我想|帮我|多少钱|怎么样|怎么办|有没有|是不是|能不能|可不可以|什么是|什么叫|怎么|什么|哪|吗|呢|啊|吧|的|了|是|在|有|我|你|他|她|它|们|这|那|很|都|也|就|还|要|会|能|可以|应该|把|被|让|给|对|从|到|和|与|或|但|而|所以|因为|如果|虽然|但是|然而|不过|只是|而且|并且)'
                query = re.sub(ZH_STOP, '', query).strip()
            tokens = _query_tokens(query)
            ranked = sand_density(all_candidates, tokens, query)
            # V2.9.9.8: sim_bonus已在sand_density处理
            ranked = dynamic_expand(ranked, tokens, limit)
            return ranked[:limit]
        return self.mmapfallback.search(query, limit)
