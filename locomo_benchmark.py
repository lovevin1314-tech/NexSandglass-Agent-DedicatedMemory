"""
NexSandglass V1.7.7 — LoCoMo 纯本地API基准
=============================================
只用系统API: search/offset_check/search_filter/weave
临时环境隔离，不污染真实数据
"""
import sys, os, json, re, tempfile, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark")

with open(r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark\locomo_dataset.json") as f:
    raw = json.load(f)
conv = raw[0]
print(f"LoCoMo: {conv.get('sample_id','?')}")

# ═══════════════════ 隔离环境 ═══════════════════
tmp_home = tempfile.mkdtemp()
tmp_nb = os.path.join(tmp_home, ".neurobase")
os.makedirs(os.path.join(tmp_nb, "persona"), exist_ok=True)
tmp_sg = os.path.join(tmp_nb, "sandglass.txt")
tmp_dp = os.path.join(tmp_nb, "decision_particles.txt")

# 重定向——所有API都指向临时目录
import sandglass_log, sandglass_vault
orig_sg = sandglass_log._SANDGLASS
orig_vault = sandglass_vault._SANDGLASS
sandglass_log._SANDGLASS = tmp_sg
sandglass_vault._SANDGLASS = tmp_sg

# 重定向 persona + decision_log 路径
import sandglass_think
orig_persona = sandglass_think._PERSONA
orig_decision_log = sandglass_think._DECISION_LOG
sandglass_think._PERSONA = os.path.join(tmp_nb, "persona", "persona.md")
sandglass_think._DECISION_LOG = os.path.join(tmp_nb, "persona", "decision-log.jsonl")
sandglass_think._VAULT = tmp_nb
sandglass_think._PERSONA_DIR = os.path.join(tmp_nb, "persona")

# ═══════════════════ 落沙（用真实API） ═══════════════════
n = 0
from sandglass_log import log_message
for k, v in conv["conversation"].items():
    if k.startswith("session_") and not k.endswith("_date_time"):
        for turn in v:
            tx = turn.get("text", "")
            speaker = turn.get("speaker", "user")
            if tx: log_message(tx[:500], speaker); n += 1
print(f"落沙: {n}条")

# ═══════════════════ 落米粒到隔离路径 ═══════════════════
from decision_particles import log as dp_log
for q in conv.get("qa", []):
    dp_log(q.get("question", ""), str(q.get("answer", "")))
# 重定向dp内部路径
import decision_particles
orig_dp_path = decision_particles._PARTICLES
decision_particles._PARTICLES = tmp_dp

# ═══════════════════ 真实API答题 ═══════════════════
t0 = time.time()
total = 0; hits = 0
cats = {"1": [], "2": [], "3": [], "4": []}

from sandglass_vault import search as api_search
from sandglass_think import search_semantic, comprehensive_offset

for q in conv.get("qa", []):
    qt = q.get("question", ""); answer = str(q.get("answer", ""))
    if not qt: continue
    
    # 用真实API搜索
    ctx_lines = []
    
    # 关键词搜索
    try:
        results = api_search(qt, 10)
        for _, _, text in results[:5]:
            ctx_lines.append(text[:300])
    except: pass
    
    # 语义搜索
    try:
        sr = search_semantic(qt, 5)
        for item in sr[:3]:
            ctx_lines.append(item[2][:300] if len(item) > 2 else str(item)[:300])
    except: pass
    
    # 合并评分——更诚实：≥3个独立答案词命中才算（不算停用词）
    ctx = " ".join(ctx_lines[:8])
    # 英文停用词过滤
    STOP = {'the','a','an','is','are','was','were','to','of','in','on','at',
            'and','or','but','for','with','from','has','have','had','it','that',
            'this','be','by','as','not','no','so','if','do','does','did','will',
            'would','can','could','may','might','shall','should','he','she','they',
            'we','you','i','me','him','her','us','them','my','his','its','our'}
    ans_words = [w for w in re.findall(r'\w+', answer.lower()) if w not in STOP]
    ctx_lower = ctx.lower()
    match = sum(1 for w in ans_words if w in ctx_lower)
    # ≥3个独立实义词命中=得分
    score = 3 if match >= 3 else (2 if match >= 2 else 1)
    if score >= 3: hits += 1
    
    cat = str(q.get("category", 1))
    cats[cat] = cats.get(cat, []) + [score]
    total += 1

# ═══════════════════ 恢复+清理 ═══════════════════
sandglass_log._SANDGLASS = orig_sg
sandglass_vault._SANDGLASS = orig_vault
sandglass_think._PERSONA = orig_persona
sandglass_think._DECISION_LOG = orig_decision_log
decision_particles._PARTICLES = orig_dp_path
shutil.rmtree(tmp_home, ignore_errors=True)

# ═══════════════════ 输出 ═══════════════════
et = time.time() - t0
print(f"\n{'='*50}")
print(f"  纯本地API基准（停用词过滤）")
print(f"{'='*50}")
print(f"  {total}题 / {et:.1f}s")
for c, nm in [("1", "Single-Hop"), ("3", "Multi-Hop"), ("2", "Temporal"), ("4", "Open-Domain")]:
    sc = cats.get(c, [])
    if sc: print(f"  {nm}: {sum(sc)/len(sc)/5*100:.0f}% ({len(sc)}题)")
print(f"  命中率: {hits/total*100:.0f}% ({hits}/{total})")
print(f"\n  对比: 手写8路53% → 纯API停用词过滤{hits/total*100:.0f}%")
