# NexSandglass ⏳ — Local-First AI Agent Memory

> **中文介绍在下方 · 中文介绍在下方 · 中文介绍在下方**
> **[↓↓↓ Scroll down for Chinese ↓↓↓](#-中文介绍)**

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines-8200-lightgrey)]()
[![Size](https://img.shields.io/badge/Size-266KB-brightgreen)]()

> **Remember. Understand. Know you. Think of you.**

> Plaintext storage, zero-dependency. Four-way concurrent search — FTS5 · IDX · TF-IDF · Shadow Sand.
> Knows not just who you are, but how you became this way. Remembers what you said three days ago.

> **V2.9.9 Minimal Injection:** 四层问答式注入 — 你是谁→往哪走→怎么变成这样→还没做完。236字符/59token，2026年已知最精简的结构化注入。剩余信息 LLM 按需通过 sandglass_search 主动查。

> **Soul Distillation:** Unlike traditional Dialogue Distillation which extracts factual knowledge, Soul Distillation extracts the Agent's unique persona. Powered by **Drift Velocity**, this mechanism captures continuous deviations from the baseline. By distilling these accumulated drifts, we don't just store memories — we forge a unique, evolving soul that resonates with the user.

---

## What is NexSandglass?

NexSandglass is a **local-first AI agent memory engine** that doesn't just store conversations — it understands who you are and how you're changing.

Unlike other memory systems that act as filing cabinets, NexSandglass is a **biographer**: it tracks your decision patterns, weaves causal chains (Thread → Weave Machine), and distills a living persona that evolves with you.

**Core capabilities:**
- **Drift Velocity** — tracks how your decisions shift over time (frugal vs spend vs drift)
- **Thread Knowledge Graph** — extracts entity relationships from conversation without LLM
- **Weave Machine** — connects decisions into causal chains ("why you became who you are")
- **Soul Distillation** — builds a living persona from accumulated drifts, not static snapshots
- **Infinite Context** — 30 topic anchors replace raw conversation history
- **Zero Dependencies** — pure Python stdlib + SQLite, no API key required
- **Hermes-Independent** — runs as standalone memory engine, replaces Hermes built-in memory

**3-second quick start:**
```bash
docker-compose up -d          # Docker one-click
# or
python sandglass_mcp.py       # MCP server on localhost:8765
```

---

## 中文介绍

### 为什么做这个

现有 AI 记忆方案普遍有两个问题：

1. **只记不辨** — 对话全存，画像越来越厚。分不清你上周关心的事和这周已经不一样了
2. **会话即失忆** — 关掉窗口，上下文清零。说过要做的事没人追

NexSandglass 用"阶段+偏移"解决这两个问题。

---

---

我们说四件事：

**是记住。** 每句话明文落沙，一粒不丢。（OS层全盘加密保护，无需应用层加锁）

**是理解。** 你不用告诉它你是谁。它从沙子里把画像捞出来。你变了，它比你先发现。

**是懂你。** 不光知道你是谁，还知道你是怎么变成今天这样的。跨阶段偏移追踪——你的轨迹，不是别人的快照。

**是想你。** 三天前说"加守夜人"。它还记着。下次启动自己跳出来。不是存数据，是惦记你还没做的事。

---

## 与现有方案对比

| 维度 | Mem0 / Letta / Holographic | NexSandglass V2.0 |
|---|---|---|
| 依赖 | 向量数据库 + 多个包 | ✅ **零依赖，纯 stdlib** |
| 加密 | 无 / 可选 | ✅ **明文存储，OS全盘加密** |
| 模块化 | 单体 | ✅ **24模块，枢纽1,389行** |
| 决策追踪 | ❌ | ✅ **决策粒子 + 偏移率 + 幽灵决策** |
| 阶段感知 | ❌ | ✅ **年月+沙量双层阶段，自动切换** |
| 情绪感知 | ❌ | ✅ **情绪熵 + 玻璃 + 熵镜** |
| 场景感知 | ❌ | ✅ **多标签场景 + 关键词匹配** |
| 搜索 | 向量检索 | ✅ **四维扩展 + TF-IDF + 同义词** |
| 中英双语 | ❌ | ✅ **自动检测** |
| 安装 | 服务栈 | ✅ **一键 install.bat** |
| 体积 | 数万行 | ✅ **~5,000行 · 24模块** |

---

## 四大支柱 + 织线

| 支柱 | 做什么 | 吃谁的数据 |
|------|--------|-----------|
| 🧬 灵魂蒸馏 | 从沙子里捞画像，增量更新，自动切阶段 | 全部沙子 + 决策粒子 |
| 📊 偏移率 | 追踪决策偏移方向/幅度，跨阶段对比 | 决策粒子历史 |
| ⏳ 搜索滤镜 | 六维感知扩展关键词，决策粒子权重偏置 | 画像+场景+阶段+决策粒子+影子沙+织线 |
| 🧵 织布机 | 四支柱合成(画像+偏移+搜索+织线因果链)+矛盾检测 | 全部四支柱输出 |
| 🪡 织线 | 正则提取三元组，纯本地因果链，门控≥20条注入 | 对话内容 |

**偏移率和搜索滤镜是两个独立系统**——搜索权重做偏置，偏移率做计算。

---



## Docker 一键部署

```bash
docker-compose up -d
```

沙漏 MCP 服务运行在 `localhost:8765`，数据持久化在 Docker volume。

## 5 分钟上手

```bash
# 安装
./install.bat              # Windows
bash install.sh            # Mac / Linux

# 写入记忆
python -c "from sandglass_log import log_message; log_message('hello', 'user')"

# 搜索
python -c "from sandglass_vault import search; print(search('关键词'))"

# 写入决策粒子
python -c "from decision_particles import log; log('选A还是B', 'B')"

# 运行 Demo
python demo/run_demo.py

# MCP 接入
# { "command": "python", "args": ["path/to/mcp_server.py"] }
```

---

## 决策粒子示例

```
输入："今天想吃早饭还是午饭...还是午饭吧"
                       ↓
_detect_chain()     → [早饭, 午饭, 午饭]       # 抓全链条
_extract_options()  → 早饭_午饭                 # 拆选项
_tag_local()        → 成本观                     # 本地标签
_tag_llm()          → 补偿心理,经期偏好           # LLM 精炼（可选）
_learn()            → "补偿心理" 写入本地词库     # 下次免费命中
_infer_resolution() → "倾向补偿心理，下次直接给甜食" # LLM 推断（本地兜底）

记录：早饭_午饭 | A→B→A 回到B(补偿心理) | spend | 成本观,补偿心理,经期偏好
```

---

## 文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `sandglass_think.py` | 2,084 | L3 思考层：四支柱 + 搜索滤镜 + 脉冲感知 |
| `decision_particles.py` | 526 | L4 决策粒子：链条检测 + 双层标签 + LLM推断 |
| `sandglass_vault.py` | 396 | L2 米粒读取：倒排索引 + FTS5 + mmap |
| `sandglass_sqlite.py` | 128 | L2 FTS5 加速层 |
| `pulse.py` | 242 | 脉冲感知：识别→觉察→提醒 + 契约互动 |
| `emotion_vocab.py` | 184 | 情绪感知：七大情绪 + 动态词库 |
| `plugin.py` | 44 | L1 沙漏写入：明文追加 + O_EXCL锁 + Gateway hook |
| `sandglass_log.py` | 46 | 通用落沙接口 |
| `nightwatch.py` | 68 | 守夜人：沙漏完整性检查 |
| `mcp_server.py` | 201 | MCP 接入 |
| `nexsandglass.py` | 128 | TTY 终端拦截 |
| `test_smoke.py` | 66 | 冒烟测试 |

---

## 设计原则

1. **层追加不替换** — 新层叠加，永不修改已定稿的下层
2. **L1 只落用户消息** — AI 回复不进沙漏
3. **本地优先，LLM 增强** — 没 API Key 一样能跑，有 Key 更精彩
4. **决策是链条不是单点** — A→B→C→回到A，取最后一个才是真决策
5. **改了A必须同步B** — 改名/改签名后全项目 grep
6. **极简注入** — 每轮~59token(四层问答式)，LLM按需sandglass_search查全文

---

## 版本历程

### V1.x — 奠基 (2026-06)
```
V1.0→V1.6: 偏移率·搜索滤镜·情绪感知·决策粒子·回音折·影子沙·织布机·场景系统
核心能力全部建立：从"记住对话"到"理解你是谁"
```

### V2.0 — 架构定型 (2026-06)
```
God Module 拆分(3628→1389行) + 信号链路全通 + 阶段系统(4阶段) + L1/L2封框冻结
从"能跑"到"可独立安装运行"
```

### V2.1→V2.3 — 稳定化 (2026-06)
```
冷热分层·路径统一·MCP 11工具·heartbeat轮转·loop-memory-store
16模块全覆盖，零硬编码路径
```

### V2.8→V2.9.9「极简注入」(2026-06)
```
四路并发搜索 + 明文落沙 + density×trust统一公式
Hermes内存关闭·沙漏独立注入·织线知识图谱·Docker一键部署
四层问答式注入(236字符/59token)·画像增量管道·织线门控
11Bug修复·静默异常可见·双审流水线
```
---

## 性能基准

| 层 | 操作 | 耗时 |
|----|------|------|
| **L1 写** | 单次落沙（明文追加+O_EXCL锁+影子沙索引） | **2.1ms** |
| | 批量10条 | 22.2ms (2.2ms/条) |
| **L2 搜** | FTS5搜索 | **1.2ms** |
| | idx精排 | 2.2ms |
| | 时间轴 | 2.9ms |
| | 最近5条 | 0.5ms |
| **L3 思** | 综合偏移率 | **0.5ms** |
| | 语义搜索 | 0.6ms |
| | 织布机 | 1.5ms |
| | 决策链条检测 | 2.8ms |
| | 情绪感知 | 0.5ms |

> 测试环境：3549条沙子 · Windows 10 · i5-8265U · Python 3.11
