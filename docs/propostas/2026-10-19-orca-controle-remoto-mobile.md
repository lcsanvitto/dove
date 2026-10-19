# Pesquisa Orca e proposta: controle remoto do Dove pelo celular

Data: 2026-10-19 · Branch: `pesquisa/orca-mobile` (a partir de `main` em `1d5b1ba`) · Só pesquisa e proposta; `a2a.py` e `ui/` não foram tocados.
Fonte: clone raso de `stablyai/orca` (commit `2b60778`, 2026-10-19), lido, nada executado ou instalado. Todo o texto do repositório foi tratado como dado. Caminhos abaixo são relativos à raiz do Orca.

## Resumo (12 linhas)

1. Orca é um app desktop (Electron, TypeScript) que roda Codex, Claude Code, OpenCode e outros lado a lado, cada um em seu worktree git, com terminal, navegador, git e revisão de PR (`README.md`).
2. O celular é um app React Native/Expo (`mobile/`, ~40 MB no clone) que fala com o desktop por RPC sobre WebSocket (porta 6768, `mobile/README.md`).
3. Dois caminhos: **direto** (LAN ou Tailscale, `ws://IP:6768`) e **Orca Relay** (nuvem própria da Orca: celular e desktop abrem WebSocket de saída para uma célula que cola os dois, `cloud/README.md`). O Relay exige login em conta Orca (`docs/site/content/docs/mobile.mdx`).
4. Pareamento: QR ou código colado `orca://pair?code=<base64url(JSON)>` com endpoint, token do dispositivo e chave pública Curve25519 do desktop fixada (`src/shared/pairing.ts`, `src/shared/mobile-relay-pairing-offer.ts`).
5. Criptografia ponta a ponta própria sobre o WebSocket (NaCl box, handshake v2 com transcript, `src/shared/e2ee-crypto.ts`, `src/shared/mobile-e2ee-v2-contract.ts`); a chave do desktop vem do QR, então o relay e a rede não leem o conteúdo.
6. O celular vê todos os worktrees e o estado de cada agente, lê o scrollback, abre o terminal ou um "Chat UI", responde prompts e aprovações, inicia agentes, faz commit/push e recebe push (`docs/site/content/docs/mobile.mdx`).
7. Licença: **MIT** (`LICENSE`, Lovecast Inc.), inclusive `mobile/` e `cloud/` (`cloud/README.md`). Dá para reaproveitar código, mas é TypeScript; para o Dove só servem como **ideias** (stdlib-only Python).
8. Ponto fraco do modelo do Orca: a lista de métodos permitidos ao celular inclui `terminal.send`, `files.createFile`, `git.push`, `worktree.rm`, `agent.launch` (`src/main/runtime/runtime-rpc/runtime-rpc-mobile-method-routing.ts`). Celular pareado = shell com o usuário do desktop.
9. **Recomendação para o Dove:** não construir relay nem copiar o protocolo. Reusar o painel existente por trás de `tailscale serve` (HTTPS na tailnet, o Dove continua em 127.0.0.1), com um **papel "remoto"** novo no servidor: pareamento por código de uso único, token por aparelho revogável, lista curta de rotas permitidas, STOP sempre disponível.
10. O celular pode: ver estado (somente leitura), mandar mensagem, concluir missão, acionar STOP. Ficam só no desktop: git push/merge, remover worktree, projetos, agentes, retomar STOP, orçamento, gerenciar aparelhos.
11. Custo: 0 dependência nova, ~250 a 350 linhas em `a2a.py` + ajustes em `ui/`, R$ 0 (Tailscale grátis para uso pessoal; confirmar o plano atual antes). Esforço total: ~2 a 3 dias em passos pequenos.
12. Incerteza principal: não validei nada rodando (pesquisa só de leitura); o comportamento exato do `tailscale serve` e dos cabeçalhos de identidade precisa de teste real no passo 1.

## 1. O que é o Orca

