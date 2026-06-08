"""
NexSandglass V1.4.2 — 感知深度
=================================
识别 → 觉察(含情绪感知) → 提醒
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
    # 第二层：觉察（偏移 + 趋势 + 情绪感知 + 对比今昔）──
    # ═══════════════════════════════════════════════

    # ── 情绪关键词库（本地识别，中英双语，不调LLM）──
    _EMOTION_SIGNALS = {
        "红牌": ["不管了", "随便", "放弃", "能用就行", "不纠结了", "就这样吧",
                "whatever", "give up", "i don't care", "fine, do what you want"],
        "负面": ["烦死了", "好累", "压力好大", "真受不了", "没意思", "无聊透顶", "失望",
                "我好焦虑", "不想干了", "太难受了", "崩溃",
                "frustrated", "exhausted", "stressed out", "sick of this", "disappointed", "anxious"],
        "困惑": ["不懂", "不明白", "怎么回事", "啥意思", "搞不懂", "奇怪", "不对劲",
                "confused", "don't understand", "what's going on", "doesn't make sense"],
        "积极": ["开心", "太好了", "有意思", "满意", "值得", "期待", "兴奋", "好棒",
                "happy", "great", "excited", "awesome", "love it", "worth it"],
    }

    for mood, keywords in _EMOTION_SIGNALS.items():
        for kw in keywords:
            if kw.lower() in user_message.lower():
                # ── 主语判断：谁的情绪？ ──
                idx = user_message.lower().find(kw.lower())
                context_before = user_message[max(0, idx-30):idx].lower()

                # 判断情绪来源
                if any(w in context_before for w in ["他", "她", "他们", "那个人", "别人",
                                                       "he ", "she ", "they ", "that person",
                                                       "someone", "somebody"]):
                    # 别人的情绪 → 记录但不触发提醒降级
                    emitter = "他人"
                elif any(w in context_before for w in ["他让", "她让", "他们让", "害得",
                                                         "he makes", "she makes", "they make"]):
                    # 别人的情绪影响了我 → 需要关注
                    emitter = "影响"
                else:
                    # 默认是我的情绪
                    emitter = "自我"

                matched = [k for k in keywords if k in user_message][:2]
                if mood == "红牌":
                    signals.append(f"🔴 觉察：红牌信号——「{'、'.join(matched)}」。优先级=自我修正。")
                elif mood == "负面":
                    if emitter == "他人":
                        signals.append(f"🟡 觉察：别人状态不太好——「{'、'.join(matched)}」。不影响你的提醒。")
                    elif emitter == "影响":
                        signals.append(f"🟡 觉察：别人的情绪影响到你了——「{'、'.join(matched)}」。提醒先缓一缓。")
                    else:
                        signals.append(f"🟡 觉察：你看起来状态不太好——「{'、'.join(matched)}」")
                elif mood == "困惑":
                    signals.append(f"🟡 觉察：你好像有点困惑——「{'、'.join(matched)}」")
                elif mood == "积极":
                    if emitter == "他人":
                        signals.append(f"🟢 觉察：别人状态不错——「{'、'.join(matched)}」")
                    else:
                        signals.append(f"🟢 觉察：状态不错——「{'、'.join(matched)}」")
                break  # 一个消息只匹配最强的情绪

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
        # ── 觉察情绪 → 评估 → 识别优先级 → 决定提醒策略 ──
        has_redcard = any("红牌" in s for s in signals)
        # 只有"自我"情绪才触发提醒降级，"他人"情绪不影响
        has_self_negative = any("你看起来状态不太好" in s for s in signals)
        has_impact = any("别人的情绪影响到你了" in s for s in signals)
        has_reminder = any("提醒" in s for s in signals)

        if has_redcard:
            signals = [s for s in signals if "提醒" not in s]
            signals.append("📋 提醒：现在最重要的事是改好自己。其他待办先放放。")

        elif (has_self_negative or has_impact) and has_reminder:
            signals = [s for s in signals if "提醒" not in s]
            signals.append("📋 提醒：待办可以先缓一缓，现在的状态最重要。")

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
