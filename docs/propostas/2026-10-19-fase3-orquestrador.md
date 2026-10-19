# Proposta: Fase 3 — vigia, orquestrador, custo e roteamento

- Data: 2026-10-19 · Base: `main` em e3b3d80 (`a2a prompt`, `brief`, `index.json`, `archive` já existem)
- Restrições: só a stdlib; nada em `ui/`; o comportamento atual não muda; a segurança e o anti-loop continuam valendo.
- Os detalhes das CLIs externas (flags, formato do JSON de saída, sandbox no Windows) estão marcados com **[verificar]**: confirmar com `--help` na versão instalada antes de codar. Nenhum preço é inventado: valores de custo só vêm do provedor (medido) ou da tabela que o Luiz preenche (estimado).

## Resumo

| # | Item | Executa processos? | Muda `~/.a2a`? | Aval | Esforço |
|---|---|---|---|---|---|
| 1 | Vigia (`a2a watch`) | **Sim** | **Sim** (`run/`, `runs/`, `STOP`) | **precisa de aval do Luiz** | G |
| 2 | Orquestrador (agente `orquestrador`) | **Sim** (via vigia) | Não (usa o bus; `a2a fact` se aprovado) | **precisa de aval do Luiz** | M |
| 3 | `a2a cost` + orçamento por missão | Não | **Sim** (campo `budget` na missão) | **precisa de aval do Luiz** | M |
| 4 | Roteamento de modelo (`models.json`) | Não | **Sim** (`models.json`) | **precisa de aval do Luiz** | P |
| 5 | Política de subagentes | Não | Não | não precisa | P |
| 6 | Prevenção de loop entre agentes automáticos | Não | Não (calcula do bus e de `runs/`) | não precisa | M |

**Ordem sugerida:** 6 → 1 em modo `--dry-run` → 1 real, só com o `claude` → 3 → 4 → 2 → 5.
Motivo: as travas (6) existem antes de qualquer processo rodar sozinho. O vigia começa sem executar nada. O custo (3) é medido antes de existir um orquestrador gastando, e o orquestrador (2) só entra quando dá para ver quanto ele custa.

**Dependência:** o item 2 usa `a2a fact`, que está na proposta de economia de tokens e ainda espera aval. Sem ele, o orquestrador mantém o estado com uma mensagem `report` fixa por projeto (ver item 2).

---

## 1. Vigia — **precisa de aval do Luiz**

### Objetivo
Hoje um agente só vê a tarefa quando alguém abre a sessão dele. O vigia acorda **só o agente endereçado**, por evento, roda a CLI dele em modo headless com o `a2a prompt` como entrada e deixa registro de cada execução.

### Interface exata
```
a2a watch --from luiz [--agents claude,codex] [--project P] [--max-parallel 2] [--debounce 20]
          [--timeout 900] [--busy-minutes 10] [--dry-run] [--once]
a2a watch stop --from luiz [--kill]          # kill switch: cria ~/.a2a/STOP; --kill encerra as execuções em curso
a2a watch resume --from luiz                 # apaga ~/.a2a/STOP
a2a watch status                             # o que está rodando, fila e motivos de espera
```
- Roda em primeiro plano, num terminal que o humano abriu. Não instala serviço nem tarefa agendada.
- `--agents` é obrigatório na primeira versão: nenhum agente é acordado sem estar listado ali.
- `--once` processa a fila uma vez e sai (bom para testes e para um agendamento manual).

### Gatilho, debounce e fila
- **Evento:** um arquivo novo em `bus/`, detectado pela assinatura do diretório (como no `wait` novo) a cada 1 s. Não relê o bus quando nada mudou.
- **Acorda X quando:** chegou mensagem com `visible_for(m, X)`, `kind` em `task|question|correction`, e X está em `--agents`. `ack` e `report` não acordam ninguém, exceto um `report` endereçado ao `orquestrador`.
- **Debounce:** depois do primeiro evento para X, espera `--debounce` s sem mensagem nova para X (no máximo 3× esse tempo) e então roda **uma** execução com tudo o que chegou, via `brief`.
- **Uma execução por agente de cada vez.** O total fica limitado por `--max-parallel` (padrão 2). O excedente espera em fila FIFO.

