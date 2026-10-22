# Roadmap do Dove

> **Sessão nova? Comece por [`docs/HANDOFF.md`](HANDOFF.md)** — contexto, regras e próximos passos para retomar sem reexplicar.

Estado em 2026-10-22 · base `main` em 8e68c86 (antes desta etapa) · etapa 16: sub-passos 1, 2, 3 e 4 feitos (sub-passo 0 com o Luiz) · etapas 17 a 21 aprovadas e pendentes.

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
| 16 | Controle remoto pelo celular (`tailscale serve`, papel `remote`) | **APROVADO** (Luiz, 2026-10-19: "Sim", MUITO IMPORTANTE) · **sub-passos 1, 2, 3 e 4 FEITOS** (pareamento aprovado por escrito pelo Luiz em 2026-10-22); sub-passo 0 (teste manual) com o Luiz · só depois de 14, 7, 9, 12, 11 e 15 |
| 17 | Memória de projeto: ideias do Hindsight (`a2a fact`/`brief`) | **APROVADO** (Luiz, 2026-10-19: "sim") · só depois do 16 |
| 18 | `a2a worktree create` copia arquivos ignorados listados num `.worktreeinclude` (só caminhos literais, stdlib) | **APROVADO** (Luiz, 2026-10-21: "sim") · pendente, só depois do 17 |
| 19 | Nota de checkpoint por worktree (`a2a worktree set --comment`), reaproveitando o campo de status | **APROVADO** (Luiz, 2026-10-21: "sim") · pendente, só depois do 18 |
| 20 | Painel em dois níveis de kanban, inspirado na interface do Orca (modelo de interação, não código) | **APROVADO** (Luiz, 2026-10-21: "sim" + nova direção para a interface) · **aguardando retomada da interface** |
| 21 | Dove no Linux (Omarchy): checagem e migração | **APROVADO** (Luiz, 2026-10-21: "sim") · pendente, só depois do 20 · etapa de verificação, não bloqueia a Fase 3 |

Ordem de dependência (revista em 396cfd5): o passo 7 foi feito **sem esperar** o 14 (decisão do Luiz, 2026-10-19: "Comitar a 7 como está agora"). O passo 14 entrou depois (38d8b13) como **emenda** ao 7, não como pré-requisito: hoje o vigia acorda **só o `assignee`** quando ele está definido numa missão ou tarefa; sem o campo, continua acordando todo participante elegível, como antes. O passo 9 (96e904c) já usou a 7 atual para liberar o codex. O passo 12 (f95a7b0) acrescentou o opt-in do hermes, independente dos demais. O passo 11 (fc7eca4) só propõe e manda mensagem — não toca em missão nem em `parent` — então não precisou esperar a 15. O passo 15 (f48f101) fechou os passos da Fase 3 (0+1 a 15 **FEITOS**); restam 16 e 17.

Ordem restante: **16 → 17 → 18 → 19 → 20 → 21** (17 só depois do 16; 18, 19 e 20 depois do 17, nessa ordem; o 20 também espera a retomada da `ui/`; o 21 depois do 20). Passo 16: sub-passos 1, 2, 3 e 4 feitos (1, 2 e 4: ba2b133, no `main` como 344335a; 3: pareamento, com aval do Luiz em 2026-10-22); o 0 (teste manual do Tailscale, com o Luiz) e os 5 a 11 seguem pendentes.

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
- **Decisão resolvida (9593f82)**: `run_budget_cap` agora propaga o teto de cada missão-mãe (`mission_ancestor_statuses`: pai, avô, ... até a raiz, com guarda de ciclo e profundidade máxima 16; mãe sumida encerra a subida; mãe cancelada/concluída é pulada): o cap é o menor entre o que resta da própria missão, de cada mãe ativa e do dia do projeto. Rodar a filha pelo id dela não contorna o limite da mãe. Limite conhecido: o rollup de gasto é de 1 nível (filhas diretas), então o gasto de uma neta entra na mãe direta dela, não na avó.
- **Decisão resolvida (9593f82)**: `a2a mission cancel <id> --from <humano>` (`mission_cancel`): só humano (`require_human`: recusado em `A2A_RUNNER` e com nome de agente), grava `state: CANCELADO` e `cancelled {by, ts, reason}`; concluída não cancela; não desfaz. Filha `CANCELADO` conta como resolvida no gate da mãe (reprovada, não cancelada, continua travando). Cancelada não acorda o vigia (`watch_plan`), sai do `brief` (lista M), não recebe aval nem filha nova, e não é alvo de orçamento ativo (`budget_targets`); a janela de gasto congela no cancelamento. Não aparece no painel (`ui/` intocada).

