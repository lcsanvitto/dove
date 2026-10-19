# Proposta: interface enxuta para os agentes (Fase 2 do barramento)

- Data: 2026-10-18 · Base: `main` em 63e3eba (`a2a.py` 0.6.0)
- Origem: análise registrada no canvas "Dove — mapa do projeto", quadro D (https://claude.ai/artifact/FHZqPEK44S47K51biYCwnv)
- Fora do escopo: nada em `ui/` (a parte visual está pausada), nenhuma dependência fora da stdlib e nada que dispense a segurança ou o anti-loop.

**Princípio.** Agentes não leem a tela; leem o que a CLI devolve. A economia vem da saída da CLI e de quanto do `bus/` cada comando relê, não do layout.

## Resumo dos itens

| # | Item | Muda envelope ou `~/.a2a`? | Aval do Luiz |
|---|---|---|---|
| 1 | `a2a brief` | Não | não precisa |
| 2 | `a2a read --compact` | Não | não precisa |
| 3 | `wait` sem reler o bus à toa | Não | não precisa |
| 4 | Arquivos por referência (`files`) | **Sim (envelope)** | **precisa de aval do Luiz antes de implementar** |
| 5 | Índice materializado `index.json` | **Sim (`~/.a2a`)** | **precisa de aval do Luiz antes de implementar** |
| 6 | Arquivar mensagens encerradas | **Sim (`~/.a2a`)** | **precisa de aval do Luiz antes de implementar** |

Ordem sugerida: 1 → 2 → 3 (aditivos, ganho imediato) → medir → decidir 4, 5 e 6.

---

## 1. `a2a brief`

**1. Objetivo.** Hoje, para se atualizar, um agente roda `inbox` (que não marca como lido e repete tudo a cada chamada), um `read` por mensagem (envelope de 14 campos indentado) e `mission list` (todas as missões, inclusive as que não são dele). O `brief` entrega numa chamada só o que é do agente, em poucas linhas.

**2. Interface exata.**
```
a2a brief --agent X [--project P] [--mark-read] [--limit N] [--width W] [--json] [--no-auto-status]
```
- `--agent X` (obrigatório): de quem é o resumo.
- `--project P`: filtra mensagens, tarefas e missões pelo projeto.
- `--mark-read`: marca como lidas as mensagens listadas em `N` e `ACK` (grava em `cursor/X.json`, como o `read`). Sem a flag, nada é marcado.
- `--limit N` (padrão 20): máximo de linhas `N`; o excedente vira a linha `… +K novas (a2a brief --limit 0 para todas)`. `0` = sem limite.
- `--width W` (padrão 100): tamanho máximo do resumo de cada linha, em caracteres.
- `--json`: a mesma informação em uma linha de JSON compacto (sem indent, sem campos vazios).
- `--no-auto-status`: não renova o heartbeat.

**3. Saída exata.** Cenário: agente `codex`, status blocked com ctx 82; 4 mensagens não lidas (1 é ack); 1 tarefa aberta já lida; 2 missões em que ele participa (uma esperando o aval dele, outra já com o aval dele dado).
```
@codex blocked ctx=82 novas=4 abertas=1 aval=1
N 3f9a1c2b7d10 claude task lagu 2m "cupom de frete grátis: aplicar regra acima de R$ 199"
N 8b21e0f4a9c3 hermes report/CONCLUIDO qlink 5m "E2E staging: 148 ok, 2 falhas (frete grátis)" +evid
N c47d0e11aa02 luiz question lagu 9m "a credencial de homologação chegou?"
ACK 1 (claude)
T 1e2b9c0d4f55 de=luiz lagu 14m "Migrar o webhook de pagamentos para a assinatura nova"
M mb222288 lagu aberta 2/3 "Checkout novo pronto para produção"
! ctx 82>=80: preparar handoff
! bloqueado: aguardando credencial do banco de homologação
```
Regras de formato (uma linha por item, campos fixos, separados por espaço):
- Cabeçalho: `@<agente> <estado> ctx=<n|-> novas=<n> abertas=<n> aval=<n>` (estado e ctx vêm de `effective_status`; `stale` aparece como `unknown`).
- `N`: mensagem não lida visível para X (`visible_for` + fora de `cursor/X.json`), exceto `ack`. Campos: `msg_id de kind[/STATE] [projeto] idade "resumo"`. O resumo é a primeira linha do `body`, cortada em `--width` (aspas internas trocadas por `'`). `+evid` aparece se `evidence` não for vazio. Em ordem cronológica, da mais antiga para a mais nova.
- `ACK <n> (<remetentes>)`: acks não lidos condensados numa linha; não se responde ack (anti-loop).
- `T`: tarefa aberta para X (`open_tasks`, `to == X`) que **já foi lida**; as não lidas já aparecem em `N` e não se repetem.
- `M`: missão em que X é participante, não concluída pelo humano, e cujo último veredito de X não é `approve`. Campos: `id [projeto] status k/n "título"`.
- `!`: alertas do próprio agente: `ctx >= CTX_HIGH`, status `blocked` (com a nota) e status `unknown (stale)`.
- Sem nada a mostrar: somente
```
@codex idle ctx=- novas=0 abertas=0 aval=0
(nada pendente)
```

**4. Efeitos colaterais.**
- Marca como lidas: só com `--mark-read`, e só as mensagens listadas em `N` e `ACK`. Sem a flag, não marca nada (mesmo comportamento do `inbox`).
- Status/heartbeat: renova o heartbeat como `inbox` (`auto(a, agent)`), sem mudar estado nem nota; desligável com `--no-auto-status`.
- Arquivos novos: nenhum. Usa `cursor/X.json` existente.

**5. Muda envelope ou `~/.a2a`?** Não.

**6. Compatibilidade.** Comando novo; `inbox`, `read`, `wait`, `ack` e `mission list` mantêm saída e comportamento idênticos.

**7. Interação com as regras.** Anti-loop: mensagens do próprio agente nunca aparecem (`visible_for`); acks são só contados. Missões: o `brief` só lista; aprovar continua exigindo `mission approve --evidence`. Heartbeat: igual ao `inbox`. Segurança: comando de CLI local, sem rota nova no painel.

**8. Critério de aceite** (em `tests/test_a2a.py`, com `A2A_HOME` temporário):
- Com o cenário acima, a saída é exatamente a do exemplo (exceto as idades, normalizadas no teste).
- Mensagens enviadas pelo próprio agente não aparecem em nenhuma linha.
- Sem `--mark-read`, duas chamadas seguidas produzem as mesmas linhas `N`; com `--mark-read`, a segunda chamada não tem linhas `N` nem `ACK`.
- Uma tarefa aberta e já lida aparece em `T`; depois de um report `CONCLUIDO` com `--reply-to`, ela some.
- Uma missão some de `M` depois de `mission approve` do agente e volta se ele der `reject`.
- `--project P` exclui itens de outros projetos; `--json` produz JSON válido em uma linha.
- O status do agente não muda de estado (só `updated`/`ts`); com `--no-auto-status`, o arquivo de status não é tocado.
- Agente sem nada pendente: exatamente as duas linhas do caso vazio.

**9. Instrução para os agentes** (substitui o passo 1 de "Ao começar uma sessão" no `ONBOARD_TEMPLATE` e acrescenta uma linha em "Durante o trabalho"):
```
1. `a2a brief --agent <seu-nome> --mark-read` — o que é seu: mensagens novas (N), tarefas abertas (T), missões esperando seu aval (M) e alertas (!). Use `a2a read <msg_id> --agent <seu-nome> --compact` só quando precisar do texto inteiro de uma mensagem.
```
```
- Para se atualizar no meio do trabalho, use `a2a brief --agent <seu-nome> --mark-read` (não `inbox` + `read` + `mission list`).
```

---

## 2. `a2a read --compact`

**1. Objetivo.** O `read` imprime os 14 campos indentados mesmo quando a maioria está vazia. O `--compact` imprime só o que tem conteúdo.

**2. Interface exata.** `a2a read <msg_id> --agent X --compact`

**3. Saída exata.**
```
1e2b9c0d4f55 luiz->codex task proj=lagu task=- 2026-10-18T14:02:11Z
Migrar o webhook de pagamentos para a assinatura nova (X-Signature).
Começar pelo handler e pelos testes.
```
Para um report com evidência:
```
8b21e0f4a9c3 hermes->codex report/CONCLUIDO proj=qlink re=1e2b9c0d4f55 2026-10-18T14:20:45Z
E2E staging: 148 ok, 2 falhas (frete grátis).
evidence: e2e/report.html
next_action: corrigir regra de frete acima de R$ 199
```
Linha 1: `msg_id from->to kind[/STATE] proj=P [re=in_reply_to] [task=task_id] data`. Depois vem o `body` inteiro, e então `campo: valor` só para `result`, `evidence`, `pending` e `next_action` não vazios. Mensagem inexistente: mesmo erro e mesmo código de saída de hoje.

**4. Efeitos colaterais.** Igual ao `read` atual: marca a mensagem como lida para `--agent`; não mexe no status; nenhum arquivo novo.

**5. Muda envelope ou `~/.a2a`?** Não.

**6. Compatibilidade.** Sem `--compact`, a saída continua o JSON indentado de hoje.

**7. Interação com as regras.** Nenhuma mudança: é só formatação.

**8. Critério de aceite.** Para um envelope com campos vazios, nenhum nome de campo vazio aparece; o `body` sai inteiro, multilinha; sem a flag, a saída é byte a byte a atual; a mensagem fica marcada como lida nos dois modos.

**9. Instrução para os agentes.** Já incluída no texto do item 1.

---

## 3. `wait` sem reler o bus à toa

**1. Objetivo.** O `cmd_wait` chama `all_messages()` (lê e parseia todo o `bus/`) a cada `--interval` (2 s), mesmo quando nada chegou. Com o `bus/` grande, cada volta do laço custa CPU e disco à toa.

**2. Interface exata.** Sem flag nova. `a2a wait --agent X [--timeout S] [--interval I]` igual.

**3. Saída exata.** Idêntica à atual (o envelope JSON da primeira mensagem nova, ou `(timeout)`).

Implementação: guardar a assinatura do diretório (`os.stat(BUS).st_mtime_ns` + `len(os.listdir(BUS))`) e só chamar `all_messages()` quando ela mudar ou a cada 30 s (rede de segurança para sistemas de arquivos com mtime grosseiro). Opcional: ler só os arquivos novos desde a última volta (o nome `YYYYMMDDTHHMMSSZ-<id>.json` é ordenável).

**4. Efeitos colaterais.** Os mesmos de hoje (marca como lida a mensagem entregue; heartbeat no início).

**5. Muda envelope ou `~/.a2a`?** Não.

**6. Compatibilidade.** Mesmo comportamento observável; `--until` não muda.

**7. Interação com as regras.** Nenhuma.

**8. Critério de aceite.** Um teste que conta chamadas de `all_messages` (monkeypatch) durante um `wait --timeout 3 --interval 0.2` sem mensagens novas: no máximo 2 releituras completas, contra cerca de 15 hoje. Uma mensagem gravada durante a espera é entregue em até um `--interval`.

**9. Instrução para os agentes.** Nenhuma mudança.

---

## 4. Arquivos por referência — **precisa de aval do Luiz antes de implementar**

**1. Objetivo.** Evitar que agentes colem conteúdo de arquivo no `body` (caro e desatualiza). A mensagem cita o caminho, o hash e o intervalo de linhas; quem recebe lê o arquivo só se precisar.

**2. Interface exata.** `a2a send ... --file caminho[:L12-16] [--file ...]` (repetível).

**3. Saída exata.** O `send` continua imprimindo `enviado <id> (de -> para)`. Na leitura:
- `brief`: `N ... "resumo" +2arq`
- `read --compact`: uma linha por arquivo, `file: src/payments/webhook.py@9be1c0 L12-16`.

**4. Efeitos colaterais.** O `send` calcula o sha1 dos bytes do arquivo (guarda os 6 primeiros caracteres hex) relativo ao diretório atual; erro se o arquivo não existir. Nenhum arquivo novo em `~/.a2a`.

**5. Muda envelope ou `~/.a2a`? Sim (envelope).**
- Campo novo **opcional** `files`: `[{"path": "src/x.py", "sha": "9be1c0", "lines": "12-16"}]`, gravado só quando há `--file` (mensagens sem arquivo continuam com os mesmos 14 campos).
- Compatibilidade: leitores antigos ignoram a chave; o `/api/state` passa a carregar `files` dentro das mensagens que o tiverem, sem mudar as chaves atuais; o `ui/` não precisa mudar.
- Migração: nenhuma. Desfazer: basta parar de gravar o campo; mensagens antigas continuam válidas.

**6. Compatibilidade.** `send` sem `--file` produz exatamente o envelope de hoje.

**7. Interação com as regras.** O caminho é só texto; o Dove não lê nem envia o conteúdo do arquivo para ninguém. Recusar caminhos absolutos fora do projeto e `..` evita vazar caminhos da máquina.

**8. Critério de aceite.** `--file a.py:3-5` grava `files` com path, sha e lines corretos; arquivo inexistente gera erro e nenhuma mensagem é gravada; mensagem sem `--file` não tem a chave `files`; `read` (JSON) mostra `files`; `brief` mostra `+Narq`.

**9. Instrução para os agentes.** "Ao citar código, use `--file caminho:Lini-fim` em vez de colar o conteúdo no corpo."

---

## 5. Índice materializado — **precisa de aval do Luiz antes de implementar**

**1. Objetivo.** `summary`, `brief`, `open_tasks` e `/api/state` (a cada 3 s, pelo painel) releem o `bus/` inteiro. Um índice com o que está vivo elimina essa releitura.

**2. Interface exata.** Interno. Mais `a2a index rebuild` (reconstrói a partir do `bus/`) e `a2a index check` (compara o índice com uma reconstrução e diz se divergem).

**3. Saída exata.** `index rebuild` → `indice reconstruido: 412 mensagens, 7 tarefas abertas, 2 missoes`; `index check` → `ok` ou `divergente: <o que difere>` com código de saída 1.

**4. Efeitos colaterais.** `post_message` atualiza `~/.a2a/index.json` sob `FileLock`, após gravar a mensagem.

**5. Muda envelope ou `~/.a2a`? Sim (`~/.a2a`).**
- Arquivo novo `~/.a2a/index.json`: `{"v": 1, "built": "...", "last": "<nome do último arquivo do bus>", "open_tasks": [...], "unread": {"<agente>": [...]}}`.
- O `bus/` continua sendo a fonte da verdade; o índice é cache. Se faltar, estiver corrompido ou `last` não bater com o último arquivo do `bus/`, é reconstruído automaticamente.
- Migração: nenhuma (é gerado no primeiro uso). Desfazer: apagar `index.json`.

**6. Compatibilidade.** Todas as saídas idênticas; o `/api/state` mantém as mesmas chaves.

**7. Interação com as regras.** Anti-loop e missões continuam calculados pelas mesmas funções; o índice só evita releitura. Mensagens gravadas por versões antigas do `a2a` (sem atualizar o índice) são detectadas pelo `last` e forçam a reconstrução.

**8. Critério de aceite.** Para um `bus/` gerado com 2.000 mensagens, `summary` e `brief` dão a mesma saída com e sem índice; `index check` dá `ok` depois de qualquer sequência de `send`/`ack`/`mission`; apagar ou corromper o índice não muda nenhuma saída; uma mensagem escrita direto no `bus/` (simulando a2a antigo) é refletida na chamada seguinte.

**9. Instrução para os agentes.** Nenhuma.

---

## 6. Arquivar mensagens encerradas — **precisa de aval do Luiz antes de implementar**

**1. Objetivo.** O `bus/` só cresce, e todo comando fica mais lento com o tempo. Mover fios encerrados e antigos para fora do `bus/` mantém o custo estável.

**2. Interface exata.** `a2a archive [--older-than-days 14] [--dry-run]` (manual; nunca automático).

**3. Saída exata.** `arquivadas 318 mensagens (52 fios) em archive/2026-10/` ou, com `--dry-run`, `arquivaria 318 mensagens (52 fios)`.

**4. Efeitos colaterais.** Move (não apaga) mensagens de `bus/` para `archive/AAAA-MM/`. Um fio só é arquivado inteiro: a task com todas as respostas, quando ela está encerrada (`CONCLUIDO`/`CANCELADO`) há mais de N dias, mais os acks e reports ligados a ele. Missões não concluídas pelo humano nunca são arquivadas.

**5. Muda envelope ou `~/.a2a`? Sim (`~/.a2a`).**
- Pasta nova `~/.a2a/archive/AAAA-MM/`, com os mesmos arquivos JSON, intocados.
- Compatibilidade: `log --all` e `read <id>` passam a procurar também em `archive/`; o resto lê só o `bus/`.
- Desfazer: `a2a archive --restore [AAAA-MM]` move de volta. Como nada é apagado, desfazer é sempre possível.

**6. Compatibilidade.** `inbox`, `brief`, `summary` e `/api/state` deixam de ver fios arquivados, que por definição estão encerrados e antigos. `read <id>` de uma mensagem arquivada continua funcionando.

**7. Interação com as regras.** Nada é apagado; operação manual, feita pelo humano. Mensagens não lidas por algum destinatário não são arquivadas.

**8. Critério de aceite.** `--dry-run` não move nada; um fio aberto nunca é arquivado; `read` de mensagem arquivada funciona; `--restore` devolve o `bus/` ao estado anterior, e `summary` dá a mesma saída de antes de arquivar.

**9. Instrução para os agentes.** Nenhuma. Agentes não arquivam; isso é do humano.

---

## Medição (reprodutível, só stdlib)

**Unidade.** Para cada comando, medir o stdout: `chars = len(texto)`, `bytes = len(texto.encode("utf-8"))` e `tokens_est = ceil(chars / 4)`.

**Script.** `tests/bench_brief.py`: cria um `A2A_HOME` temporário, popula o cenário via `post_message`/`mission_new` (sem rede, sem bibliotecas externas), roda os comandos com `subprocess` e imprime uma tabela antes/depois. Corpos das mensagens com 120 a 300 caracteres, textos fixos no script para o resultado se repetir.

**Cenário.**
- 3 agentes (`claude`, `codex`, `hermes`) e o humano `luiz`; medição do ponto de vista de `codex`.
- 40 mensagens no bus; 14 visíveis para `codex`: 9 já lidas e 5 não lidas (1 delas é ack).
- 1 tarefa aberta já lida para `codex`.
- 3 missões: 1 esperando o aval de `codex`, 1 com o aval dele já dado e 1 de que ele não participa.

**Antes:** `inbox --agent codex` + `read <id> --agent codex` para cada uma das 5 não lidas + `mission list`.
**Depois:** um único `brief --agent codex --mark-read`. Reportar também a variante "depois + 1 `read --compact`", que é o caso realista em que o agente abre uma mensagem.

**Resultado esperado.** Meta mínima: **redução de 70%** em `tokens_est`. Acima de 80% é bom. Também reportar o número de processos chamados (antes 7, depois 1). Os números finais vêm da execução do script, não de estimativa.