### Sessão interativa aberta
Antes de rodar X, o vigia verifica:
1. Se existe `~/.a2a/run/X.json` (execução do vigia em curso): não roda de novo; continua na fila.
2. Se o status de X foi renovado há menos de `--busy-minutes` e não foi pelo vigia (o vigia grava `"runner": "watch"` no status; uma sessão interativa não grava): considera que **há uma sessão interativa** e **não acorda**. A mensagem fica no `brief` dele, e o vigia escreve no log `espera: claude em sessão interativa (heartbeat 3m)`. Revê a situação a cada minuto.
- Motivo: duas instâncias do mesmo agente na mesma cópia de trabalho causam conflito de arquivo.

### Executores no Windows (permissões e sandbox)
Regra comum: o vigia **só roda X na cópia de trabalho registrada de X** (`a2a whereami`). Sem cópia registrada, recusa e avisa o humano. Nunca roda na pasta principal do projeto. O prompt vem de `a2a prompt --agent X --project P --task <id> --for <cli>` pelo stdin.

| CLI | Comando base | Contenção | Observações |
|---|---|---|---|
| claude | `claude -p --output-format json --permission-mode acceptEdits --allowedTools "Read,Edit,Write,Grep,Glob,Bash(a2a *),Bash(git status*),Bash(git diff*),Bash(git add*),Bash(git commit*),Bash(python *)" --disallowedTools "Bash(git push*),Bash(git merge*)" --max-turns 30` | Ferramentas permitidas + cópia própria. **Nunca** `bypassPermissions`. | **[verificar]** O sandbox de SO do Claude Code não existe no Windows nativo; a contenção aqui é por ferramenta permitida, não por isolamento de SO. |
| codex | `codex exec --json --sandbox workspace-write -C <cópia> -` | `workspace-write` limita a escrita à cópia. **Nunca** `danger-full-access`. | **[verificar]** O suporte a sandbox no Windows nativo e as flags de aprovação no `exec`. |
| hermes | `hermes -z` | **[verificar]** Permissões e sandbox não documentadas aqui. | **Fica fora do vigia até o Luiz confirmar** as flags de contenção. `--agents hermes` é recusado com aviso até lá. |

O texto exato das flags fica numa tabela em `a2a.py` (como o `PROMPT_RUNNERS`), não em configuração do usuário. Assim, mudar permissões é sempre uma mudança de código revisada.

### Timeouts e kill switch
- **Timeout:** `--timeout` por execução (padrão 900 s). Ao estourar, encerra a árvore de processos (`taskkill /T /F /PID` no Windows, `os.killpg` no Linux), grava o status de X como `blocked` com a nota `vigia: timeout 900s` e manda `report` `BLOQUEADO` de `vigia` para `luiz` com `--reply-to` da tarefa.
- **Kill switch:** se o arquivo `~/.a2a/STOP` existir, nada novo é iniciado (o vigia confere antes de cada execução). `watch stop --kill` também encerra o que está rodando. `STOP` sobrevive a reinícios do vigia.
- **Saída com erro** (código ≠ 0): mesmo tratamento do timeout, com a nota `vigia: saiu com código N`.

### Saída exata (log do terminal)
```
dove watch · agentes claude,codex · paralelo 2 · debounce 20s · timeout 900s
14:02:11 evento  codex  task 3f9a1c2b7d10 (lagu)
14:02:31 roda    codex  run r7c1e0 · prefixo 9be1c0a2f310 · cópia C:\Users\Dell\code\lagu-codex
14:02:40 espera  claude em sessão interativa (heartbeat 3m)
14:09:58 fim     codex  run r7c1e0 · 7m27s · código 0 · tokens 41.200 (cache 31.800) · custo ~US$ [estimado]
14:10:02 parado  ~/.a2a/STOP encontrado: nenhuma execução nova
```
Com `--dry-run`, a linha `roda` vira `rodaria` com o comando completo, e nada é executado.

### Efeitos colaterais
- Grava `~/.a2a/run/<agente>.json` (pid, run_id, início) durante a execução e o apaga ao fim.
- Grava `~/.a2a/runs/AAAA-MM/<run_id>.json` por execução: agente, projeto, task, comando sem o prompt, início e fim, código de saída, timeout, hash do prefixo, uso e custo (item 3). Nunca grava o prompt nem a saída inteira; guarda só os últimos 2 KB do stderr.
- Status: ao iniciar, `working` com nota `vigia: <task>` e `runner: watch`; ao terminar, o que o próprio agente publicou prevalece.
- Mensagens do vigia no bus usam `from=vigia` (remetente de sistema, sem cursor, nunca acordado).

