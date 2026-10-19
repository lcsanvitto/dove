# Handoff do Dove — 2026-10-21

Para uma sessão nova retomar sem reexplicar nada. Estado detalhado: [`docs/ROADMAP.md`](ROADMAP.md).

## Contexto
- Dove: canal A2A local e global entre agentes (arquivos JSON em `~/.a2a`, CLI `a2a`, painel `dove`), só stdlib do Python.
- Usuário: Luiz, no Windows (`C:\Users\Dell`); projetos em `C:\Users\Dell\Cowork\Codigo` (ex.: `lagu`).
- Também usa uma VPS Ubuntu 24.04 e uma máquina com Omarchy (canal entre máquinas ainda não existe).
- Agentes no canal: `claude` (Claude Code), `codex` (Codex), `hermes` (Hermes).
- Fase atual: Fase 3 (orquestrador/vigia) — **completa**. Feitos 0+1, 2, 3 (75c979d), 4, 5, 6, 7 (396cfd5), 8 (7fca4c3), 9 (`codex` no vigia, 96e904c), 10, 11 (orquestrador, fc7eca4), 12 (hermes no vigia, opt-in, f95a7b0), 13, 14 (`assignee`, 38d8b13 — emenda ao 7), 15 (`parent`, f48f101). O 7 foi feito **sem** esperar o 14 (decisão do Luiz, 2026-10-19: "Comitar a 7 como está agora"); o 14 entrou depois como emenda — o vigia agora acorda só o `assignee` quando ele está definido, e todo participante elegível quando não está (como antes). O 11 saiu sem esperar o 15 (só propõe e manda mensagem, não toca em missão/`parent`). Aprovados também: 16 (controle remoto pelo celular), só depois de todos esses; e 17 (memória de projeto, ideias do Hindsight), só depois do 16. Ordem restante: 16 → 17 → 18 → 19 → 20 → 21. Aprovadas em 2026-10-21: 18 (`.worktreeinclude`), 19 (nota de checkpoint), 20 (kanban em dois níveis, inspirado no Orca; aguarda a retomada da `ui/`) e 21 (Dove no Omarchy: checagem e migração, depois do 20).

## Regras do projeto
- Só stdlib.
- **NÃO mexer em `ui/`**: parte visual pausada; o Claude Design cuida só da estética, quando o Luiz retomar.
- `DOVE_VERSION` fica `"0.6.0"` enquanto a UI estiver pausada (a UI compara a versão exata e mostra a faixa "servidor desatualizado").
- Comportamento existente não muda sem aval do Luiz.
- Tudo que executa agentes, gasta dinheiro, muda o envelope ou o `~/.a2a` precisa de aval do Luiz. Já aprovados: etapas 0–15 da Fase 3 (todas); a 12 com risco aceito pelo Luiz em 2026-10-19 (desligada por padrão, opt-in explícito). A 7 está feita (396cfd5); a 9 (codex no vigia) está feita (96e904c); a 11 (orquestrador) está feita (fc7eca4); a 12 (hermes no vigia, opt-in) está feita (f95a7b0); a 14 (`assignee`) está feita (38d8b13, emenda ao 7); a 15 (`parent`) está feita (f48f101).
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
- A pergunta única ao `luiz` quando o gasto chegar a 80% já existe (`budget_alert_notify`).
- Endurecimento (revisão de segurança, corrigido): `--add-dir` do codex só em `bus/ status/ cursor/ missions/ memory/` (nunca `~/.a2a` inteiro); `Edit`/`Write` do claude presos na própria cópia e negados em `~/.a2a`; sem projeto/missão a execução também recusa com limite do dia esgotado; o vigia grava `A2A_AGENT` e, sob `A2A_RUNNER`, `--from`/`--agent` de outro agente é recusado (código 2); `watch hermes --enable` mostra o mesmo aviso de risco do `watch check`.

