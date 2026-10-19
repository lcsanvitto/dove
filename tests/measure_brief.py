#!/usr/bin/env python3
"""Medicao reprodutivel: quanto texto um agente le para se atualizar, antes e depois do `a2a brief`.

Cenario (o da proposta docs/propostas/2026-10-18-interface-agentes.md, secao "Medicao"):
- agentes claude, codex, hermes e o humano luiz; medicao do ponto de vista de codex;
- 40 mensagens no bus; 14 visiveis para codex: 9 ja lidas e 5 nao lidas (1 delas e ack);
- 1 tarefa aberta ja lida para codex;
- 3 missoes: 1 esperando o aval de codex, 1 com o aval dele ja dado e 1 de que ele nao participa.
Textos fixos (corpos de 120 a 300 caracteres), ids fixos e idades fixas (horas) -> mesmo resultado a cada execucao.

Antes:  inbox --agent codex + read <id> --agent codex para cada nao lida listada + mission list
Depois: brief --agent codex --mark-read     (e a variante "depois + 1 read")
Cada sequencia roda numa copia nova do mesmo A2A_HOME. Unidade: stdout de cada comando;
chars = len(texto), bytes = len(texto.encode("utf-8")), tokens_est = ceil(chars / 4).

Uso: python3 tests/measure_brief.py [--show]   (--show imprime as saidas brutas)
So stdlib.
"""
import hashlib, json, math, os, shutil, subprocess, sys, tempfile, time

A2A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "a2a.py")
SEED = 20261018  # ids derivados do seed: sha1(seed:indice)[:12]
AGENT = "codex"

B = {  # corpos fixos, 120-300 caracteres
    "webhook": "Migrar o webhook de pagamentos para a assinatura nova (X-Signature com HMAC-SHA256). Comecar pelo handler "
               "em src/payments/webhook.py e pelos testes de contrato; manter a assinatura antiga aceita por 7 dias.",
    "cupom": "Cupom de frete gratis: aplicar a regra acima de R$ 199 no carrinho e no checkout. A regra antiga (R$ 249) "
             "ainda esta no cache do CDN; invalidar depois do deploy em staging e avisar o hermes para rodar o E2E.",
    "e2e": "E2E staging: 148 ok, 2 falhas, as duas no fluxo de frete gratis (carrinho com 3 itens e cupom FRETE199). "
           "Relatorio completo anexado; parece ser o arredondamento do subtotal antes de aplicar o desconto.",
    "cred": "A credencial de homologacao do banco chegou? Sem ela nao da para validar o webhook novo de ponta a ponta. "
            "Se nao chegou ate amanha, vou pedir de novo ao gerente da conta e marcar a tarefa como bloqueada.",
    "review": "Revisei o PR do checkout novo: a validacao do CEP esta duplicada no front e no back, e o timeout do "
              "gateway esta em 30s (deveria ser 10s). Fora isso, aprovado. Pode seguir com os ajustes que eu reviso de novo.",
    "lint": "Rodei o lint e o typecheck no monorepo inteiro: 0 erros, 14 avisos antigos (todos em scripts/legacy). "
            "Nao mexi em nada; so registrando o estado antes da sua refatoracao do modulo de pagamentos.",
    "deploy": "Deploy em staging feito com o commit 9be1c0a. Migrations rodaram limpas (3 novas). O feature flag "
              "checkout_v2 esta ligado so para o time interno. Monitorando os logs por 30 minutos antes de liberar.",
    "doc": "Atualizei o README do servico de pagamentos com o fluxo novo de assinatura e o passo a passo para gerar "
           "a chave de homologacao. Falta so o diagrama de sequencia, que deixo para depois do merge.",
    "perf": "Medi o checkout novo em staging: p50 de 420ms e p95 de 1,3s no passo de pagamento. O gargalo e a chamada "
            "sincrona ao antifraude; sugiro mover para fila e responder 202 ao front enquanto a analise roda.",
    "ok": "Entendido. Vou pegar a parte do antifraude assincrono depois que o webhook estiver estavel em staging; "
          "abro uma tarefa separada para nao misturar os dois PRs e registro aqui quando comecar.",
    "fix": "Corrigi o arredondamento do subtotal (Decimal com ROUND_HALF_EVEN em vez de float) e adicionei 6 testes "
           "de borda para o frete gratis. Commit 3c41d2e na branch dove/claude, pronto para revisao.",
    "q": "Alguem sabe se o ambiente de staging ainda usa o banco de homologacao antigo? Os pedidos de teste de ontem "
         "nao aparecem no painel do banco e quero descartar problema de credencial antes de abrir chamado.",
}

