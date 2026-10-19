#!/usr/bin/env bash
# Instalador do Dove (Linux/macOS - Omarchy, Ubuntu VPS). Idempotente.
# Uso: ./install.sh [--instructions] [agente ...]   (padrao: claude codex hermes)
#   --instructions: grava o nucleo do Dove nos arquivos globais do Claude Code e do Codex (a2a instructions install)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
command -v python3 >/dev/null 2>&1 || { echo "ERRO: python3 nao encontrado. Instale o Python 3.8+ (ex.: sudo apt install python3 / sudo pacman -S python)." >&2; exit 1; }
chmod +x "$REPO/a2a.py"
mkdir -p "$BIN"
ln -sfn "$REPO/a2a.py" "$BIN/a2a"
ln -sfn "$REPO/a2a.py" "$BIN/dove"
echo "link: $BIN/a2a -> $REPO/a2a.py"
echo "link: $BIN/dove -> $REPO/a2a.py (abre o app: dove)"
"$BIN/a2a" init
INSTRUCTIONS=0; AGENTS=()
for arg in "$@"; do
  if [ "$arg" = "--instructions" ]; then INSTRUCTIONS=1; else AGENTS+=("$arg"); fi
done
if [ "${#AGENTS[@]}" -eq 0 ]; then AGENTS=(claude codex hermes); fi
for ag in "${AGENTS[@]}"; do "$BIN/a2a" join --agent "$ag"; done
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "AVISO: $BIN nao esta no PATH. Adicione ao ~/.bashrc (ou ~/.zshrc):"
     echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
if [ "$INSTRUCTIONS" = 1 ]; then "$BIN/a2a" instructions install --agents claude,codex
else echo "Para valer em todos os projetos: a2a instructions install"; fi
echo "Dove instalado (agentes: ${AGENTS[*]}). Atualize com: git -C \"$REPO\" pull"
echo "Teste: a2a status   |   App no navegador: dove"