**Etapa 14 — `assignee`** · **FEITO** · 38d8b13 (emenda à etapa 7, não pré-requisito; a 7 já foi feita sem ela)
- Campo opcional `assignee` em missões (`a2a mission new --assignee`) e tarefas avulsas (`a2a send --kind task --assignee`): um único agente responsável, participante registrado (nunca o humano, nunca reservado); em missão precisa estar em `--agents`, em tarefa avulsa precisa ser o destinatário (`--to`) ou, com `--to all`, qualquer agente registrado.
- Só o `assignee` marca `EM_EXECUCAO` ou `AGUARDANDO_APROVACAO` (por `--task` ou, sem ele, pela mensagem respondida via `--reply-to`); os demais participantes seguem comentando/revisando — outros estados e `mission approve`/`reject` continuam livres. O humano está sempre isento.
- O vigia (etapa 7) já acorda só o `assignee` quando definido (`watch_plan`, valendo também para `watch --once`).
- Sem o campo, nada muda no comportamento atual (testado em `assignee_fase()` e no bloco novo de `plan_fase()`, `tests/test_a2a.py`).

**Etapa 9 — Codex no vigia** · **FEITO** · 96e904c
- `codex exec --json -s workspace-write -C <cópia> --add-dir <A2A_HOME> -` (já estava na tabela desde a etapa 7).
- Exige `[windows] sandbox` configurado (verificado pelo `watch check`, etapa 5).
- O Codex não consegue commitar na cópia (gitdir read-only): entrega mudanças sem commit e reporta no canal.
- Sequencial (`max_parallel=1`, igual à etapa 7); hermes continua recusado (etapa 12, opt-in).

**Etapa 12 — Hermes no vigia (opt-in)** · **FEITO** · f95a7b0
- `hermes_enabled()`/`hermes_opt_in()`/`agent_enabled()`: chave `hermes_enabled` em `~/.a2a/config.json`; `a2a watch hermes --enable|--disable --from <humano>` (`require_human`: só o humano, nunca sob `A2A_RUNNER`, nenhum agente se auto-habilita).
- `watch_disabled()`/`_watch_exe()` usam `agent_enabled()` só para o hermes; claude e codex não mudam.
- Desligado por padrão (sem sandbox de SO); risco aceito pelo Luiz em 2026-10-19 ("quero arriscar").

**Etapa 11 — orquestrador** · **FEITO** · fc7eca4
- `orquestrador` é agente comum (`a2a join`); na tabela do vigia roda com o `claude` por baixo, mas só leitura + `a2a send/brief/read/status/fact` (nunca Edit/Write, nunca merge/deploy/gasto/exclusão).
- `mission_verdict` recusa `agent == "orquestrador"` (approve/reject); `mission done`/`archive`/`worktree` já eram só do humano (`require_human`) — a recusa por `A2A_RUNNER`/`require_human` já protegia o resto.
- Pasta própria (`run/orquestrador-home`), nunca precisa de cópia de projeto. Papel próprio no `a2a prompt` (`PROMPT_ROLE_ORQ`).
- **Pendente**: tique periódico e os demais gatilhos (`blocked`, `ctx>=80%`, task sem `ACEITO`) dependem do vigia contínuo (sem `--once`), que ainda não existe — hoje só o gatilho por evento funciona.

