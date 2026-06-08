#!/usr/bin/env bash
# NexSandglass About updater
cd /c/Users/NeuroBase/.neurobase/release
curl -s --proxy http://127.0.0.1:1086 -X PATCH \
  -H "Authorization: Bearer $(echo 'protocol=https\nhost=github.com\n' | git credential fill 2>/dev/null | grep password= | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"description":"V1.3 | 是记住。是理解。是懂你。是想你。2743行零依赖。加密、阶段感知、波浪自吸收的AI记忆管家。","topics":["ai-memory","local-first","privacy","hermes-agent","mcp-server","python","stage-aware","personal-ai"]}' \
  https://api.github.com/repos/lovevin1314-tech/NexSandglass && echo "OK" || echo "FAIL"