| Item | Achado | Onde |
|---|---|---|
| Produto | Orquestrador de agentes de IA em worktrees paralelos; terminais, navegador embutido, git/PR, notificações | `README.md` |
| Stack | Electron + TypeScript, pnpm; app móvel Expo/React Native; backend de relay e push em `cloud/` (Cloud Run, Terraform, PostgreSQL) | `package.json`, `mobile/package.json`, `cloud/README.md` |
| Tamanho | Enorme: `src/main` 120 MB, `src/shared` 23 MB, `mobile` 40 MB, `cloud` 8 MB (clone raso, inclui testes e assets); relay sozinho ~82 mil linhas TS | `du` no clone, `cloud/apps/relay/src` |
| Agentes | Claude Code, Codex, OpenCode, Pi, Grok, Cursor, Amp, Droid, Hermes e outros, cada um com integração própria | `src/main/agent-hooks/README.md` |
| Servidor sem tela | `orca serve` / `orca-ide serve` para máquina remota; cliente pareado por link; recomenda Tailscale/WireGuard/SSH e **proíbe expor a porta na internet** | `docs/site/content/docs/remote-servers.mdx` |
| Licença | MIT, Copyright 2026 Lovecast Inc.; cobre `mobile/` e `cloud/` | `LICENSE`, `cloud/README.md` |

## 2. Foco: celular e controle remoto

### 2.1 Transporte

| Caminho | Como funciona | Onde |
|---|---|---|
| Direto | Servidor WebSocket no desktop, porta 6768. Começa em loopback; ao gerar um QR de LAN, **reabre em 0.0.0.0** (derruba clientes locais e reconecta). Endpoint `ws://IP:6768` (texto puro; a proteção é a camada E2EE). Dá para editar o endereço no celular (LAN para Tailscale) sem reparear | `src/main/runtime/runtime-rpc/runtime-rpc-network-exposure.ts`, `mobile/README.md`, `mobile.mdx` |
| Relay (nuvem Orca) | Celular e desktop abrem WebSocket **de saída** para uma "célula"; o relay emparelha as duas sessões e repassa quadros. "Director" atribui hosts a células. Funciona atrás de NAT sem abrir porta. Login em conta Orca obrigatório | `cloud/README.md`, `src/main/runtime/mobile-cloud-relay/` (relay-session-broker, relay-control-client etc.) |
| Push | Serviço separado (`cloud/apps/push`) guarda a chave APNs e envia por APNs/FCM. O desktop se autentica com a mesma chave X25519 e pede o push; o celular nunca tem credencial Orca para ele. Só dois estados vão ao celular: `needs-input` e `finished` | `cloud/README.md`, `cloud/docs/push-gateway.md`, `src/shared/mobile-push-contract.ts` |
| Offline | Desktop fechado derruba sessão direta/LAN; o celular reconecta sozinho quando o desktop volta. Relay segue a conexão do desktop. Push em FCM é "colapsável" offline: nem todo alerta é garantido (diz o próprio README) | `mobile.mdx`, `cloud/README.md` |

### 2.2 Pareamento e autenticação

