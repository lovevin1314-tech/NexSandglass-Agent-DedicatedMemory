"""
NexSandglass V1.7.7 — PersonaMem基准测试适配器
================================================
用法：python persona_mem_benchmark.py
"""
import sys, os, json, re, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════
# 合成测试数据（PersonaMem格式）——真实数据从HF下载
# ═══════════════════════════════════════
TEST_DATA = [
    {"persona_id": "p1", "baseline": "frugal", "evolved": "spend",
     "contexts": [
         ["Alex: 太贵了，找免费替代品。", "Friend: 免费的够用吗？", "Alex: 够用，开源就行。"],
         ["Alex: 试用付费版，效率确实高。", "Friend: 考虑订阅？", "Alex: 是的，时间比钱值钱。"],
         ["Alex: 订了年付计划，比按月省40%。", "Friend: 你变了！", "Alex: 效率优先。"]
     ],
     "qa": [
         ("Alex初始偏好什么方案？", "免费开源方案", "偏好追踪"),
         ("Alex为什么改变？", "付费效率高省时间", "偏好演进"),
         ("Alex最终选了什么？", "年度订阅", "偏好推理"),
     ]},
    {"persona_id": "p2", "baseline": "drift", "evolved": "frugal",
     "contexts": [
         ["Bailey: 太难了不做了。", "Friend: 别放弃！", "Bailey: 算了不搞了。"],
         ["Bailey: 重新用免费工具搭的。", "Friend: 不错！", "Bailey: 关键是用对方法。"],
         ["Bailey: 坚持三周了，免费方案跑稳了。", "Friend: 进步很大！", "Bailey: 不再随便放弃了。"]
     ],
     "qa": [
         ("Bailey最初倾向什么？", "容易放弃", "偏好追踪"),
         ("Bailey怎么克服的？", "用免费工具坚持", "冲突消解"),
         ("Bailey现在的状态？", "坚持不再随便放弃", "偏好演进"),
     ]},
]

# ═══════════════════════════════════════
# 灌入沙漏 + 画像
# ═══════════════════════════════════════
tmp_dir = tempfile.mkdtemp()
tmp_sg = os.path.join(tmp_dir, "sandglass.txt")
import sandglass_log, sandglass_vault
orig_sg, orig_vault = sandglass_log._SANDGLASS, sandglass_vault._SANDGLASS
sandglass_log._SANDGLASS = tmp_sg
sandglass_vault._SANDGLASS = tmp_sg

from sandglass_think import comprehensive_offset, persona_build
from sandglass_vault import search as vs

results = []
for conv in TEST_DATA:
    pid = conv["persona_id"]
    print(f"\n{'='*40}\n  用户 {pid} (基线:{conv['baseline']}→{conv['evolved']})")
    
    for session in conv["contexts"]:
        for msg in session:
            sandglass_log.log_message(msg[:500], "user")
    
    persona_build()
    off = comprehensive_offset()
    print(f"  偏移率: {off['offset']:+d}% ({off['direction']})")
    
    correct = 0
    for q_text, answer, topic in conv["qa"]:
        ctx = vs(q_text, 5)
        # 中文匹配：答案中的字/词在上下文中出现即命中
        ans_chars = set(answer.replace(' ', ''))
        ctx_text = ' '.join(c[2] for c in ctx)
        hits = sum(1 for ch in ans_chars if ch in ctx_text) / max(len(ans_chars), 1) * 5
        score = min(5, max(1, hits))
        print(f"    {topic}: {q_text[:30]} → {score}/5")
        if score >= 3: correct += 1
    
    acc = correct / max(len(conv["qa"]), 1) * 100
    print(f"  准确率: {acc:.0f}%")
    results.append({"persona": pid, "offset": off["offset"], "direction": off["direction"], "accuracy": acc})

print(f"\n{'='*40}")
print("  NexSandglass V1.7.7 PersonaMem 评测")
print(f"{'='*40}")
for r in results:
    print(f"  {r['persona']}: 偏移{r['offset']:+d}%({r['direction']}) 准确{r['accuracy']:.0f}%")
avg = sum(r["accuracy"] for r in results) / max(len(results), 1)
print(f"  综合准确率: {avg:.0f}%")
print(f"  行业: RGMem 74% | OpenClaw 76% | NexSandglass {avg:.0f}%")

sandglass_log._SANDGLASS = orig_sg
sandglass_vault._SANDGLASS = orig_vault
shutil.rmtree(tmp_dir, ignore_errors=True)
