#!/usr/bin/env bash
# Demo rápido do Dove: claude <-> hermes
set -e
export A2A_HOME="$(mktemp -d)"
A2A="python3 $(dirname "$0")/../a2a.py"
$A2A init
$A2A join --agent claude
$A2A join --agent hermes
$A2A send --from claude --to hermes --project demo --kind task --body "revisar o modulo X"
echo "--- caixa do hermes ---"
$A2A inbox --agent hermes
$A2A status --agent claude --set working --project demo --note "revisando modulo X"
$A2A status --agent hermes --set blocked --project demo --note "aguardando acesso"
echo "--- quadro (modo herdr) ---"
$A2A status
echo "Caixa (A2A_HOME): $A2A_HOME"
