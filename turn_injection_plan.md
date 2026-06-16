# 轮次对话注入重构方案

> **目标**: 从当前 ~30 tokens 提升到 **150-250 tokens**，与市场标准（Mem0 200-500 tokens）对齐。
> **核心原则**: 不建新提取器，纯管道聚合——所有信号已存在于系统中，只需接入。

---

## 一、现状分析

### 当前注入位置：`memory_provider.py → prefetch()`

```python
# 当前返回 ~30 tokens：
"偏移: 省钱(+15%) | 情绪: 平稳 | 纠结: 轻微(5%) | 搜: 开源, 本地"
```

**问题**:
- 只有 3-4 个管道信号（偏移/情绪/纠结/搜索提示），其余全部闲置
- 没有给 LLM 提供"当前能搜到哪些相关记忆"——LLM 只能凭空调用 `sandglass_search`，完全没有上下文引导
- 铁律、决策粒子、场景、fact_tags 等强大管道完全未进入轮次注入
- 市场对标产品（Mem0 等）每轮注入 200-500 tokens，含记忆摘要 + 搜索建议 + 状态

### 已有管道（全部在 release/ 目录下，已实现）：

| 管道 | 模块 | 函数 | 作用 | 当前注入？ |
|------|------|------|------|-----------|
| **sandglass_search** | search_router.py | SearchRouter.search() | 四路并发搜索(影子沙+FTS5+IDX+TFIDF) | ❌ 未注入 |
| **_infer_expand_with_context** | sandglass_think.py | _infer_expand_with_context() | 四维关键词扩展(画像+场景+阶段+粒子) | ❌ 仅存_hints |
| **pipe_insights** | sandglass_think.py | _synthesize_3d() | 管道洞察(tags趋势+offset拐点+particles+weave) | ❌ 仅system_prompt |
| **offset** | offset_l3.py | comprehensive_offset() | 偏移率(省钱/愿投/放弃) | ✅ 一行 |
| **emotion** | emotion_l3.py | _emotional_entropy() | 香农熵情绪波动 | ✅ 一行 |
| **纠结度** | sandglass_think.py | _synthesize_3d() 内 | 决策链犹豫/回退信号 | ✅ 一行 |
| **fact_tags** | shadow_sand.py | fact_tags表 | 影子沙标签高频统计 | ❌ 仅system_prompt |
| **决策粒子** | decision_particles.py | _detect_chain() | 决策链A→B→C模式 | ❌ 未注入 |
| **场景** | scene_l3.py | scene_current() | 当前场景标签 | ❌ 仅system_prompt |
| **铁律** | discipline.py | iron_rules_with_counts() | 红牌铁律+违反正计数 | ❌ 仅system_prompt |

---

## 二、重构方案：三块式轮次注入

将 `prefetch()` 重构为三层注入结构，每轮给 LLM 发送 **150-250 tokens**：

```
┌──────────────────────────────────────────────┐
│  第一块: 【搜索引导】         ~40-60 tokens   │
│  - 用户查询的关键词扩展                        │
│  - 影子沙命中的标签/实体                       │
│  - 搜索建议（去哪搜、搜什么）                   │
├──────────────────────────────────────────────┤
│  第二块: 【记忆候选】         ~60-100 tokens  │
│  - sandglass_search 预搜结果(TOP 3)           │
│  - 每条: 时间戳 + 前80字符                    │
│  - 带sand密度评分                             │
├──────────────────────────────────────────────┤
│  第三块: 【当前状态+决策】     ~50-90 tokens   │
│  - 偏移率 + 情绪 + 纠结度（一行）              │
│  - 当前场景                                   │
│  - 匹配铁律（若与查询相关）                     │
│  - 决策粒子最近模式                            │
│  - pipe_insights 摘要                         │
└──────────────────────────────────────────────┘
```

---

## 三、具体实现

### 3.1 修改 `memory_provider.py` 的 `prefetch()` 方法

**文件**: `C:\Users\NeuroBase\.neurobase\release\memory_provider.py`
**位置**: 第 454-475 行，替换当前的 `prefetch()` 实现

#### 新 `prefetch()` 伪代码：

