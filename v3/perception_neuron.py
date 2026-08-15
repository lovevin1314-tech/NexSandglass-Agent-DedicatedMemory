"""感知神经元 — Bigram索引,词→行号。sqlite3+re零依赖。"""
import sqlite3, os, re
from sandglass_paths import _NB
_DB = os.path.join(_NB, "perception.db")
_SANDGLASS = os.path.join(_NB, "sandglass.txt")
_CN = re.compile(r'[\u4e00-\u9fff]+')
_EN = re.compile(r'[A-Za-z]{2,}')
_MX = re.compile(r'[A-Za-z0-9_\-]{2,}')
_NUM = re.compile(r'^\d+$')
_LONG = re.compile(r'^[A-Za-z0-9_\-=]{40,}$')
_EN_NORM = {'the','a','an','is','are','was','were','be','been','being',
            'in','on','at','to','for','of','with','by','and','or','but',
            'not','it','he','she','they','we','you','i','me','my','his',
            'her','our','their','this','that','these','those','do','does',
            'did','can','will','would','could','should','may','might','shall',
            'if','so','no','yes','am','has','have','had','all','some','any',
            'each','every','both','few','more','most','other','such','only'}
def _tokenize(text):
    tokens = []
    for m in _EN.finditer(text):
        w = m.group().lower()
        if w not in _EN_NORM:
            tokens.append(w)
    for m in _MX.finditer(text):
        w = m.group().lower()
        if w not in _EN_NORM and w not in tokens and not _LONG.match(w) and not _NUM.match(w) and not w.startswith('-') and not all(c == '_' for c in w):
            tokens.append(w)
    for m in _CN.finditer(text):
        c = m.group()
        for i in range(len(c) - 1):
            tokens.append(c[i:i+2])
    return list(dict.fromkeys(tokens))
def _get_db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS idx (word TEXT NOT NULL, line_num INTEGER NOT NULL, PRIMARY KEY(word, line_num))")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_word ON idx(word)")
    return _conn
_conn = None
_synced_to = 0
def _watermark():
    return _synced_to
def _file_lines():
    if not os.path.exists(_SANDGLASS):
        return 0
    with open(_SANDGLASS, "rb") as f:
        return sum(1 for _ in f)
def sense():
    wm = _watermark()
    total = _file_lines()
    if total <= wm:
        return
    from collections import deque
    need = total - wm
    db = _get_db()
    with open(_SANDGLASS, encoding="utf-8") as f:
        lines = deque(f, maxlen=need)
    start = total - len(lines) + 1
    # 断点1：铁律提取闭环——复用本次已读新行，零额外IO、被动触发
    try:
        from discipline import iron_rule_extract_and_store as _extract_iron_rules
    except Exception:
        _extract_iron_rules = None
    for j, line in enumerate(lines, start):
        parts = line.split(" | ", 2)
        text = parts[-1] if len(parts) == 3 else line
        for token in _tokenize(text):
            db.execute("INSERT OR IGNORE INTO idx(word, line_num) VALUES(?,?)", (token, j))
        if _extract_iron_rules is not None and len(parts) == 3 and parts[1] == "user":
            try:
                _extract_iron_rules(text, j)
            except Exception:
                pass
    db.commit()
    global _synced_to; _synced_to = total
def search(word):
    """Bigram 索引 search(word) → 行号。设计定稿：接收单个 token（调用方负责分词）。"""
    rows = _get_db().execute("SELECT line_num FROM idx WHERE word=? ORDER BY line_num", (word.lower(),)).fetchall()
    return [r[0] for r in rows]
