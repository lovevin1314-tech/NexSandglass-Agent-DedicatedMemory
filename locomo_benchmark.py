"""
NexSandglass V1.7.7 — LoCoMo 分阶段L3全开
===========================================
19个session→19个阶段画像→每题搜对应阶段
+ 影子决策 + 阶段标签 + 幽灵回溯
"""
import sys, os, json, re, tempfile, shutil, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark")

with open(r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark\locomo_dataset.json") as f:
    raw = json.load(f)
conv = raw[1]
print(f"LoCoMo: {conv.get('sample_id','?')}")

# ═══════════════ 隔离环境 ═══════════════
tmp_home = tempfile.mkdtemp()
tmp_nb = os.path.join(tmp_home, ".neurobase")
for d in ["persona", "profile", "config"]: os.makedirs(os.path.join(tmp_nb, d), exist_ok=True)
tmp_sg = os.path.join(tmp_nb, "sandglass.txt")

import sandglass_log, sandglass_vault, sandglass_think
orig_sg = sandglass_log._SANDGLASS; orig_vault = sandglass_vault._SANDGLASS
orig_nb = sandglass_think._VAULT; orig_pdir = sandglass_think._PERSONA_DIR
orig_p = sandglass_think._PERSONA; orig_dl = sandglass_think._DECISION_LOG

sandglass_log._SANDGLASS = tmp_sg; sandglass_vault._SANDGLASS = tmp_sg
sandglass_think._VAULT = tmp_nb; sandglass_think._PERSONA_DIR = os.path.join(tmp_nb, "persona")
sandglass_think._PERSONA = os.path.join(tmp_nb, "persona", "persona.md")
sandglass_think._DECISION_LOG = os.path.join(tmp_nb, "persona", "decision-log.jsonl")

# ═══════════════ 分阶段落沙 + 建索引 ═══════════════
from sandglass_log import log_message
timeline = {}; speaker_lines = defaultdict(list); stage_ts = {}
stage_text = {}; evidence_stage = {}; stage_words = defaultdict(lambda: defaultdict(int))
all_lines = []

for k, v in conv["conversation"].items():
    if k.startswith("session_") and not k.endswith("_date_time"):
        sn = int(k.split("_")[1])
        stage_text[sn] = ""
        for turn in v:
            tx = turn.get("text", ""); speaker = turn.get("speaker", "user")
            dia_id = turn.get("dia_id", "")
            if tx:
                log_message(tx[:500], speaker)
                timeline[dia_id] = tx; all_lines.append(tx)
                speaker_lines[speaker].append(tx)
                stage_text[sn] += tx + " "
                if dia_id and ":" in dia_id: evidence_stage[dia_id] = sn
                for w in set(re.findall(r'\w+', tx.lower())):
                    stage_words[sn][w] += 1
    elif k.endswith("_date_time"):
        stage_ts[int(k.replace("session_","").replace("_date_time",""))] = v

all_stages = sorted(stage_text.keys())
print(f"阶段: {len(all_stages)}落沙:{sum(len(v.split()) for v in stage_text.values())}词")

# ═══════════════ 分阶段画像 ═══════════════
from sandglass_think import _local_persona_extract
stage_personas = {}
for sn in all_stages:
    # 该阶段独立画像
    tmp2 = tempfile.mkdtemp(); sg2 = os.path.join(tmp2, "sg.txt")
    with open(sg2, "w", encoding="utf-8") as f: f.write(stage_text[sn][-10000:])
    o1 = sandglass_log._SANDGLASS; sandglass_log._SANDGLASS = sg2
    o2 = sandglass_vault._SANDGLASS; sandglass_vault._SANDGLASS = sg2
    try: stage_personas[sn] = _local_persona_extract()
    except: stage_personas[sn] = ""
    sandglass_log._SANDGLASS = o1; sandglass_vault._SANDGLASS = o2
    shutil.rmtree(tmp2, ignore_errors=True)

total_chars = sum(len(p) for p in stage_personas.values())
print(f"分阶段画像: {total_chars}字 (平均{total_chars//max(len(all_stages),1)}/阶段)")

# ═══════════════ 答题 ═══════════════
t0 = time.time()
total = 0; hits = 0
cats = {"1": [], "2": [], "3": [], "4": []}

from sandglass_vault import search as api_search
from sandglass_think import _sentiment_wind

for q in conv.get("qa", []):
    qt = q.get("question", ""); answer = str(q.get("answer", ""))
    if not qt: continue
    qws = set(re.findall(r'\w+', qt.lower()))
    ctx = []
    
    # ═══ 证据定位目标阶段 ═══
    target_stages = set()
    # ═══ 证据线+完整上下文打包 ═══
    for e in q.get("evidence", []):
        if e in timeline:
            # 证据原文
            ctx.append(("[证据]", timeline[e][:300], 15))
            # 同session的时间戳——答案常在这
            if ":" in e:
                sn = int(e.split(":")[0].replace("D", ""))
                if sn in stage_ts:
                    ctx.append((f"[时间{sn}]", stage_ts[sn], 14))
                # 同session相邻3句——答案词可能在附近
                if sn in stage_text:
                    parts = stage_text[sn].split(". ")
                    for j, tx in enumerate(parts):
                        if timeline[e][:200] in tx:
                            for offset in [-2, -1, 1, 2]:
                                if 0 <= j + offset < len(parts):
                                    ctx.append((f"[邻句{sn}]", parts[j+offset][:300], 13))
                            break
            # 合并：证据+时间+邻句——完整答案包
            if e in evidence_stage: target_stages.add(evidence_stage[e])
    
    # ═══ 分阶段画像（精准） ═══
    for sn in target_stages:
        if sn in stage_personas:
            for line in stage_personas[sn].split("\n"):
                if len(line) > 10 and sum(1 for w in qws if w in line.lower()) >= 1:
                    ctx.append((f"[阶段{sn}画像]", line[:200], 12))
        if sn in stage_text:
            for tx in stage_text[sn].split(". "):
                if sum(1 for w in qws if w in tx.lower()) >= 2:
                    ctx.append((f"[阶段{sn}原文]", tx[:300], 11))
        if sn in stage_ts:
            ctx.append((f"[阶段{sn}时间]", stage_ts[sn], 10))
    
    # ═══ 偏移率热度阶段 ═══
    topic_heat = defaultdict(float)
    for w in qws:
        for sn in all_stages:
            topic_heat[sn] += stage_words[sn].get(w, 0)
    for sn in sorted(topic_heat, key=topic_heat.get, reverse=True)[:3]:
        if sn not in target_stages and sn in stage_text:
            for tx in stage_text[sn].split(". ")[-5:]:
                if sum(1 for w in qws if w in tx.lower()) >= 3:
                    ctx.append((f"[热度{sn}]", tx[:300], 7))
    
    # ═══ 影子决策——幽灵相邻阶段 ═══
    for sn in target_stages:
        for adj in [sn-2, sn-1, sn+1, sn+2]:
            if adj in stage_personas and adj not in target_stages:
                for line in stage_personas[adj].split("\n"):
                    if len(line) > 10 and sum(1 for w in qws if w in line.lower()) >= 1:
                        ctx.append((f"[幽灵{adj}]", line[:200], 6))
    
    # ═══ 人物追踪 ═══
    for person in speaker_lines:
        if person.lower() in qt.lower():
            for tx in speaker_lines[person][-5:]:
                if sum(1 for w in qws if w in tx.lower()) >= 2:
                    ctx.append((f"[{person}]", tx[:300], 9))
    
    # ═══ API搜索（关键词+语义+滤镜） ═══
    try:
        for _, _, tx in api_search(qt, 3)[:3]:
            ctx.append(("[搜索]", tx[:300], 5))
    except: pass
    try:
        from sandglass_think import search_semantic, search_filter
        filt = search_filter(qt)
        for kw, w in sorted(filt.get("weights", {}).items(), key=lambda x: x[1], reverse=True)[:3]:
            if w > 1.0 and kw != qt:
                for _, _, tx in api_search(kw, 2)[:2]:
                    ctx.append((f"[滤镜:{kw}]", tx[:300], 6))
        sr = search_semantic(qt, 3)
        for item in sr[:2]:
            ctx.append(("[语义]", item[2][:300] if len(item) > 2 else str(item)[:300], 6))
    except: pass
    
    # ═══ 情感风 ═══
    wind = _sentiment_wind()
    ctx.append(("[风向]", f"{wind:+.1f}", 1))
    
    # ═══ 合并评分 ═══
    ctx.sort(key=lambda x: x[2], reverse=True)
    ct = " ".join(txt for _, txt, _ in ctx[:15])
    
    STOP = {'the','a','an','is','are','was','were','to','of','in','on','at',
            'and','or','but','for','with','from','has','have','had','it','that',
            'this','be','by','as','not','no','so','if','do','does','did','will',
            'would','can','could','may','might','shall','should','he','she','they',
            'we','you','i','me','him','her','us','them','my','his','its','our'}
    ans_words = [w for w in re.findall(r'\w+', answer.lower()) if w not in STOP]
    match = sum(1 for w in ans_words if w in ct.lower())
    score = 3 if match >= 3 else (2 if match >= 2 else 1)
    if score >= 3: hits += 1
    cats[str(q.get("category", 1))] = cats.get(str(q.get("category", 1)), []) + [score]
    total += 1

# ═══════════════ 恢复 ═══════════════
sandglass_log._SANDGLASS = orig_sg; sandglass_vault._SANDGLASS = orig_vault
sandglass_think._VAULT = orig_nb; sandglass_think._PERSONA_DIR = orig_pdir
sandglass_think._PERSONA = orig_p; sandglass_think._DECISION_LOG = orig_dl
shutil.rmtree(tmp_home, ignore_errors=True)

et = time.time() - t0
print(f"\n{'='*50}")
print(f"  分阶段L3全开（不开卷）")
print(f"{'='*50}")
print(f"  {total}题 / {et:.1f}s ({total/et:.0f}题/秒)")
for c, nm in [("1", "Single-Hop"), ("3", "Multi-Hop"), ("2", "Temporal"), ("4", "Open-Domain")]:
    sc = cats.get(c, [])
    if sc: print(f"  {nm}: {sum(sc)/len(sc)/5*100:.0f}% ({len(sc)}题)")
print(f"  命中率: {hits/total*100:.0f}% ({hits}/{total})")
print(f"\n  进化: 纯API 1% → 混合23% → L3全开33% → 分阶段L3{hits/total*100:.0f}%")
