# Roadmap do Dove

> **Sessão nova? Comece por [`docs/HANDOFF.md`](HANDOFF.md)** — contexto, regras e próximos passos para retomar sem reexplicar.

Estado em 2026-10-19 · base `main` em f48f101.

## 1. O que é o Dove
Canal A2A local e global: os agentes (`claude`, `codex`, `hermes`) conversam e dividem trabalho por arquivos JSON em `~/.a2a`, sem nuvem.
Os agentes usam a CLI `a2a`; o Luiz usa o painel `dove` no navegador.
Só a stdlib do Python; funciona no Windows, no Linux e no macOS.

## 2. Divisão de trabalho
| Quem | Faz |
|---|---|
| **Claude Code** | Código, arquitetura, propostas técnicas, testes, segurança e decisões técnicas. Leva as decisões ao Luiz com uma recomendação. |
| **Claude Design** | **Somente** estética e experiência visual do painel (`ui/`), quando o Luiz retomar a parte visual. Hoje **PAUSADA**. |
| **Luiz** | Aprova o que é sensível: execução de agentes, gasto, mudanças no `~/.a2a` ou no envelope, merges e deploys. |

## 3. Concluído
**Canal básico**
- dbcacc0 canal A2A local e global · e90fc33 README, LICENSE, exemplos e teste de fumaça

**Modo herdr**
- e458927 estado dos agentes, quadro e `wait --until` · 0ebba74 auto-status, `a2a log` e painel web local
- 46c1286 instaladores (Windows/Linux) e `a2a onboard` · 14a2042 shim do `a2a` para Git Bash

**Painel**
- 51592b3 Fase 1: app `dove` estilo herdr (projetos, missões com aval, contexto por agente)
- 4b450ad robustez: erros visíveis, add/scan no Windows, remover projeto
- e33925b navegador de pastas, + agentes, conversas em tabela, doctor e versão

**Fase 2 (backend)**
- 63e3eba git e cópias de trabalho (worktrees) por agente via CLI/API

**Interface enxuta para agentes**
- 17ccad1 `a2a brief` (**−72,9%** de tokens) · 6a181dd `read --compact` · a33fb09 `wait` só relê o bus quando ele muda
- 0f646c9 `a2a archive` (com `--restore`) · e2a5975 `index.json` (rebuild/check) · baaf174 `send --file` (**−96%**)
- `panel_state` com índice + archive em 2.000 mensagens: **~40 ms → ~5 ms**

**Economia de tokens**
- ce8c492 proposta · 31da61a núcleo curto do AGENTS.md (**189 vs 1.117 tokens**) · b4fd58f `onboard` com guia completo
- 6c94ab6 `measure_tokens` (medição reprodutível) · e3b3d80 `a2a prompt` (prefixo estável com hash)
- 73f67ad / 737f595 `a2a instructions`: núcleo nos arquivos globais dos agentes, check/uninstall, `onboard --check`
- 8748075 `a2a fact`: memória do projeto com validade (**M3 −74,8%**)

## 4. Em andamento — Fase 3 (orquestrador)
Proposta: `docs/propostas/2026-10-19-fase3-orquestrador.md` no branch `proposta/fase3-orquestrador`.
Todos os passos têm aval do Luiz; o 12 foi aceito com risco em 2026-10-19 (desligado por padrão, opt-in explícito).

