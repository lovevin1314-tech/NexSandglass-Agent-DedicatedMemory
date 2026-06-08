@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════╗
echo ║  NexSandglass V1.0  安装程序     ║
echo ╚══════════════════════════════════╝
echo.
echo 正在部署沙漏记忆系统...

:: 1. 创建目录
mkdir "%USERPROFILE%\.neurobase\scripts" 2>nul
mkdir "%USERPROFILE%\.neurobase\persona" 2>nul
mkdir "%LOCALAPPDATA%\hermes\plugins\sandglass" 2>nul

:: 2. 复制核心脚本
copy /Y "%~dp0vault.py" "%USERPROFILE%\.neurobase\scripts\sandglass_vault.py" >nul
copy /Y "%~dp0think.py" "%USERPROFILE%\.neurobase\scripts\sandglass_think.py" >nul
copy /Y "%~dp0nightwatch.py" "%USERPROFILE%\.neurobase\scripts\nightwatch.py" >nul
copy /Y "%~dp0mcp_server.py" "%USERPROFILE%\.neurobase\scripts\sandglass_mcp.py" >nul
copy /Y "%~dp0plugin.py" "%LOCALAPPDATA%\hermes\plugins\sandglass\__init__.py" >nul

:: 3. 复制守夜人启动项（可选）
copy /Y "%~dp0nightwatch.py" "%USERPROFILE%\.neurobase\scripts\nightwatch.py" >nul

:: 4. 创建.env模板（如果不存在）
if not exist "%LOCALAPPDATA%\hermes\.env" (
    echo # 沙漏需要 DeepSeek 或 OpenRouter API Key（可选，仅用于灵魂蒸馏和语义搜索）> "%LOCALAPPDATA%\hermes\.env"
    echo DEEPSEEK_API_KEY=your_key_here>> "%LOCALAPPDATA%\hermes\.env"
)

echo.
echo ✅ 安装完成！
echo.
echo 📂 文件位置:
echo    L1 插件: %LOCALAPPDATA%\hermes\plugins\sandglass\__init__.py
echo    L2 搜索: %USERPROFILE%\.neurobase\scripts\sandglass_vault.py
echo    L3 思考: %USERPROFILE%\.neurobase\scripts\sandglass_think.py
echo    守夜人: %USERPROFILE%\.neurobase\scripts\nightwatch.py
echo    MCP:    %USERPROFILE%\.neurobase\scripts\sandglass_mcp.py
echo.
echo 🚀 使用方式:
echo    重启 Hermes Gateway 即可自动开始落沙
echo    调 nightwatch.py 做全系统健康检查
echo    MCP 接入: 配 sandglass_mcp.py 进你的 Agent
echo.
echo 🔐 加密: Windows DPAPI 自动启用 / macOS 明文（本地权限保护）
echo.
pause
