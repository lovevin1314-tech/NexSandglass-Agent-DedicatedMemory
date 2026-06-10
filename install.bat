@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════╗
echo ║  NexSandglass V2.0.0 安装程序    ║
echo ╚══════════════════════════════════╝
echo.
echo 正在部署沙漏记忆系统...

:: 1. 创建目录
mkdir "%USERPROFILE%\.neurobase\scripts" 2>nul
mkdir "%USERPROFILE%\.neurobase\persona" 2>nul
mkdir "%LOCALAPPDATA%\hermes\plugins\sandglass" 2>nul

:: 2. 复制核心脚本
for %%f in (
    sandglass_vault.py sandglass_sqlite.py sandglass_log.py sandglass.py
    sandglass_think.py nexsandglass.py nightwatch.py pulse.py
    persona_l3.py offset_l3.py emotion_l3.py scene_l3.py weave_l3.py
    l3_tasks.py l3_persona_verify.py l3_search_core.py l3_persona.py
    discipline.py offset_signals.py
    decision_particles.py emotion_vocab.py
    shadow_sand.py search_router.py l0_buffer.py
) do (
    if exist "%%~dp0%%f" copy /Y "%%~dp0%%f" "%USERPROFILE%\.neurobase\scripts\%%f" >nul
)

:: 3. 复制插件
copy /Y "%%~dp0plugin.py" "%LOCALAPPDATA%\hermes\plugins\sandglass\__init__.py" >nul

:: 4. 创建.env模板（如果不存在）
if not exist "%LOCALAPPDATA%\hermes\.env" (
    echo # 沙漏需要 DeepSeek 或 OpenRouter API Key（可选，仅用于灵魂蒸馏和语义搜索）> "%LOCALAPPDATA%\hermes\.env"
    echo DEEPSEEK_API_KEY=your_key_here>> "%LOCALAPPDATA%\hermes\.env"
)

echo.
echo ✅ NexSandglass V2.0.0 安装完成！
echo.
echo 📂 模块: 24个核心文件已部署
echo 🔐 加密: Windows DPAPI 自动启用
echo 🚀 重启 Hermes Gateway 即可自动开始落沙
echo.
pause
