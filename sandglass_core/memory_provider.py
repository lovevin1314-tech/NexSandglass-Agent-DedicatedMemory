"""
NexSandglass MemoryProvider — MemoryProvider for Hermes
========================================================
让 Hermes 使用 NexSandglass 作为记忆后端，替代 Holographic。

零API Key、零外部依赖——纯本地驱动。投石问路（倒排索引）优先、
五维权重排序、偏移率感知、回音折情绪追踪、影子灵魂预测。
"""
from __future__ import annotations

import json, logging, os, re, sqlite3, threading, time
from typing import Any, Dict, List, Optional
from sandglass_paths import _NB

# 纯本地MemoryProvider——不导入Hermes核心模块避免死锁
# Hermes通过register()函数发现插件,不检查继承关系
class MemoryProvider:
    name = "nexsandglass"
    def is_available(self): return True
    def initialize(self): pass
    def shutdown(self): pass
    def get_tool_schemas(self): return []
    def handle_tool_call(self, name, args): return ""
    def system_prompt_block(self): return ""
    def prefetch(self, query): return None
    def sync_turn(self, user_msg, assistant_msg): pass

def tool_error(msg): return json.dumps({"error": msg})

logger = logging.getLogger(__name__)
# ══════════════════════════════════════════════════════════
# 管道健康追踪器 — 失败重试+降级报告+自动复活
# ══════════════════════════════════════════════════════════
import time as _time, traceback as _traceback
from collections import defaultdict as _defaultdict

class PipelineHealth:
    """管道健康状态机：OK → 瞬态重试 → 降级 → 定期复活"""
    
    def __init__(self):
        self._state = {}  # name → {failures, last_error, suppressed_until}
        self._lock = threading.Lock()
        self.TRANSIENT_PATTERNS = [
            "database is locked", "database locked",
            "threading", "Lock", "timeout",
            "disk I/O error", "Permission denied"
        ]
        self.MAX_RETRIES = 3
        self.SUPPRESS_AFTER = 5
        self.RESURRECT_INTERVAL = 300  # 降级后5分钟尝试复活
    
    def _is_transient(self, error: Exception) -> bool:
        msg = str(error).lower()
        return any(p.lower() in msg for p in self.TRANSIENT_PATTERNS)
    
    def execute(self, name: str, fn):
        """执行管道，瞬态错误自动重试，持久错误降级+定期复活。
        返回 (result, degraded_note)"""
        with self._lock:
            s = self._state.get(name, {})
            if s.get("suppressed_until", 0) > _time.time():
                return None, f"[{name} 降级中]"
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                result = fn()
                with self._lock:
                    self._state[name] = {"failures": 0, "last_ok": _time.time()}
                return result, None
            except Exception as e:
                last_error = e
                if not self._is_transient(e): break
                if attempt < self.MAX_RETRIES - 1: _time.sleep(0.3 * (attempt + 1))
        
        with self._lock:
            s = self._state.get(name, {"failures": 0})
            s["failures"] = s.get("failures", 0) + 1
            s["last_error"] = str(last_error)[:120]
            if s["failures"] >= self.SUPPRESS_AFTER:
                s["suppressed_until"] = _time.time() + self.RESURRECT_INTERVAL
                logger.warning(f"管道 [{name}] 连续失败{s['failures']}次，降级{self.RESURRECT_INTERVAL}s: {s['last_error']}")
            else:
                logger.warning(f"管道 [{name}] 第{s['failures']}次失败: {s['last_error']}")
            self._state[name] = s
        
        return None, f"[{name} 不可用: {str(last_error)[:60]}]"
    
    def degraded_summary(self) -> str:
        """LLM可见的降级报告"""
        with self._lock:
            degraded = []
            for name, s in self._state.items():
                if s.get("failures", 0) > 0:
                    status = "降级" if s.get("suppressed_until", 0) > _time.time() else "异常"
                    degraded.append(f"  {status} [{name}]: {s.get('last_error', '?')[:50]}")
            if degraded:
                return "⚠️ 部分记忆管道异常:\n" + "\n".join(degraded)
            return ""

