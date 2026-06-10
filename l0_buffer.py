"""
NexSandglass — L0 短期记忆缓冲区
=================================
记录最近5轮对话，不进入倒排索引（不污染搜索）。
满5轮自动蒸馏最新一轮到L1。

用法:
  from l0_buffer import l0_remember, l0_context
  l0_remember("用户说了一句重要的话")
  context = l0_context()  # 返回最近5轮的上下文
"""
import os, json
from datetime import datetime

L0_PATH = os.path.join(os.path.expanduser("~"), ".neurobase", "l0_buffer.jsonl")
L0_MAX = 5  # 最多保留5轮


def l0_remember(text: str, speaker: str = "user") -> None:
    """记入L0缓冲区。满L0_MAX时蒸馏最旧一条到L1。"""
    entry = {"ts": datetime.now().isoformat(), "speaker": speaker, "text": text[:500]}
    os.makedirs(os.path.dirname(L0_PATH), exist_ok=True)

    with open(L0_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 检查是否满了——满则蒸馏最旧一条到L1
    with open(L0_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if len(lines) > L0_MAX:
        # 蒸馏最旧一条
        oldest = json.loads(lines[0].strip())
        try:
            from sandglass_log import log_message
            log_message(f"[L0-auto] {oldest['speaker']}: {oldest['text'][:300]}", oldest.get("speaker", "user"))
            from decision_particles import log as dp_log
            dp_log(oldest["text"][:100], f"L0_buffer_distill")
        except Exception:
            pass

        # 只保留最近 L0_MAX 条
        with open(L0_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines[-L0_MAX:])


def l0_context() -> str:
    """返回L0缓冲区的上下文（最近5轮）。"""
    if not os.path.exists(L0_PATH):
        return ""
    with open(L0_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()[-L0_MAX:]
    if not lines:
        return ""
    parts = []
    for line in lines:
        try:
            e = json.loads(line.strip())
            parts.append(f"[{e.get('speaker','?')}] {e.get('text','')[:200]}")
        except Exception:
            pass
    return "## L0 短期记忆\n" + "\n".join(parts)


def l0_size() -> int:
    """L0当前条数。"""
    if not os.path.exists(L0_PATH):
        return 0
    with open(L0_PATH, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)
