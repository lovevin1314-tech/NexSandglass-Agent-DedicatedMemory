#!/bin/bash
# NexSandglass V1.0 — macOS/Linux 安装脚本
set -e

echo "╔══════════════════════════════════╗"
echo "║  NexSandglass V1.0  安装程序     ║"
echo "╚══════════════════════════════════╝"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 创建目录
mkdir -p "$HOME/.neurobase/scripts"
mkdir -p "$HOME/.neurobase/persona"
echo "✅ 目录已创建"

# 复制脚本
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/vault.py" "$HOME/.neurobase/scripts/sandglass_vault.py"
cp "$SCRIPT_DIR/think.py" "$HOME/.neurobase/scripts/sandglass_think.py"
cp "$SCRIPT_DIR/nightwatch.py" "$HOME/.neurobase/scripts/nightwatch.py"
cp "$SCRIPT_DIR/mcp_server.py" "$HOME/.neurobase/scripts/sandglass_mcp.py"
echo "✅ 脚本已部署"

# .env 模板
if [ ! -f "$HOME/.neurobase/.env" ]; then
    echo "# 可选：DeepSeek 或 OpenRouter API Key（用于灵魂蒸馏和语义搜索）" > "$HOME/.neurobase/.env"
    echo "DEEPSEEK_API_KEY=your_key_here" >> "$HOME/.neurobase/.env"
    chmod 600 "$HOME/.neurobase/.env"
    echo "✅ .env 模板已创建"
fi

echo ""
echo "✅ NexSandglass 安装完成！"
echo ""
echo "📂 文件位置:"
echo "   vault.py  → ~/.neurobase/scripts/sandglass_vault.py"
echo "   think.py  → ~/.neurobase/scripts/sandglass_think.py"
echo "   守夜人    → ~/.neurobase/scripts/nightwatch.py"
echo "   MCP       → ~/.neurobase/scripts/sandglass_mcp.py"
echo ""
echo "🔐 加密: macOS 本地权限保护（非 Windows 无 DPAPI）"
echo ""
echo "📋 MCP 配置示例:"
echo '   { "mcpServers": { "NexSandglass": { "command": "python3", "args": ["~/.neurobase/scripts/sandglass_mcp.py"] } } }'