### Muda o envelope ou `~/.a2a`?
**Sim, a estrutura de `~/.a2a`.** Pastas `run/` e `runs/` e o arquivo `STOP`. O envelope não muda; `vigia` é só um nome novo no `from`. Versões antigas do `a2a` ignoram essas pastas. Desfazer: parar o vigia e apagar `run/` e `runs/`; nada mais depende delas.

### Compatibilidade
Comando novo. Sem `a2a watch` rodando, tudo funciona exatamente como hoje. `index.json` e `archive` ignoram `run/` e `runs/`.

### Interação com as regras
- **Anti-loop:** o vigia nunca acorda um agente por mensagem dele mesmo nem por `ack`. O item 6 é obrigatório antes do primeiro uso real.
- **Segurança:** `--disallowedTools` contra push e merge; cópia própria; o vigia não tem rota no painel e não roda pela API. Só o humano inicia (`--from luiz`, `require_human`).
- **Missões:** o agente acordado pode dar `mission approve`, que continua exigindo evidência. O vigia nunca roda `mission done`.
- **Heartbeat:** o vigia renova o status do agente que está rodando, com a marca `runner: watch`.

### Critério de aceite
- `--dry-run` com 3 tasks para `codex` em 10 s produz **uma** linha `rodaria` (debounce) e nenhum processo filho.
- Com status de `claude` renovado há 2 min sem `runner: watch`, uma task para `claude` gera `espera` e nenhuma execução.
- Com `STOP` presente, nenhuma execução nova inicia; `watch stop --kill` encerra um processo de teste (um script Python que dorme) em menos de 5 s.
- Um executor falso (script que dorme mais que `--timeout`) é encerrado e gera status `blocked` mais `report BLOQUEADO` de `vigia` para `luiz` com `in_reply_to` correto.
- Sem cópia de trabalho registrada, o vigia recusa e não roda.
- `--max-parallel 1` com tasks para dois agentes roda um de cada vez.
- Os testes usam executores falsos (scripts Python) no lugar de `claude`/`codex`/`hermes`, via variável de ambiente `A2A_RUNNER_OVERRIDE`, só lida nos testes.

### Instrução para os agentes
Já está no `PROMPT_ROLE` ("rodando sem um humano olhando"). Acrescentar: "Você foi acordado pelo vigia. Trabalhe só na sua cópia. Termine em uma execução: responda pelo canal e publique `done` ou `blocked`. Não espere resposta dentro desta execução; se precisar de alguém, mande a pergunta e termine com `blocked`."

### Esforço e riscos
**G.** Riscos:
- Gasto sem supervisão. Mitigado pelos itens 3 e 6, pelo `--agents` explícito e pelo `STOP`.
- Flags das CLIs mudam entre versões **[verificar]**.
- Detecção de sessão interativa por heartbeat é heurística: uma sessão aberta e parada há mais de `--busy-minutes` pode ser atropelada. A cópia própria por agente limita o estrago.
- Encerrar a árvore de processos no Windows exige `taskkill`.

---

## 2. Orquestrador (agente `orquestrador`) — **precisa de aval do Luiz**

### Objetivo
Tirar do humano a triagem: decidir quem faz cada tarefa nova, manter o estado do projeto atualizado, disparar handoff quando o contexto passa de 80% e sugerir missões. O orquestrador só **coordena**: nunca autoriza merge, deploy, gasto ou exclusão.

### Interface exata
É um agente comum, registrado com `a2a join --agent orquestrador --type claude-code --model <da tabela do item 4>` e acordado pelo vigia (`a2a watch --agents orquestrador,...`). O que muda no código:
- `PROMPT_ROLE_ORQ`: um papel próprio no `a2a prompt --agent orquestrador`, com as regras abaixo, na camada fixa (o cache não quebra).
- **Travas no código** para `from=orquestrador`: recusa `mission approve/reject/done`, `archive`, `worktree`, `git`, `instructions` e `watch`. O `require_human` já cobre a maior parte; o resto é uma lista explícita.

