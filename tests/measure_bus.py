#!/usr/bin/env python3
"""Benchmark de bus grande: quanto custa brief/summary/inbox/painel quando o bus/ tem milhares de mensagens.

Cenario (fixo, gerado com seed): 2.000 mensagens, 3 agentes (claude, codex, hermes) + o humano luiz, 20 missoes
(15 confirmadas pelo humano, 5 abertas). A maior parte sao fios task -> ack -> report CONCLUIDO antigos (3 a 60 dias)
e ja lidos; os ultimos 2 dias tem tarefas abertas e mensagens nao lidas.

Mede (wall clock, mediana de 5):
- CLI (subprocess, inclui a partida do Python): brief --agent codex, summary, inbox --agent codex;
- panel_state() (em processo, o que o painel chama a cada 3s);
- wait --timeout 3 --interval 0.2: quantas vezes all_messages() (leitura completa do bus) foi chamada.
Fases medidas conforme o a2a.py disponivel: bus inteiro; se houver `a2a index`, com indice frio (apagado antes de
cada execucao) e quente; se houver `a2a archive`, depois de arquivar os fios encerrados (> 14 dias).

Uso: python3 tests/measure_bus.py [--n 2000]      So stdlib.
"""
import json, os, random, shutil, statistics, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
A2A = os.path.join(HERE, "..", "a2a.py")
AGENTS = ("claude", "codex", "hermes")
RUNS = 5

def seed_home(home, n=2000, seed=20261019):
    rnd = random.Random(seed)
    for d in ("bus", "cursor", "agents", "status", "missions"): os.makedirs(os.path.join(home, d), exist_ok=True)
    for a in AGENTS: open(os.path.join(home, "agents", a), "w").close()
    now = time.time(); msgs, seen = [], {a: set() for a in AGENTS}
    def put(t, frm, to, kind, body, state="", reply="", task="", evidence="", read=True, project=None):
        mid = "%012x" % rnd.getrandbits(48)
        m = {"data": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)), "task_id": task, "msg_id": mid, "from": frm,
             "to": to, "project": project or rnd.choice(("lagu", "qlink", "dove")), "in_reply_to": reply, "kind": kind,
             "state": state, "result": "", "evidence": evidence, "pending": "", "next_action": "",
             "body": body + " " + "detalhe " * rnd.randint(10, 30)}
        msgs.append((t, m))
        if frm in seen: seen[frm].add(mid)
        if read:
            for a in (AGENTS if to == "all" else (to,)):
                if a in seen: seen[a].add(mid)
        return mid
    who = AGENTS + ("luiz",)
    # 20 missoes: tasks de luiz para os 3 agentes + reports de aval
    for i in range(20):
        mid, t = f"m{i:07d}", now - rnd.uniform(3, 60) * 86400 if i < 15 else now - rnd.uniform(0, 2) * 86400
        ap = {}
        for a in AGENTS:
            tk = put(t, "luiz", a, "task", f"Missao {mid}: entrega {i}", task=mid, project="lagu"); t += 60
            if i < 15 or rnd.random() < 0.5:
                put(t, a, "luiz", "report", f"Missao {mid} aprovada por {a}", state="CONCLUIDO", reply=tk, task=mid,
                    evidence="testes ok", project="lagu"); t += 60
                ap[a] = {"verdict": "approve", "ts": "x", "evidence": "testes ok", "reason": ""}
        with open(os.path.join(home, "missions", mid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"id": mid, "project": "lagu", "title": f"entrega {i}", "description": "", "agents": list(AGENTS),
                       "created_by": "luiz", "created": "2026-09-01T00:00:00Z", "approvals": ap, "history": [],
                       "human": {"by": "luiz", "ts": "2026-10-01T00:00:00Z"} if i < 15 else None}, f)
    # fios task -> ack -> report (antigos e fechados; recentes as vezes abertos/nao lidos)
    while len(msgs) < n:
        recent = len(msgs) > n * 0.9
        t = now - (rnd.uniform(0, 2) if recent else rnd.uniform(3, 60)) * 86400
        frm = rnd.choice(who); to = rnd.choice([a for a in who if a != frm])
        r = rnd.random()
        if r < 0.08:  # broadcast
            put(t, frm, "all", "report", "aviso geral", read=not recent or rnd.random() < 0.5); continue
        if r < 0.2:  # pergunta e resposta
            q = put(t, frm, to, "question", "pergunta", read=not recent or rnd.random() < 0.5)
            put(t + 120, to, frm, "report", "resposta", reply=q, read=not recent or rnd.random() < 0.5); continue
        tk = put(t, frm, to, "task", "tarefa", read=not recent or rnd.random() < 0.5)
        if not recent or rnd.random() < 0.6:
            put(t + 60, to, frm, "ack", "recebido", reply=tk)
        if not recent or rnd.random() < 0.4:
            put(t + 600, to, frm, "report", "feito", state="CONCLUIDO", reply=tk, evidence="commit abc",
                read=not recent or rnd.random() < 0.5)
    for t, m in msgs[:n]:
        fn = m["data"].replace(":", "").replace("-", "") + "-" + m["msg_id"] + ".json"
        p = os.path.join(home, "bus", fn)
        with open(p, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=2)
        os.utime(p, (t, t))
    for a in AGENTS:
        with open(os.path.join(home, "cursor", a + ".json"), "w") as f: json.dump(sorted(seen[a]), f)
        with open(os.path.join(home, "status", a + ".json"), "w") as f:
            json.dump({"agent": a, "state": "working", "note": "", "project": "lagu", "updated": "x", "ts": now}, f)