**Passo 16 — Controle remoto pelo celular** (aprovado pelo Luiz em 2026-10-19: "Sim", prioridade **MUITO IMPORTANTE**)
Proposta: [`docs/propostas/2026-10-19-orca-controle-remoto-mobile.md`](propostas/2026-10-19-orca-controle-remoto-mobile.md) (pesquisa do Orca + design).
- **Direção:** o painel continua em `127.0.0.1` e é publicado com `tailscale serve` (HTTPS só dentro da tailnet). **NUNCA** Funnel, Cloudflare Tunnel, ngrok nem `0.0.0.0`. Sem relay, sem WebSocket, sem serviço de terceiros, só stdlib. O Orca (stablyai/orca, MIT, TypeScript) é só fonte de ideias.
- **Papel restrito "remote":** só para Hosts de uma lista explícita `remote_hosts` (vazia = remoto desligado); tabela de rotas fail-closed; código de pareamento de uso único, válido por 5 min; token por dispositivo, revogável, guardado com hash em `~/.a2a/devices.json` (0600).
- **O celular pode:** ler o status, **STOP** (sempre permitido), concluir missão e enviar mensagem (estes dois são permissões por dispositivo, desligadas por padrão).
- **Só no desktop:** git push/merge/commit, remover cópias de trabalho/projetos/agentes, retomar depois do STOP, orçamento, configuração, gestão de dispositivos.
- **Sub-passos em ordem** (detalhes na proposta, seção 7):
  - 0: teste manual do `tailscale serve`, sem código (roteiro abaixo, "Como testar o sub-passo 0").
  - 1: **FEITO (ba2b133; no `main`: 344335a)** `remote_hosts` (lista em `~/.a2a/config.json`, vazia = remoto desligado) e `a2a remote hosts add|remove|list` (add/remove só humano: recusado em `A2A_RUNNER` e com nome de agente; list livre). Só hostname ou hostname:porta; recusa `*`, `0.0.0.0`, IP (salvo 127.0.0.1), esquema, caminho, usuário, IPv6; máximo 8.
  - 2: **FEITO (ba2b133; no `main`: 344335a)** papel da requisição + tabela de rotas fail-closed + testes (`remoto_fase`). `local` só se o Host é exatamente o loopback host:porta do servidor **e** a requisição não veio por proxy (qualquer `X-Forwarded-*`, `Forwarded`, `Via`, `X-Real-IP` ou `Tailscale-*` com Host de loopback é recusada com 403: fecha o forjar de `Host: 127.0.0.1:8765` por quem chega pelo `tailscale serve`); `remote` só se o Host está em `remote_hosts`; o resto 403. O remoto nunca recebe o token humano e só alcança `REMOTE_ROUTES` (hoje só `GET /remote/api/state`); o resto é 403, e sem dispositivo autenticado tudo é 401. Origin/Referer do remoto: só `https://<próprio host>`. Gancho `remote_device_for_request(handler)`: ligado ao `devices.json` no sub-passo 3 (dispositivo pelo `Authorization: Bearer`); sem dispositivo, 401 em tudo. Papel `local` e `ui/` inalterados.
  - 3: **FEITO** (aval do Luiz por escrito em 2026-10-22; commit 96db60b) `a2a remote pair/list/revoke` + `~/.a2a/devices.json`. Só humano (`require_human`: recusado em `A2A_RUNNER` e com nome de agente; `--from` obrigatório). `pair`: código `secrets.token_urlsafe(16)`, válido 5 min, uso único, substitui um pendente, mostrado **uma vez**; no arquivo só o hash salgado. Resgate: `POST /remote/api/pair` com `{"code", "name"}`, a única rota remota sem dispositivo, só com o Host em `remote_hosts`; devolve o token do dispositivo **uma vez**. Autenticação remota: `Authorization: Bearer <token>`, comparação com `hmac.compare_digest`; revogado = hash apagado = 401 na hora. `list` (nome, criado, último uso; nunca hash nem token) e `revoke <id|nome>`, só humano. Limite: 5 falhas (token errado, código errado, reuso, revogado) em 10 min bloqueiam a origem por 10 min (429, inclusive para dispositivo válido). O `tailscale serve` chega como 127.0.0.1, então a origem é o próprio host: o bloqueio vale para todos os celulares até expirar (trade-off fail-closed); a memória do limite zera ao reiniciar o painel. `devices.json` 0600 em POSIX; no Windows o código não aplica ACL. `remote_hosts` continua vazia por padrão. Teste: `pareamento_fase` (dispositivos falsos).
  - 4: **FEITO (ba2b133; no `main`: 344335a)** `GET /remote/api/state` (`remote_state`): só status dos agentes (sem nota), título/estado/aprovações/percentual de orçamento das missões, contagem de não lidas, STOP. Sem corpo de mensagem, caminho, token, config nem valores de orçamento. Só alcançável depois de autenticar (sem dispositivo, 401 para todos; testado com dispositivo falso injetado no gancho).
  - 5: página móvel `ui/remote.html` (precisa do Claude Design; `ui/` está pausada). Pendente.
  - 6: STOP remoto + log de auditoria. Pendente.
  - 7: permissões de missão/mensagem. **Pendente; NECESSITA AVAL EXPLÍCITO DO LUIZ.**
  - 8: revisão de segurança. Pendente.
  - 9: notificação por polling. Pendente.
  - 10: ntfy opcional, só texto genérico. **Pendente; NECESSITA AVAL EXPLÍCITO DO LUIZ.**
  - 11: QR em texto, opcional. Pendente.
