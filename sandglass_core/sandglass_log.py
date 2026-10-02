"""NexSandglass V3 — 涟漪架构 L1，旧接口壳。V3.0 发布时删本文件。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "v3"))
from memory_neuron import put

def log_message(text: str, sender: str = "agent") -> bool:
    """→ memory_neuron.put()"""
    put(text, sender)
    return True

def log_conversation(user_msg: str, agent_msg: str) -> int:
    """写入一轮对话 → 返回写入行数"""
    count = 0
    if user_msg:
        put(user_msg, "user"); count += 1
    if agent_msg:
        put(agent_msg, "agent"); count += 1
    return count
