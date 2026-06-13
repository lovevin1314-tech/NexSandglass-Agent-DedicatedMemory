@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════╗
echo ║  NexSandglass V2.9.9 安装程序    ║
echo ║  极简注入 · 五大支柱 · 零依赖    ║
echo ╚══════════════════════════════════╝
echo.
echo 正在部署沙漏记忆系统...

:: 1. 创建目录
mkdir "%USERPROFILE%\.neurobase\scripts" 2>nul
mkdir "%USERPROFILE%\.neurobase\persona" 2>nul
mkdir "%USERPROFILE%\.neurobase\archive" 2>nul
mkdir "%LOCALAPPDATA%\hermes\plugins\memory\nexsandglass" 2>nul
mkdir "%LOCALAPPDATA%\hermes\plugins\sandglass" 2>nul

:: 2. 复制核心模块 (33个)
for %%f in (
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
) do (
    if exist "%%~dp0%%f" copy /Y "%%~dp0%%f" "%USERPROFILE%\.neurobase\scripts\%%f" >nul
)

:: 3. MemoryProvider插件
if exist "%%~dp0memory_provider.py" copy /Y "%%~dp0memory_provider.py" "%LOCALAPPDATA%\hermes\plugins\memory\nexsandglass\__init__.py" >nul

:: 4. Gateway插件
if exist "%%~dp0plugin.py" copy /Y "%%~dp0plugin.py" "%LOCALAPPDATA%\hermes\plugins\sandglass\__init__.py" >nul

echo.
echo ✅ NexSandglass V2.9.9 安装完成！
echo.
echo 📂 33模块 + MemoryProvider插件
echo 🔐 明文存储 — OS层全盘加密保护
echo 💉 四层问答式注入 — 236字符/59token
echo 🚀 重启 Hermes Gateway 即可自动落沙
echo.
pause