INPROC = r"""
import argparse, contextlib, io, json, statistics, sys, time
sys.path.insert(0, sys.argv[1]); import a2a
cold = sys.argv[2] == "1"
def drop_index():
    p = getattr(a2a, "INDEX", None)
    if cold and p:
        try: __import__("os").remove(p)
        except OSError: pass
ts = []
for _ in range(int(sys.argv[3])):
    drop_index(); t0 = time.perf_counter(); a2a.panel_state(); ts.append(time.perf_counter() - t0)
calls = {"n": 0}; orig = a2a.all_messages
def counted(*x, **k):
    calls["n"] += 1; return orig(*x, **k)
a2a.all_messages = counted
ns = argparse.Namespace(agent="codex", project="nenhum", timeout=3, interval=0.2, until=None, no_auto_status=True, compact=False)
with contextlib.redirect_stdout(io.StringIO()):
    try: a2a.cmd_wait(ns)
    except SystemExit: pass
print(json.dumps({"panel": statistics.median(ts), "wait_calls": calls["n"]}))
"""

def cli(home, *args):
    env = dict(os.environ, A2A_HOME=home, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, A2A, *args], capture_output=True, env=env)
    assert r.returncode == 0, (args, r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8")

def has_cmd(name):
    r = subprocess.run([sys.executable, A2A, name, "--help"], capture_output=True)
    return r.returncode == 0

def measure(home, cold=False):
    def timed(*args):
        ts = []
        for _ in range(RUNS):
            if cold:
                try: os.remove(os.path.join(home, "index.json"))
                except OSError: pass
            t0 = time.perf_counter(); cli(home, *args); ts.append(time.perf_counter() - t0)
        return statistics.median(ts)
    res = {"brief": timed("brief", "--agent", "codex", "--no-auto-status"), "summary": timed("summary"),
           "inbox": timed("inbox", "--agent", "codex", "--no-auto-status")}
    env = dict(os.environ, A2A_HOME=home)
    r = subprocess.run([sys.executable, "-c", INPROC, os.path.join(HERE, ".."), "1" if cold else "0", str(RUNS)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    res.update(json.loads(r.stdout))
    res["bus"] = len([f for f in os.listdir(os.path.join(home, "bus")) if f.endswith(".json")])
    return res

def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2000
    root = tempfile.mkdtemp(prefix="dove-bus-"); home = os.path.join(root, "home"); seed_home(home, n)
    ts = []
    for _ in range(RUNS):
        t0 = time.perf_counter(); cli(home, "--version"); ts.append(time.perf_counter() - t0)
    py = statistics.median(ts)
    rows = []
    idx = has_cmd("index")
    if idx:
        rows.append(("bus inteiro, sem indice", measure(home, cold=True)))
        cli(home, "index", "rebuild")
        rows.append(("bus inteiro, indice quente", measure(home)))
    else: rows.append(("bus inteiro", measure(home)))
    if has_cmd("archive"):
        out = cli(home, "archive", "--from", "luiz")
        rows.append(("depois do archive" + (" (indice quente)" if idx else ""), measure(home)))
        print("archive:", out.strip().splitlines()[0])
    print(f"Bus: {n} mensagens, 3 agentes, 20 missoes. Mediana de {RUNS}. CLI inclui a partida (a2a --version: {py*1000:.0f} ms).")
    print(f"{'fase':<34} {'bus':>5} {'brief':>8} {'summary':>8} {'inbox':>8} {'panel_state':>12} {'wait all_messages':>18}")
    for name, x in rows:
        print(f"{name:<34} {x['bus']:>5} {x['brief']*1000:>6.0f}ms {x['summary']*1000:>6.0f}ms {x['inbox']*1000:>6.0f}ms "
              f"{x['panel']*1000:>10.1f}ms {x['wait_calls']:>18}")
    shutil.rmtree(root, ignore_errors=True)

if __name__ == "__main__":
    main()
