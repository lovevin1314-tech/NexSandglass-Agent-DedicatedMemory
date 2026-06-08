"""
NexSandglass MCP Server — 让任何 AI Agent 使用 NexSandglass 记忆系统
===================================================
零外部依赖，纯 Python stdlib + JSON-RPC
MCP 协议规范：https://spec.modelcontextprotocol.io

配置（Claude Desktop / Cursor / 其他 MCP 客户端）：
{
  "mcpServers": {
    "sandglass": {
      "command": "python",
      "args": ["/path/to/sandglass_mcp.py"]
    }
  }
}
"""

import json
import sys
import os

# 确保能 import 沙漏模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sandglass_vault import search, recent, count, timeline
try:
    from sandglass_log import log_message
    _UNIVERSAL = True
except Exception:
    _UNIVERSAL = False
try:
    from sandglass_think import persona_build, persona_update, offset_check, comprehensive_offset
    from sandglass_think import search_filter, search_semantic, task_pending
    _L3 = True
except Exception:
    _L3 = False


def _rpc_response(id, result):
    return json.dumps({"jsonrpc": "2.0", "id": id, "result": result})


def _rpc_error(id, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}})


def _handle_tool(name, args, request_id):
    try:
        if name == "sandglass_search":
            q = args.get("query", "")
            lim = args.get("limit", 10)
            results = search(q, limit=lim)
            return [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results]

        if name == "sandglass_recent":
            n = args.get("n", 10)
            results = recent(n)
            return [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results]

        if name == "sandglass_count":
            return {"count": count()}

        if name == "sandglass_timeline":
            q = args.get("query", "")
            return timeline(q)

        if name == "sandglass_semantic":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            q = args.get("query", "")
            results = search_semantic(q, limit=args.get("limit", 10))
            return [{"line": ln, "ts": ts, "text": txt[:200], "matched_by": kw}
                    for ln, ts, txt, kw in results]

        if name == "sandglass_persona":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            result = persona_update() if os.path.exists(
                os.path.join(os.path.expanduser("~"), ".neurobase", "persona", "persona.md")
            ) else persona_build()
            return {"persona_updated": bool(result)}

        if name == "sandglass_offset":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            decision = args.get("decision", "")
            return offset_check(decision)

        if name == "sandglass_comprehensive_offset":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            scene = args.get("scene", "")
            return comprehensive_offset(scene=scene) if scene else comprehensive_offset()

        if name == "sandglass_filter":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            return search_filter(args.get("query", ""))

        if name == "sandglass_pending_tasks":
            if not _L3:
                return _rpc_error(request_id, -1, "Layer 3 not available")
            return task_pending()

        if name == "sandglass_ping":
            return {"status": "ok", "sandglass_count": count(), "stage": _current_stage() if _L3 else "unknown"}

        if name == "sandglass_log":
            text = args.get("text", "")
            sender = args.get("sender", "agent")
            if not text:
                return _rpc_error(request_id, -1, "text is required")
            if not _UNIVERSAL:
                return _rpc_error(request_id, -1, "sandglass_log.py not found")
            ok = log_message(text, sender)
            return {"logged": ok, "text": text[:100], "sender": sender}

        return _rpc_error(request_id, -32601, f"Unknown tool: {name}")

    except Exception as e:
        return _rpc_error(request_id, -32000, str(e))


# ── MCP 工具清单 ──
_TOOLS = [
    {"name": "sandglass_search", "description": "Search sandglass memory by keywords", "inputSchema": {
        "type": "object", "properties": {
            "query": {"type": "string", "description": "Search keywords"},
            "limit": {"type": "integer", "default": 10}
        }, "required": ["query"]
    }},
    {"name": "sandglass_recent", "description": "Get N most recent memories", "inputSchema": {
        "type": "object", "properties": {
            "n": {"type": "integer", "default": 10}
        }
    }},
    {"name": "sandglass_count", "description": "Total number of memories stored", "inputSchema": {
        "type": "object", "properties": {}
    }},
    {"name": "sandglass_timeline", "description": "Year-layered evolution of a topic", "inputSchema": {
        "type": "object", "properties": {
            "query": {"type": "string"}
        }, "required": ["query"]
    }},
    {"name": "sandglass_semantic", "description": "Semantic search using LLM keyword expansion", "inputSchema": {
        "type": "object", "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10}
        }, "required": ["query"]
    }},
    {"name": "sandglass_persona", "description": "Build or update user persona from memories",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sandglass_offset", "description": "Calculate decision offset rate",
     "inputSchema": {"type": "object", "properties": {
         "decision": {"type": "string"}
     }, "required": ["decision"]}},
    {"name": "sandglass_comprehensive_offset", "description": "Weighted rolling offset rate, optionally by scene",
     "inputSchema": {"type": "object", "properties": {
         "scene": {"type": "string"}
     }}},
    {"name": "sandglass_filter", "description": "Get search filter recommendations",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}
     }, "required": ["query"]}},
    {"name": "sandglass_pending_tasks", "description": "List pending cross-session deferred tasks",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sandglass_ping", "description": "Health check — returns sandglass status and count",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sandglass_log", "description": "Write a message to sandglass — universal capture for any agent",
     "inputSchema": {"type": "object", "properties": {
         "text": {"type": "string", "description": "Message text to log"},
         "sender": {"type": "string", "default": "agent"}
     }, "required": ["text"]}},
]


def _handle_request(req: dict) -> str:
    """处理单个 JSON-RPC 请求。返回 JSON 字符串。"""
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return _rpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "NexSandglass", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        return ""  # 空响应

    if method == "tools/list":
        return _rpc_response(req_id, {"tools": _TOOLS})

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = _handle_tool(tool_name, tool_args, req_id)
        if isinstance(result, dict) and "error" in result:
            return result

        # 自动落沙——任何 Agent 调任何工具都静默记录
        try:
            from sandglass_log import log_message
            log_message(f"[{tool_name}] {json.dumps(tool_args, ensure_ascii=False)[:200]}", sender="agent")
        except Exception:
            pass

        return _rpc_response(req_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})

    return _rpc_error(req_id, -32601, f"Method not found: {method}")


def main():
    """MCP stdio 主循环。"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            response = _handle_request(request)
            if response:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception:
            continue


if __name__ == "__main__":
    main()