| Passo | Item | Estado |
|---|---|---|
| 0+1 | Segurança: `mission done` só humano, `--from` obrigatório, `vigia` reservado, `A2A_RUNNER` nunca age como humano | **FEITO** · 67d2d37 |
| 2 | `a2a loops` (prevenção de loop entre agentes automáticos) | **FEITO** · 2a8485d |
| 3 | `a2a watch plan` / `--dry-run` (+ `git add`/`git commit` na allowlist do Claude só na própria cópia; proíbe rebase/reset/checkout/switch/`branch -D`/clean) | **FEITO** · 75c979d |
| 4 | `a2a cost` (lê os registros do Claude/Codex/Hermes, só leitura) | **FEITO** · 247ef1f |
| 5 | `a2a watch check` | **FEITO** · 37be0d7 |
| 6 | Supervisor: `STOP`, travas, timeout, Job Object | **FEITO** · 81a0e14 |
| 7 | Vigia real, só com o `claude`, iniciado à mão | **FEITO** · 396cfd5 (+ filtro por `assignee` do passo 14, 38d8b13) |
| 8 | Orçamento: `parse_run_usage`, `run_budget_cap`, `budget_status`, `budget_alerts`, `a2a mission budget`, `a2a cost budget`/`--budget`, `budgets.json`, `a2a watch usage` | **FEITO** · 7fca4c3 |
| 9 | Codex no vigia (sandbox do Windows; sem commit) | **FEITO** · 96e904c |
| 10 | `a2a models` (roteamento de modelo) | **FEITO** · 97ce044 |
| 11 | Orquestrador (só leitura + mensagens) | **FEITO** · fc7eca4 (tique periódico e demais gatilhos pendentes: vigia contínuo ainda não existe) |
| 12 | Hermes no vigia (opt-in) | **FEITO** · f95a7b0 (risco aceito pelo Luiz, 2026-10-19: "quero arriscar"; desligado por padrão) |
| 13 | Política de subagentes | **FEITO** · 898c637 (+ c65d148 teste determinístico) |
| 14 | `assignee` (responsável único) em missões e tarefas | **FEITO** · 38d8b13 (emenda ao passo 7) |
| 15 | `parent` (missão-mãe) em missões | **FEITO** · f48f101 |
| 16 | Controle remoto pelo celular (`tailscale serve`, papel `remote`) | **APROVADO** (Luiz, 2026-10-19: "Sim", MUITO IMPORTANTE) · só depois de 14, 7, 9, 12, 11 e 15 |
| 17 | Memória de projeto: ideias do Hindsight (`a2a fact`/`brief`) | **APROVADO** (Luiz, 2026-10-19: "sim") · só depois do 16 |

Ordem de dependência (revista em 396cfd5): o passo 7 foi feito **sem esperar** o 14 (decisão do Luiz, 2026-10-19: "Comitar a 7 como está agora"). O passo 14 entrou depois (38d8b13) como **emenda** ao 7, não como pré-requisito: hoje o vigia acorda **só o `assignee`** quando ele está definido numa missão ou tarefa; sem o campo, continua acordando todo participante elegível, como antes. O passo 9 (96e904c) já usou a 7 atual para liberar o codex. O passo 12 (f95a7b0) acrescentou o opt-in do hermes, independente dos demais. O passo 11 (fc7eca4) só propõe e manda mensagem — não toca em missão nem em `parent` — então não precisou esperar a 15. O passo 15 (f48f101) fechou os passos da Fase 3 (0+1 a 15 **FEITOS**); restam 16 e 17.

Ordem restante: **16 → 17** (17 só depois do 16).

**Passo 9 — Codex no vigia** (**FEITO**, 96e904c):
- `codex exec --json -s workspace-write -C <cópia> --add-dir <A2A_HOME> -` (já estava na tabela desde a etapa 7; só faltava liberar o gatilho).
- Exige `[windows] sandbox = "elevated"` (ou `"unelevated"`) configurado; verificado por `a2a watch check` (`watch_check_codex`, etapa 5).
- `workspace-write` deixa o gitdir da cópia só leitura: o codex nunca commita, entrega a mudança sem commit e reporta no canal.
- Sequencial (`max_parallel=1`, igual ao 7); hermes continua recusado (etapa 12, opt-in).

