#!/usr/bin/env python3
"""Hermes → NexSandglass 一键迁移 (零依赖)"""
import os, sys, sqlite3, json

HERMES_DB = os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "state.db")
if not os.path.exists(HERMES_DB):
    # Try Linux/Mac path
    HERMES_DB = os.path.join(os.path.expanduser("~"), ".local", "share", "hermes", "state.db")
if not os.path.exists(HERMES_DB):
    print("❌ 找不到 Hermes state.db")
    sys.exit(1)

# 连接到沙漏
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandglass_log import log_message

db = sqlite3.connect(HERMES_DB)
# 提取所有 user 消息
rows = db.execute("""
    SELECT role, content FROM messages 
    WHERE role='user' AND content IS NOT NULL AND content != ''
    ORDER BY id
""").fetchall()
db.close()

count = 0
for role, content in rows:
    if len(content.strip()) > 2:
        log_message(content.strip(), role)
        count += 1

print(f"✅ 迁移完成: {count} 条用户消息已导入沙漏")
print(f"📂 沙漏位置: {os.environ.get('NEXSANDBASE_HOME', os.path.expanduser('~/.neurobase'))}/sandglass.txt")
