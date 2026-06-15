# NexSandglass ⏳ — Local-First AI Agent Memory

> **中文介绍在下方 · 中文介绍在下方 · 中文介绍在下方**
> **[↓↓↓ Scroll down for Chinese ↓↓↓](#-中文介绍)**

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines-10000-lightgrey)]()
[![Size](https://img.shields.io/badge/Size-280KB-brightgreen)]()

> **Remember. Understand. Know you. Think of you.**

> Plaintext storage, zero-dependency. Four-way concurrent search — FTS5 · IDX · TF-IDF · Shadow Sand.
> Knows not just who you are, but how you became this way. Remembers what you said three days ago.

> **V2.9.9.11 Data-Driven Persona:** 画像更新完全去LLM化 — fact_tags + decision_particles + offset 数据点自然累积。_llm 纯本地降级，persona_update() 零外部依赖自动生长。

> **Soul Distillation:** Unlike traditional Dialogue Distillation which extracts factual knowledge, Soul Distillation extracts the Agent's unique persona. Powered by **Drift Velocity**, this mechanism captures continuous deviations from the baseline. By distilling these accumulated drifts, we don't just store memories — we forge a unique, evolving soul that resonates with the user.

---

## What is NexSandglass?

NexSandglass is a **local-first AI agent memory engine**.

**Core capabilities:**
- **Drift Velocity** — tracks how your decisions shift over time
- **Thread Knowledge Graph** — extracts entity relationships from conversation without LLM
- **Weave Machine** — connects decisions into causal chains
- **Soul Distillation** — builds a living persona from accumulated drifts
- **Zero Dependencies** — pure Python stdlib + SQLite

**⚡ 安装（给 Agent 的链接，一行搞定）：**
```bash
curl -sSL https://raw.githubusercontent.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory/main/remote_install.py | python
```
> 然后把 `NEXSANDBASE_HOME` 写入 Hermes 的 `.env`，重启 Gateway 即刻生效。

---

## 中文介绍

### 为什么做这个

1. **只记不辨** — 对话全存，分不清上周关心的事和这周已经不一样了
2. **会话即失忆** — 关掉窗口，上下文清零

NexSandglass 用"阶段+偏移"解决这两个问题。

---

我们说四件事：

**是记住。** 每句话明文落沙，一粒不丢。

**是理解。** 你不用告诉它你是谁。它从沙子里把画像捞出来。

**是懂你。** 不光知道你是谁，还知道你是怎么变成今天这样的。

**是想你。** 三天前说的事，下次启动自己跳出来。

---

## 与现有方案对比

| 维度 | Mem0 / Letta / Holographic | NexSandglass V2.9 |
|---|---|---|
| 依赖 | 向量数据库 + 多个包 | ✅ **零依赖，纯 stdlib** |
| 注入量 | ~200-22000 token | ✅ **~60 token**（236字符） |
| 模块化 | 单体 | ✅ **33模块** |
| 决策追踪 | ❌ | ✅ **决策粒子 + 偏移率 + 心理预判** |
| 阶段感知 | ❌ | ✅ **自动切阶段** |
| 情绪感知 | ❌ | ✅ **情绪熵（会话级摘要）** |
| 画像溯源 | ❌ | ✅ **SHA256 密码学验证** |
| 搜索 | 向量检索 | ✅ **四路并发（影子沙+FTS5+IDX+TF-IDF）** |
| 知识图谱 | ❌ | ✅ **织线三元组（零LLM）** |
| 中英双语 | ❌ | ✅ **自动检测** |
| 安装 | 服务栈 | ✅ **一行 python install.py** |
| 纪律系统 | ❌ | ✅ **会话级自动计数** |

---

## 五大支柱

| 支柱 | 做什么 |
|------|--------|
| 🧬 灵魂蒸馏 | 从沙子里捞画像，增量更新，自动切阶段 |
| 📊 偏移率 | 追踪决策偏移方向/幅度，跨阶段对比 |
| ⏳ 搜索滤镜 | 六维感知扩展关键词 |
| 🧵 织布机 | 四支柱合成+矛盾检测 |
| 🪡 织线 | 正则提取三元组，纯本地因果链 |

---

## 安装指引

**Herems 用户（推荐）：**
```bash
curl -sSL https://raw.githubusercontent.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory/main/remote_install.py | python
```
然后确保 Hermes 的 `.env` 有 `NEXSANDBASE_HOME=~/.neurobase`，重启 Gateway。

**MCP 用户（独立服务）：**
```bash
git clone https://github.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory
cd NexSandglass-Agent-DedicatedMemory
pythonw sandglass_mcp.py    # Windows无弹窗
# 或 python sandglass_mcp.py  # Mac/Linux
```

**Docker：**
```bash
docker-compose up -d
```

## 快速体验

```bash
# 写入记忆
python -c "from sandglass_log import log_message; log_message('hello', 'user')"

# 搜索
python -c "from sandglass_vault import search; print(search('关键词'))"
```

## 多 Agent 隔离

用 `NEXSANDBASE_HOME` 给不同 Agent 分配独立沙漏：

```bash
# Claude Code 专用
NEXSANDBASE_HOME=~/.neurobase-claude python sandglass_mcp.py

# Codex 专用
NEXSANDBASE_HOME=~/.neurobase-codex python sandglass_mcp.py
```

## 一键搬家

```bash
# 打包全部记忆为 tar.gz（解压到新电脑即刻恢复）
python -c "from sandglass_think import memory_migrate; print(memory_migrate())"

# 或导出沙漏文本文件
python -c "from sandglass_vault import sandglass_export; print(sandglass_export())"
```

---

## 从 Hermes 迁移

```bash
python hermes_to_sandglass.py
```
一行命令，自动找到 Hermes 记忆并导入沙漏。

## 冒烟测试

```bash
python test_smoke.py
```

---

## 设计原则

1. **层追加不替换** — 新层叠加，永不修改已定稿的下层
2. **本地优先，LLM 增强** — 没 API Key 一样能跑
3. **决策是链条不是单点** — A→B→C→回到A
4. **改了A必须同步B** — 改名/改签名后全项目 grep
5. **极简注入** — 每轮~60token，LLM按需sandglass_search
6. **零外部依赖** — Python stdlib + SQLite

---

## 版本历程

### V1.x — 奠基
偏移率·搜索滤镜·情绪感知·决策粒子·回音折·影子沙·织布机·场景系统

### V2.0 — 架构定型
God Module 拆分 + 信号链路全通 + L1/L2封框冻结

### V2.9 — 极简注入
四路并发搜索 + 织线知识图谱 + 四层问答式注入(~60token)

### V2.9.9.8 — MCP 合规
19工具 inputSchema + 情绪熵重构 + 纪律因子自动触发

### V2.9.9.11 — 数据点自生长
`persona_update()` 加 `_data_driven_refresh()` 本地兜底。_llm 返回空不再冻住画像，自动从 fact_tags + offset + decision_particles 聚合更新。清理 memory_provider.py 重复代码块。

### V2.9.9.12 — 搜索密度回归ratio
`sand_density` 余弦+IDF → 简单 ratio + trust + SimHash。15项对比测试 0 退化，LLM 理解精准度显著提升（分数 0.4-1.0 vs 0.1-0.3）。代码 -9 行。

### V2.9.12 — 首次画像管道化
`persona_build` fallback 从正则匹配 → `_pipe_build()` 管道聚合。fact_tags+offset+particles+scenes 四管道生成首次画像。越用管道越丰富，画像越准。

---

## 性能基准 (V2.9.9.8 实测)

| 层 | 操作 | median | p99 |
|----|------|--------|------|
| **L1 写** | 单次落沙 | **4.3ms** | 19.5ms |
| | 批量10条 | 79.0ms | — |
| **L2 搜** | FTS5搜索 | **1.6ms** | 5.4ms |
| | 四路并发 | 79.4ms | — |
| | 最近10条 | 2.8ms | 4.1ms |
| | 影子沙(<1ms) | **0.7ms** | 1.2ms |
| **L3 思** | 综合偏移率 | **<0.1ms** | — |
| | 情绪熵(会话级) | 6.5ms | — |
| | 织布洞察 | 85.3ms | — |
| | 心理预判 | 7.0ms | — |
| | 搜索滤镜 | 4.8ms | — |
| | 决策标签 | **0.5ms** | — |
| | 纪律因子 | **<0.1ms** | — |

> 测试环境：5900条沙子 · Windows 10 · i5-8265U · Python 3.11 · 完全隔离
