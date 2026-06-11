"""
NexSandglass — 灵魂差分 (Soul Diff)
=====================================
跨设备同步认知状态，不暴露原始数据。
导出：偏移率 + 决策链 + 回音折残留 → .soul-diff 文件
合并：追加写入另一台设备

用法:
  python soul_diff.py export  → 导出到 ~/.neurobase/soul_diff.json
  python soul_diff.py merge <file>  → 从文件合并
"""
import sys, os, json, shutil, logging
from datetime import datetime

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandglass_paths import _NB, __version__

SOUL_DIFF = os.path.join(_NB, "soul_diff.json")


def export_soul(output: str = "") -> str:
    """导出灵魂差分——偏移率+决策链+回音折残留。"""
    path = output or SOUL_DIFF
    soul = {
        "version": __version__,
        "exported_at": datetime.now().isoformat(),
        "drift": {},
        "decisions": [],
        "echo_wind": [],
    }

    # 偏移率
    try:
        from sandglass_think import comprehensive_offset
        off = comprehensive_offset()
        soul["drift"] = {
            "offset": off.get("offset", 0),
            "direction": off.get("direction", "neutral"),
            "trend": off.get("trend", "stable"),
            "sample": off.get("sample", 0),
        }
    except Exception:
        pass

    # 决策粒子（最近50条）
    dp_path = os.path.join(_NB, "decision_particles.txt")
    if os.path.exists(dp_path):
        with open(dp_path, "r", encoding="utf-8") as f:
            soul["decisions"] = f.readlines()[-50:]

    # 回音折残留
    echo_path = os.path.join(_NB, "echo_wind.jsonl")
    if os.path.exists(echo_path):
        with open(echo_path, "r", encoding="utf-8") as f:
            soul["echo_wind"] = f.readlines()[-20:]

    # 影子沙 MBTI
    try:
        from shadow_sand import shadow_mbti
        mbti = shadow_mbti()
        if mbti:
            soul["mbti"] = mbti
    except Exception:
        pass

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(soul, f, ensure_ascii=False, indent=2)

    size = os.path.getsize(path)
    logger.info(f"灵魂导出: {path} ({size}B) | 偏移:{soul['drift']} | 决策:{len(soul['decisions'])}条 | 回音:{len(soul['echo_wind'])}条")
    return path


def merge_soul(filepath: str) -> bool:
    """合并灵魂差分到当前系统——追加写入，不覆盖。"""
    if not os.path.exists(filepath):
        logger.warning(f"合并失败: 文件不存在 {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        soul = json.load(f)

    # 合并决策粒子
    dp_path = os.path.join(_NB, "decision_particles.txt")
    if soul.get("decisions"):
        os.makedirs(os.path.dirname(dp_path), exist_ok=True)
        with open(dp_path, "a", encoding="utf-8") as f:
            f.writelines(soul["decisions"])

    # 合并回音折
    echo_path = os.path.join(_NB, "echo_wind.jsonl")
    if soul.get("echo_wind"):
        os.makedirs(os.path.dirname(echo_path), exist_ok=True)
        with open(echo_path, "a", encoding="utf-8") as f:
            f.writelines(soul["echo_wind"])

    # 合并 MBTI（如果目标为空）
    if soul.get("mbti"):
        try:
            from shadow_sand import shadow_mbti, shadow_mbti_set
            if not shadow_mbti():
                shadow_mbti_set(soul["mbti"])
        except Exception:
            pass

    logger.info(f"灵魂合并完成: +{len(soul.get('decisions',[]))}决策 +{len(soul.get('echo_wind',[]))}回音")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python soul_diff.py export [output_path]")
        print("      python soul_diff.py merge <filepath>")
        sys.exit(1)

    action = sys.argv[1]
    if action == "export":
        export_soul(sys.argv[2] if len(sys.argv) > 2 else "")
    elif action == "merge":
        merge_soul(sys.argv[2])
    else:
        print(f"未知操作: {action}")
