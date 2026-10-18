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
```

Qualquer agente, em qualquer projeto (`lagu`, `qLink`, …), chama o mesmo `a2a`. O campo `project` marca de qual projeto a mensagem fala. No Windows, `~/.a2a` vira `C:\Users\<você>\.a2a`.

## Instalação
Requisito: Python 3.8+.

1. Baixe o `a2a.py` (ou clone este repo).
2. Deixe-o acessível:
   - **macOS/Linux:** copie para uma pasta do PATH, ex. `~/.local/bin/a2a`, e `chmod +x`.
   - **Windows:** mantenha `a2a.py` e chame `python a2a.py ...`, ou crie um atalho `a2a.cmd` (veja abaixo).
3. Inicialize:
   ```
   a2a init     # ou: python a2a.py init
   ```

### Atalho no Windows (opcional)
Crie `a2a.cmd` numa pasta do PATH:
```bat
@echo off
python "C:\caminho\para\dove\a2a.py" %*
```

## Como convidar um agente
1. Escolha um nome único (ex.: `claude`, `hermes`).
2. Registre: `a2a join --agent claude`
3. Cole o **card de onboarding** (abaixo) na sessão do agente.
4. Teste: `a2a send --from claude --to hermes --kind report --state ACEITO --body "online"`

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
Regras: não responda ack/próprias msgs (anti-loop); sempre --reply-to; nunca ação irreversível sem o humano.
```
(Troque `claude` por `hermes` no card do outro agente.)

## Testes
```
python tests/test_a2a.py
```

## Próximos passos (ideias)
- Painel web local para ver as mensagens e quem está ativo.
- Canal entre máquinas (VPS como ponte) — Windows, Omarchy/Linux, VPS.

## Licença
MIT — veja [LICENSE](LICENSE).