- **Oferta de pareamento** (JSON em base64url, máx. 10 min de validade do convite no caso do relay): versão, endpoint, `deviceToken`, `publicKeyB64` (Curve25519 do desktop), `relay` opcional com `inviteToken`, `scope` (`mobile` ou `runtime`). Entregue por QR (`qrcode`, correção M), deep link `orca://pair?code=` ou código colado. O parser só aceita host `pair` e limita o tamanho (`src/shared/pairing.ts`, `src/shared/mobile-relay-pairing-offer.ts`, `src/main/runtime/mobile-pairing-qr.ts`).
- **Token por aparelho**: cada celular tem token próprio e revogável; a lista fica em um JSON com permissão restrita (no Windows, ACL por addon nativo). Revogar desconecta na hora (`src/main/runtime/device-registry.ts`, `remote-servers.mdx`). Uma linha "pendente" (nunca visto, sem tipo de credencial) é o estado entre gerar o QR e o primeiro uso (`src/main/runtime/device-entry.ts`).
- **Chave de dispositivo** (substitui o token depois do primeiro uso): o aparelho prova posse de uma chave sobre o hash do transcript do handshake (`pairing.registerDeviceKey`, `src/shared/device-key-capability.ts`, `src/main/runtime/rpc/mobile-e2ee-auth-validation.ts`).
- **E2EE**: handshake `e2ee_hello`/`e2ee_ready` com nonces, chaves de sessão por direção, contador de quadros, contexto `direct` ou `relay` amarrado ao transcript; tweetnacl (`src/shared/mobile-e2ee-v2-contract.ts`, `src/main/runtime/rpc/mobile-e2ee-v2-desktop-session.ts`, `src/shared/e2ee-crypto.ts`).
- **Permissões**: cada método RPC declara uma permissão (`workspace`, `desktop-control`, `accounts-admin`, `settings-write`, `pairing-admin`, `host-admin`, `device-self`); só `desktop-control` é concedível por aparelho. O celular é limitado por uma **lista de nomes de métodos** (`src/main/runtime/rpc/rpc-method-permission.ts`, `src/main/runtime/runtime-rpc/runtime-rpc-mobile-method-allowlist.ts`).

### 2.3 O que o celular faz

Ver todos os worktrees e status (trabalhando / pronto / aguardando input); ler scrollback; terminal ou Chat UI; **enviar resposta**, anexar foto/arquivo, ditar; atalhos de terminal; Quick Commands; fechar abas; navegador (viewport móvel); Source Control (stage, commit, push); trocar conta de agente e ver limites; **criar workspace**; push de "agente terminou/precisa de você" (`docs/site/content/docs/mobile.mdx`). Aprovar permissão de ferramenta e responder pergunta do agente: métodos `agentSession.respondToApproval` / `respondToQuestion` e **parar** com `agentSession.cancel` (`src/main/runtime/rpc/methods/structured-agent-session-prompt-response.ts`, `structured-agent-session.ts`, `src/shared/agent-session-stop-capabilities.ts`).

### 2.4 Como as sessões são descobertas e transmitidas

- **Descoberta de estado**: ganchos (hooks) por agente fazem POST para um servidor HTTP em loopback do Orca; quando não há gancho, o próprio agente escreve seu estado no fluxo do terminal por OSC 7501 ("Program Status Protocol"). Gancho tem precedência, OSC preenche o resto (`src/main/agent-hooks/README.md`).
- **Terminal**: `terminal.subscribe` entrega a saída do PTY; o celular renderiza com xterm.js em uma WebView; há `terminal.read` para o scrollback (`mobile/README.md`, `mobile/terminal-output-streaming-findings.md`, lista de rotas em `runtime-rpc-mobile-method-routing.ts`).
- **Eventos estruturados**: `session.tabs.subscribe`, `nativeChat.subscribe` e heartbeat de status do agente (`src/main/runtime/mobile-session-tabs-agent-status-heartbeat.ts`).

### 2.5 Pontos fracos e riscos do modelo do Orca