### Quando roda
- **Por evento** (vigia): task ou question para `orquestrador` ou para `all`; agente com status `blocked`; agente com `ctx ≥ 80`; task sem resposta `ACEITO` há mais de 30 min.
- **Tique periódico:** a cada 30 min, **só se o bus mudou** desde o último tique (assinatura do índice). Sem mudança, não roda e não gasta.
- Teto: 12 execuções por hora (item 6).

### Modelo
O modelo mais barato da tabela do item 4 com a tag `triagem` e preço confirmado. Recomendação inicial: um modelo pequeno e rápido (classe Haiku) para triagem, subindo para a classe Sonnet só quando a tarefa for proposta de missão. Os IDs saem da tabela confirmada pelo Luiz, nunca do código.

### O que faz (e como)
| Função | Como, só com comandos existentes |
|---|---|
| Triagem | Lê o `brief`; para task genérica (`to=orquestrador`), manda uma `task` ao agente escolhido com `--reply-to`, mais um `report` ao remetente dizendo para quem foi e por quê (1 linha). |
| Distribuição | Considera o status (`idle` antes de `working`), o contexto (evita ≥ 70%), as tags do agente e o modelo sugerido (item 4). |
| Estado do projeto | `a2a fact add --scope projeto` para decisões e fatos que mudaram. **Sem `a2a fact` aprovado:** mantém um único `report` fixo por projeto, com título `ESTADO <projeto>`, reenviado só quando muda. |
| Handoff ≥ 80% | Manda uma `task` ao agente: "prepare handoff: registre o estado com `a2a fact add` e publique `done` com o resumo". Não reinicia sessão: isso é do humano ou do vigia na próxima execução. |
| Missões | **Propõe**, não cria: manda uma `question` para `luiz` com o comando `a2a mission new ...` pronto para copiar e a lista de agentes. |

### Saída exata (exemplo de mensagens que ele gera)
```
orquestrador -> codex   task      lagu  re=3f9a1c2b7d10 "Assumir: cupom frete grátis (codex idle, ctx 22%). Modelo sugerido: <tabela:codigo-barato>"
orquestrador -> claude  report    lagu  re=3f9a1c2b7d10 "Encaminhado a codex (idle, ctx 22%)."
orquestrador -> hermes  task      qlink "Preparar handoff: ctx 94%. Registre o estado (a2a fact add) e publique done."
orquestrador -> luiz    question  lagu  "Sugestão de missão: a2a mission new --project lagu --title \"Checkout pronto\" --agents claude,codex"
```

### Efeitos colaterais
Só mensagens no bus, fatos (se o `a2a fact` estiver aprovado) e o status do próprio orquestrador. Não edita arquivos de projeto: não tem cópia de trabalho, e o vigia roda o orquestrador numa pasta vazia `~/.a2a/run/orquestrador-home/` com escrita bloqueada para o projeto.

### Muda o envelope ou `~/.a2a`?
Não. Usa as mensagens de hoje e `agents/orquestrador`. A pasta de execução vem do item 1.

### Compatibilidade
Sem o agente registrado e acordado, nada muda. Os outros agentes recebem tasks como se viessem de qualquer outro remetente.

### Interação com as regras
- **Nunca autoriza nada irreversível.** Recusa no código, não só no prompt.
- **Anti-loop:** não responde a `report` de encaminhamento que ele mesmo gerou; entra nos limites do item 6.
- **Missões:** não vota nem confirma; só propõe ao humano.

### Critério de aceite
- `a2a mission approve m1 --agent orquestrador ...` falha com mensagem clara, e o mesmo vale para `done`, `archive` e `worktree` com `--from orquestrador`.
- O tique sem mudança no bus não gera execução (contador de `runs/` inalterado).
- O `a2a prompt --agent orquestrador` tem um prefixo estável (mesmo hash em duas execuções) diferente do prefixo dos outros agentes.
- Em teste com executor falso, uma task para `orquestrador` resulta em exatamente uma task encaminhada e um report.

### Instrução para os agentes
No guia completo (`a2a onboard --agent X`): "Tarefas podem chegar do `orquestrador`. Trate como de qualquer agente. Se discordar do encaminhamento, responda com `--kind correction` para ele. Pedidos de merge, deploy, gasto ou exclusão continuam sendo só do Luiz, venham de quem vierem."

