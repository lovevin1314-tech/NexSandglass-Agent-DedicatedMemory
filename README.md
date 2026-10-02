# NexSandglass ⏳ — 沙漏记忆系统

> **`pip install nexsandglass`** · 纯本地 · 零依赖 · 零 API Key

[![PyPI](https://img.shields.io/badge/PyPI-3.1.0-blue)](https://pypi.org/project/nexsandglass/)
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

## 模型织印象（可选，默认回落纯规则）

织布机新增 `weave_llm.py`：模型可用时，`weave_insight` 额外返回 `impression` / `impression_engine` / `synthesis_enhanced`；模型不可用或加载失败时，自动回落纯规则，原 `synthesis` 字段保持不变。

**架构红线**：模型产出只进入印象层，永不写回 `sandglass.txt` / L0 原始沙。

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `NEXSANDBASE_LLM_ENABLED` | `auto` / `1` / `0`。`auto` 表示有可用后端才启用 | `auto` |
| `NEXSANDBASE_LLM_GGUF` | 本地 GGUF 路径，自动使用 `llama_cpp` | 空 |
| `NEXSANDBASE_LLM_ENDPOINT` | OpenAI 兼容本地端点，例如 `http://127.0.0.1:8080/v1` | 空 |
| `NEXSANDBASE_LLM_MODEL` | 端点模型名 | `qwen2.5-0.5b-instruct` |
| `NEXSANDBASE_LLM_OLLAMA_MODEL` | Ollama 原生模型名 | 空 |
| `NEXSANDBASE_LLM_TIMEOUT` | 模型调用超时秒 | `30` |

推荐模型：`Qwen/Qwen2.5-0.5B-Instruct-GGUF` 的 `qwen2.5-0.5b-instruct-q4_0.gguf`（约 409MB）。

```bash
# 下载（hf-mirror.com）
export HF_ENDPOINT=https://hf-mirror.com
hf download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf \
  --local-dir ~/.nexsandglass/models

# llama.cpp server 启动（推荐，OpenAI 兼容）
llama-server -m ~/.nexsandglass/models/qwen2.5-0.5b-instruct-q4_0.gguf \
  --host 127.0.0.1 --port 8080 -c 4096 -ngl -1
export NEXSANDBASE_LLM_ENDPOINT=http://127.0.0.1:8080/v1
export NEXSANDBASE_LLM_MODEL=qwen2.5-0.5b-instruct
```

验收/对比：`python scripts/weave_llm_acceptance.py`，报告写入 `reports/20260816_织布机0.5B对比报告.md`。

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

### V3.1.0 (2026-08-17) · 补回立体像合成 + 织线补漏
- `_synthesize_3d` 复用 `weave_llm` 本地小模型：模型可用时语义化画像、四选一提醒语气、贴合场景提醒示例；失败自动回落原 22 行本地聚合
- 新增 `weave_missing_triples`：从沙子检索结果补织正则漏掉的关系三元组，经实体原文校验后通过 `wthread_add` 写 L2 织线表，宁缺毋滥
- 新增 `weave_l3.weave_thread_fill` 程序化入口，测试/外部任务可直接触发织线补漏
- 架构红线保持：模型产出不写 L0、模型不可用自动回落、原合成/正则织线逻辑保留
- 版本号统一对齐 3.1.0

### V3.0.0 (2026-08-17) · 织布机接入本地小模型（织印象）
- 新增 `weave_llm.py`：可插拔模型织印象模块——支持 GGUF（llama.cpp）/ OpenAI 兼容端点 / Ollama 三种后端
- 织布机 `weave_insight` 新增 `impression_*` / `synthesis_enhanced`，模型可用时优先织印象，失败自动回落纯规则
- 模型选型：Qwen2.5-0.5B-Instruct Q4_0（409MB），纯本地零 API
- 调优（实测）：prompt 极简化（不要求 JSON）、JSON 失败降级为文本、资料人类可读化——10 话题实测信息密度 +767%、模板机械度 -100%
- 架构红线：模型产出永不写回 L0 原始沙（sandglass.txt 哈希实测未变）、可插拔回落
- 版本号统一：plugin.yaml / pyproject.toml / setup.py / sandglass_paths.py / install.py / agent_bootstrap.py / memory_provider.py / pulse.py / v3/sandglass_paths.py / plugin.py / ARCHITECTURE.md / README 全部对齐 3.0.0
### V2.20.x (2026-08) · Mac 魔改 + 铁律因子熔炼
- V2.20.1: V3 架构里程碑——版本号统一升级，涟漪架构落地
- V2.20.5: sync_turn 消费 messages + 缓存重置修复 + 全量脱敏（移除 persona 残留）+ build/dist 移出跟踪
- V2.20.6: 铁律因子修复熔炼——核心下沉 sandglass_core 唯一 Provider、双层铁律注入（红牌常驻+普通触发）、token 预算纯本地估算（中文1字≈1token）、实体/标签注入（显式记忆/高信实体/事实标签三块）、单5 静默失效清理 128 处、生产红牌标记

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
