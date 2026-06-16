"""
NexSandglass V2.1.1 — 冷热分层存储
热沙(sandglass.txt): 最近30天完整对话
冷沙(archive/): 超过30天，按月分文件，AI低价值丢弃
"""
import os, re, shutil
from sandglass_paths import _NB
from datetime import datetime, timedelta

_VAULT = _NB
_ARCHIVE = os.path.join(_VAULT, "archive")
_HOT_DAYS = 30


def archive_path(month: str) -> str:
    """冷沙文件路径。month='2026-06'。"""
    os.makedirs(_ARCHIVE, exist_ok=True)
    return os.path.join(_ARCHIVE, f"sandglass_{month}.txt")


def parse_ts(line: str) -> str:
    """从沙漏行提取时间戳。"""
    return line[:19] if len(line) >= 19 else ""


def is_old(ts: str, cutoff_days: int = _HOT_DAYS) -> bool:
    """时间戳是否超过cutoff天。"""
    try:
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days > cutoff_days
    except Exception:
        return False


def cold_migration(dry_run: bool = False) -> dict:
    """
    冷迁移：将超过30天的沙子从热沙移到冷沙。
    AI低价值回复在冷沙中丢弃。
    返回 {moved, dropped, kept}。
    """
    hot_file = os.path.join(_VAULT, "sandglass.txt")
    if not os.path.exists(hot_file):
        return {"moved": 0, "dropped": 0, "kept": 0}

    to_keep = []
    moved = 0
    dropped = 0
    kept = 0

    with open(hot_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            ts = parse_ts(line)
            if not is_old(ts):
                to_keep.append(line)
                kept += 1
                continue

            # 超过30天——移入冷沙
            month = ts[:7]  # '2026-06'
            parts = line.split(" | ", 2)
            sender = parts[1] if len(parts) > 1 else "agent"

            # AI低价值回复在冷沙中丢弃
            if sender == "agent":
                text = parts[2] if len(parts) > 2 else ""
                if len(text) < 100 and not re.search(r'\d{3,}|建议|方案|步骤|注意|因为|所以', text):
                    dropped += 1
                    continue

            if not dry_run:
                with open(archive_path(month), "a", encoding="utf-8") as af:
                    af.write(line + "\n")
            moved += 1

    if not dry_run and (moved > 0 or dropped > 0):
        # 和落沙用同一把锁——O_CREAT|O_EXCL
        import time as _time
        lock = hot_file + ".lock"
        deadline = _time.time() + 5
        while _time.time() < deadline:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                _time.sleep(0.01)
        else:
            # 锁超时——落沙正在写入，跳过本次迁移，下次再试
            return {"moved": 0, "dropped": 0, "kept": kept}

        try:
            # 重写热沙
            tmp = hot_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for line in to_keep:
                    f.write(line + "\n")
            os.replace(tmp, hot_file)
        finally:
            try:
                os.unlink(lock)
            except OSError:
                pass

        # 重建索引
        try:
            from sandglass_vault import rebuild_index
            rebuild_index()
        except Exception:
            pass

    return {"moved": moved, "dropped": dropped, "kept": kept}


def search_archive(query: str, limit: int = 10) -> list:
    """搜索冷沙。返回 [(line_no, ts, text), ...]"""
    if not os.path.exists(_ARCHIVE):
        return []

    results = []
    for fname in sorted(os.listdir(_ARCHIVE)):
        if not fname.startswith("sandglass_"):
            continue
        fpath = os.path.join(_ARCHIVE, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if query.lower() in line.lower():
                    parts = line.split(" | ", 2)
                    ts = parts[0] if len(parts) > 0 else ""
                    text = parts[2] if len(parts) > 2 else ""
                    results.append((i + 1, ts, text[:300]))
        if len(results) >= limit:
            break

    return results[:limit]


def archive_stats() -> dict:
    """冷沙统计。"""
    if not os.path.exists(_ARCHIVE):
        return {"files": 0, "total_lines": 0}
    files = [f for f in os.listdir(_ARCHIVE) if f.startswith("sandglass_")]
    total = 0
    for f in files:
        with open(os.path.join(_ARCHIVE, f), "r", encoding="utf-8") as fh:
            total += sum(1 for _ in fh)
    return {"files": len(files), "total_lines": total}
