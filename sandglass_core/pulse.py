"""
NexSandglass V2.11.1 — 感知深度
=================================
识别 → 觉察(含情绪感知) → 提醒
三层独立函数 + pulse() 编排。
每次对话前 pulse() 自动选择最深的一层回应。
"""

import os, re, random, logging
from datetime import datetime

logger = logging.getLogger(__name__)

sys_path = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, sys_path)
from sandglass_paths import _NB


# ══════════════════════════════════════════════════════════
# 三层感知 — 独立函数，可独立测试
# ══════════════════════════════════════════════════════════

def _layer1_recognize(user_message: str, signals: list):
    """第一层：识别 — 实时感知身份信号。你说什么，立刻听懂。"""
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
            signals.append(f"{emoji} {category}信号：「{value}」— 已记录")


def _layer2_perceive(user_message: str, signals: list):
    """第二层：觉察 — 情绪感知 + 决策粒子 + 偏移率 + 今昔对比。"""
    # ── 情绪感知 ──
    try:
        from emotion_vocab import detect as emotion_detect, mood_message, learn as emotion_learn
        det = emotion_detect(user_message)
        if det["mood"]:
            msg = mood_message(det)
            if msg:
                signals.append(msg)
            if det["emitter"] == "自我":
                for kw in det["keywords"]:
                    emotion_learn(kw, det["mood"], "zh" if any('\u4e00' <= c <= '\u9fff' for c in kw) else "en")
            echo(user_message)
    except ImportError:
        logger.error("emotion_vocab 导入失败——核心模块损坏，情绪+决策链路中断")
        raise  # 致命——让 pulse() 捕获并返回空

    # ── 决策粒子 ──
    try:
        from decision_particles import log as dp_log, _detect_chain, _is_decision
        if _is_decision(user_message):
            ch = _detect_chain(user_message)
            if ch:
                dp_log(user_message, ch[-1], chain=ch)
    except Exception as e:
        logger.error(f"决策粒子触发失败: {e}")

    # ── 偏移率觉察 ──
    try:
        from sandglass_think import glass_reminder, persona_freshness
        reminder = glass_reminder(user_message)
        if reminder:
            signals.append(reminder)
        fresh = persona_freshness()
        if fresh.get("stale"):
            count = fresh.get("since_sands", 0)
            msg = f"📊 觉察：画像已滞后 {count}条沙子，建议更新。" if count > 0 else "📊 觉察：画像需要更新。"
            signals.append(msg)
    except Exception as e:
        logger.error(f"画像新鲜度检测失败: {e}")

    # ── 对比今昔 ──
    from sandglass_vault import count as sv_count, search
    total = sv_count()
    if total > 50 and user_message and random.random() < 0.10:
        old = search(user_message[:20], limit=3)
        if old and len(old) >= 2:
            _, ts, text = old[-1]
            text = text.strip()[:60]
            if len(text) > 10:
                signals.append(f"📊 觉察：{ts[:10]} 你也说过——「{text}」— 看看今天有什么不同。")


