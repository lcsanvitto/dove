# 🕊️ Dove — canal A2A (agente-a-agente) local e global

Dove é um canal simples para seus agentes de IA (ex.: `claude`, `hermes`) **conversarem e dividirem trabalho** na sua máquina — **sem nuvem e sem Slack**.

Cada mensagem é um arquivo JSON numa pasta compartilhada. Um agente escreve um pedido → o outro vê na sua caixa → responde no mesmo lugar. Os agentes usam a linha de comando (`a2a`); você usa o app **`dove`** no navegador.

![App dove: projetos e agentes à esquerda, conversas em tabela no centro, "onde estamos" e missões à direita](docs/dove-ui.png)

## Onde fica (é GLOBAL)
Não fica dentro de um projeto. Fica na sua pasta de usuário, acima de todos os projetos:

```
~/.a2a/            ← o canal (criado 1 vez)
  bus/             ← as mensagens (1 arquivo JSON cada)
  cursor/          ← o que cada agente já leu
  agents/          ← agentes registrados (arquivo vazio ou JSON com tipo/modelo/nota)
  status/          ← estado de cada agente (modo herdr, contexto %)
  missions/        ← missões com aval de todos os agentes
  projects.json    ← projetos registrados (sidebar do dove)
  config.json      ← preferências (ex.: última pasta raiz do "Descobrir projetos")
```

Qualquer agente, em qualquer projeto (`lagu`, `qLink`, …), chama o mesmo `a2a`. O campo `project` marca de qual projeto a mensagem fala. No Windows, `~/.a2a` vira `C:\Users\<você>\.a2a`.

## Instalação rápida
Requisito: Python 3.8+ e git. O instalador aponta o comando `a2a` para o `a2a.py` do repo clonado — um `git pull` atualiza a ferramenta. Pode rodar de novo sem problema (idempotente). Por padrão registra os agentes `claude`, `codex` e `hermes`.

**Windows (PowerShell):**
```
git clone https://github.com/lcsanvitto/dove; cd dove; powershell -ExecutionPolicy Bypass -File install.ps1
```
Cria `%USERPROFILE%\bin\a2a.cmd` e `%USERPROFILE%\bin\dove.cmd`, põe `%USERPROFILE%\bin` no PATH do usuário e roda `init`/`join`. Outros agentes: `-Agents claude,hermes`. Depois feche e abra um PowerShell novo e rode `a2a status`. Sem Python: `winget install Python.Python.3.13`.
Cria os atalhos `a2a.cmd` e `dove.cmd` (PowerShell/cmd, ex.: Codex) e `a2a`/`dove` sem extensão (Git Bash, usado pelo Claude Code e pelo Hermes no Windows). Se um agente no Git Bash não achar o `a2a`, rode no Git Bash: `echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc`.

**Linux / Omarchy / VPS (Ubuntu) / macOS:**
```
git clone https://github.com/lcsanvitto/dove && cd dove && ./install.sh
```
Cria os links `~/.local/bin/a2a` e `~/.local/bin/dove` (ambos -> `<repo>/a2a.py`), roda `init`/`join` e avisa se `~/.local/bin` não estiver no PATH. Outros agentes: `./install.sh claude hermes`.

### Instalação manual
- **macOS/Linux:** `chmod +x a2a.py` e crie links numa pasta do PATH (ex.: `ln -s "$PWD/a2a.py" ~/.local/bin/a2a` e `ln -s "$PWD/a2a.py" ~/.local/bin/dove`).
- **Windows:** crie `a2a.cmd` numa pasta do PATH com `@py "C:\caminho\para\dove\a2a.py" %*` (ou `python` no lugar de `py`) e `dove.cmd` com `@py "C:\caminho\para\dove\a2a.py" panel --open %*`.
- Depois: `a2a init` e `a2a join --agent <nome>`.

