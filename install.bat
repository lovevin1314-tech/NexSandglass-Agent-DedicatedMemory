@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════╗
echo ║  NexSandglass V2.1.14 安装程序    ║
echo ╚══════════════════════════════════╝
echo.
echo 正在部署沙漏记忆系统...

:: 1. 创建目录
mkdir "%USERPROFILE%\.neurobase\scripts" 2>nul
mkdir "%USERPROFILE%\.neurobase\persona" 2>nul
mkdir "%USERPROFILE%\.neurobase\archive" 2>nul
mkdir "%LOCALAPPDATA%\hermes\plugins\memory\nexsandglass" 2>nul

:: 2. 复制核心脚本 (19个)
for %%f in (
    sandglass_paths.py
    sandglass_vault.py sandglass_sqlite.py sandglass_log.py sandglass.py
    sandglass_think.py sandglass_archive.py nexsandglass.py nightwatch.py pulse.py
    persona_l3.py offset_l3.py emotion_l3.py scene_l3.py weave_l3.py
    l3_tasks.py l3_persona_verify.py l3_search_core.py l3_persona.py
    discipline.py offset_signals.py
    decision_particles.py emotion_vocab.py
    shadow_sand.py search_router.py l0_buffer.py
) do (
    if exist "%%~dp0%%f" copy /Y "%%~dp0%%f" "%USERPROFILE%\.neurobase\scripts\%%f" >nul
)

:: 3. 复制MemoryProvider插件
if exist "%%~dp0memory_provider.py" copy /Y "%%~dp0memory_provider.py" "%LOCALAPPDATA%\hermes\plugins\memory\nexsandglass\__init__.py" >nul

:: 4. 复制Gateway插件
if exist "%%~dp0plugin.py" copy /Y "%%~dp0plugin.py" "%LOCALAPPDATA%\hermes\plugins\sandglass\__init__.py" >nul

:: 5. 创建.env模板（如果不存在）
if not exist "%LOCALAPPDATA%\hermes\.env" (
    echo # 沙漏需要 DeepSeek 或 OpenRouter API Key（可选，仅用于灵魂蒸馏和语义搜索）> "%LOCALAPPDATA%\hermes\.env"
    echo DEEPSEEK_API_KEY=your_key_here>> "%LOCALAPPDATA%\hermes\.env"
)

:: 6. 多profile支持（可选）
echo # 如需多profile隔离，取消下行注释并设自定义路径 >> "%USERPROFILE%\.neurobase\README.txt"
echo # set NEXSANDBASE_HOME=%%USERPROFILE%%\.neurobase-your-profile >> "%USERPROFILE%\.neurobase\README.txt"

echo.
echo ✅ NexSandglass V2.1.14 安装完成！
echo.
echo 📂 核心: 19模块 + MemoryProvider插件
echo 🔐 加密: Windows DPAPI / Mac Linux base64
echo 🌡️ 路径: NEXSANDBASE_HOME可配置多profile
echo 🚀 重启 Hermes Gateway 即可自动落沙
echo.
pause
