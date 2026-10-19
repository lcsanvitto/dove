# Handoff do Dove — 2026-10-19

Para uma sessão nova retomar sem reexplicar nada. Estado detalhado: [`docs/ROADMAP.md`](ROADMAP.md).

## Contexto
- Dove: canal A2A local e global entre agentes (arquivos JSON em `~/.a2a`, CLI `a2a`, painel `dove`), só stdlib do Python.
- Usuário: Luiz, no Windows (`C:\Users\Dell`); projetos em `C:\Users\Dell\Cowork\Codigo` (ex.: `lagu`).
- Também usa uma VPS Ubuntu 24.04 e uma máquina com Omarchy (canal entre máquinas ainda não existe).
- Agentes no canal: `claude` (Claude Code), `codex` (Codex), `hermes` (Hermes).
- Fase atual: Fase 3 (orquestrador/vigia). Feitos 0+1, 2, 3 (75c979d), 4, 5, 6, 8 (7fca4c3), 10, 13; 7 bloqueado — aguardando decisão do Luiz; 9 e 11 dependem do 7; 12 aceito com risco (desligado por padrão). Aprovados em 2026-10-19: 14 (`assignee`, antes do 7) e 15 (`parent`, junto com o 11). Ordem: 14 → 7 → (9, 11 + 15) → 12 → 16. Aprovado também o 16 (controle remoto pelo celular), que só começa depois de todos esses.

## Regras do projeto
- Só stdlib.
- **NÃO mexer em `ui/`**: parte visual pausada; o Claude Design cuida só da estética, quando o Luiz retomar.
- `DOVE_VERSION` fica `"0.6.0"` enquanto a UI estiver pausada (a UI compara a versão exata e mostra a faixa "servidor desatualizado").
- Comportamento existente não muda sem aval do Luiz.
- Tudo que executa agentes, gasta dinheiro, muda o envelope ou o `~/.a2a` precisa de aval do Luiz. Já aprovados: etapas 0–11 da Fase 3; a 12 com risco aceito pelo Luiz em 2026-10-19 (desligada por padrão, opt-in explícito). A 7 aguarda decisão do Luiz antes de começar; a 14 (`assignee`) e a 15 (`parent`) foram aprovadas em 2026-10-19 (14 antes da 7; 15 junto com a 11).
- Workers trabalham em worktrees `/home/user/dove-wt/<nome>` com branch própria; rebase só dos próprios commits; rodar os testes completos (`python3 tests/test_a2a.py`); push em `main` sem force.
- Commits terminam com as linhas `Co-Authored-By:` / `Claude-Session:` usadas no repo.

## Próximos passos

**Etapa 14 — `assignee`** · aprovada (Luiz, 2026-10-19: "sim") · **pré-requisito da etapa 7** (fazer antes)
- Campo opcional `assignee` em missões e tarefas: um único agente responsável.
- Só o `assignee` marca `EM_EXECUCAO` ou `AGUARDANDO_APROVACAO`; os demais participantes só comentam ou revisam.
- O vigia (etapa 7) acorda só o `assignee`, não todos os participantes (menos gasto, menos risco de loop, dono claro). A especificação da etapa 7 abaixo não muda.
- Sem o campo, nada muda no comportamento atual.

**Etapa 7 — vigia real, só Claude, `a2a watch --once` iniciado à mão** · bloqueado — aguardando decisão do Luiz
- Usa `watch_plan()` (etapa 3) + `run_agent()`/`resolve_runner()` (etapa 6); plugar `WATCH_RUNNERS` em `real_runner_argv()`.
- Linha de comando do claude: `-p --output-format stream-json --verbose --permission-mode dontAsk --permission-prompts none --allowedTools <tabela> --max-turns N --max-budget-usd <run_budget_cap()> --session-id <run_id>`.
- cwd = cópia de trabalho do agente; prompt de `a2a prompt` via stdin; env `A2A_RUNNER` e `A2A_RUN_ID`.
- Gravar `"mission"` e `"usage_file"` (Hermes) nos registros de run.
- Chamar `parse_run_usage()` (etapa 8, já no `main`) logo depois de `run_agent()`.
- `--max-budget-usd` vem de `run_budget_cap()`; se `budget_status()['exceeded']`, recusar o run.
- Ajustar `loop_runs()` para **não** contar runs `refused` como "já acionados".
- Falta fazer: a pergunta única ao `luiz` quando o gasto chegar a 80%.
- Só acorda por conversas iniciadas pelo humano. Sem `--bare` (usa a assinatura).
- Teste: executor falso valida a linha de comando exata; teste manual acompanhado pelo Luiz.

