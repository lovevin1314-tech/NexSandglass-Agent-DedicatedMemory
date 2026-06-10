"""
NexSandglass V1.7.7 — LoCoMo基准测试（画像增强版）
===================================================
完整管线：灌入对话→生成画像→搜题时先查画像再查沙子。
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
sl._SANDGLASS = ts
sv._SANDGLASS = ts

# 灌入对话
n = 0
for k, v in conv["conversation"].items():
    if k.startswith("session_") and not k.endswith("_date_time"):
        for turn in v:
            tx = turn.get("text", "")
            if tx:
                sl.log_message(tx[:500], turn.get("speaker", "user"))
                n += 1
print(f"灌入 {n} 条")

# 生成画像
from sandglass_think import persona_build
persona_build()
persona_path = os.path.expanduser("~/.neurobase/persona/persona.md")
persona_text = ""
if os.path.exists(persona_path):
    with open(persona_path, "r", encoding="utf-8") as f:
        persona_text = f.read()
    print(f"画像: {len(persona_text)}字")

# 答题——先画像后沙子
cats = {}
total = 0
hits = 0
for q in conv.get("qa", []):
    q_text = q.get("question", "")
    if not q_text:
        continue
    
    # 先搜画像
    persona_hits = []
    for line in persona_text.split("\n"):
        if len(line) > 10:
            if any(w in line.lower() for w in q_text.lower().split()):
                persona_hits.append(line[:200])
    
    # 再搜沙子
    sand_hits = sv.search(q_text, 5)
    sand_texts = [c[2][:300] for c in sand_hits]
    
    # 合并：画像优先
    all_ctx = persona_hits[:3] + sand_texts[:3]
    
    # 评分
    answer = str(q.get("answer", "")).lower()
    ans_words = set(re.findall(r'[\w]+', answer))
    ctx_text = " ".join(all_ctx).lower()
    match = sum(1 for w in ans_words if w in ctx_text)
    score = 3 if match >= 2 else (2 if match >= 1 else 1)
    if score >= 3:
        hits += 1
    
    cat = str(q.get("category", 1))
    cats[cat] = cats.get(cat, []) + [score]
    total += 1

print(f"\n{'='*40}")
print(f"  NexSandglass V1.7.7 LoCoMo（画像增强）")
print(f"{'='*40}")
for c, nm in [("1", "Single-Hop"), ("3", "Multi-Hop"), ("2", "Temporal"), ("4", "Open-Domain")]:
    sc = cats.get(c, [])
    if sc:
        print(f"  {nm}: {sum(sc)/len(sc)/5*100:.0f}% ({len(sc)}题)")
print(f"  综合命中率: {hits/total*100:.0f}% ({total}题, 命中{hits})")
print(f"\n  行业: Backboard 90% | Mem0 67% | NexSandglass {hits/total*100:.0f}%")

sl._SANDGLASS = o1
sv._SANDGLASS = o2
shutil.rmtree(td, ignore_errors=True)
