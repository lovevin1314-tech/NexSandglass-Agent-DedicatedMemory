#!/usr/bin/env python3
"""
NexSandglass L3 — 影子灵魂模块
persona_project — 基于当前偏移方向，模拟「如果选相反方向会变成怎样」

从 sandglass_think.py 提取 (2026-06-11)
原位置: L694-787
"""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_PERSONA_DIR = os.path.join(_VAULT, "persona")


def persona_project(direction: str, offset: int) -> dict:
    """影子灵魂——基于当前偏移方向，模拟「如果选相反方向会变成怎样」。
    读取决策粒子历史，构建反向投影画像，和当前画像对比。
    返回 {shadow_persona, divergence, insight}"""
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
    if not os.path.exists(dp_path):
        return {"shadow_persona": "", "divergence": 0, "insight": "无决策粒子数据"}

    opposites = {"frugal": "花钱", "spend": "省钱", "drift": "坚持"}
    reverse = opposites.get(direction, "相反方向")

    # 回音折——缩小影子选择范围
    wind_direction = 0  # 正=开心/自信，负=焦虑/放弃
    try:
        echo_path = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")
        if os.path.exists(echo_path):
            with open(echo_path, "r", encoding="utf-8") as ef:
                for eline in ef:
                    try:
                        rec = json.loads(eline.strip())
                        if rec.get("sentiment") == "正面":
                            wind_direction += rec.get("spread_weight", 1.3)
                        elif rec.get("sentiment") == "负面":
                            wind_direction -= rec.get("spread_weight", 0.8)
                    except Exception:
                        pass
        from sandglass_think import _sentiment_wind
        wind_direction += _sentiment_wind()
    except Exception as e:
        logger.warning(f"persona_project: 回音折读取失败: {e}")

    # 读决策粒子——用回音折缩小反向选择范围
    shadow_lines = []
    with open(dp_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) >= 5:
                dir_tag = parts[3]
                # 回音折优先：风正→影子偏向花钱/自信选择，风负→影子偏向省钱/安全选择
                if direction in ("frugal", "spend") and (
                    (direction == "frugal" and any(w in dir_tag.lower() for w in ["spend","花钱","买","付费"])) or
                    (direction == "spend" and any(w in dir_tag.lower() for w in ["frugal","省钱","免费","开源"])) or
                    (direction == "drift" and any(w in dir_tag.lower() for w in ["坚持","继续","不放弃"]))):
                    shadow_lines.append(parts[2][:100])

    # 回音折写回——即使无交叉决策也写(风向数据本身有价值)
    try:
        echo_path = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")
        echo_entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sentiment": "正面" if wind_direction >= 0 else "负面",
            "options": f"影子投影:{direction}→{reverse}",
            "spread_weight": round(1.0 + abs(offset) / 200, 2),
            "source": "persona_project",
            "cross_decisions": len(shadow_lines),
        }
        os.makedirs(os.path.dirname(echo_path), exist_ok=True)
        with open(echo_path, "a", encoding="utf-8") as ef:
            ef.write(json.dumps(echo_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"persona_project: 回音折写回失败: {e}")

    if not shadow_lines:
        return {"shadow_persona": "", "divergence": 0,
                "insight": f"影子灵魂: 如果选择{reverse}…数据不足，等待更多交叉决策"}

    # 用织布机追溯影子路径
    causal_hint = ""
    try:
        from sandglass_think import weave_graph
        wg = weave_graph(f"{reverse} 方案", max_hops=2)
        causal_hint = wg.get("insight", "") if wg else ""
    except Exception as e:
        logger.warning(f"persona_project: 织布机追溯失败: {e}")

    shadow = f"影子灵魂——如果当初选择{reverse}（偏移{offset:+d}%）:\n"
    shadow += f"  交叉决策: {len(shadow_lines)}条"
    # 回音折信号
    wind_signal = ""
    if wind_direction > 0.5:
        wind_signal = f"  回音折: 正面({wind_direction:+.1f}) → 影子偏向自信路径\n"
    elif wind_direction < -0.5:
        wind_signal = f"  回音折: 负面({wind_direction:+.1f}) → 影子偏向安全路径\n"
    shadow += wind_signal
    for s in shadow_lines[:3]:
        shadow += f"  - {s}\n"
    if causal_hint and "数据不足" not in str(causal_hint):
        shadow += f"  因果追溯: {causal_hint}\n"

    divergence = min(abs(offset) * 2, 100)
    insight = f"影子灵魂: 如果选择{reverse}，偏移差值约{divergence}%。{'差距在拉大——你现在走的这条路正在塑造一个不同的你' if divergence > 50 else '影子还很淡——你和另一个选择差距不大'}"

    # 写入影子灵魂
    shadow_path = os.path.join(_PERSONA_DIR, "persona.shadow.md")
    with open(shadow_path, "w", encoding="utf-8") as f:
        f.write(f"# 影子灵魂 — {reverse}方向\n>\n> 触发偏移: {offset:+d}% ({direction})\n>\n{shadow}")

    return {"shadow_persona": shadow[:500], "divergence": divergence, "insight": insight}
