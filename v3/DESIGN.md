# L1 涟漪架构 · 设计定稿

> 2026-06-18 封框。164行，4文件，3神经元，跨平台，零依赖外部LLM。

## 涟漪原理

```
put("沙子")
  ├── 📜 记忆  写 sandglass.txt
  ├── 🔍 感知  读 sandglass.txt → 增量 Bigram 索引
  └── 🧠 认知  读 sandglass.txt → jieba 分词 + 正则关系 + 三元组
```

不是事件总线。三神经元盯同一片水（sandglass.txt），各自独立感知水位变化，各自记账。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `sandglass_paths.py` | 2 | `_NB` 路径常量 |
| `memory_neuron.py` | 14 | `put(text, sender)` 落沙 + 连锁涟漪 |
| `perception_neuron.py` | 56 | Bigram 索引 `search(word)` → 行号 |
| `cognition_neuron.py` | 92 | `facts_by_line()` `triples_by_line()` |

## 各神经元定稿

### 📜 记忆神经元

- 换行消毒: `\r\n \n \r` → 空格
- 格式化: `ts | sender | text`
- 写文件: `with open('a') as f: f.write(line)`
- 涟漪: 写完后调 `perc_sense()` `cog_sense()`
- 零锁（单写入源）· 零加密（OS全盘加密）· 零过滤（归 L2）

### 🔍 感知神经元

- 分词: 中文 2 字滑窗，英文整词 + 60 停用词归一化
- 存储: SQLite B-tree `idx(word, line_num)`
- 水位: `MAX(line_num)` 增量索引
- 查询: `search("词")` → 行号列表
- 零判断（不判断词价值，全索引）

### 🧠 认知神经元

- 分词: jieba.cut（中文）+ 英文整词归一化
- 关系: 6 条正则（我是/我在/我用/我喜欢/我讨厌 → identity/location/tool/preference/aversion）
- 三元组: posseg 动词前后找主语宾语 → (主,谓,宾)
- 存储: SQLite `facts(line_num, category, value)` `triples(line_num, subject, verb, object)`
- 零 LLM，纯本地规则

## 设计原则

1. **涟漪不连线** — 各神经元独立读文件，不互传消息
2. **水位各自管** — 感知和认知各维护自己的 `MAX(line_num)`，多调无害
3. **单写入源** — 只有记忆写 sandglass.txt，无锁竞争
4. **L1 不加 try** — 炸就炸，守沙人兜底
5. **全产出零判断** — 感知全索引、认知全提取，L2 过滤
6. **零装饰** — 零空行、零分区注释、零函数 docstring

## 跨平台

- `os.path.join` 自动适配 Win/Mac/Linux 路径分隔符
- `encoding="utf-8"` 中英双语全通
- `jieba` 0.42.1 跨平台已安装
- SQLite WAL 模式三平台兼容

## 旧架构对照

| 旧 (sandglass_log.py) | 新 (涟漪) |
|----------------------|----------|
| 144 行一体 | 3 神经元 164 行 |
| 锁 + 加密 + 过滤 + 影子沙 + 织线全挤在 log_message | 各归各位 |
| FTS5 搜索 | Bigram 索引 |
| 正则实体提取 9% | jieba+posseg |
| 记忆写 → 影子沙 ← 织线 | 记忆写 → 感知读 → 认知读 |
