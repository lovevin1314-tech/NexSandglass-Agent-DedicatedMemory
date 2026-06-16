#!/usr/bin/env python3
"""
NexSandglass L3 — 任务追踪模块
跨会话承诺追踪：task_defer / task_pending / task_done / task_check_trigger

从 sandglass_think.py 提取 (2026-06-11)
原位置: L1520-1585
"""

import os
from sandglass_paths import _NB
import json
import hashlib
from datetime import datetime, timezone

_VAULT = _NB
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_TASK_LOG = os.path.join(_PERSONA_DIR, "task-log.jsonl")


def task_defer(task: str, trigger: str = "", note: str = "") -> dict:
    """记下一个延迟任务。trigger = 触发条件描述，如"沙漏系统完成后"。
    返回 {id, task, trigger, status}"""
    os.makedirs(os.path.dirname(_TASK_LOG), exist_ok=True)
    task_id = hashlib.md5((task + (trigger or "")).encode()).hexdigest()[:8]

    entry = {
        "id": task_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": task,
        "trigger": trigger,
        "note": note,
        "status": "pending",
    }
    with open(_TASK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def task_pending() -> list:
    """列出所有未完成的延迟任务。"""
    if not os.path.exists(_TASK_LOG):
        return []
    tasks = []
    with open(_TASK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                if t.get("status") == "pending":
                    tasks.append(t)
            except Exception:
                continue
    return tasks


def task_done(task_id: str) -> bool:
    """标记任务完成。"""
    if not os.path.exists(_TASK_LOG):
        return False
    lines = []
    found = False
    with open(_TASK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                if t.get("id") == task_id:
                    t["status"] = "done"
                    t["done_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    found = True
                lines.append(json.dumps(t, ensure_ascii=False))
            except Exception:
                lines.append(line.strip())
    if found:
        with open(_TASK_LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return found


def task_check_trigger(keyword: str) -> list:
    """检查是否有任务的触发条件被满足。keyword 匹配 trigger 字段。
    返回匹配到的 pending 任务列表。"""
    pending = task_pending()
    matched = []
    for t in pending:
        trigger = t.get("trigger", "")
        if trigger and keyword.lower() in trigger.lower():
            matched.append(t)
    return matched
