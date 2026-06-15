# metrics.py — NexSandglass 可观测性埋点 (V2.9.9)
# 追加式写入，零依赖，与 sandglass.txt 落沙哲学一致
import json, os, time
from datetime import datetime
from sandglass_paths import _NB

_METRICS = os.path.join(_NB, 'metrics.jsonl')
_lock = __import__('threading').Lock()

def emit_metric(event: str, **kwargs):
    """追加一条指标到 metrics.jsonl。失败不阻塞主流程。"""
    try:
        entry = {'ts': datetime.now().isoformat(), 'event': event, **kwargs}
        with _lock:
            with open(_METRICS, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

def vocab_hit_rate(hours: int = 24) -> dict:
    """查询词库命中率"""
    if not os.path.exists(_METRICS):
        return {'error': 'no metrics yet'}
    cutoff = (datetime.now() - __import__('datetime').timedelta(hours=hours)).isoformat()
    infer_calls = local_hits = 0
    total_latency = 0
    with open(_METRICS, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                e = json.loads(line)
                if e['ts'] < cutoff: continue
                if e['event'] == 'tag_infer_call':
                    infer_calls += 1
                    total_latency += e.get('latency_ms', 0)
                elif e['event'] == 'tag_result' and e.get('local_hit'):
                    local_hits += 1
            except Exception:
                pass
    total = infer_calls + local_hits
    return {
        'period_hours': hours,
        'infer_calls': infer_calls,
        'local_hits': local_hits,
        'vocab_hit_rate': f'{local_hits/max(1,total)*100:.1f}%',
        'avg_infer_latency_ms': total_latency // max(1, infer_calls)
    }