def mid(i): return hashlib.sha1(f"{SEED}:{i}".encode()).hexdigest()[:12]

def seed_home(home):
    for d in ("bus", "cursor", "agents", "status", "missions"): os.makedirs(os.path.join(home, d), exist_ok=True)
    for a in ("claude", "codex", "hermes"): open(os.path.join(home, "agents", a), "w").close()
    base = time.time() - 4 * 3600  # 40 mensagens, 1 por minuto: idades entre 3h e 4h (2 caracteres)
    msgs, seen = [], []
    def put(frm, to, kind, body, project="lagu", state="", evidence="", reply="", task="", read=False):
        i = len(msgs); m_id = mid(i)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * 60))
        m = {"data": ts, "task_id": task, "msg_id": m_id, "from": frm, "to": to, "project": project,
             "in_reply_to": reply, "kind": kind, "state": state, "result": "", "evidence": evidence,
             "pending": "", "next_action": "", "body": body}
        msgs.append(m)
        if read: seen.append(m_id)
        return m_id
    # missoes (ids fixos); tasks de missao como o mission_new faz
    M1, M2, M3 = "m1a2b3c4", "m5d6e7f8", "m9a0b1c2"
    t_m1 = put("luiz", "codex", "task", f"Missao {M1}: Checkout novo pronto para producao\nVerifique e de seu aval: a2a mission approve {M1} --agent codex --evidence \"...\" (ou: a2a mission reject {M1} --agent codex --reason \"...\")", task=M1, read=True)
    put("luiz", "claude", "task", f"Missao {M1}: Checkout novo pronto para producao\nVerifique e de seu aval: a2a mission approve {M1} --agent claude --evidence \"...\"", task=M1)
    put("luiz", "hermes", "task", f"Missao {M1}: Checkout novo pronto para producao\nVerifique e de seu aval: a2a mission approve {M1} --agent hermes --evidence \"...\"", task=M1)
    t_m2 = put("luiz", "codex", "task", f"Missao {M2}: Webhook novo em staging\nVerifique e de seu aval: a2a mission approve {M2} --agent codex --evidence \"...\" (ou: a2a mission reject {M2} --agent codex --reason \"...\")", task=M2, read=True)
    put("luiz", "hermes", "task", f"Missao {M2}: Webhook novo em staging\nVerifique e de seu aval: a2a mission approve {M2} --agent hermes --evidence \"...\"", task=M2)
    put("codex", "luiz", "report", f"Missao {M2} aprovada por codex: Webhook novo em staging", state="CONCLUIDO", evidence="testes de contrato 38/38", reply=t_m2, task=M2)
    put("luiz", "claude", "task", f"Missao {M3}: Documentacao do servico\nVerifique e de seu aval: a2a mission approve {M3} --agent claude --evidence \"...\"", task=M3, project="dove")
    put("luiz", "hermes", "task", f"Missao {M3}: Documentacao do servico\nVerifique e de seu aval: a2a mission approve {M3} --agent hermes --evidence \"...\"", task=M3, project="dove")
    # trafego geral (lidas pelo codex, proprias do codex e entre os outros)
    t_open = put("luiz", "codex", "task", B["webhook"], read=True)                    # tarefa aberta ja lida -> T
    t_lint = put("claude", "codex", "task", B["lint"], read=True)
    put("codex", "claude", "report", B["ok"], state="CONCLUIDO", reply=t_lint)
    put("hermes", "codex", "report", B["deploy"], state="CONCLUIDO", evidence="staging 9be1c0a", read=True)
    put("claude", "hermes", "task", B["review"])
    put("hermes", "claude", "report", B["perf"], state="EM_EXECUCAO")
    put("claude", "codex", "question", B["q"], read=True)
    put("codex", "claude", "report", B["doc"], state="EM_EXECUCAO")
    put("hermes", "codex", "question", B["q"], project="qlink", read=True)
    put("codex", "hermes", "report", B["ok"], project="qlink")
    put("claude", "all", "report", B["doc"], read=True)                               # broadcast visivel
    put("hermes", "luiz", "report", B["deploy"], state="CONCLUIDO", evidence="staging 9be1c0a")
    put("claude", "luiz", "report", B["review"], state="AGUARDANDO_APROVACAO")
    put("codex", "luiz", "question", B["cred"])
    put("hermes", "claude", "task", B["perf"])
    put("claude", "hermes", "report", B["fix"], state="CONCLUIDO", evidence="commit 3c41d2e")
    put("luiz", "hermes", "task", B["e2e"], project="qlink")
    put("hermes", "luiz", "report", B["e2e"], project="qlink", state="EM_EXECUCAO")
    put("claude", "hermes", "question", B["q"])
    put("hermes", "claude", "report", B["ok"])
    put("codex", "hermes", "task", B["e2e"])
    put("hermes", "codex", "ack", "recebido", reply=mid(len(msgs) - 1), read=True)
    put("hermes", "claude", "report", B["deploy"], state="CONCLUIDO")
    put("codex", "luiz", "report", B["perf"], state="EM_EXECUCAO")
    put("claude", "hermes", "task", B["doc"], project="dove")
    put("luiz", "claude", "question", B["cred"])
    q_codex = put("codex", "claude", "question", B["q"])
    # 5 nao lidas para codex (1 ack)
    put("claude", "codex", "task", B["cupom"])
    put("hermes", "codex", "report", B["e2e"], project="qlink", state="CONCLUIDO", evidence="e2e/report.html")
    put("luiz", "codex", "question", B["cred"])
    put("claude", "codex", "ack", "recebido", reply=q_codex)
    put("claude", "codex", "report", B["fix"], state="AGUARDANDO_APROVACAO", evidence="commit 3c41d2e")
    assert len(msgs) == 40, len(msgs)
    for m in msgs:
        fn = m["data"].replace(":", "").replace("-", "") + "-" + m["msg_id"] + ".json"
        with open(os.path.join(home, "bus", fn), "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=2)
        t = base + msgs.index(m) * 60; os.utime(os.path.join(home, "bus", fn), (t, t))
    with open(os.path.join(home, "cursor", "codex.json"), "w") as f: json.dump(sorted(seen), f)
    ap = lambda *xs: {a: {"verdict": "approve", "ts": "2026-10-18T12:00:00Z", "evidence": "ok", "reason": ""} for a in xs}
    for m_id, title, proj, agents, approvals in (
            (M1, "Checkout novo pronto para producao", "lagu", ["claude", "codex", "hermes"], ap("claude", "hermes")),
            (M2, "Webhook novo em staging", "lagu", ["codex", "hermes"], ap("codex")),
            (M3, "Documentacao do servico", "dove", ["claude", "hermes"], {})):
        with open(os.path.join(home, "missions", m_id + ".json"), "w", encoding="utf-8") as f:
            json.dump({"id": m_id, "project": proj, "title": title, "description": "", "agents": agents,
                       "created_by": "luiz", "created": "2026-10-18T10:00:00Z", "approvals": approvals,
                       "history": [], "human": None}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(home, "status", "codex.json"), "w") as f:
        json.dump({"agent": "codex", "state": "working", "note": "webhook novo", "project": "lagu",
                   "context": 64, "updated": "x", "ts": time.time()}, f)
    vis = [m for m in msgs if m["to"] in (AGENT, "all") and m["from"] != AGENT]
    unread = [m for m in vis if m["msg_id"] not in seen]
    assert len(vis) == 14 and len(unread) == 5 and sum(m["kind"] == "ack" for m in unread) == 1, (len(vis), len(unread))
    return t_open

def a2a(home, *args):
    env = dict(os.environ, A2A_HOME=home, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, A2A, *args], capture_output=True, env=env)
    assert r.returncode == 0, (args, r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8")

def measure(outs):
    text = "".join(o for _, o in outs)
    chars = len(text)
    return {"cmds": len(outs), "chars": chars, "bytes": len(text.encode("utf-8")), "tokens": math.ceil(chars / 4)}

def main():
    show = "--show" in sys.argv
    root = tempfile.mkdtemp(prefix="dove-measure-")
    seeded = os.path.join(root, "seed"); t_open = seed_home(seeded)
    def fresh(name): p = os.path.join(root, name); shutil.copytree(seeded, p); return p
    # antes
    h = fresh("antes"); antes = [("inbox --agent codex", a2a(h, "inbox", "--agent", AGENT))]
    ids = [l.split()[1] for l in antes[0][1].splitlines() if l.startswith("[")]
    for i in ids: antes.append((f"read {i} --agent codex", a2a(h, "read", i, "--agent", AGENT)))
    antes.append(("mission list", a2a(h, "mission", "list")))
    # depois
    h = fresh("depois"); depois = [("brief --agent codex --mark-read", a2a(h, "brief", "--agent", AGENT, "--mark-read"))]
    first_n = next(l.split()[1] for l in depois[0][1].splitlines() if l.startswith("N "))
    depois_read = depois + [(f"read {first_n} --agent codex", a2a(h, "read", first_n, "--agent", AGENT))]
    ra, rd, rr = measure(antes), measure(depois), measure(depois_read)
    red = lambda x: f"{100 * (1 - x / ra['tokens']):.1f}%" if ra["tokens"] else "-"
    print(f"Cenario: 40 mensagens, 14 visiveis para {AGENT} (9 lidas, 5 nao lidas incl. 1 ack), 1 tarefa aberta lida, 3 missoes")
    print("tokens_est = ceil(chars / 4); medido no stdout de cada comando\n")
    print(f"{'sequencia':<26} {'cmds':>4} {'chars':>7} {'bytes':>7} {'tokens_est':>10} {'reducao':>8}")
    for name, r in (("antes (inbox+5 read+list)", ra), ("depois (brief)", rd), ("depois + 1 read", rr)):
        print(f"{name:<26} {r['cmds']:>4} {r['chars']:>7} {r['bytes']:>7} {r['tokens']:>10} {red(r['tokens']) if r is not ra else '-':>8}")
    # equivalencia de informacao (checagens automaticas)
    b = depois[0][1]; a_all = "".join(o for _, o in antes)
    print("\nEquivalencia:")
    print(f"  nao lidas: antes {len(ids)} ids; brief cita {sum(i in b for i in ids)} (as N + o ack contado em ACK, sem o id)")
    print(f"  tarefa aberta ja lida ({t_open}): antes {'aparece' if t_open in a_all else 'NAO aparece'}; brief {'aparece (T)' if t_open in b else 'nao aparece'}")
    print(f"  missoes: mission list mostra {antes[-1][1].count(chr(10))}; brief mostra {b.count(chr(10) + 'M ')} (so a que espera o aval de {AGENT})")
    if show:
        for title, outs in (("ANTES", antes), ("DEPOIS (+1 read)", depois_read)):
            print(f"\n===== {title} =====")
            for cmd, o in outs: print(f"$ a2a {cmd}\n{o}", end="" if o.endswith("\n") else "\n")
    shutil.rmtree(root, ignore_errors=True)

if __name__ == "__main__":
    main()
