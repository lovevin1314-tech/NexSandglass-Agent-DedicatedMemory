"""
NexSandglass V1.7.8 全新安装验证
===============================
模拟第一次安装——零数据起步，验证全链路
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("═" * 50)
print("  NexSandglass V1.7.8 全新安装验证")
print("═" * 50)

# 1. 验证模块可用
checks = []
try:
    from sandglass_log import log_message; checks.append(("L1 落沙", True))
except: checks.append(("L1 落沙", False))

try:
    from sandglass_vault import search, count, rebuild_index
    total = count() if os.path.exists(os.path.expanduser("~/.neurobase/sandglass.txt")) else 0
    checks.append(("L2 投石问路", True, f"{total}条"))
except: checks.append(("L2 投石问路", False))

try:
    from shadow_sand import shadow_search, shadow_index
    # 全新安装影子沙可能不存在，但不影响
    checks.append(("L2 影子沙", True))
except: checks.append(("L2 影子沙", False))

try:
    from sandglass_think import (full_sanity, comprehensive_offset,
                                  _local_persona_extract, _sentiment_wind,
                                  scene_mode)
    fs = full_sanity()
    checks.append(("L3 织布机", True, f"{fs['passed']}/{fs['total']}"))
except: checks.append(("L3 织布机", False))

try:
    from decision_particles import log as dp_log
    dp_log("验证测试", "免费方案")
    checks.append(("L3 决策粒子", True))
except: checks.append(("L3 决策粒子", False))

try:
    from emotion_vocab import detect as emotion_detect
    r = emotion_detect("太棒了终于搞定了")
    checks.append(("L3 情绪检测", True, r.get("mood","?")))
except: checks.append(("L3 情绪检测", False))

try:
    from pulse import pulse
    checks.append(("守夜人", True))
except: checks.append(("守夜人", False))

# 2. LLM上下文合成验证
print("\n📋 模块检查:")
all_ok = True
for name, ok, *detail in checks:
    d = detail[0] if detail else ""
    print(f"  {'✅' if ok else '❌'} {name} {d}")
    if not ok: all_ok = False

# 3. 上下文注入演示
print("\n📤 LLM上下文注入示例:")
try:
    off = comprehensive_offset()
    pt = _local_persona_extract()
    wind = _sentiment_wind()
    mode = scene_mode()
    
    context = f"""
## NexSandglass 认知上下文

**场景感知**: {mode} 模式
**情绪状态**: 回音折风向 {wind:+.2f}
**偏移趋势**: {off['offset']:+d}% ({off['direction']})  
**当前画像**: {pt[:200] if pt else '首次使用，画像待生成'}
**建议**: {'用户倾向省钱方案' if off.get('direction')=='frugal' else '用户注重效率' if off.get('direction')=='spend' else '正常模式'}
"""
    print(context)
    checks.append(("LLM上下文合成", True))
except Exception as e:
    print(f"  ❌ LLM上下文合成失败: {e}")
    all_ok = False

# 4. 总结
print(f"\n{'═' * 50}")
print(f"  {'🎉 全部通过' if all_ok else '⚠️ 存在失败'}")
print(f"═" * 50)
