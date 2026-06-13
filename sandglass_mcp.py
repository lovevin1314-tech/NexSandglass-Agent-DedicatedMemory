"""
NexSandglass MCP Server V2.6.14
===============================
标准 MCP 协议——任何 MCP 兼容 Agent 可直接调用。
启动: python sandglass_mcp.py
"""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandglass_paths import __version__


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
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt, *_ in r
            ])

        elif name == "sandglass_semantic":
            from sandglass_think import search_semantic
            r = search_semantic(args.get("query", ""), limit=args.get("limit", 5))
            return _rpc_response(request_id, [
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt, *_ in r
            ])

        elif name == "sandglass_recent":
            from sandglass_vault import recent
            r = recent(args.get("limit", 10))
            return _rpc_response(request_id, [
                {"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt, *_ in r
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

        elif name == "sandglass_chart":
            from sandglass_think import entropy_chart
            return _rpc_response(request_id, {"chart": entropy_chart(args.get("n", 10))})

        elif name == "sandglass_migrate":
            from sandglass_think import memory_migrate
            path = memory_migrate(args.get("output", ""))
            return _rpc_response(request_id, {"exported": path})

        elif name == "sandglass_soul_export":
            from soul_diff import export_soul
            path = export_soul(args.get("output", ""))
            return _rpc_response(request_id, {"soul": path})

        elif name == "sandglass_soul_merge":
            from soul_diff import merge_soul
            n = merge_soul(args.get("source", ""))
            return _rpc_response(request_id, {"merged": n})

        elif name == "sandglass_import":
            from sandglass_vault import sandglass_import
            r = sandglass_import(args.get("source_path", ""), args.get("format", "sandglass"))
            return _rpc_response(request_id, r)

        elif name == "sandglass_export":
            from sandglass_vault import sandglass_export
            path = sandglass_export(args.get("output_path"), args.get("limit"), args.get("month", ""))
            return _rpc_response(request_id, {"exported": path})

        elif name == "sandglass_thread":
            from weavethread import wthread_query
            r = wthread_query(args.get("entity"), args.get("relation"), args.get("limit", 20))
            return _rpc_response(request_id, r)

        elif name == "sandglass_thread_graph":
            from weavethread import wthread_graph
            r = wthread_graph(args.get("entity", ""), args.get("depth", 1))
            return _rpc_response(request_id, r)

        elif name == "sandglass_thread_weave":
            from weavethread import wthread_weave
            r = wthread_weave(args.get("limit", 3))
            return _rpc_response(request_id, {"causal_summary": r})

        elif name == "sandglass_thread_add":
            from weavethread import wthread_add
            ok = wthread_add(args.get("subject", "user"), args.get("relation", ""), args.get("object", ""))
            return _rpc_response(request_id, {"added": ok})

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
                    {"name": "sandglass_chart", "description": "情绪熵 ASCII 可视化图表"},
                    {"name": "sandglass_migrate", "description": "一键导出全部记忆数据为 tar.gz"},
                    {"name": "sandglass_soul_export", "description": "导出灵魂差分(偏移率+决策+回音折)"},
                    {"name": "sandglass_soul_merge", "description": "合并外部灵魂差分"},
                    {"name": "sandglass_import", "description": "导入外部沙漏或ChatGPT/Claude对话导出"},
                    {"name": "sandglass_export", "description": "导出沙漏为可迁移文件"},
                    {"name": "sandglass_thread", "description": "查询织线知识图谱——实体关系三元组"},
                    {"name": "sandglass_thread_graph", "description": "织线实体子图——展开N跳关系"},
                    {"name": "sandglass_thread_weave", "description": "织线→织布机桥接——因果链摘要"},
                    {"name": "sandglass_thread_add", "description": "手动补入三元组——Agent发现漏抓时调用"},
                ]
                print(_rpc_response(tid, {"tools": tools}), flush=True)

            elif method == "tools/call":
                name = req.get("params", {}).get("name", "")
                args = req.get("params", {}).get("arguments", {})
                print(_handle_tool(name, args, tid), flush=True)

            elif method == "initialize":
                print(_rpc_response(tid, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "NexSandglass", "version": __version__}
                }), flush=True)

            else:
                print(_rpc_error(tid, -32601, f"Unknown method: {method}"), flush=True)

        except json.JSONDecodeError:
            print(_rpc_error(0, -32700, "Parse error"), flush=True)
        except Exception as e:
            print(_rpc_error(0, -32000, str(e)), flush=True)


if __name__ == "__main__":
    main()
