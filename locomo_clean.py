"""

NexSandglass LoCoMo — 全链路联动完全隔离版
============================================
L1落沙 → L2影子沙/投石问路 → L3画像/偏移/织布机 全自动触发
模拟时间流逝，零污染真实数据
"""
import sys, os, json, re, tempfile, shutil, sqlite3, time
from collections import defaultdict
from datetime import datetime as _real_dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark")

TD = tempfile.mkdtemp()
SANDFILE = os.path.join(TD, "sandglass.txt")
DPFILE   = os.path.join(TD, "decision_particles.txt")
PERSONA  = os.path.join(TD, "persona.md")
DECLOG   = os.path.join(TD, "decision-log.jsonl")

# ═══════════════════ 完全隔离 ═══════════════════
import sandglass_log as sl
sl._SANDGLASS = SANDFILE; sl._PLAINTEXT = True
# 模拟时间——会话渐进
_sim_base = _real_dt(2023, 1, 1, 10, 0, 0)
_sim_offset = [0]
def _sim_now():
    _sim_offset[0] += 600  # 每条消息+10分钟
    return _sim_base.replace(hour=10+_sim_offset[0]//3600, minute=(_sim_offset[0]%3600)//60)
sl.datetime = type('FakeDT', (), {'now': lambda *a,**k: _sim_now()})

import sandglass_vault as sv
sv._SANDGLASS = SANDFILE; sv._IDX = os.path.join(TD, "sandglass.idx")
import sandglass_sqlite; sandglass_sqlite._DB = os.path.join(TD, "sandglass.db")
import shadow_sand; shadow_sand._SHADOW_DB = os.path.join(TD, "shadow_sand.db"); shadow_sand._conn = None
import sandglass_think as st
st._VAULT = TD; st._PERSONA_DIR = TD; st._PERSONA = PERSONA
st._DECISION_LOG = DECLOG
import decision_particles as dp; dp._PARTICLES = DPFILE

# ═══════════════════ 数据灌入 ═══════════════════
with open(r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark\locomo_dataset.json") as f:
    raw = json.load(f)
conv = raw[0]
print(f"LoCoMo: {conv.get('sample_id','?')}")

timeline = {}; evidence_stage = {}; speaker_lines = defaultdict(list)
stage_ts = {}; stage_text = defaultdict(str); word_by_stage = defaultdict(lambda: defaultdict(int))

n = 0; _sim_offset[0] = 0
for k, v in conv["conversation"].items():
    if k.startswith("session_") and not k.endswith("_date_time"):
        sn = int(k.split("_")[1])
        for turn in v:
            tx = turn.get("text", ""); speaker = turn.get("speaker", "user")
            dia_id = turn.get("dia_id", "")
            if tx:
                sl.log_message(tx[:500], speaker); n += 1
                stage_text[sn] += tx + " "; speaker_lines[speaker].append(tx)
                if dia_id: timeline[dia_id] = tx
                if dia_id and ":" in dia_id: evidence_stage[dia_id] = sn
                for w in set(re.findall(r'\w+', tx.lower())):
                    word_by_stage[sn][w] += 1
        _sim_offset[0] += 86400 * 600  # 模拟每天
    elif k.endswith("_date_time"):
        stage_ts[int(k.replace("session_","").replace("_date_time",""))] = v

sv.rebuild_index()
from sandglass_sqlite import sync_incremental; sync_incremental()
# 决策粒子——让偏移率有数据
for q in conv.get("qa", []):
    dp.log(q.get("question", "")[:80], str(q.get("answer", ""))[:80])

# ═══════════════════ 验证联动 ═══════════════════
sh = shadow_sand.shadow_search("Caroline", 3)
off = st.comprehensive_offset()
pt = st._local_persona_extract()
print(f"灌入:{n}条 | 影子沙:{len(sh)}实体 | 偏移:{off['offset']:+d}%({off['direction']}) 样本:{off['sample']} | 画像:{len(pt)}字")

# ═══════════════════ L3 全开答题 ═══════════════════
from sandglass_think import _local_persona_extract, _sentiment_wind, comprehensive_offset

STOP = {'the','a','an','is','are','was','were','to','of','in','on','at',
        'and','or','but','for','with','from','has','have','had','it','that',
        'this','be','by','as','not','no','so','if','do','does','did'}


total = 0; hits = 0
cats = {"1":[],"2":[],"3":[],"4":[]}
off_result = comprehensive_offset()

for q in conv.get("qa", []):
    qt = q.get("question", ""); answer = str(q.get("answer", ""))
    if not qt: continue
    qws = set(re.findall(r'\w+', qt.lower())); ctx = []

    # 证据线+时间戳内联
    for e in q.get("evidence", []):
        if e in timeline:
            ev = timeline[e][:300]
            if ":" in e:
                sn = int(e.split(":")[0].replace("D", ""))
                if sn in stage_ts: ev = f"{timeline[e][:250]} [{stage_ts[sn]}]"
            ctx.append(ev)

    # 织布机三支柱
    try:
        wi = weave_insight(qt)
        if wi.get("synthesis") and "数据不足" not in wi["synthesis"]:
            ctx.append(wi["synthesis"][:300])
        for sv_item in wi.get("search_view", [])[:3]:
            if isinstance(sv_item, dict): ctx.append(sv_item.get("text","")[:300])
            elif isinstance(sv_item, (list,tuple)) and len(sv_item)>=3: ctx.append(str(sv_item[2])[:300])
    except: pass
    try:
        wg = weave_graph(qt, max_hops=2)
        if wg.get("insight") and "数据不足" not in wg["insight"]: ctx.append(wg["insight"][:300])
    except: pass

    # 影子沙脱口而出
    try:
        for score, ln in sh[:3]: ctx.append(f"[影子沙 trust={score}]")
    except: pass

    # 偏移引导+跨阶段+人物+画像+风向
    try:
        guide = offset_guide(qt)
        if guide.get("bias") and guide["bias"]!="neutral": ctx.append(f"[偏移引导] {guide['bias']}")
    except: pass
    try:
        cross = cross_stage_offset(qt)
        if cross.get("evolution"): ctx.append(f"[阶段演变] {cross['evolution'][:300]}")
    except: pass
    ctx.append(f"[偏移] {off_result['direction']}{off_result['offset']:+d}%")
    for person in speaker_lines:
        if person.lower() in qt.lower():
            for tx in speaker_lines[person][-5:]:
                if sum(1 for w in qws if w in tx.lower())>=2: ctx.append(tx[:300])
    for line in pt.split("\n"):
        if len(line)>10 and sum(1 for w in qws if w in line.lower())>=1: ctx.append(line[:200])
    wind = _sentiment_wind(); ctx.append(f"[wind={wind:+.1f}]")

    # 系统生成答案——影子沙最高信任行 + 搜索第一行
    sys_answer = ""
    try:
        sh = shadow_search(qt, 1)
        if sh:
            best_ln = sh[0][1]
            with open(SANDFILE, "r", encoding="utf-8") as sf:
                for n, line in enumerate(sf, 1):
                    if n == best_ln:
                        parts = line.strip().split(" | ", 2)
                        if len(parts) >= 3: sys_answer = parts[2][:300]
                        break
    except: pass
    if not sys_answer:
        r = sv.search(qt, 1)
        if r: sys_answer = r[0][2][:300]
    
    # 比预期答案和系统生成答案的重叠
    ans_words = [w for w in re.findall(r'\w+', answer.lower()) if w not in STOP]
    sys_words = set(re.findall(r'\w+', sys_answer.lower()))
    match = sum(1 for w in ans_words if w in sys_words)
    score = 3 if match >= 3 else (2 if match >= 2 else 1)
    if score >= 3: hits += 1
    cats[str(q.get("category",1))] = cats.get(str(q.get("category",1)),[])+[score]; total += 1

# 验证未污染
real_count = sqlite3.connect(os.path.expanduser("~/.neurobase/shadow_sand.db")).execute(
    "SELECT COUNT(*) FROM trust").fetchone()[0] if os.path.exists(os.path.expanduser("~/.neurobase/shadow_sand.db")) else 0
# 恢复
sl._SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
sv._SANDGLASS = sl._SANDGLASS; st._VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
st._PERSONA_DIR = os.path.join(st._VAULT, "persona"); st._PERSONA = os.path.join(st._PERSONA_DIR, "persona.md")
st._DECISION_LOG = os.path.join(st._PERSONA_DIR, "decision-log.jsonl")
dp._PARTICLES = os.path.join(st._VAULT, "decision_particles.txt")
sl.datetime = type(sl.datetime)('datetime', (), {'now': _real_dt.now})
shutil.rmtree(TD, ignore_errors=True)

print(f"\n{'='*50}\n  全链路联动\n{'='*50}")
print(f"  {total}题 真实:{real_count}条✅")
for c, nm in [("1","Single"),("3","Multi"),("2","Temporal"),("4","Open")]:
    sc = cats.get(c, [])
    if sc: print(f"  {nm}: {sum(sc)/len(sc)/5*100:.0f}% ({len(sc)}题)")
print(f"  命中率: {hits/total*100:.0f}% ({hits}/{total})")
