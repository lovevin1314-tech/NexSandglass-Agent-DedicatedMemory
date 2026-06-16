#!/usr/bin/env python3
"""NexSandglass V2.9.9.1 — 最小冒烟测试 (零依赖)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("NEXSANDBASE_HOME", os.path.join(os.path.expanduser("~"), ".neurobase"))

def test_comprehensive_offset():
    """偏移率返回正确结构"""
    from offset_l3 import comprehensive_offset
    off = comprehensive_offset()
    assert isinstance(off, dict), f"期望dict, 得到{type(off)}"
    assert "direction" in off, "缺少direction"
    assert "offset" in off, "缺少offset"
    assert "sample" in off, "缺少sample"
    print("  ✅ comprehensive_offset")

def test_read_decision_log():
    """决策日志返回list"""
    from offset_l3 import _read_decision_log
    entries = _read_decision_log(20)
    assert isinstance(entries, list), f"期望list, 得到{type(entries)}"
    print(f"  ✅ _read_decision_log ({len(entries)}条)")

def test_emotional_entropy():
    """情绪熵不抛异常"""
    from sandglass_think import _emotional_entropy
    ent = _emotional_entropy()
    assert isinstance(ent, (int, float)), f"期望数字, 得到{type(ent)}"
    print(f"  ✅ _emotional_entropy ({ent})")

def test_full_sanity():
    """全系统冒烟"""
    from sandglass_think import full_sanity
    fs = full_sanity()
    assert fs["passed"] >= 3, f"full_sanity only {fs['passed']}/4"
    print(f"  ✅ full_sanity ({fs['passed']}/4)")

def test_psychology_hint():
    """预判不抛异常"""
    from offset_l3 import psychology_hint
    hint = psychology_hint()
    assert isinstance(hint, str)
    print(f"  ✅ psychology_hint ({hint if hint else '无触发'})")

def test_persona_verify():
    """画像验证不抛异常"""
    from l3_persona_verify import persona_verify
    pv = persona_verify()
    assert isinstance(pv, dict)
    print(f"  ✅ persona_verify ({pv['insight']})")

if __name__ == "__main__":
    print("NexSandglass 冒烟测试")
    tests = [
        test_comprehensive_offset,
        test_read_decision_log,
        test_emotional_entropy,
        test_full_sanity,
        test_psychology_hint,
        test_persona_verify,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} 通过")
