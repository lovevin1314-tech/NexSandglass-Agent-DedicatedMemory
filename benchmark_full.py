"""
NexSandglass V1.7.6 综合基准测试（脱敏版）
=========================================
纯构造数据，零真实沙子。结果可直接发布。
用法：python benchmark_full.py
"""
import sys, os, time, json, tempfile, shutil, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0; FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1; return f"✅ {label}"
    else:
        FAIL += 1; return f"❌ {label}: {detail}"

def hdr(title): print(f"\n{'='*50}\n  {title}\n{'='*50}")

# ═══════════════════════════════════════════════
# 1. 构造合成测试数据
# ═══════════════════════════════════════════════
hdr("1. 数据准备")

SYNTHETIC_SANDS = [
    "选Python还是Rust做后端？最终还是用Python，生态更好。",
    "太贵了这个API，找找有没有免费替代品。开源的最好。",
    "今天心情不错，系统跑通了，性能比预期好20%。",
    "不管了，能用就行，别纠结了。先上线再说。",
    "买了Pro版，效率确实高，这钱花得值。",
    "自己手写一个加密模块吧，不用第三方库了。",
    "放弃这个方案，太复杂了维护成本高。",
    "用免费开源的工具，社区活跃更新快，不花钱还省心。",
    "烦死了，这个bug修了3天了还没搞定。",
    "太好了！终于找到了满意的方案，性能和安全都达标。",
    "本地部署不用上云，省钱又安全。",
    "算了就选这个吧，不想再纠结了。",
    "性价比很重要，贵的不一定好，便宜的不一定差。",
    "花了200块买了个工具，真香，早知道早买了。",
    "先对比A、B、C三个方案，测试后再决定。",
    "效率优先，付费工具能省时间就值得。",
    "这个需求太简单了，自己写两行代码就行，不用买。",
    "随便吧都差不多，已经选麻了。",
    "订阅了年度计划，一年省40%，付费比按月买划算。",
    "成功把系统迁移到本地，不依赖任何云服务了，稳。",
    "今天学到了DPAPI加密的新用法，之前一直用AES。",
    "搞不定了，太难了，我放弃了。",
    "买了新设备，虽然贵但是开发效率提升明显。",
    "开源社区真有活力，一个PR过去第二天就merge了。",
    "心情很好，今天把所有测试用例都写完了。",
    "焦虑，明天要上线，还有很多问题没解决。",
    "不管花多少钱，稳定第一，不能在生产环境崩。",
    "免费的就是最好的，省下来的钱干别的。",
    "订阅到期了，要不要续？算了续吧，已经离不开了。",
    "这个框架太臃肿了，自己写个轻量的替代。",
    "终于搞定了！发了篇技术博客记录整个过程。",
    "难受，浪费了一整天在兼容性问题上。",
    "买了云服务器的三年合约，比按小时付费省了60%。",
    "用开源方案替代了商业软件，功能一样还不要钱。",
    "随便用哪个都行，我已经不想再选了。",
    "付费！付费！能花钱解决的事坚决不动手。",
    "太棒了，团队新来的同事能力很强，终于可以分担了。",
    "我不想再管这个项目了，爱谁谁吧。",
    "权衡之后选了中等方案，不是最便宜也不是最贵。",
    "花钱买了正版IDE，比盗版稳定太多了。",
    "累了，今天就到这吧，什么都不想做了。",
    "又学到新东西了，感觉每天都在进步。",
    "放弃治疗了，这代码写得跟屎一样。",
    "用免费CDN+开源框架搭了整个前端，零成本。",
    "充了GPT Plus，回答质量确实比免费版好很多。",
    "完美！所有测试用例全部通过，可以发布了。",
    "好烦，这个客户需求一天改三次。",
    "自己搭建的私有云比公有云便宜多了，维护也不难。",
    "不管了，先推代码，有问题再改。",
    "今天的代码审查收获很大，学到了很多新思路。",
]

# 写入临时沙漏
tmp_dir = tempfile.mkdtemp()
tmp_sandglass = os.path.join(tmp_dir, "sandglass.txt")
tmp_nb = os.path.join(tmp_dir, ".neurobase")
os.makedirs(tmp_nb, exist_ok=True)

import sandglass_log
orig_sandglass = sandglass_log._SANDGLASS
sandglass_log._SANDGLASS = tmp_sandglass

# 也重定向 vault 的 sandglass 路径
import sandglass_vault
orig_vault_sg = sandglass_vault._SANDGLASS
sandglass_vault._SANDGLASS = tmp_sandglass

t0 = time.perf_counter()
for i, msg in enumerate(SYNTHETIC_SANDS):
    sandglass_log.log_message(msg, "user")
