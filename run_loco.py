import os, subprocess, sys
# Read key from Hermes env
hp = os.path.expanduser("~/.hermes/.env")
with open(hp) as f:
    for line in f:
        if line.startswith("DEEPSEEK_API_KEY=***            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            os.environ["DEEPSEEK_API_KEY"] = key
            break
# Run benchmark
sys.exit(subprocess.run([sys.executable, "locomo_benchmark.py"], 
                         cwd=r"C:\Users\NeuroBase\NexSandglass").returncode)
