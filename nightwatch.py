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

    # ── L0 会话层监控：compaction 告警 ──
    _LAST_COUNT = os.path.join(_VAULT, ".last_sandglass_count")
    current_lines = sum(1 for _ in open(_SANDGLASS, "rb")) if os.path.exists(_SANDGLASS) else 0
    prev_lines = 0
    if os.path.exists(_LAST_COUNT):
        with open(_LAST_COUNT, "r") as f:
            try: prev_lines = int(f.read().strip())
            except: pass
    if prev_lines and current_lines < prev_lines - 10:
        lost = prev_lines - current_lines
        alerts.append(f"🔴 L0 告急！沙漏从 {prev_lines} 条降到 {current_lines} 条（疑似 compaction 吞了 {lost} 条沙子）。L1 沙漏未受影响，但会话层（L0）可能丢失了对话。")
    with open(_LAST_COUNT, "w") as f:
        f.write(str(current_lines))

    # ── 阴影副本：区块链式只读备份 ──
    _SHADOW = os.path.join(_VAULT, "sandglass.backup")
    if os.path.exists(_SANDGLASS):
        if not os.path.exists(_SHADOW):
            # 首次——从主沙漏拷贝
            import shutil
            shutil.copy2(_SANDGLASS, _SHADOW)
            ok.append("✅ 阴影副本已创建（sandglass.backup）")
        else:
            # 比对——主文件被破坏/截断 → 从备份恢复
            master_lines = current_lines
            backup_lines = sum(1 for _ in open(_SHADOW, "rb"))
            if master_lines < backup_lines:
                import shutil
                shutil.copy2(_SHADOW, _SANDGLASS)
                alerts.append(f"🟡 主沙漏被截断（{master_lines}→{backup_lines}行），已从阴影副本恢复")
            elif master_lines == backup_lines:
                ok.append("✅ 阴影副本同步")
            # master_lines > backup_lines → 正常累积，pulse 会同步

    if os.path.exists(_ERROR):
        with open(_ERROR, "r") as f:
            ts = f.read().strip()
        alerts.append(f"🔴 沙漏告急！上次写入失败于 {ts}。需重启 Gateway 或检查磁盘")

    # ── 第1层崩溃恢复：末行损坏检测 ──
    if os.path.exists(_SANDGLASS):
        try:
            with open(_SANDGLASS, "rb") as f:
                # 读最后 256 字节
                f.seek(max(0, os.path.getsize(_SANDGLASS) - 256))
                tail = f.read()
            # 找最后一行
            last_line = tail.split(b"\n")[-1].decode("utf-8", errors="ignore").strip()
            if last_line:
                # 有效行：timestamp | sender | ...
                parts = last_line.split(" | ")
                if len(parts) < 3 or not parts[0][:4].isdigit():
                    # 末行损坏 → 自动切除
                    with open(_SANDGLASS, "rb") as f:
                        all_data = f.read()
                    # 找最后一个完整行
                    clean_end = all_data.rstrip(b"\n").rsplit(b"\n", 1)[0] + b"\n"
                    with open(_SANDGLASS, "wb") as f:
                        f.write(clean_end)
                    alerts.append(f"🟡 沙漏末行损坏（断点写入），守夜人已修复。原行内容：{last_line[:60]}...")
                    ok.append("✅ 沙漏末行已修复")
        except Exception as e:
            alerts.append(f"🔴 沙漏崩溃恢复失败：{e}")

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