- **Lacuna conhecida: CORRIGIDA nos sub-passos 1 e 2** (antes de expor qualquer coisa). O `/` só entrega o token ao papel `local`; `/api/state` e `/api/messages` continuam sem token no loopback (a UI atual não envia token nelas), mas o papel remoto não alcança nenhuma delas.

**Como testar o sub-passo 0 (manual, Luiz)**: não precisa de pareamento; serve para ver o fail-closed funcionando atrás do `tailscale serve`.
1. Tailscale instalado e logado no desktop e no celular; HTTPS ligado na tailnet (console admin, DNS, "HTTPS Certificates").
2. Rode `dove` normalmente (fica em `127.0.0.1:8765`). **Nunca** use `--host 0.0.0.0`.
3. `tailscale serve --bg 8765`, depois `tailscale serve status`: deve mostrar `https://<máquina>.<tailnet>.ts.net` como "(tailnet only)". `tailscale funnel status` precisa estar vazio (Funnel é público: **nunca** ligue).
4. No celular (Tailscale ligado), abra essa URL. Esperado, sem `remote_hosts`: `403 Host nao permitido`.
5. `a2a remote hosts add <máquina>.<tailnet>.ts.net --from luiz` e recarregue: esperado `401 dispositivo nao autenticado` (em `/` também; a página do painel e o token **não** aparecem). Meça a latência e anote se o `tailscale serve` manda `X-Forwarded-For` (o painel local depende disso para recusar Host de loopback forjado).
6. No próprio desktop, `http://127.0.0.1:8765/` continua abrindo o painel normal.
7. Desfazer: `tailscale serve reset` e `a2a remote hosts remove <host> --from luiz`.
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

**Passo 18 — `a2a worktree create` copia arquivos ignorados** (aprovado pelo Luiz em 2026-10-21: "sim")
- **Ideia (Orca, `.worktreeinclude`, MIT):** um arquivo `.worktreeinclude` na raiz do projeto lista arquivos ignorados pelo git (ex.: configs locais) que `a2a worktree create` copia para a cópia de trabalho nova.
- **Escopo:** só caminhos literais, um por linha; sem globs, sem scripts, sem comandos. Só stdlib, sem tokens extras. Sem o arquivo, nada muda.
- **Esforço:** pequeno. Não conflita com nenhum princípio do projeto.
- **Dependência:** começa só **depois** do passo 17, porque mexe no `a2a.py` (evita conflitos).

**Passo 19 — Nota de checkpoint por worktree** (aprovado pelo Luiz em 2026-10-21: "sim")
- **Ideia:** `a2a worktree set --comment "<texto>"` grava uma nota de checkpoint na cópia de trabalho, reaproveitando o campo de status que já existe, **sem mudar o envelope**.
- **Já coberto em parte:** `a2a status --note` faz o registro por agente; o que falta é a nota presa à cópia de trabalho.
- **Esforço:** pequeno.
- **Dependência:** começa só **depois** do passo 18.

**Passo 20 — Painel em dois níveis de kanban, inspirado na interface do Orca** (aprovado pelo Luiz em 2026-10-21: "sim" + nova direção para a interface) · **aguardando retomada da interface**
- **Decisão:** copiar o **modelo de interação** do Orca (dois níveis de kanban, navegação, estados), **não o código**. O Orca é Electron/React/TypeScript e traria uma stack inteira para um projeto de stdlib e arquivo único.
- **Implementação:** HTML puro dentro do `ui/` existente, quando o trabalho visual for retomado; a estética fica com o Claude Design.
- **Licença:** se algum código do Orca for copiado um dia, manter o aviso de copyright MIT no cabeçalho do arquivo e no `NOTICE`.
- **Subtrair antes de concluir o passo** (partes arriscadas do Orca): sem modos de bypass/yolo, sem confiança de workspace pré-autorizada, sem servidor HTTP local de hooks, sem relay, sem telemetria ligada por padrão.
- **Dependências:** passo 16 (papel `remote`, para a visão do celular) e a `ui/` saindo da pausa.

