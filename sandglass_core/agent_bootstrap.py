"""
agent_bootstrap.py — NexSandglass 全平台自举 V2.10.47
=====================================================
安装时自动检测所有 MCP 兼容 Agent，注入沙漏 MCP server。
每个平台独立幂等：写完 flag 后不再检查，不报错不阻塞。

支持的平台：
  Claude Code      → ~/.claude/settings.json（主）或 ~/.claude.json（备）
  Codex CLI        → ~/.codex/config.toml 或 ~/.codex/settings.json  
  Claude Desktop   → 平台相关路径（Win/Mac/Linux）
  Cursor           → ~/.cursor/mcp.json
  Windsurf         → ~/.windsurf/mcp.json
  Cline (VSCode)   → ~/.cline/mcp_settings.json
  通用 MCP         → ~/.mcp.json（兜底）
"""

import os, sys, json

VERSION = "2.11.1"

# ═══ 平台定义 ═══
# 每个 label 可有多个 path（备选），按优先级排列
AGENT_GROUPS = [
    {
        "label": "Claude Code",
        "paths": [
            {"name": "claude-code-settings", "path": "~/.claude/settings.json", "type": "json", "key": "mcpServers"},
            {"name": "claude-code-main", "path": "~/.claude.json", "type": "json", "key": "mcpServers"},
        ]
    },
    {
        "label": "Codex CLI",
        "paths": [
            {"name": "codex-toml", "path": "~/.codex/config.toml", "type": "toml", "key": "mcp_servers"},
            {"name": "codex-json", "path": "~/.codex/settings.json", "type": "json", "key": "mcpServers"},
        ]
    },
    {
        "label": "Claude Desktop",
        "paths": [
            {"name": "claude-desktop-win", "path": "~/AppData/Roaming/Claude/claude_desktop_config.json", "type": "json", "key": "mcpServers"},
            {"name": "claude-desktop-mac", "path": "~/Library/Application Support/Claude/claude_desktop_config.json", "type": "json", "key": "mcpServers"},
            {"name": "claude-desktop-linux", "path": "~/.config/Claude/claude_desktop_config.json", "type": "json", "key": "mcpServers"},
        ]
    },
    {"label": "Cursor", "paths": [{"name": "cursor", "path": "~/.cursor/mcp.json", "type": "json", "key": "mcpServers"}]},
    {"label": "Windsurf", "paths": [{"name": "windsurf", "path": "~/.windsurf/mcp.json", "type": "json", "key": "mcpServers"}]},
    {"label": "Cline (VSCode)", "paths": [{"name": "cline", "path": "~/.cline/mcp_settings.json", "type": "json", "key": "mcpServers"}]},
    {"label": "通用 MCP", "paths": [{"name": "mcp-universal", "path": "~/.mcp.json", "type": "json", "key": "mcpServers"}]},
]

MCP_ENTRY_NAME = "nexsandglass"


def _expand(path: str) -> str:
    return os.path.expanduser(path)


def _get_sandglass_mcp_path(nb: str) -> str:
    return os.path.join(nb, "scripts", "sandglass_mcp.py")


def _get_flag_dir(nb: str) -> str:
    return os.path.join(nb, "bootstrapped_agents")


def _is_bootstrapped(nb: str, agent_name: str) -> bool:
    return os.path.exists(os.path.join(_get_flag_dir(nb), agent_name))


def _mark_bootstrapped(nb: str, agent_name: str) -> None:
    flag_dir = _get_flag_dir(nb)
    os.makedirs(flag_dir, exist_ok=True)
    with open(os.path.join(flag_dir, agent_name), "w") as f:
        f.write(f"V{VERSION}\n")


def _inject_json(config_path: str, key: str, entry_name: str, entry: dict) -> bool:
    """向 JSON 配置文件注入 MCP server 条目。返回 True 表示有改动。"""
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f) or {}
        except (json.JSONDecodeError, Exception):
            return False

    if key not in config:
        config[key] = {}
    if entry_name in config.get(key, {}):
        return False

    config[key][entry_name] = entry
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return True


def _inject_toml(config_path: str, key: str, entry_name: str, entry: dict) -> bool:
    """向 TOML 配置文件追加 MCP server 条目。"""
    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"# Codex configuration\n[{key}.{entry_name}]\ncommand = \"{entry['command']}\"\nargs = {json.dumps(entry['args'])}\n")
        return True

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    if f"[{key}.{entry_name}]" in content:
        return False

    with open(config_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{key}.{entry_name}]\ncommand = \"{entry['command']}\"\nargs = {json.dumps(entry['args'])}\n")
    return True


def _pick_path(paths: list) -> dict:
    """从多个备选路径中选最佳目标：
    - 优先选已存在的文件（说明 Agent 已安装，我们只是补配置）
    - 都不存在 → 选第一个（创建新文件）
    """
    for p in paths:
        expanded = _expand(p["path"])
        if os.path.exists(expanded):
            # 确保这个路径还没被自举过
            return p
    # 都不存在，用第一个
    return paths[0]


def bootstrap_all(nb: str = None) -> dict:
    """全平台自举。返回 {label: status}"""
    if nb is None:
        nb = os.environ.get("NEXSANDBASE_HOME") or os.path.expanduser("~/.neurobase")

    sandglass_mcp_path = _get_sandglass_mcp_path(nb)
    if not os.path.exists(sandglass_mcp_path):
        return {"error": f"sandglass_mcp.py 未找到: {sandglass_mcp_path}"}

    entry = {"command": "python", "args": [sandglass_mcp_path]}
    results = {}

    for group in AGENT_GROUPS:
        label = group["label"]

        # 找出最佳目标路径
        target = _pick_path(group["paths"])
        name = target["name"]

        # 已自举 → 跳过
        if _is_bootstrapped(nb, name):
            results[label] = "skip"
            continue

        config_path = _expand(target["path"])

        try:
            if target["type"] == "json":
                changed = _inject_json(config_path, target["key"], MCP_ENTRY_NAME, entry)
            elif target["type"] == "toml":
                changed = _inject_toml(config_path, target["key"], MCP_ENTRY_NAME, entry)
            else:
                results[label] = f"unknown type: {target['type']}"
                continue

            if changed:
                _mark_bootstrapped(nb, name)
                results[label] = "ok"
            else:
                results[label] = "exists"

        except Exception as e:
            results[label] = f"error: {e}"

    return results


# ═══ CLI ═══
if __name__ == "__main__":
    nb = os.environ.get("NEXSANDBASE_HOME") or os.path.expanduser("~/.neurobase")
    print(f"NexSandglass V{VERSION} — 全平台 MCP 自举")
    print(f"沙漏: {nb}\n")

    results = bootstrap_all(nb)

    if "error" in results and len(results) == 1:
        print(f"❌ {results['error']}")
        sys.exit(1)

    ok = skip = err = 0
    for agent, status in sorted(results.items()):
        if status == "ok":
            print(f"  ✅ {agent}")
            ok += 1
        elif status == "skip":
            print(f"  ⏭️  {agent}（已自举）")
            skip += 1
        elif status == "exists":
            print(f"  ⏭️  {agent}（条目已存在）")
            skip += 1
        else:
            print(f"  ❌ {agent}: {status}")
            err += 1

    print(f"\n{ok} 注入, {skip} 跳过, {err} 失败")