```python
def prefetch(self, query: str) -> str:
    """
    每轮对话前注入 — 三块式 150-250 tokens。
    块1: 搜索引导 (关键词扩展 + 影子沙标签)
    块2: 记忆候选 (预搜TOP3 + 密度评分)
    块3: 当前状态 + 决策上下文
    """
    blocks = []
    
    # ═══════════════════════════════════════════════
    # 块1: 搜索引导 (~40-60 tokens)
    # ═══════════════════════════════════════════════
    search_guide = []
    try:
        # 1a. _infer_expand_with_context — 四维关键词扩展
        from sandglass_think import _infer_expand_with_context, search_filter
        sf = search_filter(query)
        ctx = sf or {}
        expanded = _infer_expand_with_context(
            query,
            ctx.get("persona_context", ""),
            ctx.get("scene_context", ""),
            ctx.get("stage_context", ""),
            ctx.get("dp_context", ""),
            ctx.get("decision_bias", "")
        )
        if expanded and len(expanded) > 1:
            search_guide.append(f"搜索: {' / '.join(expanded[1:4])}")
        
        # 1b. 影子沙命中标签 — 脱口而出层直接喂给LLM
        try:
            from shadow_sand import shadow_search
            sh = shadow_search(query, 3)
            if sh:
                import sqlite3, os
                from sandglass_paths import _NB
                db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
                tags_set = set()
                for _, ln in sh[:3]:
                    row = db.execute(
                        "SELECT category, tags FROM fact_tags WHERE line_num=?", (ln,)
                    ).fetchone()
                    if row:
                        if row[0] and row[0] != 'general':
                            tags_set.add(row[0][:15])
                        if row[1]:
                            for t in row[1].split(",")[:2]:
                                t = t.strip()
                                if len(t) > 1:
                                    tags_set.add(t[:15])
                db.close()
                if tags_set:
                    search_guide.append(f"标签: {', '.join(list(tags_set)[:4])}")
        except Exception:
            pass
    except Exception:
        pass
    
    if search_guide:
        blocks.append("🔍 " + " | ".join(search_guide))
    
    # ═══════════════════════════════════════════════
    # 块2: 记忆候选 — 预搜TOP3结果 (~60-100 tokens)
    # ═══════════════════════════════════════════════
    try:
        from search_router import SearchRouter
        router = SearchRouter()
        # 使用扩展关键词预搜
        router_query = " ".join(expanded[:4]) if expanded and len(expanded) > 1 else query
        results = router.search(router_query, limit=3)
        if results:
            memory_lines = ["📋 相关记忆:"]
            for ln, ts, text in results[:3]:
                # 压缩: 时间戳(前7字) + 内容(前80字)
                short_ts = ts[:10] if len(ts) >= 10 else ts
                short_text = text[:80].replace("\n", " ")
                # 计算密度作为可信度指标
                try:
                    from l3_search_core import sand_density, _tokenize_for_density
                    q_tokens = _tokenize_for_density(query)
                    density = sand_density(text, q_tokens)
                    d_flag = "✓" if density > 0.3 else ("·" if density > 0.1 else "?")
                except:
                    d_flag = "·"
                memory_lines.append(f"  {d_flag} [{short_ts}] {short_text}")
            blocks.append("\n".join(memory_lines))
    except Exception:
        pass
    
    # ═══════════════════════════════════════════════
    # 块3: 当前状态 + 决策上下文 (~50-90 tokens)
    # ═══════════════════════════════════════════════
    status_parts = []
    
    # 3a. 偏移 + 情绪 + 纠结度 (一行)
    try:
        from sandglass_think import comprehensive_offset, _emotional_entropy, _synthesize_3d
        off = comprehensive_offset()
        ent = _emotional_entropy()
        mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")
        dirs = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
        off_d = dirs.get(off.get('direction', ''), '平稳')
        
        # 纠结度
        syn = _synthesize_3d(trigger="prefetch")
        pi = syn.get("pipe_insights", "")
        tangle_str = ""
        if "纠结:" in pi:
            tangle_str = pi.split("纠结:")[1].split("|")[0].strip()
        
        status_line = f"状态: {off_d}({off.get('offset',0):+d}%) | 🎭{mood}"
        if tangle_str:
            status_line += f" | 纠结:{tangle_str}"
        status_parts.append(status_line)
    except Exception:
        pass
    
    # 3b. 当前场景
    try:
        from scene_l3 import scene_current
        scenes = scene_current()
        if scenes:
            status_parts.append(f"场景: {'·'.join(scenes[:3])}")
    except Exception:
        pass
    
    # 3c. 匹配铁律 (只注与查询相关的，最多2条)
    try:
        from discipline import iron_rules_with_counts
        rules = iron_rules_with_counts(5)  # 多取几条做筛选
        if rules:
            # 用fact_tags影子沙判定相关性
            matched = []
            import sqlite3, os
            from sandglass_paths import _NB
            db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
            for rule, count in rules:
                # 取铁律关键词做标签匹配
                rule_keywords = [w for w in rule.split() if len(w) >= 2]
                matched_tags = db.execute(
                    "SELECT COUNT(*) FROM fact_tags WHERE " + 
                    " OR ".join(["tags LIKE ?" for _ in rule_keywords]),
                    [f"%{kw}%" for kw in rule_keywords[:3]]
                ).fetchone()
                if matched_tags and matched_tags[0] > 0:
                    matched.append(f"⚠{rule[:40]}")
                    if len(matched) >= 2:
                        break
            db.close()
            if matched:
                status_parts.append(" | ".join(matched))
    except Exception:
        pass
    
    # 3d. 决策粒子最近模式
    try:
        dp_path = os.path.join(os.environ.get("NEXSANDBASE_HOME", 
            os.path.join(os.path.expanduser("~"), ".neurobase")), "decision_particles.txt")
        if os.path.exists(dp_path):
            with open(dp_path, "r", encoding="utf-8", errors="replace") as f:
                dps = [l for l in f if l.strip() and not l.startswith("#")]
            if dps:
                last = dps[-1]
                if "→" in last:
                    parts = last.split(" | ")
                    if len(parts) >= 4:
                        # 格式: ts | query | chain | direction
                        chain = parts[2][:40].strip()
                        direction = parts[3].strip()[:10]
                        status_parts.append(f"决策: {chain} ({direction})")
    except Exception:
        pass
    
    # 3e. pipe_insights 摘要 (标签趋势+告警)
    try:
        if pi and "|" in pi:
            # 提取关键片段，去重
            snippets = [s.strip() for s in pi.split("|") if s.strip()]
            # 只保留有价值的部分，去掉和上面重复的
            key_snippets = []
            for s in snippets:
                if any(k in s for k in ["告警", "标签:", "链:"]):
                    key_snippets.append(s[:40])
            if key_snippets:
                status_parts.append(" | ".join(key_snippets[:2]))
    except Exception:
        pass
    
    blocks.append("\n".join(status_parts))
    
    result = "\n".join(blocks)
    # 硬截断: 确保不超过 250 tokens (约600字符)
    if len(result) > 600:
        result = result[:597] + "..."
    return result
```

