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
from l3_search_core import simhash as _l3_simhash
from sandglass_vault import _query_tokens


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
    q_fp = _l3_simhash(query)
    if q_fp == -1:
        q_fp = 0
    trust_scores = {}
    try:
        from shadow_sand import shadow_boost
        line_nums = {c[0] for c in candidates if len(c) > 0}
        boosted = shadow_boost(line_nums, limit=len(candidates))
        trust_scores = {ln: score for score, ln in boosted}
    except Exception:
        pass
    scored = []
    for item in candidates:
        ln = item[0]
        text = item[2] if len(item) > 2 else ""
        text_tokens = _query_tokens(text)
        matched = len(query_tokens & text_tokens)
        density = matched / max(len(query_tokens), 1)
        trust = trust_scores.get(ln, 0.5)
        fp = _l3_simhash(text[:500])
        if fp == -1:
            sim_bonus = 0
        else:
            dist = bin(q_fp ^ fp).count('1')
            sim_bonus = min(1.0 / (1 + dist / 64), 0.5)
        final = density * trust + sim_bonus
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
    def search(self, query: str, limit: int = 10) -> list:
        try:
            from shadow_sand import shadow_search
            return shadow_search(query, limit)
        except Exception:
            return []


class Fts5Search:
    def search(self, query: str, limit: int = 10) -> list:
        try:
            from sandglass_sqlite import search as fts5_search, sync_incremental
            sync_incremental()
            return fts5_search(query, limit)
        except Exception:
            return []


class IdxSearch:
    def search(self, query: str, limit: int = 30) -> list:
        try:
            from sandglass_vault import _sync_index, _query_tokens
            idx = _sync_index()
            if not idx:
                try:
                    from sandglass_vault import rebuild_index
                    rebuild_index()
                    idx = _sync_index()
                except: return []
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
    def search(self, query: str, limit: int = 10) -> list:
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
    def __init__(self, shadow=None, fts5=None, idx=None, tfidf=None, mmap=None):
        self.shadow = shadow or ShadowSearch()
        self.fts5 = fts5 or Fts5Search()
        self.idx = idx or IdxSearch()
        self.tfidf = tfidf or TfidfSearch()
        self.mmapfallback = mmap or MmapFallback()

    def search(self, query: str, limit: int = 10) -> list:
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
            tokens = _query_tokens(query)
            ranked = sand_density(all_candidates, tokens, query)
            ranked = simhash_rerank(ranked, query)
            ranked = dynamic_expand(ranked, tokens, limit)
            return ranked[:limit]
        return self.mmapfallback.search(query, limit)
