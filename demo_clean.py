"""
NexSandglass Demo — 纯净版（无真实数据）
=========================================
模拟 3 天对话 → 画像从零长出来 → 偏移追踪 → 跨阶段演化
"""

import sys, os, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 创建临时沙漏 ──
REAL_SANDGLASS = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
REAL_IDX = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.idx")
TMP = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass_demo.txt")
TMP_IDX = TMP + ".idx"

# 备份真实沙漏
if os.path.exists(REAL_SANDGLASS):
    shutil.copy2(REAL_SANDGLASS, REAL_SANDGLASS + ".demo_backup")
    shutil.copy2(REAL_IDX, REAL_IDX + ".demo_backup") if os.path.exists(REAL_IDX) else None

# 替换为临时沙漏
import sandglass_vault as sv
sv._SANDGLASS = TMP
sv._IDX = TMP_IDX
# 清空缓存
import sandglass_think as s3
s3._PERSONA = os.path.join(os.path.expanduser("~"), ".neurobase", "persona_demo", "persona.md")
s3._PERSONA_DIR = os.path.join(os.path.expanduser("~"), ".neurobase", "persona_demo")
os.makedirs(s3._PERSONA_DIR, exist_ok=True)

# ── 模拟第1天：基础信息 ──
from sandglass_log import log_message as lm
# 覆盖沙漏路径
import sandglass_log as sl
sl._SANDGLASS = TMP

lm("我是一名独立开发者，主要做开源项目", "user")
lm("技术栈是 Python + Rust，偶尔写 Go", "user")
lm("我是那种能自己写就不买工具的人", "user")
lm("性价比优先，免费方案能跑就行", "user")
lm("最近对 AI Agent 记忆系统特别感兴趣", "user")
lm("想在 GitHub 上做个开源项目", "user")

print("=== 第1天 — 初始画像（零LLM） ===")
from sandglass_vault import count
print(f"沙子: {count()} 条")
lp = s3._local_persona_extract()
print(lp[:400] or "(数据不足，多聊几天)")
print()

# ── 模拟第2天：决策偏移 ──  
lm("看了市面上几个记忆方案", "user")
lm("Mem0 功能全但要花钱，不划算", "user")
lm("还是自己手写吧，不依赖外部服务", "user")
lm("DPAPI 加密就够用了", "user")
lm("开源 + 零依赖才是正道", "user")

off = s3.offset_check("不花钱自己搞，开源零依赖", user_persisted=False)
print("=== 第2天 — 偏移追踪 ===")
print(f"偏移率: {off['offset']:+d}% ({off['direction']})")
print(f"维度: {off.get('dimensions', {})}")
print()

# ── 模拟第3天：跨阶段演化 ──
lm("项目在 GitHub 上收到了一些反馈", "user")
lm("有人说 Mac 上没加密，有点担心", "user")
lm("我在考虑要不要加一个付费功能", "user")
lm("但现阶段预算有限，还是先免费吧", "user")
lm("以后有了收入再考虑买工具", "user")
lm("先把免费版做好再说", "user")

off3 = s3.offset_check("付费以后再说，先免费", user_persisted=False)
print("=== 第3天 — 松动信号 ===")
print(f"偏移率: {off3['offset']:+d}% ({off3['direction']})")
print(f"维度: {off3.get('dimensions', {})}")
print()

# ── 偏移轨迹 ──
from sandglass_think import offset_chart
print("=== 3天偏移轨迹 ===")
print(offset_chart())
print()

# ── 织布机 ──
from sandglass_think import weave_contradiction
contra = weave_contradiction()
print("=== 织布机矛盾检测 ===")
print(f"矛盾: {len(contra['conflicts'])}处 — {contra['suggestion']}")
print()

# ── 恢复真实沙漏 ──
print("=== 输出文件 ===")
print(f"临时画像: {s3._PERSONA}")
s3._local_persona_extract_result = lp  # for demo output

# 恢复
sv._SANDGLASS = REAL_SANDGLASS
sv._IDX = REAL_IDX
if os.path.exists(REAL_SANDGLASS + ".demo_backup"):
    shutil.move(REAL_SANDGLASS + ".demo_backup", REAL_SANDGLASS)
if os.path.exists(REAL_IDX + ".demo_backup"):
    shutil.move(REAL_IDX + ".demo_backup", REAL_IDX)

print(f"沙漏已恢复: {sv.count()} 条")
print()
print("🎉 Demo 完成！没有触碰任何真实数据。")
