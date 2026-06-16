# NexSandglass ⏳ — 沙漏记忆系统

> **`pip install nexsandglass`** · 纯本地 · 零依赖 · 零 API Key

[![PyPI](https://img.shields.io/badge/PyPI-2.10.9-blue)](https://pypi.org/project/nexsandglass/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

**不是记住你说过什么——是理解你怎么变成今天的你。**

灵魂蒸馏 · 偏移率感知 · 铁律因子 · 四路并发搜索 · 极简注入。纯本地，零依赖，越用越懂你。

---

## 快速开始

```bash
pip install nexsandglass
```

```python
from sandglass_vault import search, count
from sandglass_log import log_message

log_message("今天讨论了搜索排序优化", "user")
print(search("搜索排序"))
print(f"沙漏总量: {count()}条")
```

**Hermes Studio / Desktop 用户（推荐）：**
```bash
hermes plugins install lovevin1314-tech/NexSandglass    # 首次安装
hermes plugins update NexSandglass                       # 升级到最新
```
重启 Desktop → 设置 → 记忆体 → 选择 NexSandglass → 开始对话

**⚡ 影子接管（自动）**
内置记忆与沙漏共存。沙漏自动接管：影子沙索引 + `on_memory_write` 捕获 + 三块式注入(421字符)远大于内置(50字符)。无需手动配置。

**⚠️ Desktop GUI 下拉菜单看不到 NexSandglass？**
这是 Hermes Desktop 硬编码限制，非沙漏问题。一行命令激活：
```bash
hermes config set memory.provider nexsandglass
```
重启 Desktop 后生效。

**已安装过？直接更新：**
```bash
hermes plugins update NexSandglass
# 或强制重装: hermes plugins remove NexSandglass && hermes plugins install lovevin1314-tech/NexSandglass
```
```bash
hermes plugins install lovevin1314-tech/NexSandglass
# 重启 Desktop → 设置 → 记忆体 → 选择 NexSandglass
```

**MCP / Docker：**
```bash
git clone https://github.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory
python sandglass_mcp.py
```

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🧬 灵魂蒸馏 | fact_tags + decision_particles → 从沙子里自然生长出画像，越用越懂你 |
| 📊 偏移率追踪 | 省钱/愿投/放弃 三维量化 + 决策疲劳检测 + 15种心理预判 |
| ⚖️ 铁律因子 | 推前必确认 / 永远说实话 / 不先调研不动手 等铁律自动注入+计数 |
| 🔍 四路并发搜索 | 影子沙 + FTS5 + IDX + TF-IDF，毫秒级响应，中英双语 |
| 🎢 纠结度检测 | 决策链条完整追踪，犹豫模式识别，50%犹豫告警 |
| 💉 极简注入 | ~150t，三块式（搜索上下文+状态快照），LLM 一眼看懂 |
| 🔒 全本地 | 数据不出设备，Python stdlib + SQLite，零外部依赖 |

---

## 与现有方案对比

| 维度 | Mem0 / Letta | NexSandglass |
|------|:---:|:---:|
| 依赖 | 向量数据库+N个包 | **零依赖，纯 stdlib** |
| 注入量 | ~200-22000t | **会话~186t + 轮次~150t** |
| 决策追踪 | ❌ | **决策粒子+偏移率+心理预判** |
| 情绪感知 | ❌ | **情绪熵（会话级摘要）** |
| 画像溯源 | ❌ | **可追溯到行号** |
| 铁律系统 | ❌ | **自动注入+违规计数** |
| 搜索 | 向量检索 | **四路并发（影子沙+FTS5+IDX+TF-IDF）** |
| 安装 | 服务栈 | **pip install** |

---

## 设计原则

1. **层追加不替换** — 新层叠加，永不修改下层
2. **纯本地** — Python stdlib + SQLite，零外部依赖
3. **双向注入** — 会话~186t(四层问答) + 轮次~150t(三块式)
4. **越用越懂你** — 管道数据随沙子自然积累

---

## 性能基准

| 层 | 操作 | median | p99 |
|----|------|--------|------|
| **L1 写** | 单次落沙 | **4.3ms** | 19.5ms |
| **L2 搜** | FTS5搜索 | **1.6ms** | 5.4ms |
| | 影子沙 | **0.7ms** | 1.2ms |
| | 四路并发 | 79.4ms | — |
| **L3 思** | 偏移率 | **<0.1ms** | — |
| | 情绪熵(会话级) | 6.5ms | — |
| | 心理预判 | 7.0ms | — |
| | 铁律因子 | **<0.1ms** | — |

> 测试：5900条 · Windows 10 · i5-8265U · Python 3.11 · 完全隔离

---


---

## 教程

### 安装

```bash
# Hermes Studio / Desktop（推荐—小白用户首选）
hermes plugins install lovevin1314-tech/NexSandglass
# 重启 → 设置 → 记忆体 → 选择 NexSandglass → 开始对话

# 升级到最新版
hermes plugins update NexSandglass

# 开发者—任何 Python 项目
pip install nexsandglass
```

### 实用范例

```python
from sandglass_vault import search, count, recent
from sandglass_log import log_message

# 写入记忆（自动落沙）
log_message("今天讨论了搜索排序优化", "user")

# 搜索记忆（毫秒级）
for ln, ts, text in search("搜索排序", limit=3):
    print(f"[{ts}] {text[:80]}")

# 最近记忆
for ln, ts, text in recent(5):
    print(f"[{ts}] {text[:60]}")

print(f"沙漏总量: {count()}条")
```

### Agent 子代理隔离

用 `NEXSANDBASE_HOME` 给不同 Agent 分配独立沙漏，记忆不串：

```bash
# Claude Code 专用
NEXSANDBASE_HOME=~/.neurobase-claude python sandglass_mcp.py
# Codex 专用
NEXSANDBASE_HOME=~/.neurobase-codex python sandglass_mcp.py
# 主 Agent
export NEXSANDBASE_HOME=~/.neurobase
```

### 一键搬家

```bash
python -c "from sandglass_think import memory_migrate; print(memory_migrate())"
# 解压 tar.gz 到新电脑即刻恢复全部记忆
```

### 从 Hermes 迁移

```bash
python hermes_to_sandglass.py  # 一行命令导入 Hermes 历史记忆
```

## 版本历程

### V2.10 (2026-06) · PyPI 发布 + 双向注入
PyPI 发布 `pip install nexsandglass`。三块式轮次注入(150t)+四层问答式会话注入(186t)，DB 自省增量启动，沙子自愈，Porter Stemmer，psychology_hint 15种模式，local_distill 管道蒸馏，enrich_choice 模板引擎。

### V2.9.28-42 (2026-06)
极简注入优化(132→58t)，sim_bonus 线性化修复，`_llm` 全链路根除，停用词过滤(中38+英52)，shadow_index 实体提取修复，fact_tags 空标签回填，`_write_idx` RLock 并发安全，SimHash 跨会话持久化，five-facets.json 管道自动生成，首次画像管道化(`_pipe_build`)。

### V2.9.11-27 (2026-06)
数据点自生长(画像 LLM→数据点驱动)，搜索密度回归 ratio，C组语义扩展(决策粒子注入 7.5x)，管道洞察接入 LLM，铁律因子统一命名，函数名/变量名 LLM 残留全清。

### V2.9 极简注入
四路并发搜索，织线知识图谱，四层问答式注入(~60t)，管道聚合画像，偏移率·纠结度·scene_l3。

### V1.x 奠基
偏移率·情绪感知·决策粒子·影子沙·织布机·场景系统·回音折