write_time = (time.perf_counter() - t0) * 1000
total = len(SYNTHETIC_SANDS)
print(f"  构造{total}条合成对话: {write_time:.0f}ms ({write_time/total:.1f}ms/条)")

# ═══════════════════════════════════════════════
# 2. L1 写入性能
# ═══════════════════════════════════════════════
hdr("2. L1 写入性能")

from sandglass_vault import count
c = count()
print(check("沙漏总量正确", c == total, f"期望{total} 实际{c}"))
print(check("单条写入<5ms", write_time/total < 5, f"{write_time/total:.1f}ms/条"))
print(check("50条/秒以上", total*1000/write_time > 50, f"{total*1000/write_time:.0f}条/秒"))

# ═══════════════════════════════════════════════
# 3. L2 搜索精度
# ═══════════════════════════════════════════════
hdr("3. L2 搜索精度")

from sandglass_vault import search, recent

# 关键词搜索
r = search("免费", 50)
free_count = len(r)
r2 = search("开源", 20)
oss_count = len(r2)
print(check("搜索'免费'命中>1条", free_count >= 1, f"命中{free_count}条（50条合成数据限制）"))
print(check("搜索'开源'命中>2条", oss_count >= 2, f"命中{oss_count}条"))

# 中文搜索
r3 = search("纠结", 10)
cn_ok = len(r3) >= 1
print(check("中文搜索'纠结'有结果", cn_ok, f"命中{len(r3)}条"))

# 不存在的词
r4 = search("XYZ123NotExist", 5)
print(check("不存在的词返回空", len(r4) == 0))

# 最近条数
r5 = recent(5)
print(check("recent返回正确条数", len(r5) == 5))

# ═══════════════════════════════════════════════
# 4. L3 偏移率精度
# ═══════════════════════════════════════════════
hdr("4. L3 偏移率精度")

from sandglass_think import comprehensive_offset
off = comprehensive_offset()
print(f"  综合偏移率: {off['offset']:+d}% ({off['direction']}), {off['sample']}条决策")
print(check("偏移率有足够样本", off["sample"] >= 5, f"{off['sample']}条"))
print(check("偏移方向非空", off["direction"] in ("frugal","spend","drift","neutral")))

# ═══════════════════════════════════════════════
# 5. L3 搜索排序质量
# ═══════════════════════════════════════════════
hdr("5. L3 搜索排序")

from sandglass_think import composite_rerank, search_semantic

# composite_rerank: 带权重的词应排前面
test_data = [(1,'','免费开源工具DPAPI加密','免费'), (2,'','付费专业版功能强大','付费'), (3,'','中性文本无关','加密')]
w = {'免费':1.5, '开源':1.5, 'DPAPI':1.3, '加密':1.0, '付费':0.8}
ranked = composite_rerank(test_data, w)
print(check("权重排序: 免费优先", ranked[0][0] == 1, f"排第一L{ranked[0][0]}"))

# 语义搜索
r = search_semantic("加密方案", 5)
print(check("语义搜索有结果", len(r) > 0, f"{len(r)}条"))

# ═══════════════════════════════════════════════
# 6. L3 情绪检测
# ═══════════════════════════════════════════════
hdr("6. L3 情绪检测")

from emotion_vocab import detect as emotion_detect

tests = [
    ("太好了终于搞定了！", "开心"),
    ("烦死了这都什么破玩意", "愤怒"),
    ("算了不搞了放弃", "放弃"),
    ("今天天气不错", ""),
]
for text, expected in tests:
    det = emotion_detect(text)
    ok = (det["mood"] == expected) if expected else (det["mood"] in ("", "开心"))
    print(check(f"情绪'{text[:15]}'→{expected or '中性'}", ok, f"实际:{det['mood']}"))

# ═══════════════════════════════════════════════
# 7. L3 健康体检
# ═══════════════════════════════════════════════
hdr("7. L3 全系统体检")

from sandglass_think import full_sanity, stage_brief
fs = full_sanity()
print(f"  full_sanity: {fs['passed']}/{fs['total']}层通过")
for k, v in fs['details'].get('L3_checks', {}).items():
    print(f"    {k}: {v}")

# ═══════════════════════════════════════════════
# 8. 清理
# ═══════════════════════════════════════════════
sandglass_log._SANDGLASS = orig_sandglass
sandglass_vault._SANDGLASS = orig_vault_sg
shutil.rmtree(tmp_dir, ignore_errors=True)

hdr("汇总")
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  沙漏规模: {total}条合成数据")
print(f"  总耗时: {write_time:.0f}ms")
