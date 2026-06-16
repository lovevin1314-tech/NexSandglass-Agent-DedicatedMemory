"""
NexSandglass 系统心跳 (Heartbeat)
==================================
每10分钟呼吸一次：检查沙漏健康、待办任务、当前环境。
零依赖跨平台：Windows tasklist / Mac ps -ax / Linux ps -aux
"""
import os, json, platform
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
        "health_score": 0,
    }

    # 1. 沙漏健康
    sg = os.path.join(_NB, "sandglass.txt")
    if os.path.exists(sg):
        with open(sg, encoding="utf-8") as f:
            status["sand_count"] = sum(1 for _ in f)
        status["sandglass_ok"] = True
        status["health_score"] += 1

    # 2. 错误标记检查
    errflag = os.path.join(_NB, ".sandglass_error")
    if os.path.exists(errflag):
        with open(errflag) as f:
            status["error_ts"] = f.read().strip()
        status["health_score"] -= 50

    # 3. 待办检查
    task_file = os.path.join(_NB, "persona", "task-log.jsonl")
    if os.path.exists(task_file):
        with open(task_file, encoding="utf-8") as f:
            pending = [l for l in f if '"status":"pending"' in l]
        status["pending_tasks"] = len(pending)

    # 4. 场景检测（跨平台零依赖)
    try:
        system = platform.system()
        if system == "Windows":
            apps = os.popen("tasklist 2>nul").read()
        elif system == "Darwin":
            apps = os.popen("ps -ax 2>/dev/null").read()
        else:
            apps = os.popen("ps -aux 2>/dev/null").read()

        if any(w in apps.lower() for w in ["code.exe", "devenv", "pycharm", "intellij"]):
            status["env"] = "开发"
        elif any(w in apps.lower() for w in ["chrome", "firefox", "safari", "edge"]):
            status["env"] = "浏览"
        else:
            status["env"] = "空闲"
    except Exception:
        status["env"] = "未知"

    # 5. 写心跳日志（超过1MB自动轮转保留最后1000行）
    os.makedirs(os.path.dirname(_HEARTBEAT_LOG), exist_ok=True)
    if os.path.exists(_HEARTBEAT_LOG) and os.path.getsize(_HEARTBEAT_LOG) > 1_000_000:
        with open(_HEARTBEAT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()[-1000:]
        with open(_HEARTBEAT_LOG, "w", encoding="utf-8") as f:
            f.writelines(lines)
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