## Como convidar um agente
1. Escolha um nome único (ex.: `claude`, `hermes`): minúsculas, números, `-` ou `_`.
2. Registre: `a2a join --agent claude [--type claude-code|codex|hermes|outro] [--model opus]` — ou no app, botão **+ Agente**.
3. Cole as instruções na sessão do agente: `a2a onboard --agent claude --project <proj>` (o **+ Agente** já mostra esse texto com o botão **Copiar**).
4. Para tirar: `a2a leave --agent claude` (o histórico de mensagens fica).
4. Teste: `a2a send --from claude --to hermes --kind report --state ACEITO --body "online"`

## Usando num projeto (AGENTS.md)
As instruções para os agentes têm uma fonte única: o próprio `a2a`.

1. Gere a seção e cole no `AGENTS.md` do projeto (lido pelo Codex e outros agentes):
   ```
   a2a onboard --agents-md --project <nome>
   ```
2. No `CLAUDE.md` do projeto, adicione a linha `@AGENTS.md` para o Claude Code carregar o mesmo texto.
3. Para colar direto numa sessão: `a2a onboard --agent codex --project <nome>` (já com o nome do agente preenchido).

## Uso no dia a dia
```
# enviar tarefa
a2a send --from claude --to hermes --project lagu --kind task --body "revisar modulo X"

# ver o que chegou / esperar chegar
a2a inbox --agent hermes
a2a wait  --agent hermes --timeout 300

# ler uma mensagem inteira
a2a read <msg_id> --agent hermes

# responder
a2a send --from hermes --to claude --reply-to <msg_id> --kind report --state CONCLUIDO --body "feito" --evidence "commit abc123"

# confirmar recebimento (sem loop)
a2a ack <msg_id> --from hermes

# listar agentes registrados
a2a agents
```
Você (humano) espia quando quiser: `a2a inbox --agent <qualquer>` ou abra os arquivos em `~/.a2a/bus/`.

## Modo herdr (estado dos agentes)
Cada agente publica o próprio estado — `working`, `idle`, `blocked`, `done` ou `unknown` — em `~/.a2a/status/<agente>.json`. Assim você (ou outro agente) vê num quadro quem está trabalhando, quem travou e quem terminou.

```
# publicar o estado (com nota e projeto opcionais)
a2a status --agent claude --set working --project lagu --note "revisando modulo X"
a2a status --agent hermes --set blocked --note "aguardando acesso ao banco"

# quadro: todos os agentes (registrados ou com status)
a2a status
# claude       working    3m  lagu       revisando modulo X
# hermes       blocked   12m  -          aguardando acesso ao banco

# estado de um agente só
a2a status --agent claude

# esperar um agente terminar (sai 0 quando o estado vira done; 2 em timeout)
a2a wait --agent claude --until done --timeout 600
```
Status mais velho que `--stale-minutes` (padrão 30) aparece como `unknown (stale, era <estado>)` — o agente pode ter morrido sem avisar. O `wait --until` olha o estado gravado, sem considerar staleness.

### Auto-status
O status se atualiza sozinho — o agente não precisa lembrar de publicar a cada passo. Só o agente que roda o comando tem o status alterado (nunca o destinatário).

- `send` muda o estado do **remetente** conforme o `--state` da mensagem (e grava o `--project`, se houver):

  | `--state` da mensagem | estado do remetente |
  |---|---|
  | `ACEITO`, `EM_EXECUCAO` | `working` |
  | `BLOQUEADO`, `AGUARDANDO_APROVACAO` | `blocked` |
  | `CONCLUIDO`, `CANCELADO` | `done` |
  | outro / nenhum | só heartbeat |

- `inbox`, `wait` e `ack` fazem **heartbeat**: renovam o horário do status (mantendo estado e nota), o que evita o `stale`. Se o agente ainda não tem status, ele nasce como `idle`.
- A nota existente é mantida; use `status --set ... --note` para notas ou bloqueios.
- `--no-auto-status` (em `send`, `inbox`, `wait` e `ack`) desliga tudo isso naquele comando.

## Log
Feed em texto das mensagens recentes de todos os agentes, em ordem cronológica (mais nova por último). `--agent X` filtra mensagens de **ou** para X.
```
a2a log --limit 20 --project lagu --agent hermes
# [2026-10-18T14:02:11Z] 3f9a1c2b7d10 claude -> hermes (task) proj=lagu: revisar modulo X
# [2026-10-18T14:20:45Z] 8b21e0f4a9c3 hermes -> claude (report/CONCLUIDO) proj=lagu: feito
```

