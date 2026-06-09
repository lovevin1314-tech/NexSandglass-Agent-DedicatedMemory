"""
NexSandglass V1.6.1 基准测试
============================
三层全量性能基准：L1写 · L2搜 · L3思

L1 写入使用临时沙漏副本，不污染真实数据。
用法：python benchmark.py
"""
import sys, os, time, json, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NB = os.path.expanduser("~/.neurobase")
REAL_SANDGLASS = os.path.join(NB, "sandglass.txt")
RESULTS = {}

def bench(label: str, fn, *args, **kw):
    start = time.perf_counter()
    result = fn(*args, **kw)
    elapsed = (time.perf_counter() - start) * 1000
    RESULTS[label] = {"time_ms": round(elapsed, 2), "result": str(result)[:80]}
    return result

def fmt(ms):
    return f"{ms:.1f}ms" if ms >= 1 else f"{ms*1000:.0f}μs"


print("=" * 60)
print("  NexSandglass V1.6.1 基准测试")
print("=" * 60)

# ═══════════════════════════════════════════════
# L1: 写性能（临时沙漏副本，不污染真实数据）
# ═══════════════════════════════════════════════
print("\n── L1 写性能 ──")

from sandglass_log import log_message

# 创建临时沙漏副本
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
tmp_path = tmp.name
tmp.close()

try:
    # 复制真实沙漏（只读，不改原文件）
    if os.path.exists(REAL_SANDGLASS):
        shutil.copy2(REAL_SANDGLASS, tmp_path)
    else:
        # 无沙漏 → 空临时文件
        open(tmp_path, 'w', encoding='utf-8').close()

    # Monkey-patch: 临时重定向 sandglass.txt 到临时文件
    import sandglass_log
    orig_path = sandglass_log._SANDGLASS
    sandglass_log._SANDGLASS = tmp_path

    test_msg = "主人说这是基准测试消息，用于测量沙漏写入速度。决策粒子记录：选Python还是Rust，最终还是用Python。"

    bench("L1_单次落沙", log_message, test_msg, "user")
    print(f"  单次落沙: {fmt(RESULTS['L1_单次落沙']['time_ms'])}")

    start = time.perf_counter()
    for i in range(10):
        log_message(f"基准批量消息 #{i}: 测试数据流 {i*100}", "user")
    RESULTS["L1_批量10条"] = {"time_ms": round((time.perf_counter()-start)*1000, 2)}
    print(f"  批量10条: {fmt(RESULTS['L1_批量10条']['time_ms'])} ({fmt(RESULTS['L1_批量10条']['time_ms']/10)}/条)")

    # 恢复原路径
    sandglass_log._SANDGLASS = orig_path
finally:
    # 清理临时文件
    for f in [tmp_path, tmp_path + ".real_bak"]:
        if os.path.exists(f):
            os.remove(f)


# ═══════════════════════════════════════════════
# L2: 搜索性能（只读，不写）
# ═══════════════════════════════════════════════
print("\n── L2 搜索性能 ──")

from sandglass_vault import search, recent, count as sv_count, timeline
from sandglass_sqlite import search as fts_search

total_sands = bench("L2_总沙数", sv_count)
print(f"  沙漏总量: {total_sands} 条")

bench("L2_FTS5搜索", fts_search, "记忆")
print(f"  FTS5搜索('记忆'): {fmt(RESULTS['L2_FTS5搜索']['time_ms'])}")

bench("L2_精排搜索", search, "记忆", limit=10)
print(f"  idx精排('记忆'): {fmt(RESULTS['L2_精排搜索']['time_ms'])}")

bench("L2_时间轴", timeline, "记忆")
print(f"  时间轴('记忆'): {fmt(RESULTS['L2_时间轴']['time_ms'])}")

bench("L2_最近", recent, 5)
print(f"  最近5条: {fmt(RESULTS['L2_最近']['time_ms'])}")

for q in ["测试", "Python", "决策", "基准"]:
    bench(f"L2_搜索_{q}", search, q, limit=10)
    print(f"  搜索'{q}': {fmt(RESULTS[f'L2_搜索_{q}']['time_ms'])}")


