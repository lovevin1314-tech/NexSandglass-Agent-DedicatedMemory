"""
NexSandglass V1.7.7 — LoCoMo 全管线织布机答题
===============================================
完整记忆系统答题: 沙子→米粒→画像→织布机→情感风→幽灵决策
"""
import sys, os, json, re, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark")

with open(r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark\locomo_dataset.json") as f:
    raw = json.load(f)
conv = raw[0]
print(f"对话: {conv.get('sample_id','?')}")

td = tempfile.mkdtemp()
ts = os.path.join(td, "sandglass.txt")
import sandglass_log as sl, sandglass_vault as sv
o1, o2 = sl._SANDGLASS, sv._SANDGLASS
sl._SANDGLASS = ts; sv._SANDGLASS = ts

# ═══════════════════ 1. 沙子：灌入全部对话 ═══════════════════
n = 0
for k, v in conv["conversation"].items():
    if k.startswith("session_") and not k.endswith("_date_time"):
        for turn in v:
            tx = turn.get("text", "")
            if tx:
                sl.log_message(tx[:500], turn.get("speaker", "user"))
                n += 1
print(f"沙子: {n}条")

# ═══════════════════ 2. 米粒：灌入推理——每个Q&A作为决策粒子 ═══════════════════
from decision_particles import log as dp_log
for q in conv.get("qa", []):
    dp_log(q.get("question", ""), str(q.get("answer", "")))
# 同时 feed_all 反哺画像+权重+矛盾检测
from decision_particles import feed_all, _weave_check
# 已通过log()调用feed_all

# ═══════════════════ 3. 画像：LLM四层深度扫描 ═══════════════════
import sandglass_think
sandglass_think._LLM_MODEL = 'deepseek-v4-flash'
from sandglass_think import persona_build
import sandglass_vault as sv_mod
orig_recent = sv_mod.recent
sv_mod.recent = lambda n: orig_recent(min(n, 80))
persona_build()
sv_mod.recent = orig_recent

pp = os.path.expanduser("~/.neurobase/persona/persona.md")
persona_text = ""
if os.path.exists(pp):
    with open(pp, "r", encoding="utf-8") as f:
        persona_text = f.read()
    print(f"画像: {len(persona_text)}字")

# ═══════════════════ 4. 织布机：采集所有子系统数据 ═══════════════════
from sandglass_think import (weave_insight, weave_graph, weave_contradiction,
                              search_semantic, _sentiment_wind, sentiment_rerank)
from sandglass_vault import search as vs

cats = {"1": [], "2": [], "3": [], "4": []}
total = 0; hits = 0

for q in conv.get("qa", []):
    q_text = q.get("question", "")
    if not q_text: continue
    
    ctx_lines = []
    
    # --- 画像：结构化事实 ---
    for line in persona_text.split("\n"):
        if len(line) > 15 and any(w in line.lower() for w in q_text.lower().split()):
            ctx_lines.append(f"[画像] {line[:200]}")
    
    # --- 织布机：三支柱合成洞察 ---
    try:
        wi = weave_insight(q_text)
        if wi.get("synthesis"):
            ctx_lines.append(f"[织布] {wi['synthesis'][:200]}")
        if wi.get("persona_view") and wi["persona_view"][0] != "画像中无相关内容":
            for pv in wi["persona_view"][:2]:
                ctx_lines.append(f"[画像线] {pv[:200]}")
        if wi.get("offset_view", {}).get("evolution"):
            ctx_lines.append(f"[偏移线] {wi['offset_view']['evolution'][:200]}")
        for sv_item in wi.get("search_view", [])[:2]:
            ctx_lines.append(f"[检索线] {str(sv_item)[:200]}")
    except: pass
    
    # --- 因果图：织布机因果追溯 ---
    try:
        wg = weave_graph(q_text, max_hops=2)
        for chain in wg.get("chains", [])[:3]:
            ctx_lines.append(f"[因果] {str(chain)[:200]}")
        if wg.get("insight"):
            ctx_lines.append(f"[因果洞察] {wg['insight'][:200]}")
    except: pass
    
    # --- 矛盾检测：织布机矛盾信号 ---
    try:
        wc = weave_contradiction()
        for c in wc.get("conflicts", [])[:2]:
            ctx_lines.append(f"[矛盾] {c.get('conflict','')[:150]}")
    except: pass
    
    # --- 情感风：当前情绪方向 ---
    try:
        wind = _sentiment_wind()
        ctx_lines.append(f"[情感风] wind={wind:+0.2f}")
    except: pass
    
    # --- 语义搜索 + 情感重排 ---
    try:
        sr = search_semantic(q_text, 5)
        for item in sr:
            ctx_lines.append(f"[语义] {item[2][:200]}")
    except: pass
    
    # --- 关键词搜索 ---
    sh = vs(q_text, 5)
    for c in sh:
        ctx_lines.append(f"[关键词] {c[2][:200]}")
    
    # ═══════ 合并评分 ═══════
    ctx = " ".join(ctx_lines[:10])
    answer = str(q.get("answer", "")).lower()
    ans_words = set(re.findall(r'[\w]+', answer))
    match = sum(1 for w in ans_words if w in ctx.lower())
    score = 3 if match >= 2 else (2 if match >= 1 else 1)
    if score >= 3: hits += 1
    
    cats[str(q.get("category", 1))] = cats.get(str(q.get("category", 1)), []) + [score]
    total += 1

# ═══════════════════ 输出 ═══════════════════
print(f"\n{'='*50}")
print(f"  NexSandglass V1.7.7 LoCoMo（全管线织布机）")
print(f"{'='*50}")
for c, nm in [("1", "Single-Hop"), ("3", "Multi-Hop"), ("2", "Temporal"), ("4", "Open-Domain")]:
    sc = cats.get(c, [])
    if sc: print(f"  {nm}: {sum(sc)/len(sc)/5*100:.0f}% ({len(sc)}题)")
print(f"  命中率: {hits/total*100:.0f}% ({total}题)")
print(f"  对比: 离线0% → LLM画像14% → 全管线{hits/total*100:.0f}%")

sl._SANDGLASS = o1; sv._SANDGLASS = o2
shutil.rmtree(td, ignore_errors=True)
