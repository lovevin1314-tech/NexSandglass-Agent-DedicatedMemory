"""NexSandglass 织布机 — 模型织印象（可插拔，纯本地优先）。

架构红线：
- 本模块绝不读写 L0 原始沙 `sandglass.txt`，只消费 `weave_l3` 传入的检索视图
  以及影子沙/织线（`shadow_sand.db` 的 entities / wthread_triples）。
- 模型不可用、加载失败、返回 JSON 非法、超时等一切异常，均自动回落
  `rule_impression()`，绝不让沙漏崩溃。
- 模型选择优先级：
  1. `NEXSANDBASE_LLM_GGUF` → `llama_cpp` 本地加载 GGUF
  2. `NEXSANDBASE_LLM_ENDPOINT` → OpenAI 兼容本地服务（llama-server/Ollama/LM Studio）
  3. `NEXSANDBASE_LLM_OLLAMA_MODEL` → Ollama 原生 `/api/chat`
  4. 以上都不可用 → `rule_impression()`
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional

from sandglass_paths import _NB

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "qwen2.5-0.5b-instruct"
DEFAULT_GGUF_NAME = "qwen2.5-0.5b-instruct-q4_0.gguf"
_SYSTEM_PROMPT = (
    "你是记忆织布机，根据资料用中文写关于话题的记忆印象。"
)
_JSON_TEMPLATE = """话题：{topic}
资料：
{data}
用 2-4 句中文写关于这个话题的记忆印象，直接写。"""

_model_lock = threading.Lock()
_llama_model = None
_llama_model_key = None


def llm_enabled() -> bool:
    """模型增强总开关。`auto` 表示有后端配置才开启，`0/off` 强制纯规则。"""
    val = os.environ.get("NEXSANDBASE_LLM_ENABLED", "auto").strip().lower()
    if val in {"0", "false", "no", "off", "rule", "never"}:
        return False
    if val in {"1", "true", "yes", "on", "force"}:
        return True
    return backend_config() is not None


def _default_model_paths() -> List[str]:
    paths: List[str] = []
    env_path = os.environ.get("NEXSANDBASE_LLM_GGUF", "").strip()
    if env_path:
        paths.append(os.path.expanduser(env_path))
    model_home = os.environ.get("NEXSANDBASE_MODEL_HOME", "").strip()
    if model_home:
        paths.append(os.path.join(os.path.expanduser(model_home), DEFAULT_GGUF_NAME))
    else:
        paths.append(os.path.join(os.path.expanduser("~"), ".nexsandglass", "models", DEFAULT_GGUF_NAME))
    return paths


def backend_config() -> Optional[Dict[str, Any]]:
    """只探测配置，不做加载/推理。"""
    endpoint = os.environ.get("NEXSANDBASE_LLM_ENDPOINT", "").strip()
    if endpoint:
        return {
            "kind": "endpoint",
            "endpoint": endpoint,
            "model": os.environ.get("NEXSANDBASE_LLM_MODEL", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME,
        }
    for path in _default_model_paths():
        if path and os.path.isfile(path):
            return {"kind": "gguf", "path": path}
    ollama_model = os.environ.get("NEXSANDBASE_LLM_OLLAMA_MODEL", "").strip()
    if ollama_model:
        return {"kind": "ollama", "model": ollama_model}
    return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """从模型返回中稳健地提取首个 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start = text.find("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    # 从每个 `{` 尝试解码，取第一个合法 dict
    for idx in range(start, len(text)):
        if text[idx] != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _normalise_llm_result(topic: str, raw: Any, model: str, latency_ms: int) -> Dict[str, Any]:
    """模型返回的结构化结果归一化。字段缺失时安全兜底，不写回 L0。"""
    if not isinstance(raw, dict):
        return rule_impression(topic, {}, fallback_reason="model_invalid_json")
    entities: List[str] = []
    for item in raw.get("key_entities") or []:
        if isinstance(item, str) and item.strip():
            entities.append(item.strip())
        elif isinstance(item, dict) and item.get("name"):
            entities.append(str(item["name"]).strip())
    relations: List[Dict[str, str]] = []
    for item in raw.get("relations") or []:
        if not isinstance(item, dict):
            continue
        rel = {
            "subject": str(item.get("subject", "")).strip(),
            "relation": str(item.get("relation", item.get("predicate", ""))).strip(),
            "object": str(item.get("object", "")).strip(),
        }
        if rel["subject"] or rel["object"]:
            if not rel["subject"]:
                rel["subject"] = topic
            if not rel["relation"]:
                rel["relation"] = "关联"
            relations.append(rel)
    impression = " ".join(str(raw.get("impression", "")).split())
    if not impression and entities:
        impression = f"关于「{topic}」，浮现出这些记忆节点：" + "、".join(entities)
    if not impression:
        return rule_impression(topic, {}, fallback_reason="model_empty_impression")
    return {
        "engine": "llm",
        "model": model,
        "key_entities": list(dict.fromkeys(entities))[:8],
        "relations": relations[:12],
        "impression": impression,
        "structured": bool(entities or relations),
        "fallback_reason": "",
        "latency_ms": int(latency_ms),
    }


def rule_impression(
    topic: str,
    context: Optional[Dict[str, Any]] = None,
    fallback_reason: str = "",
) -> Dict[str, Any]:
    """纯规则织印象。不依赖模型，也不会写回 L0。"""
    context = context or {}
    relations: List[Dict[str, str]] = []
    for item in context.get("triples") or []:
        if not isinstance(item, dict):
            continue
        rel = {
            "subject": str(item.get("subject", "")).strip(),
            "relation": str(item.get("relation", "")).strip(),
            "object": str(item.get("object", "")).strip(),
        }
        if rel["subject"] and rel["object"]:
            if not rel["relation"]:
                rel["relation"] = "关联"
            relations.append(rel)
        if len(relations) >= 12:
            break
    entities: List[str] = []
    seen_entities = set()
    for rel in relations:
        for name in (rel["subject"], rel["object"]):
            if name and name not in seen_entities:
                seen_entities.add(name)
                entities.append(name)
        if len(entities) >= 8:
            break
    for item in context.get("entities") or []:
        name = item.get("name") if isinstance(item, dict) else str(item)
        name = str(name or "").strip()
        if name and name not in seen_entities:
            seen_entities.add(name)
            entities.append(name)
        if len(entities) >= 8:
            break
    if topic and topic not in seen_entities:
        entities.insert(0, topic)
        entities = entities[:8]
    if not entities:
        entities = [topic]
    sands = context.get("sands") or context.get("search") or []
    n_sand = len(sands) if isinstance(sands, (list, tuple)) else 0
    evo = str(context.get("evolution") or "").strip()
    parts = [f"关于「{topic}」的记忆开始浮现"]
    if entities:
        parts.append("关键节点：" + "、".join(entities[:5]))
    if relations:
        parts.append("已织出的联结：" + "；".join(
            f"{r['subject']}→{r['relation']}→{r['object']}" for r in relations[:4]
        ))
    elif n_sand:
        parts.append(f"沙子里有 {n_sand} 条相关记录，但暂时只留下模糊轮廓")
    if evo:
        parts.append(f"轨迹上有一个变化：{evo[:80]}")
    impression = "。".join(parts) + "。"
    return {
        "engine": "rule",
        "model": "",
        "key_entities": entities,
        "relations": relations,
        "impression": impression,
        "structured": bool(entities or relations),
        "fallback_reason": fallback_reason,
        "latency_ms": 0,
    }


def build_context(topic: str, weave_view: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """从 weave_insight 的检索视图 + 影子沙/织线组装模型输入。"""
    view = weave_view or {}
    context: Dict[str, Any] = {"topic": topic}
    context["persona"] = list(view.get("persona_view") or [])[:5]
    off = view.get("offset_view") or {}
    context["evolution"] = off.get("evolution", "")
    context["sands"] = list(off.get("recent_sands") or [])[:5]
    context["search"] = list(view.get("search_view") or [])[:3]
    context["thread"] = view.get("thread_view", "")

    entities: List[Dict[str, Any]] = []
    try:
        from shadow_sand import shadow_top_entities
        for row in shadow_top_entities(limit=8):
            if row and len(row) >= 2:
                entities.append({"name": str(row[0]), "line_nums": str(row[1])})
    except Exception:
        logger.warning("build_context: shadow_top_entities 不可用", exc_info=True)
    context["entities"] = entities

    triples: List[Dict[str, Any]] = []
    try:
        from weavethread import wthread_query
        rows = wthread_query(entity=topic, limit=16)
        if not rows:
            rows = wthread_query(limit=16)
        for row in rows:
            triples.append({
                "subject": str(row.get("subject", "")),
                "relation": str(row.get("relation", "")),
                "object": str(row.get("object", "")),
            })
    except Exception:
        logger.warning("build_context: wthread_query 不可用", exc_info=True)
    context["triples"] = triples
    return context


def _prompt(topic: str, context: Dict[str, Any]) -> str:
    # 调优 v2（2026-08-16 实测）：必须传人类可读文本，JSON 结构会让 0.5B 输出百科幻觉。
    parts: List[str] = []
    persona = context.get("persona") or []
    if persona:
        parts.append("画像：" + "；".join(str(x).strip()[:80] for x in persona[:3]))
    sands = []
    for item in context.get("sands") or []:
        if isinstance(item, (tuple, list)) and len(item) >= 3:
            sands.append(f"- {str(item[2])[:120]}")
        else:
            sands.append(f"- {str(item)[:160]}")
    if sands:
        parts.append("相关记忆：\n" + "\n".join(sands[:8]))
    triples = context.get("triples") or []
    if triples:
        rels = []
        for t in triples[:6]:
            if isinstance(t, dict):
                rels.append(f"{t.get('subject','')}-{t.get('relation','')}-{t.get('object','')}")
        if rels:
            parts.append("已知联结：" + "；".join(rels))
    evo = str(context.get("evolution") or "").strip()
    if evo:
        parts.append("轨迹变化：" + evo[:100])
    data = "\n".join(parts) or "（暂无相关资料）"
    return _JSON_TEMPLATE.format(topic=topic, data=data[:3500])


def _chat_endpoint(config: Dict[str, Any], topic: str, context: Dict[str, Any]) -> str:
    endpoint = config.get("endpoint", "").rstrip("/")
    if endpoint.endswith("/chat/completions"):
        url = endpoint
    elif endpoint.endswith("/v1"):
        url = endpoint + "/chat/completions"
    else:
        url = endpoint + "/v1/chat/completions"
    payload = {
        "model": config.get("model", DEFAULT_MODEL_NAME),
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(topic, context)},
        ],
        "temperature": 0.2,
        "max_tokens": int(os.environ.get("NEXSANDBASE_LLM_MAX_TOKENS", "256")),
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = float(os.environ.get("NEXSANDBASE_LLM_TIMEOUT", "30"))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"])


def _chat_gguf(config: Dict[str, Any], topic: str, context: Dict[str, Any]) -> str:
    global _llama_model, _llama_model_key
    try:
        import llama_cpp  # type: ignore
    except Exception as exc:
        raise RuntimeError("llama_cpp 未安装") from exc

    path = os.path.abspath(os.path.expanduser(config.get("path", "")))
    key = (path, int(os.environ.get("NEXSANDBASE_LLM_CTX", "4096")))
    with _model_lock:
        if _llama_model is None or _llama_model_key != key:
            if _llama_model is not None:
                try:
                    _llama_model.close()
                except Exception:
                    pass
            _llama_model = llama_cpp.Llama(
                model_path=path,
                n_ctx=key[1],
                n_threads=int(os.environ.get("NEXSANDBASE_LLM_THREADS", "4")),
                n_gpu_layers=int(os.environ.get("NEXSANDBASE_LLM_GPU_LAYERS", "-1")),
                verbose=False,
            )
            _llama_model_key = key
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(topic, context)},
        ]
        resp = _llama_model.create_chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=int(os.environ.get("NEXSANDBASE_LLM_MAX_TOKENS", "256")),
        )
        return str(resp["choices"][0]["message"]["content"])


