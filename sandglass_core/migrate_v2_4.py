"""
NexSandglass V2.4+ 数据迁移工具
===============================
用途：将旧版本 DPAPI/base64 加密的 sandglass.txt 解密为明文。
V2.4.0 开始 NexSandglass 改为明文存储，旧加密数据需要迁移。

用法：
  python migrate_v2_4.py [--dry-run] [sandglass.txt路径]

  --dry-run  预览，不实际修改
  不传路径默认 ~/.neurobase/sandglass.txt

注意：
  - 会自动备份原文件为 sandglass.txt.bak.时间戳
  - 已明文的行自动跳过
  - Windows: 需要 pywin32 (win32crypt) 解密 DPAPI
  - 非 Windows: base64 编码的沙子尝试解码，无法解码的保持原样
"""
import argparse
import base64
import os
import shutil
import sys
from datetime import datetime


def decrypt_dpapi(text: str) -> str:
    """DPAPI 解密。失败返回原文。"""
    from win32crypt import CryptUnprotectData
    raw = base64.b64decode(text.strip())
    return CryptUnprotectData(raw, None, None, None, 0)[1].decode("utf-8")


def decrypt_base64(text: str) -> str:
    """base64 解码。失败返回原文。"""
    try:
        return base64.b64decode(text.strip()).decode("utf-8")
    except Exception:
        return text


def migrate(sandglass_path: str, dry_run: bool = False) -> dict:
    """迁移 sandglass.txt 从加密到明文。返回统计。"""
    if not os.path.exists(sandglass_path):
        print(f"❌ 文件不存在: {sandglass_path}")
        sys.exit(1)

    # 检测 win32crypt
    try:
        from win32crypt import CryptUnprotectData
        has_dpapi = True
    except ImportError:
        has_dpapi = False
        print("⚠️  win32crypt 不可用，仅处理 base64 行")

    # 读取
    with open(sandglass_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    stats = {"total": 0, "decrypted_dpapi": 0, "decrypted_b64": 0, "already_plain": 0, "failed": 0}
    new_lines = []

    for line in lines:
        stats["total"] += 1
        line = line.rstrip("\n\r")
        if " | " not in line:
            new_lines.append(line + "\n")
            stats["already_plain"] += 1
            continue

        parts = line.split(" | ", 2)
        if len(parts) < 3:
            new_lines.append(line + "\n")
            stats["already_plain"] += 1
            continue

        ts, sender, text = parts
        text_stripped = text.strip()

        # 判断是否需要解密
        if text_stripped.startswith("AQAA"):
            # DPAPI 加密
            if not has_dpapi:
                new_lines.append(line + "\n")
                stats["failed"] += 1
                continue
            try:
                plaintext = decrypt_dpapi(text_stripped)
                new_lines.append(f"{ts} | {sender} | {plaintext}\n")
                stats["decrypted_dpapi"] += 1
                if stats["decrypted_dpapi"] <= 3:
                    print(f"  ✓ DPAPI: {ts} | {sender} | {plaintext[:60]}...")
            except Exception as e:
                new_lines.append(line + "\n")
                stats["failed"] += 1
                print(f"  ✗ 解密失败: {ts} - {e}")
        elif any(ord(c) > 127 for c in text_stripped):
            # 含中文 = 已明文
            new_lines.append(line + "\n")
            stats["already_plain"] += 1
        elif len(text_stripped) > 40 and "/" not in text_stripped and " " not in text_stripped:
            # 可能是 base64（无空格无斜杠的长字符串）
            try:
                plaintext = decrypt_base64(text_stripped)
                if any(ord(c) > 127 for c in plaintext) or plaintext.isascii():
                    new_lines.append(f"{ts} | {sender} | {plaintext}\n")
                    stats["decrypted_b64"] += 1
                else:
                    new_lines.append(line + "\n")
                    stats["already_plain"] += 1
            except Exception:
                new_lines.append(line + "\n")
                stats["already_plain"] += 1
        else:
            new_lines.append(line + "\n")
            stats["already_plain"] += 1

    if dry_run:
        print(f"\n🔍 预览模式 — 未修改文件")
    else:
        # 备份
        backup = sandglass_path + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(sandglass_path, backup)
        print(f"\n📦 备份: {backup}")

        # 写回
        with open(sandglass_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("✅ 迁移完成")

    print(f"  总行数: {stats['total']}")
    print(f"  DPAPI解密: {stats['decrypted_dpapi']}")
    print(f"  base64解码: {stats['decrypted_b64']}")
    print(f"  已明文: {stats['already_plain']}")
    print(f"  失败: {stats['failed']}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NexSandglass V2.4+ 数据迁移")
    parser.add_argument("path", nargs="?", default=None, help="sandglass.txt 路径")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    path = args.path or os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
    migrate(path, args.dry_run)
