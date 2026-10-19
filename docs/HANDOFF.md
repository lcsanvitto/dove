# Handoff do Dove — 2026-10-19

Para uma sessão nova retomar sem reexplicar nada. Estado detalhado: [`docs/ROADMAP.md`](ROADMAP.md).

## Contexto
- Dove: canal A2A local e global entre agentes (arquivos JSON em `~/.a2a`, CLI `a2a`, painel `dove`), só stdlib do Python.
- Usuário: Luiz, no Windows (`C:\Users\Dell`); projetos em `C:\Users\Dell\Cowork\Codigo` (ex.: `lagu`).
- Também usa uma VPS Ubuntu 24.04 e uma máquina com Omarchy (canal entre máquinas ainda não existe).
- Agentes no canal: `claude` (Claude Code), `codex` (Codex), `hermes` (Hermes).
- Fase atual: Fase 3 (orquestrador/vigia). Feitos 0+1, 2, 4, 5, 6, 10, 13; em andamento 3 e 8; próximos 7, 9, 11; 12 pendente.

## Regras do projeto
- Só stdlib.
- **NÃO mexer em `ui/`**: parte visual pausada; o Claude Design cuida só da estética, quando o Luiz retomar.
- `DOVE_VERSION` fica `"0.6.0"` enquanto a UI estiver pausada (a UI compara a versão exata e mostra a faixa "servidor desatualizado").
- Comportamento existente não muda sem aval do Luiz.
- Tudo que executa agentes, gasta dinheiro, muda o envelope ou o `~/.a2a` precisa de aval do Luiz. Já aprovados: etapas 0–11 da Fase 3 (a 12 não).
- Workers trabalham em worktrees `/home/user/dove-wt/<nome>` com branch própria; rebase só dos próprios commits; rodar os testes completos (`python3 tests/test_a2a.py`); push em `main` sem force.
- Commits terminam com as linhas `Co-Authored-By:` / `Claude-Session:` usadas no repo.

## Próximos passos

**Etapa 7 — vigia real, só Claude, `a2a watch --once` iniciado à mão**
- Usa `watch_plan()` (etapa 3) + `run_agent()`/`resolve_runner()` (etapa 6); plugar `WATCH_RUNNERS` em `real_runner_argv()`.
- Linha de comando do claude: `-p --output-format stream-json --verbose --permission-mode dontAsk --permission-prompts none --allowedTools <tabela> --max-turns N --max-budget-usd <run_budget_cap()> --session-id <run_id>`.
- cwd = cópia de trabalho do agente; prompt de `a2a prompt` via stdin; env `A2A_RUNNER` e `A2A_RUN_ID`.
- Depois de rodar, `parse_run_usage()` (etapa 8) grava o usage no registro do run.
- Ajustar `loop_runs()` para **não** contar runs `refused` como "já acionados".
- Só acorda por conversas iniciadas pelo humano. Sem `--bare` (usa a assinatura).
- Teste: executor falso valida a linha de comando exata; teste manual acompanhado pelo Luiz.

**Etapa 9 — Codex no vigia**
- `codex exec --json -s workspace-write -C <cópia> --add-dir <A2A_HOME> -`.
- Exige `[windows] sandbox` configurado (verificado pelo `watch check`).
- O Codex não consegue commitar na cópia (gitdir read-only): entrega mudanças sem commit e reporta no canal.

**Etapa 11 — orquestrador**
- Só ferramentas de leitura + `a2a send/brief/read/status/fact`.
- A recusa por `A2A_RUNNER` já protege as ações humanas.
- Tique só quando o bus muda; entra nos tetos globais de `a2a loops`.
- Usa `a2a fact` para o estado do projeto; modelo barato na rotina (`a2a models suggest`).

**Etapa 12 — Hermes**: aguardando o Luiz definir a contenção (sem sandbox de SO; `approvals.mode`).

**Depois**: atualizar o ROADMAP; roteiro de ativação para o Luiz no Windows; canal entre máquinas (VPS/Omarchy); retomada visual com o Claude Design; qLink.

## Roteiro de ativação na máquina do Luiz (PowerShell)
```powershell
cd C:\Users\Dell\dove
git pull
powershell -ExecutionPolicy Bypass -File install.ps1 -Instructions
# abrir um PowerShell novo
a2a instructions status
cd C:\Users\Dell\Cowork\Codigo\lagu
a2a project which
a2a watch check --project lagu
a2a cost --since 7d
a2a models init --from luiz
a2a worktree create --project lagu --agent claude --from luiz
a2a worktree create --project lagu --agent codex --from luiz
dove   # painel
```

## Decisões registradas
- token-optimizer não adotado.
- `a2a map` adiado até medir com `a2a cost`.
- Instruções globais (`a2a instructions`) em vez de AGENTS.md por repositório (PR lagu #38 fechado).
- Hermes sem instruções globais por padrão.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor não adotados.

## Onde estão as coisas
- Propostas: `docs/propostas/`.
- Pesquisa de economia de tokens: branch `pesquisa/economia-tokens`.
- Proposta da Fase 3: branch `proposta/fase3-orquestrador`.