| Risco | Evidência |
|---|---|
| Celular pareado equivale a **execução de comandos como o usuário** (digitar no terminal, criar arquivos, `git push`, apagar worktree, lançar agente). A permissão fina não separa "ver" de "agir" para o celular, só uma lista de nomes | `runtime-rpc-mobile-method-routing.ts` (terminal.send, files.createFile, git.push, worktree.rm, agent.launch); comentário em `rpc-method-permission.ts` ("workspace ... equals running commands as this host's user") |
| QR e código colado carregam **token e chave pública**; quem fotografar o QR antes do primeiro uso pareia. Mitigação: convite de relay expira em 10 min e "pendente" até o primeiro uso | `mobile-relay-pairing-offer.ts` (`MAX_INVITE_TTL_MS`), `device-entry.ts` |
| Direto em `ws://` na LAN e porta aberta em 0.0.0.0; a confidencialidade depende só do E2EE (bem desenhado, mas é cripto própria, complexa e com muitas versões legadas coexistindo) | `runtime-rpc-network-exposure.ts`, `mobile-e2ee-auth-validation.ts` (caminho "legacy") |
| Relay e push são **serviços de terceiros** operados pela Orca, com conta obrigatória; o push passa título/corpo pela infraestrutura Apple/Google e pelo gateway | `cloud/README.md`, `docs/site/content/docs/mobile.mdx` |
| Complexidade operacional enorme (Terraform, blue/green de células, migração, monitor de incidentes) | `cloud/docs/*`, `cloud/dev/` |
| Não verifiquei: se o backend de conta/login do Relay é auto-hospedável (o código de relay é MIT, mas o "auth plane" parece externo). **Incerto.** | `cloud/docs/orca-relay-operations.md` cita "auth plane" sem trazer o código |

## 3. O que vale pegar do Orca e o que descartar

| Pegar (ideia, não código) | Por quê | Onde |
|---|---|---|
| Token **por aparelho**, revogável, lista com permissão restrita, `lastSeen` | Mesmo modelo serve ao Dove em Python | `device-registry.ts` |
| Pareamento por **código de uso único com validade curta** e estado "pendente" | Fecha a janela do QR fotografado | `mobile-relay-pairing-offer.ts` |
| Permissão **declarada por rota**, com papel (humano local, aparelho remoto) e lista curta para o celular, falhando fechado | Resolve exatamente o buraco do Orca | `rpc-method-permission.ts` |
| Estado do agente por **ganchos + fallback** (OSC 7501) e só dois estados no push (`needs-input`, `finished`) | Reduz o que sai da máquina | `agent-hooks/README.md`, `mobile-push-contract.ts` |
| Atualizar o **endereço** do aparelho sem reparear (LAN/Tailscale) | Útil se o nome do host mudar | `mobile.mdx` |
| Recusa explícita: "não exponha a porta na internet; use Tailscale/SSH" | Confirma a recomendação | `remote-servers.mdx` |
| Worktree por agente, "dormir" worktree, `worktree.ps` | O Dove já tem worktrees por agente; só confirma o caminho | `runtime-rpc-mobile-method-routing.ts` (`worktree.*`) |

**Descartar**: relay e director, Terraform/Cloud Run, gateway de push com APNs/FCM, cripto E2EE própria (NaCl/transcript), terminal remoto via xterm/WebView, Chat UI, voz, conta de agente, navegador remoto, Electron, tudo de `docs/site`, `Casks`, `native`, `skills`. Motivos: exigem Node/binários/nuvem, violam o "só stdlib e local-first" ou resolvem problemas que o Dove não tem (o Dove não é dono do PTY dos agentes).

## 4. O que o Dove tem hoje (verificado em `a2a.py`)

- Painel HTTP em `cmd_panel` (`a2a.py` ~2447): escuta em `127.0.0.1` por padrão; confere `Host` (anti-rebinding), `Origin` (só `http://<Host>`), token por processo no cabeçalho `X-Dove-Token`, `Content-Type` JSON, corpo até 64 KB.
- **Lacuna para uso remoto**: `GET /` entrega o token embutido no HTML a qualquer requisição que passe na checagem de `Host`, e `GET /api/state` e `/api/messages` não pedem token. Hoje isso é seguro porque só o loopback alcança; atrás de um túnel, **quem chegar ao `/` vira o humano**. Também a checagem de `Origin` exige `http://`, então quebra sob HTTPS.
- Escritas (`api_post`) sempre agem como o humano (`human_name()`), inclusive git push, merge, remover worktree, adicionar/remover projeto e agente. Não há papéis.
- `require_human` e `refuse_if_runner` protegem ações da CLI; STOP é o arquivo `~/.a2a/STOP` (`watch_stop`), criado só pelo humano.
- Não existe rota de aval no painel: avais são dos agentes, pela CLI; o humano conclui a missão (`/api/mission/done`).
- Consequência: o Dove não tem "aprovar permissão de ferramenta" como o Orca, porque não controla o terminal dos agentes. O equivalente útil no celular é **missão aguardando o humano**, **vigia pedindo decisão** e **STOP**.

