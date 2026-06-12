"""
NexSandglass SearchRouter V2.8 — 四路并发搜索架构
===================================================
影子沙 + FTS5 + IDX + TF-IDF 四路并发 → 米粒密度融合 → SimHash重排 → mmap兜底
"""
import os, mmap, re, threading, concurrent.futures, math
from sandglass_vault import _SANDGLASS, _parse_line


# ═══════════════════ 语言检测 ═══════════════════
def _detect_lang(text: str) -> str:
    """检测查询语言：zh / en / mixed。"""
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    eng = sum(1 for c in text if c.isascii() and c.isalpha())
    if cjk and eng: return "mixed"
    return "zh" if cjk >= eng else "en"


# ═══════════════════ SimHash ═══════════════════
def _simhash(text: str) -> int:
    """32位SimHash指纹——零依赖纯Python。"""
    v = [0] * 32
    for ch in text:
        h = ord(ch) + (hash(ch) & 0xFFFFFFFF)
        for i in range(32):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    return sum((1 << i) for i in range(32) if v[i] > 0)


def _simhash_density_decay(score: float, rank: int) -> float:
    """密度衰减：排名越靠后衰减越大。"""
    return score * (0.85 ** rank)


def simhash_rerank(candidates, query) -> list:
    """SimHash汉明距离重排。"""
    q_fp = _simhash(query)
    def hamming(item):
        fp = _simhash(item[2] if len(item) > 2 else "")
        return bin(fp ^ q_fp).count('1')
    return sorted(candidates, key=hamming)


# ═══════════════════ 米粒密度 ═══════════════════
def grain_density(candidates, tokens, query) -> list:
    """米粒密度排序 — token重叠率驱动。
    density = matched_tokens / total_tokens × simhash_score
    """
    q_fp = _simhash(query)
    scored = []
    for item in candidates:
        text = item[2] if len(item) > 2 else ""
        matched = sum(1 for t in tokens if t.lower() in text.lower())
        density = matched / max(len(tokens), 1)
        sim_score = 1.0 / (1 + bin(q_fp ^ _simhash(text)).count('1') / 32)
        scored.append((density * 0.6 + sim_score * 0.4, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


def dynamic_expand(candidates, tokens, limit: int) -> list:
    """动态上下文扩展：密度衰减扩容。
    当前候选不足时，降低密度阈值扩窗重选。
    """
    if len(candidates) >= limit:
        return candidates[:limit]
    # 密度衰减扩窗 — 放宽到只匹配任一token
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


# ═══════════════════ ShadowSearch ═══════════════════
class ShadowSearch:
    """影子沙信任层——<1ms脱口而出。独立可测。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 10) -> list:
        try:
            from shadow_sand import shadow_search
            return shadow_search(query, limit)
        except Exception:
            return []


# ═══════════════════ Fts5Search ═══════════════════
class Fts5Search:
    """FTS5全文搜索——内置倒排+BM25精排。独立可测。"""
    def search(self, query: str, limit: int = 10) -> list:
        try:
            from sandglass_sqlite import search as fts5_search, sync_incremental
            sync_incremental()
            return fts5_search(query, limit)
        except Exception:
            return []


# ═══════════════════ IdxSearch ═══════════════════
class IdxSearch:
    """IDX倒排索引搜索—中文子串+英文模糊。独立可测。"""
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
            if not idx:
                return []

            tokens = _query_tokens(query)
            candidates = {}
            for token in tokens:
                if token in idx:
                    for ln in idx[token]:
                        candidates[ln] = candidates.get(ln, 0) + 1

            if not candidates:
                return []

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


# ═══════════════════ TfidfSearch ═══════════════════
class TfidfSearch:
    """TF-IDF语义引擎——零依赖纯Python。独立可测。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 30) -> list:
        try:
            from sandglass_vault import _query_tokens
            tokens = _query_tokens(query)
            if not tokens:
                return []

            # 全量读沙子文本
            all_lines = []
            with open(self.sandfile, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if " | " in line:
                        parts = line.split(" | ", 2)
                        if len(parts) >= 3:
                            ts, sender, text = _parse_line(line)
                            if ts and text:
                                all_lines.append((n, ts, text))

            if not all_lines:
                return []

            # TF-IDF计算
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


# ═══════════════════ MmapFallback ═══════════════════
class MmapFallback:
    """mmap全量扫描兜底——最后一层保障。"""
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


# ═══════════════════ SearchRouter ═══════════════════
class SearchRouter:
    """搜索路由器——四路并发 + 米粒密度融合 + SimHash重排 + mmap兜底。"""

    def __init__(self, shadow=None, fts5=None, idx=None, tfidf=None, mmap=None):
        self.shadow = shadow or ShadowSearch()
        self.fts5 = fts5 or Fts5Search()
        self.idx = idx or IdxSearch()
        self.tfidf = tfidf or TfidfSearch()
        self.mmapfallback = mmap or MmapFallback()

    def search(self, query: str, limit: int = 10) -> list:
        # 四路并发搜索
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            fut_shadow = ex.submit(self.shadow.search, query, limit)
            fut_fts5 = ex.submit(self.fts5.search, query, max(limit * 2, 30))
            fut_idx = ex.submit(self.idx.search, query, max(limit * 2, 30))
            fut_tfidf = ex.submit(self.tfidf.search, query, max(limit * 2, 30))

        shadow_hits = fut_shadow.result() or []
        fts5_hits = fut_fts5.result() or []
        idx_hits = fut_idx.result() or []
        tfidf_hits = fut_tfidf.result() or []

        # 影子沙命中即返回（脱口而出）
        if shadow_hits:
            from shadow_sand import shadow_retrieval_bump
            results = []
            try:
                with open(_SANDGLASS, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for score, ln in shadow_hits[:limit]:
                    if 0 < ln <= len(lines):
                        ts, sender, text = _parse_line(lines[ln - 1])
                        if ts and text:
                            results.append((ln, ts, text))
                if results:
                    shadow_retrieval_bump([ln for _, ln in shadow_hits[:limit]])
                    return results
            except: pass

        # 多路融合：FTS5 + IDX + TF-IDF + 影子沙
        all_candidates = []
        seen = set()
        for hits in [fts5_hits, idx_hits, tfidf_hits]:
            for item in hits:
                ln = item[0]
                if ln not in seen:
                    seen.add(ln)
                    all_candidates.append(item)

        # 影子沙结果也融入
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
            # 米粒密度排序
            from sandglass_vault import _query_tokens
            tokens = _query_tokens(query)
            ranked = grain_density(all_candidates, tokens, query)

            # SimHash语义重排
            ranked = simhash_rerank(ranked, query)

            # 动态上下文扩展
            ranked = dynamic_expand(ranked, tokens, limit)

            return ranked[:limit]

        # mmap兜底
        return self.mmapfallback.search(query, limit)
