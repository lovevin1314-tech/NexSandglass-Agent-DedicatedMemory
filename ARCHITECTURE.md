# NexSandglass V2.10 架构简报 — 供审查者参考

## 五层架构
```
L0 会话: pulse(脉冲) · nightwatch(守夜人)
L1 存储: sandglass.txt(明文落沙) · sandglass_log
L2 搜索: shadow_sand(影子沙<1ms) · FTS5 · IDX倒排 · search_router(四路并发)
L3 思维: sandglass_think(枢纽) → persona_l3/offset_l3/emotion_l3/scene_l3/weave_l3
织线:   weavethread(正则三元组·零LLM) → weave_l3(织布机四支柱合成)
注入:   memory_provider → system_prompt_block(四层问答式·59token)
```

## 关键依赖图 (马云已验证)
```
sandglass_think ← 被14个文件依赖(核心枢纽)
  ├── persona_l3  ← sandglass_think/sandglass_mcp/emotion_l3/offset_l3/scene_l3
  ├── weave_l3    ← sandglass_think/memory_provider/offset_l3
  │   └── weavethread  ← weave_l3/memory_provider/sandglass_log/sandglass_mcp
  └── memory_provider ← 零入度(顶层注入器)
```

## 每轮对话数据流
```
用户消息 → pulse() → sandglass_log → shadow_sand + wthread_store
                ↓
LLM调用前 ← system_prompt_block() ← 四层注入(59token)
  ├── 【你是谁】    search_filter → persona_context + scene
  ├── 【往哪走】    comprehensive_offset + 决策 + 矛盾检测
  ├── 【怎么变】    wthread_weave (门控≥20)
  └── 【没做完】    待办 + 纪律
```

## 设计铁律 (不可妥协)
1. 零外部依赖: Python stdlib + SQLite
2. 极简注入: 每轮~59token, LLM按需sandglass_search
3. L1/L2封框: 不可改
4. 层追加不替换: 新功能只能追加新层
5. 本地优先: 无API也能跑
6. 织布机中枢: 所有注入数据必须经织布机加工

## v2.9.9 改动范围
- system_prompt_block: 四层问答式
- persona_l3: 画像增量管道(阈值30/80)
- weave_l3: 第四支柱(织线因果链) + 键名修复
- decision_particles: 词库自生长(mtime缓存+Lock)
- memory_provider: 织线注入+精简
- sandglass_think: persona_maintain(24h间隔)
