"""
NexSandglass — JSON Replay 回放模式
====================================
接受历史对话JSON，按时间顺序喂给系统
用法: python replay.py my_history.json
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) < 2:
    print("用法: python replay.py <history.json>")
    sys.exit(1)

path = sys.argv[1]
if not os.path.exists(path):
    print(f"文件不存在: {path}")
    sys.exit(1)

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 支持多种格式
if isinstance(data, list):
    messages = data
elif isinstance(data, dict):
    messages = data.get("messages", data.get("conversation", data.get("history", [])))
else:
    print("无法识别的JSON格式，期望数组或{conversation/messages: [...]}")
    sys.exit(1)

from sandglass_log import log_message

count = 0
for msg in messages:
    if isinstance(msg, str):
        log_message(msg, "user")
    elif isinstance(msg, dict):
        text = msg.get("text", msg.get("content", msg.get("message", "")))
        role = msg.get("role", msg.get("speaker", "user"))
        ts = msg.get("timestamp", msg.get("ts", msg.get("time", "")))
        if text:
            log_message(text[:500], role)
    count += 1

print(f"回放完成: {count}条消息灌入沙漏")
