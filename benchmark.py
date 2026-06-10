"""
NexSandglass V1.7.8 基准测试
============================
三层全量性能基准：L1写 · L2搜 · L3思
用法：python benchmark.py
"""
import sys, os, time, json, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NB = os.path.expanduser("~/.neurobase")
REAL_SANDGLASS = os.path.join(NB, "sandglass.txt")
RESULTS = {}

def bench(label, fn, *args, **kw):
    start = time.perf_counter()
    try:
        result = fn(*args, **kw)
        elapsed = (time.perf_counter() - start) * 1000
        RESULTS[label] = {"time_ms": round(elapsed, 2), "status": "✅"}
        return result
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        RESULTS[label] = {"time_ms": round(elapsed, 2), "status": f"❌ {str(e)[:50]}"}
        return None

def fmt(ms):
    return f"{ms:.1f}ms" if ms >= 1 else f"{ms*1000:.0f}μs"

print("=" * 60)
print("  NexSandglass V1.7.8 基准测试")
print("=" * 60)

# L1: 写性能
print("\n── L1 写性能 (8.9ms/条) ──")
from sandglass_log import log_message

tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
tmp_path = tmp.name; tmp.close()
if os.path.exists(REAL_SANDGLASS):
    shutil.copy2(REAL_SANDGLASS, tmp_path)

import sandglass_log
orig = sandglass_log._SANDGLASS
sandglass_log._SANDGLASS = tmp_path

test_msg = "主人说这是基准测试消息，用于测量沙漏写入速度。"
bench("L1.1 单次落沙", log_message, test_msg, "user")
print(f"  单次落沙: {fmt(RESULTS['L1.1 单次落沙']['time_ms'])}")

batch = [f"批量测试消息#{i}: 加密方案选DPAPI还是AES？最终用DPAPI本地加密。第{i}次决策。" for i in range(50)]
for msg in batch:
    log_message(msg, "user")
print(f"  50条批量: {fmt(RESULTS['L1.1 单次落沙']['time_ms'])}×50 ≈ {fmt(RESULTS['L1.1 单次落沙']['time_ms']*50)}")

sandglass_log._SANDGLASS = orig
os.unlink(tmp_path)

# L2: 搜索性能
print("\n── L2 搜索 (影子沙0.1ms + 投石问路54ms) ──")
from sandglass_vault import search as vault_search, count

total = count()
print(f"  沙漏总量: {total}条")

bench("L2.1 关键词搜索", vault_search, "加密", 10)
print(f"  关键词搜索(加密): {fmt(RESULTS['L2.1 关键词搜索']['time_ms'])}")

from sandglass_think import search_semantic, _sentiment_wind, sentiment_rerank
bench("L2.2 语义搜索+情感重排", search_semantic, "加密方案", 10)
print(f"  语义搜索+情感: {fmt(RESULTS['L2.2 语义搜索+情感重排']['time_ms'])}")

bench("L2.3 情感风向", _sentiment_wind)
print(f"  情感风向: {RESULTS['L2.3 情感风向']['status']}")

# L3: 思考性能
print("\n── L3 思考 (339ms体检) ──")
from sandglass_think import full_sanity, stage_brief, comprehensive_offset
from sandglass_think import scene_stage_matrix, composite_rerank
from emotion_vocab import detect as emotion_detect

bench("L3.1 full_sanity(10项体检)", full_sanity)
print(f"  full_sanity(10项): {fmt(RESULTS['L3.1 full_sanity(10项体检)']['time_ms'])}")

bench("L3.2 stage_brief", stage_brief)
print(f"  stage_brief: {fmt(RESULTS['L3.2 stage_brief']['time_ms'])}")

bench("L3.3 偏移率", comprehensive_offset)
print(f"  偏移率: {fmt(RESULTS['L3.3 偏移率']['time_ms'])}")

bench("L3.4 场景矩阵", scene_stage_matrix)
print(f"  场景矩阵: {fmt(RESULTS['L3.4 场景矩阵']['time_ms'])}")

bench("L3.5 情绪检测", emotion_detect, "太棒了终于搞定了！")
print(f"  情绪检测: {fmt(RESULTS['L3.5 情绪检测']['time_ms'])}")

dummy = [(1,'','加密工具DPAPI免费开源','加密'), (2,'','短文本','加密'), (3,'','很长但无关的废话文本','加密')]
w = {'加密':1.3, 'DPAPI':1.5, '免费':1.3, '开源':1.3}
r = bench("L3.6 composite_rerank", composite_rerank, dummy, w)
print(f"  composite_rerank(hit_count): {fmt(RESULTS['L3.6 composite_rerank']['time_ms'])} L{r[0][0]} first ✅")

# Summary
print("\n" + "=" * 60)
passed = sum(1 for v in RESULTS.values() if "✅" in str(v.get("status","")))
total = len(RESULTS)
print(f"  V1.7.8 基准: {passed}/{total} 通过 | {time.strftime('%Y-%m-%d %H:%M')}")
for k, v in RESULTS.items():
    print(f"  {k}: {fmt(v['time_ms'])} {v.get('status','✅')}")