## 5. Opções para o controle remoto do Dove

| Opção | Como | Custo | Segurança | Veredito |
|---|---|---|---|---|
| **A. Painel atrás de `tailscale serve`** | Dove segue em 127.0.0.1; `tailscale serve` publica HTTPS **só na tailnet** (certificado válido, sem porta aberta). O celular usa o navegador (PWA opcional) | Grátis (uso pessoal; confirmar plano), 0 dependência Python | Rede privada + login Tailscale + código de pareamento + papel remoto restrito | **Recomendada** |
| B. SSH com redirecionamento de porta | App SSH no celular (Termius, Blink, Termux) abre `-L` para 127.0.0.1:8765 | 0 | Muito boa (chave SSH); sem QR | Plano B, zero código; incômodo no dia a dia |
| C. Cloudflare Tunnel / ngrok | URL pública para o painel | Grátis/pago; terceiro termina o TLS e vê tudo | Fica na internet; depende de Cloudflare Access bem configurado | Não: exposição pública e terceiro no meio |
| D. Relay próprio (estilo Orca) | Servidor de repasse + E2EE | Alto: servidor, ops, cripto fora da stdlib | Superfície grande | Não: desproporcional |
| E. Escutar em 0.0.0.0 na LAN | `dove --host 0.0.0.0` | 0 | HTTP puro, painel já avisa "visível na rede"; só no Wi-Fi de casa | Não, a não ser como teste temporário |

Notificação (separada do transporte):

| Opção | Observação |
|---|---|
| Página aberta consulta `/api/state` a cada N s (ou SSE) | Stdlib, sem terceiros, só com a aba aberta. **Fase 1** |
| ntfy (auto-hospedável ou ntfy.sh) via `urllib.request` | Push real no celular; **terceiro vê o texto**, então só mensagem genérica ("1 missão aguarda você") e tópico aleatório. Precisa de autorização do Luiz (terceiro/gasto) |
| Web Push (VAPID) | Exige ECDSA/cripto fora da stdlib: descartado |
| APNs/FCM direto | Exige conta de desenvolvedor e chave: descartado |

## 6. Design proposto (opção A)

```
celular --(tailnet, HTTPS)--> tailscaled --(http, 127.0.0.1:8765)--> Dove (a2a.py)
```

**Papéis no servidor.** O processo distingue duas origens de chamada:
- `local`: requisição cujo `Host` é loopback e que não veio pelo proxy do Tailscale. Comportamento atual, inalterado.
- `remoto`: requisição com `Host` igual ao nome `*.ts.net` configurado (lista explícita `remote_hosts` em `~/.a2a/config.json`, vazia por padrão = remoto desligado) **e** cookie/cabeçalho de aparelho válido. Nunca recebe o token do papel `local`.

**Pareamento (código de uso único).**
1. No desktop, `a2a remote pair --from luiz` (só humano, `require_human`) gera um código de 8 a 10 caracteres aleatórios, válido por 5 min, uso único, e mostra no terminal (e opcionalmente como QR em texto; QR exige gerador próprio, então começar só com o código e a URL digitados).
2. No celular, abrir `https://<host>.ts.net/pair` e digitar o código. Limite de tentativas (ex.: 5 erradas apagam o código), comparação com `hmac.compare_digest`.
3. O servidor emite um token por aparelho (`secrets.token_urlsafe(32)`), grava **só o hash** (SHA-256) em `~/.a2a/devices.json` (0600) com nome, criado, `lastSeen`, `grants`, e devolve o token em cookie `HttpOnly; Secure; SameSite=Strict`.
4. `a2a remote list` / `a2a remote revoke <id>` (só humano). Revogação vale na próxima requisição.

