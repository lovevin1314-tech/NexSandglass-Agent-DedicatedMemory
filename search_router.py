"""
NexSandglass SearchRouter — Matt Pocock TDD风格
================================================
search()拆为三层独立可测:
  ShadowSearch → IdxFtsSearch → MmapFallback
每层<50行，依赖注入，独立可测
"""
import os, re, mmap
from sandglass_vault import (_SANDGLASS, _IDX, _parse_line, _decrypt,
                              _tokenize, _query_tokens, _sync_index, rebuild_index)

# ═══════════════════ ShadowSearch ═══════════════════
class ShadowSearch:
    """影子沙优先级——<1ms脱口而出层。独立可测。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 10) -> list:
        try:
            from shadow_sand import shadow_search, shadow_retrieval_bump
            hits = shadow_search(query, limit)
            if not hits:
                return []
            results = []
            with open(self.sandfile, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for score, ln in hits:
                        if n == ln:
                            ts, sender, text = _parse_line(line)
                            if ts and text:
                                results.append((ln, ts, text))
                    if len(results) >= limit:
                        break
            if results:
                shadow_retrieval_bump([ln for _, ln in hits[:limit]])
            return results
        except Exception as e:
            return []  # 影子沙失败→降级

# ═══════════════════ IdxFtsSearch ═══════════════════
class IdxFtsSearch:
    """投石问路→FTS5精排。独立可测。"""
    def __init__(self, sandfile=None, idxfile=None, dbfile=None):
        self.sandfile = sandfile or _SANDGLASS
        self.idxfile = idxfile or _IDX

    def search(self, query: str, limit: int = 10) -> list:
        try:
            idx = _sync_index()
            if not idx:
                rebuild_index()
                idx = _sync_index()
            if not idx:
                return []

            candidate_lines = set()
            for token in _query_tokens(query):
                if token in idx:
                    candidate_lines.update(idx[token])
            if not candidate_lines:
                return []

            from sandglass_sqlite import search_in, sync_incremental
            sync_incremental()
            ranked = search_in(list(candidate_lines), query)
            if not ranked:
                return []

            results = []
            with open(self.sandfile, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if n in set(r[0] for r in ranked[:limit]):
                        ts, sender, text = _parse_line(line)
                        if ts and text:
                            results.append((n, ts, text))
                    if len(results) >= limit:
                        break

            # 五维权重排序
            try:
                from sandglass_think import search_filter
                filt = search_filter(query)
                weights = filt.get("weights", {})
                if weights:
                    scored = [(sum(weights.get(w, 1.0) for w in _query_tokens(t) if w in weights), item)
                              for _, _, t in results for item in [(_, _, t)]]
                    results = [item for _, item in sorted(scored, key=lambda x: x[0], reverse=True)]
            except: pass

            return results[:limit]
        except Exception as e:
            return []


# ═══════════════════ MmapFallback ═══════════════════
class MmapFallback:
    """mmap兜底——全量扫描最后手段。独立可测。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 200, month: str = "") -> list:
        results = []
        try:
            stage_filter = False
            scan_months = [month] if month else []
            if not month:
                try:
                    from sandglass_think import _current_stage
                    scan_months = [_current_stage()]
                except: pass

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
                            ts, sender, encrypted = parts

                            # 降级解密
                            try: text = _decrypt(encrypted)
                            except: text = encrypted

                            # 阶段过滤
                            if scan_months and not any(ts.startswith(m) for m in scan_months):
                                continue

                            if query.lower() in text.lower():
                                results.append((ln, ts, text[:300]))
                                if len(results) >= limit: break
                        except: pass

            # 再走 FTS5 精排
            if results:
                from sandglass_sqlite import search_in, sync_incremental
                line_nums = list(range(1, len(results)+1))
                sync_incremental()
                ranked = search_in(line_nums[:500], query)
                if ranked:
                    return [(r[0], r[1], r[2]) for r in ranked[:10]]

            return results[:10]
        except Exception as e:
            return []


# ═══════════════════ SearchRouter ═══════════════════
class SearchRouter:
    """搜索路由器——三层依次降级，每层独立可测。"""
    def __init__(self, shadow=None, idxfts=None, mmap=None):
        self.shadow = shadow or ShadowSearch()
        self.idxfts = idxfts or IdxFtsSearch()
        self.mmapfallback = mmap or MmapFallback()

    def search(self, query: str, limit: int = 10) -> list:
        # Layer 1: 影子沙 (<1ms)
        r = self.shadow.search(query, limit)
        if r: return r

        # Layer 2: 投石问路→FTS5
        r = self.idxfts.search(query, limit)
        if r: return r

        # Layer 3: mmap兜底
        return self.mmapfallback.search(query, limit)
