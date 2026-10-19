import http.client, json, os, re, socket, subprocess, sys, tempfile, time, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
A2A = ROOT / "a2a.py"

def run(env, *args):
    return subprocess.run([sys.executable, str(A2A), *args],
                          capture_output=True, text=True, env=env)

def main():
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, A2A_HOME=tmp)
    assert run(env, "init").returncode == 0
    run(env, "join", "--agent", "claude")
    run(env, "join", "--agent", "hermes")
    r = run(env, "send", "--from", "claude", "--to", "hermes",
            "--project", "demo", "--kind", "task", "--body", "oi hermes")
    assert r.returncode == 0, r.stderr
    inb = run(env, "inbox", "--agent", "hermes", "--no-auto-status")
    assert "oi hermes" in inb.stdout, inb.stdout
    inb_c = run(env, "inbox", "--agent", "claude")
    assert "(caixa vazia)" in inb_c.stdout, inb_c.stdout
    print("OK: fluxo send/inbox e anti-eco funcionam")

    # modo herdr: status / quadro / stale / wait --until
    r = run(env, "status", "--agent", "claude", "--set", "working", "--note", "rev X", "--project", "demo")
    assert r.returncode == 0, r.stderr
    board = run(env, "status")
    line = next(l for l in board.stdout.splitlines() if l.startswith("claude"))
    assert "working" in line and "rev X" in line, board.stdout
    assert any(l.startswith("hermes") and "unknown" in l for l in board.stdout.splitlines()), board.stdout
    one = run(env, "status", "--agent", "claude")
    assert "working" in one.stdout and one.stdout.count("\n") == 1, one.stdout
    assert run(env, "status", "--set", "done").returncode == 1
    old = {"agent": "velho", "state": "working", "note": "", "project": "",
           "updated": "x", "ts": time.time() - 7200}
    json.dump(old, open(os.path.join(tmp, "status", "velho.json"), "w"))
    board = run(env, "status")
    line = next(l for l in board.stdout.splitlines() if l.startswith("velho"))
    assert "unknown" in line and "stale" in line and "era working" in line, board.stdout
    run(env, "status", "--agent", "hermes", "--set", "done")
    t0 = time.time()
    w = run(env, "wait", "--agent", "hermes", "--until", "done", "--timeout", "2")
    assert w.returncode == 0 and '"done"' in w.stdout and time.time() - t0 < 2, (w.returncode, w.stdout)
    w = run(env, "wait", "--agent", "claude", "--until", "done", "--timeout", "1", "--interval", "0.2")
    assert w.returncode == 2 and "(timeout)" in w.stdout, (w.returncode, w.stdout)
    print("OK: modo herdr (status, quadro, stale, wait --until) funciona")

    # auto-status: estado vem das mensagens; heartbeat em inbox/wait/ack
    st = lambda a: json.load(open(os.path.join(tmp, "status", a + ".json")))
    for state, exp in (("EM_EXECUCAO", "working"), ("CONCLUIDO", "done"), ("BLOQUEADO", "blocked")):
        before = st("hermes")
        r = run(env, "send", "--from", "ana", "--to", "hermes", "--kind", "report",
                "--state", state, "--project", "auto", "--body", "estado " + state)
        assert r.returncode == 0, r.stderr
        assert st("ana")["state"] == exp and st("ana")["project"] == "auto", st("ana")
        assert st("hermes") == before, "status do destinatario nao pode mudar"
    run(env, "status", "--agent", "ana", "--set", "blocked", "--note", "nota fixa")
    run(env, "send", "--from", "ana", "--to", "hermes", "--kind", "question", "--body", "so heartbeat")
    assert st("ana")["state"] == "blocked" and st("ana")["note"] == "nota fixa", st("ana")
    assert not os.path.exists(os.path.join(tmp, "status", "bia.json"))
    run(env, "inbox", "--agent", "bia")
    assert st("bia")["state"] == "idle", st("bia")
    old = dict(st("bia"), state="working", ts=time.time() - 3600, updated="velho")
    json.dump(old, open(os.path.join(tmp, "status", "bia.json"), "w"))
    run(env, "inbox", "--agent", "bia")
    assert st("bia")["state"] == "working" and st("bia")["ts"] > old["ts"] + 3000, st("bia")
    snap = st("bia")
    run(env, "send", "--from", "bia", "--to", "ana", "--state", "CONCLUIDO", "--body", "x", "--no-auto-status")
    run(env, "inbox", "--agent", "bia", "--no-auto-status")
    run(env, "wait", "--agent", "bia", "--timeout", "0.3", "--interval", "0.1", "--no-auto-status")
    assert st("bia") == snap, st("bia")
    assert not os.path.exists(os.path.join(tmp, "status", "caio.json"))
    run(env, "wait", "--agent", "caio", "--timeout", "0.3", "--interval", "0.1")
    assert st("caio")["state"] == "idle", st("caio")
    print("OK: auto-status (mapa de estados, heartbeat, --no-auto-status, destinatario intocado)")

    # log
    lg = run(env, "log")
    assert lg.returncode == 0 and "oi hermes" in lg.stdout and "ana -> hermes" in lg.stdout, lg.stdout
    lines = lg.stdout.strip().splitlines()
    assert "x" in lines[-1] and "bia -> ana" in lines[-1], lg.stdout  # mais nova por ultimo
    assert len(run(env, "log", "--limit", "2").stdout.strip().splitlines()) == 2
    la = run(env, "log", "--agent", "claude").stdout.strip().splitlines()
    assert la and all("claude" in l for l in la) and not any("ana -> hermes" in l for l in la), la
    assert all("proj=auto" in l for l in run(env, "log", "--project", "auto").stdout.strip().splitlines())
    print("OK: a2a log (feed, --limit, --agent, --project)")

    # painel
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    p = subprocess.Popen([sys.executable, str(A2A), "panel", "--port", str(port)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        base, data = f"http://127.0.0.1:{port}", None
        for _ in range(50):
            try: data = json.load(urllib.request.urlopen(base + "/api/state", timeout=2)); break
            except OSError: time.sleep(0.1)
        assert data, "painel nao respondeu"
        assert {"agents", "messages", "generated"} <= set(data), data.keys()
        assert any(a["agent"] == "ana" and a["state"] == "blocked" for a in data["agents"]), data["agents"]
        assert any(m["body"] == "oi hermes" for m in data["messages"]), data["messages"]
        r = urllib.request.urlopen(base + "/", timeout=2)
        assert r.status == 200 and "Dove" in r.read().decode("utf-8")
    finally:
        p.terminate(); p.wait(timeout=5)
    print("OK: painel web (/api/state e /)")

    # sem BOM: shebang na linha 1
    raw = A2A.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and raw.startswith(b"#!/usr/bin/env python3\n"), raw[:30]
    assert b"\r\n" not in raw
    print("OK: a2a.py sem BOM, shebang na linha 1, LF")

    # onboard
    uenv = dict(env, PYTHONIOENCODING="utf-8")
    ob = subprocess.run([sys.executable, str(A2A), "onboard", "--agent", "codex", "--project", "lagu"],
                        capture_output=True, env=uenv)
    t = ob.stdout.decode("utf-8")
    assert ob.returncode == 0 and "`codex`" in t and "lagu" in t, t
    assert "<seu-nome>" not in t and "<projeto>" not in t and "Claude Code →" not in t, t
    ob = subprocess.run([sys.executable, str(A2A), "onboard", "--agents-md"], capture_output=True, env=uenv)
    t = ob.stdout.decode("utf-8")
    assert ob.returncode == 0 and "Claude Code → `claude`" in t and "<seu-nome>" in t and "<projeto>" in t, t
    assert run(env, "onboard").returncode != 0
    print("OK: a2a onboard (--agent e --agents-md)")

    # install.sh num HOME temporario
    if os.name != "nt":
        h = tempfile.mkdtemp(); ienv = dict(os.environ, HOME=h, A2A_HOME=os.path.join(h, ".a2a"))
        for _ in range(2):  # idempotente
            r = subprocess.run(["bash", str(ROOT / "install.sh")], capture_output=True, text=True, env=ienv)
            assert r.returncode == 0, r.stdout + r.stderr
        link = os.path.join(h, ".local", "bin", "a2a")
        assert os.path.islink(link) and os.path.realpath(link) == str(A2A.resolve()), link
        r = subprocess.run([link, "--help"], capture_output=True, text=True, env=ienv)
        assert r.returncode == 0 and "onboard" in r.stdout, r.stdout + r.stderr
        assert sorted(os.listdir(os.path.join(h, ".a2a", "agents"))) == ["claude", "codex", "hermes"]
        dlink = os.path.join(h, ".local", "bin", "dove")
        assert os.path.islink(dlink) and os.path.realpath(dlink) == str(A2A.resolve()), dlink
        print("OK: install.sh (symlinks a2a e dove, shebang, agentes, idempotente)")

    # install.ps1: checagem estatica (shims .cmd e Git Bash, ASCII puro)
    raw = (ROOT / "install.ps1").read_bytes()
    assert all(b < 128 for b in raw), "install.ps1 tem bytes nao-ASCII"
    txt = raw.decode("ascii")
    for needle in ("a2a.cmd", "#!/bin/sh", "UTF8Encoding($false)", "dove.cmd", "panel --open %*",
                   'Join-Path $bin "dove"', 'panel --open `"`$@`"'):
        assert needle in txt, needle
    print("OK: install.ps1 (estatico: a2a.cmd, dove.cmd, shims Git Bash, ASCII)")

    # install.ps1: checagem de sintaxe se houver pwsh
    import shutil
    if shutil.which("pwsh"):
        ps = ("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
              f"'{ROOT / 'install.ps1'}',[ref]$null,[ref]$e) | Out-Null; if($e){{$e; exit 1}}")
        r = subprocess.run(["pwsh", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        print("OK: install.ps1 (sintaxe)")
    else:
        print("PULADO: install.ps1 (pwsh nao disponivel)")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close(); return port

def req(port, method, path, body=None, headers=None, host=None):
    """Requisicao crua (permite forjar Host/Origin)."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    c.putheader("Host", host or f"127.0.0.1:{port}")
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    hs = dict(headers or {})
    if method == "POST": hs.setdefault("Content-Type", "application/json"); hs["Content-Length"] = str(len(data))
    for k, v in hs.items(): c.putheader(k, v)
    c.endheaders();
    if data: c.send(data)
    r = c.getresponse(); raw = r.read(); c.close()
    try: j = json.loads(raw.decode("utf-8"))
    except ValueError: j = raw.decode("utf-8", "replace")
    return r.status, j

def wait_ping(port, proc=None):
    for _ in range(80):
        try:
            if json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)).get("dove"): return True
        except OSError: time.sleep(0.1)
        if proc is not None and proc.poll() is not None: return False
    return False

def mkrepo(path, branch="main", url=None, gitfile=False):
    os.makedirs(path, exist_ok=True)
    if gitfile:  # worktree: .git e um arquivo apontando para o gitdir real
        real = path + "-gitdir"; os.makedirs(real, exist_ok=True)
        open(os.path.join(path, ".git"), "w").write(f"gitdir: {real}\n"); g = real
    else:
        g = os.path.join(path, ".git"); os.makedirs(g, exist_ok=True)
    open(os.path.join(g, "HEAD"), "w").write(f"ref: refs/heads/{branch}\n")
    cfg = "[core]\n\tbare = false\n"
    if url: cfg += '[remote "upstream"]\n\turl = https://example.com/wrong.git\n[remote "origin"]\n\turl = ' + url + "\n"
    open(os.path.join(g, "config"), "w").write(cfg)

def fase1():
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex", "hermes"): run(env, "join", "--agent", ag)
    st = lambda a: json.load(open(os.path.join(tmp, "status", a + ".json"), encoding="utf-8"))

    # ---- projetos
    pdir = tempfile.mkdtemp()
    for n in ("lagu", "qlink"): os.makedirs(os.path.join(pdir, n))
    assert run(env, "project", "list").stdout.startswith("(nenhum projeto)")
    r = run(env, "project", "add", "lagu", os.path.join(pdir, "lagu")); assert r.returncode == 0, r.stderr
    assert run(env, "project", "add", "qlink", os.path.join(pdir, "qlink")).returncode == 0
    r = run(env, "project", "add", "lagu", os.path.join(pdir, "qlink"))
    assert r.returncode == 1 and "ja" in r.stderr, r.stderr
    assert run(env, "project", "pin", "qlink").returncode == 0
    lines = run(env, "project", "list").stdout.splitlines()
    assert lines[0].startswith("* qlink") and lines[1].startswith("  lagu"), lines
    run(env, "project", "pin", "qlink", "--off")
    assert run(env, "project", "list").stdout.splitlines()[0].startswith("  lagu")
    assert run(env, "project", "remove", "qlink").returncode == 0
    assert run(env, "project", "remove", "qlink").returncode == 1
    pj = json.load(open(os.path.join(tmp, "projects.json"), encoding="utf-8"))
    assert [p["name"] for p in pj] == ["lagu"] and {"name", "path", "pinned", "added"} <= set(pj[0]), pj
    print("OK: projetos (add, remove, pin, list, duplicados)")

    # ---- scan: ~50 repos falsos
    root = tempfile.mkdtemp()
    for i in range(40): mkrepo(os.path.join(root, "clientes", f"repo{i:02d}"), url=f"https://github.com/u/repo{i:02d}.git")
    for i in range(8): mkrepo(os.path.join(root, "a", "b", f"deep{i}"), branch="develop", url=f"git@gitlab.com:u/deep{i}.git")
    mkrepo(os.path.join(root, "a", "b", "c", "toodeep"))                       # nivel 4: fora com --depth 3
    mkrepo(os.path.join(root, "web", "node_modules", "pkg"))                   # ignorado
    mkrepo(os.path.join(root, ".cache", "hidden"))                             # pasta oculta: ignorado
    mkrepo(os.path.join(root, "mono"), url="https://github.com/u/mono.git")
    mkrepo(os.path.join(root, "mono", "packages", "inner"))                    # dentro de repo: nao desce
    mkrepo(os.path.join(root, "wt"), branch="feature/x", gitfile=True)         # .git arquivo
    mkrepo(os.path.join(root, "x", "app")); mkrepo(os.path.join(root, "y", "app"))  # colisao de nome
    os.makedirs(os.path.join(root, "clientes", "repo00", "node_modules", "z", ".git"))
    t0 = time.time(); r = run(env, "project", "scan", root, "--depth", "3"); dt = time.time() - t0
    assert r.returncode == 0, r.stderr
    out = r.stdout
    found = [l for l in out.splitlines() if l and not l.startswith(tuple("0123456789"))]
    names = [l.split()[0] for l in found]
    assert len(found) == 40 + 8 + 1 + 1 + 2, (len(found), out[-500:])
    assert "toodeep" not in names and "pkg" not in names and "hidden" not in names and "inner" not in names, names
    assert dt < 3, f"scan lento: {dt:.2f}s"
    sys.path.insert(0, str(ROOT)); os.environ["A2A_HOME"] = tmp
    import importlib; a2a = importlib.import_module("a2a")
    repos = {r_["path"]: r_ for r_ in a2a.scan_repos(root, 3)}
    rr = repos[os.path.join(root, "clientes", "repo07")]
    assert rr["branch"] == "main" and rr["remote"] == "https://github.com/u/repo07.git" and rr["host"] == "github.com", rr
    rd = repos[os.path.join(root, "a", "b", "deep3")]
    assert rd["branch"] == "develop" and rd["host"] == "gitlab.com" and rd["last_activity"] > 0, rd
    assert repos[os.path.join(root, "wt")]["branch"] == "feature/x"
    assert len(a2a.scan_repos(root, 4)) == len(repos) + 1  # --depth 4 acha o toodeep
    t0 = time.time(); a2a.scan_repos(root, 3); assert time.time() - t0 < 1.0
    r = run(env, "project", "scan", root, "--add"); assert r.returncode == 0, r.stderr
    pnames = sorted(p["name"] for p in json.load(open(os.path.join(tmp, "projects.json"), encoding="utf-8")))
    assert "app" in pnames and ("app-x" in pnames or "app-y" in pnames), pnames
    assert len(pnames) == 1 + len(found), len(pnames)
    r = run(env, "project", "scan", root, "--add"); assert "0 projetos adicionados" in r.stdout, r.stdout
    assert json.load(open(os.path.join(tmp, "config.json"), encoding="utf-8"))["scan_root"] == os.path.abspath(root)
    print(f"OK: project scan ({len(found)} repos em {dt:.2f}s; ignora node_modules/ocultas, nao desce em repo, --add com colisao)")

    # ---- status --context/--model
    r = run(env, "status", "--agent", "claude", "--set", "working", "--project", "lagu", "--note", "rev", "--context", "63", "--model", "opus")
    assert r.returncode == 0, r.stderr
    assert st("claude")["context"] == 63 and st("claude")["model"] == "opus", st("claude")
    line = next(l for l in run(env, "status").stdout.splitlines() if l.startswith("claude"))
    assert "ctx 63%" in line and "rev" in line, line
    assert run(env, "status", "--agent", "claude", "--context", "101").returncode == 2
    run(env, "status", "--agent", "claude", "--set", "blocked", "--note", "x")
    assert st("claude")["context"] == 63 and st("claude")["state"] == "blocked"  # contexto persiste
    run(env, "status", "--agent", "codex", "--context", "91")
    assert st("codex")["context"] == 91 and st("codex")["state"] == "idle", st("codex")
    print("OK: status --context/--model (gravado, quadro mostra ctx, validacao 0-100)")

    # ---- missoes
    r = run(env, "mission", "new", "--project", "lagu", "--title", "Checkout pronto", "--desc", "conferir tudo")
    assert r.returncode == 0, r.stderr
    mid = re.search(r"missao (\w+) criada", r.stdout).group(1)
    m = json.load(open(os.path.join(tmp, "missions", mid + ".json"), encoding="utf-8"))
    assert m["agents"] == ["claude", "codex", "hermes"] and m["created_by"] == "luiz" and m["human"] is None, m
    msgs = [json.load(open(f, encoding="utf-8")) for f in sorted(pathlib.Path(tmp, "bus").glob("*.json"))]
    tasks = [x for x in msgs if x["task_id"] == mid and x["kind"] == "task"]
    assert sorted(x["to"] for x in tasks) == ["claude", "codex", "hermes"], tasks
    assert all("Checkout pronto" in x["body"] and x["from"] == "luiz" and x["project"] == "lagu" for x in tasks)
    assert not os.path.exists(os.path.join(tmp, "status", "luiz.json")), "humano nao vira agente no quadro"
    show = lambda: run(env, "mission", "list").stdout
    assert "aberta" in show() and "0/3" in show()
    r = run(env, "mission", "approve", mid, "--agent", "claude", "--evidence", "   ")
    assert r.returncode == 1 and "evidence" in r.stderr, r.stderr
    assert run(env, "mission", "approve", mid, "--agent", "claude").returncode == 2  # argparse: obrigatorio
    r = run(env, "mission", "approve", mid, "--agent", "intruso", "--evidence", "x")
    assert r.returncode == 1 and "nao participa" in r.stderr, r.stderr
    r = run(env, "mission", "done", mid); assert r.returncode == 1 and "aval de todos" in r.stderr, r.stderr
    assert run(env, "mission", "approve", mid, "--agent", "claude", "--evidence", "testes 212/212").returncode == 0
    assert "aberta" in show() and "1/3" in show()
    rep = [json.load(open(f, encoding="utf-8")) for f in sorted(pathlib.Path(tmp, "bus").glob("*.json"))]
    rep = [x for x in rep if x["task_id"] == mid and x["kind"] == "report"]
    assert rep and rep[-1]["to"] == "luiz" and rep[-1]["state"] == "CONCLUIDO" and rep[-1]["from"] == "claude", rep
    assert rep[-1]["in_reply_to"] == next(t["msg_id"] for t in tasks if t["to"] == "claude")
    r = run(env, "mission", "reject", mid, "--agent", "codex", "--reason", "falta teste de frete")
    assert r.returncode == 0 and "reprovada" in r.stdout, r.stdout
    assert "reprovada" in show()
    assert run(env, "mission", "done", mid).returncode == 1
    rep = [json.load(open(f, encoding="utf-8")) for f in sorted(pathlib.Path(tmp, "bus").glob("*.json"))]
    assert any(x["task_id"] == mid and x["state"] == "BLOQUEADO" and x["from"] == "codex" for x in rep)
    run(env, "mission", "approve", mid, "--agent", "codex", "--evidence", "frete testado")  # ultimo veredito vale
    assert "aberta" in show() and "2/3" in show(), show()
    run(env, "mission", "approve", mid, "--agent", "hermes", "--evidence", "e2e ok")
    assert "aval_completo" in show() and "3/3" in show(), show()
    sh = run(env, "mission", "show", mid).stdout
    assert "frete testado" in sh and "aval_completo" in sh, sh
    assert run(env, "mission", "done", mid, "--from", "luiz").returncode == 0
    assert "concluida" in show(), show()
    assert run(env, "mission", "approve", mid, "--agent", "hermes", "--evidence", "x").returncode == 1
    assert run(env, "mission", "new", "--project", "dove", "--title", "So dois", "--agents", "claude,hermes").returncode == 0
    assert "dove" in run(env, "mission", "list", "--project", "dove").stdout
    assert "lagu" not in run(env, "mission", "list", "--project", "dove").stdout
    print("OK: missoes (tasks aos participantes, evidencia obrigatoria, nao-participante, ultimo veredito, status, done)")

    # ---- summary
    run(env, "send", "--from", "luiz", "--to", "hermes", "--project", "sumtest", "--kind", "task", "--body", "tarefa resumo X", "--no-auto-status")
    tid = [json.load(open(f, encoding="utf-8")) for f in sorted(pathlib.Path(tmp, "bus").glob("*.json"))]
    tid = next(x["msg_id"] for x in tid if x["body"] == "tarefa resumo X")
    s1 = run(env, "summary", "--project", "sumtest").stdout
    assert "Tarefas abertas: 1" in s1 and "tarefa resumo X" in s1, s1
    run(env, "send", "--from", "hermes", "--to", "luiz", "--project", "sumtest", "--reply-to", tid, "--kind", "report", "--state", "EM_EXECUCAO", "--body", "indo")
    assert "Tarefas abertas: 1" in run(env, "summary", "--project", "sumtest").stdout
    run(env, "send", "--from", "hermes", "--to", "luiz", "--project", "sumtest", "--reply-to", tid, "--kind", "report", "--state", "CONCLUIDO", "--body", "feito resumo")
    s2 = run(env, "summary", "--project", "sumtest").stdout
    assert "Tarefas abertas: 0" in s2 and "feito resumo" in s2, s2
    g = run(env, "summary").stdout
    assert "Contexto alto (>=80%): codex 91%" in g and "concluida 1" in g, g
    print("OK: summary (tarefa some com CONCLUIDO, contexto alto, missoes)")

    # ---- API do painel
    port = free_port()
    p = subprocess.Popen([sys.executable, str(A2A), "panel", "--port", str(port)], env=dict(env, DOVE_NO_BROWSER="1"),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert wait_ping(port, p), "painel nao respondeu"
        code, stj = req(port, "GET", "/api/state")
        assert code == 200 and {"agents", "messages", "projects", "missions", "summary", "registered"} <= set(stj), stj
        assert any(a["agent"] == "codex" and a["context"] == 91 for a in stj["agents"])
        assert any(m["status"] == "concluida" for m in stj["missions"]) and "lagu" in stj["summary"]["projects"]
        code, html = req(port, "GET", "/")
        tok = re.search(r'name="dove-token" content="([^"]+)"', html).group(1)
        assert code == 200 and tok and tok != "__DOVE_TOKEN__"
        body = {"to": "claude", "project": "lagu", "kind": "task", "body": "via painel ✓"}
        assert req(port, "POST", "/api/send", body)[0] == 403                                   # sem token
        assert req(port, "POST", "/api/send", body, {"X-Dove-Token": "errado"})[0] == 403
        assert req(port, "GET", "/api/state", host="evil.example:%d" % port)[0] == 403         # DNS rebinding
        assert req(port, "POST", "/api/send", body, {"X-Dove-Token": tok}, host="evil.example")[0] == 403
        assert req(port, "POST", "/api/send", body, {"X-Dove-Token": tok, "Origin": "http://evil.example"})[0] == 403
        assert req(port, "POST", "/api/send", body, {"X-Dove-Token": tok, "Content-Type": "text/plain"})[0] == 415
        assert req(port, "POST", "/api/send", {"body": "x" * 70000}, {"X-Dove-Token": tok})[0] == 413
        assert req(port, "GET", f"/api/scan?root={root}")[0] == 403                             # scan exige token
        code, j = req(port, "POST", "/api/send", body, {"X-Dove-Token": tok, "Origin": f"http://127.0.0.1:{port}"})
        assert code == 200 and j["ok"] and j["message"]["from"] == "luiz", j
        assert "via painel ✓" in run(env, "inbox", "--agent", "claude", "--no-auto-status").stdout
        code, j = req(port, "POST", "/api/send", {"to": "ninguem", "body": "x"}, {"X-Dove-Token": tok})
        assert code == 400 and "desconhecido" in j["error"], j
        assert req(port, "POST", "/api/mission/verdict", {"id": "x"}, {"X-Dove-Token": tok})[0] == 404
        assert req(port, "GET", "/api/debug/raise")[0] == 404                                  # rota de teste so com env
        assert req(port, "GET", "/api/state", host=f"localhost:{port}")[0] == 200
        T = {"X-Dove-Token": tok}
        code, j = req(port, "GET", f"/api/scan?root={urllib.request.quote(root)}&depth=3", None, T)
        assert code == 200 and len(j["repos"]) == len(found) and all(x["registered"] for x in j["repos"]), (code, str(j)[:300])
        code, j = req(port, "POST", "/api/project/add", {"name": "novo", "path": pdir}, T); assert code == 200, j
        code, j = req(port, "POST", "/api/project/pin", {"name": "novo", "pinned": True}, T); assert j["project"]["pinned"]
        assert req(port, "GET", "/api/state")[1]["projects"][0]["name"] == "novo"
        code, j = req(port, "POST", "/api/project/remove", {"name": "novo"}, T); assert code == 200, j
        code, j = req(port, "POST", "/api/mission/new", {"project": "lagu", "title": "Pelo painel", "agents": ["claude", "codex"]}, T)
        assert code == 200 and j["mission"]["status"] == "aberta" and j["mission"]["created_by"] == "luiz", j
        mid2 = j["mission"]["id"]
        code, j = req(port, "POST", "/api/mission/done", {"id": mid2}, T)
        assert code == 400 and "aval de todos" in j["error"], j
        for ag in ("claude", "codex"): run(env, "mission", "approve", mid2, "--agent", ag, "--evidence", "ok " + ag)
        ms = {m["id"]: m for m in req(port, "GET", "/api/state")[1]["missions"]}
        assert ms[mid2]["status"] == "aval_completo" and ms[mid2]["approved"] == 2, ms[mid2]
        code, j = req(port, "POST", "/api/mission/done", {"id": mid2}, T)
        assert code == 200 and j["mission"]["status"] == "concluida" and j["mission"]["human"]["by"] == "luiz", j
    finally:
        p.terminate(); p.wait(timeout=5)
    print("OK: API do painel (token, Host, Origin, Content-Type, limite, send, projetos, scan, missao new/done)")

    # ---- comando dove (symlink) e --open com painel ja rodando
    if os.name != "nt":
        d = tempfile.mkdtemp(); dove = os.path.join(d, "dove"); os.symlink(str(A2A), dove)
        port = free_port()
        p = subprocess.Popen([dove, "--port", str(port)], env=dict(env, DOVE_NO_BROWSER="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert wait_ping(port, p), "dove nao serviu /api/ping"
            r = subprocess.run([dove, "--port", str(port)], env=dict(env, DOVE_NO_BROWSER="1"),
                               capture_output=True, text=True, timeout=10)
            assert r.returncode == 0 and "ja esta rodando" in r.stdout, r.stdout + r.stderr
        finally:
            p.terminate(); p.wait(timeout=5)
        print("OK: comando dove (symlink -> panel --open; segunda chamada so abre o navegador)")

    # ---- onboard com contexto e missoes
    t = run(env, "onboard", "--agent", "codex").stdout
    assert "--context <0-100>" in t and "a2a mission approve <id> --agent codex --evidence" in t, t

def raw_post(port, path, data, headers):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("POST", path, skip_host=True, skip_accept_encoding=True)
    c.putheader("Host", f"127.0.0.1:{port}")
    for k, v in dict(headers, **{"Content-Length": str(len(data))}).items(): c.putheader(k, v)
    c.endheaders(); c.send(data)
    r = c.getresponse(); raw = r.read(); c.close()
    return r.status, json.loads(raw.decode("utf-8"))

def robustez():
    """Painel nunca derruba a conexao; add/scan robustos (Windows: aspas, maiusculas, junctions, permissoes)."""
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8", DOVE_NO_BROWSER="1", DOVE_TEST_RAISE="1")
    sys.path.insert(0, str(ROOT)); os.environ["A2A_HOME"] = tmp
    import importlib; a2a = importlib.import_module("a2a")

    # ---- funcoes puras: aspas, nomes e caminhos no Windows simulado
    d = tempfile.mkdtemp()
    assert a2a.clean_path(f'"{d}"') == d and a2a.clean_path(f"  '{d}'  ") == d and a2a.clean_path(f'" {d}/ "') == d
    assert a2a.clean_path("  ") == ""
    assert a2a.name_taken("Dove", ["lagu", "dove"], windows=True)
    assert not a2a.name_taken("Dove", ["lagu", "dove"], windows=False)
    assert a2a.name_taken("dove", ["dove"], windows=False)
    assert a2a.path_key("C:/Users/Dell/dove/", windows=True) == a2a.path_key("c:\\users\\DELL\\Dove", windows=True)
    assert a2a.unique_name("App", "/x/y/App", ["app"]) == "App"  # Linux: diferencia maiusculas
    real_isw = a2a.is_windows
    try:
        a2a.is_windows = lambda: True  # Windows simulado: "LAGU" colide com "lagu" ja registrado
        a2a.project_add("x-tmp", d); a2a.project_remove("x-tmp")
        try: a2a.project_add("X-TMP", d); a2a.project_add("x-tmp", tempfile.mkdtemp()); assert False
        except a2a.DoveError as e: assert "ja existe" in str(e), e
        assert a2a.project_add("x-tmp", tempfile.mkdtemp(), auto_name=True)["name"] != "x-tmp"
    finally:
        a2a.is_windows = real_isw
    print("OK: clean_path (aspas/espacos), nome duplicado sem maiusculas no Windows (name_taken/path_key)")

    # ---- write_json: replace bloqueado (antivirus/leitor no Windows) nao derruba
    real_replace, real_sleep = os.replace, time.sleep
    def busy(*x): raise PermissionError(13, "arquivo em uso")
    try:
        os.replace, a2a.time.sleep = busy, (lambda s: None)
        tgt = os.path.join(d, "x.json"); a2a.write_json(tgt, {"caminho": "C:\\Usuários\\João"})
    finally:
        os.replace, a2a.time.sleep = real_replace, real_sleep
    assert json.load(open(tgt, encoding="utf-8")) == {"caminho": "C:\\Usuários\\João"}
    assert not [f for f in os.listdir(d) if f.endswith(".tmp")], os.listdir(d)
    print("OK: write_json com os.replace bloqueado (cai para gravacao direta em UTF-8, sem lixo .tmp)")

    # ---- scan: pasta ilegivel, symlink em loop, link para fora, .git ilegivel
    root = tempfile.mkdtemp()
    mkrepo(os.path.join(root, "ok", "r1"), url="https://github.com/u/r1.git")
    mkrepo(os.path.join(root, "trancada", "segredo"))
    os.makedirs(os.path.join(root, "loop"))
    os.symlink(os.path.join(root, "loop"), os.path.join(root, "loop", "eu"))      # loop
    os.symlink(root, os.path.join(root, "ok", "raiz"))                            # volta para a raiz
    os.symlink(os.path.join(root, "ok", "r1"), os.path.join(root, "atalho"))      # link para repo: nao segue
    mkrepo(os.path.join(root, "estranho"))
    open(os.path.join(root, "estranho", ".git", "config"), "wb").write(b'[remote "origin"]\n\turl = https://h\xe9.com/x\n')
    os.chmod(os.path.join(root, "trancada"), 0)
    try:
        t0 = time.time(); repos = a2a.scan_repos(root, 6); dt = time.time() - t0
    finally:
        os.chmod(os.path.join(root, "trancada"), 0o755)
    paths = sorted(r["path"] for r in repos)
    assert dt < 3, dt
    assert os.path.join(root, "ok", "r1") in paths and os.path.join(root, "estranho") in paths, paths
    assert len(paths) == len(set(paths)) and not any("atalho" in p or "raiz" in p or "eu" in p.split(os.sep) for p in paths), paths
    if os.geteuid() != 0: assert os.path.join(root, "trancada", "segredo") not in paths, paths
    # root le tudo: simula PermissionError na pasta trancada
    real_scandir = os.scandir
    def fake_scandir(p="."):
        if os.path.basename(str(p)) == "trancada": raise PermissionError(13, "Acesso negado", str(p))
        return real_scandir(p)
    try:
        a2a.os.scandir = fake_scandir; repos = a2a.scan_repos(root, 6)
    finally:
        a2a.os.scandir = real_scandir
    paths = [r["path"] for r in repos]
    assert os.path.join(root, "trancada", "segredo") not in paths and os.path.join(root, "ok", "r1") in paths, paths
    try: a2a.scan_repos(os.path.join(root, "nao-existe")); assert False
    except a2a.DoveError as e: assert "nao encontrada" in str(e)
    try: a2a.scan_repos(f'"{os.path.join(root, "ok")}"', 2)  # aspas coladas
    except a2a.DoveError as e: assert False, e
    print(f"OK: scan pula pasta sem permissao, symlink em loop e links ({len(repos)} repos em {dt:.2f}s)")

    # ---- painel: 400 com mensagem, aspas, 500 JSON, servidor continua de pe
    port = free_port()
    p = subprocess.Popen([sys.executable, str(A2A), "panel", "--port", str(port)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert wait_ping(port, p), "painel nao respondeu"
        tok = re.search(r'name="dove-token" content="([^"]+)"', req(port, "GET", "/")[1]).group(1)
        T = {"X-Dove-Token": tok}
        code, j = req(port, "POST", "/api/project/add", {"path": os.path.join(root, "nao-existe")}, T)
        assert code == 400 and "nao existe" in j["error"] and j["ok"] is False, (code, j)
        f = os.path.join(root, "arquivo.txt"); open(f, "w").write("x")
        code, j = req(port, "POST", "/api/project/add", {"path": f}, T)
        assert code == 400 and "nao e uma pasta" in j["error"], (code, j)
        code, j = req(port, "POST", "/api/project/add", {"path": "   "}, T)
        assert code == 400 and "caminho" in j["error"], (code, j)
        dove_dir = os.path.join(root, "ok", "r1")
        code, j = req(port, "POST", "/api/project/add", {"path": f'"{dove_dir}"'}, T)
        assert code == 200 and j["project"]["path"] == dove_dir and j["project"]["name"] == "r1", (code, j)
        code, j = req(port, "POST", "/api/project/add", {"path": dove_dir + os.sep}, T)
        assert code == 400 and "ja esta registrada" in j["error"], (code, j)
        code, j = req(port, "POST", "/api/project/add", {"name": "r1", "path": os.path.join(root, "estranho")}, T)
        assert code == 400 and "ja existe" in j["error"], (code, j)
        code, j = raw_post(port, "/api/project/add", b"{nao e json", dict(T, **{"Content-Type": "application/json"}))
        assert code == 400 and "JSON invalido" in j["error"], (code, j)
        code, j = req(port, "POST", "/api/project/remove", {"name": ""}, T)
        assert code == 400 and "nome" in j["error"], (code, j)
        code, j = req(port, "POST", "/api/project/remove", {"name": "fantasma"}, T)
        assert code == 400 and "nao encontrado" in j["error"], (code, j)
        # erro inesperado no handler -> 500 JSON (nao derruba a conexao)
        code, j = req(port, "GET", "/api/debug/raise")
        assert code == 500 and j["ok"] is False and j["error"].startswith("RuntimeError: falha de teste"), (code, j)
        code, j = req(port, "POST", "/api/debug/raise", {}, T)
        assert code == 500 and j["error"].startswith("RuntimeError"), (code, j)
        # token errado com corpo grande: resposta 403 chega (corpo drenado antes de responder)
        code, j = raw_post(port, "/api/send", b"{" + b" " * 60000 + b"}", {"X-Dove-Token": "x", "Content-Type": "application/json"})
        assert code == 403 and "token" in j["error"], (code, j)
        code, j = req(port, "GET", f"/api/scan?root={urllib.request.quote(chr(34) + root + chr(34))}&depth=6", None, T)
        assert code == 200 and j["root"] == root and any(r["registered"] for r in j["repos"]), (code, str(j)[:300])
        code, j = req(port, "GET", f"/api/scan?root={urllib.request.quote(os.path.join(root, 'nada'))}", None, T)
        assert code == 400 and "nao encontrada" in j["error"], (code, j)
        assert wait_ping(port, p) and p.poll() is None, "servidor caiu depois dos erros"
        code, st = req(port, "GET", "/api/state")
        assert code == 200 and st["config"]["scan_root"] == root and [x["name"] for x in st["projects"]] == ["r1"], st["config"]
    finally:
        p.terminate(); _, err = p.communicate(timeout=5)
    assert re.search(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] erro em GET /api/debug/raise", err, re.M), err
    assert "Traceback" in err and "RuntimeError: falha de teste" in err, err
    print("OK: painel robusto (400 com mensagem em add/remove/scan, aspas, JSON invalido, 500 JSON + traceback, segue no ar)")

def start_panel(env, port):
    p = subprocess.Popen([sys.executable, str(A2A), "panel", "--port", str(port)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert wait_ping(port, p), "painel nao respondeu"
    tok = re.search(r'name="dove-token" content="([^"]+)"', req(port, "GET", "/")[1]).group(1)
    return p, {"X-Dove-Token": tok}

def fase2():
    """Versao/doctor, navegador de pastas, abrir pasta, agentes com metadados, paginacao de mensagens."""
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8", DOVE_NO_BROWSER="1", DOVE_FAKE_OPEN="1")
    sys.path.insert(0, str(ROOT)); os.environ["A2A_HOME"] = tmp
    import importlib; a2a = importlib.import_module("a2a")
    for k, v in (("HOME", tmp), ("BUS", os.path.join(tmp, "bus")), ("CURSOR", os.path.join(tmp, "cursor")),
                 ("AGENTS", os.path.join(tmp, "agents")), ("STATUS", os.path.join(tmp, "status")),
                 ("MISSIONS", os.path.join(tmp, "missions")), ("PROJECTS", os.path.join(tmp, "projects.json")),
                 ("CONFIG", os.path.join(tmp, "config.json"))):
        setattr(a2a, k, v)  # o modulo pode ter sido importado por outro teste com outro A2A_HOME

    # ---- --version e doctor
    r = run(env, "--version"); assert r.returncode == 0 and r.stdout.strip() == "dove " + a2a.DOVE_VERSION, r.stdout
    run(env, "init"); run(env, "join", "--agent", "claude")
    r = run(env, "doctor", "--port", str(free_port()))
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "OK    versao: dove " + a2a.DOVE_VERSION in out and "OK    A2A_HOME:" in out and "gravavel" in out, out
    assert re.search(r"^OK    porta: porta \d+ livre", out, re.M) and "agents: 1 arquivo" in out, out
    assert "OK    pagina:" in out, out  # ui/index.html com UI_VERSION igual ao DOVE_VERSION
    assert not re.search(r"^ERRO", out, re.M), out
    print("OK: --version e doctor (linhas OK, porta livre, pagina na mesma versao)")

    # ---- agentes com metadados (CLI)
    r = run(env, "join", "--agent", "codex", "--type", "codex", "--model", "gpt-5"); assert r.returncode == 0, r.stderr
    meta = json.load(open(os.path.join(tmp, "agents", "codex"), encoding="utf-8"))
    assert meta["type"] == "codex" and meta["model"] == "gpt-5" and meta["added"], meta
    run(env, "join", "--agent", "codex")  # re-join sem flags nao apaga metadados
    assert json.load(open(os.path.join(tmp, "agents", "codex"), encoding="utf-8"))["model"] == "gpt-5"
    assert os.path.getsize(os.path.join(tmp, "agents", "claude")) == 0  # legado: arquivo vazio
    assert a2a.agent_meta("claude") == {} and a2a.agent_meta("codex")["type"] == "codex"
    assert run(env, "join", "--agent", "Mal Nome").returncode == 1
    assert run(env, "join", "--agent", "../x").returncode == 1
    assert run(env, "join", "--agent", "x", "--type", "robo").returncode == 2
    assert "claude" in run(env, "agents").stdout.split() and "codex" in run(env, "agents").stdout.split()
    run(env, "send", "--from", "codex", "--to", "claude", "--body", "msg do codex")
    assert os.path.exists(os.path.join(tmp, "status", "codex.json"))
    r = run(env, "leave", "--agent", "codex"); assert r.returncode == 0, r.stderr
    assert not os.path.exists(os.path.join(tmp, "agents", "codex")) and not os.path.exists(os.path.join(tmp, "status", "codex.json"))
    assert "msg do codex" in run(env, "log").stdout  # historico fica
    assert run(env, "leave", "--agent", "codex").returncode == 1
    print("OK: join --type/--model (JSON em agents/<nome>), legado vazio, validacao de nome, leave mantem mensagens")

    # ---- arvore de pastas para o navegador
    root = tempfile.mkdtemp()
    mkrepo(os.path.join(root, "lagu"), branch="dev", url="https://github.com/u/lagu.git")
    open(os.path.join(root, "lagu", "AGENTS.md"), "w").write("# x")
    mkrepo(os.path.join(root, "qlink"))
    os.makedirs(os.path.join(root, "docs", "sub")); os.makedirs(os.path.join(root, ".oculta")); os.makedirs(os.path.join(root, "$Recycle"))
    open(os.path.join(root, "arquivo.txt"), "w").write("x")
    os.makedirs(os.path.join(root, "trancada"))
    os.makedirs(os.path.join(root, "loop")); os.symlink(os.path.join(root, "loop"), os.path.join(root, "loop", "eu"))
    os.symlink(os.path.join(root, "nada"), os.path.join(root, "quebrado"))
    os.symlink(os.path.join(root, "zz1"), os.path.join(root, "zz2")); os.symlink(os.path.join(root, "zz2"), os.path.join(root, "zz1"))
    l = a2a.fs_list(root)
    names = [e["name"] for e in l["entries"]]
    assert names == ["docs", "lagu", "loop", "qlink", "trancada"], names  # so pastas, ordenadas, sem ocultas/$/arquivos/links quebrados
    lg = next(e for e in l["entries"] if e["name"] == "lagu")
    assert lg["is_repo"] and lg["branch"] == "dev" and lg["has_agents_md"] and lg["path"] == os.path.join(root, "lagu"), lg
    assert not next(e for e in l["entries"] if e["name"] == "docs")["is_repo"]
    assert l["path"] == root and l["parent"] == os.path.dirname(root), l
    eu = a2a.fs_list(os.path.join(root, "loop"))["entries"]  # link para a propria pasta: lista uma camada, sem recursao
    assert [(e["name"], e["link"]) for e in eu] == [("eu", True)], eu
    real_scandir = os.scandir
    def fake_scandir(p="."):
        if os.path.basename(str(p)) == "trancada": raise PermissionError(13, "Acesso negado", str(p))
        return real_scandir(p)
    try:
        a2a.os.scandir = fake_scandir
        try: a2a.fs_list(os.path.join(root, "trancada")); assert False
        except a2a.DoveError as e: assert "sem permissao" in str(e), e
    finally:
        a2a.os.scandir = real_scandir
    try: a2a.fs_list(os.path.join(root, "nada")); assert False
    except a2a.DoveError as e: assert "nao encontrada" in str(e)
    try: a2a.fs_list(os.path.join(root, "arquivo.txt")); assert False
    except a2a.DoveError as e: assert "nao e uma pasta" in str(e)
    real_max = a2a.FS_MAX
    try:
        a2a.FS_MAX = 2; t = a2a.fs_list(root); assert len(t["entries"]) == 2 and t["truncated"], t
    finally:
        a2a.FS_MAX = real_max
    print("OK: fs_list (so pastas, ordenado, ocultas/$ fora, repo+branch+AGENTS.md, link em loop/quebrado, sem permissao, limite)")

    # ---- API: fs/list, project/open, project/info, agentes, paginacao, doctor
    for i in range(25):
        run(env, "send", "--from", "claude", "--to", "luiz", "--project", "pg" if i % 2 else "outro", "--body", f"pagina {i:02d}", "--no-auto-status")
    port = free_port()
    p, T = start_panel(env, port)
    try:
        code, j = req(port, "GET", "/api/ping"); assert j == {"dove": True, "version": a2a.DOVE_VERSION}, j
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5); c.request("GET", "/"); r = c.getresponse()
        html = r.read().decode("utf-8"); c.close()
        assert r.getheader("Cache-Control") == "no-store" and a2a.DOVE_VERSION in html and "__DOVE_SERVER_VERSION__" not in html
        # rotas novas exigem token (e Host)
        q = urllib.request.quote
        for path in ("/api/doctor", f"/api/fs/list?path={q(root)}", "/api/fs/list", "/api/project/info?name=x", "/api/onboard?agent=claude"):
            assert req(port, "GET", path)[0] == 403, path
            assert req(port, "GET", path, None, {"X-Dove-Token": "errado"})[0] == 403, path
            assert req(port, "GET", path, None, T, host="evil.example")[0] == 403, path
        for path, body in (("/api/project/open", {"name": "x"}), ("/api/agent/add", {"name": "x"}), ("/api/agent/remove", {"name": "claude"})):
            assert req(port, "POST", path, body)[0] == 403, path
            assert req(port, "POST", path, body, dict(T, Origin="http://evil.example"))[0] == 403, path
        code, j = req(port, "GET", "/api/doctor", None, T)
        assert code == 200 and "OK    versao: dove" in j["text"] and any(x["check"] == "porta" and "este painel" in x["detail"] for x in j["checks"]), j
        code, j = req(port, "GET", f"/api/fs/list?path={q(root)}", None, T)
        assert code == 200 and [e["name"] for e in j["entries"]] == ["docs", "lagu", "loop", "qlink", "trancada"], j
        code, j = req(port, "GET", "/api/fs/list", None, T)
        assert code == 200 and j["path"] == "" and j["entries"] == [] and any(x["kind"] == "home" for x in j["places"]), j
        assert any(x["kind"] == "recent" and x["path"] == root for x in j["places"]), j["places"]  # ultima pasta lembrada
        code, j = req(port, "GET", f"/api/fs/list?path={q(os.path.join(root, 'nada'))}", None, T)
        assert code == 400 and "nao encontrada" in j["error"], j
        # adicionar pelo navegador: a pasta vira "ja adicionado"
        code, j = req(port, "POST", "/api/project/add", {"name": "lagu", "path": os.path.join(root, "lagu")}, T); assert code == 200, j
        code, j = req(port, "GET", f"/api/fs/list?path={q(root)}", None, T)
        assert next(e for e in j["entries"] if e["name"] == "lagu")["project"] == "lagu", j
        req(port, "GET", f"/api/fs/list?path={q(os.path.join(root, 'docs'))}", None, T)  # ultima pasta passa a ser outra
        code, j = req(port, "GET", "/api/fs/list", None, T)
        assert any(x["kind"] == "projects" and x["path"] == root for x in j["places"]), j["places"]  # pai dos projetos
        code, j = req(port, "GET", "/api/project/info?name=lagu", None, T)
        i = j["info"]
        assert code == 200 and i["branch"] == "dev" and i["host"] == "github.com" and i["has_agents_md"] and i["exists"], j
        assert req(port, "GET", "/api/project/info?name=fantasma", None, T)[0] == 400
        # abrir pasta: so projeto registrado; DOVE_FAKE_OPEN devolve o caminho sem abrir nada
        code, j = req(port, "POST", "/api/project/open", {"name": "lagu"}, T)
        assert code == 200 and j["path"] == os.path.join(root, "lagu"), j
        for bad in ({"name": "fantasma"}, {"name": ""}, {"path": root}, {"name": root}):
            code, j = req(port, "POST", "/api/project/open", bad, T); assert code == 400 and "nao encontrado" in j["error"], (bad, j)
        sumiu = os.path.join(root, "sumiu"); os.makedirs(sumiu)
        req(port, "POST", "/api/project/add", {"name": "sumiu", "path": sumiu}, T); os.rmdir(sumiu)
        code, j = req(port, "POST", "/api/project/open", {"name": "sumiu"}, T); assert code == 400 and "nao existe" in j["error"], j
        # agentes pelo painel
        code, j = req(port, "POST", "/api/agent/add", {"name": "hermes", "type": "hermes", "model": "h-1", "note": "infra", "project": "lagu"}, T)
        assert code == 200 and j["agent"]["name"] == "hermes" and "`hermes`" in j["onboard"] and "--project lagu" in j["onboard"], j
        meta = json.load(open(os.path.join(tmp, "agents", "hermes"), encoding="utf-8"))
        assert meta["type"] == "hermes" and meta["model"] == "h-1" and meta["note"] == "infra", meta
        code, j = req(port, "POST", "/api/agent/add", {"name": "hermes"}, T); assert code == 400 and "ja existe" in j["error"], j
        for bad in ("Hermes", "-x", "a" * 33, "a b", "../etc", "", "luiz"):
            code, j = req(port, "POST", "/api/agent/add", {"name": bad}, T); assert code == 400, (bad, j)
        code, j = req(port, "POST", "/api/agent/add", {"name": "novo", "type": "robo"}, T); assert code == 400 and "tipo" in j["error"], j
        code, j = req(port, "POST", "/api/agent/add", {"name": "simples"}, T); assert code == 200 and "<projeto>" in j["onboard"], j
        st = req(port, "GET", "/api/state")[1]
        assert "hermes" in st["registered"] and st["agent_meta"]["hermes"]["model"] == "h-1" and st["agent_meta"]["claude"] == {}, st["agent_meta"]
        assert st["version"] == a2a.DOVE_VERSION
        code, j = req(port, "GET", "/api/onboard?agent=hermes&project=lagu", None, T); assert code == 200 and "`hermes`" in j["text"], j
        code, j = req(port, "GET", "/api/onboard", None, T); assert code == 200 and "<seu-nome>" in j["text"], j
        run(env, "status", "--agent", "hermes", "--set", "working")
        run(env, "send", "--from", "hermes", "--to", "luiz", "--body", "historico do hermes", "--no-auto-status")
        code, j = req(port, "POST", "/api/agent/remove", {"name": "hermes"}, T); assert code == 200, j
        assert not os.path.exists(os.path.join(tmp, "agents", "hermes")) and not os.path.exists(os.path.join(tmp, "status", "hermes.json"))
        st = req(port, "GET", "/api/state")[1]
        assert "hermes" not in st["registered"] and not any(a["agent"] == "hermes" for a in st["agents"])
        assert any(m["body"] == "historico do hermes" for m in st["messages"])
        assert req(port, "POST", "/api/agent/remove", {"name": "hermes"}, T)[0] == 400
        # paginacao
        st = req(port, "GET", "/api/state?project=pg&limit=5")[1]
        assert [m["body"] for m in st["messages"]] == [f"pagina {i:02d}" for i in (15, 17, 19, 21, 23)], st["messages"]
        assert st["messages_total"] == 12 and st["messages_has_more"] and st["messages_project"] == "pg", st
        code, j = req(port, "GET", f"/api/messages?project=pg&limit=5&before={st['messages'][0]['msg_id']}")
        assert code == 200 and [m["body"] for m in j["messages"]] == [f"pagina {i:02d}" for i in (5, 7, 9, 11, 13)] and j["has_more"], j
        code, j = req(port, "GET", f"/api/messages?project=pg&limit=5&before={j['messages'][0]['msg_id']}")
        assert [m["body"] for m in j["messages"]] == ["pagina 01", "pagina 03"] and not j["has_more"], j
        code, j = req(port, "GET", "/api/messages?limit=3")
        assert len(j["messages"]) == 3 and j["has_more"] and j["messages"][-1]["body"] == "historico do hermes", j
        assert req(port, "GET", "/api/messages?before=naoexiste")[0] == 400
        assert len(req(port, "GET", "/api/state")[1]["messages"]) <= 300
        code, j = req(port, "POST", "/api/rota/inventada", {}, T); assert code == 404 and "rota nao encontrada" in j["error"], j
    finally:
        p.terminate(); _, err = p.communicate(timeout=5)
    assert "400 em POST /api/project/open" in err, err  # erros do usuario aparecem na janela do dove
    print("OK: API nova (ping/versao, no-store, token+Host+Origin nas rotas novas, fs/list, project/open+info, agent add/remove, paginacao)")

if __name__ == "__main__":
    main()
    fase1()
    robustez()
    fase2()
