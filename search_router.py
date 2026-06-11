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
            scan_months = []
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
                            ts, sender, text = parts

                            if scan_months and not any(ts.startswith(m) for m in scan_months):
                                continue

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
    """搜索路由器——两层并行 + 兜底。
    影子沙(信任分) + FTS5(BM25) 并行 → 混合排序 → mmap兜底。"""

    def __init__(self, shadow=None, fts5=None, mmap=None):
        self.shadow = shadow or ShadowSearch()
        self.fts5 = fts5 or Fts5Search()
        self.mmapfallback = mmap or MmapFallback()

    def search(self, query: str, limit: int = 10) -> list:
        # FTS5 全文搜索（主力，BM25精排）
        fts5_hits = self.fts5.search(query, max(limit * 3, 30))
        if not fts5_hits:
            # FTS5没结果 → mmap兜底
            return self.mmapfallback.search(query, limit)

        # 影子沙 → 获取信任分（附加到 FTS5 结果上）
        shadow_scores = {}
        try:
            from shadow_sand import shadow_search, shadow_retrieval_bump
            sh = shadow_search(query, limit * 2)
            if sh:
                shadow_scores = {ln: score for score, ln in sh}
                shadow_retrieval_bump([ln for _, ln in sh[:limit]])
        except: pass

        # 合并：FTS5结果 × 影子沙信任分
        candidates = {}
        for rowid, ts, text in fts5_hits:
            trust = shadow_scores.get(rowid, 0.5)
            candidates[rowid] = (ts, text, trust)

        # L3 搜索滤镜 — 五维权重统一排序
        try:
            from sandglass_think import search_filter
            filt = search_filter(query)
            weights = filt.get("weights", {})
            keywords = filt.get("keywords", [])
            if weights:
                # 五维权重排序：场景×1.5 + 画像×1.3 + 阶段×0.7 + 粒子×1.2 + 偏移×1.3
                def _score(item):
                    ln, (ts, text, trust) = item
                    w = sum(weights.get(kw, 1.0) for kw in keywords if kw.lower() in text.lower())
                    return trust * 0.3 + w * 0.7  # 信任分30% + 搜索滤镜70%
                ranked = sorted(candidates.items(), key=_score, reverse=True)
                results = [(ln, ts, text) for ln, (ts, text, _) in ranked[:limit]]
                return results
        except Exception:
            pass

        # 无搜索滤镜时：信任分排序
        ranked = sorted(candidates.items(), key=lambda x: x[1][2], reverse=True)
        return [(ln, ts, text) for ln, (ts, text, _) in ranked[:limit]]
