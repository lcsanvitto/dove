# Economia de tokens para o Dove — pesquisa de referências

Data: 2026-10-19 · Branch: `pesquisa/economia-tokens` · Somente pesquisa; nenhum código foi alterado.

## Resumo executivo

1. O Dove é um barramento de arquivos com stdlib; ele **não chama modelo**. O desperdício está no que ele faz os agentes lerem, reenviarem e reprocessarem.
2. O maior fator de custo verificado é o **cache de prompt**: leitura de cache custa 0,1× (0,05× em Opus 5.5 e Sonnet 5.5) do preço base de entrada, mas escrita custa 1,25× (TTL 5 min) ou 2× (TTL 1 h). Ou seja, prefixo instável paga escrita de novo.
3. Na doc do Claude Code, mensagens entre sessões que chegam com a sessão ociosa são entregues como um novo turno **com o contexto completo**. Isso é desperdício direto num canal de mensagens como o Dove.
4. `/clear` não custa nada; `/compact` relê a conversa inteira. Para trocar de assunto, `/clear` com um handoff curto é mais barato.
5. O Aider resolve o mapa do repositório com tree-sitter, limite de 1024 tokens por padrão e cache de tags em disco. O padrão (mapa cacheado, limitado, invalidado por mudança) cabe no Dove com stdlib.
6. Para medir, há ferramentas maduras que leem dados locais (ccusage, MIT) e a própria saída JSON do `claude -p` (`total_cost_usd`). O Dove ainda não mede custo por agente.
7. Memória dedicada: Letta, mem0 e Graphiti são Apache-2.0 e ativos, mas são infraestrutura pesada. O Hermes já tem memória curada e busca FTS5 de sessões, o que serve de padrão.
8. Roteamento de modelo: claude-code-router e LiteLLM (MIT) são opcionais; RouteLLM está parado desde 2024-08 e não é recomendado.
9. Recomendação principal, em ordem: (1) medir custo por agente e missão; (2) prefixo estável nos textos que o Dove emite; (3) entrega de mensagens sem reenviar contexto; (4) mapa de repositório cacheado por commit; (5) handoff estruturado com `/clear`.
10. Limite desta pesquisa: não consegui abrir as docs da OpenAI, do Aider, do Letta e do RouteLLM a partir do sandbox. Itens que dependem delas estão marcados como "não verificado".

## Como ler as tabelas

- **Licença** e **último commit** vêm dos clones rasos feitos hoje (`git log -1`, arquivo de licença do repositório). Versão = última tag encontrada no remoto.
- "Verificado" = visto na página ou no código-fonte citado. "Não verificado" = só pelo nome ou por fonte secundária.
- Números de preço e de cache vêm da documentação oficial da Anthropic (`platform.claude.com`) e de `code.claude.com`; não foram copiados de terceiros.

---

## 1. Cache de prompt

**Fatos verificados (Anthropic, doc oficial):**

- Escrita no cache: 1,25× o preço base de entrada (TTL 5 min) e 2× (TTL 1 h).
- Leitura do cache: 0,1× o preço base; em Opus 5.5 e Sonnet 5.5, 0,05×.
- Ordem do prefixo: `tools` → `system` → `messages`. Até 4 breakpoints por requisição.
- Mínimo cacheável: 512 tokens para Opus 5.5, Sonnet 5.5 e Haiku 5.5. Abaixo disso, não há erro, só não há cache.
- Invalidam tudo: mudança em definições de ferramentas. Invalidam `system` e `messages`: mudança de busca web, citações ou velocidade. Invalidam só `messages`: escolha de ferramenta, imagens, parâmetros de raciocínio, esforço (`output_config.effort`).
- Cache automático: `cache_control` de nível superior; o sistema move o breakpoint para o último bloco cacheável.

Fonte: <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>

**Claude Code (verificado):** o cache tem TTL de 1 h na assinatura e 5 min por padrão na API. O `/usage` mostra estatísticas de cache (`Prompt cache (main)`), incluindo "misses" e "warm/cold". Fonte: <https://code.claude.com/docs/en/costs>