**Passo 21 — Dove no Linux (Omarchy): checagem e migração** (aprovado pelo Luiz em 2026-10-21: "sim") · pendente
- **Objetivo:** rodar o Dove no Omarchy (Linux baseado em Arch) depois que a instalação no Windows estiver estável. O Luiz planeja mudar a máquina para o Omarchy porque o Orca roda bem lá.
- **Portabilidade:** o Dove é só stdlib do Python, então o núcleo roda em qualquer Linux com Python 3. Não se aplicam as partes só do Windows: `install.ps1`, os shims `.cmd`, as regras de PowerShell na allowlist do vigia e o controle de processo por Job Object do Windows. O vigia no Linux precisa de um caminho próprio de controle de processo, **verificado** (testar, não presumir).
- **Migração:** copiar a pasta inteira `~/.a2a` (bus, missões, memória, orçamentos, runs) e depois rodar `install.sh`. Manter os dados do Windows até a checagem no Linux passar.
- **Checklist** (no Omarchy, **sem nenhum run real de agente**):
  1. `which a2a` aponta para o Dove, não para outra ferramenta.
  2. `python3 --version` é 3.8 ou superior.
  3. `python3 a2a.py --version` imprime `dove 0.6.0`.
  4. Suíte de testes passa: `python3 tests/test_a2a.py`.
  5. `a2a watch check` reporta as flags de CLI do Claude Code, Codex e Hermes como descrito na documentação. Flags a verificar: `claude --permission-prompts` / `--permission-mode` / `--allowedTools`; configurações de sandbox do `codex exec`; `hermes chat --oneshot`.
  6. Controle de processo do vigia verificado com um agente falso que dorme e é parado pelo STOP e pelo timeout.
  7. Arquivo STOP bloqueia um run.
  8. Comando só-humano é recusado sob `A2A_RUNNER`.
- **Só depois do checklist passar:** primeiro run real, só com o `claude`, supervisionado, com o STOP à mão.
- **Diferenças Windows/Linux:** permissões de arquivo, caminhos (barras invertidas) e finais de linha (CRLF, via `.gitattributes`) devem ser conferidos no clone do Linux.
- **Dependências:** nenhum código da Fase 3 fica bloqueado por esta etapa; é uma etapa de verificação. Na ordem: 15 → 16 → 17 → 18 → 19 → 20 → 21.

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
- 2026-10-21: UI do Orca como inspiração (kanban em dois níveis); copiar o modelo de interação, não o código Electron; subtrair modos de bypass, relay e telemetria antes de qualquer uso.

**Pendentes**
- Teste manual do vigia (passo 7) com o `claude` real, acompanhado pelo Luiz (os testes automáticos usam executor falso).
- ~~Pergunta única ao `luiz` quando o gasto chegar a 80%~~: feito (`budget_alert_notify`).
- ~~Achados da revisão de segurança (add-dir do codex, caminhos de Edit/Write, orçamento sem projeto/missão, identidade do executor, aviso do `hermes --enable`)~~: corrigidos.
- Vigia contínuo (sem `--once`): hoje só existe `a2a watch --once`/`a2a watch plan`. Sem ele, o orquestrador (passo 11) só tem o gatilho por evento (mensagem nova endereçada a ele); o tique periódico e os gatilhos extras (agente `blocked`, `ctx>=80%`, task sem `ACEITO` em 30min) ficam pendentes.
- ~~Propagação do teto da mãe para a filha~~ e ~~`mission cancel`~~: feitos (9593f82), ver passo 15.
- Rollup de gasto recursivo (neta na avó): hoje só 1 nível; se importar, tornar `mission_children` recursivo em `budget_status`/`cost_data`.
- Primeira ativação no Windows: ver checklist no `docs/HANDOFF.md` (`a2a` do Dove no PATH, não o qlink; `a2a watch check`; sandbox `[windows]` do codex; primeiro run real só com o claude, PARAR na mão).
- Falta terminar a fase 16 (sub-passos 1, 2, 3 e 4 feitos; pendentes: 0 com o Luiz e 5 a 11), depois a 17, 18, 19, 20 e 21 (ordem restante: 16 → 17 → 18 → 19 → 20 → 21; o 20 aguarda a retomada da `ui/`; o 21 é a checagem no Omarchy, sem run real até o checklist passar).

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
