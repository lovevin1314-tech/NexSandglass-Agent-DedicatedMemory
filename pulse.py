"""
NexSandglass V1.4.2 — 感知深度
=================================
识别 → 觉察 → 提醒
每次对话前 pulse() 自动选择最深的一层回应。
"""

import os, re, random
from datetime import datetime

sys_path = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, sys_path)


def pulse(user_message: str = "") -> str:
    """四层感知——逐层深化。"""

    signals = []

    # ── 第零条消息：欢迎仪式 ──
    _FIRST = os.path.join(os.path.expanduser("~"), ".neurobase", ".first_run")
    if not os.path.exists(_FIRST):
        os.makedirs(os.path.dirname(_FIRST), exist_ok=True)
        with open(_FIRST, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M"))
        return (
            "> 🧵 欢迎使用 NexSandglass。从今天起，我是你的记忆管家。\n"
            "> \n"
            "> 🔐 你说的每句话都会加密落沙。\n"
            "> 🧬 我会从沙子里提炼你的画像。你变了我比你先发现。\n"
            "> 📊 你的决策偏移率会实时追踪。\n"
            "> 📋 你说过要做的事，我不会忘。\n"
            "> \n"
            "> — 说句「我是XXX」，我们正式开始。"
        )

    if not user_message:
        return ""

    # ═══════════════════════════════════════════════
    # 第一层：识别（实时感知）──
    # 你说什么，立刻听懂
    # ═══════════════════════════════════════════════

    persona_triggers = [
        (r"我(?:是|叫|就是)(?!不)(.+?)(?:[，。！\n]|$)", "角色", "🧬"),
        (r"我(?:喜欢|偏好|爱|习惯)\s*(.{2,30})", "偏好", "💚"),
        (r"我(?:讨厌|不喜欢|烦|受不了)\s*(.{2,30})", "禁区", "🚫"),
        (r"我(?:在用|装|配)\s*([A-Za-z].{1,20})", "工具", "🔧"),
    ]

    for pattern, category, emoji in persona_triggers:
        m = re.search(pattern, user_message)
        if m:
            value = m.group(1).strip()[:30]
            signals.append(
                f"{emoji} {category}信号：「{value}」— 已记录"
            )

    # ═══════════════════════════════════════════════
    # 第二层：觉察（偏移 + 趋势 + 对比今昔）──
    # ═══════════════════════════════════════════════

    try:
        from sandglass_vault import search, count as sv_count
        from sandglass_think import comprehensive_offset, persona_freshness

        comp = comprehensive_offset()
        if abs(comp["offset"]) >= 40 and comp["sample"] >= 3:
            direction_cn = {"frugal": "省钱优先", "spend": "愿意投入", "drift": "红牌漂移"}.get(
                comp["direction"], comp["direction"]
            )
            signals.append(
                f"📊 觉察：你最近{comp['sample']}次决策偏向「{direction_cn}」（偏移{comp['offset']:+d}%）"
            )

        fresh = persona_freshness()
        if fresh.get("stale") and fresh.get("level", 0) >= 1:
            signals.append(
                f"📊 觉察：画像已滞后 {fresh.get('since_sands', '?')}条沙子，建议更新。"
            )

        # 对比今昔——搜过去相关的话题
        total = sv_count()
        if total > 50 and user_message and random.random() < 0.10:
            old = search(user_message[:20], limit=3)
            if old and len(old) >= 2:
                _, ts, text = old[-1]
                text = text.strip()[:60]
                if len(text) > 10:
                    signals.append(
                        f"📊 觉察：{ts[:10]} 你也说过——「{text}」— 看看今天有什么不同。"
                    )
    except Exception:
        pass

    # ═══════════════════════════════════════════════
    # 第三层：提醒（待办 + 里程碑）──
    # ═══════════════════════════════════════════════

    try:
        from sandglass_vault import count as sv_count
        from sandglass_think import task_pending

        tasks = task_pending()
        if tasks:
            if len(tasks) == 1:
                signals.append(f"📋 提醒：{tasks[0].get('task','')}")
            else:
                signals.append(f"📋 提醒：{len(tasks)}项待办未完成")

        # 里程碑
        total = sv_count()
        if total % 100 == 0 and total > 0:
            signals.insert(0, f"🎉 里程碑：已有 {total} 条记忆。")
    except Exception:
        pass

    if signals:
        return "\n".join(["> 🧵 管家："] + [f"> {s}" for s in signals])

    return ""


def echo(user_message: str, assistant_response: str = "") -> str:
    """对话后自动落沙 + 回响确认。用正则避免子串误报。"""
    triggers = {
        (r"我(?:是|叫|就是)(?!不)(.+?)(?:[，。！\n]|$)", "角色"),
        (r"我(?:喜欢|偏好|爱|习惯)\s*(.{2,30})", "偏好"),
        (r"我(?:讨厌|不喜欢|烦|受不了)\s*(.{2,30})", "禁区"),
        (r"我(?:在用|装|配)\s*([A-Za-z].{1,20})", "工具"),
    }
    caught = []
    for (pattern, category) in triggers:
        if re.search(pattern, user_message):
            caught.append(category)

    if caught:
        try:
            from sandglass_log import log_message
            log_message(user_message, "user")
            if assistant_response:
                log_message(assistant_response, "agent")
        except Exception:
            pass
        return f"> 🧵 已感知：{'、'.join(caught)}信号已捕捉"

    return ""
