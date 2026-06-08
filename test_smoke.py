"""
NexSandglass Smoke Test — 核心链路验证
========================================
用法：python test_smoke.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_all():
    from sandglass_vault import count, recent, search, timeline
    from sandglass_think import offset_check, comprehensive_offset, cross_stage_offset
    from sandglass_think import weave_insight, search_semantic, task_pending
    import nightwatch

    errors = []

    # L2: 第二层核心功能
    try:
        assert count() > 0, "沙漏为空"
        assert len(recent(3)) == 3
        assert len(search("记忆")) > 0
        assert "2026" in timeline("记忆")
        print("✅ L2 搜索/最近/时间线正常")
    except Exception as e:
        errors.append(f"L2: {e}")

    # L3: 偏移率
    try:
        off = offset_check("免费方案最好")
        assert off["offset"] in [60, -60, 0, -80, 30], f"偏移值异常: {off['offset']}"
        assert "dimensions" in off, "偏移率缺少维度分解"
        print(f"✅ L3 偏移率: {off['offset']:+d} 维度={list(off['dimensions'].keys())}")
    except Exception as e:
        errors.append(f"L3偏移: {e}")

    # L3: 织布机
    try:
        w = weave_insight("记忆")
        assert w["synthesis"], "织布无输出"
        print(f"✅ L3 织布机: {w['synthesis'][:60]}")
    except Exception as e:
        errors.append(f"L3织布: {e}")

    # L3: 语义搜索
    try:
        s = search_semantic("数据")
        assert len(s) > 0
        print(f"✅ L3 语义搜索: {len(s)}条")
    except Exception as e:
        errors.append(f"L3语义: {e}")

    # L3: 待办
    try:
        p = task_pending()
        assert isinstance(p, list)
        print(f"✅ L3 待办: {len(p)}项")
    except Exception as e:
        errors.append(f"L3待办: {e}")

    # 守夜人
    try:
        r = nightwatch.night_watch()
        assert "沙漏" in r
        print("✅ 守夜人正常")
    except Exception as e:
        errors.append(f"守夜人: {e}")

    # 跨阶段
    try:
        c = cross_stage_offset("免费")
        assert "trajectory" in c
        print(f"✅ L3 跨阶段: {len(c['trajectory'])}阶段")
    except Exception as e:
        errors.append(f"L3跨阶段: {e}")

    print()
    if errors:
        print(f"❌ {len(errors)}项失败:")
        for e in errors:
            print(f"   {e}")
        sys.exit(1)
    else:
        print("🎉 NexSandglass 核心链路全部通过")
        sys.exit(0)

if __name__ == "__main__":
    test_all()
