# Handoff do Dove — 2026-10-19

Para uma sessão nova retomar sem reexplicar nada. Estado detalhado: [`docs/ROADMAP.md`](ROADMAP.md).

## Contexto
- Dove: canal A2A local e global entre agentes (arquivos JSON em `~/.a2a`, CLI `a2a`, painel `dove`), só stdlib do Python.
- Usuário: Luiz, no Windows (`C:\Users\Dell`); projetos em `C:\Users\Dell\Cowork\Codigo` (ex.: `lagu`).
- Também usa uma VPS Ubuntu 24.04 e uma máquina com Omarchy (canal entre máquinas ainda não existe).
- Agentes no canal: `claude` (Claude Code), `codex` (Codex), `hermes` (Hermes).
- Fase atual: Fase 3 (orquestrador/vigia). Feitos 0+1, 2, 3 (75c979d), 4, 5, 6, 7 (396cfd5), 8 (7fca4c3), 10, 13, 14 (`assignee`, 38d8b13 — emenda ao 7); 9 e 11 livres pra seguir (dependiam só do 7); 12 aceito com risco (desligado por padrão). Aprovado em 2026-10-19: 15 (`parent`, junto com o 11). O 7 foi feito **sem** esperar o 14 (decisão do Luiz, 2026-10-19: "Comitar a 7 como está agora"); o 14 entrou depois como emenda — o vigia agora acorda só o `assignee` quando ele está definido, e todo participante elegível quando não está (como antes).

## Regras do projeto
- Só stdlib.
- **NÃO mexer em `ui/`**: parte visual pausada; o Claude Design cuida só da estética, quando o Luiz retomar.
- `DOVE_VERSION` fica `"0.6.0"` enquanto a UI estiver pausada (a UI compara a versão exata e mostra a faixa "servidor desatualizado").
- Comportamento existente não muda sem aval do Luiz.
- Tudo que executa agentes, gasta dinheiro, muda o envelope ou o `~/.a2a` precisa de aval do Luiz. Já aprovados: etapas 0–11 da Fase 3; a 12 com risco aceito pelo Luiz em 2026-10-19 (desligada por padrão, opt-in explícito). A 7 está feita (396cfd5); a 14 (`assignee`) está feita (38d8b13, emenda ao 7); a 15 (`parent`) foi aprovada em 2026-10-19 (junto com a 11).
- Workers trabalham em worktrees `/home/user/dove-wt/<nome>` com branch própria; rebase só dos próprios commits; rodar os testes completos (`python3 tests/test_a2a.py`); push em `main` sem force.
- Commits terminam com as linhas `Co-Authored-By:` / `Claude-Session:` usadas no repo.

## Próximos passos

**Etapa 7 — vigia real, só Claude, `a2a watch --once` iniciado à mão** · **FEITO** · 396cfd5
- Usa `watch_plan()` (etapa 3) + `run_agent()`/`resolve_runner()` (etapa 6); `WATCH_RUNNERS["claude"]["argv"]` plugado em `real_runner_argv()`.
- Linha de comando do claude: `-p --output-format stream-json --verbose --permission-mode dontAsk --permission-prompts none --allowedTools <tabela> --max-turns N --max-budget-usd <run_budget_cap()> --session-id <run_id>`.
- cwd = cópia de trabalho do agente; prompt de `a2a prompt` via stdin; env `A2A_RUNNER` e `A2A_RUN_ID`.
- `"mission"` e `"usage_file"` (Hermes) gravados nos registros de run; `parse_run_usage()` chamado logo depois de `run_agent()`.
- `--max-budget-usd` vem de `run_budget_cap()`; se `budget_status()['exceeded']`, o run é recusado (`outcome: "refused"`, log em `budget_alerts.json`).
- `loop_runs()` não conta runs `refused` como "já acionados".
- Só acorda por conversas iniciadas pelo humano (`a2a watch --once --from <human>`). Sem `--bare` (usa a assinatura).
- Testado só com executor falso (valida a linha de comando exata); **falta o teste manual acompanhado pelo Luiz com o `claude` real** — esse é o gate real antes de automatizar o disparo.
- **Gap resolvido pela etapa 14** (38d8b13): com `assignee` definido na missão/tarefa, o vigia acorda só o responsável; sem o campo, continua acordando todo participante elegível (como antes).
- Falta fazer: a pergunta única ao `luiz` quando o gasto chegar a 80%.

