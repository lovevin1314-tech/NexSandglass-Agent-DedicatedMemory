"""
NexSandglass V1.7.7 — LoCoMo基准测试
=====================================
将LoCoMo标准数据集灌入沙漏，用沙漏搜索回答问题，LLM-as-judge评分。
纯脱敏——使用临时沙漏，不污染真实数据。
用法：python locomo_benchmark.py
"""
import sys, os, json, time, re, tempfile, shutil
# 从Hermes读API Key
import os as _os
_hermes_env = _os.path.expanduser("~/.hermes/.env")
if _os.path.exists(_hermes_env):
    with open(_hermes_env) as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                _os.environ["DEEPSEEK_API_KEY"] = line.split("=",1)[1].strip().strip('"').strip("'")
                break

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark")

DATASET = r"C:\Users\NeuroBase\Backboard-Locomo-Benchmark\locomo_dataset.json"
if not os.path.exists(DATASET):
    print(f"❌ 数据集不存在"); sys.exit(1)

with open(DATASET, 'r', encoding='utf-8') as f:
    raw = json.load(f)

# 只跑前2个对话（每个199题，省时间）
conversations = raw[:2]
print(f"LoCoMo对话: {len(conversations)}个, 每个~199题")

# 初始化临时沙漏
tmp_dir = tempfile.mkdtemp()
tmp_sg = os.path.join(tmp_dir, "sandglass.txt")
import sandglass_log, sandglass_vault
orig_sg, orig_vault = sandglass_log._SANDGLASS, sandglass_vault._SANDGLASS
sandglass_log._SANDGLASS = tmp_sg
sandglass_vault._SANDGLASS = tmp_sg

# 灌入对话
total_msgs = 0
for conv in conversations:
    for key, val in conv["conversation"].items():
        if key.startswith("session_") and not key.endswith("_date_time"):
            for turn in val:
                text = turn.get("text", "")
                if text:
                    sandglass_log.log_message(text[:500], turn.get("speaker", "user"))
                    total_msgs += 1

print(f"灌入 {total_msgs} 条消息")
from sandglass_vault import count as vc
print(f"沙漏: {vc()} 条")

# 搜索+评分
from sandglass_vault import search as vs
from sandglass_think import _llm

def answer(q_text, top_k=5):
    results = vs(q_text, top_k)
    return [r[2][:300] for r in results] if results else []

def judge(question, answer, ctx):
    try:
        system = "你是记忆评测专家。只看检索到的上下文能否回答问题。1=完全不能 5=完美。只输出数字。"
        prompt = f"问题: {question}\n上下文:\n" + "\n".join(ctx[:5]) + "\n\n能回答吗？只输出1-5:"
        r = _llm(system, prompt, max_tokens=10)
        return int(re.search(r'[1-5]', r).group()) if r and re.search(r'[1-5]', r) else 0
    except: return 0

cats = {"single_hop": [], "multi_hop": [], "temporal": [], "open_domain": []}
total = 0; total_score = 0

for conv in conversations:
    for q in conv.get("qa", []):
        q_text = q.get("question", "")
        if not q_text: continue
        ctx = answer(q_text, 5)
        score = judge(q_text, q.get("answer", ""), ctx)
        
        cat = q.get("category", 1)
        if cat == 1: cats["single_hop"].append(score)
        elif cat == 2: cats["temporal"].append(score)
        elif cat == 3: cats["multi_hop"].append(score)
        elif cat == 4: cats["open_domain"].append(score)
        else: cats["single_hop"].append(score)
        
        total += 1; total_score += score

# 输出
print("\n" + "=" * 50)
print("  NexSandglass V1.7.7 LoCoMo 评测")
print("=" * 50)
for name, scores in [("Single-Hop", cats["single_hop"]), ("Multi-Hop", cats["multi_hop"]),
                      ("Temporal", cats["temporal"]), ("Open-Domain", cats["open_domain"])]:
    if scores:
        avg = sum(scores)/len(scores)/5*100
        print(f"  {name}: {avg:.1f}% ({len(scores)}题)")
overall = total_score/max(total,1)/5*100
print(f"  综合: {overall:.1f}% ({total}题)")
print(f"\n行业: Backboard 90% | Mem0 67% | NexSandglass {overall:.0f}%")

# 清理
sandglass_log._SANDGLASS = orig_sg
sandglass_vault._SANDGLASS = orig_vault
shutil.rmtree(tmp_dir, ignore_errors=True)