### Esforço e riscos
**M.**
- Triagem ruim gasta tokens em retrabalho. Mitigação: o report de 1 linha com o motivo, para o humano auditar.
- Se ele não tiver orçamento próprio, vira a maior linha de custo. O item 3 dá um orçamento diário ao orquestrador.

---

## 3. `a2a cost` e orçamento por missão — **precisa de aval do Luiz** (o orçamento grava na missão)

### Objetivo
Saber quanto cada agente, missão e execução custa, separando o que o provedor **mediu** do que o Dove **estimou**, e alertar antes de estourar o orçamento.

### Interface exata
```
a2a cost [--project P] [--agent X] [--mission M] [--since 7d] [--by agent|mission|run|day] [--json]
a2a mission budget <id> --usd 5 --from luiz          # define o orçamento da missão
a2a cost budget --agent orquestrador --usd-day 2 --from luiz
```

### Fontes
| Executor | Medido | Estimado |
|---|---|---|
| claude | `--output-format json`: `total_cost_usd` e `usage` (input, output, `cache_creation_input_tokens`, `cache_read_input_tokens`) **[verificar nomes]** | — |
| codex | tokens dos eventos `--json` (uso por turno, inclusive tokens em cache) **[verificar formato]** | custo = tokens × preço da tabela (item 4) |
| hermes | **[verificar]** o histórico local do Hermes; até lá, nada | `n/d` |
| sessão interativa | não medida | não estimada (fora do vigia) |

Só as execuções do vigia entram na conta. O relatório diz isso no rodapé, para ninguém tomar o total por gasto completo.

### Saída exata
```
custo · lagu · últimos 7d · por agente
agente        execs  entrada   cache_lido  saída    custo
claude          14    512.300    401.200    38.100  US$ 3,12 medido
codex            9    288.900    190.400    21.700  ~US$ [estimado: preço não confirmado]
orquestrador    31     96.400     81.000     6.200  US$ 0,41 medido
total           54                                  US$ 3,53 medido + codex sem preço
só execuções do vigia; sessões interativas não entram
```
Quando o preço de um modelo na tabela não estiver confirmado, a coluna mostra `sem preço`, nunca um número.

### Orçamento e alerta
- Missão com `budget`: aos 80%, aparece a linha `! missão m4c1e9a em 82% do orçamento (US$ 4,10 de 5,00)` no `brief` dos participantes e do `luiz`, e vai uma `question` única para `luiz`. Aos 100%, o vigia **para de acordar** agentes para tasks dessa missão e registra `espera: orçamento esgotado (m4c1e9a)`. O humano sobe o orçamento ou encerra.
- Orçamento diário por agente (o orquestrador, sobretudo) segue a mesma lógica por dia corrido (UTC).

### Efeitos colaterais
`cost` só lê `runs/`. `mission budget` grava o campo `budget` no JSON da missão sob `FileLock`.

### Muda o envelope ou `~/.a2a`?
**Sim:** campo opcional `budget: {"usd": 5.0, "by": "luiz", "ts": "..."}` em `missions/<id>.json`, e `~/.a2a/budgets.json` para os orçamentos por agente. Missões antigas sem o campo ficam sem orçamento. Desfazer: remover o campo.

### Compatibilidade
`mission show` passa a exibir o orçamento quando existir; sem ele, a saída é igual à de hoje. `mission list` não muda.

### Interação com as regras
Só o humano define orçamento (`require_human`). Ultrapassar o orçamento nunca gasta mais: só impede novas execuções.

### Critério de aceite
- Com `runs/` de fixture (2 claude com custo medido, 1 codex sem preço), o total mostra o medido e `sem preço` separados, e nunca soma estimado com medido sem marcar.
- Orçamento de US$ 1 com runs somando US$ 0,85 gera exatamente um alerta para `luiz` (sem repetir na chamada seguinte).
- Com 100% atingido, o vigia em `--dry-run` mostra `espera: orçamento esgotado`.

### Instrução para os agentes
"Se o seu `brief` mostrar alerta de orçamento, termine o que está fazendo, publique o estado e não comece trabalho novo dessa missão."