**Etapa 15 — `parent`** · **FEITO** · f48f101
- Campo opcional `parent` em missões (`a2a mission new --parent`): a mãe precisa existir, estar aberta (sem conclusão) e ser do mesmo projeto da filha; inválido não grava nada. Sem o campo, nada muda.
- `mission_children(mid)` (só leitura, sem `ensure_dirs`, igual a `mission_assignees()` da etapa 14).
- Soma o gasto das filhas no orçamento/teto da mãe (`budget_status`/`run_budget_cap`) e no `a2a cost --mission` numa **única passada** de escopo-família (ids mãe+filhas, agentes em união) — não soma chamadas independentes por missão, pra não contar o mesmo registro do vigia duas vezes. O rollup é só pra cima (a filha nunca vê o gasto da mãe).
- `mission done` só fecha a mãe com **todas** as filhas diretas `concluida` (reprovada não conta como fechada).
- `mission show` lista mãe/filhas.
- **Decisão resolvida (9593f82)**: `run_budget_cap` agora propaga o teto das missões-mãe (pai, avô, ... até a raiz, guarda de ciclo/profundidade 16): rodar a filha pelo id dela respeita o que resta de cada mãe ativa. Limite conhecido: o gasto de netas só entra na mãe direta delas (rollup de 1 nível, passo 15), não na avó.
- **Decisão resolvida (9593f82)**: `a2a mission cancel <id> --from <humano>` (só humano, `require_human`; recusado em `A2A_RUNNER`): `state: CANCELADO` + quem/quando/motivo. Filha CANCELADO conta como resolvida no gate da mãe (reprovada continua travando); cancelada não acorda o vigia, sai do `brief` e dos orçamentos ativos, não recebe aval nem filha nova; não desfaz.

**Etapa 16 — Controle remoto pelo celular** · aprovada (Luiz, 2026-10-19: "Sim", **MUITO IMPORTANTE**)
Proposta: [`docs/propostas/2026-10-19-orca-controle-remoto-mobile.md`](propostas/2026-10-19-orca-controle-remoto-mobile.md) (pesquisa do Orca + design).
- **Direção:** o painel continua em `127.0.0.1` e é publicado com `tailscale serve` (HTTPS só dentro da tailnet). **NUNCA** Funnel, Cloudflare Tunnel, ngrok nem `0.0.0.0`. Sem relay, sem WebSocket, sem serviço de terceiros, só stdlib. O Orca (stablyai/orca, MIT, TypeScript) é só fonte de ideias.
- **Papel restrito "remote":** só para Hosts de uma lista explícita `remote_hosts` (vazia = remoto desligado); tabela de rotas fail-closed; código de pareamento de uso único, válido por 5 min; token por dispositivo, revogável, guardado com hash em `~/.a2a/devices.json` (0600).
- **O celular pode:** ler o status, **STOP** (sempre permitido), concluir missão e enviar mensagem (estes dois são permissões por dispositivo, desligadas por padrão).
- **Só no desktop:** git push/merge/commit, remover cópias de trabalho/projetos/agentes, retomar depois do STOP, orçamento, configuração, gestão de dispositivos.
- **Sub-passos em ordem** (detalhes na proposta, seção 7):
  - 0: teste manual do `tailscale serve`, sem código (roteiro abaixo, "Como testar o sub-passo 0").
  - 1: **FEITO (ba2b133)** `remote_hosts` (lista em `~/.a2a/config.json`, vazia = remoto desligado) e `a2a remote hosts add|remove|list` (add/remove só humano: recusado em `A2A_RUNNER` e com nome de agente; list livre). Só hostname ou hostname:porta; recusa `*`, `0.0.0.0`, IP (salvo 127.0.0.1), esquema, caminho, usuário, IPv6; máximo 8.
  - 2: **FEITO (ba2b133)** papel da requisição + tabela de rotas fail-closed + testes (`remoto_fase`). `local` só se o Host é exatamente o loopback host:porta do servidor **e** a requisição não veio por proxy (qualquer `X-Forwarded-*`, `Forwarded`, `Via`, `X-Real-IP` ou `Tailscale-*` com Host de loopback é recusada com 403: fecha o forjar de `Host: 127.0.0.1:8765` por quem chega pelo `tailscale serve`); `remote` só se o Host está em `remote_hosts`; o resto 403. O remoto nunca recebe o token humano e só alcança `REMOTE_ROUTES` (hoje só `GET /remote/api/state`); o resto é 403, e sem dispositivo autenticado tudo é 401. Origin/Referer do remoto: só `https://<próprio host>`. Gancho `remote_device_for_request(handler)` devolve `None` até o sub-passo 3: **hoje o remoto autentica ninguém (401 em tudo)**. Papel `local` e `ui/` inalterados.
  - 3: `a2a remote pair/list/revoke` + `~/.a2a/devices.json`. **NECESSITA AVAL EXPLÍCITO DO LUIZ antes de implementar (cria um arquivo de credencial novo).**
  - 4: **FEITO (ba2b133)** `GET /remote/api/state` (`remote_state`): só status dos agentes (sem nota), título/estado/aprovações/percentual de orçamento das missões, contagem de não lidas, STOP. Sem corpo de mensagem, caminho, token, config nem valores de orçamento. Só alcançável depois de autenticar (hoje 401 para todos; testado com dispositivo falso injetado no gancho).
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