---

## 四、输出格式示例

### 示例1：日常开发场景 (约180 tokens)

```
🔍 搜索: 开源 / 本地 / 免费 | 标签: NeuroBase, sandglass, 记忆

📋 相关记忆:
  ✓ [2026-06-15] 主人说NeuroBase要全本地运行，不能依赖任何外部API
  ✓ [2026-06-14] 重构了sandglass_vault的索引层，SearchRouter四路并发
  · [2026-06-13] 讨论过mem0的轮次注入模式，200-500 tokens每轮

状态: 省钱(+22%) | 🎭平稳 | 场景:开发·重构
⚠必须全本地运行 ⚠改动前先跑测试
决策: 开源→本地→自建 (省钱)
标签: sandglass(12)·NeuroBase(8) | 告警: 画像滞后147条
```

### 示例2：决策纠结场景 (约220 tokens)

```
🔍 搜索: 付费工具 / 免费替代 / 对比 | 标签: 纠结, 预算, 诊所

📋 相关记忆:
  ✓ [2026-06-10] 主人问过Claude Code vs Codex的价格对比，最终选了Claude
  ✓ [2026-06-08] 诊所管理系统在对比牙医管家和轻松牙医
  · [2026-05-30] 主人说过"能本地就不订阅"

状态: 省钱(+8%) | 🎭波动 | 纠结:35%犹豫(7/20)
场景: 工具选型·成本控制
决策: 对比→纠结→回退→对比 (波动)
链: 付费→免费→本地
```

