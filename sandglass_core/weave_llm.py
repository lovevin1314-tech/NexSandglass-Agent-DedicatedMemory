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

# V3.1.0：立体像合成。prompt 极简、四支柱人类可读文本、JSON 失败降级文本。
_SYSTEM_PROMPT_3D = (
    "你是沙漏记忆系统的立体像织布机。只根据给定资料合成，"
    "不编造资料里没有的内容。直接输出三行，不要 JSON，不要解释。"
)
_3D_PROMPT_TEMPLATE = """根据以下资料判断：1) 主人的画像描述 2) 提醒语气（只能选：好奇式|陪伴式|安静式|行动式）3) 一句贴合当前状态的提醒。

资料：
{data}

直接输出三行，不要解释：
第一行：画像描述
第二行：语气
第三行：提醒内容

不要重复资料原文，写新的。"""

# V3.1.0：织线补漏。主体/客体必须来自资料原文，关系必须克制。
_SYSTEM_PROMPT_TRIPLES = (
    "你是沙漏织线补漏器。只从给定原文中提取正则漏掉的关系三元组。"
    "主体和客体必须是原文中出现的文字；没有把握就输出空列表；每行一条：主体-关系-客体，不要 JSON，不要解释。"
)
_TRIPLES_PROMPT_TEMPLATE = """请从下面的原文中，补出尚未列入“已有织线”的关系三元组。

原文：
{data}

已有织线：
{existing}

每行输出一条三元组，格式：主体-关系-客体
主体和客体必须逐字复制原文中的词组，不要改写、不要概括、不要翻译。
没有把握就不输出。
不要解释，不要 JSON。"""

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


def _chat_endpoint(
    config: Dict[str, Any],
    topic: str,
    context: Dict[str, Any],
    system_prompt: str = "",
    prompt_text: str = "",
) -> str:
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
            {"role": "system", "content": system_prompt or _SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text or _prompt(topic, context)},
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


def _chat_gguf(
    config: Dict[str, Any],
    topic: str,
    context: Dict[str, Any],
    system_prompt: str = "",
    prompt_text: str = "",
) -> str:
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
            {"role": "system", "content": system_prompt or _SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text or _prompt(topic, context)},
        ]
        resp = _llama_model.create_chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=int(os.environ.get("NEXSANDBASE_LLM_MAX_TOKENS", "256")),
        )
        return str(resp["choices"][0]["message"]["content"])


