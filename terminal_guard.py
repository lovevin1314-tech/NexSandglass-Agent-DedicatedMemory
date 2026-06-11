"""
NexSandglass 终端自检器 — 防偷懒机制
=====================================
任何终端命令执行前，扫描是否违反硬阻断规则。
如果匹配到禁止模式，拒绝执行并返回提醒。
"""

import os
import sys
import re

# ── 硬阻断规则 ──
_BLOCK_RULES = [
    # 图片处理手写 API → 必须用 vision_analyze
    (r"base64.*image|qwen-vl.*base64|dashscope.*base64|image_cache.*base64",
     "🚫 图片处理禁止手写API！请用 vision_analyze 工具。"),
    (r"urllib.*request.*image",
     "🚫 图片处理禁止手写API！请用 vision_analyze 工具。"),

    # Token 明文出现在命令中
    (r"ghp_[A-Za-z0-9]{36}",
     "🚫 Token 明文禁止出现在命令中！请用环境变量或文件读入。"),

    # curl 直接访问 GitHub API（无 auth 会快速耗尽限流）
    (r"curl.*api\.github\.com.*(?!Bearer|token)",
     "🚫 GitHub API 无认证禁止调用！API限流每小时仅60次。"),

    # 我应该用但没用 patch/edit 而是用 sed/awk
    (r"sed -i.*\.py|awk.*>.*\.py",
     "⚠️ 编辑代码建议用 patch 工具，不要用 sed/awk。"),
]

# ── 图像文件检测 ──
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def check_command(command: str) -> bool:
    """检查终端命令是否违反硬阻断规则。返回 True=放行, False=阻断。"""
    for pattern, message in _BLOCK_RULES:
        if re.search(pattern, command, re.IGNORECASE):
            print(message, file=sys.stderr)
            return False

    # 检查是否在处理图片文件
    for ext in _IMAGE_EXT:
        if ext in command.lower():
            # 再检查是否是 API 调用而非工具调用
            if "base64" in command.lower() or "urllib" in command.lower():
                print("🚫 检测到图片文件+API调用组合！请用 vision_analyze。", file=sys.stderr)
                return False

    return True


if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read().strip()
    ok = check_command(cmd)
    sys.exit(0 if ok else 1)
