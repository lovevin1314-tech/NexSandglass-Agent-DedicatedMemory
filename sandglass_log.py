"""
NexSandglass 通用落沙 — 任何 Agent 都能用
==========================================
不依赖 Hermes plugin。任何 Python 脚本 import 即可。
V2.4.0: 去掉 DPAPI/base64 加密，明文存储。靠 OS 层全盘加密保护（BitLocker/FileVault/LUKS）。

用法：
  from sandglass_log import log_message
  log_message("用户：今天天气真好")
  log_message("Assistant：明天有雨，记得带伞")
"""

import logging
import os
import re
import time as _time
from datetime import datetime

logger = logging.getLogger(__name__)

# ── AI无意义回复过滤器（V2.1.10修复：长度判断替代^锚定）──
_AI_TRIVIAL = re.compile(
    r'(好的|明白了|没问题|请稍等|我来看看|是的|对的|'
    r'你说得对|当然可以|不用担心|不客气|谢谢|可以|'
    r'好|嗯|OK|ok|嗯嗯|好的呢|没问题呢|知道了|收到)'
)


def _estimate_info_value(text: str) -> float:
    """评估消息信息量。0.0=纯确认词，1.0=高价值。"""
    score = 0.3
    if len(text) > 50:                score += 0.2
    if re.search(r'\d+', text):       score += 0.2
    if re.search(r'[。：；]', text):  score += 0.1
    if any(kw in text for kw in [
        '建议', '需要', '注意', '因为', '方案',
        '步骤', '第一种', '第二种', '推荐',
        '区别', '对比', '优点是', '缺点是',
    ]):                                 score += 0.2
    # 短文本+纯确认词 → 零价值；长文本开头是确认词 → 仍可加分
    stripped = text.strip()
    if _AI_TRIVIAL.match(stripped) and len(stripped) <= 10:
        score = 0.0
    return min(score, 1.0)


from sandglass_paths import _NB

_SANDGLASS = os.path.join(_NB, "sandglass.txt")


def log_message(text: str, sender: str = "agent") -> bool:
    """写入一条消息到沙漏。明文存储——OS层全盘加密保护。
    返回 True 表示写入成功。
    V2.4.0: 去掉DPAPI，落沙提速~2ms，FTS5可直接索引中文。"""
    try:
        # AI低价值回复过滤（V2.1）
        if sender == "agent" and _estimate_info_value(text) < 0.3:
            return False

        os.makedirs(os.path.dirname(_SANDGLASS), exist_ok=True)
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {text}\n"

        # 文件锁——指数退避：3次×5s=15s（V2.4.0修复：超时不裸写，重试+告警）
        lock = _SANDGLASS + ".lock"
        for attempt in range(3):
            deadline = _time.time() + 5
            while _time.time() < deadline:
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    break
                except FileExistsError:
                    _time.sleep(0.01)
            else:
                continue  # 本轮超时，重试
            break  # 获取锁成功
        else:
            # 3次重试全部超时——记录告警但继续写入
            logger.error(f"落沙锁 3 次重试均超时（15s），强制写入（可能并发冲突）")

        try:
            with open(_SANDGLASS, "a", encoding="utf-8") as f:
                f.write(line)
        finally:
            try:
                os.unlink(lock)
            except OSError as e:
                logger.warning(f"锁文件清理失败（可能残留，下次会超时自愈）: {e}")
                try:
                    if os.path.exists(lock):
                        os.remove(lock)
                except Exception as e:
                    logger.warning(f"锁文件二次删除也失败: {e}")

        # 影子沙——落沙后同步索引（传实际行号）
        try:
            from shadow_sand import shadow_index
            shadow_index(text, line_num=0)  # 0=让shadow_sand用trust表自增
        except Exception as e:
            logger.error(f"影子沙索引同步失败: {e}")

        return True
    except Exception as e:
        logger.error(f"沙漏写入失败: {e}")
        return False


def log_conversation(user_msg: str, agent_msg: str) -> int:
    """写入一轮对话（用户+Agent）。返回新写入的行数。"""
    count = 0
    if user_msg:
        if log_message(user_msg, sender="user"): count += 1
    if agent_msg:
        if log_message(agent_msg, sender="agent"): count += 1
    return count
