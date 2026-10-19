# Roadmap do Dove

Estado em 2026-10-19 · base `main` em 8748075.

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
Todos os passos têm aval do Luiz, **exceto o 12**.

| Passo | Item | Estado |
|---|---|---|
| 0+1 | Segurança: `mission done` só humano, `--from` obrigatório, `vigia` reservado, `A2A_RUNNER` nunca age como humano | em execução |
| 2 | `a2a loops` (prevenção de loop entre agentes automáticos) | em execução |
| 3 | `a2a watch --dry-run` | próximo |
| 4 | `a2a cost` (lê os registros do Claude/Codex/Hermes, só leitura) | em execução |
| 5 | `a2a watch check` | em execução |
| 6 | Supervisor: `STOP`, travas, timeout, Job Object | em execução |
| 7 | Vigia real, só com o `claude`, iniciado à mão | próximo |
| 8 | Orçamento por missão | próximo |
| 9 | Codex no vigia (sandbox do Windows; sem commit) | próximo |
| 10 | `a2a models` (roteamento de modelo) | em execução |
| 11 | Orquestrador (só leitura + mensagens) | próximo |
| 12 | Hermes no vigia | **PENDENTE**: aguarda o Luiz definir a contenção |
| 13 | Política de subagentes | em execução |

## 5. Decisões
**Tomadas**
- `a2a map` adiado até medir a exploração com `a2a cost`.
- token-optimizer **não adotado** (licença PolyForm Noncommercial, hooks em toda ferramenta, grava `cleanupPeriodDays`); só ideias, reescritas.
- TOON, memória vetorial/GraphRAG, SupervisorAgent e mcp-compressor **não adotados**.
- Instruções globais (`a2a instructions`) em vez de AGENTS.md por repositório (PR lagu #38 fechado).
- Hermes não recebe instruções globais por padrão (o `SOUL.md` dele é persona).
- Parte visual pausada. O backend já está pronto para: aba Git, cópias de trabalho, memória e custo.

**Pendentes**
- Contenção do Hermes no vigia (passo 12) — decisão do Luiz.

## 6. Depois da Fase 3
- Canal entre máquinas: VPS Ubuntu 24.04 + Omarchy + Windows.
- Retomada visual com o Claude Design.
- Integração ou substituição do qLink.

## 7. Como retomar numa sessão nova
1. Leia este arquivo e rode `git log --oneline | head -30`.
2. Rode os testes: `python3 tests/test_a2a.py`.
3. Propostas: `docs/propostas/` no `main` e os branches `proposta/*` (`fase3-orquestrador`, `interface-agentes`).
4. Regras: só a stdlib; não mexer em `ui/` sem o Luiz; `DOVE_VERSION` estável enquanto a UI estiver pausada.
5. Sensível (execução de agentes, gasto, `~/.a2a`, envelope, merge/deploy) só com aval do Luiz.