**Passo 14 — `assignee`** (**FEITO**, 38d8b13 — emenda ao 7, não pré-requisito dele):
- Campo opcional `assignee` em missões (`a2a mission new --assignee`) e tarefas avulsas (`a2a send --kind task --assignee`): um único agente responsável, precisa ser participante registrado (nunca o humano, nunca reservado).
- Só o `assignee` marca `EM_EXECUCAO` ou `AGUARDANDO_APROVACAO` (por `--task` ou por `--reply-to`); os demais participantes seguem comentando/revisando — outros estados e `mission approve`/`reject` continuam livres. O humano está sempre isento da restrição.
- O vigia (passo 7) já acorda só o `assignee` quando definido (`watch_plan`, e portanto também `watch --once`); sem o campo, tudo se comporta exatamente como antes (nenhuma mudança de comportamento).

**Passo 11 — Orquestrador** (**FEITO**, fc7eca4):
- `orquestrador` é um agente comum (`a2a join --agent orquestrador`), registrado na tabela do vigia com o `claude` por baixo, mas só leitura + `a2a send/brief/read/status/fact` (`WATCH_ORQ_ALLOW`): nunca `Edit`/`Write`, nunca `mission approve/reject/done`, nunca merge, deploy, gasto ou exclusão.
- `mission_verdict` recusa `agent == "orquestrador"` explicitamente (approve/reject não passam por `require_human` para os demais participantes, por design; o orquestrador é a única exceção). `mission done`, `archive` e `worktree` já eram só do humano (`require_human`).
- Nunca precisa de cópia de projeto: usa uma pasta própria (`run/orquestrador-home`), sempre disponível, mesmo sem projeto registrado.
- Papel próprio no `a2a prompt` (`PROMPT_ROLE_ORQ`): prefixo estável e diferente dos demais agentes.
- `watch check`/`--show-command` só listam o orquestrador sem `--agent` se ele estiver registrado; claude/codex/hermes continuam sempre listados, registrados ou não.
- **Pendente**: o tique periódico e os demais gatilhos do orquestrador (agente `blocked`, `ctx>=80%`, task sem `ACEITO` em 30min) dependem de `a2a watch` contínuo (sem `--once`), que ainda não existe (`a2a watch` sem `--once` sai com erro, código 2).

**Passo 12 — Hermes no vigia (opt-in)** (**FEITO**, f95a7b0):
- `hermes_enabled()`/`hermes_opt_in()`/`agent_enabled()`: chave `hermes_enabled` em `~/.a2a/config.json`; liga/desliga só com `a2a watch hermes --enable|--disable --from <humano>` (`require_human`: nunca sob `A2A_RUNNER`, nenhum agente se auto-habilita).
- `watch_disabled()` e `_watch_exe()` usam `agent_enabled()` só para o hermes; os demais agentes (claude, codex) não mudam.
- Desligado por padrão: sem sandbox de SO (`approvals.mode` do hermes só reduz o risco), risco aceito pelo Luiz em 2026-10-19 ("quero arriscar"), por isso opt-in explícito em vez de automático.
- `a2a watch check` mostra se está ligado por opt-in ou desabilitado (com o comando para habilitar).

**Passo 15 — `parent`** (**FEITO**, f48f101):
- Campo opcional `parent` em missões (`a2a mission new --parent`): id da missão-mãe. Validado na criação: a mãe precisa existir (`load_mission`), estar aberta (sem `human` / conclusão) e ser do mesmo projeto da filha; inválido não grava nada (nem missão, nem mensagem). Sem o campo, nada muda.
- `mission_children(mid)` (só leitura, sem `ensure_dirs`, no mesmo padrão de `mission_assignees()`, etapa 14): filhas diretas de uma missão (não recursivo).
- Soma o gasto das filhas no orçamento/teto da mãe (`budget_status`, `run_budget_cap`) e no `a2a cost --mission`: **uma única passada** com escopo-família (ids = mãe + filhas diretas, agentes em união, janela = menor criação até maior conclusão-ou-agora), em vez de somar chamadas independentes por missão — evita contar o mesmo registro do vigia duas vezes. A busca pelas filhas só acontece depois do `has_budget` (sem orçamento definido, nada extra é lido). O rollup é só para cima: a filha nunca vê o gasto da mãe.
- `mission done` (`mission_done`) só fecha a mãe quando **todas** as filhas diretas estiverem `concluida` (reprovada **não** conta como fechada — o último veredito de cada agente vale, e um reject é retrabalhável); fechar continua só humano (`require_human`).
- `mission show` lista `mae: <id>` (na filha) e `filhas: <id> (status), ...` (na mãe).
- **Sem** automação de propagação de estado e **sem** UI de árvore, como no escopo aprovado.
- **Decisão explícita, não implementada**: `run_budget_cap` soma o orçamento da própria missão (e agora das filhas dela), mas **não propaga** o teto de uma mãe para baixo quando quem está rodando é a filha direto (sem passar pela mãe) — ou seja, uma mãe com orçamento esgotado não impede sozinha a próxima execução de uma filha, a não ser que o teto seja checado explicitamente com `--mission <id-da-mãe>`. Ver "Pendentes".