**OpenAI:** a doc oficial (`developers.openai.com`) **não foi acessível**. Um resumo de busca (fonte secundária, LiteLLM) diz que o cache é automático a partir de 1024 tokens, com `prompt_cache_key` e retenção `in_memory`/`24h`. Essa mesma busca aponta que modelos GPT-5.6+ mudaram para `prompt_cache_options`. **Não verificado no original**; o percentual de desconto não foi confirmado.

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| Prompt caching da Anthropic — <https://platform.claude.com/docs/en/build-with-claude/prompt-caching> | Documentação (não é software) | Doc viva | Define o preço e a regra de prefixo; é a base de qualquer decisão de layout de prompt | Padrão de mercado | **Copiar o padrão**: textos emitidos pelo Dove (onboard, brief) com parte fixa no início e dados que mudam no fim |
| `agent/prompt_caching.py`, `prompt_cache_boundary.py`, `prompt_cache_scope.py` do Hermes — <https://github.com/NousResearch/hermes-agent> | MIT · 2026-10-18 · v2026.9.24 | — | O Hermes separa explicitamente a fronteira do cache no prompt (nomes de arquivo verificados; conteúdo não lido) | Ativo | **Ignorar o código** (é Python de agente, fora do escopo do Dove); usar só como referência de desenho |
| Claude Code `/usage` com estatísticas de cache — <https://code.claude.com/docs/en/costs> | Proprietário (uso permitido) | — | Mostra taxa de acerto e misses | Padrão | **Ensinar o agente a ler** a própria taxa; o Dove pode exibir a mesma métrica no `status` se o agente reportar |

**Recomendação:** tratar o layout do texto como API. Nada dinâmico (hora, contagem, "novas=4") antes da parte estável; nada que mude as ferramentas do agente no meio de uma sessão.

---

## 2. Memória dedicada ao projeto (expira ou se condensa)

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| Letta (ex-MemGPT) — <https://github.com/letta-ai/letta> | Apache-2.0 · 2026-10-18 · 0.16.8 | — | Agentes com memória persistente em blocos. Detalhes dos blocos e limites: **não verificado** (docs do Letta inacessíveis) | Ativo; infraestrutura pesada (servidor) | **Ignorar** como dependência; o padrão de "blocos com limite de caracteres" é a ideia a copiar |
| mem0 — <https://github.com/mem0ai/mem0> | Apache-2.0 · 2026-10-14 · tag de SDK | — | Camada de memória por usuário/agente. O README cita um algoritmo "token-efficient"; **conteúdo do paper não verificado** | Ativo; biblioteca | **Ignorar** (depende de LLM e banco vetorial); fora do escopo stdlib |
| Graphiti — <https://github.com/getzep/graphiti> | Apache-2.0 · 2026-10-19 · v0.31.1 | — | Grafo temporal: "rastreia o que é verdade agora e o que era antes" (verificado no README) | Ativo; infra pesada | **Ignorar**; a ideia de fato com data de validade é útil para status de missões |
| Memória do Hermes (memória curada + busca FTS5 de sessões) — <https://github.com/NousResearch/hermes-agent> | MIT · 2026-10-18 | — | Memória escrita pelo próprio agente com lembretes periódicos e busca FTS5 entre sessões (verificado no README) | Ativo | **Copiar o padrão**: missão fechada vira resumo curto; o `status`/missão guarda só o "estado atual", o histórico fica em arquivo |
| Memórias do Claude Code (`CLAUDE.md`, skills sob demanda) — <https://code.claude.com/docs/en/costs> | Proprietário | — | `CLAUDE.md` entra em todo contexto; skills entram só quando chamadas. Recomendação oficial: manter `CLAUDE.md` abaixo de 200 linhas (verificado) | Padrão | **Copiar**: o `AGENTS.md`/onboard do Dove deve ser enxuto; regras longas viram comando (`a2a onboard --topic ...`) |
| Cline "memory bank" — <https://github.com/cline/cline> | Apache-2.0 · 2026-10-19 · v4.1.25 | — | Arquivos de memória por projeto. Detalhes: **não verificado** | Ativo | Ideia (arquivos curtos por projeto, lidos sob demanda) para `~/.a2a/projects`; sem dependência |