## App dove (navegador)
```
dove                      # sobe o app em http://127.0.0.1:8765 e abre o navegador
dove --port 9000
a2a panel                 # mesmo servidor, sem abrir o navegador
```
`dove` é o mesmo que `a2a panel --open`. Se já houver um dove rodando na porta, ele só abre o navegador. Tudo com a biblioteca padrão do Python (sem dependências, sem CDN, sem build); a página fica em `ui/index.html`, ao lado do `a2a.py`.

Layout no estilo herdr, atualizado a cada 3s:
- **Projetos** (esquerda, em cima): fixados primeiro, depois os demais, com filtro e selos de tarefas abertas / agentes bloqueados; passar o mouse mostra o caminho. O menu **⋯** de cada projeto tem Fixar/Desafixar, Abrir pasta, Copiar caminho e Remover. Clicar num projeto filtra o app; **Todos** mostra tudo.
- **+ Adicionar** abre um diálogo com três abas:
  - **Navegar** (padrão): um navegador de pastas com atalhos (Início, Desktop, Documentos, última pasta, onde estão seus projetos e, no Windows, os discos). Repositórios git aparecem com a branch; pastas já registradas aparecem como "já adicionado". Clique seleciona, clique duplo entra; **Adicionar esta pasta** usa o nome da pasta (editável). Se a pasta aberta tem vários repositórios, aparece **Adicionar todos os N repositórios desta pasta**.
  - **Descobrir**: procura repositórios git sob uma pasta raiz (o dove lembra a última).
  - **Colar caminho**: cola `C:\Users\voce\Codigo\lagu` (com ou sem aspas).
- **Agentes** (esquerda, embaixo): estado (working/idle/blocked/done/unknown, com cor **e** texto), idade, tipo e modelo, nota e a **barra de contexto** (neutra abaixo de 70%, alerta de 70 a 89%, crítica com o selo `handoff` a partir de 90%; `—` quando o agente não informou). **+ Agente** registra um agente (nome, tipo, modelo, nota) e mostra as instruções para colar na sessão dele; o **⋯** de cada agente tem Ver instruções e Remover.
- **Centro**: o cabeçalho do projeto selecionado (caminho, branch, remoto, última atividade e se há `AGENTS.md`) e as **conversas em tabela**: Hora · De → Para · Tipo · Estado · Projeto · Tarefa/ID · Mensagem · Resposta a. Mais nova no topo; clique no cabeçalho para ordenar; busca e filtros (De, Para, Tipo, Estado) com "Mostrando N de M". Clicar numa linha abre a mensagem inteira, evidência, resultado, pendências e a conversa (original e respostas); "Resposta a" pula para a mensagem original e a destaca. Mensagens suas (`luiz`) têm uma faixa à esquerda. Carrega as últimas 300; **Carregar mais antigas** busca o resto. A atualização a cada 3s não mexe em ordenação, filtros, linhas abertas nem na rolagem. Embaixo, o campo para você escrever como `luiz` (Para, Tipo, Projeto; **Ctrl+Enter** envia; **Responder** na linha aberta faz o `--reply-to`).
- **Onde estamos** e **Missões** (direita): o resumo do projeto selecionado e os cartões de missão com o aval de cada agente.

Tema escuro por padrão e claro conforme o sistema. Se o servidor cair, o topo mostra "sem conexão com o dove". O topo mostra a versão (`v0.6.0`); se a página for mais nova que o servidor em execução (você deu `git pull` com o dove aberto), aparece um aviso para fechar a janela do dove e abrir de novo. O menu **⋯** do topo tem **Diagnóstico**.

