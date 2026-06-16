@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════╗
echo ║  NexSandglass V2.9.42 安装程序    ║
echo ║  极简注入 · 零依赖 · 纯本地        ║
echo ╚══════════════════════════════════╝
echo.
echo 正在部署沙漏记忆系统...

:: 1. 创建目录
mkdir "%USERPROFILE%\.neurobase\scripts" 2>nul
mkdir "%USERPROFILE%\.neurobase\persona" 2>nul
mkdir "%USERPROFILE%\.neurobase\profile" 2>nul
mkdir "%LOCALAPPDATA%\hermes\hermes-agent\plugins\memory\nexsandglass" 2>nul

:: 2. 复制全部模块
copy /Y "%%~dp0*.py" "%USERPROFILE%\.neurobase\scripts\" >nul 2>&1
copy /Y "%%~dp0*.py" "%LOCALAPPDATA%\hermes\hermes-agent\plugins\memory\nexsandglass\" >nul 2>&1
copy /Y "%%~dp0plugin.yaml" "%LOCALAPPDATA%\hermes\hermes-agent\plugins\memory\nexsandglass\" >nul 2>&1

echo.
echo ✅ NexSandglass V2.9.42 安装完成！
echo.
echo 📂 39模块 + 插件已部署
echo 🔐 全本地运行，数据不出设备
echo.
echo ⚡ 下一步：
echo    1. 重启 Hermes Desktop
echo    2. 设置 → 记忆体 → 选择 NexSandglass
echo    3. 开始对话，沙子自动落下
echo.
pause
