#!/usr/bin/env python3
"""NexSandglass V2.20.4 — fact_tags 注入质量闸 阶段A 验证（临时沙漏，绝不碰真实数据）

场景：NEXSANDBASE_HOME=/tmp/sandglass_stageA_quality 全套临时沙漏，
含已知污染样本（TheUsers IMPORTANT/张三/刚忙完一/亲爱的/测试用户 等行），
跑注入逻辑断言：
  a) TheUsers IMPORTANT 不进 top3
  b) 张三 归一化为 测试用户
  c) 亲爱的/刚忙完一/点事情/我在呢亲/爱的/聊成你在/好的/问题 被停用词/别名剔除
  d) 行号 > 当前行数的行不参与统计（越界残留出局）
  e) 正常中文标签（测试用户/沙漏/记忆）保留
"""
import os, sys, shutil, tempfile, sqlite3

TEST_ROOT = os.path.join(tempfile.gettempdir(), "sandglass_stageA_quality")
shutil.rmtree(TEST_ROOT, ignore_errors=True)
os.makedirs(os.path.join(TEST_ROOT, "persona"), exist_ok=True)
os.environ["NEXSANDBASE_HOME"] = TEST_ROOT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shadow_sand import (  # noqa: E402
    set_shadow_path, shadow_index, shadow_top_tags, extract_tags, _get_conn,
)
import logging
logger = logging.getLogger(__name__)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ✅ {name}")
    else:
        FAIL.append(name)
        print(f"  ❌ {name} {detail}")