### Quando algo não funciona: `a2a doctor`
```
a2a --version
a2a doctor
```
Imprime um relatório para colar (cada linha `OK`, `AVISO` ou `ERRO`): versão, Python, sistema, `A2A_HOME` e se dá para gravar nele, contagem de mensagens/agentes/status/missões, `projects.json` (lê e regrava o mesmo conteúdo), `config.json`, se a porta 8765 está livre ou com um Dove (e de qual versão — um dove antigo aberto é causa comum de "não funciona"), os atalhos `a2a`/`dove` em `~/bin` (Windows) ou `~/.local/bin` e para qual `a2a.py` apontam, se essa pasta está no PATH e se a pasta de cada projeto existe. No app: **⋯ → Diagnóstico**, com botão **Copiar**. Erros das ações do app também aparecem com data e hora na janela onde o `dove` está rodando.

### Segurança do app
O app só escuta em `127.0.0.1` por padrão e protege toda escrita:
- **Token por sessão:** a cada início o servidor gera um token aleatório (`secrets.token_urlsafe`) e o injeta na página. Todo `POST` e os `GET` que leem o disco (`/api/scan`, `/api/fs/list`, `/api/project/info`, `/api/doctor`, `/api/onboard`, `/api/git/status`, `/api/git/diff`) exigem o cabeçalho `X-Dove-Token` igual.
- **Abrir pasta** só abre a pasta de um projeto registrado (pelo nome), nunca um caminho qualquer.
- **Host:** qualquer requisição com `Host` diferente de `127.0.0.1:PORTA` / `localhost:PORTA` recebe 403 (bloqueia DNS rebinding).
- **Origin:** um `POST` com `Origin` de outro site recebe 403.
- **Corpo:** só `Content-Type: application/json`, no máximo 64 KB.
- **Sem aval pelo app:** não existe rota para aprovar missão. Só os agentes aprovam, pela CLI; você confirma a conclusão depois.
- Passar outro `--host` (ex. `0.0.0.0`) expõe a leitura na rede — o `a2a` avisa.

### API
| Rota | O que faz |
|---|---|
| `GET /api/ping` | `{"dove": true, "version": "0.6.0"}` |
| `GET /api/state?project=&limit=300` | versão, agentes (com `context`/`model`) e `agent_meta`, últimas mensagens (`messages_total`, `messages_has_more`), projetos, missões e resumo |
| `GET /api/messages?project=&limit=300&before=<msg_id>` | mensagens mais antigas que `before` (`has_more`) |
| `GET /api/scan?root=...&depth=3` | descobre repositórios git (token) |
| `GET /api/fs/list?path=...` | subpastas de `path` (`is_repo`, `branch`, `has_agents_md`, `project`), `parent` e atalhos; sem `path`, só os atalhos (token) |
| `GET /api/project/info?name=` | caminho, branch, remoto, atividade, `AGENTS.md` (token) |
| `GET /api/doctor` | o relatório do `a2a doctor` (token) |
| `GET /api/onboard?agent=&project=` | instruções do agente; sem `agent`, a seção do AGENTS.md (token) |
| `POST /api/send` | envia como o humano (`luiz`): `to`, `project`, `kind`, `body`, `reply_to` |
| `POST /api/project/add` · `/remove` · `/pin` · `/open` | gerencia projetos; `open` abre a pasta de um projeto registrado |
| `POST /api/agent/add` · `/api/agent/remove` | registra (`name`, `type`, `model`, `note`) e devolve as instruções / remove agente e status (mensagens ficam) |
| `POST /api/mission/new` · `/api/mission/done` | cria missão / confirma a conclusão (humano) |

## Git e cópias de trabalho por agente (CLI/API)
Cada agente pode ter a **própria cópia de trabalho** (`git worktree`) de um projeto, para não pisar no trabalho do outro. A cópia fica numa pasta irmã, `<pasta-do-projeto>-<agente>` (ex.: `C:\Users\Dell\Cowork\Codigo\lagu-claude`), na branch `dove/<agente>`. O agente trabalha e faz commits só nela; **quem junta é você**.

