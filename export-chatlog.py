#!/usr/bin/env python3
"""
NeuroBase 对话全量导出脚本
读取 Hermes state.db，将新消息增量追加到 Obsidian vault 的 JSONL 日志中。
每半小时由 cron job 调用一次。

输出目录: ~/.neurobase/chatlog/
格式: 每天一个 JSONL 文件，每行一条消息（含完整 metadata）
"""

import sqlite3
import json
import os
from datetime import datetime, timezone

HERMES_HOME = os.path.expanduser(r"~\AppData\Local\hermes")
VAULT_DIR = os.path.expanduser(r"~\.neurobase\chatlog")
CHECKPOINT_FILE = os.path.join(VAULT_DIR, ".export_checkpoint.json")
DB_PATH = os.path.join(HERMES_HOME, "state.db")

def get_checkpoint():
    """读取上次导出到的 message ID"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_message_id', 0)
    return 0

def save_checkpoint(last_id):
    os.makedirs(VAULT_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({
            'last_message_id': last_id,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }, f)

def export_new_messages():
    if not os.path.exists(DB_PATH):
        print(f"state.db not found at {DB_PATH}")
        return 0

    last_id = get_checkpoint()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取新消息（排除纯 tool 输出，保留 user/assistant/system）
    cursor = conn.execute("""
        SELECT m.id, m.session_id, m.role, m.content, m.tool_name,
               m.tool_calls, m.timestamp, s.source, s.model, s.title
        FROM messages m
        LEFT JOIN sessions s ON m.session_id = s.id
        WHERE m.id > ?
          AND (
            (m.content IS NOT NULL AND m.content != '' AND m.content NOT LIKE '%CONTEXT COMPACTION%')
            OR (m.tool_calls IS NOT NULL AND m.tool_calls != '')
          )
          AND m.role != 'session_meta'
        ORDER BY m.id ASC
    """, (last_id,))

    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return 0

    # 按日期分组写入
    exported = 0
    files_written = set()

    for row in rows:
        ts = row['timestamp']
        if ts:
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
        else:
            date_str = 'unknown'

        filepath = os.path.join(VAULT_DIR, f'{date_str}.jsonl')
        files_written.add(filepath)

        record = {
            'id': row['id'],
            'session_id': row['session_id'],
            'role': row['role'],
            'content': row['content'][:10000],  # 截断超长消息
            'tool_name': row['tool_name'],
            'tool_calls': row['tool_calls'],
            'timestamp': row['timestamp'],
            'source': row['source'],
            'model': row['model'],
            'session_title': row['title'],
        }
        # 序列化 tool_calls（可能是 JSON 字符串或 None）
        if record['tool_calls']:
            try:
                record['tool_calls'] = json.loads(record['tool_calls'])
            except (json.JSONDecodeError, TypeError):
                pass

        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        exported += 1

    # 更新检查点
    max_id = rows[-1]['id']
    save_checkpoint(max_id)
    conn.close()

    return exported

if __name__ == '__main__':
    os.makedirs(VAULT_DIR, exist_ok=True)
    count = export_new_messages()
    if count > 0:
        print(f"Exported {count} new messages to {VAULT_DIR}")
    else:
        print("No new messages to export")
