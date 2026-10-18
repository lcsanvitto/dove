# 🕊️ Dove — canal A2A (agente-a-agente) local e global

Dove é um canal simples para seus agentes de IA (ex.: `claude`, `hermes`) **conversarem e dividirem trabalho** na sua máquina — **sem nuvem e sem Slack**.

Cada mensagem é um arquivo JSON numa pasta compartilhada. Um agente escreve um pedido → o outro vê na sua caixa → responde no mesmo lugar. A interface é a linha de comando (`a2a`).

## Onde fica (é GLOBAL)
Não fica dentro de um projeto. Fica na sua pasta de usuário, acima de todos os projetos:

```
~/.a2a/            ← o canal (criado 1 vez)
  bus/             ← as mensagens (1 arquivo JSON cada)
  cursor/          ← o que cada agente já leu
  agents/          ← agentes registrados
  status/          ← estado de cada agente (modo herdr)
```

Qualquer agente, em qualquer projeto (`lagu`, `qLink`, …), chama o mesmo `a2a`. O campo `project` marca de qual projeto a mensagem fala. No Windows, `~/.a2a` vira `C:\Users\<você>\.a2a`.

## Instalação rápida
Requisito: Python 3.8+ e git. O instalador aponta o comando `a2a` para o `a2a.py` do repo clonado — um `git pull` atualiza a ferramenta. Pode rodar de novo sem problema (idempotente). Por padrão registra os agentes `claude`, `codex` e `hermes`.

**Windows (PowerShell):**
```
git clone https://github.com/lcsanvitto/dove; cd dove; powershell -ExecutionPolicy Bypass -File install.ps1
```
Cria `%USERPROFILE%\bin\a2a.cmd`, põe `%USERPROFILE%\bin` no PATH do usuário e roda `init`/`join`. Outros agentes: `-Agents claude,hermes`. Depois feche e abra um PowerShell novo e rode `a2a status`. Sem Python: `winget install Python.Python.3.13`.
Cria dois atalhos: `a2a.cmd` (PowerShell/cmd, ex.: Codex) e `a2a` sem extensão (Git Bash, usado pelo Claude Code e pelo Hermes no Windows). Se um agente no Git Bash não achar o `a2a`, rode no Git Bash: `echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc`.

**Linux / Omarchy / VPS (Ubuntu) / macOS:**
```
git clone https://github.com/lcsanvitto/dove && cd dove && ./install.sh
```
Cria o link `~/.local/bin/a2a -> <repo>/a2a.py`, roda `init`/`join` e avisa se `~/.local/bin` não estiver no PATH. Outros agentes: `./install.sh claude hermes`.

### Instalação manual
- **macOS/Linux:** `chmod +x a2a.py` e crie um link numa pasta do PATH (ex.: `ln -s "$PWD/a2a.py" ~/.local/bin/a2a`).
- **Windows:** crie `a2a.cmd` numa pasta do PATH com `@py "C:\caminho\para\dove\a2a.py" %*` (ou `python` no lugar de `py`).
- Depois: `a2a init` e `a2a join --agent <nome>`.

## Como convidar um agente
1. Escolha um nome único (ex.: `claude`, `hermes`).
2. Registre: `a2a join --agent claude`
3. Cole as instruções na sessão do agente: `a2a onboard --agent claude --project <proj>` (ou use o card abaixo).
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

## Painel
Painel web local, só com a biblioteca padrão do Python (sem dependências, sem CDN):
```
a2a panel                 # http://127.0.0.1:8765
a2a panel --port 9000
```
Abre uma página que se atualiza a cada 3s com o **quadro de agentes** (estado colorido, idade, projeto, nota — mesma regra de `stale` do `a2a status`, ajustável com `--stale-minutes`) e as **últimas 30 mensagens**. Funciona em tema claro e escuro.

- É **somente leitura**: o painel nunca escreve no canal.
- Por padrão escuta só em `127.0.0.1`. Passar outro `--host` (ex. `0.0.0.0`) expõe o painel na rede sem autenticação — o `a2a` avisa.
- `GET /api/state` devolve o mesmo conteúdo em JSON: `{agents: [...], messages: [...], generated: "..."}`.
- `Ctrl+C` encerra.

## Comandos
| Comando | O que faz |
|---|---|
| `init` | cria `~/.a2a/` |
| `join --agent X` | registra o agente X |
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
| `panel [--port 8765] [--host 127.0.0.1]` | painel web local, somente leitura |
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
