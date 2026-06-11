#!/usr/bin/env python3
"""
NeuroBase 记忆同步脚本 — state.db → memory.db
每 5 分钟由 cron 执行，增量同步新消息。
零依赖 Hermes 之外的工具，纯 Python + SQLite。
"""

import sqlite3
import os
import json
import time

HERMES_DB = os.path.expanduser(r"~\AppData\Local\hermes\state.db")
MEMORY_DB = os.path.expanduser(r"~\.neurobase\memory.db")

def sync():
    if not os.path.exists(HERMES_DB):
        return "state.db not found"

    hermes = sqlite3.connect(HERMES_DB)
    hermes.row_factory = sqlite3.Row
    memory = sqlite3.connect(MEMORY_DB)
    memory.execute('PRAGMA journal_mode=WAL')

    # 读取上次同步到的 message ID
    last_id = memory.execute(
        "SELECT value FROM export_state WHERE key='last_hermes_msg_id'"
    ).fetchone()
    last_id = int(last_id[0]) if last_id else 0

    # 获取新消息
    rows = hermes.execute("""
        SELECT m.id, m.session_id, m.role, m.content, m.tool_calls,
               m.tool_name, m.timestamp, s.source, s.model, s.title
        FROM messages m
        LEFT JOIN sessions s ON m.session_id = s.id
        WHERE m.id > ?
        ORDER BY m.id ASC
    """, (last_id,)).fetchall()

    if not rows:
        hermes.close()
        memory.close()
        return None  # 无新消息

    inserted = 0
    for row in rows:
        content = row['content'] or ''
        # 跳过 compaction 摘要
        if 'CONTEXT COMPACTION' in content:
            continue

        # 插入/更新 session
        sid = row['session_id']
        if sid:
            memory.execute("""
                INSERT OR IGNORE INTO sessions (id, source, model, title, started_at)
                VALUES (?, ?, ?, ?, ?)
            """, (sid, row['source'], row['model'], row['title'], row['timestamp']))

        # 处理 tool_calls
        tc = row['tool_calls']
        if tc:
            try:
                tc = json.dumps(json.loads(tc)) if isinstance(tc, str) else json.dumps(tc)
            except:
                tc = str(tc)

        memory.execute("""
            INSERT OR IGNORE INTO messages
            (id, session_id, role, content, tool_calls, tool_name, timestamp, source, model, session_title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['id'], sid, row['role'], content[:50000],
            tc, row['tool_name'], row['timestamp'],
            row['source'], row['model'], row['title']
        ))
        inserted += 1

    # 更新进度
    max_id = rows[-1]['id']
    memory.execute(
        "INSERT OR REPLACE INTO export_state (key, value) VALUES ('last_hermes_msg_id', ?)",
        (str(max_id),)
    )

    # 更新 session 消息计数
    memory.execute("""
        UPDATE sessions SET message_count = (
            SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id
        )
    """)

    memory.commit()
    hermes.close()
    memory.close()
    return inserted

if __name__ == '__main__':
    count = sync()
    if count is None:
        print("No new messages")
    elif count == 0:
        print("No new messages to sync")
    else:
        print(f"Synced {count} new messages")