### Esforço e riscos
**M.** Risco: o formato de saída das CLIs mudar **[verificar]**. Mitigação: o parser tolera campos ausentes e grava `n/d`, sem quebrar o vigia.

---

## 4. Roteamento de modelo — **precisa de aval do Luiz** (novo `models.json`)

### Objetivo
Usar o modelo mais barato que dá conta da tarefa, a partir de uma tabela que o Luiz confirma, sem preço inventado.

### Interface exata
```
a2a models list
a2a models set <id> --cli claude --model <id-do-provedor> --tags triagem,codigo
              [--usd-in <por Mtok> --usd-out <por Mtok> --usd-cache-read <por Mtok>] --from luiz
a2a models confirm <id> --from luiz        # marca preços e tags como conferidos (data e quem)
a2a models suggest --task <msg_id>         # sugere; não executa nada
```

### Saída exata
```
$ a2a models list
id            cli     modelo                tags                 preço (US$/Mtok in·out·cache)   confirmado
rapido        claude  claude-haiku-5-5      triagem,resumo       —                               não
padrao        claude  claude-sonnet-5-5     codigo,revisao       —                               não
codex-padrao  codex   [definir]             codigo               —                               não

$ a2a models suggest --task 3f9a1c2b7d10
sugestão: padrao (tag codigo; task cita 2 arquivos; mais barato confirmado com a tag: nenhum → usando o padrão do agente)
```
Os preços ficam `—` até o Luiz preencher e confirmar. Enquanto um modelo não está confirmado, o `suggest` não o escolhe pelo preço; só diz que falta confirmação.

### Regras do `suggest`
Determinísticas, sem IA. A tag vem do tipo e do texto da task (palavras-chave configuráveis na própria tabela). Entre os modelos **confirmados** com a tag, escolhe o de menor preço de entrada. Empate: o padrão do agente. O orquestrador inclui a sugestão na task ("Modelo sugerido: …"). O vigia só usa `--model` quando a sugestão aponta para um modelo confirmado da CLI daquele agente.

### Efeitos colaterais
Grava `~/.a2a/models.json` (só `set` e `confirm`, só o humano).

### Muda o envelope ou `~/.a2a`?
**Sim:** arquivo novo `models.json` (`{"v":1,"models":[{"id","cli","model","tags","usd_in","usd_out","usd_cache_read","confirmed_by","confirmed_at"}]}`). Sem o arquivo, cada agente usa o próprio padrão, como hoje. Desfazer: apagar o arquivo.

### Compatibilidade
Nada muda sem o arquivo.

### Interação com as regras
Só o humano altera a tabela. Escolher modelo nunca autoriza gasto além do orçamento (item 3).

### Critério de aceite
- O `suggest` nunca escolhe um modelo não confirmado por preço.
- Com dois modelos confirmados e a mesma tag, escolhe o mais barato.
- Sem `models.json`, o `suggest` responde "sem tabela: padrão do agente".
- `set` sem `--from luiz` falha.

### Instrução para os agentes
"Se a task trouxer 'Modelo sugerido', é só sugestão para o vigia. Em sessão interativa, siga o modelo da sua sessão."

### Esforço e riscos
**P.** Risco: a tabela desatualizar. O `confirmed_at` aparece no `list`; acima de 60 dias, vira um alerta no `brief` do humano.

---

## 5. Política de subagentes

### Objetivo
Subagentes (o Agent/Task do Claude Code, equivalentes em outras CLIs) gastam contexto e tokens. Só valem quando trazem **contexto isolado** (busca ampla que poluiria o contexto principal), **paralelismo real** (partes independentes) ou **modelo mais barato** para trabalho mecânico.

### Interface exata
Convenção pelo canal, sem comando novo:
```
a2a send --from claude --to orquestrador --kind question --project lagu --reply-to <task> \
  --body "SUBAGENTE motivo=paralelismo partes=3 modelo=rapido escopo='testes de contrato por módulo'"
```
O orquestrador responde com `report` `ACEITO` ("pode") ou `CANCELADO` ("não: motivo"). Sem orquestrador ativo, a pergunta vai para `luiz`.