def _layer3_remind(signals: list):
    """第三层：提醒 — 跨会话待办 + 里程碑演化。"""
    from sandglass_vault import count as sv_count

    # ── 待办提醒 ──
    try:
        from sandglass_think import task_pending
        tasks = task_pending()
        if tasks:
            count = len(tasks)
            signals.append(f"📋 待办提醒: {count}项未完成")
            for t in tasks[:3]:
                signals.append(f"  ⏳ {t.get('task', '')[:80]}")
    except Exception as e:
        logger.error(f"待办提醒失败: {e}")

    # ── 里程碑 ──
    try:
        total = sv_count()
        _MILESTONE_FLAG = os.path.join(_NB, f".milestone_{total}")
        if total % 100 == 0 and total > 0 and not os.path.exists(_MILESTONE_FLAG):
            os.makedirs(os.path.dirname(_MILESTONE_FLAG), exist_ok=True)
            with open(_MILESTONE_FLAG, "w") as f: f.write("ok")

            if total == 100:
                try:
                    from sandglass_think import persona_build
                    persona_build()
                    signals.insert(0, "🧬 沙漏满100条——首次灵魂蒸馏，画像已生成")
                except Exception as e:
                    logger.warning(f"里程碑100: {e}")
            elif total == 200:
                try:
                    from sandglass_think import comprehensive_offset
                    comp = comprehensive_offset()
                    d = comp.get("direction", "neutral") if comp.get("sample", 0) >= 2 else "?"
                    signals.insert(0, f"📊 沙漏满200条——偏移率基准建立，影子开始偏向{d}")
                except Exception as e:
                    logger.warning(f"里程碑200: {e}")
            elif total >= 200 and total % 200 == 0:
                try:
                    from sandglass_think import persona_maintain
                    r = persona_maintain()
                    if r.get("triggered"):
                        signals.insert(0, f"🧬 画像自动维护: {r.get('reason','')[:40]}")
                except Exception as e:
                    logger.warning(f"里程碑维护: {e}")
            elif total == 500:
                signals.insert(0, "🌊 沙漏满500条——小波浪开始累积，影子轮廓成形")
            elif total == 1000:
                try:
                    from sandglass_think import _maybe_switch_stage
                    _maybe_switch_stage("neutral")
                    signals.insert(0, "📜 沙漏满1000条——阶段切换系统启用")
                except Exception as e:
                    logger.warning(f"里程碑1000: {e}")
                try:
                    from sandglass_archive import cold_migration
                    r = cold_migration(dry_run=False)
                    if r.get("moved", 0) > 0:
                        signals.insert(0, f"🧊 冷迁移: {r['moved']}条→归档")
                except Exception as e:
                    logger.warning(f"冷迁移: {e}")
            elif total == 1500:
                signals.insert(0, "🔮 沙漏满1500条——接近3D立体合成门槛(2000)")
            elif total >= 2000 and total % 500 == 0:
                try:
                    from sandglass_think import _should_synthesize, _synthesize_3d
                    should, _ = _should_synthesize()
                    if should:
                        _synthesize_3d(force=True, trigger="milestone")
                        signals.insert(0, "🧬 3D立体合成已更新")
                except Exception as e:
                    logger.warning(f"里程碑3D: {e}")
            else:
                signals.insert(0, f"🎉 里程碑：{total}条记忆")
    except Exception as e:
        logger.warning(f"里程碑检测失败: {e}")


# ══════════════════════════════════════════════════════════
# 编排入口 — pulse() 只做编排+格式化，不处理感知逻辑
# ══════════════════════════════════════════════════════════

