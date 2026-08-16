#!/usr/bin/env python3
"""V3.1.0 立体像合成 + 织线补漏验收脚本。

铁律：
- 只使用 `NEXSANDBASE_HOME=/tmp/nexsandglass-v31-tests-*` 临时沙漏；
- 先跑纯本地聚合/纯正则基线，再用 mock 适配器验证模型分支，再验证不可达回落；
- 每次阶段前后核对 L0 `sandglass.txt` 哈希。

真实 Qwen2.5-0.5B 在 Hermes 主机可跑；当前执行沙箱如 Metal 后端不可用，
则本脚本至少给出 mock 分支 + 不可达端点回落证据，不伪造真实模型推理数据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "sandglass_core"
sys.path.insert(0, str(CORE_DIR))

# 必须在导入 sandglass 模块前设置临时沙漏。
TMP_HOME = tempfile.mkdtemp(prefix="nexsandglass-v31-tests-", dir="/tmp")
os.environ["NEXSANDBASE_HOME"] = TMP_HOME
os.environ["NEXSANDBASE_LLM_ENABLED"] = "0"

for name in ("persona", "archive", "scripts"):
    Path(TMP_HOME, name).mkdir(parents=True, exist_ok=True)

SAND = Path(TMP_HOME, "sandglass.txt")
PERSONA = Path(TMP_HOME, "persona", "persona.md")

TEST_SANDS = [
    "我选择 Figma 做界面设计，同时开着 Sketch 和 XD 很累",
    "最近开始用 Lightroom 修照片，不再依赖手机滤镜",
    "我决定用 Notion 替代 Obsidian 做知识库",
    "从 Apple Notes 迁到 Notion，导出很麻烦",
    "本地优先很重要，尽量不用需要联网的工具",
    "最近工作压力大，晚上经常失眠",
    "我偏好深色模式，晚上写代码眼睛舒服",
    "Vim 比 VS Code 更轻，但 VS Code 插件生态好",
    "我安装了 llama.cpp，准备跑本地小模型",
    "织布机现在还是纯正则，想加一个本地小脑",
    "我更喜欢命令行，少点 GUI 干扰",
    "讨厌强制订阅的软件，喜欢买断制",
    "早上九点前不碰手机，专注写代码",
    "用 SQLite 存记忆索引，简单可靠",
    "想把 Qwen2.5-0.5B 接到织布机",
    "换了 M4 Mac，内存 16GB，本地推理应该够用",
    "选择 hf-mirror 下载模型，官方域名不可达",
    "这条沙子和模型织布任务直接相关",
    "模型产出不能写回原始沙，只能作为印象层",
    "测试一定要用 NEXSANDBASE_HOME=/tmp/xxx 隔离",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def seed_data() -> None:
    lines = []
    for idx, text in enumerate(TEST_SANDS, 1):
        lines.append(f"2026-08-17 10:{idx:02d}:00 | user | {text}\n")
    SAND.write_text("".join(lines), encoding="utf-8")
    PERSONA.write_text(
        "# 本地优先工具控\n"
        "- 喜欢买断制、命令行和深色模式\n"
        "- 工具选择偏好本地运行，讨厌强制订阅\n"
        "- 当前阶段在给织布机接入本地小模型\n",
        encoding="utf-8",
    )
    from weavethread import wthread_store
    for idx, text in enumerate(TEST_SANDS, 1):
        wthread_store(text, line_num=idx, subject="user")


def sentence_count(text: str) -> int:
    if not text:
        return 0
    return max(1, sum(text.count(p) for p in "。！？!?."))


def tone_diversity(rows: list[dict]) -> int:
    return len({r.get("reminder_tone") or "" for r in rows})


def install_mock():
    import weave_llm
    original = {
        "backend_config": weave_llm.backend_config,
        "call_model": weave_llm._call_model,
    }
    weave_llm.backend_config = lambda: {"kind": "mock", "model": "mock-qwen-0.5b"}
    weave_llm._call_model = mock_call_model
    return original


def mock_call_model(config, topic, context, system_prompt="", prompt_text=""):
    if "立体像" in topic:
        return json.dumps(
            {
                "persona_type": "本地优先、买断制偏好的精简工具使用者",
                "reminder_tone": "行动式",
                "reminder_example": "今天先把 Figma 的版本整理一下，别再同时开三个编辑器。",
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "triples": [
                {"subject": "Figma", "relation": "用途", "object": "界面设计", "source_line": 1},
                {"subject": "Lightroom", "relation": "用途", "object": "照片", "source_line": 2},
                {"subject": "Photoshop", "relation": "用途", "object": "海报", "source_line": 1},
            ]
        },
        ensure_ascii=False,
    )


def restore_backends(original) -> None:
    import weave_llm
    weave_llm.backend_config = original["backend_config"]
    weave_llm._call_model = original["call_model"]


def local_synthesis() -> dict:
    from sandglass_think import _synthesize_3d
    return _synthesize_3d(trigger="baseline_rule")


def model_synthesis() -> dict:
    os.environ["NEXSANDBASE_LLM_ENABLED"] = "1"
    from sandglass_think import _synthesize_3d
    return _synthesize_3d(trigger="mock_model")


def regex_thread_count() -> int:
    from weavethread import wthread_stats
    return int(wthread_stats().get("total_triples", 0))


def model_thread_fill() -> dict:
    os.environ["NEXSANDBASE_LLM_ENABLED"] = "1"
    from weave_l3 import weave_thread_fill
    return weave_thread_fill(topic="Figma", limit=20)


def fallback_synthesis() -> dict:
    os.environ["NEXSANDBASE_LLM_ENABLED"] = "1"
    os.environ["NEXSANDBASE_LLM_ENDPOINT"] = "http://127.0.0.1:9/v1"
    os.environ["NEXSANDBASE_LLM_MODEL"] = "qwen2.5-0.5b-instruct"
    from sandglass_think import _synthesize_3d
    return _synthesize_3d(trigger="fallback_unreachable")


def fallback_thread_fill() -> dict:
    os.environ["NEXSANDBASE_LLM_ENABLED"] = "1"
    os.environ["NEXSANDBASE_LLM_ENDPOINT"] = "http://127.0.0.1:9/v1"
    os.environ["NEXSANDBASE_LLM_MODEL"] = "qwen2.5-0.5b-instruct"
    from weave_llm import weave_missing_triples
    from sandglass_vault import recent
    return weave_missing_triples(recent(20), allow_llm=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-json", default=str(REPO_ROOT / "reports" / "20260817_v31_acceptance.json"))
    args = parser.parse_args()

    seed_data()
    l0_before = sha256(SAND)

    local = local_synthesis()
    l0_after_rule = sha256(SAND)
    regex_count = regex_thread_count()

    original = install_mock()
    model3d = model_synthesis()
    l0_after_mock3d = sha256(SAND)
    fill = model_thread_fill()
    l0_after_mock_fill = sha256(SAND)
    after_fill_count = regex_thread_count()
    restore_backends(original)

    fb3d = fallback_synthesis()
    l0_after_fallback3d = sha256(SAND)
    fb_fill = fallback_thread_fill()
    l0_after_fallback_fill = sha256(SAND)

    report = {
        "environment": {
            "temp_home": TMP_HOME,
            "corpus_size": len(TEST_SANDS),
            "model_gguf_found": Path.home().joinpath(".nexsandglass", "models", "qwen2.5-0.5b-instruct-q4_0.gguf").exists(),
            "real_model_usable": False,
            "real_model_block_reason": "llama_context failed: sandbox Metal command queue unavailable",
        },
        "integrity": {
            "l0_before": l0_before,
            "l0_after_rule": l0_after_rule,
            "l0_after_mock3d": l0_after_mock3d,
            "l0_after_mock_fill": l0_after_mock_fill,
            "l0_after_fallback3d": l0_after_fallback3d,
            "l0_after_fallback_fill": l0_after_fallback_fill,
            "l0_unchanged": len({
                l0_before, l0_after_rule, l0_after_mock3d,
                l0_after_mock_fill, l0_after_fallback3d, l0_after_fallback_fill,
            }) == 1,
        },
        "task_a": {
            "rule": {
                "persona_type": local.get("persona_type", ""),
                "reminder_tone": local.get("reminder_tone", ""),
                "reminder_example": local.get("reminder_example", ""),
                "source": local.get("source", ""),
                "engine": local.get("synthesis_engine", ""),
                "fallback_reason": local.get("synthesis_fallback_reason", ""),
                "persona_chars": len(local.get("persona_type") or ""),
                "example_chars": len(local.get("reminder_example") or ""),
                "example_sentences": sentence_count(local.get("reminder_example") or ""),
            },
            "model": {
                "persona_type": model3d.get("persona_type", ""),
                "reminder_tone": model3d.get("reminder_tone", ""),
                "reminder_example": model3d.get("reminder_example", ""),
                "source": model3d.get("source", ""),
                "engine": model3d.get("synthesis_engine", ""),
                "model": model3d.get("synthesis_model", ""),
                "fallback_reason": model3d.get("synthesis_fallback_reason", ""),
                "persona_chars": len(model3d.get("persona_type") or ""),
                "example_chars": len(model3d.get("reminder_example") or ""),
                "example_sentences": sentence_count(model3d.get("reminder_example") or ""),
            },
            "fallback": {
                "engine": fb3d.get("synthesis_engine", ""),
                "fallback_reason": fb3d.get("synthesis_fallback_reason", ""),
                "source": fb3d.get("source", ""),
                "example_nonempty": bool(fb3d.get("reminder_example")),
            },
            "tone_diversity_rule": tone_diversity([local]),
            "tone_diversity_model": tone_diversity([model3d]),
        },
        "task_b": {
            "regex_count": regex_count,
            "model_fill": fill,
            "after_fill_count": after_fill_count,
            "increase": max(0, after_fill_count - regex_count),
            "fallback": fb_fill,
        },
    }

    os.makedirs(Path(args.out_json).parent, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(TMP_HOME, ignore_errors=True)
