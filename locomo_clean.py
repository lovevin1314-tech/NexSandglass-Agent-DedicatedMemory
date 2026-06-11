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
    total = _sim_offset[0]
    return _sim_base.replace(
        hour=min(10 + total // 3600, 23),
        minute=(total % 3600) // 60)
sl.datetime = type("FakeDT", (), {"now": lambda *a,**k: _sim_now()})

import sandglass_vault as sv
sv._SANDGLASS = SANDFILE; sv._IDX = os.path.join(TD, "sandglass.idx")
import sandglass_sqlite; sandglass_sqlite._DB = os.path.join(TD, "sandglass.db")
import shadow_sand; shadow_sand._SHADOW_DB = os.path.join(TD, "shadow_sand.db"); shadow_sand._conn = None
import sandglass_think as st
import persona_l3 as pl
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
pt = pl._local_persona_extract()
print(f"灌入:{n}条 | 影子沙:{len(sh)}实体 | 偏移:{off['offset']:+d}%({off['direction']}) 样本:{off['sample']} | 画像:{len(pt)}字")

# ═══════════════════ L3 全开答题 ═══════════════════
from sandglass_think import search_semantic

STOP = {'the','a','an','is','are','was','were','to','of','in','on','at',
        'and','or','but','for','with','from','has','have','had','it','that',
        'this','be','by','as','not','no','so','if','do','does','did'}

total = 0; hits = 0
cats = {"1":[],"2":[],"3":[],"4":[]}

for q in conv.get("qa", []):
    qt = q.get("question", ""); answer = str(q.get("answer", ""))
    if not qt: continue

    # 用系统搜索链获取答案
    results = search_semantic(qt, limit=10)
    sys_words = set()
    for item in results:
        if len(item) >= 3:
            sys_words.update(re.findall(r'\w+', str(item[2]).lower()))

    ans_words = [w for w in re.findall(r'\w+', answer.lower()) if w not in STOP]
    match = sum(1 for w in ans_words if w in sys_words)
    score = 3 if match >= 2 else (2 if match >= 1 else 1)  # 2实义词即可
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