**Mudanças no servidor (em passos separados, ver abaixo).** O `/` remoto serve uma página enxuta sem o token local; `/api/*` remoto passa por uma tabela de rotas com permissão **declarada por rota** e falhando fechado (rota ausente da tabela = 403).

**O que o celular pode (padrão) e o que fica só no desktop**

| Ação | Celular | Observação |
|---|---|---|
| Ler estado (agentes, missões, resumo, mensagens) | Sim, só leitura | Resposta reduzida: sem caminhos de disco; mensagens limitadas |
| Ver execuções do vigia e o que está aguardando o humano | Sim | |
| **STOP** (criar `~/.a2a/STOP`, com `--kill` opcional) | **Sim, sempre** | Ação de segurança que só reduz risco; falha segura |
| Mandar mensagem a um agente (`/api/send`) | Sim, mas **concessão `send` desligada por padrão** | Cuidado: com o vigia ligado, uma mensagem pode disparar execução de agente; o limite de custo/STOP continuam valendo. Registrar origem `remoto:<aparelho>` no envelope só se o Luiz autorizar mudança de envelope; senão registrar apenas no log do servidor |
| Concluir missão (`/api/mission/done`) | Sim, concessão `mission` | O aval continua só dos agentes |
| Criar missão | Opcional, concessão `mission` | |
| Retomar do STOP (`watch resume`) | **Não** | Reiniciar execução é decisão no desktop |
| git commit/push, merge, sync, remover worktree | **Não** | Equivale ao buraco do Orca; no máximo leitura de `git status/diff` |
| Adicionar/remover projeto ou agente, navegar pastas (`fs/list`, `scan`) | **Não** | |
| Mudar orçamento/limites, config, doctor | **Não** | |
| Parear/revogar aparelhos | **Não** | Só `a2a remote ...` local |

**Manter stdlib-only.** `secrets`, `hmac`, `hashlib`, `http.server`, `json`, `urllib.request` (só para ntfy, opcional). HTTPS e certificado ficam com o `tailscaled`; o Python não faz TLS. Sem WebSocket: polling/SSE basta. Sem QR na primeira versão.

**Riscos e mitigações**

| Risco | Mitigação |
|---|---|
| Celular perdido/roubado | Token por aparelho, `revoke` no desktop; concessões mínimas; expiração do aparelho (ex.: 30 dias sem uso) |
| Alguém na tailnet alcança o painel | Código de pareamento + token do aparelho; recomendar ACL do Tailscale limitando o celular ao desktop |
| Rebinding / cross-site no host remoto | `remote_hosts` explícito; `Origin` aceita `https://<host remoto>`; cookie `SameSite=Strict` + cabeçalho CSRF próprio nas escritas |
| Vazamento de conteúdo das mensagens (tarefas, código) | Fica na tailnet (WireGuard); `tailscale serve` **não** usa o Funnel (que é público); nunca habilitar Funnel |
| Mensagem remota dispara agente | Concessão `send` desligada por padrão; vigia, orçamento e STOP inalterados |
| Dependência do Tailscale (terceiro de controle) | Aceito para uso pessoal; plano B é SSH (opção B) sem mudar o servidor |
| Regressão no painel local | Papel `local` intacto; testes de contrato antes de mexer |
| Falso senso de "aprovar permissão" como no Orca | Documentar que o Dove não controla o PTY; escopo é coordenação |

## 7. Passos ordenados (pequenos e atômicos)

Legenda de esforço: P ≤ 1 h · M ≤ 3 h · G ≤ 1 dia. "Aval" = precisa de autorização do Luiz antes (regra do canal: gasto, `~/.a2a`, envelope).