def _chat_ollama(config: Dict[str, Any], topic: str, context: Dict[str, Any]) -> str:
    endpoint = os.environ.get("NEXSANDBASE_LLM_OLLAMA_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    url = endpoint + "/api/chat"
    payload = {
        "model": config.get("model", DEFAULT_MODEL_NAME),
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(topic, context)},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = float(os.environ.get("NEXSANDBASE_LLM_TIMEOUT", "30"))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["message"]["content"])


def _call_model(config: Dict[str, Any], topic: str, context: Dict[str, Any]) -> str:
    kind = config.get("kind")
    if kind == "endpoint":
        return _chat_endpoint(config, topic, context)
    if kind == "gguf":
        return _chat_gguf(config, topic, context)
    if kind == "ollama":
        return _chat_ollama(config, topic, context)
    raise RuntimeError(f"未知模型后端: {kind}")


def weave_impression(
    topic: str,
    weave_view: Optional[Dict[str, Any]] = None,
    *,
    allow_llm: Optional[bool] = None,
    force_llm: bool = False,
) -> Dict[str, Any]:
    """织印象入口。

    返回 dict，调用方只把返回值放进 weave_insight 结果，本函数不写任何数据文件。
    `allow_llm=None` 时遵循环境开关；`allow_llm=True` 可让测试显式走模型分支。
    """
    context = build_context(topic, weave_view)
    # V3.0.0 防幻觉：检索视图无资料时模型会编百科（实测），直接回落规则。
    has_material = bool(
        context.get("sands") or context.get("persona")
        or context.get("triples") or context.get("search")
    )
    if not has_material:
        return rule_impression(topic, context, fallback_reason="no_material")
    can_llm = force_llm or (llm_enabled() if allow_llm is None else allow_llm)
    if not can_llm:
        return rule_impression(topic, context, fallback_reason="llm_disabled")

    config = backend_config()
    if not config:
        return rule_impression(topic, context, fallback_reason="no_backend")

    start = time.perf_counter()
    try:
        raw_text = _call_model(config, topic, context)
        latency_ms = int((time.perf_counter() - start) * 1000)
        raw = _extract_json_object(raw_text)
        if raw is None:
            # 调优 v2（2026-08-16 实测）：0.5B 适合直接输出文本印象。
            # JSON 解析失败时把全文当印象，而不是回落规则。
            raw = {"impression": raw_text.strip()}
        result = _normalise_llm_result(topic, raw, config.get("model", DEFAULT_MODEL_NAME), latency_ms)
        result["model"] = config.get("model", DEFAULT_MODEL_NAME)
        result["latency_ms"] = latency_ms
        return result
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("weave_impression: 模型调用失败，回落纯规则: %s", exc)
        fallback = rule_impression(
            topic, context,
            fallback_reason=f"{type(exc).__name__}:{str(exc)[:120]}",
        )
        fallback["latency_ms"] = latency_ms
        return fallback


__all__ = [
    "DEFAULT_MODEL_NAME",
    "DEFAULT_GGUF_NAME",
    "llm_enabled",
    "backend_config",
    "build_context",
    "rule_impression",
    "weave_impression",
]
