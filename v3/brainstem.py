"""脑干高速路 — 独立于L1/L2/L3。过滤·去重·搜索·守沙人。"""
import sqlite3, os
from sandglass_paths import _NB
import logging
logger = logging.getLogger(__name__)
_PERCEPTION_DB = os.path.join(_NB, "perception.db")
_COGNITION_DB = os.path.join(_NB, "cognition.db")
_SANDGLASS = os.path.join(_NB, "sandglass.txt")

def _get_db(path):
    conn = sqlite3.connect(path)
    return conn

def search(query, min_freq=1):
    """搜索词→行号列表(频率>=min_freq,按时间序)"""
    db = _get_db(_PERCEPTION_DB)
    if min_freq > 1:
        cnt = db.execute("SELECT COUNT(DISTINCT line_num) FROM idx WHERE word=?", (query.lower(),)).fetchone()[0]
        if cnt < min_freq:
            db.close()
            return []
    rows = db.execute(
        "SELECT line_num FROM idx WHERE word=? ORDER BY line_num",
        (query.lower(),)
    ).fetchall()
    db.close()
    return [r[0] for r in rows]

def search_multi(queries, min_freq=3):
    """多词搜索→去重合并+按行号排序→[(行号,命中词列表),...]"""
    all_hits = {}
    for q in queries:
        for ln in search(q, min_freq):
            all_hits.setdefault(ln, []).append(q)
    return sorted(all_hits.items())

def recent(n=10, sender=None):
    """最近N条沙子原文。sender=None=全部, 'user'/'agent'=过滤"""
    if not os.path.exists(_SANDGLASS):
        return []
    from collections import deque
    with open(_SANDGLASS, encoding="utf-8") as f:
        lines = deque(f, maxlen=n * 2 if sender else n)
    results = []
    i = max(1, total() - len(lines) + 1)
    for line in lines:
        parts = line.rstrip("\n").split(" | ", 2)
        if len(parts) >= 3:
            if sender and parts[1] != sender:
                i += 1
                continue
            results.append((i, parts[0], parts[2]))
        i += 1
    if sender:
        results = results[-n:]
    return results

def triples():
    """三元组全量(已去自循环)，按行号排序"""
    db = _get_db(_COGNITION_DB)
    rows = db.execute(
        "SELECT line_num, subject, verb, object FROM triples ORDER BY line_num"
    ).fetchall()
    db.close()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

def total():
    """沙漏总行数"""
    if not os.path.exists(_SANDGLASS):
        return 0
    with open(_SANDGLASS, "rb") as f:
        return sum(1 for _ in f)

def startup_check():
    """脑干守沙人 — 启动时检查L1三神经元+沙漏文件"""
    ok = []
    if not os.path.exists(_SANDGLASS):
        ok.append("sandglass.txt缺失")
    try:
        from memory_neuron import put
        from perception_neuron import search
        from cognition_neuron import triples_by_line
    except Exception as e:
        logger.warning(f"startup_check: 局部导入失败: from memory_neuron import put", exc_info=True)
        ok.append(f"神经元import失败: {e}")
    return len(ok) == 0, ok