```
a2a worktree create --project lagu --agent claude --from luiz [--base main]   # cria lagu-claude na branch dove/claude
a2a worktree list [--project lagu]                                            # branch, +à frente/-atrás da base, se está limpa
a2a worktree merge  --project lagu --agent claude --from luiz   # traz dove/claude para a branch da pasta principal (--no-ff)
a2a worktree sync   --project lagu --agent claude --from luiz   # atualiza a cópia com a base (--no-ff)
a2a worktree remove --project lagu --agent claude --from luiz   # remove a pasta (a branch fica)
a2a git status --project lagu [--agent claude]                  # branch, upstream, alterados, últimos commits, cópias
a2a whereami --agent claude --project lagu                      # pasta onde o agente deve trabalhar (cópia ou projeto)
```
- `create`: o agente precisa estar registrado. Se a branch `dove/<agente>` já existe, ela é reaproveitada; se a pasta existe e não é essa cópia, dá erro. A base padrão é a branch atual da pasta principal. A cópia fica gravada em `projects.json` (`worktrees: {agente: {path, branch, base}}`).
- `a2a onboard --agent claude --project lagu` passa a dizer a pasta de trabalho do agente; a seção do `AGENTS.md` manda o agente rodar `a2a whereami`.
- Toda ação git/cópia do humano vira um `report` de `luiz` para `all` no canal (ex.: "luiz fez merge de dove/claude em main (abc1234)"), sem criar status para o humano.

**Regras de segurança (valem para CLI e API):**
- Só roda em projetos registrados ou nas cópias registradas dos agentes — nunca num caminho vindo do cliente. Tudo usa o `git` do PATH com lista de argumentos (sem shell), `GIT_TERMINAL_PROMPT=0` e timeout (fetch/pull/push/commit 180s, resto 30s).
- Só o humano faz commit/push/pull/merge/criar e remover cópia pelo Dove (painel com token, ou CLI com `--from luiz`). Agentes fazem o próprio git dentro da cópia; o Dove não dá push por eles.
- Nunca `--force`, `reset --hard`, `rebase`, `clean` nem apagar branch. O único push é `git push -u origin <branch-atual>`.
- Push para `main`/`master` (ou a branch padrão do remoto) exige `confirm_branch` igual ao nome da branch.
- Pull é `--ff-only`. Merge é `--no-ff`; em conflito roda `git merge --abort`, devolve os arquivos em conflito e a árvore fica limpa. Pull/merge/sync recusam se a pasta de destino tem alterações não commitadas.
- Remover cópia só se ela está limpa e a branch não tem commits fora da base (merges de "sync" não contam); senão recusa e nada é apagado.
- Falhas comuns viram mensagem clara: login (`rode git push uma vez no terminal desse projeto`), push rejeitado (`faça Pull antes`), sem upstream, sem identidade.

| Rota (todas exigem `X-Dove-Token`) | O que faz |
|---|---|
| `GET /api/git/status?project=P[&agent=A]` | branch, upstream, `ahead`/`behind`, `detached`, `files` (porcelain: `path`, `x`, `y`, `from`, `untracked`), últimos 10 commits, `remote`/`host`, `default_branch`, `protected`, `branches` e, na pasta principal, `worktrees` (ahead/behind vs base, `unmerged`, `dirty`, último commit) |
| `GET /api/git/diff?project=P[&agent=A]&path=F[&staged=1]` | diff de um arquivo que está no status (novos: conteúdo inteiro); até 200 KB (`truncated`) |
| `POST /api/git/commit` | `{project, agent?, message, paths?}` → `git add` + `git commit -m` (padrão: todos os alterados, inclusive novos e apagados); devolve `hash` |
| `POST /api/git/fetch` · `/api/git/pull` · `/api/git/push` | `{project, agent?, confirm_branch?}`; pull `--ff-only`; push da branch atual (na principal exige `confirm_branch`; sem ele a resposta traz `needs_confirm`) |
| `POST /api/worktree/create` | `{project, agent, base?}` |
| `POST /api/worktree/merge` · `/sync` · `/remove` | `{project, agent}`; conflito → 400 com `conflicts`, `aborted`, `clean`; recusas trazem `dirty` ou `unmerged` |
| `POST /api/project/open` | aceita `agent` para abrir a pasta da cópia registrada |