**Passo 16 — Controle remoto pelo celular** (aprovado pelo Luiz em 2026-10-19: "Sim", prioridade **MUITO IMPORTANTE**)
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

**Passo 17 — Memória de projeto: ideias do Hindsight** (aprovado pelo Luiz em 2026-10-19: "sim")
- **Decisão (pesquisa do vectorize-io/hindsight, MIT; PostgreSQL+pgvector, chamada de LLM a cada retain, auto-recall injeta até 1024 tokens por prompt):** **aproveitar só as ideias, NÃO adotar o produto.** Adotar quebraria o só-stdlib/local-first e a prioridade de economia de tokens; os benchmarks são em sua maioria autorrelatados e medem recall em conversas longas, não memória curta de projeto.
- **Sub-passos em ordem** (pequenos, todos **sem chamadas extras de LLM**):
  - 1: filtro de segredo/PII por regex ao gravar `a2a fact` (o mais barato, pode ir primeiro).
  - 2: campos `type`, `tags` e `source` em `a2a fact`, com filtros `brief --type`/`--tag`.
  - 3: mesma chave reforça/substitui o fato existente e conta confirmações (a ordenação do `brief` usa isso).
  - 4: limite de tokens no `brief`, priorizado por tipo, confirmações e recência.
  - 5: ao `done` de uma missão, o agente pode sugerir 0 a 3 fatos duráveis (opt-in, nunca automático).
  - 6: `a2a fact search` sob demanda (substring ou SQLite FTS5 da stdlib).
- **Explicitamente NÃO faremos:** instalar plugins/providers do Hindsight, auto-recall/auto-retain, grafo de entidades, embeddings, Postgres/Docker no caminho do a2a, reflect/consolidação por LLM.
- **Reabrir só se** a memória chegar a milhares de fatos e o filtro por tipo/tag deixar de bastar; aí testar o Hindsight isolado como serviço opcional (modo chunks sem LLM, `max_tokens` baixo, medir antes).
- **Dependência:** começa só **depois** do passo 16, porque mexe no `a2a.py` (evita conflitos).

**Nota do passo 7 (implementado em 396cfd5)**:
- `"mission"` e `"usage_file"` (Hermes) gravados nos registros de run.
- `parse_run_usage()` chamado logo depois de `run_agent()`.
- `run_budget_cap()` em `--max-budget-usd` e `budget_status()['exceeded']` recusam o run (`budget_alerts.json`).
- `loop_runs()` não conta runs `refused`.
- Filtro por `assignee` (passo 14, 38d8b13) já entrou. A pergunta única ao `luiz` aos 80% também já existe (`budget_alert_notify`).
- Testado só com executor falso (`claude` fake); o teste manual acompanhado pelo Luiz com o `claude` real continua pendente.

