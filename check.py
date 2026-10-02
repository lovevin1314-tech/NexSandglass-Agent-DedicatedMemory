"""
NexSandglass — 健康检查体温计
=============================
零依赖，只检查目录权限、数据完整性、版本兼容性
用法: python check.py
"""
import os, sys, json

def check(label, condition, detail=""):
    ok = "✅" if condition else "❌"
    print(f"  {ok} {label}" + (f": {detail}" if detail else ""))
    return condition

NB = os.path.expanduser("~/.neurobase")
SG = os.path.join(NB, "sandglass.txt")
all_ok = True

print("NexSandglass 健康检查")
print("=" * 40)

# 目录
all_ok &= check("知识库目录", os.path.isdir(NB))
all_ok &= check("沙漏文件", os.path.exists(SG), f"{os.path.getsize(SG)}字节" if os.path.exists(SG) else "缺失")

# 数据完整性
if os.path.exists(SG):
    try:
        with open(SG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        all_ok &= check("沙漏可读", True, f"{len(lines)}条记录")
        # 检查DPAPI加密标记
        encrypted = sum(1 for l in lines if "AQAAANCMnd8" in l)
        all_ok &= check("加密状态", encrypted > 0, f"{encrypted}/{len(lines)}条加密")
    except Exception as e:
        all_ok &= check("沙漏读取", False, str(e))

# 索引
idx = os.path.join(NB, "sandglass.idx")
if os.path.exists(idx):
    with open(idx) as f:
        idx_lines = [l for l in f if l.strip() and not l.startswith("#")]
    all_ok &= check("索引文件", True, f"{len(idx_lines)}条索引")
else:
    all_ok &= check("索引文件", False, "不存在（首次搜索自动重建）")

# 配置文件
for f in ["profile/user-profile.md", "memory/neurobase/personality.md", "config/environment.md"]:
    p = os.path.join(NB, f)
    all_ok &= check(f.split("/")[-1], os.path.exists(p))

# 版本
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sandglass_vault import count
    c = count()
    all_ok &= check("Vault可用", c >= 0, f"{c}条")
except Exception as e:
    all_ok &= check("Vault", False, str(e))

# 脚本完整性
scripts = ["sandglass_log.py", "sandglass_vault.py", "sandglass_think.py",
           "decision_particles.py", "emotion_vocab.py", "pulse.py"]
for s in scripts:
    p = os.path.join(NB, "scripts", s)
    all_ok &= check(s, os.path.exists(p))

print("=" * 40)
if all_ok:
    print("🎉 你的灵魂很健康")
else:
    print("⚠️ 有些问题需要处理，见上")