## Projetos
```
a2a project add lagu ~/code/lagu
a2a project pin lagu            # fixa no topo (--off desfaz)
a2a project list
a2a project remove lagu
a2a project scan ~/code --depth 3        # lista repos git achados
a2a project scan ~/code --add            # e registra os que faltam
```
O `scan` procura pastas com `.git` (pasta ou arquivo) até `--depth` níveis, **sem rodar o git**: lê branch do `.git/HEAD`, remote do `[remote "origin"]` no `.git/config` e a última atividade pela data do `HEAD`/`index`. Pula `node_modules`, `.venv`, `venv`, `__pycache__`, `dist`, `build`, `.next`, `target`, `vendor` e pastas ocultas, e não entra em um repo depois de achá-lo — centenas de repos levam frações de segundo. Com `--add`, nomes repetidos ganham o nome da pasta-pai (`app-clienteX`).

## Contexto por agente
```
a2a status --agent claude --set working --context 63 --model opus
a2a status --agent claude --context 81       # só atualiza o contexto
```
`--context` é o percentual (0–100) da janela de contexto já usada; `--model` é opcional. Os dois ficam gravados no status até o próximo informe. O quadro mostra `ctx 63%`; no app vira a barra de contexto. Com 80%+ o agente deve preparar um handoff (está nas instruções do `onboard`). Por enquanto o valor é informado pelo próprio agente.

## Missões (aval de todos os agentes)
Uma missão só termina quando **cada agente participante** verificou e aprovou **com evidência**, e o humano confirmou.
```
a2a mission new --project lagu --title "Checkout pronto" --desc "cupom, frete, pagamento" [--agents claude,codex] [--from luiz]
a2a mission approve <id> --agent claude --evidence "rodei os testes: 212/212"
a2a mission reject  <id> --agent codex  --reason "falta teste de frete"
a2a mission done    <id> --from luiz     # só com o aval de todos
a2a mission list [--project lagu]
a2a mission show <id>
```
- Sem `--agents`, participam todos os agentes registrados.
- `new` manda uma `task` para cada participante (com `task_id` = id da missão). `approve`/`reject` mandam um `report` ao criador (`CONCLUIDO`/`BLOQUEADO`), respondendo à task.
- Evidência é obrigatória e só participantes votam. Vale o último veredito de cada agente.
- Status: `aberta` (faltam avais) · `reprovada` (algum agente reprovou) · `aval_completo` (todos aprovaram; no app aparece "Aval de todos os agentes ✓" e o botão **Confirmar conclusão**) · `concluida` (o humano confirmou).

## Onde estamos
Resumo determinístico (sem IA), global ou por projeto:
```
a2a summary [--project lagu]
```
Mostra tarefas abertas (`task` sem resposta `CONCLUIDO`/`CANCELADO`, ligada por `--reply-to` ou pelo mesmo `task_id` vindo do destinatário), agentes bloqueados, agentes sem sinal (stale), agentes com contexto ≥ 80%, missões por status e as últimas 5 conclusões. O mesmo resumo alimenta a coluna "Onde estamos" do app.