**Etapa 17 — Memória de projeto: ideias do Hindsight** · aprovada (Luiz, 2026-10-19: "sim") · só depois da etapa 16
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

**Etapa 18 — `a2a worktree create` copia arquivos ignorados** · aprovada (Luiz, 2026-10-21: "sim") · só depois da etapa 17
- **Ideia (Orca, `.worktreeinclude`, MIT):** um `.worktreeinclude` na raiz do projeto lista arquivos ignorados pelo git (ex.: configs locais) que `a2a worktree create` copia para a cópia de trabalho nova.
- **Escopo:** só caminhos literais, um por linha; sem globs, sem scripts, sem comandos. Só stdlib, sem tokens extras. Sem o arquivo, nada muda.
- **Esforço:** pequeno. Não conflita com nenhum princípio do projeto.
- **Dependência:** começa só depois da etapa 17 (mexe no `a2a.py`).

**Etapa 19 — Nota de checkpoint por worktree** · aprovada (Luiz, 2026-10-21: "sim") · só depois da etapa 18
- **Ideia:** `a2a worktree set --comment "<texto>"` grava uma nota de checkpoint na cópia de trabalho, reaproveitando o campo de status existente, **sem mudar o envelope**.
- **Já coberto em parte:** `a2a status --note` faz o registro por agente; falta a nota presa à cópia de trabalho.
- **Esforço:** pequeno.

**Etapa 20 — Painel em dois níveis de kanban, inspirado no Orca** · aprovada (Luiz, 2026-10-21: "sim" + nova direção para a interface) · **aguardando retomada da interface**
- **Decisão:** copiar o **modelo de interação** do Orca (dois níveis de kanban, navegação, estados), **não o código**. O Orca é Electron/React/TypeScript e traria uma stack inteira para um projeto de stdlib e arquivo único.
- **Implementação:** HTML puro dentro do `ui/` existente, quando o trabalho visual for retomado; a estética fica com o Claude Design.
- **Licença:** se algum código do Orca for copiado um dia, manter o aviso MIT no cabeçalho do arquivo e no `NOTICE`.
- **Subtrair antes de concluir o passo:** sem modos de bypass/yolo, sem confiança de workspace pré-autorizada, sem servidor HTTP local de hooks, sem relay, sem telemetria ligada por padrão.
- **Dependências:** etapa 16 (papel `remote`, para a visão do celular) e a `ui/` saindo da pausa.

**Etapa 21 — Dove no Linux (Omarchy): checagem e migração** · aprovada (Luiz, 2026-10-21: "sim") · pendente, só depois da etapa 20
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
- **Dependências:** nenhum código da Fase 3 fica bloqueado por esta etapa; é uma etapa de verificação.

**Etapa 12 — Hermes**: o Luiz aceitou o risco em 2026-10-19 ("quero arriscar"). Sem sandbox de SO (`approvals.mode`), então fica **desligado por padrão** e só liga com opt-in explícito.

**Fase 3 (0+1 a 15) está completa, com as duas decisões abertas do 15 resolvidas (cap herdado das mães e `mission cancel`, 9593f82); restam 16 e depois 17.** Passo 16: sub-passos 1, 2 e 4 feitos (ba2b133); o 3 (pareamento) espera aval explícito do Luiz.

**Depois**: roteiro de ativação para o Luiz no Windows; canal entre máquinas (VPS/Omarchy); retomada visual com o Claude Design; qLink.

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

