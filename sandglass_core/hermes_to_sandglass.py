#!/usr/bin/env python3
"""Hermes + Holographic → NexSandglass 一键迁移 (零依赖)"""
import os, sys, sqlite3, json, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandglass_log import log_message

total = 0

# ═══ 1. Hermes 记忆 ═══
HERMES_PATHS = [
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "state.db"),
    os.path.join(os.path.expanduser("~"), ".local", "share", "hermes", "state.db"),
    os.path.join(os.path.expanduser("~"), ".hermes", "state.db"),
]
for db_path in HERMES_PATHS:
    if os.path.exists(db_path):
        db = sqlite3.connect(db_path)
        rows = db.execute("SELECT role, content FROM messages WHERE role='user' AND content IS NOT NULL AND content != '' ORDER BY id").fetchall()
        db.close()
        for role, content in rows:
            if len(content.strip()) > 2:
                log_message(content.strip(), "user")
                total += 1
        print(f"✅ Hermes: {total} 条")
        break
else:
    print("⚠️ 未找到 Hermes state.db")

# ═══ 2. Holographic 记忆 ═══
HOLO_PATHS = [
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "holographic.db"),
    os.path.join(os.path.expanduser("~"), ".local", "share", "hermes", "holographic.db"),
    os.path.join(os.path.expanduser("~"), ".hermes", "holographic.db"),
] + glob.glob(os.path.join(os.path.expanduser("~"), "**", "holographic*.db"), recursive=True)

for db_path in HOLO_PATHS:
    if os.path.exists(db_path):
        db = sqlite3.connect(db_path)
        try:
            rows = db.execute("SELECT role, content FROM memories WHERE content IS NOT NULL AND content != '' ORDER BY id").fetchall()
        except:
            rows = db.execute("SELECT 'user', text FROM entries WHERE text IS NOT NULL AND text != ''").fetchall()
        db.close()
        holo_count = 0
        for role, content in rows:
            if len(content.strip()) > 2:
                log_message(content.strip(), "user")
                holo_count += 1
        if holo_count:
            total += holo_count
            print(f"✅ Holographic: {holo_count} 条")
        break

print(f"\n🎉 迁移完成: 共 {total} 条记忆")
NB = os.environ.get("NEXSANDBASE_HOME", os.path.join(os.path.expanduser("~"), ".neurobase"))
print(f"📂 沙漏位置: {NB}/sandglass.txt")