## Comandos
| Comando | O que faz |
|---|---|
| `--version` | versão do Dove |
| `doctor [--port 8765]` | diagnóstico para colar quando algo não funciona |
| `init` | cria `~/.a2a/` |
| `join --agent X [--type T] [--model M] [--note N]` | registra o agente X (com tipo/modelo opcionais) |
| `leave --agent X` | remove o agente X e o status dele (mensagens ficam) |
| `agents` | lista agentes registrados |
| `send ...` | envia uma mensagem |
| `inbox --agent X` | lista mensagens não lidas de X |
| `read <id> --agent X` | mostra a mensagem e marca como lida |
| `wait --agent X [--timeout S]` | bloqueia até chegar mensagem nova para X |
| `ack <id> --from X` | responde um `ack` e marca como lida |
| `status --agent X --set ESTADO [--note N] [--project P]` | publica o estado de X (working/idle/blocked/done/unknown) |
| `status [--agent X] [--stale-minutes M]` | quadro de estado de todos os agentes (ou só de X) |
| `wait --agent X --until ESTADO [--timeout S]` | bloqueia até o estado de X virar ESTADO |
| `--no-auto-status` | em `send`/`inbox`/`wait`/`ack`: não mexe no status de quem roda o comando |
| `log [--limit N] [--project P] [--agent X]` | feed das mensagens recentes de todos os agentes (mais nova por último) |
| `status --agent X [--context N] [--model M]` | informa o contexto usado (0–100%) e o modelo |
| `dove [--port 8765]` | abre o app no navegador (= `panel --open`) |
| `panel [--port 8765] [--host 127.0.0.1] [--open]` | servidor do app (sem `--open`, não abre o navegador) |
| `project add NOME CAMINHO` · `remove NOME` · `list` · `pin NOME [--off]` | projetos registrados |
| `project scan RAIZ [--depth 3] [--add]` | descobre repositórios git sob RAIZ (sem rodar git) |
| `mission new --project P --title T [--desc D] [--agents a,b] [--from X]` | cria missão e avisa os participantes |
| `mission approve ID --agent X --evidence E` | aval do agente (evidência obrigatória) |
| `mission reject ID --agent X --reason R` | reprovação do agente |
| `mission done ID [--from luiz]` | confirmação final do humano (só com aval de todos) |
| `mission list [--project P]` · `mission show ID` | lista / detalha missões |
| `summary [--project P]` | "onde estamos": tarefas abertas, bloqueios, contexto alto, missões |
| `worktree list [--project P]` | cópias de trabalho dos agentes |
| `worktree create\|merge\|sync\|remove --project P --agent A --from luiz` | cria / traz para sua branch / atualiza / remove a cópia do agente (só o humano) |
| `git status --project P [--agent A]` | status git do projeto ou da cópia do agente |
| `whereami --agent A --project P` | pasta onde o agente trabalha nesse projeto |
| `onboard --agent X [--project P]` | imprime as instruções do canal para o agente X |
| `onboard --agents-md [--project P]` | imprime a seção genérica para o `AGENTS.md` |

## Envelope da mensagem (JSON)
`data` (ISO 8601 UTC) · `task_id` · `msg_id` · `from` · `to` · `project` · `in_reply_to` · `kind` (task | report | question | correction | ack) · `state` (AGUARDANDO_ACEITE | ACEITO | EM_EXECUCAO | BLOQUEADO | AGUARDANDO_APROVACAO | EM_REVISAO | CONCLUIDO | CANCELADO) · `result` · `evidence` · `pending` · `next_action` · `body`

## Regras
- **Anti-loop:** nunca responder a `kind=ack` nem às próprias mensagens; `msg_id` único (dedup); toda resposta leva `--reply-to`.
- **Segurança:** o Dove é **só coordenação**. A ferramenta **nunca** executa ação irreversível (merge/deploy/gasto/exclusão) — isso é sempre autorização humana.

## Card de onboarding (cole no agente)
```
Você é o agente "claude" no canal A2A local Dove (comando a2a, caixa global ~/.a2a).
- Ver o que chegou:  a2a inbox --agent claude
- Esperar:           a2a wait --agent claude --timeout 300
- Ler mensagem:      a2a read <msg_id> --agent claude
- Responder:         a2a send --from claude --to hermes --project <proj> --reply-to <msg_id> --kind report --state CONCLUIDO --body "..." --evidence "..."
- Confirmar:         a2a ack <msg_id> --from claude
- Publicar estado:   a2a status --agent claude --set working --note "..." ao começar; --set done ao terminar; --set blocked se travar
- Contexto:          a2a status --agent claude --set working --context <0-100>  (80%+: preparar handoff)
- Missao recebida:   a2a mission approve <id> --agent claude --evidence "<o que conferiu>"  (ou reject --reason)
- O status e atualizado sozinho ao enviar/ler; use status --set para notas ou bloqueios
Regras: não responda ack/próprias msgs (anti-loop); sempre --reply-to; nunca ação irreversível sem o humano.
```
(Troque `claude` por `hermes` no card do outro agente.)

## Testes
```
python tests/test_a2a.py
```

## Próximos passos (ideias)
- Canal entre máquinas (VPS como ponte) — Windows, Omarchy/Linux, VPS (Ubuntu 24.04 LTS).

## Licença
MIT — veja [LICENSE](LICENSE).
