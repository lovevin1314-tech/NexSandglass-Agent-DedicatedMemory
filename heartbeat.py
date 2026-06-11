"""
NexSandglass V2.2 — 系统心跳 (Heartbeat)
=========================================
PROTOTYPE — 不要推，等主人确认后再合并。

每分钟呼吸一次：检查健康、待办、场景变化。
跨平台零依赖：Windows tasklist / Mac ps -ax / Linux ps -aux
"""

import os, json, time, platform
from datetime import datetime

from sandglass_paths import _NB
_HEARTBEAT_LOG = os.path.join(_NB, "heartbeat.log")


def tick() -> dict:
    """一次心跳——检查系统健康并返回状态。"""
    status = {
        "ts": datetime.now().isoformat(),
        "sandglass_ok": False,
        "sand_count": 0,
        "pending_tasks": 0,
        "scene_changed": False,
        "health_score": 0,
    }

    # 1. 沙漏健康
    sg = os.path.join(_NB, "sandglass.txt")
    if os.path.exists(sg):
        with open(sg, encoding="utf-8") as f:
            status["sand_count"] = sum(1 for _ in f)
        status["sandglass_ok"] = True
        status["health_score"] += 1

    # 2. 待办检查
    task_file = os.path.join(_NB, "persona", "task-log.jsonl")
    if os.path.exists(task_file):
        with open(task_file, encoding="utf-8") as f:
            pending = [l for l in f if '"status":"pending"' in l]
        status["pending_tasks"] = len(pending)

    # 3. 场景检测（跨平台零依赖）
    try:
        system = platform.system()
        if system == "Windows":
            apps = os.popen("tasklist 2>nul").read()
        elif system == "Darwin":
            apps = os.popen("ps -ax 2>/dev/null").read()
        else:
            apps = os.popen("ps -aux 2>/dev/null").read()
        
        # 检测当前环境
        if any(w in apps.lower() for w in ["code.exe", "devenv", "pycharm", "intellij"]):
            status["env"] = "开发"
        elif any(w in apps.lower() for w in ["chrome", "firefox", "safari", "edge"]):
            status["env"] = "浏览"
        else:
            status["env"] = "空闲"
    except Exception:
        status["env"] = "未知"

    # 4. 写心跳日志
    os.makedirs(os.path.dirname(_HEARTBEAT_LOG), exist_ok=True)
    with open(_HEARTBEAT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(status, ensure_ascii=False) + "\n")

    return status


def last_tick() -> dict:
    """读取最近一次心跳状态。"""
    if not os.path.exists(_HEARTBEAT_LOG):
        return {}
    with open(_HEARTBEAT_LOG, encoding="utf-8") as f:
        lines = f.readlines()
    if lines:
        return json.loads(lines[-1].strip())
    return {}


def health_summary() -> str:
    """生成一句话健康摘要。"""
    s = last_tick()
    if not s:
        return ""
    pending = s.get("pending_tasks", 0)
    count = s.get("sand_count", 0)
    env = s.get("env", "未知")
    parts = [f"沙漏{count}条"]
    if pending:
        parts.append(f"{pending}项待办")
    if env != "未知":
        parts.append(f"当前环境:{env}")
    return " | ".join(parts)


def demo():
    """演示心跳机制"""
    print("=" * 50)
    print("💓 NexSandglass 系统心跳 — 原型演示")
    print("=" * 50)

    # 模拟3次心跳
    for i in range(3):
        s = tick()
        print(f"\n心跳 {i+1}: {s['ts'][:19]}")
        print(f"  沙漏: {'OK' if s['sandglass_ok'] else '❌'} ({s['sand_count']}条)")
        print(f"  待办: {s['pending_tasks']}项")
        print(f"  环境: {s['env']}")
        time.sleep(0.5)

    print(f"\n健康摘要: {health_summary()}")
    print(f"\n心跳日志: {_HEARTBEAT_LOG}")
    print("=" * 50)


if __name__ == "__main__":
    demo()
