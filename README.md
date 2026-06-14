1|# NexSandglass ⏳ — Local-First AI Agent Memory
2|
3|> **中文介绍在下方 · 中文介绍在下方 · 中文介绍在下方**
4|> **[↓↓↓ Scroll down for Chinese ↓↓↓](#-中文介绍)**
5|
6|[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
7|[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
8|[![Lines](https://img.shields.io/badge/Lines-8200-lightgrey)]()
9|[![Size](https://img.shields.io/badge/Size-266KB-brightgreen)]()
10|
11|> **Remember. Understand. Know you. Think of you.**
12|
13|> Plaintext storage, zero-dependency. Four-way concurrent search — FTS5 · IDX · TF-IDF · Shadow Sand.
14|> Knows not just who you are, but how you became this way. Remembers what you said three days ago.
15|
16|> **V2.9.9 Minimal Injection:** 四层问答式注入 — 你是谁→往哪走→怎么变成这样→还没做完。236字符/59token，2026年已知最精简的结构化注入。剩余信息 LLM 按需通过 sandglass_search 主动查。
17|
18|> **Soul Distillation:** Unlike traditional Dialogue Distillation which extracts factual knowledge, Soul Distillation extracts the Agent's unique persona. Powered by **Drift Velocity**, this mechanism captures continuous deviations from the baseline. By distilling these accumulated drifts, we don't just store memories — we forge a unique, evolving soul that resonates with the user.
19|
20|---
21|
22|## What is NexSandglass?
23|
24|NexSandglass is a **local-first AI agent memory engine** that doesn't just store conversations — it understands who you are and how you're changing.
25|
26|Unlike other memory systems that act as filing cabinets, NexSandglass is a **biographer**: it tracks your decision patterns, weaves causal chains (Thread → Weave Machine), and distills a living persona that evolves with you.
27|
28|**Core capabilities:**
29|- **Drift Velocity** — tracks how your decisions shift over time (frugal vs spend vs drift)
30|- **Thread Knowledge Graph** — extracts entity relationships from conversation without LLM
31|- **Weave Machine** — connects decisions into causal chains ("why you became who you are")
32|- **Soul Distillation** — builds a living persona from accumulated drifts, not static snapshots
33|- **Infinite Context** — 30 topic anchors replace raw conversation history
34|- **Zero Dependencies** — pure Python stdlib + SQLite, no API key required
35|- **Hermes-Independent** — runs as standalone memory engine, replaces Hermes built-in memory
36|
37|**一键安装（Windows/Mac/Linux）：**
38|```bash
39|python install.py              # 全平台通用，安装+自动验证
40|# 或
41|./install.bat                  # Windows
42|bash install.sh                # Mac / Linux
43|```
44|
45|---
46|
47|## 中文介绍
48|
49|### 为什么做这个
50|
51|现有 AI 记忆方案普遍有两个问题：
52|
53|1. **只记不辨** — 对话全存，画像越来越厚。分不清你上周关心的事和这周已经不一样了
54|2. **会话即失忆** — 关掉窗口，上下文清零。说过要做的事没人追
55|
56|NexSandglass 用"阶段+偏移"解决这两个问题。
57|
58|---
59|
60|---
61|
62|我们说四件事：
63|
64|**是记住。** 每句话明文落沙，一粒不丢。（OS层全盘加密保护，无需应用层加锁）
65|
66|**是理解。** 你不用告诉它你是谁。它从沙子里把画像捞出来。你变了，它比你先发现。
67|
68|**是懂你。** 不光知道你是谁，还知道你是怎么变成今天这样的。跨阶段偏移追踪——你的轨迹，不是别人的快照。
69|
70|**是想你。** 三天前说"加守夜人"。它还记着。下次启动自己跳出来。不是存数据，是惦记你还没做的事。
71|
72|---
73|
74|## 与现有方案对比
75|
76|| 维度 | Mem0 / Letta / Holographic | NexSandglass V2.0 |
77||---|---|---|
78|| 依赖 | 向量数据库 + 多个包 | ✅ **零依赖，纯 stdlib** |
79|| 加密 | 无 / 可选 | ✅ **明文存储，OS全盘加密** |
80|| 模块化 | 单体 | ✅ **24模块，枢纽1,389行** |
81|| 决策追踪 | ❌ | ✅ **决策粒子 + 偏移率 + 幽灵决策** |
82|| 阶段感知 | ❌ | ✅ **年月+沙量双层阶段，自动切换** |
83|| 情绪感知 | ❌ | ✅ **情绪熵 + 玻璃 + 熵镜** |
84|| 场景感知 | ❌ | ✅ **多标签场景 + 关键词匹配** |
85|| 搜索 | 向量检索 | ✅ **四维扩展 + TF-IDF + 同义词** |
86|| 中英双语 | ❌ | ✅ **自动检测** |
87|| 安装 | 服务栈 | ✅ **一键 install.bat** |
88|| 体积 | 数万行 | ✅ **~5,000行 · 24模块** |
89|
90|---
91|
92|## 四大支柱 + 织线
93|
94|| 支柱 | 做什么 | 吃谁的数据 |
95||------|--------|-----------|
96|| 🧬 灵魂蒸馏 | 从沙子里捞画像，增量更新，自动切阶段 | 全部沙子 + 决策粒子 |
97|| 📊 偏移率 | 追踪决策偏移方向/幅度，跨阶段对比 | 决策粒子历史 |
98|| ⏳ 搜索滤镜 | 六维感知扩展关键词，决策粒子权重偏置 | 画像+场景+阶段+决策粒子+影子沙+织线 |
99|| 🧵 织布机 | 四支柱合成(画像+偏移+搜索+织线因果链)+矛盾检测 | 全部四支柱输出 |
100|| 🪡 织线 | 正则提取三元组，纯本地因果链，门控≥20条注入 | 对话内容 |
101|
102|**偏移率和搜索滤镜是两个独立系统**——搜索权重做偏置，偏移率做计算。
103|
104|---
105|
106|
107|
108|## Docker 一键部署
109|
110|```bash
111|docker-compose up -d
112|```
113|
114|沙漏 MCP 服务运行在 `localhost:8765`，数据持久化在 Docker volume。
115|
116|## 一键安装
117|
118|```bash
119|# 一行搞定 — 安装 + 自动验证
120|python install.py
121|
122|# 安装到自定义路径
123|export NEXSANDBASE_HOME=/your/path && python install.py
```

## 快速体验

```bash
# 写入记忆
python -c "from sandglass_log import log_message; log_message('hello', 'user')"
126|
127|# 搜索
128|python -c "from sandglass_vault import search; print(search('关键词'))"
129|
130|# 写入决策粒子
131|python -c "from decision_particles import log; log('选A还是B', 'B')"
132|
133|# 运行 Demo
134|python demo/run_demo.py
135|
136|# MCP 接入
137|# { "command": "python", "args": ["path/to/mcp_server.py"] }
138|```
139|
140|---
141|
142|## 决策粒子示例
143|
144|```
145|输入："今天想吃早饭还是午饭...还是午饭吧"
146|                       ↓
147|_detect_chain()     → [早饭, 午饭, 午饭]       # 抓全链条
148|_extract_options()  → 早饭_午饭                 # 拆选项
149|_tag_local()        → 成本观                     # 本地标签
150|_tag_llm()          → 补偿心理,经期偏好           # LLM 精炼（可选）
151|_learn()            → "补偿心理" 写入本地词库     # 下次免费命中
152|_infer_resolution() → "倾向补偿心理，下次直接给甜食" # LLM 推断（本地兜底）
153|
154|记录：早饭_午饭 | A→B→A 回到B(补偿心理) | spend | 成本观,补偿心理,经期偏好
155|```
156|
157|---
158|
159|## 文件清单
160|
161|| 文件 | 行数 | 说明 |
162||------|------|------|
163|| `sandglass_think.py` | 2,084 | L3 思考层：四支柱 + 搜索滤镜 + 脉冲感知 |
164|| `decision_particles.py` | 526 | L4 决策粒子：链条检测 + 双层标签 + LLM推断 |
165|| `sandglass_vault.py` | 396 | L2 米粒读取：倒排索引 + FTS5 + mmap |
166|| `sandglass_sqlite.py` | 128 | L2 FTS5 加速层 |
167|| `pulse.py` | 242 | 脉冲感知：识别→觉察→提醒 + 契约互动 |
168|| `emotion_vocab.py` | 184 | 情绪感知：七大情绪 + 动态词库 |
169|| `plugin.py` | 44 | L1 沙漏写入：明文追加 + O_EXCL锁 + Gateway hook |
170|| `sandglass_log.py` | 46 | 通用落沙接口 |
171|| `nightwatch.py` | 68 | 守夜人：沙漏完整性检查 |
172|| `mcp_server.py` | 201 | MCP 接入 |
173|| `nexsandglass.py` | 128 | TTY 终端拦截 |
174|| `test_smoke.py` | 66 | 冒烟测试 |
175|
176|---
177|
178|## 设计原则
179|
180|1. **层追加不替换** — 新层叠加，永不修改已定稿的下层
181|2. **L1 只落用户消息** — AI 回复不进沙漏
182|3. **本地优先，LLM 增强** — 没 API Key 一样能跑，有 Key 更精彩
183|4. **决策是链条不是单点** — A→B→C→回到A，取最后一个才是真决策
184|5. **改了A必须同步B** — 改名/改签名后全项目 grep
185|6. **极简注入** — 每轮~59token(四层问答式)，LLM按需sandglass_search查全文
186|
187|---
188|
189|## 版本历程
190|
191|### V1.x — 奠基 (2026-06)
192|```
193|V1.0→V1.6: 偏移率·搜索滤镜·情绪感知·决策粒子·回音折·影子沙·织布机·场景系统
194|核心能力全部建立：从"记住对话"到"理解你是谁"
195|```
196|
197|### V2.0 — 架构定型 (2026-06)
198|```
199|God Module 拆分(3628→1389行) + 信号链路全通 + 阶段系统(4阶段) + L1/L2封框冻结
200|从"能跑"到"可独立安装运行"
201|```
202|
203|### V2.1→V2.3 — 稳定化 (2026-06)
204|```
205|冷热分层·路径统一·MCP 11工具·heartbeat轮转·loop-memory-store
206|16模块全覆盖，零硬编码路径
207|```
208|
209|### V2.8→V2.9.9「极简注入」(2026-06)
210|```
211|四路并发搜索 + 明文落沙 + density×trust统一公式
212|Hermes内存关闭·沙漏独立注入·织线知识图谱·Docker一键部署
213|四层问答式注入(236字符/59token)·画像增量管道·织线门控
214|11Bug修复·静默异常可见·双审流水线
215|```
216|---
217|
218|## 性能基准
219|
220|| 层 | 操作 | 耗时 |
221||----|------|------|
222|| **L1 写** | 单次落沙（明文追加+O_EXCL锁+影子沙索引） | **2.1ms** |
223|| | 批量10条 | 22.2ms (2.2ms/条) |
224|| **L2 搜** | FTS5搜索 | **1.2ms** |
225|| | idx精排 | 2.2ms |
226|| | 时间轴 | 2.9ms |
227|| | 最近5条 | 0.5ms |
228|| **L3 思** | 综合偏移率 | **0.5ms** |
229|| | 语义搜索 | 0.6ms |
230|| | 织布机 | 1.5ms |
231|| | 决策链条检测 | 2.8ms |
232|| | 情绪感知 | 0.5ms |
233|
234|> 测试环境：3549条沙子 · Windows 10 · i5-8265U · Python 3.11
235|