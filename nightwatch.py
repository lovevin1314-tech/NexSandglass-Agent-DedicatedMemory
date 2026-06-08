"""
NeuroBase 守夜人 — 全系统 V1.0 守护
====================================
会话启动时检查三层健康状态。
用法：在 SOUL.md 或 prefill 中调用 night_watch()。
"""

import os
import sys
from datetime import datetime

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_SANDGLASS = os.path.join(_VAULT, "sandglass.txt")
_IDX = os.path.join(_VAULT, "sandglass.idx")
_ERROR = os.path.join(_VAULT, ".sandglass_error")
_PERSONA = os.path.join(_VAULT, "persona", "persona.md")


def night_watch() -> str:
    """全系统守夜人检查。返回状态报告。如有告急，立即告知主人。"""
    import hashlib
    alerts = []
    ok = []

    # ── 封框完整性（只验存在，不验内容——允许用户定制）──
    _sealed = {
        "sandglass_vault.py": "L2 倒排索引+解密搜索",
        "sandglass_think.py": "L3 灵魂蒸馏+偏移率+织布机",
        "nightwatch.py": "全系统守夜人",
        "pulse.py": "V1.4 三层感知",
        "emotion_vocab.py": "情绪词库",
    }
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for filename, desc in _sealed.items():
        path = os.path.join(script_dir, filename)
        if not os.path.exists(path):
            alerts.append(f"🔴 {filename} 丢失！{desc}")
        else:
            ok.append(f"✅ {filename} 存在（{desc}）")

    # ── 第1层：沙子落盘 ──
    if not os.path.exists(_SANDGLASS):
        alerts.append("🔴 沙漏文件丢失！sandglass.txt 不存在")
    else:
        size = os.path.getsize(_SANDGLASS)
        ok.append(f"✅ 沙漏存在（{size // 1024}KB）")

    if os.path.exists(_ERROR):
        with open(_ERROR, "r") as f:
            ts = f.read().strip()
        alerts.append(f"🔴 沙漏告急！上次写入失败于 {ts}。需重启 Gateway 或检查磁盘")

    # ── 第2层：索引健康 ──
    if not os.path.exists(_IDX):
        alerts.append("🟡 米粒索引缺失，搜索不可用（下次搜索时自动重建）")
    else:
        idx_size = os.path.getsize(_IDX)
        ok.append(f"✅ 米粒索引存在（{idx_size // 1024}KB）")

    # 检查 import
    try:
        from sandglass_vault import count, search
        total = count()
        hits = len(search("test", limit=1))
        ok.append(f"✅ 第二层可用（{total}条沙子，搜索正常）")
    except Exception as e:
        alerts.append(f"🔴 第二层异常：{e}")

    # ── 第3层：画像健康 ──
    if not os.path.exists(_PERSONA):
        alerts.append("🟡 人格画像不存在（首次使用需运行 persona_build()）")
    else:
        ok.append("✅ 人格画像存在")

    try:
        import sandglass_think
        ok.append("✅ 第三层可用")
    except Exception as e:
        alerts.append(f"🔴 第三层异常：{e}")

    # ── 汇总 ──
    lines = [f"## 🛡 守夜人报告 — {datetime.now():%Y-%m-%d %H:%M}", ""]
    lines.extend(ok)
    if alerts:
        lines.append("")
        lines.append("### ⚠️ 告急")
        lines.extend(alerts)
        lines.append("")
        lines.append("> 主人，沙漏记忆系统有问题，需要处理。")

    return "\n".join(lines)