**Recomendação:** no Dove, a "memória do projeto" é a própria missão. Uma missão com aval fechada gera um resumo de 3–5 linhas e os detalhes saem do caminho do `brief`. Isso é implementável em stdlib.

---

## 3. Mapa do repositório, reaproveitável e invalidado por commit

**Aider (verificado no código-fonte, `aider/repomap.py`):**

- Usa tree-sitter para extrair tags (definições e referências).
- `map_tokens=1024` por padrão; `--map-tokens` (em `aider/args.py`) ajusta o limite e `0` desliga.
- Cache de tags em disco (`.aider.tags.cache.v{CACHE_VERSION}`) e cache em memória do mapa (`map_cache`).
- Limiar `cache_threshold = 0.95` usado no ajuste do mapa.
- Último commit do repositório: 2026-05-22 (mais antigo que os demais).

Fonte: <https://github.com/Aider-AI/aider> (arquivos `aider/repomap.py`, `aider/args.py`). A página de docs `aider.chat/docs/repomap.html` **não foi acessível**.

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| Aider repo map — <https://github.com/Aider-AI/aider> | Apache-2.0 · 2026-05-22 · v0.86.3.dev | Verificado no código | Mapa de símbolos com teto de tokens e cache em disco | Padrão de mercado | **Copiar o padrão** com stdlib: lista de arquivos do `git ls-files`, extração por regex de `def`/`class`, cache por SHA de commit do arquivo. Tree-sitter fica como extra opcional |
| Repomix — <https://github.com/yamadashy/repomix> | MIT · 2026-10-18 · v1.18.1 | Descrição pelo nome; recursos **não verificados** | Empacota o repositório em um arquivo único | Ativo | **Integrar como opcional**: `a2a` chama `repomix` se instalado; o Dove só guarda o caminho do arquivo gerado |
| code2prompt — <https://github.com/mufeedvh/code2prompt> | MIT · 2026-09-07 · v4.2.0 | Descrição pelo nome; **não verificado** | Empacota código em prompt, com contagem de tokens | Ativo | **Ignorar** (sobreposição com repomix) |
| Serena — <https://github.com/oraios/serena> | App: GPL-3.0-or-later; SolidLSP: MIT · 2026-10-15 · v2.0.0 | Verificado no README | Ferramentas simbólicas via LSP em vez de ler arquivo inteiro. O README relata reduzir "8–12 passos" a uma chamada (depoimento citado no README, não medido) | Ativo | **Integrar como opcional** (não copiar código: GPL). Útil para agentes, não para o Dove |
| claude-context (Zilliz) — <https://github.com/zilliztech/claude-context> | MIT · 2026-07-14 · v0.1.11 | Descrição pelo nome; **não verificado** | Índice semântico do código para busca | Ativo (recente) | **Ignorar** por ora (exige base vetorial) |
| Ferramentas de code intelligence do Claude Code — <https://code.claude.com/docs/en/costs> | Proprietário | Verificado | LSP reduz leituras de arquivos (verificado na doc de custos) | Padrão | **Recomendar** aos agentes, sem código no Dove |

**Recomendação:** mapa gerado por `a2a map` (stdlib), guardado em `~/.a2a/cache/map/<projeto>-<sha>.txt` e limitado a N linhas. O `brief` mostra só o caminho e o SHA, não o conteúdo.

---

## 4. Handoff e compactação de contexto

