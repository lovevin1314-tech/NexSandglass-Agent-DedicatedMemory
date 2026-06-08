# NexSandglass 沙漏记忆系统⏳ V1.3

> **是记住。是理解。是懂你。是想你。**
>
> **Soul Distillation (灵魂蒸馏):** Unlike traditional Dialogue Distillation which extracts factual knowledge, Soul Distillation extracts the Agent's unique persona. Powered by **Drift Velocity (偏移率)**, this mechanism captures continuous deviations from the baseline. By distilling these accumulated drifts, we don't just store memories——we forge a unique, evolving soul that resonates with the user.
>
> 真正意义上的"越用越懂你"。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines-2743-lightgrey)]()
[![Size](https://img.shields.io/badge/Size-40KB-brightgreen)]()

---

## 为什么做这个

现有 AI 记忆方案普遍有两个问题：

1. **只记不辨** — 对话全存，画像越来越厚。分不清你上周关心的事和这周已经不一样了
2. **会话即失忆** — 关掉窗口，上下文清零。说过要做的事没人追

NexSandglass 用"阶段+偏移"解决这两个问题。

---

我们说四件事：

**是记住。** 每句话加密落沙，一粒不丢。谁也看不见。

**是理解。** 你不用告诉它你是谁。它从沙子里把画像捞出来。你变了，它比你先发现。

**是懂你。** 不光知道你是谁，还知道你是怎么变成今天这样的。跨阶段偏移追踪——你的轨迹，不是别人的快照。

**是想你。** 三天前说"加守夜人"。它还记着。下次启动自己跳出来。不是存数据，是惦记你还没做的事。

---

## 与现有方案对比

| 维度 | Mem0 / Letta | NexSandglass |
|---|---|---|
| 依赖 | 向量数据库 + 多个包 | **零依赖，纯 stdlib** |
| 加密 | 无 / 可选 | **本地 OS 密钥链加密** |
| 阶段感知 | ❌ | ✅ **偏移率追踪 + 自动切阶段** |
| 语义搜索 | 向量检索（需嵌入模型） | 关键词倒排 + 可选 LLM 扩展 |
| 画像 | 静态累积 | 自动切阶段 + 波浪吸收 |
| 体积 | 上万行 + 服务栈 | **2743 行 · 40KB** |

---

## 5 分钟上手

```bash
# 安装
./install.bat              # Windows
bash install.sh            # Mac / Linux

# 写入第一条记忆
python -c "from sandglass_log import log_message; log_message('hello', 'user')"

# 搜索
python -c "from sandglass_vault import search; print(search('关键词'))"

# 运行 Demo（贾斯汀·比伯 14 年成长轨迹）
python demo/run_demo.py

# MCP 接入（Claude Desktop / Cursor / Windsurf）
# { "command": "python", "args": ["path/to/mcp_server.py"] }
```

---

## 实际效果

**偏移轨迹（ASCII 可视化）：**

```
  2009    +80% ██████████████  纯真·名利驱动
  2014    -80% ██████████████  谷底·自毁
  2022    +70% █████████████  与自己和好
```

**本地画像提取（零 LLM）：**

```
# 主人画像 — 本地提取
## 角色：独立开发者，主要做开源项目
## 工具：Python、Rust、Go
## 决策：开源、免费、性价比优先
```

**织布机跨阶段洞察：**

```
✦ 2009 vs 2014 相似度: 8%——几乎是完全不同的人
✦ 2009 vs 2022 相似度: 12%——核心的纯真和感恩回来了
```

---

## V1.3 新增

| 功能 | 说明 |
|------|------|
| 本地画像提取 | 零 LLM 也能生成画像——纯模式匹配 |
| ASCII 偏移可视化 | `offset_chart()` 一秒钟看懂轨迹 |
| 互链层 | 阶段间自动关联——过去封存，规律长进现在 |
| 波浪自吸收 | 小波浪累积 ≥5 条或 ≥60% 偏移 → 自动重整画像 |

---

## 任何 Agent 都能用

| 方式 | 适用 |
|------|------|
| Hermes 插件 | 全自动落沙 |
| TTY Wrapper | Mac / Linux 终端 Agent |
| MCP 12 工具 | 任何 MCP Agent |
| `sandglass_log.py` | 自定义脚本 |

---

Windows ✅ DPAPI · macOS / Linux ⚠️ 本地权限保护

---

**NexLSL** · Neuro + Loom · MIT