**Checklist da primeira ativação no Windows** (antes de ligar o vigia):
1. `a2a` no PATH tem de ser o do **Dove**, não o `qlink`: `where.exe a2a` / `Get-Command a2a -All` e `a2a --version` (deve dizer Dove 0.6.0). Se aparecer o qlink primeiro, corrigir a ordem do PATH ou o `install.ps1`.
2. `a2a watch check --project lagu` sem erro (claude, codex e hermes; hermes aparece desabilitado até o opt-in).
3. Codex: `[windows] sandbox = "elevated"` (ou `"unelevated"`) no `config.toml` do Codex, senão o `watch check` acusa.
4. Orçamento antes do primeiro run: `a2a cost budget` (teto por execução; padrão US$ 0,50). Sem projeto/missão o limite do dia vale.
5. Primeira execução real **só com o `claude`**, acompanhada pelo Luiz, via `a2a watch --once` (nunca contínuo ainda), numa missão pequena. **PARAR na mão** se algo sair do esperado: `a2a watch stop` (STOP) e conferir `a2a watch runs`.
6. Só depois, `codex`; o `hermes` só com `a2a watch hermes --enable --from luiz` (risco aceito, sem sandbox de SO).

## Decisões registradas
- token-optimizer não adotado.
- `a2a map` adiado até medir com `a2a cost`.
- Instruções globais (`a2a instructions`) em vez de AGENTS.md por repositório (PR lagu #38 fechado).
- Hermes sem instruções globais por padrão.
- Etapa 21 (Dove no Omarchy: checagem e migração) aprovada pelo Luiz em 2026-10-21 ("sim"): só checagem antes de qualquer run real; primeiro run só com o `claude`, supervisionado.
- Hermes no vigia (12, **FEITO**, f95a7b0): risco aceito pelo Luiz (2026-10-19); desligado por padrão, liga só com `a2a watch hermes --enable --from <humano>`.
- Orquestrador (11, **FEITO**, fc7eca4): agente comum, restrito a leitura + `a2a send/brief/read/status/fact`; nunca vota/aprova/conclui missão nem merge/deploy/gasto/exclusão; pasta própria, sem cópia de projeto.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor não adotados.
- Controle remoto pelo celular (16): aprovado pelo Luiz em 2026-10-19 ("Sim", MUITO IMPORTANTE); `tailscale serve`, nunca Funnel/túnel público; sub-passos 3, 7 e 10 pedem aval explícito.
- Memória de projeto (17): aprovada pelo Luiz em 2026-10-19 ("sim"); Hindsight pesquisado, só ideias, produto não adotado; só depois do 16.
- `assignee` (14, FEITO 38d8b13) e `parent` (15, FEITO f48f101) aprovados pelo Luiz em 2026-10-19 ("sim"). Descartados: prioridade, tags, dependências entre tarefas e qualquer coisa que o agente já leia no texto da missão.
- Etapa 7 comitada sem esperar a 14 (Luiz, 2026-10-19: "Comitar a 7 como está agora"): o vigia acorda todos os participantes elegíveis até a 14 entrar como emenda.
- Etapa 14 (`assignee`) feita (38d8b13): restrição de estado (`EM_EXECUCAO`/`AGUARDANDO_APROVACAO`) e filtro do vigia ligados só quando o campo está definido; sem ele, nada muda. Uma mensagem do humano endereçada a um participante que não é o `assignee` de uma conversa com responsável definido não aciona esse participante (leitura literal do pedido do Luiz: "só o assignee marca/é acionado").
- 2026-10-21: UI do Orca como inspiração (kanban em dois níveis); copiar o modelo de interação, não o código Electron; subtrair modos de bypass, relay e telemetria antes de qualquer uso.

## Onde estão as coisas
- Propostas: `docs/propostas/` (controle remoto mobile: `docs/propostas/2026-10-19-orca-controle-remoto-mobile.md`).
- Pesquisa de economia de tokens: branch `pesquisa/economia-tokens`.
- Proposta da Fase 3: branch `proposta/fase3-orquestrador`.