**Etapa 9 — Codex no vigia** (depende da 7)
- `codex exec --json -s workspace-write -C <cópia> --add-dir <A2A_HOME> -`.
- Exige `[windows] sandbox` configurado (verificado pelo `watch check`).
- O Codex não consegue commitar na cópia (gitdir read-only): entrega mudanças sem commit e reporta no canal.

**Etapa 11 — orquestrador** (depende da 7)
- Só ferramentas de leitura + `a2a send/brief/read/status/fact`.
- A recusa por `A2A_RUNNER` já protege as ações humanas.
- Tique só quando o bus muda; entra nos tetos globais de `a2a loops`.
- Usa `a2a fact` para o estado do projeto; modelo barato na rotina (`a2a models suggest`).

**Etapa 15 — `parent`** · aprovada (Luiz, 2026-10-19: "sim") · entra junto com a etapa 11 (depois da 7)
- Campo opcional `parent` em missões: id da missão-mãe.
- Escopo mínimo: o campo + somar o gasto das filhas no orçamento da mãe e no `a2a cost`.
- A mãe só fecha quando todas as filhas estiverem `CONCLUIDO` ou `CANCELADO`; fechar continua só humano (`require_human`).
- **Sem** automação de propagação de estado, **sem** UI de árvore.

**Etapa 16 — Controle remoto pelo celular** · aprovada (Luiz, 2026-10-19: "Sim", **MUITO IMPORTANTE**)
Proposta: [`docs/propostas/2026-10-19-orca-controle-remoto-mobile.md`](propostas/2026-10-19-orca-controle-remoto-mobile.md) (pesquisa do Orca + design).
- **Direção:** o painel continua em `127.0.0.1` e é publicado com `tailscale serve` (HTTPS só dentro da tailnet). **NUNCA** Funnel, Cloudflare Tunnel, ngrok nem `0.0.0.0`. Sem relay, sem WebSocket, sem serviço de terceiros, só stdlib. O Orca (stablyai/orca, MIT, TypeScript) é só fonte de ideias.
- **Papel restrito "remote":** só para Hosts de uma lista explícita `remote_hosts` (vazia = remoto desligado); tabela de rotas fail-closed; código de pareamento de uso único, válido por 5 min; token por dispositivo, revogável, guardado com hash em `~/.a2a/devices.json` (0600).
- **O celular pode:** ler o status, **STOP** (sempre permitido), concluir missão e enviar mensagem (estes dois são permissões por dispositivo, desligadas por padrão).
- **Só no desktop:** git push/merge/commit, remover cópias de trabalho/projetos/agentes, retomar depois do STOP, orçamento, configuração, gestão de dispositivos.
- **Lacuna conhecida, corrigir PRIMEIRO:** hoje `GET /` entrega o token do processo a qualquer requisição que passe na checagem de Host, e `/api/state` e `/api/messages` não pedem token; a checagem de Origin só aceita `http://`. Só é seguro porque o painel é loopback. Precisa ser corrigido antes de expor qualquer coisa.
- **Sub-passos em ordem** (detalhes na proposta, seção 7):
  - 0: teste manual do `tailscale serve`, sem código.
  - 1: `remote_hosts`.
  - 2: papel + tabela de rotas fail-closed + testes.
  - 3: `a2a remote pair/list/revoke` + arquivo de dispositivos. **Precisa de aval explícito do Luiz.**
  - 4: estado reduzido, só leitura.
  - 5: página móvel `ui/remote.html` (precisa do Claude Design; `ui/` está pausada).
  - 6: STOP remoto + log de auditoria.
  - 7: permissões de missão/mensagem. **Precisa de aval explícito do Luiz.**
  - 8: revisão de segurança.
  - 9: notificação por polling.
  - 10: ntfy opcional, só texto genérico. **Precisa de aval explícito do Luiz.**
  - 11: QR em texto, opcional.
- **Dependência:** começa só **depois** dos passos 14, 7, 9, 12, 11 e 15, porque mexe no `a2a.py` (evita conflitos).

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
- Controle remoto pelo celular (16): aprovado pelo Luiz em 2026-10-19 ("Sim", MUITO IMPORTANTE); `tailscale serve`, nunca Funnel/túnel público; sub-passos 3, 7 e 10 pedem aval explícito.
- `assignee` (14) e `parent` (15) aprovados pelo Luiz em 2026-10-19 ("sim"). Descartados: prioridade, tags, dependências entre tarefas e qualquer coisa que o agente já leia no texto da missão.

## Onde estão as coisas
- Propostas: `docs/propostas/` (controle remoto mobile: `docs/propostas/2026-10-19-orca-controle-remoto-mobile.md`).
- Pesquisa de economia de tokens: branch `pesquisa/economia-tokens`.
- Proposta da Fase 3: branch `proposta/fase3-orquestrador`.