## 5. Decisões
**Tomadas**
- `a2a map` adiado até medir a exploração com `a2a cost`.
- token-optimizer **não adotado** (licença PolyForm Noncommercial, hooks em toda ferramenta, grava `cleanupPeriodDays`); só ideias, reescritas.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor **não adotados**.
- Instruções globais (`a2a instructions`) em vez de AGENTS.md por repositório (PR lagu #38 fechado).
- Hermes não recebe instruções globais por padrão (o `SOUL.md` dele é persona).
- Parte visual pausada. O backend já está pronto para: aba Git, cópias de trabalho, memória e custo.

- Hermes no vigia (passo 12, **FEITO**, f95a7b0): o Luiz aceitou o risco em 2026-10-19 ("quero arriscar"); desligado por padrão, liga só com `a2a watch hermes --enable --from <humano>`.
- Orquestrador (passo 11, **FEITO**, fc7eca4): agente comum (`a2a join`), restrito a leitura + `a2a send/brief/read/status/fact`; nunca vota/aprova/conclui missão nem merge/deploy/gasto/exclusão. Sem cópia de projeto (pasta própria).

- `assignee` (passo 14) e `parent` (passo 15): aprovados pelo Luiz em 2026-10-19 ("sim"), nos termos acima. Ambos **FEITOS**.
- Controle remoto pelo celular (passo 16): aprovado pelo Luiz em 2026-10-19 ("Sim", MUITO IMPORTANTE), nos termos acima; `tailscale serve`, nunca Funnel/túnel público.
- Memória de projeto (passo 17): aprovado pelo Luiz em 2026-10-19 ("sim"); só ideias do Hindsight, produto não adotado; só depois do 16.
- **Descartados** explicitamente: prioridade, tags, dependências entre tarefas e qualquer coisa que o agente já leia no texto da missão.

**Pendentes**
- Teste manual do vigia (passo 7) com o `claude` real, acompanhado pelo Luiz (os testes automáticos usam executor falso).
- ~~Pergunta única ao `luiz` quando o gasto chegar a 80%~~: feito (`budget_alert_notify`).
- ~~Achados da revisão de segurança (add-dir do codex, caminhos de Edit/Write, orçamento sem projeto/missão, identidade do executor, aviso do `hermes --enable`)~~: corrigidos.
- Vigia contínuo (sem `--once`): hoje só existe `a2a watch --once`/`a2a watch plan`. Sem ele, o orquestrador (passo 11) só tem o gatilho por evento (mensagem nova endereçada a ele); o tique periódico e os gatilhos extras (agente `blocked`, `ctx>=80%`, task sem `ACEITO` em 30min) ficam pendentes.
- `run_budget_cap` não propaga o teto de uma missão-mãe (passo 15) para a execução de uma filha quando ela é acionada direto pelo id dela (sem passar `--mission <mãe>`); decisão explícita de não automatizar isso agora (ver passo 15).
- Pergunta aberta ao Luiz: hoje missão não tem conceito de cancelamento (só `aberta`/`reprovada`/`aval_completo`/`concluida`); o gate do passo 15 exige `concluida` nas filhas para fechar a mãe. Quer um `mission cancel` humano-only, para destravar uma mãe cuja filha ficou obsoleta sem precisar concluí-la de verdade?

## 6. Depois da Fase 3
- Canal entre máquinas: VPS Ubuntu 24.04 + Omarchy + Windows.
- Retomada visual com o Claude Design.
- Integração ou substituição do qLink.

## 7. Como retomar numa sessão nova
1. Leia este arquivo e rode `git log --oneline | head -30`.
2. Rode os testes: `python3 tests/test_a2a.py`.
3. Propostas: `docs/propostas/` no `main` (inclui `2026-10-19-orca-controle-remoto-mobile.md`) e os branches `proposta/*` (`fase3-orquestrador`, `interface-agentes`).
4. Regras: só a stdlib; não mexer em `ui/` sem o Luiz; `DOVE_VERSION` estável enquanto a UI estiver pausada.
5. Sensível (execução de agentes, gasto, `~/.a2a`, envelope, merge/deploy) só com aval do Luiz.
