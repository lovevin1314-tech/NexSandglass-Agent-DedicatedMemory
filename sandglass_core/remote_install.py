#!/usr/bin/env python3
"""NexSandglass — 远程一键安装 (curl | python)"""
import os, sys, subprocess, tempfile, shutil

REPO = "https://github.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory.git"
NB = os.path.join(os.path.expanduser("~"), ".neurobase")

print(f"╔══════════════════════════════════╗")
print(f"║  NexSandglass 远程一键安装       ║")
print(f"╚══════════════════════════════════╝")
print()

# 1. 克隆到临时目录
td = tempfile.mkdtemp()
print(f"→ 克隆仓库...")
r = subprocess.run(["git", "clone", "--depth", "1", REPO, td], capture_output=True, text=True)
if r.returncode != 0:
    print(f"❌ 克隆失败: {r.stderr}")
    sys.exit(1)
print("✅ 仓库已下载")

# 2. 运行 install.py
print(f"→ 安装到 {NB} ...")
r = subprocess.run([sys.executable, os.path.join(td, "install.py")], cwd=td)
if r.returncode != 0:
    print(f"❌ 安装失败")
    sys.exit(1)

# 3. 清理
shutil.rmtree(td, ignore_errors=True)
print(f"✅ NexSandglass 安装完成！重启 Hermes Gateway 生效。")
