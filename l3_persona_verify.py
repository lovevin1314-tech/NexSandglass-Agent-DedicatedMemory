#!/usr/bin/env python3
"""
NexSandglass L3 — 画像验证模块
persona_trace / persona_verify / persona_diff — SHA256溯源验证

从 sandglass_think.py 提取 (2026-06-11)
原位置: L692-803
"""

import os
import re
import hashlib
import shutil

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_PERSONA_DIR = os.path.join(_VAULT, "persona")


def persona_trace(claim: str) -> list:
    """给定人格声明，搜索 sandglass 找到来源行并验证 SHA256 hash。"""
    from sandglass_vault import search

    # 提取 [src:hash:L行号] 格式的溯源标记
    src_match = re.search(r'\[src:([a-f0-9]+):L?(\d+)\]', claim)
    if src_match:
        expected_hash = src_match.group(1)
        line_num = int(src_match.group(2))
        # 验证源行内容是否匹配
        results = search("", limit=1)
        # 直接读沙漏行验证 hash
        sg = os.path.join(_VAULT, "sandglass.txt")
        if os.path.exists(sg):
            with open(sg, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if i == line_num:
                        actual_hash = hashlib.sha256(line.strip().encode()).hexdigest()[:8]
                        if actual_hash == expected_hash:
                            return [{"line": line_num, "verified": True, "text": line.strip()[:100]}]
                        else:
                            return [{"line": line_num, "verified": False,
                                     "expected": expected_hash, "actual": actual_hash,
                                     "warning": "源行已变或 LLM 幻觉行号"}]
            return [{"line": line_num, "verified": False, "warning": "行号不存在——LLM 幻觉"}]

    # Fallback: no hash tag, do plain search
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", claim)
    query = " ".join(tokens[:5])
    return search(query, limit=5)


def persona_verify() -> dict:
    """一键验证画像所有声明。扫描 [src:hash:L行号] 标签，批量验证 hash。"""
    p = os.path.join(_PERSONA_DIR, "persona.md")
    if not os.path.exists(p):
        return {"verified": 0, "failed": 0, "total": 0, "details": [], "insight": "画像不存在"}

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    sg = os.path.join(_VAULT, "sandglass.txt")
    if not os.path.exists(sg):
        return {"verified": 0, "failed": 0, "total": 0, "details": [], "insight": "沙漏不存在"}

    # 读沙漏行号索引
    sg_lines = {}
    with open(sg, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            sg_lines[i] = line.strip()

    details = []
    verified = 0
    failed = 0

    for m in re.finditer(r'\[src:([a-f0-9]+):L?(\d+)\]', content):
        expected_hash = m.group(1)
        line_num = int(m.group(2))
        if line_num in sg_lines:
            actual_hash = hashlib.sha256(sg_lines[line_num][:300].encode()).hexdigest()[:8]
            if actual_hash == expected_hash:
                verified += 1
                details.append({"line": line_num, "status": "ok", "hash": expected_hash})
            else:
                failed += 1
                details.append({"line": line_num, "status": "mismatch",
                               "expected": expected_hash, "actual": actual_hash})
        else:
            failed += 1
            details.append({"line": line_num, "status": "missing", "warning": "行号不存在"})

    insight = f"✅ {verified}/{verified+failed} 溯源验证通过" if verified+failed > 0 else "画像中无溯源标签"
    if failed > 0:
        insight += f"，{failed}条异常（{'幻觉行号' if any(d.get('status')=='missing' for d in details) else '源内容已变'}）"
    return {"verified": verified, "failed": failed, "total": verified+failed,
            "details": details, "insight": insight}


def persona_diff() -> dict:
    """对比新旧画像变更——新增/消失/不变的声明。用于persona_update后自动追踪。"""
    backup = os.path.join(_PERSONA_DIR, "persona.prev.md")
    current = os.path.join(_PERSONA_DIR, "persona.md")

    if not os.path.exists(current):
        return {"added": 0, "removed": 0, "unchanged": 0, "insight": "画像不存在"}
    if not os.path.exists(backup):
        # 首次——保存当前为基准
        shutil.copy2(current, backup)
        return {"added": 0, "removed": 0, "unchanged": 0, "insight": "首次——已保存基线"}

    with open(backup, "r", encoding="utf-8") as f:
        old = f.read()
    with open(current, "r", encoding="utf-8") as f:
        new = f.read()

    # 提取 [src:...] 标签作为声明ID
    def extract_src(text):
        return set(re.findall(r'\[src:([a-f0-9]+):L\d+\]', text))

    old_srcs = extract_src(old)
    new_srcs = extract_src(new)

    added = new_srcs - old_srcs
    removed = old_srcs - new_srcs
    unchanged = old_srcs & new_srcs

    return {"added": len(added), "removed": len(removed), "unchanged": len(unchanged),
            "added_hashes": list(added)[:10], "removed_hashes": list(removed)[:10],
            "insight": f"🆕 {len(added)}新增 💨 {len(removed)}消失 ✅ {len(unchanged)}不变" if added or removed else "无变化"}
