"""
NexSandglass Demo — 3 天模拟对话
=================================
展示：画像零→长出来、偏移追踪、跨阶段演化
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sandglass_log import log_message

# ── 第1天：初始画像积累 ──
log_message("我是独立开发者，平时做点小项目", sender="user")
log_message("我喜欢用 Python，偶尔也写点 Go", sender="user")
log_message("最近在研究 AI Agent 记忆系统", sender="user")
log_message("偏好开源方案，不太想花钱买云服务", sender="user")
log_message("自己搞比较有成就感", sender="user")
log_message("装了个 Hermes，觉得挺有意思的", sender="user")
log_message("不过感觉 Agent 老是忘记我说过的话", sender="user")
log_message("想自己搭一个记忆层", sender="user")

# ── 第1天：Persona 构建 ──
from sandglass_think import persona_build, persona_canvas, offset_chart
print("=== 第1天 — 初始画像 ===")
p = persona_build()
if p:
    with open(p, "r", encoding="utf-8") as f:
        print(f.read()[:500])
    print("...\n")

# ── 第2天：偏移信号 ──
log_message("今天看了一圈 Mem0 和 TencentDB", sender="user")
log_message("Mem0 是挺方便的，就是贵", sender="user")
log_message("TencentDB 太重了，不喜欢", sender="user")
log_message("还是自己手搓吧，不花钱", sender="user")
log_message("用 DPAPI 加密就够了", sender="user")

# 对比昨天——偏移追踪
print("=== 第2天 — 偏移追踪 ===")
from sandglass_think import offset_check
off = offset_check("不花钱，自己搞，性价比优先", user_persisted=False)
print(f"偏移率: {off['offset']:+d}% ({off['direction']})")
print(f"维度: {off.get('dimensions', {})}")
print()

# ── 第3天：跨阶段演化 ──
log_message("项目上线 GitHub 了", sender="user")
log_message("要考虑多平台支持了", sender="user")
log_message("Mac 上没 DPAPI，得想个办法", sender="user")
log_message("先明文存着吧，本地权限保护也行", sender="user")
log_message("付费方案其实也有道理，效率高", sender="user")
log_message("不过我现阶段预算有限，先免费吧", sender="user")

# 第3天偏移——出现花钱信号
off3 = offset_check("付费方案效率高但先免费", user_persisted=False)
print("=== 第3天 — 偏移信号 ===")
print(f"偏移率: {off3['offset']:+d}% ({off3['direction']})")
print(f"维度: {off3.get('dimensions', {})}")
print()

# ── 综合轨迹 ──
print("=== 偏移轨迹 ===")
print(offset_chart())
print()

# ── 画像更新 ──
from sandglass_think import persona_update
print("=== 第3天 — 画像更新 ===")
persona_update()
persona_canvas()
canvas_path = os.path.join(os.path.expanduser("~"), ".neurobase", "profile", "canvas.md")
if os.path.exists(canvas_path):
    with open(canvas_path, "r", encoding="utf-8") as f:
        print(f.read()[:400])

print("\n🎉 Demo 完成！")
print("文件输出: ~/.neurobase/profile/persona.md")
print("          ~/.neurobase/profile/canvas.md")
print("          ~/.neurobase/sandglass.txt")
