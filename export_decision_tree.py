"""
NexSandglass — 决策树导出
==========================
输出Graphviz DOT格式或纯缩进文本
用法: python export_decision_tree.py [--dot] [output_file]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

dp_path = os.path.expanduser("~/.neurobase/decision_particles.txt")
if not os.path.exists(dp_path):
    print("决策粒子文件不存在")
    sys.exit(1)

fmt = sys.argv[1] if len(sys.argv) > 1 else "text"
out = sys.argv[2] if len(sys.argv) > 2 else None

with open(dp_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

if fmt == "--dot":
    dot = ["digraph DecisionTree {", '  rankdir=LR; node [shape=box];']
    nodes = {}
    for i, line in enumerate(lines):
        parts = line.strip().split(" | ")
        if len(parts) >= 4:
            ts, options, choice, direction = parts[0], parts[1], parts[2], parts[3]
            nodes[i] = f'  n{i} [label="{choice}\\n({direction})"];'
            if i > 0:
                dot.append(f'  n{i-1} -> n{i};')
    dot.extend(nodes.values())
    dot.append("}")
    output = "\n".join(dot)
else:
    output = "决策树\n" + "=" * 40 + "\n"
    for i, line in enumerate(lines):
        parts = line.strip().split(" | ")
        if len(parts) >= 4:
            ts, options, choice, direction = parts[0], parts[1], parts[2], parts[3]
            indent = "  " * min(i, 10)
            output += f"{indent}{i+1}. {choice} [{direction}]\n"

if out:
    with open(out, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"导出到: {out}")
else:
    print(output)