# ═══════════════════════════════════════════════
# L3: 思考性能（纯计算，不写文件）
# ═══════════════════════════════════════════════
print("\n── L3 思考性能 ──")

from sandglass_think import (
    comprehensive_offset, offset_check, persona_freshness,
    weave_insight, search_semantic, task_pending
)
from decision_particles import _detect_chain, _chain_summary, _tag_local, _direction
from emotion_vocab import detect as emotion_detect

bench("L3_偏移率", comprehensive_offset)
print(f"  综合偏移率: {fmt(RESULTS['L3_偏移率']['time_ms'])}")

bench("L3_偏移检查", offset_check, "还是用免费方案吧，性价比高")
print(f"  单次偏移检查: {fmt(RESULTS['L3_偏移检查']['time_ms'])}")

bench("L3_画像新鲜度", persona_freshness)
print(f"  画像新鲜度: {fmt(RESULTS['L3_画像新鲜度']['time_ms'])}")

bench("L3_语义搜索", search_semantic, "记忆")
print(f"  语义搜索: {fmt(RESULTS['L3_语义搜索']['time_ms'])}")

bench("L3_织布机", weave_insight, "偏移率")
print(f"  织布机: {fmt(RESULTS['L3_织布机']['time_ms'])}")

bench("L3_待办", task_pending)
print(f"  待办检查: {fmt(RESULTS['L3_待办']['time_ms'])}")

# 决策粒子（纯内存，不落盘）
chain_test = "先用Python写了个demo，试了试还是不行，最后还是换Rust吧，性能确实好"
bench("L3_决策链条检测", _detect_chain, chain_test)
print(f"  决策链条: {fmt(RESULTS['L3_决策链条检测']['time_ms'])}")

chain = _detect_chain(chain_test)
if chain:
    bench("L3_链条摘要", _chain_summary, chain)
    print(f"  链条摘要: {RESULTS['L3_链条摘要']['result']}")

bench("L3_本地标签", _tag_local, chain_test)
print(f"  本地标签: {RESULTS['L3_本地标签']['result']}")

bench("L3_方向判断", _direction, chain_test)
print(f"  方向判断: {RESULTS['L3_方向判断']['result']}")

bench("L3_情绪感知", emotion_detect, "亲爱的今天我特别开心，系统终于跑通了")
print(f"  情绪感知: {RESULTS['L3_情绪感知']['result']}")


# ═══════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("  基准汇总")
print("=" * 60)

l1_times = [v["time_ms"] for k, v in RESULTS.items() if k.startswith("L1")]
l2_times = [v["time_ms"] for k, v in RESULTS.items() if k.startswith("L2")]
l3_times = [v["time_ms"] for k, v in RESULTS.items() if k.startswith("L3")]

print(f"  L1 写:  {fmt(sum(l1_times)/len(l1_times))} 平均")
print(f"  L2 搜:  {fmt(sum(l2_times)/len(l2_times))} 平均 ({len(l2_times)}项)")
print(f"  L3 思:  {fmt(sum(l3_times)/len(l3_times))} 平均 ({len(l3_times)}项)")
print(f"  数据量:  {total_sands} 条沙子")
print(f"  总耗时:  {fmt(sum(l1_times)+sum(l2_times)+sum(l3_times))}")

# 输出 JSON
benchmark_json = {
    "version": "V1.6.1",
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "data_size": total_sands,
    "summary": {
        "L1_write_avg_ms": round(sum(l1_times)/len(l1_times), 2),
        "L2_search_avg_ms": round(sum(l2_times)/len(l2_times), 2),
        "L3_think_avg_ms": round(sum(l3_times)/len(l3_times), 2),
        "total_ms": round(sum(l1_times)+sum(l2_times)+sum(l3_times), 2),
    },
    "details": {k: {"ms": v["time_ms"]} for k, v in RESULTS.items()}
}

json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "benchmark.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(benchmark_json, f, ensure_ascii=False, indent=2)

print(f"\n  📊 结果已保存: {json_path}")
print("  ✅ 零污染 — 沙漏原数据未改动")