def pulse(user_message: str = "") -> str:
    """三层感知编排。自动中英切换。V2.11.1: 三层独立函数。"""

    signals = []
    is_cn = any('\u4e00' <= c <= '\u9fff' for c in user_message) if user_message else True

    # ── 第零条消息：欢迎仪式 ──
    _FIRST = os.path.join(_NB, ".first_run")
    if not os.path.exists(_FIRST):
        os.makedirs(os.path.dirname(_FIRST), exist_ok=True)
        with open(_FIRST, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M"))
        return (
            "> 🧵 你好 / Hello\n"
            "> \n"
            "> 📝 明文落沙 / Plaintext sandglass\n"
            "> 🧬 从沙子里捞画像 / Persona from the sand\n"
            "> 📊 偏移率追踪变化 / Drift tracking\n"
            "> 📋 跨会话待办提醒 / Cross-session reminders\n"
            "> \n"
            "> — 说句「我是XXX」/ Say \"I am [name]\"\n"
        )

    if not user_message:
        return ""

    # ── 签契约/改名 ──
    if os.path.exists(_FIRST):
        with open(_FIRST, "r") as f:
            content = f.read()

        name_match = re.search(r"(?:我是|叫我|称呼我)(?!不)(.+?)(?:[，。！\n]|$)", user_message)
        if name_match:
            new_name = name_match.group(1).strip()[:10]
            existing = re.search(r"称呼: (.+)", content)
            if not existing:
                with open(_FIRST, "a") as f:
                    f.write(f"\n称呼: {new_name}")
                return (
                    f"> 🧵 {'小二记住了。以后就叫您' if is_cn else 'Got it. I will call you'}「{new_name}」。\n"
                    f"> \n"
                    f"> {'沙漏里刻下了你的姓名——从今往后，你说的每句话、每次变化、每件待办，我都记着。' if is_cn else 'Your name is carved in the sandglass.'}\n"
                    f"> \n"
                    f"> {'客官请。' if is_cn else 'Ready when you are.'}\n"
                )
            elif existing.group(1) != new_name:
                with open(_FIRST, "a") as f:
                    f.write(f"\n候选称呼: {new_name}")
                return (
                    f"> 🧵 您之前让我叫「{existing.group(1)}」，现在想改成「{new_name}」吗？\n"
                    f"> \n"
                    f"> — 说「对」「好」「是的」来确认。说别的就保持原名。\n"
                )

        candidate = re.search(r"候选称呼: (.+)", content)
        if candidate and re.search(r"^(对|好|是的|可以|确认|行|嗯|OK|yes|ok|yeah)", user_message.strip().lower()):
            existing_name = re.search(r"称呼: (.+)", content)
            old_name = existing_name.group(1) if existing_name else "?"
            new_name = candidate.group(1)
            updated = content.replace(f"候选称呼: {new_name}", f"称呼: {new_name}")
            with open(_FIRST, "w") as f:
                f.write(updated)
            return (
                f"> 🧵 好嘞。以后就叫您「{new_name}」了。\n"
                f"> \n"
                f"> （原名「{old_name}」已封存——沙漏里还是那个你。）\n"
            )

    # ═══ 三层感知 ═══
    _layer1_recognize(user_message, signals)
    try:
        _layer2_perceive(user_message, signals)
    except ImportError:
        return ""
    _layer3_remind(signals)

    # ═══ 情绪协调 + 格式化 ═══
    if signals:
        try:
            from emotion_vocab import detect as _ed
            det = _ed(user_message)
        except ImportError:
            det = {"mood": "", "emitter": "自我", "priority": "低"}
        has_reminder = any("提醒" in s for s in signals)
        priority = det.get("priority", "低")
        emitter = det.get("emitter", "自我")

        if det.get("mood") == "放弃":
            signals = [s for s in signals if not s.startswith("📋")]
            signals.append("📋 提醒：现在最重要的事是改好自己。其他待办先放放。")
        elif priority == "高" and emitter in ("自我", "影响") and has_reminder:
            signals = [s for s in signals if not s.startswith("📋")]
            signals.append("📋 提醒：待办先放放，状态比任务重要。")
        elif priority == "中" and emitter in ("自我", "影响") and has_reminder:
            signals = [s for s in signals if not s.startswith("📋")]
            signals.append("📋 提醒：不急的事可以先缓一缓。")

        header = "> 🧵 小二：" if is_cn else "> 🧵 Keeper:"
        return "\n".join([header] + [f"> {s}" for s in signals])

    return ""


# ══════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════

def echo(user_message: str, assistant_response: str = "") -> None:
    """对话后自动落沙。"""
    try:
        from sandglass_log import log_message
        log_message(user_message, "user")
        if assistant_response:
            log_message(assistant_response, "agent")
    except Exception as e:
        logger.error(f"沙漏落沙失败: {e}")
    _sync_shadow()


def _sync_shadow() -> None:
    """每次消息触发：主沙漏 → 阴影副本增量同步。只追加不替换。"""
    try:
        _VAULT = _NB
        master = os.path.join(_VAULT, "sandglass.txt")
        shadow = os.path.join(_VAULT, "sandglass.backup")
        if not os.path.exists(master):
            return
        with open(master, "rb") as fm:
            master_lines = fm.readlines()
        backup_lines_count = 0
        if os.path.exists(shadow):
            with open(shadow, "rb") as fb:
                backup_lines_count = len(fb.readlines())
        if len(master_lines) > backup_lines_count:
            with open(shadow, "ab") as fb:
                for line in master_lines[backup_lines_count:]:
                    fb.write(line)
    except Exception as e:
        logger.warning(f"影子同步失败: {e}")