def main():
    print("NexSandglass V2.20.4 fact_tags 质量闸 阶段A 验证")
    print(f"临时沙漏: {TEST_ROOT}")

    # ── 1) 建临时沙漏 ──
    sand_path = os.path.join(TEST_ROOT, "sandglass.txt")
    lines = [
        "2026-08-13 10:00:00 | user | 今天和测试用户聊天聊得很开心，记忆沙漏工作正常。\n",
        "2026-08-13 10:01:00 | user | 刚忙完一点事情，亲爱的，我现在有空了。\n",
        "2026-08-13 10:02:00 | tool | {\"output\": \"The IMPORTANT result for Users is here\", \"exit_code\": 0}\n",
        "2026-08-13 10:03:00 | user | [System note: Your previous turn was interrupted]\n",
        "2026-08-13 10:04:00 | user | 沙漏记忆测试，张三说过的话。\n",
        "2026-08-13 10:05:00 | user | 我在呢亲，爱的，聊成你在哪里？\n",
        "2026-08-13 10:06:00 | user | 好的，问题解决了，对的，最近的对。\n",
        "2026-08-13 10:07:00 | user | 测试用户的记忆沙漏很好用。\n",
    ]
    with open(sand_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    CUR = len(lines)

    db = _get_conn()
    db.execute("DELETE FROM fact_tags")
    db.execute("DELETE FROM entities")
    db.execute("DELETE FROM trust")

    # 2) 模拟 6/17 旧提取器残留（含越界行号——95.4% 场景）
    legacy_rows = [
        (1, "测试用户,聊天"),
        (2, "刚忙完一,点事情,亲爱的,我现在"),
        (3, "The,Users,IMPORTANT"),
        (4, "System,note"),
        (5, "张三,沙漏,记忆"),
        (6, "我在呢亲,爱的,聊成你在"),
        (7, "好的,问题,对的,最近的对"),
        (8, "测试用户,沙漏,记忆"),
    ]
    for ln, tags in legacy_rows:
        db.execute(
            "INSERT OR REPLACE INTO fact_tags (line_num, category, tags) VALUES (?, 'general', ?)",
            (ln, tags),
        )
    for ln in range(100, 120):  # 越界残留——行号远超当前 8 行
        db.execute(
            "INSERT OR REPLACE INTO fact_tags (line_num, category, tags) VALUES (?, 'general', '越界残留,The,亲爱的,刚忙完一')",
            (ln,),
        )
    db.commit()

    # 3) 新提取器写入——归一化 + system/tool 内容跳过 + category 不再首标签污染
    shadow_index("2026-08-13 10:08:00 | user | 张三，今天很忙。", line_num=9)
    shadow_index("2026-08-13 10:09:00 | tool | {\"output\": \"IMPORTANT thing\", \"exit_code\": 0}", line_num=10)

    # ── 4) 注入统计断言 ──
    tags_out = shadow_top_tags(limit=2000)
    tagset = set(tags_out)

    # e) 正常中文标签保留
    check("e1 测试用户 保留", "测试用户" in tagset)
    check("e2 沙漏 保留", "沙漏" in tagset)
    check("e3 记忆 保留", "记忆" in tagset)

    # a) ASCII 垃圾不进统计
    check("a1 The 剔除", "The" not in tagset)
    check("a2 Users 剔除", "Users" not in tagset)
    check("a3 IMPORTANT 剔除", "IMPORTANT" not in tagset)
    check("a4 System/note 剔除", not ({"System", "note"} & tagset))

    # b) 张三 归一化为 测试用户
    check("b1 张三 不再出现", "张三" not in tagset)
    check("b2 提取侧归一化", "测试用户" in extract_tags("张三，今天很忙。"))

    # c) 停用词/别名剔除
    for bad in ("亲爱的", "刚忙完一", "点事情", "我在呢亲", "爱的", "聊成你在",
                "好的", "问题", "对的", "最近的对", "我现在"):
        check(f"c 剔除 {bad}", bad not in tagset)

    # d) 行号门控——越界残留出局
    check("d1 越界残留 不参与统计", "越界残留" not in tagset)
    check("d2 越界残留行已入库(供门控验证)",
          db.execute("SELECT COUNT(*) FROM fact_tags WHERE line_num >= 100").fetchone()[0] == 20)

    # 关注 注入行组装（与 memory_provider.py / __init__.py 同口径）
    from collections import Counter
    c = Counter()
    for t in shadow_top_tags(limit=2000):
        t = t.strip()
        if t and len(t) > 1:
            c[t] += 1
    top = [t for t, _ in c.most_common(3) if _ >= 2]
    focus = f"关注: {', '.join(top)}" if top else ""
    print(f"\n  → 注入『关注: 』输出: {focus}")
    check("关注 top3 中文为主", set(top) == {"测试用户", "沙漏", "记忆"}, f"实际 {top}")

    # 5) 新提取器落库断言
    row9 = db.execute("SELECT tags, category FROM fact_tags WHERE line_num=9").fetchone()
    check("提取落库 张三→测试用户", row9 and "测试用户" in row9[0] and "张三" not in row9[0], str(row9))
    check("category 不再首标签污染", row9 and row9[1] in ("general", "exam_general")
          and not row9[1].startswith("测试用户"), str(row9))
    row10 = db.execute("SELECT tags, category FROM fact_tags WHERE line_num=10").fetchone()
    check("system/tool 内容不落标签", row10 is None or row10[0] in ("", None), str(row10))

    # 6) 真实注入链路（provider.system_prompt_block）——临时沙漏内跑通
    try:
        from memory_provider import NexSandglassProvider
        prov = NexSandglassProvider()
        block = prov.system_prompt_block()
        focus_line = [l for l in block.split("\n") if l.startswith("关注: ")]
        print(f"  → provider.system_prompt_block 关注行: {focus_line}")
        if focus_line:
            fl = focus_line[0]
            check("provider 关注行含测试用户", "测试用户" in fl)
            check("provider 关注行不含 The", "The" not in fl)
        else:
            check("provider 关注行生成", False, "未找到 关注: 行")
    except Exception as e:
        logger.warning(f"main: 局部导入失败: from memory_provider import NexSandglassProvider", exc_info=True)
        check("provider 注入链路", False, f"{type(e).__name__}: {e}")

    print(f"\n结果: {len(PASS)}/{len(PASS) + len(FAIL)} 通过")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
