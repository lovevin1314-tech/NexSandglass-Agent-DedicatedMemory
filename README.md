# NexSandglass 沙漏记忆系统⏳ V1.6.1 — 四层记忆架构

> **是记住。是理解。是懂你。是想你。**

> 每句话加密落沙，一粒不丢。从沙子里捞画像——你变了，它比你先发现。
> 不光知道你是谁，还知道你是怎么变成今天这样的。三天前说过的事，它还记着。
>
> 真正意义上的"越用越懂你"。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines-4230-lightgrey)]()
[![Size](https://img.shields.io/badge/Size-57KB-brightgreen)]()

---

## 与现有方案对比

| 维度 | Mem0 / Letta | NexSandglass |
|---|---|---|
| 依赖 | 向量数据库 + 多个包 | ✅ **零依赖，纯 stdlib** |
| 加密 | 无 / 可选 | ✅ **DPAPI 本地加密** |
| 决策追踪 | ❌ | ✅ **决策链条 + LLM 推断 + 本地兜底** |
| 自进化 | ❌ | ✅ **_learn() LLM 标签 → 本地词库 → 免费命中** |
| 阶段感知 | ❌ | ✅ **偏移率追踪 + 自动切阶段** |
| 情绪感知 | ❌ | ✅ **七大情绪 + 主语判断 + 协调提醒** |
| 实时感知 | ❌ | ✅ **角色/偏好/禁区/工具 即说即应** |
| 搜索 | 向量检索 | ✅ **四维扩展（场景+画像+阶段+决策粒子）** |
| 中英双语 | ❌ | ✅ **自动检测，全双语** |
| 体积 | 数万行 + 服务栈 | ✅ **4,230 行 · 57KB** |

---

## 四大支柱

| 支柱 | 做什么 | 吃谁的数据 |
|------|--------|-----------|
| 🧬 灵魂蒸馏 | 从沙子里捞画像，自动切阶段，波浪自吸收 | 全部沙子 + 决策粒子 |
| 📊 偏移率 | 追踪决策偏移方向/幅度，跨阶段对比 | 决策粒子历史 |
| ⏳ 搜索滤镜 | 四维扩展关键词，决策粒子权重偏置搜索结果 | 画像+场景+阶段+决策粒子 |
| 🧵 织布机 | 检测画像矛盾，跨阶段互链，追索链 | 全部四支柱输出 |

**偏移率和搜索滤镜是两个独立系统**——搜索权重做偏置，偏移率做计算。

---

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
| `plugin.py` | 44 | L1 沙漏写入：DPAPI 加密 + Gateway hook |
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
6. **双审标准** — 代码 push 后 6h 内自动审查

---

## 版本历程

| 版本 | 核心 | 具体 |
|------|------|------|
| **V1.0** | 🏗 地基 | 三层架构封框。L1加密落沙·L2倒排搜索·L3灵魂蒸馏+偏移率+织布机。2320行，Hermes-only。 |
| **V1.1** | 🔧 补漏 | 偏移率维度分解·TF-IDF三级降级·smoke test·全平台安装·MCP ping。从能用→好用。 |
| **V1.2** | 🌍 去 Hermes 化 | sandglass_log通用落沙·TTY Wrapper·MCP 12工具。任何Agent都能用。 |
| **V1.3** | 🧬 自生长 | 本地画像提取·ASCII偏移可视化·互链层·波浪自吸收。零LLM也能跑。 |
| **V1.3.1** | 🎬 展示 | 贾斯汀·比伯14年成长Demo。README重构：Quick Start+点名竞品+实际输出。 |
| **V1.4** | 💬 对话感 | 用户体验层：首次欢迎仪式·人格实时感知·偏移告警·回响确认。系统活起来了。 |
| **V1.4.3** | 感知深度 | 识别·觉察·提醒三层感知。情绪闭环：放弃→先改好自己→其他待办放放。 |
| **V1.5** | 🌐 中英双语 | 自动语言检测。中文小二 / English Keeper。签约仪式：问称呼→刻进沙子。 |
| **V1.6** | 🔍 双感知三维检索 | 画像+场景+阶段驱动搜索。偏移率静默加权。三级搜索加速(FTS5→idx→mmap)。 |
| **V1.6.1** | 🧬 决策粒子V2 | 双层标签(本地+LLM自进化)。决策链条(A→B→C→A)。LLM吃画像推断倾向。双审自检。 |

```
V1.0  地基：能跑
V1.1  补漏：跑得稳
V1.2  扩圈：别人也能跑
V1.3  自长：不喂数据也能长
V1.3.1 展示：让人看见它在长
V1.4  对话：让人感觉它在长
V1.6  懂你：你说过的每句话，我都拿着去找答案
V1.6.1 进化：每做一个决定，我就更懂你一分
```

---

## 性能基准

| 层 | 操作 | 耗时 |
|----|------|------|
| **L1 写** | 单次落沙（append+DPAPI加密） | **1.3ms** |
| | 批量10条 | 10.4ms (1.0ms/条) |
| **L2 搜** | FTS5搜索 | **1.2ms** |
| | idx精排 | 2.2ms |
| | 时间轴 | 2.9ms |
| | 最近5条 | 0.5ms |
| **L3 思** | 综合偏移率 | **0.5ms** |
| | 语义搜索 | 0.6ms |
| | 织布机 | 1.5ms |
| | 决策链条检测 | 2.8ms |
| | 情绪感知 | 0.5ms |

> 测试环境：931条沙子 · Windows 10 · i5-8265U · Python 3.11 · 零污染（L1写入使用临时沙漏副本）
> 基准脚本：`benchmark.py` — `python benchmark.py`