def _chat_ollama(
    config: Dict[str, Any],
    topic: str,
    context: Dict[str, Any],
    system_prompt: str = "",
    prompt_text: str = "",
) -> str:
    endpoint = os.environ.get("NEXSANDBASE_LLM_OLLAMA_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    url = endpoint + "/api/chat"
    payload = {
        "model": config.get("model", DEFAULT_MODEL_NAME),
        "messages": [
            {"role": "system", "content": system_prompt or _SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text or _prompt(topic, context)},
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


def _call_model(
    config: Dict[str, Any],
    topic: str,
    context: Dict[str, Any],
    system_prompt: str = "",
    prompt_text: str = "",
) -> str:
    kind = config.get("kind")
    if kind == "endpoint":
        return _chat_endpoint(config, topic, context, system_prompt, prompt_text)
    if kind == "gguf":
        return _chat_gguf(config, topic, context, system_prompt, prompt_text)
    if kind == "ollama":
        return _chat_ollama(config, topic, context, system_prompt, prompt_text)
    raise RuntimeError(f"未知模型后端: {kind}")


_ALLOWED_3D_TONES = {"好奇式", "陪伴式", "安静式", "行动式"}


def _canonical_tone(tone: str, fallback: str = "安静陪伴") -> str:
    """把模型返回的语气归一化到四种允许语气；非法时用传入的本地语气。"""
    if not tone:
        return fallback
    text = str(tone).strip()
    for allowed in _ALLOWED_3D_TONES:
        if allowed in text:
            return allowed
    aliases = {
        "好奇": "好奇式",
        "陪伴": "陪伴式",
        "安静": "安静式",
        "行动": "行动式",
        "数据汇报": "安静式",
        "安静陪伴": "陪伴式",
    }
    for key, value in aliases.items():
        if key in text:
            return value
    return fallback


def _build_3d_prompt(context: Dict[str, Any]) -> str:
    parts: List[str] = []
    persona = str(context.get("persona_type") or "").strip()
    emotional = str(context.get("emotional_state") or "").strip()
    decision = str(context.get("decision_pattern") or "").strip()
    off_dir = str(context.get("offset_direction") or "").strip()
    off_value = context.get("offset_value", 0)
    thread = str(context.get("weave_thread") or "").strip()
    insights = str(context.get("pipe_insights") or "").strip()
    if persona:
        parts.append("画像：" + persona[:120])
    if emotional:
        parts.append("情绪：" + emotional[:120])
    if decision:
        parts.append("决策：" + decision[:160])
    if off_dir:
        parts.append(f"偏移：{off_dir} {off_value:+d}%")
    if thread:
        parts.append("织布机织线：" + thread[:500])
    if insights:
        parts.append("管道洞察：" + insights[:300])
    data = "\n".join(parts) or "（暂无资料）"
    return _3D_PROMPT_TEMPLATE.format(data=data[:3500])


def _clean_line_prefix(text: str) -> str:
    """清理模型输出行首的"第一行：/画像描述：/提醒内容："等标签前缀。"""
    import re as _re
    return _re.sub(
        r"^(第一行|第二行|第三行|画像描述|画像|语气|提醒内容|提醒示例|提醒)[:：、\s]*",
        "", str(text or "").strip(),
    )


def synthesize_3d(
    context: Dict[str, Any],
    *,
    allow_llm: Optional[bool] = None,
    force_llm: bool = False,
) -> Dict[str, Any]:
    """立体像合成：有本地模型时增强画像/提醒语气/提醒示例，否则返回本地聚合字段。

    本函数不写 L0；只有调用方决定是否把返回字段写入 `3d_annotations.jsonl`。
    """
    context = context or {}
    local = {
        "engine": "rule",
        "model": "",
        "persona_type": str(context.get("persona_type") or "").strip(),
        "reminder_tone": str(context.get("reminder_tone") or "").strip(),
        "reminder_example": str(context.get("reminder_example") or "").strip(),
        "fallback_reason": "llm_disabled",
        "latency_ms": 0,
    }
    has_material = any(
        context.get(k)
        for k in ("persona_type", "emotional_state", "decision_pattern", "offset_direction", "weave_thread")
    )
    if not has_material:
        local["fallback_reason"] = "no_material"
        return local

    can_llm = force_llm or (llm_enabled() if allow_llm is None else allow_llm)
    if not can_llm:
        return local

    config = backend_config()
    if not config:
        local["fallback_reason"] = "no_backend"
        return local

    start = time.perf_counter()
    try:
        prompt_text = _build_3d_prompt(context)
        raw_text = _call_model(
            config, "立体像", {}, system_prompt=_SYSTEM_PROMPT_3D, prompt_text=prompt_text
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        raw = _extract_json_object(raw_text)
        if raw is None:
            # V3.1 调优：极简三行输出解析（画像/语气/提醒），JSON 失败时的兜底。
            lines = [ln.strip() for ln in raw_text.strip().splitlines() if ln.strip()]
            raw = {}
            if lines:
                raw["persona_type"] = lines[0]
            if len(lines) > 1:
                raw["reminder_tone"] = lines[1]
            if len(lines) > 2:
                raw["reminder_example"] = lines[2]
        model_name = config.get("model", DEFAULT_MODEL_NAME)
        persona = _clean_line_prefix(raw.get("persona_type") or "")
        tone = _canonical_tone(_clean_line_prefix(raw.get("reminder_tone", "")), local["reminder_tone"])
        example = " ".join(_clean_line_prefix(raw.get("reminder_example") or "").split())
        return {
            "engine": "llm",
            "model": model_name,
            "persona_type": persona or local["persona_type"],
            "reminder_tone": tone,
            "reminder_example": example or local["reminder_example"],
            "fallback_reason": "",
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("synthesize_3d: 模型调用失败，回落本地聚合: %s", exc)
        local["fallback_reason"] = f"{type(exc).__name__}:{str(exc)[:120]}"
        local["latency_ms"] = latency_ms
        return local


_TRIPLE_STOP_ENTITIES = {
    "", "我", "你", "他", "她", "它", "我们", "你们", "他们", "她们", "它们",
    "这个", "那个", "这些", "那些", "现在", "今天", "昨天", "明天", "一个",
    "什么", "怎么", "为什么", "这", "那", "的", "了", "是", "在", "有",
}
_TRIPLE_STOP_RELATIONS = {
    "", "关系", "关联", "是", "有", "属于", "相关", "有关", "相关于",
}


def _normalise_material_rows(materials: Any) -> List[Dict[str, Any]]:
    """把调用方传入的检索结果统一为 [{line_num, text}]。"""
    rows: List[Dict[str, Any]] = []
    for item in materials or []:
        line_num = 0
        text = ""
        if isinstance(item, dict):
            line_num = int(item.get("line_num") or item.get("line") or 0)
            text = str(item.get("text") or item.get("content") or "")
        elif isinstance(item, (tuple, list)):
            if len(item) >= 3:
                line_num = int(item[0] or 0)
                text = str(item[2] or "")
            elif len(item) == 2:
                text = str(item[1] or "")
            elif len(item) == 1:
                text = str(item[0] or "")
        else:
            text = str(item)
        text = text.strip()
        if text:
            rows.append({"line_num": line_num, "text": text})
    return rows


def _entity_in_material(entity: str, material_by_line: Dict[int, str]) -> bool:
    entity = str(entity or "").strip()
    if entity in _TRIPLE_STOP_ENTITIES:
        return False
    if len(entity) < 2:
        return False
    if any(ch.isspace() for ch in entity):
        # 多词英文短语做整体匹配即可；长到不像实体且带空格的先拒掉。
        if len(entity) > 40:
            return False
    return any(entity in text for text in material_by_line.values())


def _relation_suspicious(relation: str) -> bool:
    relation = str(relation or "").strip()
    if relation in _TRIPLE_STOP_RELATIONS:
        return True
    if not relation or len(relation) > 20:
        return True
    if any(ch in relation for ch in ("\n", "\r", "\t")):
        return True
    return False


def _existing_triple_set(existing: Any) -> set:
    seen = set()
    for item in existing or []:
        if isinstance(item, dict):
            key = (
                str(item.get("subject") or "").strip(),
                str(item.get("relation") or item.get("predicate") or "").strip(),
                str(item.get("object") or "").strip(),
            )
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            key = (str(item[0]).strip(), str(item[1]).strip(), str(item[2]).strip())
        else:
            continue
        if key[0] and key[1] and key[2]:
            seen.add(key)
    return seen


def _build_triples_prompt(rows: List[Dict[str, Any]], existing: set) -> str:
    lines = []
    for row in rows:
        ln = row.get("line_num") or 0
        prefix = f"{ln}:" if ln else "?:"
        lines.append(f"{prefix}{row['text'][:220]}")
    data = "\n".join(lines) or "（暂无原文）"
    existing_text = "；".join(f"{s}-{r}-{o}" for s, r, o in sorted(existing)[:30]) or "（无）"
    return _TRIPLES_PROMPT_TEMPLATE.format(data=data[:5000], existing=existing_text[:1200])


def weave_missing_triples(
    materials: Any,
    existing_triples: Any = None,
    *,
    allow_llm: Optional[bool] = None,
    force_llm: bool = False,
) -> Dict[str, Any]:
    """从沙子检索结果中补织缺失关系三元组。

    防幻觉门控：
    - subject/object 必须逐字出现在资料原文中；
    - source_line 必须能定位到同时包含 subject 和 object 的原文行；
    - 重复三元组和可疑关系直接丢弃。
    写入仍走 `weavethread.wthread_add`（L2 织线表），绝不写 L0。
    """
    rows = _normalise_material_rows(materials)
    existing = _existing_triple_set(existing_triples)
    base = {
        "engine": "rule",
        "model": "",
        "triples": [],
        "candidates": 0,
        "added": 0,
        "discarded_hallucination": 0,
        "discarded_invalid": 0,
        "fallback_reason": "llm_disabled",
        "latency_ms": 0,
    }
    if not rows:
        base["fallback_reason"] = "no_material"
        return base

    can_llm = force_llm or (llm_enabled() if allow_llm is None else allow_llm)
    if not can_llm:
        return base

    config = backend_config()
    if not config:
        base["fallback_reason"] = "no_backend"
        return base

    material_by_line = {row["line_num"]: row["text"] for row in rows if row.get("line_num")}
    all_material = material_by_line
    start = time.perf_counter()
    try:
        prompt_text = _build_triples_prompt(rows, existing)
        raw_text = _call_model(
            config, "织线补漏", {}, system_prompt=_SYSTEM_PROMPT_TRIPLES, prompt_text=prompt_text
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        base["latency_ms"] = latency_ms
        raw = _extract_json_object(raw_text)
        if raw is None:
            # V3.1 调优：极简行输出解析（每行：主体-关系-客体），JSON 失败时的兜底。
            lines = [ln.strip() for ln in raw_text.strip().splitlines() if ln.strip()]
            candidates = []
            for ln in lines[:40]:
                ln = ln.lstrip("-•*0123456789.、 ")
                if "-" not in ln:
                    continue
                parts = [p.strip() for p in ln.split("-", 2)]
                if len(parts) >= 2 and parts[0] and parts[2] if len(parts) >= 3 else False:
                    candidates.append({"subject": parts[0], "relation": parts[1], "object": parts[2] if len(parts) > 2 else ""})
            base["fallback_reason"] = "" if candidates else "model_invalid_json"
            if not candidates:
                return base
        else:
            candidates = raw.get("triples") or []
            if not isinstance(candidates, list):
                base["fallback_reason"] = "model_invalid_triples"
                return base

        base["model"] = config.get("model", DEFAULT_MODEL_NAME)
        base["engine"] = "llm"
        base["fallback_reason"] = ""
        added: List[Dict[str, Any]] = []
        added_keys: set = set()
        try:
            from weavethread import wthread_add
        except Exception as exc:
            logger.warning("weave_missing_triples: wthread_add 不可用: %s", exc)
            base["fallback_reason"] = f"wthread_add_unavailable:{type(exc).__name__}"
            base["engine"] = "rule"
            return base

        for item in candidates[:40]:
            base["candidates"] += 1
            if not isinstance(item, dict):
                base["discarded_invalid"] += 1
                continue
            subject = str(item.get("subject") or "").strip()
            relation = str(item.get("relation") or item.get("predicate") or "").strip()
            object_ = str(item.get("object") or "").strip()
            if not subject or not object_ or _relation_suspicious(relation):
                base["discarded_invalid"] += 1
                continue
            if not _entity_in_material(subject, all_material) or not _entity_in_material(object_, all_material):
                base["discarded_hallucination"] += 1
                continue
            key = (subject, relation, object_)
            if key in existing or key in added_keys:
                base["discarded_invalid"] += 1
                continue

            source_line = 0
            try:
                candidate_line = int(item.get("source_line") or item.get("line") or 0)
            except Exception:
                candidate_line = 0
            if candidate_line and candidate_line in material_by_line:
                line_text = material_by_line[candidate_line]
                if subject in line_text and object_ in line_text:
                    source_line = candidate_line
            if not source_line:
                for ln, text in material_by_line.items():
                    if subject in text and object_ in text:
                        source_line = ln
                        break
            if not source_line:
                base["discarded_hallucination"] += 1
                continue

            try:
                wthread_add(subject, relation, object_, source_line)
            except Exception as exc:
                logger.warning("weave_missing_triples: wthread_add 写入失败: %s", exc)
                base["discarded_invalid"] += 1
                continue
            added.append({
                "subject": subject,
                "relation": relation,
                "object": object_,
                "source_line": source_line,
            })
            added_keys.add(key)
            existing.add(key)
        base["triples"] = added
        base["added"] = len(added)
        return base
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("weave_missing_triples: 模型调用失败，回落纯正则: %s", exc)
        base["fallback_reason"] = f"{type(exc).__name__}:{str(exc)[:120]}"
        base["latency_ms"] = latency_ms
        return base


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
    "synthesize_3d",
    "weave_missing_triples",
]