### 示例3：少量记忆冷启动 (约160 tokens)

```
🔍 搜索: 用户画像 / 偏好

📋 相关记忆:
  · [2026-06-16] 主人是诊所老板，技术栈Python+本地优先

状态: 平稳(0%) | 🎭平稳 | 场景: 通用
```

---

## 五、管道聚合对照表

| 管道 | 输出位置 | tokens估算 | 触发条件 |
|------|---------|-----------|---------|
| **sandglass_search** (预搜) | 块2: 记忆候选 | 60-100 | 每轮 |
| **_infer_expand_with_context** | 块1: 搜索引导 | 15-30 | 每轮 |
| **影子沙标签 (fact_tags)** | 块1: 搜索引导 | 15-20 | 有命中 |
| **offset 偏移率** | 块3: 状态行 | 10-15 | 每轮 |
| **emotion 情绪熵** | 块3: 状态行 | 5-10 | 每轮 |
| **纠结度** | 块3: 状态行 | 5-15 | 有犹豫信号 |
| **场景 (scene)** | 块3: 场景行 | 10-20 | 有场景 |
| **铁律 (discipline)** | 块3: 匹配行 | 10-25 | 与查询相关 |
| **决策粒子** | 块3: 决策模式 | 10-20 | 有决策历史 |
| **pipe_insights** | 块3: 摘要行 | 10-20 | 有管道数据 |

**总计**: 150-250 tokens（典型值 ~200 tokens）

---

## 六、与 `system_prompt_block()` 的分工

| 维度 | `system_prompt_block()` (会话启动) | `prefetch()` (每轮注入) |
|------|-----------------------------------|------------------------|
| 频率 | 会话开始时 1 次 | 每轮对话前 |
| tokens | 400-800 (不压缩) | 150-250 (压缩) |
| 身份画像 | ✅ 你是谁 | ❌ (已存入上下文) |
| 搜索引导 | ❌ | ✅ 关键词 + 标签 |
| 记忆候选 | ❌ | ✅ 预搜 TOP3 |
| 偏移/情绪/纠结 | ✅ (含在管道洞察) | ✅ (实时动态) |
| 场景 | ✅ | ✅ (可能随轮次变化) |
| 铁律 | ✅ 全部 TOP3 | ✅ 仅匹配查询的 |
| 决策上下文 | ❌ | ✅ 最近决策模式 |
| 织线因果 | ✅ | ❌ (保持不变) |
| 待办任务 | ✅ | ❌ (保持不变) |

---

## 七、实施步骤

### Step 1: 修改 `memory_provider.py` 的 `prefetch()`
- 替换当前 20 行实现为三块式注入 (~120 行)
- 所有调用均为已有模块，零新依赖

### Step 2: 添加 `_prefetch_memory_candidates()` 辅助方法
- 从 `prefetch()` 中提取块2逻辑
- 可被 `queue_prefetch()` 复用

### Step 3: 添加 token 预算控制
- 三块分别有 target tokens
- 块2 (记忆候选) 可动态扩缩: 记忆多→3条, 记忆少→1条
- 硬截断 600 字符 (~250 tokens)

### Step 4: 测试验证
- 验证 `prefetch(query)` 返回的字符串长度在 150-600 字符之间
- 验证所有管道均可正常调用
- 验证冷启动（无记忆时）优雅降级不报错

---

## 八、关键设计决策

1. **块2预搜结果由 SearchRouter 统一入口**: 不经 `sandglass_search` 工具（那是LLM调用的），而是直接调用 `SearchRouter.search()` 走四路并发
2. **铁律只在匹配时注入**: 不刷全量铁律（那是system_prompt的活），只注与查询标签相关的
3. **决策粒子压缩为箭头模式**: `A→B→C` 比完整决策文本节省 80% tokens
4. **所有信号来自已有管道**: `_infer_expand_with_context`、`_synthesize_3d`、`comprehensive_offset`、`_emotional_entropy`、`iron_rules_with_counts`、`scene_current` —— 全部已实现，只做接入
5. **冷启动优雅降级**: 每个 try/except 独立，任一管道失败不影响其他
