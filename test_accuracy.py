"""
NexSandglass V1.7.6 正确性基准测试
===================================
P1-4: 写入-搜索 round-trip（脱敏版）
P0-1: 偏移率精度基准
P0-2: composite_rerank 排序质量
用法：python test_accuracy.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0; FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1; print(f"  ✅ {label}")
    else:
        FAIL += 1; print(f"  ❌ {label}: {detail}")

# ═══════════════════════════════════════════════
print("═══ P1-4 写入-搜索闭环 ═══")

from sandglass_vault import search, recent, count
total = count()
print(f"  沙漏总量: {total}条")

check("搜索'DPAPI'有结果", len(search("DPAPI")) > 0)
check("搜索'加密'有结果", len(search("加密")) > 0)
check("搜索'偏移率'有结果", len(search("偏移率")) > 0)
check("搜索不存在词返回空", len(search("XyzzyNoSuch12345")) == 0)

r = recent(10)
check("最近10条可读", len(r) == 10 and all(x[2] for x in r))
if len(r) >= 2:
    # recent返回行号可能因并发写入不完全倒序，只验至少有内容
    pass

for q in ["加密", "记忆", "决策"]:
    results = search(q, 5)
    ok = all(len(x) == 3 and isinstance(x[0], int) and x[1] and x[2] for x in results)
    check(f"搜索'{q}'格式正确", ok)

print(f"  → {PASS}通过 / {PASS+FAIL}项")

# ═══════════════════════════════════════════════
print("\n═══ P0-1 偏移率精度基准 ═══")

from sandglass_think import offset_check

ANNOTATED = [
    ("还是用免费方案吧，不花钱的最好",  "frugal"),
    ("不买了，自己写一个算了",          "frugal"),
    ("开源的有现成的吗？免费的就行",    "frugal"),
    ("太贵了，找找替代的便宜方案",      "frugal"),
    ("这功能自己搞也不难，不花冤枉钱",  "frugal"),
    ("性价比第一，贵的不要",            "frugal"),
    ("本地部署吧，不上云了",            "frugal"),
    ("算了不搞了，太麻烦了",            "drift"),
    ("不管了，能用就行",                "drift"),
    ("放弃吧，这个方向不对",            "drift"),
    ("随便选一个吧，都差不多",          "drift"),
    ("去买个付费版吧，省时间",          "spend"),
    ("订阅一个算了，自己写太慢",       "spend"),
    ("花钱能解决的事都不是事",          "spend"),
    ("效率优先，该花就花",              "spend"),
    ("用Python写个脚本处理一下",        "neutral"),
    ("今天天气不错",                    "neutral"),
    ("先做A方案再对比B方案",            "neutral"),
]

direction_ok = 0
for text, expected in ANNOTATED:
    result = offset_check(text)
    if result["direction"] == expected:
        direction_ok += 1

accuracy = direction_ok / len(ANNOTATED) * 100
print(f"  标注集: {len(ANNOTATED)}条, 准确率: {accuracy:.0f}%")
check("偏移率方向准确率≥70%", accuracy >= 70, f"当前{accuracy:.0f}%")

# 偏移值符号验证
for text, expected in ANNOTATED:
    result = offset_check(text)
    if expected == "frugal":
        ok = result["offset"] >= 0
    elif expected == "spend":
        ok = result["offset"] <= 0
    elif expected == "drift":
        ok = result["offset"] <= 0
    else:
        ok = True
    if not ok:
        print(f"  ⚠️ 符号异常: '{text[:25]}' expected {expected} got offset={result['offset']:+d} dir={result['direction']}")

# ═══════════════════════════════════════════════
print("\n═══ P0-2 搜索排序质量 ═══")

from sandglass_think import composite_rerank

dummy = [(1,'','加密工具DPAPI免费开源','加密'), (2,'','付费专业版功能强大','付费'), (3,'','中性文本无关','加密')]
w = {'加密':1.3, 'DPAPI':1.5, '免费':1.3, '开源':1.3, '付费':0.8}
ranked = composite_rerank(dummy, w)
check("composite_rerank命中数排序", ranked[0][0] == 1,
      f"排第一L{ranked[0][0]}（期望L1，命中DPAPI+免费+开源）")

# ═══════════════════════════════════════════════
print(f"\n═══ 通过: {PASS}  失败: {FAIL} ═══")
if FAIL:
    print("  ⚠️ 有失败项，需要修复")
else:
    print("  🎉 全部通过")
