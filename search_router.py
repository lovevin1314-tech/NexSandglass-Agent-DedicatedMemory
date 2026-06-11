"""
NexSandglass SearchRouter V2.5 — 两层并行架构
===============================================
去加密后 idx 不再需要，FTS5 直接索引中文。
影子沙(信任分) + FTS5(全文) 并行 → 混合排序 → mmap兜底。
"""
import os, mmap
from sandglass_vault import _SANDGLASS, _parse_line


# ═══════════════════ ShadowSearch ═══════════════════
class ShadowSearch:
    """影子沙信任层——<1ms脱口而出。独立可测。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 10) -> list:
        """返回 [(score, line_num)] 信任分列表，不读原文。"""
        try:
            from shadow_sand import shadow_search
            return shadow_search(query, limit)
        except Exception:
            return []


# ═══════════════════ Fts5Search ═══════════════════
class Fts5Search:
    """FTS5全文搜索——内置倒排+BM25精排。独立可测。"""
    def search(self, query: str, limit: int = 10) -> list:
        """返回 [(line_num, ts, text), ...]"""
        try:
            from sandglass_sqlite import search as fts5_search, sync_incremental
            sync_incremental()
            return fts5_search(query, limit)
        except Exception:
            return []


# ═══════════════════ MmapFallback ═══════════════════
class MmapFallback:
    """mmap全量扫描兜底——最后一层保障。"""
    def __init__(self, sandfile=None):
        self.sandfile = sandfile or _SANDGLASS

    def search(self, query: str, limit: int = 10) -> list:
        results = []
        try:
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
                        except: pass

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
    """搜索路由器——三级串联降级。
    影子沙(脱口而出) → FTS5+搜索滤镜 → mmap兜底。"""

    def __init__(self, shadow=None, fts5=None, mmap=None):
        self.shadow = shadow or ShadowSearch()
        self.fts5 = fts5 or Fts5Search()
        self.mmapfallback = mmap or MmapFallback()

    def search(self, query: str, limit: int = 10) -> list:
        # Layer 1: 影子沙 — 脱口而出，命中即返回
        from shadow_sand import shadow_search as _sh_search, shadow_retrieval_bump
        shadow_hits = []
        try:
            shadow_hits = _sh_search(query, limit)
        except: pass

        if shadow_hits:
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

        # Layer 2: FTS5 + 搜索滤镜
        fts5_hits = self.fts5.search(query, max(limit * 3, 30))
        if fts5_hits:
            # L3 搜索滤镜 — 五维权重统一排序
            try:
                from sandglass_think import search_filter
                filt = search_filter(query)
                weights = filt.get("weights", {})
                keywords = filt.get("keywords", [])
                if weights:
                    def _score(item):
                        _, _, text = item
                        return sum(weights.get(kw, 1.0) for kw in keywords if kw.lower() in text.lower())
                    ranked = sorted(fts5_hits, key=_score, reverse=True)
                    return [(r[0], r[1], r[2]) for r in ranked[:limit]]
            except: pass
            return [(r[0], r[1], r[2]) for r in fts5_hits[:limit]]

        # Layer 3: mmap 兜底
        return self.mmapfallback.search(query, limit)
