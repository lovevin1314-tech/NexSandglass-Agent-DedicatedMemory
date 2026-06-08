"""
NexSandglass V1.4 — 用户体验层
================================
每一轮对话都是一次小型体验。
用法：prefill 或 pre_llm_call 中调用 pulse()。
"""

import os, re, json
from datetime import datetime

_FIRST_RUN = os.path.join(os.path.expanduser("~"), ".neurobase", ".first_run")


def pulse(user_message: str = "") -> str:
    """织布机心跳——检测关键信号并返回洞察。
    挂在 prefill 或 pre_llm_call 中，每次对话前调用。"""

    signals = []

    # ── 第零条消息：欢迎仪式 ──
    if not os.path.exists(_FIRST_RUN):
        os.makedirs(os.path.dirname(_FIRST_RUN), exist_ok=True)
        with open(_FIRST_RUN, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M"))
        return (
            "> 🧵 欢迎使用 NexSandglass。从今天起，我是你的记忆管家。\n"
            "> \n"
            "> 🔐 你说的每句话都会加密落沙——只有你能打开。\n"
            "> 🧬 我会从沙子里提炼你的画像。你变了我比你先发现。\n"
            "> 📊 你的决策偏移率会实时追踪。大波浪来了我会告诉你。\n"
            "> 📋 你说过要做的事，我不会忘。\n"
            "> \n"
            "> — 说句「我是XXX，我喜欢XXX」，我们正式开始。"
        )

    if not user_message:
        return ""

    # ── 信号1：人格声明（实时感知）──
    persona_triggers = [
        (r"我是(.+?)(?:[，。！\n]|$)", "角色", "🧬"),
        (r"我(?:喜欢|偏好|爱|习惯)\s*(.{2,30})", "偏好", "💚"),
        (r"我(?:讨厌|不喜欢|烦|受不了)\s*(.{2,30})", "禁区", "🚫"),
        (r"我(?:在用|装|配|跑)\s*(.{2,20})", "工具", "🔧"),
    ]

    for pattern, category, emoji in persona_triggers:
        m = re.search(pattern, user_message)
        if m:
            value = m.group(1).strip()[:30]
            signals.append(
                f"{emoji} 已捕捉{category}信号：「{value}」— 下次偏移追踪会参考"
            )

    # ── 信号2：偏移告警 ──
    try:
        from sandglass_think import comprehensive_offset, persona_freshness
        comp = comprehensive_offset()
        if abs(comp["offset"]) >= 40 and comp["sample"] >= 3:
            direction_cn = {"frugal": "省钱优先", "spend": "愿意投入", "drift": "红牌漂移"}.get(
                comp["direction"], comp["direction"]
            )
            signals.append(
                f"📊 管家洞察：你最近{comp['sample']}次决策偏向「{direction_cn}」（偏移{comp['offset']:+d}%）"
            )

        fresh = persona_freshness()
        if fresh.get("stale"):
            signals.append(
                f"📝 画像需要更新— {fresh.get('since_sands', '?')}条新沙子未纳入。说句「更新画像」我来处理。"
            )
    except Exception:
        pass

    # ── 信号3：待办 ──
    try:
        from sandglass_think import task_pending
        tasks = task_pending()
        if tasks and len(tasks) == 1:
            signals.append(f"📋 还有1件事没做完：{tasks[0].get('task','')}")
        elif tasks:
            signals.append(f"📋 {len(tasks)}项待办未完成")
    except Exception:
        pass

    if signals:
        return "\n".join(["> 🧵 织布机："] + [f"> {s}" for s in signals])

    return ""


def echo(user_message: str, assistant_response: str = "") -> str:
    """对话后自动落沙 + 回响确认。"""
    triggers = {"我是": "角色", "我喜欢": "偏好", "我讨厌": "禁区", "我在用": "工具"}
    caught = []
    for keyword, category in triggers.items():
        if keyword in user_message:
            caught.append(f"{category}")

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
