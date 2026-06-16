#!/usr/bin/env python3
"""NexSandglass V2.9.9 — 一键安装+验证 (Python stdlib, 零依赖)"""
import os, sys, shutil

VERSION = "2.11.1"
NB = os.path.join(os.path.expanduser("~"), ".neurobase")
HERMES = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")), "hermes")

# ═══ 33个核心模块 ═══
MODULES = [
    "sandglass_paths.py", "sandglass_vault.py", "sandglass_sqlite.py",
    "sandglass_log.py", "sandglass.py", "sandglass_think.py",
    "sandglass_archive.py", "sandglass_mcp.py", "nexsandglass.py",
    "nightwatch.py", "pulse.py", "heartbeat.py",
    "persona_l3.py", "offset_l3.py", "emotion_l3.py", "scene_l3.py",
    "weave_l3.py", "weavethread.py",
    "l3_tasks.py", "l3_persona_verify.py", "l3_search_core.py", "l3_persona.py",
    "discipline.py", "offset_signals.py",
    "decision_particles.py", "emotion_vocab.py",
    "shadow_sand.py", "search_router.py", "l0_buffer.py",
    "soul_diff.py", "plugin.py", "migrate_v2_4.py", "metrics.py",
    "agent_bootstrap.py",
]

DIRS = [
    f"{NB}/scripts",
    f"{NB}/persona",
    f"{NB}/archive",
    f"{HERMES}/plugins/memory/nexsandglass",
    f"{HERMES}/plugins/sandglass",
]

SRC = os.path.dirname(os.path.abspath(__file__))

def main():
    print(f"╔══════════════════════════════════╗")
    print(f"║  NexSandglass V{VERSION} 安装程序  ║")
    print(f"╚══════════════════════════════════╝")
    print()

    # 1. 创建目录
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
    print("✅ 目录结构已创建")

    # 2. 复制模块
    ok = fail = 0
    for m in MODULES:
        src = os.path.join(SRC, m)
        dst = os.path.join(NB, "scripts", m)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            ok += 1
        else:
            print(f"  ⚠️ 缺少: {m}")
            fail += 1
    print(f"✅ 核心模块: {ok}/{len(MODULES)}")

    # 3. MemoryProvider 插件
    mp_src = os.path.join(SRC, "memory_provider.py")
    mp_dst = os.path.join(HERMES, "plugins", "memory", "nexsandglass", "__init__.py")
    if os.path.exists(mp_src):
        shutil.copy2(mp_src, mp_dst)
        print("✅ MemoryProvider 插件")
    else:
        print("⚠️ memory_provider.py 缺失")

    # 4. Gateway 插件
    pl_src = os.path.join(SRC, "plugin.py")
    pl_dst = os.path.join(HERMES, "plugins", "sandglass", "__init__.py")
    if os.path.exists(pl_src):
        shutil.copy2(pl_src, pl_dst)
        print("✅ Gateway 插件")

    # 5. 环境变量
    env_line = f"\n# NexSandglass\nexport NEXSANDBASE_HOME={NB}\n"
    env_file = os.path.join(HERMES, ".env")
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write(env_line)
        print(f"✅ .env 已创建")
    else:
        with open(env_file, "r") as f:
            content = f.read()
        if "NEXSANDBASE_HOME" not in content:
            with open(env_file, "a") as f:
                f.write(env_line)
            print(f"✅ NEXSANDBASE_HOME 已追加到 .env")
        else:
            print("✅ NEXSANDBASE_HOME 已配置")

    # 6. 验证
    print()
    print("═" * 40)
    print("验证安装...")
    sys.path.insert(0, os.path.join(NB, "scripts"))
    try:
        from sandglass_paths import __version__ as v
        assert v == VERSION, f"版本不匹配: {v}"
        print(f"✅ 版本: {v}")
        from sandglass_think import full_sanity
        fs = full_sanity()
        print(f"✅ full_sanity: {fs['passed']}/4")
    except Exception as e:
        print(f"⚠️ 验证失败: {e}")

    # 7. 全平台自举（V2.10.47）
    print()
    print("═" * 40)
    print("全平台 MCP 自举（自动配置各 Agent）...")
    try:
        from agent_bootstrap import bootstrap_all
        results = bootstrap_all(NB)
        ok = sum(1 for v in results.values() if v == "ok")
        skip = sum(1 for v in results.values() if v in ("skip", "exists"))
        print(f"✅ {ok} 个注入, {skip} 个跳过")
    except Exception as e:
        print(f"⚠️ 自举跳过: {e}")

    print()
    print(f"✅ NexSandglass V{VERSION} 安装完成！")
    print(f"📂 {NB}/scripts/ — {ok}个模块")
    print(f"🚀 重启 Hermes Gateway 即可自动落沙")

if __name__ == "__main__":
    main()