**Claude Code (verificado em <https://code.claude.com/docs/en/costs>):**

- `/compact [instruções]` resume a conversa; a doc avisa que o próprio `/compact` **é uma requisição grande**, pois relê a conversa a ser resumida.
- `/clear` começa do zero e "custa nada".
- `/rename` + `/resume` para retomar uma sessão depois de limpar.
- Instruções de compactação podem ficar numa seção `# Compact instructions` do `CLAUDE.md`.
- Auto-compact: resume o histórico ao se aproximar do limite de contexto.

**Hermes (verificado no README e nos nomes de arquivo):** `/compress`, `/usage`, `/insights`; módulos `context_compressor*`, `conversation_compression*` e `micro_compaction.py`. Conteúdo não lido.

**Codex:** as docs de AGENTS.md e exec são links externos (`developers.openai.com`), **não verificados**.

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| `/compact`, `/clear`, `/resume` do Claude Code | Proprietário | Verificado | Resume ou zera o contexto | Padrão | **Recomendar**: usar `/clear` + handoff para troca de assunto; `/compact` só quando a continuidade importa |
| Compressão do Hermes (`agent/context_compressor*.py`) — <https://github.com/NousResearch/hermes-agent> | MIT | Verificado nos nomes | Compressão automática com resumo e "prune" | Ativo | **Copiar a ideia** (checkpoint com resumo), não o código |
| Padrão de handoff do Dove (`status` com `ctx=%` e aviso `preparar handoff`) | Interno | — | Já existe o alerta; falta o artefato | — | **Evoluir**: o alerta gera um arquivo de handoff curto na missão |

**Recomendação:** quando `ctx ≥ 80`, o agente grava um handoff de até ~15 linhas (estado, próximo passo, arquivos, IDs de mensagem) e roda `/clear`. Com isso, o contexto novo começa pequeno e o custo de reler a conversa não se repete.

---

## 5. Roteamento de modelo por tarefa

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| claude-code-router — <https://github.com/musistudio/claude-code-router> | MIT · 2026-10-10 · v3.1.3 | Verificado no README | Gateway local que envia cada requisição a um modelo; mostra logs, rotas, latência, tokens e custo estimado | Ativo | **Integrar como opcional** (o usuário instala). O Dove não depende dele |
| LiteLLM — <https://github.com/BerriAI/litellm> | MIT no núcleo; pasta `enterprise/` com licença própria · 2026-10-18 | Verificado no LICENSE | Roteador e controle de gasto por chave (citado na doc de custos do Claude Code) | Padrão de mercado | **Integrar como opcional** para quem quer gasto por chave |
| RouteLLM — <https://github.com/lm-sys/RouteLLM> | Apache-2.0 · **último commit 2024-08-10** · sem tag | Verificado | Roteia entre modelo forte e fraco por dificuldade | **Parado** | **Ignorar** (sem manutenção há mais de dois anos) |
| Nativo: `/model`, `/effort`, subagentes com `model: haiku` (Claude Code) | Proprietário | Verificado em <https://code.claude.com/docs/en/costs> | Escolha de modelo e esforço por tarefa e por subagente | Padrão | **Recomendar** nas instruções do onboard: tarefas mecânicas com modelo menor e esforço menor |
| Nativo: `hermes model` e configuração de subagentes (Hermes) | MIT | Verificado no README | Provedor e modelo por subagente | Ativo | **Recomendar** no onboard |

**Recomendação:** o Dove deve apenas **recomendar** modelo e esforço por tipo de tarefa no `task` (campo `model`/`effort` opcional). Não precisa de roteador.

---

## 6. Enviar só a diferença ou referências em vez de conteúdo

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| Hooks de filtro no Claude Code (`PreToolUse`) — <https://code.claude.com/docs/en/costs> | Proprietário | Verificado | Um hook filtra a saída (ex.: só falhas de teste) antes de o modelo ler | Padrão | **Recomendar** nas instruções: comandos verbosos saem por `grep`/`head`, não colados inteiros |
| Subagentes para operações verbosas (Claude Code) | Proprietário | Verificado | A saída longa fica no subagente; volta só o resumo | Padrão | **Recomendar** para o agente que roda testes em tarefas grandes |
| `a2a read --compact` e `brief --width` (Dove) | Interno | Commits `6a181dd`, `17ccad1` | Já enviam só campos preenchidos e linhas curtas | — | **Evoluir**: `brief` mostra `msg_id` e tamanho do corpo; o corpo só com `read` |

**Recomendação:** o Dove já tem a base. O que falta é padronizar **ponteiros** (ID de mensagem, caminho de arquivo, SHA de commit) em todo lugar em que hoje vai texto.

---

## 7. Acordar agentes só por evento, com debounce

**Verificado na doc do Claude Code (<https://code.claude.com/docs/en/costs>):**

- Mensagens de outra sessão são entregues como novo turno quando a sessão está ociosa, **enviando o contexto completo a cada vez**. A configuração `crossSessionInbound` aceita `hold` para segurar as mensagens.
- Tarefas agendadas e `/loop` disparam mesmo ociosos, enviando o contexto completo.
- Check-ins de metas: no máximo três por meta entre prompts (versão ≥ 2.1.246).

Isso é o ponto mais direto para o Dove: um aviso de mensagem nova não deveria acordar o agente com o contexto inteiro.

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| `crossSessionInbound: hold` (Claude Code) | Proprietário | Verificado | Segura mensagens entre sessões em vez de entregar cada uma como turno | Padrão | **Recomendar** nas instruções do onboard; o agente lê com `a2a brief` quando decidir |
| watchfiles — <https://github.com/samuelcolvin/watchfiles> | MIT · 2026-09-21 · v1.3.0 | Descrição pelo nome; **debounce não verificado** | Observa mudanças de arquivo | Ativo | **Ignorar** (stdlib basta: `os.stat` com intervalo mínimo) |
| watchdog — <https://github.com/gorakhargosh/watchdog> | Apache-2.0 · 2026-10-18 · v6.0.0 | Descrição pelo nome | Eventos de sistema de arquivos | Ativo | **Ignorar** pelo mesmo motivo |
| A2A protocol — <https://github.com/a2aproject/A2A> | Apache-2.0 · 2026-10-15 · v1.0.1 | Verificado (versão) | Protocolo de tarefas entre agentes com estados | Padrão emergente | **Ignorar o protocolo**; o modelo de estados (já parecido com `ESTADO` do Dove) é suficiente |
| `a2a wait` do Dove — `a2a.py` (`cmd_wait`) | Interno | — | Espera por mensagens | — | **Verificar** se é polling com intervalo fixo ou se usa debounce; não lido nesta pesquisa |

**Recomendação:** `wait` com intervalo mínimo e agregação de mensagens (uma notificação por janela de N segundos), e `brief` como única leitura padrão.

---

## 8. Trocar chamadas de IA por código determinístico

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| pre-commit — <https://github.com/pre-commit/pre-commit> | MIT · 2026-10-13 · v4.7.0 | Verificado | Verificações determinísticas em hooks, sem LLM | Padrão | **Recomendar** no README do projeto para lint/format, em vez de pedir ao agente que revise estilo |
| ast-grep — <https://github.com/ast-grep/ast-grep> | MIT · 2026-10-15 · tag v0.1.0 (não confere com a série atual; não verificado) | Verificado (licença) | Busca e reescrita estrutural de código | Ativo | **Integrar como opcional** para mudanças mecânicas em vez de pedir a um modelo |
| Hooks do Claude Code | Proprietário | Verificado | Lógica determinística antes/depois de ferramentas | Padrão | **Recomendar** para bloquear comandos caros ou repetidos |
| Dove já: `status`, `brief`, `mission list` | Interno | — | Cálculos de estado sem modelo | — | **Ampliar**: detecção de "bloqueado há N min", "missão sem aval" e "handoff pendente" como comandos, não como texto para o agente interpretar |

**Recomendação:** tudo que é contagem, prazo ou estado deve sair do agente e virar saída do `a2a`.

---

## 9. Tarefas bem recortadas (templates e spec)

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| spec-kit (GitHub) — <https://github.com/github/spec-kit> | MIT · 2026-10-16 · v1.2.1 | Verificado (licença e versão); conteúdo **não verificado** | Fluxo com especificação antes de implementar | Ativo | **Copiar o padrão**: campos de `task` (objetivo, arquivos, critério de pronto) como modelo no `a2a send` |
| Task Master — <https://github.com/eyaltoledano/claude-task-master> | **MIT + Commons Clause** (proíbe venda como serviço) · 2026-04-23 · v0.20.0-rc.0 | Verificado | Quebra objetivo em tarefas | Pré-lançamento | **Ignorar** (licença restritiva e versão RC) |
| AGENTS.md (padrão) — <https://github.com/agentsmd/agents.md> | MIT · 2026-09-10 | Verificado (licença) | Formato único de instruções a agentes | Padrão | Já usado pelo Dove (`a2a onboard --agents-md`) |
| Nativo: plan mode, "dê alvos de verificação" (Claude Code) | Proprietário | Verificado em <https://code.claude.com/docs/en/costs> | Planejar antes de editar; incluir critério de teste no prompt | Padrão | **Recomendar** no template de `task` |

**Recomendação:** `a2a send --kind task` ganha um modelo de corpo com três campos obrigatórios (arquivos, critério de pronto, o que não fazer).

---

## 10. Respostas curtas e protocolos enxutos

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| MCP — <https://github.com/modelcontextprotocol/modelcontextprotocol> | **Transição de MIT para Apache-2.0 em andamento** · 2026-10-17 · tag RC `2026-07-28-RC` | Verificado (RC) | Padrão de ferramentas; ferramentas são **carregadas sob demanda** (só o nome entra no contexto, verificado na doc de custos) | Padrão | **Recomendar** que o Dove, se expuser ferramentas, use MCP com carregamento sob demanda |
| TOON — <https://github.com/toon-format/toon> | MIT · 2026-10-09 · v4.4.0 | Verificado (licença/versão); **economia de tokens não verificada** | Formato compacto para dados estruturados em prompts | Ativo | **Ignorar por ora**; o `--compact` do Dove já cobre o caso |
| Dove `--compact` e `--json` | Interno | — | Campos vazios somem | — | **Manter**; padronizar chaves curtas |

**Recomendação:** nenhuma troca de formato. Medir primeiro (ver seção 12).

---

## 11. Revisão por amostragem ou revezamento

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| qodo PR-Agent — <https://github.com/qodo-ai/pr-agent> | MIT · 2026-10-18 · v0.48.0 | Verificado (licença/versão); conteúdo não lido | Revisão automática de PR | Ativo | **Ignorar** (serve a PR, não a conversas entre agentes) |
| claude-code-action — <https://github.com/anthropics/claude-code-action> | MIT · 2026-10-18 · v1.0.253 | Verificado | Claude em CI para revisão | Padrão | **Ignorar**; útil só se o Dove virar parte de CI |
| Revisão rotativa com aval (Dove) | Interno | — | Missão com aval de todos os agentes | — | **Evoluir**: revisão por amostragem (um agente revisa 1 em cada N entregas), com registro de resultado |

**Recomendação:** revisão por amostragem é um padrão de processo, não precisa de ferramenta. Escolher o revisor por rodízio na própria missão.

---

## 12. Orçamento e medição de tokens e custo

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| ccusage — <https://github.com/ryoppippi/ccusage> | MIT (`apps/ccusage/LICENSE`) · 2026-10-18 · v20.0.36 | Verificado no README | Lê dados locais de CLIs de código e gera relatórios diários, semanais, mensais e por sessão | Ativo | **Integrar como opcional**: `a2a cost` chama o `ccusage` se instalado; sem dependência |
| claude-code-log — <https://github.com/daaain/claude-code-log> | MIT · 2026-10-09 · v1.7.0 | Descrição pelo nome; **não verificado** | Lê logs de sessão do Claude Code | Ativo | **Ignorar** por ora (ccusage cobre) |
| Langfuse — <https://github.com/langfuse/langfuse> | MIT fora de `ee/` (pastas `ee/` têm licença própria) · 2026-10-18 · v4.63.0 | Verificado no LICENSE | Observabilidade com custo, self-host | Padrão | **Ignorar** no Dove (servidor); útil para quem quer painel completo |
| Helicone — <https://github.com/Helicone/helicone> | Apache-2.0 · 2026-09-16 | Verificado no README | Proxy com rastreamento de custo e latência; self-host | Ativo | **Ignorar** (exige proxy na frente da API) |
| OpenLLMetry — <https://github.com/traceloop/openllmetry> | Apache-2.0 · 2026-10-13 · v0.62.4 | Descrição pelo nome | Telemetria OpenTelemetry para LLM | Ativo | **Ignorar**; usar a exportação OTel nativa do Claude Code |
| Nativo: `claude -p --output-format json` | Proprietário | Verificado em <https://code.claude.com/docs/en/headless> | Campo `total_cost_usd` e breakdown por modelo na saída | Padrão | **Copiar agora**: `a2a` grava o custo de cada tarefa que roda via `claude -p` |
| Nativo: `/usage`, `/insights`, exportação OTel | Proprietário | Verificado em <https://code.claude.com/docs/en/costs> | Custo e uso por sessão e por usuário | Padrão | **Recomendar** para medição humana |
| Nativo do Hermes: `/usage`, `/insights [days]` | MIT | Verificado no README | Uso e relatórios | Ativo | **Recomendar** no onboard |

**Recomendação (a prioridade número 1):** sem número por agente e por missão, as outras otimizações não podem ser medidas. Começar gravando `total_cost_usd` (quando disponível) e `cache_read`/`cache_write` por tarefa.

---

## 13. Arquivamento e índice de histórico de mensagens

| Referência | Licença | Último commit / tag | Como resolve a dor | Maturidade | Como o Dove pode aproveitar |
|---|---|---|---|---|---|
| simonw/llm — <https://github.com/simonw/llm> | Apache-2.0 · 2026-10-18 · 0.36 | Verificado (licença/versão); recursos de log **não verificados nesta pesquisa** | CLI que registra prompts e respostas em banco local | Ativo | **Copiar o padrão** (registro local em SQLite opcional), mas o Dove segue só com arquivos JSON |
| Busca FTS5 de sessões do Hermes — <https://github.com/NousResearch/hermes-agent> | MIT | Verificado no README | Busca de texto nas sessões passadas, com resumo | Ativo | **Copiar a ideia** com `grep` ou índice opcional; evitar reler o histórico inteiro |
| Retenção de sessões do Claude Code (`cleanupPeriodDays`, padrão 30 dias para dados de sessão) — <https://code.claude.com/docs/en/costs> | Proprietário | Verificado (para relatórios) | Limpeza automática | Padrão | **Recomendar** uma política de retenção no Dove (arquivar mensagens fechadas após N dias) |
| `a2a log` do Dove (`cmd_log`) | Interno | — | Lista eventos recentes | — | **Ampliar** com filtro por missão e por agente |

**Recomendação:** mover mensagens de missões fechadas para `~/.a2a/archive/` com um índice pequeno (ID, título, data, agentes), e manter o `bus/` só com o que está aberto.

---

## Os 5 maiores impactos para o Dove, em ordem

| # | Recomendação | Por que | Esforço |
|---|---|---|---|
| 1 | **Medir custo e cache por agente e missão** — gravar `total_cost_usd` e contagens de cache a cada `task` executada por `claude -p`; `a2a cost` mostra o agregado; `ccusage` como opcional | Sem medição, nada do resto pode ser comprovado | M |
| 2 | **Prefixo estável nos textos que o Dove emite** — onboard, brief e cabeçalhos fixos no início; dinâmicos (contagens, horas) no fim; nada que troque ferramentas no meio da sessão | Leitura de cache custa 0,1× (0,05× em Opus/Sonnet 5.5); escrita custa 1,25× a 2× | P |
| 3 | **Entrega sem reenviar contexto** — `crossSessionInbound: hold` nas instruções; `wait` com agregação por janela; `brief` como leitura padrão; corpo só com `read` | Mensagem que acorda sessão ociosa reenvia o contexto inteiro | M |
| 4 | **Mapa de repositório cacheado por commit** — `a2a map` em stdlib, teto de linhas, chave pelo SHA; o `brief` traz só caminho e SHA | Padrão do Aider (limite de 1024 tokens e cache em disco), sem tree-sitter | M |
| 5 | **Handoff estruturado com `/clear`** — ao `ctx ≥ 80`, o agente grava um handoff de ~15 linhas na missão e troca de contexto; `/compact` só quando a continuidade importa | `/compact` é uma requisição grande; `/clear` é gratuito | M |

Esforço: P = pequeno (uma função ou texto), M = médio (um comando novo ou mudança de formato), G = grande (mudança de modelo de dados).

---

## Riscos

- **Licenças:** Serena é GPL-3.0 (integrar, não copiar); Task Master tem Commons Clause (não pode ser vendido como serviço); Langfuse e LiteLLM têm pastas com licença própria; MCP está em transição de MIT para Apache-2.0.
- **Projetos parados ou pré-lançamento:** RouteLLM sem commit desde 2024-08; Aider sem commit desde 2026-05; Task Master em RC.
- **Cache expira:** TTL de 5 min na API (padrão). Agente ocioso por mais tempo paga a escrita de novo. Isso pode contrariar a recomendação 3 se o agente só lê de tempos em tempos.
- **Números mudam:** preços, TTL e pisos de cache mudam por modelo e versão; os valores aqui são de 2026-10-19 da doc da Anthropic.
- **OpenAI e Codex não verificados:** a doc não abriu. Não tomar decisões sobre cache do Codex com base nesta pesquisa.
- **Medição é estimativa:** o próprio Claude Code diz que o custo do `/usage` é calculado localmente a partir de preço de lista, e que o cobrado está no console. Usar como tendência, não como fatura.
- **Privacidade:** ccusage e Langfuse leem ou guardam conteúdo de sessão. Por padrão, o Dove não deve enviar nada a serviços externos.
- **Restrição stdlib:** tudo que foi recomendado como "copiar o padrão" é reimplementável em stdlib. Só as ferramentas marcadas como "integrar como opcional" exigem instalação do usuário.
- **Windows:** caminhos com barra e `git ls-files` precisam de teste no Windows antes de adotar o mapa de repositório.

---

## Fontes

Documentação oficial verificada:
- Prompt caching (Anthropic): <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>
- Custos do Claude Code: <https://code.claude.com/docs/en/costs>
- Claude Code programático (`-p`, `total_cost_usd`, `--bare`): <https://code.claude.com/docs/en/headless>

Repositórios verificados (licença, último commit, tag, e no caso de Aider, código-fonte):
- <https://github.com/Aider-AI/aider> (`aider/repomap.py`, `aider/args.py`)
- <https://github.com/NousResearch/hermes-agent> (README; lista de arquivos)
- <https://github.com/musistudio/claude-code-router>
- <https://github.com/BerriAI/litellm>
- <https://github.com/lm-sys/RouteLLM>
- <https://github.com/ryoppippi/ccusage>
- <https://github.com/langfuse/langfuse>
- <https://github.com/Helicone/helicone>
- <https://github.com/yamadashy/repomix>
- <https://github.com/mufeedvh/code2prompt>
- <https://github.com/oraios/serena>
- <https://github.com/zilliztech/claude-context>
- <https://github.com/letta-ai/letta>
- <https://github.com/mem0ai/mem0>
- <https://github.com/getzep/graphiti>
- <https://github.com/cline/cline>
- <https://github.com/samuelcolvin/watchfiles>
- <https://github.com/gorakhargosh/watchdog>
- <https://github.com/a2aproject/A2A>
- <https://github.com/pre-commit/pre-commit>
- <https://github.com/ast-grep/ast-grep>
- <https://github.com/github/spec-kit>
- <https://github.com/eyaltoledano/claude-task-master>
- <https://github.com/agentsmd/agents.md>
- <https://github.com/modelcontextprotocol/modelcontextprotocol>
- <https://github.com/toon-format/toon>
- <https://github.com/qodo-ai/pr-agent>
- <https://github.com/anthropics/claude-code-action>
- <https://github.com/daaain/claude-code-log>
- <https://github.com/traceloop/openllmetry>
- <https://github.com/simonw/llm>
- <https://github.com/openai/codex> (licença e tag; docs externas não verificadas)
- <https://github.com/anthropics/claude-code> (proprietário; só para referência de versão)

Fontes não acessíveis ou só por fonte secundária:
- Docs de cache da OpenAI (`developers.openai.com`): não acessível; resumo de busca de LiteLLM, não verificado no original.
- Docs do Aider (`aider.chat`) e do Letta (`docs.letta.com`): não acessíveis.
- Docs do Codex (AGENTS.md, exec): só como links no repositório; não acessíveis.
- Paper do mem0 (`mem0.ai/research`): não verificado.

Dove (referência interna): `README.md`, `a2a.py` (`cmd_wait`, `cmd_log`, `cmd_read`), commits `6a181dd` e `17ccad1`.