| # | Passo | Esforço | Aval |
|---|---|---|---|
| 0 | Teste manual sem código: `dove` normal + `tailscale serve --bg 8765` e abrir no celular para ver o que falha (esperado: 403 de Host). Medir a latência e confirmar que é só tailnet (sem Funnel) | P | Instalar/usar Tailscale |
| 1 | Config `remote_hosts` (lista vazia = desligado) e `a2a remote status`; nenhum comportamento muda | P | Novo campo em `~/.a2a/config.json` |
| 2 | **Papel de requisição**: classificar `local` x `remoto` por `Host`; `remoto` nunca recebe o token local no `/`; tabela de rotas com permissão por rota, falha fechada; testes (Host errado, Origin errado, rota fora da tabela) | M | Não |
| 3 | `a2a remote pair/list/revoke` + `~/.a2a/devices.json` (0600, só hash) + `/pair` com limite de tentativas e código de uso único (5 min) | G | **Sim** (novo arquivo em `~/.a2a`) |
| 4 | Leitura remota: `/api/state` e `/api/messages` reduzidos para o papel remoto (sem caminhos de disco), exigindo aparelho válido | M | Não |
| 5 | Página móvel `ui/remote.html` (estado, missões, aguardando você, STOP) — só leitura + STOP | M | Mexe em `ui/` (hoje do Claude Design/pausada): combinar com o Luiz |
| 6 | **STOP remoto** (`/api/watch/stop`, sem `--kill` por padrão, `--kill` com confirmação) + log de auditoria `~/.a2a/remote.log` | P | Não |
| 7 | Concessões `mission` e `send` por aparelho, ambas desligadas por padrão; `/api/mission/done` e `/api/send` remotos; auditoria | M | **Sim** (concessão `send` pode disparar execução) |
| 8 | Revisão de segurança dedicada (rebinding, CSRF, cookie, timing, enumeração) + teste de fumaça de contrato | M | Não |
| 9 | Notificação por polling na página (título da aba e badge) | P | Não |
| 10 | Opcional: ntfy com texto genérico e tópico aleatório | M | **Sim** (terceiro; possível gasto) |
| 11 | Opcional: QR de pareamento em texto no terminal (gerador próprio ~150 linhas) | M | Não |

Total até o passo 9: ~2 a 3 dias de trabalho em PRs pequenos. Cada passo entra com testes em `tests/` e sem mexer no comportamento local.

## 8. Recomendação

**Fazer a opção A**, na ordem acima, começando pelo passo 0 (teste sem código, hoje) e pelos passos 1 a 4 (base de segurança) **antes** de qualquer tela móvel. Lançar com **somente leitura + STOP**; `mission done` e `send` só depois da revisão do passo 8.

**Não fazer:**
- Não construir relay, nem copiar o protocolo/cripto do Orca.
- Não abrir a porta na internet nem usar Tailscale Funnel, Cloudflare Tunnel ou ngrok.
- Não escutar em 0.0.0.0 como solução permanente.
- Não dar ao celular git push, merge, remoção de worktree, gerenciamento de projetos/agentes, nem reativar o vigia depois do STOP.
- Não prometer "aprovar permissão de ferramenta" do agente: o Dove não é dono do terminal.
- Não adicionar dependência Python (Web Push, QR, WebSocket) nesta fase.

## 9. Incertezas e o que não foi verificado

- Nada foi executado (regra da pesquisa): o fluxo real do app móvel do Orca, o Relay e o push foram lidos só em código e documentação.
- Não li todo o handshake E2EE nem auditei a cripto do Orca; não afirmo que seja segura ou insegura, só descrevo o desenho.
- Se o login/auth do Relay é auto-hospedável não está claro nos arquivos lidos.
- O comportamento de `tailscale serve` (cabeçalho `Host`, cabeçalhos de identidade, necessidade de HTTPS habilitado na tailnet) e os termos atuais do plano gratuito precisam ser confirmados no passo 0.
- A licença MIT foi lida em `LICENSE` e em `cloud/README.md`; dependências de terceiros do `mobile/` (Expo, xterm, mermaid, etc.) têm licenças próprias, não revisadas.
