#!/bin/bash
# NexSandglass V2.9.9 — macOS/Linux 安装脚本
# 极简注入 · 五大支柱 · 零依赖
set -e

echo "╔══════════════════════════════════╗"
echo "║  NexSandglass V2.9.9 安装程序    ║"
echo "║  极简注入 · 五大支柱 · 零依赖    ║"
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

# 复制核心模块 (33个)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILES=(
    sandglass_paths.py
    sandglass_vault.py sandglass_sqlite.py sandglass_log.py sandglass.py
    sandglass_think.py sandglass_archive.py sandglass_mcp.py
    nexsandglass.py nightwatch.py pulse.py heartbeat.py
    persona_l3.py offset_l3.py emotion_l3.py scene_l3.py weave_l3.py
    weavethread.py
    l3_tasks.py l3_persona_verify.py l3_search_core.py l3_persona.py
    discipline.py offset_signals.py
    decision_particles.py emotion_vocab.py
    shadow_sand.py search_router.py l0_buffer.py
    soul_diff.py plugin.py migrate_v2_4.py
)
for f in "${FILES[@]}"; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$HOME/.neurobase/scripts/$f"
done
echo "✅ 33个核心模块已部署"

# MemoryProvider 插件
[ -f "$SCRIPT_DIR/memory_provider.py" ] && cp "$SCRIPT_DIR/memory_provider.py" "$HOME/.hermes/plugins/memory/nexsandglass/__init__.py"
echo "✅ MemoryProvider 插件已部署"

# Gateway 插件
[ -f "$SCRIPT_DIR/plugin.py" ] && cp "$SCRIPT_DIR/plugin.py" "$HOME/.hermes/plugins/sandglass/__init__.py"
echo "✅ Gateway 插件已部署"

echo ""
echo "✅ NexSandglass V2.9.9 安装完成！"
echo ""
echo "📂 33模块 + MemoryProvider + Gateway插件"
echo "🔐 明文存储 — OS层全盘加密保护（BitLocker/FileVault/LUKS）"
echo "💉 四层问答式注入 — 236字符/59token"
echo "🌡️ 多profile: export NEXSANDBASE_HOME=~/.neurobase-custom"
echo "🚀 重启 Hermes Gateway 即可自动落沙"
echo ""
