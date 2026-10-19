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
echo "--- missao com aval de todos ---"
$A2A project add demo "$A2A_HOME"
$A2A status --agent claude --set working --project demo --context 42
$A2A mission new --project demo --title "Modulo X revisado" --agents claude,hermes --from luiz
MID=$(ls "$A2A_HOME/missions" | head -1 | sed 's/\.json//')
$A2A mission approve "$MID" --agent claude --evidence "testes ok"
$A2A mission approve "$MID" --agent hermes --evidence "revisei o diff"
$A2A mission done "$MID" --from luiz
$A2A mission list
echo "--- onde estamos ---"
$A2A summary --project demo
echo "Caixa (A2A_HOME): $A2A_HOME"
