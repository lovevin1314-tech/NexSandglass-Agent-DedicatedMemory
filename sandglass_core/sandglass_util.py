"""Shared stdlib helpers for NexSandglass core modules."""

import json
import logging
import os
import sqlite3
import stat
import tempfile
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write(path: str, payload: str) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = None
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=parent, delete=False
    )
    try:
        with tmp:
            tmp.write(payload)
        if mode is not None:
            os.chmod(tmp.name, mode)
        os.replace(tmp.name, path)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def write_json_atomic(path: str, data, indent=2) -> None:
    _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=indent))


def read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def db_connect(path: str, wal: bool = False, timeout: int = 10,
               check_same_thread: bool = True):
    conn = sqlite3.connect(
        path, timeout=timeout, check_same_thread=check_same_thread
    )
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _pipe_warn(name, e):
    """Local logging stub shared by pipeline modules."""
    logging.getLogger(__name__).warning(f"管道 [{name}] 降级: {e}")


def _fail_open(default):
    """Decorator that logs and returns a default on any exception."""
    logger = logging.getLogger(__name__)

    def deco(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"{func.__name__} failed, returning default: {e}"
                )
                return default

        return wrapper

    return deco
