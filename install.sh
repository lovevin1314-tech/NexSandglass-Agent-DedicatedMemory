#!/bin/bash
# NexSandglass V2.9.2 — macOS/Linux 安装脚本
set -e

echo "╔══════════════════════════════════╗"
echo "║  NexSandglass V2.9.2 安装程序    ║"
echo "╚══════════════════════════════════╝"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 创建目录
mkdir -p "$HOME/.neurobase/scripts"
mkdir -p "$HOME/.neurobase/persona"
mkdir -p "$HOME/.neurobase/archive"
mkdir -p "$HOME/.hermes/plugins/memory/nexsandglass"
mkdir -p "$HOME/.hermes/plugins/sandglass"
echo "✅ 目录已创建"

# 复制核心脚本 (30个)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILES=(
    sandglass_paths.py
    sandglass_vault.py sandglass_sqlite.py sandglass_log.py sandglass.py
    sandglass_think.py sandglass_archive.py sandglass_mcp.py
    nexsandglass.py nightwatch.py pulse.py
    persona_l3.py offset_l3.py emotion_l3.py scene_l3.py weave_l3.py
    l3_tasks.py l3_persona_verify.py l3_search_core.py l3_persona.py
    discipline.py offset_signals.py
    decision_particles.py emotion_vocab.py
    shadow_sand.py search_router.py l0_buffer.py
    soul_diff.py plugin.py heartbeat.py
)
for f in "${FILES[@]}"; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$HOME/.neurobase/scripts/$f"
done
echo "✅ 30个核心模块已部署"

# MemoryProvider 插件
[ -f "$SCRIPT_DIR/memory_provider.py" ] && cp "$SCRIPT_DIR/memory_provider.py" "$HOME/.hermes/plugins/memory/nexsandglass/__init__.py"
echo "✅ MemoryProvider 插件已部署"

# .env 模板
if [ ! -f "$HOME/.hermes/.env" ]; then
    echo "# 可选：API Key（用于灵魂蒸馏和语义搜索）" > "$HOME/.hermes/.env"
    echo "DEEPSEEK_API_KEY=***" >> "$HOME/.hermes/.env"
    chmod 600 "$HOME/.hermes/.env" 2>/dev/null || true
    echo "✅ .env 模板已创建"
fi

echo ""
echo "✅ NexSandglass V2.4.0 安装完成！"
echo ""
echo "📂 核心: 30模块 + MemoryProvider插件"
echo "🔐 存储: 明文 — OS层全盘加密保护（BitLocker/FileVault/LUKS）"
echo "🌡️ 多profile: export NEXSANDBASE_HOME=~/.neurobase-custom"
echo "🚀 重启 Hermes Gateway 即可自动落沙"
echo ""