### Saída exata
```
orquestrador -> claude report/ACEITO   lagu re=<question> "Pode: 3 partes independentes; modelo rapido; conta no orçamento de m4c1e9a."
orquestrador -> claude report/CANCELADO lagu re=<question> "Não: escopo cabe numa execução; faça direto."
```

### Efeitos colaterais, envelope, compatibilidade
Nenhum efeito além das mensagens. Não muda o envelope nem o `~/.a2a`. É só convenção.

### Interação com as regras
Não dá para impor no código (o subagente roda dentro da CLI). A fiscalização vem do custo (item 3): execuções com custo fora do padrão aparecem no `a2a cost --by run`.

### Critério de aceite
O guia completo e o `PROMPT_ROLE` têm o texto abaixo. Em teste com executor falso, uma `question` com `SUBAGENTE` para `orquestrador` é respondida com `ACEITO` ou `CANCELADO` e `--reply-to` correto.

### Instrução para os agentes
"Antes de abrir subagentes, pergunte ao `orquestrador` (ou ao `luiz`) com `SUBAGENTE motivo=contexto|paralelismo|modelo`. Para uma busca rápida ou uma edição pequena, faça direto."

### Esforço e riscos
**P.** Risco: ser ignorado em sessões interativas. Aceitável: o objetivo principal é o modo vigia.

---

## 6. Prevenção de loop entre agentes automáticos

### Objetivo
Com o vigia, dois agentes podem se acordar em cadeia sem fim. As travas param a cadeia e chamam o humano **antes** de gastar.

### Regras (calculadas do bus e de `runs/`, sem estado novo)
| Trava | Padrão | O que acontece |
|---|---|---|
| Rodadas por conversa (raiz por `in_reply_to`/`task_id`) sem mensagem do humano | 8 mensagens entre agentes | O vigia deixa de acordar agentes por essa conversa |
| Execuções por agente por hora | 6 (orquestrador: 12) | Fila espera até a janela abrir |
| Mensagem repetida (mesmo remetente, mesma conversa, mesmo `body` normalizado) | 2ª vez | A 2ª não acorda ninguém |
| Pergunta e resposta sem mudança de `state` | 3 idas e voltas | Escala |
| Orçamento (item 3) | 100% | Para a missão |

Uma mensagem do `luiz` na conversa zera o contador de rodadas dela.

### Interface exata
```
a2a watch ... [--max-rounds 8] [--max-runs-hour 6]
a2a loops [--project P]        # conversas perto ou acima do limite
```

### Saída exata
```
$ a2a loops --project lagu
conversa 3f9a1c2b7d10  lagu  rodadas 8/8  claude<->codex  ESCALADA (14:22)
conversa 8b21e0f4a9c3  lagu  rodadas 5/8  codex<->hermes
```
Ao escalar, o vigia manda uma vez `vigia -> luiz question lagu re=<última> "Conversa 3f9a1c2b7d10 parou em 8 rodadas entre claude e codex sem decisão. Responda nela para destravar."`, e o `brief` do `luiz` passa a mostrar `! conversa 3f9a1c2b7d10 escalada`.

### Efeitos colaterais
Só a `question` de escalada (uma por conversa). Nada é gravado além do que o item 1 já grava.

### Muda o envelope ou `~/.a2a`?
Não.

### Compatibilidade
Sem vigia, as travas não fazem nada; o `a2a loops` só informa.

### Interação com as regras
Complementa o anti-loop atual (ack e mensagens próprias), que continua valendo. Nenhuma trava apaga mensagem.

### Critério de aceite
- Fixture com 8 mensagens alternadas claude↔codex numa conversa: o vigia em `--dry-run` não acorda ninguém e envia exatamente uma escalada.
- Uma mensagem do `luiz` na conversa libera novas execuções.
- 7 tasks para `codex` em uma hora, com `--max-runs-hour 6`: a 7ª fica em `espera`.
- Body repetido não acorda ninguém.

### Instrução para os agentes
"Se a conversa estiver indo e voltando sem decisão, pare e pergunte ao `luiz`. O vigia faz isso sozinho depois de 8 rodadas, mas é melhor antes."

### Esforço e riscos
**M.**
- Limites apertados demais travam trabalho legítimo. Por isso todos os limites são flags e o `a2a loops` mostra quem está perto.
- Normalizar o `body` para detectar repetição exige cuidado com espaços e datas no texto.