_pipeline_health = PipelineHealth()


# ══════════════════════════════════════════════════════════
# 工具方法——把 sandglass 函数暴露给 Hermes 模型调用
# ══════════════════════════════════════════════════════════

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "sandglass_search",
            "description": "搜索沙漏记忆——投石问路（倒排索引）优先，五维权重排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_semantic",
            "description": "精炼语义搜索——六维滤镜+影子沙+同义词+情感重排。概念查询更准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_migrate",
            "description": "一键导出全部记忆数据为 tar.gz。换电脑时解压即用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "output": {"type": "string", "description": "输出路径", "default": ""},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_export",
            "description": "导出沙漏为可迁移文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "输出路径"},
                    "limit": {"type": "integer", "description": "导出条数"},
                    "month": {"type": "string", "description": "指定月份 YYYY-MM"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_recent",
            "description": "获取最近 N 条记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_offset",
            "description": "计算当前偏移率——主人决策方向的趋势。返回偏移百分比和方向。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fact_store",
            "description": "影子沙事实存储。action=add/search/probe/reason。存储结构化事实，信任评分排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "search", "probe", "reason"]},
                    "content": {"type": "string", "description": "事实内容"},
                    "category": {"type": "string", "default": "general"},
                    "query": {"type": "string"},
                    "entity": {"type": "string"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fact_feedback",
            "description": "信任评分反馈。标记记忆是否有帮助。",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_num": {"type": "integer"},
                    "helpful": {"type": "boolean"},
                },
                "required": ["line_num", "helpful"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_echo",
            "description": "读取回音折——最近的情感风向。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _pipe_warn(name, e):
    """管道降级——PipelineHealth追踪+LLM可见"""
    logger.warning(f"管道 [{name}] 降级: {e}")
    # 记录到PipelineHealth——用于自动复活和LLM降级报告
    _pipeline_health.execute(name, lambda: (_ for _ in ()).throw(e))

class NexSandglassProvider(MemoryProvider):
    """NexSandglass 记忆提供器——替代 Holographic，纯本地零依赖。"""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._lock = threading.Lock()
        self._initialized = False
        self._turn_count = 0

    # ═══════ MemoryProvider 核心接口 ═══════

    @property
    def name(self) -> str:
        return "nexsandglass"

    def is_available(self) -> bool:
        """始终可用——零API Key，纯本地。"""
        return True

    def initialize(self, session_id: str = "", **kwargs) -> None:
        """设置沙漏路径、重建投石问路索引。"""
        with self._lock:
            if self._initialized:
                return
            # V2.10.47: 自举——自动配置 Hermes memory provider（新用户零手动）
            self._bootstrap_hermes_config()
            # 确保 sandglass 模块可导入
            import sys
            nb = os.environ.get("NEXSANDBASE_HOME") or os.path.expanduser("~/.neurobase")
            nb_scripts = os.path.join(nb, "scripts")
            if nb_scripts not in sys.path:
                sys.path.insert(0, nb_scripts)

            from sandglass_vault import rebuild_index
            from sandglass_paths import validate, __version__
            validate()
            # V2.9.37: 索引重建仅首次运行
            idx_done = os.path.join(nb, "idx_done")
            if not os.path.exists(idx_done):
                rebuild_index()
                with open(idx_done, "w") as f: f.write("1")
            # V2.10.22: 自愈Timer——initialize()时启动，不在模块导入时跑
            try:
                from sandglass_vault import init_autoheal
                init_autoheal()
            except Exception as e:

                _pipe_warn("pipe", e)            # V2.10.14: 沙漏自愈——仅在initialize()时跑，不在模块导入时跑
            try:
                from sandglass_vault import _startup_autoheal
                _startup_autoheal()
            except Exception as e:

                _pipe_warn("pipe", e)            # V2.9.39: DB自省增量——用trust表MAX(line_num)替代外部checkpoint
            try:
                sand_path = os.path.join(nb, "sandglass.txt")
                if os.path.exists(sand_path):
                    current_lines = sum(1 for _ in open(sand_path, encoding="utf-8", errors="replace"))
                    db = sqlite3.connect(os.path.join(nb, "shadow_sand.db"), check_same_thread=False)
                    max_trust = db.execute("SELECT COALESCE(MAX(line_num), 0) FROM trust").fetchone()[0]
                    db.close()
                    if current_lines > max_trust:
                        from shadow_sand import shadow_index
                        with open(sand_path, encoding="utf-8", errors="replace") as f:
                            for ln, line in enumerate(f, 1):
                                if ln <= max_trust: continue
                                text = line.strip()
                                if text: shadow_index(text, line_num=ln)
            except Exception as e:
                logger.warning(f"增量初始化跳过: {e}")
            self._initialized = True
            logger.info(f"NexSandglass V{__version__} 就绪")
    def _bootstrap_hermes_config(self) -> None:
        """V2.10.47: 首次初始化时自动配置 Hermes——零手动。
        
        检测 config.yaml 中 memory 段：
        - provider 非 "nexsandglass" → 自动设为 "nexsandglass"
        - memory_enabled 非 false → 自动设为 false（不设 char_limit，避免反弹）
        
        幂等：_bootstrapped flag 文件写入一次后跳过检查。
        """
        try:
            import yaml as _yaml
        except ImportError:
            # 无 YAML 库 → 静默跳过（极少情况）
            return
        
        try:
            # 检查是否已自举过
            nb = os.environ.get("NEXSANDBASE_HOME") or os.path.expanduser("~/.neurobase")
            boot_flag = os.path.join(nb, "_bootstrapped")
            if os.path.exists(boot_flag):
                return
            
            # 找 Hermes config.yaml
            hermes_home = os.environ.get("HERMES_HOME") or os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")),
                "hermes"
            )
            config_path = os.path.join(hermes_home, "config.yaml")
            if not os.path.exists(config_path):
                # 尝试备选路径
                alt = os.path.expanduser("~/.hermes/config.yaml")
                if os.path.exists(alt):
                    config_path = alt
                else:
                    return  # 找不到 config，不阻塞
            
            # 读配置
            with open(config_path, "r", encoding="utf-8") as f:
                config = _yaml.safe_load(f) or {}
            
            changed = False
            
            # memory 段
            if "memory" not in config:
                config["memory"] = {}
            mem = config["memory"]
            
            # provider → "nexsandglass"
            if mem.get("provider") != "nexsandglass":
                mem["provider"] = "nexsandglass"
                changed = True
            
            # memory_enabled → false（关键：不设 char_limit=1，避免反弹）
            if mem.get("memory_enabled") is not False:
                mem["memory_enabled"] = False
                changed = True
            
            # 写入
            if changed:
                with open(config_path, "w", encoding="utf-8") as f:
                    _yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                logger.info(f"NexSandglass 自举完成：config.yaml memory 段已自动配置")
            
            # 写 flag（无论是否 changed——避免每次初始化都读 YAML）
            os.makedirs(os.path.dirname(boot_flag), exist_ok=True)
            with open(boot_flag, "w") as f:
                f.write(f"NexSandglass V{__version__} bootstrapped at {os.path.join(hermes_home, 'config.yaml')}\n")
        
        except Exception as e:
            # 绝不因自举失败阻塞初始化
            logger.warning(f"NexSandglass 自举跳过: {e}")

    def _safe_pipe(self, name, fn):
        """管道健康包装——失败时LLM可见降级"""
        result, note = _pipeline_health.execute(name, fn)
        if note:
            if not hasattr(self, '_degraded_notes'):
                self._degraded_notes = []
            self._degraded_notes.append(note)
        return result
    
    def _degraded_report(self):
        """收集本轮所有降级，注入LLM可见"""
        report = _pipeline_health.degraded_summary()
        if hasattr(self, '_degraded_notes') and self._degraded_notes:
            report += "\n" + "\n".join(self._degraded_notes)
            self._degraded_notes = []
        return report
    
    def system_prompt_block(self) -> str:
        """V2.9.8: 四层问答式注入 — 你是谁→往哪走→怎么变成这样→还没做完"""
        try:
            from sandglass_vault import count
            from sandglass_think import comprehensive_offset, _current_stage
            from sandglass_think import _emotional_entropy, search_filter

            total = count()
            off = comprehensive_offset()
            stage = _current_stage()
            ent = _emotional_entropy()
            mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")

            # 偏移方向
            dirs = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
            off_label = dirs.get(off.get('direction', ''), '平稳')
            off_pct = off.get('offset', 0)

            blocks = []

            # ═══════ 第一层：你是谁 V2.9.9.10 数据点 ═══════
            identity_parts = []
            
            # 身份：从画像快照提取
            try:
                from persona_l3 import _local_persona_extract
                local = _local_persona_extract()
                if local and local != "数据不足":
                    for line in local.split("\n"):
                        if "：" in line or ":" in line:
                            identity_parts.append(line.strip()[:60])
            except Exception as e:
                _pipe_warn("five_facets", e)
            
            # 铁律：从 five-facets.json 注入结构化事实（importance×confidence 排序）
            try:
                facets_path = os.path.join(_NB, "profile", "five-facets.json")
                if os.path.exists(facets_path):
                    with open(facets_path, "r", encoding="utf-8") as f:
                        facets = json.load(f)
                    # V2.10.54: fact全量注入——同分挑选导致核心身份随机丢失
                    for ftype, count in [("fact", 99), ("preference", 1), ("restriction", 2)]:
                        scored = []
                        for entry in facets.get(ftype, []):
                            imp = entry.get("importance", 0)
                            conf = entry.get("confidence", 0)
                            scored.append((imp * conf, entry["content"]))
                        scored.sort(reverse=True)
                        for _, content in scored[:count]:
                            title = content.split("：")[0].split(":")[0].split("=")[0].strip()[:30]
                            if not title:
                                title = content[:30]
                            if title and title not in identity_parts:
                                identity_parts.append(title)
            except Exception as e:
                _pipe_warn("persona_extract", e)
            
            # 决策：管道洞察已含偏移方向，此处不重复
            
            # 关注：从fact_tags高频标签
            try:
                from collections import Counter
                db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"), check_same_thread=False)
                tags = Counter()
                for r in db.execute("SELECT tags FROM fact_tags WHERE tags != '' AND tags != '未分类'").fetchall():
                    for t in r[0].split(","):
                        t = t.strip()
                        if t and len(t) > 1: tags[t] += 1
                db.close()
                top = [t for t,_ in tags.most_common(3) if _ >= 2]
                if top: identity_parts.append(f"关注: {', '.join(top)}")
            except Exception as e:

                _pipe_warn("pipe", e)
            # V2.10.52: 实体注入——影子沙entities表接system_prompt
            try:
                db2 = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"), check_same_thread=False)
                ent_rows = db2.execute("""
                    SELECT name, line_nums FROM entities 
                    WHERE length(name) >= 2 
                    ORDER BY length(line_nums) - length(replace(line_nums,',','')) DESC 
                    LIMIT 5
                """).fetchall()
                db2.close()
                if ent_rows:
                    ents = [e[0] for e in ent_rows if len(e[0]) >= 2 and not e[0].startswith(('什么','怎么','这个','那个')) and ' ' not in e[0] and len(e[0]) <= 8]
                    if ents:
                        identity_parts.append(f"实体: {', '.join(ents[:5])}")
            except Exception:
                pass
            # 场景
            scene_text = ""
            try:
                from scene_l3 import scene_current
                scenes = scene_current()
                if scenes: scene_text = ", ".join(scenes[:3])
            except Exception as e:

                _pipe_warn("pipe", e)            
            if not identity_parts:
                identity_parts.append("身份: 待积累（使用中自动发现）")
            
            blocks.append(f"【你是谁】\n{' | '.join(identity_parts)}")
            if scene_text:
                blocks.append(f"📍 {scene_text}")

            # V2.9.9.7: 溯源异常告警
            try:
                from l3_persona_verify import persona_verify
                pv = persona_verify()
                if pv.get("failed", 0) > 0:
                    blocks.append(f"⚠️ 画像溯源异常：{pv['failed']}条声明源行已变更")
            except Exception:
                pass

            # ═══════ 第二层：你在往哪走（极简） ═══════
            layer2 = []
            # 情绪状态
            if mood != "平稳":
                layer2.append(f"【状态】🎭 {mood}")
            # 最近决策（管道洞察已含，此处只补情绪）
            decisions = []
            try:
                dlog = os.path.join(_NB, "persona", "decision-log.jsonl")
                if os.path.exists(dlog):
                    with open(dlog, "r", encoding="utf-8") as f:
                        all_lines = f.readlines()
                    recent = [json.loads(l) for l in all_lines[-10:]]
                    recent = [d for d in recent if d.get("decision")]
                    seen_d, unique_d = set(), []
                    for d in reversed(recent):
                        if d["decision"] not in seen_d:
                            seen_d.add(d["decision"])
                            unique_d.append(d)
                        if len(unique_d) >= 2:
                            break
                    unique_d.reverse()
                    decisions = [d['decision'][:60] for d in unique_d]
                    # 子串去重：短的被长的包含→去掉短的
                    if len(decisions) == 2 and decisions[0] in decisions[1]:
                        decisions = [decisions[1]]
                    elif len(decisions) == 2 and decisions[1] in decisions[0]:
                        decisions = [decisions[0]]
            except Exception:
                pass
            if decisions:
                layer2.append(f"📋 最近：{'；'.join(decisions)}")

            # V2.9.9.7: 情绪×偏移预判+语气合并行
            try:
                from offset_l3 import psychology_hint
                hint = psychology_hint()
                emo = ""
                if mood != "平稳":
                    tone = ""
                    if ent > 1.0: tone = " — 安静陪着"
                    elif ent < 0.3: tone = " — 状态稳"
                    emo = f" 🎭 {mood}{tone}"
                elif ent < 0.3:
                    emo = " 🎭 平稳 — 状态稳"
                if hint or emo:
                    line = (hint or "") + emo
                    if line.strip():
                        layer2.append(line.strip())
            except Exception:
                pass

            # 矛盾检测
            try:
                from weave_l3 import weave_contradiction
                contra = weave_contradiction()
                if contra.get("conflicts"):
                    c0 = contra["conflicts"][0]
                    if c0.get("conflict"):
                        layer2.append(f"⚠️ {c0['conflict'][:100]}")
            except Exception:
                logger.debug("矛盾检测失败", exc_info=True)


            blocks.append("\n".join(layer2))

            # ═══════ V2.10.51: 最近对话——10轮用户消息注入 ═══════
            try:
                import sqlite3 as _sq
                state_db = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")), "hermes", "state.db")
                if os.path.exists(state_db):
                    _db = _sq.connect(state_db)
                    _rows = _db.execute("""
                        SELECT content FROM messages 
                        WHERE role='user' AND content NOT LIKE '{%' AND content NOT LIKE '[{%' AND length(content) > 2
                        ORDER BY id DESC LIMIT 10
                    """).fetchall()
                    _db.close()
                    if _rows:
                        _lines = [r[0][:80].replace('\n',' ').strip() for r in reversed(_rows)]
                        # 去重相邻重复
                        _dedup = []
                        for l in _lines:
                            if not _dedup or l != _dedup[-1]:
                                _dedup.append(l)
                        blocks.append("【最近对话】\n" + "\n".join(f"  {l}" for l in _dedup))
            except Exception:
                pass

            # ═══════ 第三层：你怎么变成这样 ═══════
            try:
                from weavethread import wthread_stats, wthread_weave
                stats = wthread_stats()
                if stats["total_triples"] >= 20:
                    thread = wthread_weave(limit=3)
                    if thread and thread != "织线因果:":
                        blocks.append(f"【你怎么变成这样】\n{thread[:200]}")
            except Exception:
                logger.debug("织线失败", exc_info=True)

            # ═══════ 第四层：还没做完 ═══════
            layer4 = []

            # 待办
            tasks = []
            try:
                from l3_tasks import task_pending
                tp = task_pending()
                if tp:
                    tasks = [t['task'][:80] for t in tp[:3]]
            except Exception:
                pass

            # 铁律
            rules = []
            try:
                from discipline import iron_rules_with_counts, iron_rule_inject_bump
                raw_rules = iron_rules_with_counts(3)
                if raw_rules:
                    if any(c > 0 for _, c in raw_rules):
                        rules = [f"{r} ×{c}" for r, c in raw_rules]
                    else:
                        rules = [r for r, _ in raw_rules]
                    # V2.9.9: 会话级去重bump — 每条规则每session+1
                    for r, _ in raw_rules:
                        iron_rule_inject_bump(r)
            except Exception:
                pass

            if tasks or rules:
                header = "【还没做完】"
                if tasks:
                    layer4.append(header)
                    layer4.append("待办：")
                    layer4.extend(f"  {i+1}. {t}" for i, t in enumerate(tasks))
                if rules:
                    if not tasks:
                        layer4.append(header)
                    layer4.append("铁律：")
                    layer4.extend(f"  {i+1}. {r}" for i, r in enumerate(rules))
                blocks.append("\n".join(layer4))

            # ═══════ 管道洞察（V2.9.11） ═══════
            try:
                from sandglass_think import _synthesize_3d
                syn = _synthesize_3d(trigger="inject")
                if syn and syn.get("pipe_insights"):
                    blocks.append(f"🔍 {syn['pipe_insights']}")
            except Exception as e:

                _pipe_warn("pipe", e)
            # ═══════ 尾部 ═══════
            # V2.10.19: 管道降级报告——LLM可见
            degraded = self._degraded_report()
            if degraded:
                blocks.insert(0, degraded)
            
            blocks.append(f"沙漏: {total}条 | 阶段: {stage}")

            result = "\n\n".join(blocks).strip()
            if not result:
                logger.debug("system_prompt_block: 无可注入数据")
            return result
        except Exception:
            logger.warning("system_prompt_block 整体失败", exc_info=True)
            return "NexSandglass记忆系统已就绪。使用sandglass_search搜索记忆。"

    def prefetch(self, query: str) -> str:
        """V2.10.55: 极简轮次注入 — 搜索引导+记忆预览。去重system_prompt_block已覆盖内容。"""
        try:
            blocks = []
            hints = getattr(self, '_prefetch_hints', [])
            
            # ═══ 块1: 搜索引导 ═══
            guide = []
            if hints:
                guide.append(f"搜索: {' / '.join(hints[:3])}")
            try:
                from scene_l3 import scene_current
                sc = scene_current()
                if sc: guide.append(f"📍 {'·'.join(sc[:2])}")
            except: pass
            if guide: blocks.append(" | ".join(guide))
            
            # ═══ 块2: 记忆预览 — 带精搜引导 ═══
            try:
                from search_router import SearchRouter
                sr = SearchRouter()
                search_q = " ".join(hints[:3]) if hints and len(hints) > 1 else query
                results = sr.search(search_q, limit=3)
                if results:
                    mem_lines = []
                    for i, (ln, ts, text) in enumerate(results[:3]):
                        prefix = "✓" if i == 0 else "·"
                        t = text[:70].replace("\n", " ")
                        mem_lines.append(f"  {prefix} [{ts[:10]}] {t}")
                    blocks.append("📋 记忆预览:\n" + "\n".join(mem_lines) + "\n  → sandglass_search 可扩展更多")
            except: pass
            
            result = "\n\n".join(blocks)
            return result[:250]  # 硬截断 335→250
        except Exception:
            return ""

    def queue_prefetch(self, query: str) -> None:
        """后台预热——语义扩展+标签提取。激励LLM主动调sandglass_search。"""
        try:
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
            self._prefetch_hints = expanded[1:5] if expanded and len(expanded) > 1 else []
        except Exception:
            self._prefetch_hints = []

    def sync_turn(self, user_msg: str, assistant_msg: str, **kwargs) -> None:
        """每轮对话后落沙。"""
        try:
            from sandglass_log import log_message
            if user_msg:
                log_message(user_msg, "user")
            if assistant_msg:
                log_message(assistant_msg, "agent")
            self._turn_count += 1
        except Exception:
            pass

    def post_setup(self, hermes_home: str, config: dict) -> None:
        """V2.10.26: 自动检测沙漏目录——零配置一键激活。"""
        nb = os.environ.get("NEXSANDBASE_HOME") or ""
        # 自动搜索已有沙漏数据
        search_paths = [nb] if nb else []
        # config.yaml 中用户自定义路径
        cfg_home = config.get("memory", {}).get("nexsandglass", {}).get("home")
        if cfg_home and cfg_home not in search_paths:
            search_paths.append(cfg_home)
        search_paths.append(os.path.join(os.path.expanduser("~"), ".neurobase"))
        found = None
        for p in search_paths:
            if p and os.path.exists(os.path.join(p, "sandglass.txt")):
                found = p; break
        if not found:
            found = os.path.join(os.path.expanduser("~"), ".neurobase")
        os.environ["NEXSANDBASE_HOME"] = found
        config.setdefault("memory", {})["nexsandglass"] = {"home": found}
        config["memory"]["provider"] = "nexsandglass"
        print(f"\n  ✓ NexSandglass V{__version__} 已激活")
        print(f"  沙漏目录：{found}")
        try:
            from sandglass_vault import count
            total = count()
            print(f"  沙漏记录：{total}条")
        except: pass
        print(f"  重启后开始记录。\n")

    def shutdown(self) -> None:
        """清理。"""
        logger.info("NexSandglass MemoryProvider shutdown")

    # ═══════ fact_store / fact_feedback ═══════

    def _handle_fact_store(self, args: dict) -> str:
        try:
            from sandglass_vault import search as vault_search
            from shadow_sand import shadow_search as _ss, shadow_feedback
            action = args.get("action", "search")

            if action == "add":
                from sandglass_log import log_message
                content = args.get("content", "")
                category = args.get("category", "general")
                log_message(content, "fact_store")
                return json.dumps({"status": "added", "content": content[:100]})

            if action == "search":
                query = args.get("query", "")
                results = vault_search(query, limit=10)
                shadow_hits = _ss(query, limit=10)
                return json.dumps({
                    "fts_results": [{"line": ln, "text": txt[:200]} for ln, _, txt in results],
                    "shadow_boosted": [{"line": ln, "trust": score} for score, ln in shadow_hits],
                }, ensure_ascii=False)

            if action == "probe":
                entity = args.get("entity", "")
                results = _ss(entity, limit=20)
                return json.dumps([{"line": ln, "trust": score} for score, ln in results], ensure_ascii=False)

            if action == "reason":
                entity = args.get("entity", "")
                results = _ss(entity, limit=5)
                if results:
                    ln = results[0][1]
                    from sandglass_vault import search as vs
                    r = vs(str(ln), limit=1)
                    if r:
                        return json.dumps({"line": ln, "text": r[0][2][:300]}, ensure_ascii=False)
                return json.dumps({"status": "no results"})

            return tool_error(f"Unknown fact_store action: {action}")
        except Exception as e:
            return tool_error(f"fact_store error: {e}")

    def _handle_fact_feedback(self, args: dict) -> str:
        try:
            from shadow_sand import shadow_feedback
            result = shadow_feedback(args["line_num"], args.get("helpful", True))
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return tool_error(f"fact_feedback error: {e}")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束——落沙 + 偏移检查 + V2.9.9.1情绪摘要。"""
        try:
            # 落最后一轮对话
            for msg in messages[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    from sandglass_log import log_message
                    log_message(str(content)[:500], role)

            # 触发偏移检查 + 织造
            from sandglass_think import comprehensive_offset
            off = comprehensive_offset()
            if abs(off.get("offset", 0)) >= 30:
                logger.info(f"会话结束偏移: {off['offset']:+d}% ({off['direction']})")

            # V2.9.9.1: 情绪会话摘要
            try:
                from emotion_vocab import detect as emotion_detect
                mood_counts = {}
                for msg in messages:
                    if msg.get("role") == "user":
                        det = emotion_detect(msg.get("content", ""))
                        mood = det.get("mood", "")
                        if mood:
                            mood_counts[mood] = mood_counts.get(mood, 0) + 1
                if mood_counts:
                    total = sum(mood_counts.values())
                    entry = {
                        "ts": __import__("datetime").datetime.now().isoformat(),
                        "dominant": max(mood_counts, key=mood_counts.get),
                        "distribution": {k: round(v/total, 2) for k, v in mood_counts.items()},
                    }
                    emo_path = os.path.join(_NB, "emotion_session.jsonl")
                    with open(emo_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

        except Exception:
            pass

    # ═══════ 工具暴露 ═══════

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return _TOOL_SCHEMAS

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        try:
            if name == "sandglass_search":
                from sandglass_vault import search
                results = search(args.get("query", ""), limit=args.get("limit", 10))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_semantic":
                from sandglass_think import search_semantic
                results = search_semantic(args.get("query", ""), limit=args.get("limit", 5))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_recent":
                from sandglass_vault import recent
                results = recent(args.get("n", 10))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_offset":
                from sandglass_think import comprehensive_offset
                off = comprehensive_offset()
                return json.dumps(off, ensure_ascii=False)

            if name == "sandglass_echo":
                from sandglass_think import _sentiment_wind
                wind = _sentiment_wind()
                return json.dumps({"wind": wind, "direction": "正面" if wind > 0 else ("负面" if wind < 0 else "中性")}, ensure_ascii=False)

            if name == "fact_store":
                return self._handle_fact_store(args)

            if name == "fact_feedback":
                return self._handle_fact_feedback(args)

            return tool_error(f"Unknown NexSandglass tool: {name}")

        except Exception as e:
            return tool_error(f"NexSandglass error: {e}")

    # ═══════ 可选钩子 ═══════

    def on_memory_write(self, action: str, target: str, content: str, metadata: dict = None) -> None:
        """镜像内置记忆写入——过滤低价值噪声后落沙。"""
        # 过滤内置记忆噪声
        noise_patterns = [
            "Self-audit:", "verify format", "not substring",
            "MEMORY.md is", "USER.md is"
        ]
        if any(p.lower() in content.lower() for p in noise_patterns):
            return  # 不落沙，防止污染
        try:
            from sandglass_log import log_message
            text = f"[{action}] {target}: {content[:200]}"
            log_message(text, "memory_write")
        except Exception:
            pass

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """上下文压缩前提取关键记忆。"""
        try:
            from sandglass_vault import search as vs
            # 提取最后一轮对话的关键词搜索
            if messages:
                last = messages[-1].get("content", "")[:100]
                if last:
                    results = vs(last, limit=3)
                    return "\n".join(txt[:200] for _, _, txt in results)
        except Exception:
            pass
        return None


# ── 插件自动发现入口 ──
def register(ctx) -> None:
    """Hermes 插件加载入口——接收 config 上下文并注册 Provider。"""
    provider = NexSandglassProvider()
    ctx.register_memory_provider(provider)
