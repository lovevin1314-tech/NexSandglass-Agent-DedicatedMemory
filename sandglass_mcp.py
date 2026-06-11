"""
NexSandglass MCP Server V2.2.0
===============================
标准 MCP 协议——任何 MCP 兼容 Agent 可直接调用。
启动: python sandglass_mcp.py
"""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _rpc_response(id, result):
    return json.dumps({"jsonrpc": "2.0", "id": id, "result": result})


def _rpc_error(id, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}})


def _handle_tool(name, args, request_id):
    try:
        if name == "sandglass_ping":
            from sandglass_vault import count
            from sandglass_think import _current_stage
            return _rpc_response(request_id, {
                "status": "ok", "sands": count(), "stage": _current_stage()
            })

        elif name == "sandglass_search":
            from sandglass_vault import search
            r = search(args.get("query", ""), limit=args.get("limit", 10))
            return _rpc_response(request_id, [
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in r
            ])

        elif name == "sandglass_semantic":
            from sandglass_think import search_semantic
            r = search_semantic(args.get("query", ""), limit=args.get("limit", 5))
            return _rpc_response(request_id, [
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in r
            ])

        elif name == "sandglass_recent":
            from sandglass_vault import recent
            r = recent(args.get("limit", 10))
            return _rpc_response(request_id, [
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in r
            ])

        elif name == "sandglass_offset":
            from sandglass_think import comprehensive_offset
            r = comprehensive_offset()
            return _rpc_response(request_id, r)

        elif name == "sandglass_persona":
            from sandglass_think import _current_stage
            import persona_l3
            p = persona_l3._local_persona_extract()
            return _rpc_response(request_id, {"stage": _current_stage(), "persona": p[:500]})

        elif name == "sandglass_tasks":
            from l3_tasks import task_pending
            return _rpc_response(request_id, task_pending())

        elif name == "sandglass_echo":
            from l3_search_core import _sentiment_wind
            return _rpc_response(request_id, {"wind": _sentiment_wind()})

        elif name == "sandglass_dream":
            from emotion_l3 import entropy_ghost
            r = entropy_ghost(args.get("question", "如果选另一个选项"))
            return _rpc_response(request_id, r)

        else:
            return _rpc_error(request_id, -32601, f"Unknown tool: {name}")

    except Exception as e:
        return _rpc_error(request_id, -32000, str(e))


def main():
    """MCP stdio 主循环"""
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())
            tid = req.get("id", 0)
            method = req.get("method", "")

            if method == "tools/list":
                tools = [
                    {"name": "sandglass_ping", "description": "健康检查——返回沙漏总数和当前阶段"},
                    {"name": "sandglass_search", "description": "关键词搜索记忆"},
                    {"name": "sandglass_semantic", "description": "语义搜索记忆(同义词+SimHash+TF-IDF)"},
                    {"name": "sandglass_recent", "description": "最近N条记忆"},
                    {"name": "sandglass_offset", "description": "当前偏移率(省钱/愿投/放弃)"},
                    {"name": "sandglass_persona", "description": "当前阶段画像"},
                    {"name": "sandglass_tasks", "description": "待办事项列表"},
                    {"name": "sandglass_echo", "description": "当前回音折风向"},
                    {"name": "sandglass_dream", "description": "幽灵决策——'如果选另一个选项会怎样'"},
                ]
                print(_rpc_response(tid, {"tools": tools}), flush=True)

            elif method == "tools/call":
                name = req.get("params", {}).get("name", "")
                args = req.get("params", {}).get("arguments", {})
                print(_handle_tool(name, args, tid), flush=True)

            elif method == "initialize":
                print(_rpc_response(tid, {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "NexSandglass", "version": "2.2.0"}
                }), flush=True)

            else:
                print(_rpc_error(tid, -32601, f"Unknown method: {method}"), flush=True)

        except json.JSONDecodeError:
            print(_rpc_error(0, -32700, "Parse error"), flush=True)
        except Exception as e:
            print(_rpc_error(0, -32000, str(e)), flush=True)


if __name__ == "__main__":
    main()
