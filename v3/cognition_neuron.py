"""认知神经元 — jieba分词+posseg+三元组。"""
import sqlite3, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "jieba"))
import jieba, jieba.posseg as pseg
from sandglass_paths import _NB
_DB = os.path.join(_NB, "cognition.db")
_SANDGLASS = os.path.join(_NB, "sandglass.txt")
_SUBJ = {'n','nr','ns','r','eng'}
_OBJ  = {'n','nr','ns','eng'}
def _process(text):
    pos = list(pseg.cut(text))
    tokens = [w.word for w in pos]
    pos_items = [(w.word, w.flag) for w in pos]
    triples = []
    for i, (word, flag) in enumerate(pos_items):
        if flag == 'v':
            subj = None
            for j in range(i-1, -1, -1):
                if pos_items[j][1] in _SUBJ:
                    subj = pos_items[j][0]
                    break
            obj = None
            for j in range(i+1, len(pos_items)):
                if pos_items[j][1] in _OBJ:
                    obj = pos_items[j][0]
                    break
            if subj and obj and subj != obj:
                triples.append((subj, word, obj))
    return {"tokens": tokens, "pos": pos_items, "triples": triples}
def _get_db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS triples (line_num INTEGER, subject TEXT, verb TEXT, object TEXT, PRIMARY KEY(line_num, subject, verb, object))")
    return _conn
_conn = None
_synced_to = 0
def _watermark():
    return _synced_to
def sense():
    from perception_neuron import _file_lines as f_lines
    wm = _watermark()
    total = f_lines()
    if total <= wm:
        return
    from collections import deque
    need = total - wm
    db = _get_db()
    with open(_SANDGLASS, encoding="utf-8") as f:
        lines = deque(f, maxlen=need)
    start = total - len(lines) + 1
    for j, line in enumerate(lines, start):
        text = line.split(" | ", 2)[-1] if " | " in line else line
        r = _process(text)
        for s, v, o in r["triples"]:
            db.execute("INSERT OR IGNORE INTO triples(line_num, subject, verb, object) VALUES(?,?,?,?)", (j, s, v, o))
    db.commit()
    global _synced_to; _synced_to = total
def triples_by_line(line_num):
    rows = _get_db().execute("SELECT subject, verb, object FROM triples WHERE line_num=?", (line_num,)).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]
