#!/usr/bin/env bash
# Instalador do Dove (Linux/macOS - Omarchy, Ubuntu VPS). Idempotente.
# Uso: ./install.sh [agente ...]   (padrao: claude codex hermes)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
command -v python3 >/dev/null 2>&1 || { echo "ERRO: python3 nao encontrado. Instale o Python 3.8+ (ex.: sudo apt install python3 / sudo pacman -S python)." >&2; exit 1; }
chmod +x "$REPO/a2a.py"
mkdir -p "$BIN"
ln -sfn "$REPO/a2a.py" "$BIN/a2a"
echo "link: $BIN/a2a -> $REPO/a2a.py"
"$BIN/a2a" init
if [ "$#" -gt 0 ]; then AGENTS=("$@"); else AGENTS=(claude codex hermes); fi
for ag in "${AGENTS[@]}"; do "$BIN/a2a" join --agent "$ag"; done
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "AVISO: $BIN nao esta no PATH. Adicione ao ~/.bashrc (ou ~/.zshrc):"
     echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
echo "Dove instalado (agentes: ${AGENTS[*]}). Atualize com: git -C \"$REPO\" pull"
echo "Teste: a2a status"