**Etapa 14 — `assignee`** · **FEITO** · 38d8b13 (emenda à etapa 7, não pré-requisito; a 7 já foi feita sem ela)
- Campo opcional `assignee` em missões (`a2a mission new --assignee`) e tarefas avulsas (`a2a send --kind task --assignee`): um único agente responsável, participante registrado (nunca o humano, nunca reservado); em missão precisa estar em `--agents`, em tarefa avulsa precisa ser o destinatário (`--to`) ou, com `--to all`, qualquer agente registrado.
- Só o `assignee` marca `EM_EXECUCAO` ou `AGUARDANDO_APROVACAO` (por `--task` ou, sem ele, pela mensagem respondida via `--reply-to`); os demais participantes seguem comentando/revisando — outros estados e `mission approve`/`reject` continuam livres. O humano está sempre isento.
- O vigia (etapa 7) já acorda só o `assignee` quando definido (`watch_plan`, valendo também para `watch --once`).
- Sem o campo, nada muda no comportamento atual (testado em `assignee_fase()` e no bloco novo de `plan_fase()`, `tests/test_a2a.py`).

**Etapa 9 — Codex no vigia** (a 7 já está feita, pode seguir)
- `codex exec --json -s workspace-write -C <cópia> --add-dir <A2A_HOME> -`.
- Exige `[windows] sandbox` configurado (verificado pelo `watch check`).
- O Codex não consegue commitar na cópia (gitdir read-only): entrega mudanças sem commit e reporta no canal.

**Etapa 11 — orquestrador** (a 7 já está feita, pode seguir)
- Só ferramentas de leitura + `a2a send/brief/read/status/fact`.
- A recusa por `A2A_RUNNER` já protege as ações humanas.
- Tique só quando o bus muda; entra nos tetos globais de `a2a loops`.
- Usa `a2a fact` para o estado do projeto; modelo barato na rotina (`a2a models suggest`).

**Etapa 15 — `parent`** · aprovada (Luiz, 2026-10-19: "sim") · entra junto com a etapa 11 (depois da 7)
- Campo opcional `parent` em missões: id da missão-mãe.
- Escopo mínimo: o campo + somar o gasto das filhas no orçamento da mãe e no `a2a cost`.
- A mãe só fecha quando todas as filhas estiverem `CONCLUIDO` ou `CANCELADO`; fechar continua só humano (`require_human`).
- **Sem** automação de propagação de estado, **sem** UI de árvore.

**Etapa 12 — Hermes**: o Luiz aceitou o risco em 2026-10-19 ("quero arriscar"). Sem sandbox de SO (`approvals.mode`), então fica **desligado por padrão** e só liga com opt-in explícito.

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
- Hermes no vigia: risco aceito pelo Luiz (2026-10-19); desligado por padrão, opt-in explícito.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor não adotados.
- `assignee` (14) e `parent` (15) aprovados pelo Luiz em 2026-10-19 ("sim"). Descartados: prioridade, tags, dependências entre tarefas e qualquer coisa que o agente já leia no texto da missão.
- Etapa 7 comitada sem esperar a 14 (Luiz, 2026-10-19: "Comitar a 7 como está agora"): o vigia acorda todos os participantes elegíveis até a 14 entrar como emenda.
- Etapa 14 (`assignee`) feita (38d8b13): restrição de estado (`EM_EXECUCAO`/`AGUARDANDO_APROVACAO`) e filtro do vigia ligados só quando o campo está definido; sem ele, nada muda. Uma mensagem do humano endereçada a um participante que não é o `assignee` de uma conversa com responsável definido não aciona esse participante (leitura literal do pedido do Luiz: "só o assignee marca/é acionado").

## Onde estão as coisas
- Propostas: `docs/propostas/`.
- Pesquisa de economia de tokens: branch `pesquisa/economia-tokens`.
- Proposta da Fase 3: branch `proposta/fase3-orquestrador`.
