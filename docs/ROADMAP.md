# Roadmap do Dove

> **Sessão nova? Comece por [`docs/HANDOFF.md`](HANDOFF.md)** — contexto, regras e próximos passos para retomar sem reexplicar.

Estado em 2026-10-19 · base `main` em 7fca4c3.

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
Todos os passos têm aval do Luiz; o 12 foi aceito com risco em 2026-10-19 (desligado por padrão).

| Passo | Item | Estado |
|---|---|---|
| 0+1 | Segurança: `mission done` só humano, `--from` obrigatório, `vigia` reservado, `A2A_RUNNER` nunca age como humano | **FEITO** · 67d2d37 |
| 2 | `a2a loops` (prevenção de loop entre agentes automáticos) | **FEITO** · 2a8485d |
| 3 | `a2a watch plan` / `--dry-run` (+ `git add`/`git commit` na allowlist do Claude só na própria cópia; proíbe rebase/reset/checkout/switch/`branch -D`/clean) | **FEITO** · 75c979d |
| 4 | `a2a cost` (lê os registros do Claude/Codex/Hermes, só leitura) | **FEITO** · 247ef1f |
| 5 | `a2a watch check` | **FEITO** · 37be0d7 |
| 6 | Supervisor: `STOP`, travas, timeout, Job Object | **FEITO** · 81a0e14 |
| 7 | Vigia real, só com o `claude`, iniciado à mão | **bloqueado — aguardando decisão do Luiz** |
| 8 | Orçamento: `parse_run_usage`, `run_budget_cap`, `budget_status`, `budget_alerts`, `a2a mission budget`, `a2a cost budget`/`--budget`, `budgets.json`, `a2a watch usage` | **FEITO** · 7fca4c3 |
| 9 | Codex no vigia (sandbox do Windows; sem commit) | próximo (aprovado) · depende do 7 |
| 10 | `a2a models` (roteamento de modelo) | **FEITO** · 97ce044 |
| 11 | Orquestrador (só leitura + mensagens) | próximo (aprovado) · depende do 7 |
| 12 | Hermes no vigia | **APROVADO COM RISCO** (Luiz, 2026-10-19: "quero arriscar"): desligado por padrão, só com opt-in explícito |
| 13 | Política de subagentes | **FEITO** · 898c637 (+ c65d148 teste determinístico) |
| 14 | `assignee` (responsável único) em missões e tarefas | **APROVADO** (Luiz, 2026-10-19: "sim") · **pré-requisito do passo 7** (entra antes dele) |
| 15 | `parent` (missão-mãe) em missões | **APROVADO** (Luiz, 2026-10-19: "sim") · entra junto com o 11, depois do 7 |
| 16 | Controle remoto pelo celular (`tailscale serve`, papel `remote`) | **APROVADO** (Luiz, 2026-10-19: "Sim", MUITO IMPORTANTE) · só depois de 14, 7, 9, 12, 11 e 15 |
| 17 | Memória de projeto: ideias do Hindsight (`a2a fact`/`brief`) | **APROVADO** (Luiz, 2026-10-19: "sim") · só depois do 16 |

Ordem de dependência: **14 → 7 → (9, 11 + 15) → 12 → 16 → 17**.

**Passo 14 — `assignee`** (pré-requisito do 7; a especificação do passo 7 continua como está):
- Campo opcional `assignee` em missões e tarefas: um único agente responsável.
- Regra: só o `assignee` marca `EM_EXECUCAO` ou `AGUARDANDO_APROVACAO`; os demais participantes só comentam ou revisam.
- O vigia (passo 7) acorda só o `assignee`, não todos os participantes: menos gasto, menos risco de loop, dono claro.
- Sem o campo, tudo se comporta exatamente como hoje (nenhuma mudança de comportamento).

**Passo 15 — `parent`** (junto com o 11, depois do 7):
- Campo opcional `parent` em missões: id da missão-mãe.
- Escopo mínimo: o campo + somar o gasto das filhas no orçamento da mãe e no `a2a cost`.
- A mãe só fecha quando todas as filhas estiverem `CONCLUIDO` ou `CANCELADO`; fechar continua só humano (`require_human`).
- **Sem** automação de propagação de estado e **sem** UI de árvore.

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

**Nota para quem implementar o passo 7** (o orçamento do passo 8 já existe, falta ligar no executor):
- Gravar `"mission"` e `"usage_file"` (Hermes) nos registros de run.
- Chamar `parse_run_usage()` logo depois de `run_agent()`.
- Usar `run_budget_cap()` em `--max-budget-usd` e `budget_status()['exceeded']` para recusar o run.
- `loop_runs()` não pode contar runs recusados.
- Falta fazer: a pergunta única ao `luiz` quando o gasto chegar a 80%.

## 5. Decisões
**Tomadas**
- `a2a map` adiado até medir a exploração com `a2a cost`.
- token-optimizer **não adotado** (licença PolyForm Noncommercial, hooks em toda ferramenta, grava `cleanupPeriodDays`); só ideias, reescritas.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor **não adotados**.
- Instruções globais (`a2a instructions`) em vez de AGENTS.md por repositório (PR lagu #38 fechado).
- Hermes não recebe instruções globais por padrão (o `SOUL.md` dele é persona).
- Parte visual pausada. O backend já está pronto para: aba Git, cópias de trabalho, memória e custo.

- Hermes no vigia (passo 12): o Luiz aceitou o risco em 2026-10-19 ("quero arriscar"); desligado por padrão, exige opt-in explícito.

- `assignee` (passo 14) e `parent` (passo 15): aprovados pelo Luiz em 2026-10-19 ("sim"), nos termos acima.
- Controle remoto pelo celular (passo 16): aprovado pelo Luiz em 2026-10-19 ("Sim", MUITO IMPORTANTE), nos termos acima; `tailscale serve`, nunca Funnel/túnel público.
- Memória de projeto (passo 17): aprovado pelo Luiz em 2026-10-19 ("sim"); só ideias do Hindsight, produto não adotado; só depois do 16.
- **Descartados** explicitamente: prioridade, tags, dependências entre tarefas e qualquer coisa que o agente já leia no texto da missão.

**Pendentes**
- Executor real do vigia (passo 7) — decisão do Luiz; os passos 9 e 11 dependem dele. O passo 14 (`assignee`) entra antes do 7.

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
