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
    # guia completo (--agent): exemplos copiaveis
    for ex_ in ('a2a send --from codex --to hermes --project lagu --kind task --body',
                '--reply-to 1e2b9c0d4f55 --kind report --state CONCLUIDO --body "handler migrado, testes ok" --evidence',
                'a2a status --agent codex --set blocked --note', '--file src/payments/webhook.py:40-62',
                'a2a mission approve m3f9a2c1 --agent codex --evidence', 'a2a mission reject m3f9a2c1 --agent codex --reason',
                'a2a read <msg_id> --agent codex --compact', '--context <0-100>', 'a2a status --agent codex --set done'):
        assert ex_ in t, (ex_, t)
    for ex_ in ("### Contexto e handoff", "Próximos passos:", "Bloqueios:", "`/clear`", "`/compact`",
                "### Para o Claude Code", "crossSessionInbound", "verifique a sintaxe exata na doc do Claude Code"):
        assert ex_ in t, (ex_, t)
    ob = subprocess.run([sys.executable, str(A2A), "onboard", "--agents-md"], capture_output=True, env=uenv)
    t = ob.stdout.decode("utf-8")
    assert ob.returncode == 0 and "Claude Code → `claude`" in t and "<seu-nome>" in t and "<projeto>" in t, t
    # nucleo do AGENTS.md: curto, estavel, com os elementos e as regras de seguranca
    ob = subprocess.run([sys.executable, str(A2A), "onboard", "--agents-md", "--project", "lagu"], capture_output=True, env=uenv)
    core = ob.stdout.decode("utf-8")
    assert ob.returncode == 0 and core.startswith("## Canal A2A — Dove\n"), core
    body = [l for l in core.split("\n")[1:] if l.strip()]
    assert len(body) <= 10 and len(core) <= 800, (len(body), len(core), core)
    for el in ("Claude Code → `claude` · Codex → `codex` · Hermes → `hermes`",
               "`a2a brief --agent <seu-nome> --mark-read`", "`a2a status --agent <seu-nome> --set working --note",
               "`a2a whereami --agent <seu-nome> --project lagu`", '--set done --note "<resumo>"',
               "Detalhes e exemplos: `a2a onboard --agent <seu-nome>` e `a2a <comando> --help`",
               "`kind=ack`", "a si mesmo", "`--reply-to`", "só coordenação",
               "merge, deploy, migração em produção, gasto ou exclusão", "outro agente", "autorização do Luiz",
               "missão só com evidência real", "Sem `a2a`? Avise o Luiz"):
        assert el in core, (el, core)
    for no in ("Contexto e handoff", "Para o Claude Code", "crossSessionInbound", "/clear", "/compact"):
        assert no not in core, (no, core)
    assert "<projeto>" not in core and not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}", core), core
    assert core == subprocess.run([sys.executable, str(A2A), "onboard", "--agents-md", "--project", "lagu"],
                                  capture_output=True, env=uenv).stdout.decode("utf-8")  # estavel
    # --help com exemplos copiaveis, sem mudar o resto
    for cmd, ex_ in ((["send"], "a2a send --from claude --to hermes"), (["brief"], "a2a brief --agent claude --mark-read"),
                     (["read"], "a2a read 1e2b9c0d4f55 --agent claude --compact"), (["status"], "a2a status --agent claude --set blocked"),
                     (["mission"], "a2a mission approve m3f9a2c1"), (["mission", "approve"], "--evidence"),
                     (["mission", "reject"], "--reason"), (["whereami"], "a2a whereami --agent claude --project lagu")):
        h = run(env, *cmd, "--help").stdout
        assert "exemplos:\n" in h and ex_ in h, (cmd, h)
    assert "Resumo unico para o agente se atualizar (substitui inbox + read de cada\nmensagem" in \
        subprocess.run([sys.executable, str(A2A), "brief", "--help"], capture_output=True, text=True,
                       env=dict(uenv, COLUMNS="80")).stdout  # descricao continua quebrada pela largura
    assert run(env, "onboard").returncode != 0
    h = " ".join(subprocess.run([sys.executable, str(A2A), "brief", "--help"], capture_output=True, text=True, env=uenv).stdout.split())
    assert "O contador abertas conta so as tarefas abertas que voce ja leu (linhas T); as nao lidas aparecem como N." in h, h
    print("OK: a2a onboard (--agent guia com exemplos, --agents-md nucleo curto) e --help com exemplos")

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
        ienv = {k: v for k, v in ienv.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "HERMES_HOME")}
        r = subprocess.run(["bash", str(ROOT / "install.sh")], capture_output=True, text=True, env=ienv)
        assert "Para valer em todos os projetos: a2a instructions install" in r.stdout, r.stdout
        assert not os.path.exists(os.path.join(h, ".claude")), "sem --instructions nao mexe nos arquivos globais"
        for _ in range(2):  # --instructions: claude e codex (nao hermes), idempotente
            r = subprocess.run(["bash", str(ROOT / "install.sh"), "--instructions", "claude"], capture_output=True, text=True, env=ienv)
            assert r.returncode == 0 and "Para valer" not in r.stdout, r.stdout + r.stderr
        assert "ja atualizado" in r.stdout and os.path.isfile(os.path.join(h, ".claude", "CLAUDE.md")), r.stdout
        assert os.path.isfile(os.path.join(h, ".codex", "AGENTS.md")) and not os.path.exists(os.path.join(h, ".hermes"))
        print("OK: install.sh (symlinks a2a e dove, shebang, agentes, idempotente)")

    # install.ps1: checagem estatica (shims .cmd e Git Bash, ASCII puro)
    raw = (ROOT / "install.ps1").read_bytes()
    assert all(b < 128 for b in raw), "install.ps1 tem bytes nao-ASCII"
    txt = raw.decode("ascii")
    for needle in ("a2a.cmd", "#!/bin/sh", "UTF8Encoding($false)", "dove.cmd", "panel --open %*",
                   'Join-Path $bin "dove"', 'panel --open `"`$@`"', "[switch]$Instructions",
                   'instructions install --agents "claude,codex"', "Para valer em todos os projetos: a2a instructions install"):
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

def git_fase():
    """Fase 2: git no painel (status/diff/commit/fetch/pull/push) e uma copia (worktree) por agente. Git de verdade."""
    tmp = tempfile.mkdtemp(); home = os.path.join(tmp, "home")
    gcfg = os.path.join(tmp, "gitconfig")
    open(gcfg, "w").write("[user]\n\tname = Teste\n\temail = teste@example.com\n[init]\n\tdefaultBranch = main\n"
                          "[commit]\n\tgpgsign = false\n[push]\n\tnegotiate = false\n")
    gitvars = {"GIT_CONFIG_GLOBAL": gcfg, "GIT_CONFIG_NOSYSTEM": "1"}
    env = dict(os.environ, A2A_HOME=home, PYTHONIOENCODING="utf-8", DOVE_NO_BROWSER="1", DOVE_FAKE_OPEN="1", **gitvars)
    os.environ.update(gitvars)
    sys.path.insert(0, str(ROOT)); os.environ["A2A_HOME"] = home
    import importlib; a2a = importlib.import_module("a2a")
    for k, v in (("HOME", home), ("BUS", os.path.join(home, "bus")), ("CURSOR", os.path.join(home, "cursor")),
                 ("AGENTS", os.path.join(home, "agents")), ("STATUS", os.path.join(home, "status")),
                 ("MISSIONS", os.path.join(home, "missions")), ("PROJECTS", os.path.join(home, "projects.json")),
                 ("CONFIG", os.path.join(home, "config.json"))):
        setattr(a2a, k, v)
    def g(cwd, *args, check=True):
        r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
        if check: assert r.returncode == 0, (args, r.stdout, r.stderr)
        return r.stdout.strip()
    def write(p, t): open(p, "w", encoding="utf-8").write(t)
    code = os.path.join(tmp, "Codigo"); os.makedirs(code)
    remote = os.path.join(code, "lagu.git"); g(code, "init", "-q", "--bare", "-b", "main", remote)
    lagu = os.path.join(code, "lagu"); g(code, "clone", "-q", remote, lagu)
    for f, t in (("a.txt", "a1\n"), ("b.txt", "b1\n"), ("conf.txt", "linha=1\n")): write(os.path.join(lagu, f), t)
    g(lagu, "add", "."); g(lagu, "commit", "-qm", "inicio"); g(lagu, "push", "-q", "-u", "origin", "main")
    other = os.path.join(tmp, "outro"); g(tmp, "clone", "-q", remote, other)
    run(env, "init")
    for ag in ("claude", "codex", "hermes"): run(env, "join", "--agent", ag)
    assert run(env, "project", "add", "lagu", lagu).returncode == 0
    msgs = lambda: [json.load(open(f, encoding="utf-8")) for f in sorted(pathlib.Path(home, "bus").glob("*.json"))]
    port = free_port(); p, T = start_panel(env, port)
    q = urllib.request.quote
    G = lambda path: req(port, "GET", path, None, T)
    P = lambda path, body: req(port, "POST", path, body, T)
    try:
        # ---- seguranca: toda rota nova exige token e Host
        gets = ["/api/git/status?project=lagu", "/api/git/diff?project=lagu&path=a.txt"]
        posts = ["/api/git/commit", "/api/git/fetch", "/api/git/pull", "/api/git/push", "/api/worktree/create",
                 "/api/worktree/merge", "/api/worktree/sync", "/api/worktree/remove"]
        for path in gets:
            assert req(port, "GET", path)[0] == 403, path
            assert req(port, "GET", path, None, {"X-Dove-Token": "x"})[0] == 403, path
            assert req(port, "GET", path, None, T, host="evil.example")[0] == 403, path
        for path in posts:
            body = {"project": "lagu", "agent": "claude", "message": "x", "confirm_branch": "main"}
            assert req(port, "POST", path, body)[0] == 403, path
            assert req(port, "POST", path, body, T, host="evil.example")[0] == 403, path
            assert req(port, "POST", path, body, dict(T, Origin="http://evil.example"))[0] == 403, path
            code, j = P(path, {"project": "fantasma", "agent": "claude", "message": "x"})
            assert code == 400 and "nao encontrado" in j["error"], (path, j)
            code, j = P(path, {"project": lagu, "message": "x"})           # caminho no lugar do nome: rejeitado
            assert code == 400 and "nao encontrado" in j["error"], (path, j)
        code, j = G(f"/api/git/status?project={q(lagu)}"); assert code == 400, j
        code, j = G("/api/git/status?project=lagu&agent=claude"); assert code == 400 and "copia" in j["error"], j
        print("OK: git/worktree: token + Host + Origin em todas as rotas novas; projeto nao registrado/caminho rejeitado")

        # ---- status
        code, s = G("/api/git/status?project=lagu")
        assert code == 200 and s["branch"] == "main" and s["upstream"] == "origin/main" and (s["ahead"], s["behind"]) == (0, 0), s
        assert s["files"] == [] and s["default_branch"] == "main" and s["protected"] and not s["detached"], s
        assert s["commits"][0]["subject"] == "inicio" and s["commits"][0]["author"] == "Teste" and s["commits"][0]["date"], s["commits"]
        assert "main" in s["branches"] and s["path"] == lagu, s
        write(os.path.join(lagu, "a.txt"), "a1\na2 nova linha\n"); write(os.path.join(lagu, "novo arquivo.txt"), "conteudo novo\n")
        os.makedirs(os.path.join(lagu, "pasta")); write(os.path.join(lagu, "pasta", "x.txt"), "x\n")
        code, s = G("/api/git/status?project=lagu")
        fs = {f["path"]: f for f in s["files"]}
        assert set(fs) == {"a.txt", "novo arquivo.txt", "pasta/x.txt"}, fs
        assert fs["a.txt"]["y"] == "M" and fs["novo arquivo.txt"]["untracked"] and fs["novo arquivo.txt"]["x"] == "?", fs
        # ---- diff
        code, d = G("/api/git/diff?project=lagu&path=a.txt")
        assert code == 200 and "+a2 nova linha" in d["text"] and not d["truncated"] and not d["untracked"], d
        code, d = G("/api/git/diff?project=lagu&path=" + q("novo arquivo.txt"))
        assert code == 200 and d["untracked"] and "+conteudo novo" in d["text"], d
        for bad in ("../etc/passwd", "c.txt", lagu + "/a.txt", ""):
            code, j = G("/api/git/diff?project=lagu&path=" + q(bad)); assert code == 400 and "alterados" in j["error"], (bad, j)
        real_max = a2a.DIFF_MAX
        try:
            a2a.DIFF_MAX = 10; d = a2a.git_diff("lagu", "", "a.txt"); assert d["truncated"] and len(d["text"].encode()) <= 10, d
        finally:
            a2a.DIFF_MAX = real_max
        print("OK: git status (branch, upstream, arquivos, commits, padrao) e diff (modificado, novo, caminho fora do status, limite)")

        # ---- commit
        code, j = P("/api/git/commit", {"project": "lagu", "message": "   ", "paths": ["a.txt"]}); assert code == 400 and "mensagem" in j["error"], j
        code, j = P("/api/git/commit", {"project": "lagu", "message": "x", "paths": ["b.txt"]}); assert code == 400 and "alterados" in j["error"], j
        code, j = P("/api/git/commit", {"project": "lagu", "message": "x", "paths": []}); assert code == 400, j
        code, j = P("/api/git/commit", {"project": "lagu", "message": "Muda a e cria novo", "paths": ["a.txt", "novo arquivo.txt"]})
        assert code == 200 and j["files"] == 2 and j["branch"] == "main" and j["hash"] == g(lagu, "rev-parse", "--short", "HEAD"), j
        assert g(lagu, "log", "-1", "--format=%B") == "Muda a e cria novo"  # mensagem como digitada, sem trailers
        code, s = G("/api/git/status?project=lagu")
        assert [f["path"] for f in s["files"]] == ["pasta/x.txt"] and s["ahead"] == 1 and s["behind"] == 0, s
        os.remove(os.path.join(lagu, "b.txt"))
        code, j = P("/api/git/commit", {"project": "lagu", "message": "resto (com remocao)"})  # padrao: tudo, inclusive novos e apagados
        assert code == 200 and j["files"] == 2, j
        assert G("/api/git/status?project=lagu")[1]["files"] == [] and not os.path.exists(os.path.join(lagu, "b.txt"))
        assert "b.txt" not in g(lagu, "ls-files")
        code, j = P("/api/git/commit", {"project": "lagu", "message": "nada"}); assert code == 400 and "nada para commitar" in j["error"], j
        print("OK: commit (arquivos escolhidos, padrao = todos com novos/apagados, mensagem vazia, arquivo fora da lista, nada a commitar)")

        # ---- push: feature livre; main exige confirm_branch; nunca --force
        assert a2a.push_argv("main") == ["push", "-u", "origin", "main"]
        g(lagu, "checkout", "-q", "-b", "feat/x"); write(os.path.join(lagu, "f.txt"), "f\n")
        P("/api/git/commit", {"project": "lagu", "message": "feature"})
        code, j = P("/api/git/push", {"project": "lagu"})
        assert code == 200 and j["branch"] == "feat/x", j
        assert "refs/heads/feat/x" in g(lagu, "ls-remote", "origin")
        assert G("/api/git/status?project=lagu")[1]["upstream"] == "origin/feat/x"
        g(lagu, "checkout", "-q", "main")
        code, j = P("/api/git/push", {"project": "lagu"}); assert code == 400 and j["needs_confirm"] == "main", j
        code, j = P("/api/git/push", {"project": "lagu", "confirm_branch": "Main"}); assert code == 400, j
        assert g(remote, "rev-parse", "main") != g(lagu, "rev-parse", "main")
        code, j = P("/api/git/push", {"project": "lagu", "confirm_branch": "main"}); assert code == 200, j
        assert g(remote, "rev-parse", "main") == g(lagu, "rev-parse", "main")
        # rejeitado (remoto andou): mensagem "faca Pull antes"; push nunca forca
        g(other, "pull", "-q"); write(os.path.join(other, "o.txt"), "o\n"); g(other, "add", "."); g(other, "commit", "-qm", "do outro")
        g(other, "push", "-q")
        write(os.path.join(lagu, "l.txt"), "l\n"); P("/api/git/commit", {"project": "lagu", "message": "local"})
        code, j = P("/api/git/push", {"project": "lagu", "confirm_branch": "main"})
        assert code == 400 and "Pull antes" in j["error"], j
        print("OK: push (feature sem confirmar, main exige confirm_branch exato, rejeitado -> faca Pull antes)")

        # ---- fetch / pull --ff-only
        code, j = P("/api/git/fetch", {"project": "lagu"}); assert code == 200, j
        code, s = G("/api/git/status?project=lagu"); assert (s["ahead"], s["behind"]) == (1, 1), s
        code, j = P("/api/git/pull", {"project": "lagu"}); assert code == 400 and "divergiram" in j["error"], j  # ff-only nao faz merge
        assert g(lagu, "status", "--porcelain") == "" and not os.path.exists(os.path.join(lagu, ".git", "MERGE_HEAD"))
        g(lagu, "checkout", "-q", "feat/x")  # volta main ao remoto sem reset: apaga o commit local criando main de novo a partir do remoto
        g(lagu, "branch", "-q", "-m", "main", "main-local"); g(lagu, "checkout", "-q", "-b", "main", "origin/main~1")
        g(lagu, "branch", "-q", "--set-upstream-to=origin/main", "main")
        write(os.path.join(lagu, "a.txt"), "sujo\n")
        code, j = P("/api/git/pull", {"project": "lagu"}); assert code == 400 and "commit antes" in j["error"] and j["dirty"] == ["a.txt"], j
        g(lagu, "checkout", "--", "a.txt")
        code, j = P("/api/git/pull", {"project": "lagu"})
        assert code == 200 and j["updated"] and g(lagu, "rev-parse", "HEAD") == g(remote, "rev-parse", "main"), j
        g(lagu, "branch", "-q", "-D", "main-local")
        print("OK: fetch, pull --ff-only (avanca; recusa com alteracoes; divergente nao faz merge)")

        # ---- copias (worktree) por agente
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "ninguem"}); assert code == 400 and "registrado" in j["error"], j
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "claude", "base": "nao-existe"}); assert code == 400 and "nao existe" in j["error"], j
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "claude", "base": "--force"}); assert code == 400, j
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "claude"})
        wc = os.path.join(os.path.dirname(lagu), "lagu-claude")
        assert code == 200 and j["worktree"]["path"] == wc and j["worktree"]["branch"] == "dove/claude" and j["worktree"]["base"] == "main", j
        assert not j["worktree"]["reused"] and os.path.isdir(wc) and g(wc, "branch", "--show-current") == "dove/claude"
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "claude"}); assert code == 400 and "ja tem" in j["error"], j
        g(lagu, "branch", "dove/codex")  # branch ja existe: reaproveita
        r = run(env, "worktree", "create", "--project", "lagu", "--agent", "codex", "--from", "codex")
        assert r.returncode == 1 and "so o humano" in r.stderr, r.stderr
        r = run(env, "worktree", "create", "--project", "lagu", "--agent", "codex", "--from", "luiz"); assert r.returncode == 0, r.stderr
        wx = os.path.join(os.path.dirname(lagu), "lagu-codex")
        assert "branch existente" in r.stdout and g(wx, "branch", "--show-current") == "dove/codex"
        pj = json.load(open(os.path.join(home, "projects.json"), encoding="utf-8"))[0]
        assert set(pj["worktrees"]) == {"claude", "codex"} and pj["worktrees"]["codex"]["path"] == wx, pj
        os.makedirs(os.path.join(os.path.dirname(lagu), "lagu-hermes"))  # pasta ocupada por outra coisa
        code, j = P("/api/worktree/create", {"project": "lagu", "agent": "hermes"}); assert code == 400 and "ja existe" in j["error"], j
        os.rmdir(os.path.join(os.path.dirname(lagu), "lagu-hermes"))
        lst = run(env, "worktree", "list", "--project", "lagu").stdout
        assert "claude" in lst and "dove/codex" in lst and wx in lst and "limpa" in lst, lst
        assert run(env, "whereami", "--agent", "claude", "--project", "lagu").stdout.strip() == wc
        assert run(env, "whereami", "--agent", "hermes", "--project", "lagu").stdout.strip() == lagu
        ob = run(env, "onboard", "--agent", "claude", "--project", "lagu").stdout
        assert f"Sua pasta de trabalho neste projeto: `{wc}` (branch `dove/claude`)" in ob and "o Luiz traz seu trabalho pelo painel" in ob, ob
        assert "Sua pasta de trabalho" not in run(env, "onboard", "--agent", "hermes", "--project", "lagu").stdout
        gen = run(env, "onboard", "--agents-md", "--project", "lagu").stdout  # nucleo: whereami generico, sem a pasta
        assert "`a2a whereami --agent <seu-nome> --project lagu`" in gen and "Sua pasta" not in gen, gen
        code, j = req(port, "GET", "/api/onboard?agent=claude&project=lagu", None, T); assert wc in j["text"], j
        code, j = P("/api/project/open", {"name": "lagu", "agent": "claude"}); assert code == 200 and j["path"] == wc, j
        code, j = P("/api/project/open", {"name": "lagu", "agent": "hermes"}); assert code == 400, j
        # trabalho dos agentes: claude commita algo novo; codex mexe na mesma linha que o main vai mexer
        write(os.path.join(wc, "c.txt"), "do claude\n"); g(wc, "add", "."); g(wc, "commit", "-qm", "claude: c.txt")
        write(os.path.join(wx, "conf.txt"), "linha=codex\n"); g(wx, "commit", "-qam", "codex: conf")
        write(os.path.join(wx, "rascunho.txt"), "wip\n")  # sujo (nao rastreado)
        code, s = G("/api/git/status?project=lagu")
        w1, w2 = s["worktrees"]["claude"], s["worktrees"]["codex"]
        assert (w1["ahead"], w1["behind"], w1["dirty"], w1["unmerged"]) == (1, 0, 0, 1) and w1["last"]["subject"] == "claude: c.txt", w1
        assert w2["dirty"] == 1 and w2["ahead"] == 1 and w2["exists"] and w2["path"] == wx, w2
        code, s = G("/api/git/status?project=lagu&agent=claude")
        assert code == 200 and s["branch"] == "dove/claude" and s["path"] == wc and s["worktrees"] == {}, s
        print("OK: worktree create (pasta <proj>-<agente>, dove/<agente>, reaproveita branch, pasta ocupada, so humano), list, resumo, whereami, onboard")

        # ---- merge (Trazer para minha branch)
        write(os.path.join(lagu, "a.txt"), "sujo\n")
        code, j = P("/api/worktree/merge", {"project": "lagu", "agent": "claude"}); assert code == 400 and "commit antes" in j["error"], j
        g(lagu, "checkout", "--", "a.txt")
        code, j = P("/api/worktree/merge", {"project": "lagu", "agent": "claude"})
        assert code == 200 and j["merged"] and j["branch"] == "main" and os.path.exists(os.path.join(lagu, "c.txt")), j
        assert g(lagu, "log", "-1", "--format=%s") == "Merge dove/claude (via Dove)" and len(g(lagu, "log", "-1", "--format=%P").split()) == 2
        code, j = P("/api/worktree/merge", {"project": "lagu", "agent": "claude"}); assert code == 200 and not j["merged"], j
        write(os.path.join(lagu, "conf.txt"), "linha=main\n"); g(lagu, "commit", "-qam", "main: conf")
        head = g(lagu, "rev-parse", "HEAD")
        code, j = P("/api/worktree/merge", {"project": "lagu", "agent": "codex"})
        assert code == 400 and j["conflicts"] == ["conf.txt"] and j["aborted"] and j["clean"] and "conflito" in j["error"], j
        assert g(lagu, "status", "--porcelain") == "" and g(lagu, "rev-parse", "HEAD") == head
        assert not os.path.exists(os.path.join(lagu, ".git", "MERGE_HEAD"))
        # ---- sync (Atualizar copia)
        code, j = P("/api/worktree/sync", {"project": "lagu", "agent": "codex"})
        assert code == 400 and "nao commitados" not in j["error"] and j["conflicts"] == ["conf.txt"], j  # untracked nao bloqueia; conflito aborta
        assert g(wx, "status", "--porcelain") == "?? rascunho.txt"
        write(os.path.join(wc, "c.txt"), "editando\n")
        code, j = P("/api/worktree/sync", {"project": "lagu", "agent": "claude"}); assert code == 400 and "nao commitados" in j["error"], j
        g(wc, "checkout", "--", "c.txt")
        code, j = P("/api/worktree/sync", {"project": "lagu", "agent": "claude"})
        assert code == 200 and j["merged"] and open(os.path.join(wc, "conf.txt")).read() == "linha=main\n", j
        print("OK: merge --no-ff (limpo; recusa com main sujo; conflito -> abortado, main limpo, arquivos listados) e sync")

        # ---- remove
        code, j = P("/api/worktree/remove", {"project": "lagu", "agent": "codex"})
        assert code == 400 and j["dirty"] == ["rascunho.txt"] and os.path.isdir(wx), j
        os.remove(os.path.join(wx, "rascunho.txt"))
        code, j = P("/api/worktree/remove", {"project": "lagu", "agent": "codex"})
        assert code == 400 and j["unmerged"] == 1 and "mantenha" in j["error"] and os.path.isdir(wx), j
        code, s = G("/api/git/status?project=lagu")
        assert s["worktrees"]["claude"]["unmerged"] == 0 and s["worktrees"]["claude"]["ahead"] == 1, s["worktrees"]["claude"]  # so o merge do sync
        code, j = P("/api/worktree/remove", {"project": "lagu", "agent": "claude"})
        assert code == 200 and not os.path.exists(wc) and g(lagu, "rev-parse", "--verify", "dove/claude"), j
        assert "claude" not in json.load(open(os.path.join(home, "projects.json"), encoding="utf-8"))[0]["worktrees"]
        code, j = P("/api/worktree/remove", {"project": "lagu", "agent": "claude"}); assert code == 400, j
        r = run(env, "worktree", "remove", "--project", "lagu", "--agent", "codex", "--from", "luiz")
        assert r.returncode == 1 and "nao estao em main" in r.stderr, r.stderr
        print("OK: remove (recusa suja / com commits fora da base; limpa+juntada remove a pasta e mantem a branch)")

        # ---- canal: reports do luiz; luiz sem status
        bodies = [m["body"] for m in msgs() if m["from"] == "luiz" and m["to"] == "all" and m["kind"] == "report" and m["project"] == "lagu"]
        for needle in ("fez commit em main", "fez push de feat/x", "fez push de main", "fez pull em main", "criou a copia de trabalho de claude",
                       "fez merge de dove/claude em main", "atualizou a copia de claude", "removeu a copia de trabalho de claude"):
            assert any(needle in b for b in bodies), (needle, bodies)
        assert not any("codex" in b and "merge de" in b for b in bodies), bodies  # conflito nao gera "fez merge"
        assert not os.path.exists(os.path.join(home, "status", "luiz.json"))
        print("OK: cada acao do humano vira report luiz -> all no canal; luiz continua sem status")
    finally:
        p.terminate(); p.communicate(timeout=5)

    # ---- nenhuma acao monta argv proibido (--force, reset, rebase, clean, branch -D)
    calls, real = [], a2a.run_git
    def spy(cwd, args, **kw): calls.append(list(args)); return real(cwd, args, **kw)
    try:
        a2a.run_git = spy
        write(os.path.join(lagu, "z.txt"), "z\n"); a2a.git_commit("lagu", "", "z", None)
        a2a.git_fetch("lagu")
        try: a2a.git_push("lagu", "", "main")
        except a2a.DoveError: pass
        try: a2a.git_pull("lagu")
        except a2a.DoveError: pass
        try: a2a.worktree_merge("lagu", "codex")
        except a2a.DoveError: pass
        try: a2a.worktree_sync("lagu", "codex")
        except a2a.DoveError: pass
        try: a2a.worktree_remove("lagu", "codex")
        except a2a.DoveError: pass
        a2a.git_status("lagu"); a2a.git_diff
    finally:
        a2a.run_git = real
    flat = [x for c in calls for x in c]
    assert calls and any(c[:1] == ["push"] for c in calls), calls
    for bad in ("--force", "-f", "--force-with-lease", "--hard", "rebase", "clean", "-D", "--delete"):
        assert bad not in flat, (bad, [c for c in calls if bad in c])
    assert all(c == ["push", "-u", "origin", "main"] for c in calls if c[0] == "push"), calls
    assert not any(c[0] == "reset" for c in calls)
    print(f"OK: {len(calls)} comandos git montados, nenhum com --force/reset/rebase/clean/branch -D")

def brief_fase():
    """a2a brief (item 1 da proposta de interface): saida exata, anti-loop, --mark-read, T, M, filtros, status."""
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex", "hermes"): run(env, "join", "--agent", ag)
    bus, base = os.path.join(tmp, "bus"), time.time() - 3600
    def put(i, mid, frm, to, kind, body, project="lagu", state="", evidence="", reply="", task=""):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * 60))
        m = {"data": ts, "task_id": task, "msg_id": mid, "from": frm, "to": to, "project": project,
             "in_reply_to": reply, "kind": kind, "state": state, "result": "", "evidence": evidence,
             "pending": "", "next_action": "", "body": body}
        with open(os.path.join(bus, ts.replace(":", "").replace("-", "") + "-" + mid + ".json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False)
    def mission(mid, title, approvals, project="lagu", agents=("claude", "codex", "hermes"), human=None):
        ap = {a: {"verdict": "approve", "ts": "x", "evidence": "ok", "reason": ""} for a in approvals}
        m = {"id": mid, "project": project, "title": title, "description": "", "agents": list(agents), "created_by": "luiz",
             "created": "2026-10-18T10:00:00Z", "approvals": ap, "history": [], "human": human}
        with open(os.path.join(tmp, "missions", mid + ".json"), "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False)
    # cenario do exemplo da proposta
    put(1, "1e2b9c0d4f55", "luiz", "codex", "task", "Migrar o webhook de pagamentos para a assinatura nova\nComeçar pelo handler e pelos testes.")
    put(2, "aa00000000a1", "codex", "claude", "question", "mensagem do proprio codex", project="lagu")  # nunca aparece
    put(3, "3f9a1c2b7d10", "claude", "codex", "task", "cupom de frete grátis: aplicar regra acima de R$ 199")
    put(4, "8b21e0f4a9c3", "hermes", "codex", "report", "E2E staging: 148 ok, 2 falhas (frete grátis)", project="qlink",
        state="CONCLUIDO", evidence="e2e/report.html")
    put(5, "c47d0e11aa02", "luiz", "codex", "question", "a credencial de homologação chegou?")
    put(6, "bb00000000b2", "claude", "codex", "ack", "recebido", reply="aa00000000a1")
    put(7, "cc00000000c3", "claude", "hermes", "task", "nao e para o codex")
    mission("mb222288", "Checkout novo pronto para produção", ["claude", "hermes"])
    mission("ma111111", "Ja aprovada pelo codex", ["codex"])
    mission("mc333333", "Sem o codex", [], agents=("claude", "hermes"))
    with open(os.path.join(tmp, "cursor", "codex.json"), "w") as f: json.dump(["1e2b9c0d4f55", "aa00000000a1"], f)
    run(env, "status", "--agent", "codex", "--set", "blocked", "--note", "aguardando credencial do banco de homologação",
        "--context", "82", "--project", "lagu")
    norm = lambda s: re.sub(r" \d+[smhd] \"", ' AGE "', s)
    expected = """@codex blocked ctx=82 novas=4 abertas=1 aval=1
N 3f9a1c2b7d10 claude task lagu AGE "cupom de frete grátis: aplicar regra acima de R$ 199"
N 8b21e0f4a9c3 hermes report/CONCLUIDO qlink AGE "E2E staging: 148 ok, 2 falhas (frete grátis)" +evid
N c47d0e11aa02 luiz question lagu AGE "a credencial de homologação chegou?"
ACK 1 (claude)
T 1e2b9c0d4f55 de=luiz lagu AGE "Migrar o webhook de pagamentos para a assinatura nova"
M mb222288 lagu aberta 2/3 "Checkout novo pronto para produção"
! ctx 82>=80: preparar handoff
! bloqueado: aguardando credencial do banco de homologação
"""
    st = lambda a: json.load(open(os.path.join(tmp, "status", a + ".json"), encoding="utf-8"))
    snap = lambda: {c: run(env, *c.split()).stdout for c in
                    ("inbox --agent codex --no-auto-status", "mission list", "summary", "log --limit 50",
                     "read 3f9a1c2b7d10", "inbox --agent hermes --no-auto-status")}
    seen0, before, st0 = open(os.path.join(tmp, "cursor", "codex.json")).read(), snap(), st("codex")
    b1 = run(env, "brief", "--agent", "codex")
    assert b1.returncode == 0 and norm(b1.stdout) == expected, b1.stdout + b1.stderr
    b2 = run(env, "brief", "--agent", "codex")
    assert [l for l in b2.stdout.splitlines() if l[:2] in ("N ", "AC")] == [l for l in b1.stdout.splitlines() if l[:2] in ("N ", "AC")]
    assert open(os.path.join(tmp, "cursor", "codex.json")).read() == seen0, "sem --mark-read nada e marcado"
    assert snap() == before, "brief nao pode mudar a saida de inbox/read/mission list/summary/log/status"
    st1 = st("codex")
    assert {k: v for k, v in st1.items() if k not in ("updated", "ts")} == {k: v for k, v in st0.items() if k not in ("updated", "ts")}
    assert st1["ts"] >= st0["ts"], (st0, st1)  # heartbeat
    raw = open(os.path.join(tmp, "status", "codex.json"), "rb").read()
    run(env, "brief", "--agent", "codex", "--no-auto-status")
    assert open(os.path.join(tmp, "status", "codex.json"), "rb").read() == raw, "--no-auto-status nao toca o status"
    # proprias mensagens nunca aparecem (nem no --json, nem com --limit 0)
    for args in ((), ("--json",), ("--limit", "0"), ("--project", "lagu")):
        o = run(env, "brief", "--agent", "codex", *args).stdout
        assert "aa00000000a1" not in o and "proprio codex" not in o and "cc00000000c3" not in o, o
    # --project e --json
    pl = run(env, "brief", "--agent", "codex", "--project", "qlink").stdout
    assert "8b21e0f4a9c3" in pl and "3f9a1c2b7d10" not in pl and "mb222288" not in pl and "1e2b9c0d4f55" not in pl, pl
    assert pl.splitlines()[0] == "@codex blocked ctx=82 novas=1 abertas=0 aval=0", pl
    j = run(env, "brief", "--agent", "codex", "--json").stdout
    assert j.count("\n") == 1 and "\n  " not in j, j
    jd = json.loads(j)
    assert jd["agent"] == "codex" and jd["novas"] == 4 and jd["abertas"] == 1 and jd["aval"] == 1 and jd["ctx"] == 82, jd
    assert [n["id"] for n in jd["new"]] == ["3f9a1c2b7d10", "8b21e0f4a9c3", "c47d0e11aa02"] and jd["acks"] == {"n": 1, "from": ["claude"]}, jd
    assert "state" not in jd["new"][0] and jd["new"][1]["evid"] is True and "evid" not in jd["new"][0], jd  # sem campos vazios
    assert jd["missions"][0]["id"] == "mb222288" and len(jd["alerts"]) == 2, jd
    # --limit e --width
    lim = run(env, "brief", "--agent", "codex", "--limit", "1", "--width", "20").stdout.splitlines()
    assert [l for l in lim if l.startswith("N ")] == ['N 3f9a1c2b7d10 claude task lagu ' + lim[1].split()[5] + ' "cupom de frete gr..."'], lim
    assert "… +2 novas (a2a brief --limit 0 para todas)" in lim, lim
    # --mark-read com --limit: marca so o listado (N e ACK); o resto continua novo
    run(env, "brief", "--agent", "codex", "--mark-read", "--limit", "1")
    s = json.load(open(os.path.join(tmp, "cursor", "codex.json")))
    assert "3f9a1c2b7d10" in s and "bb00000000b2" in s and "8b21e0f4a9c3" not in s, s
    run(env, "brief", "--agent", "codex", "--mark-read")
    b3 = run(env, "brief", "--agent", "codex").stdout
    assert not [l for l in b3.splitlines() if l.startswith(("N ", "ACK", "…"))], b3
    assert "novas=0 abertas=2 aval=1" in b3 and "T 3f9a1c2b7d10 de=claude" in b3, b3  # task lida vira T
    # tarefa some de T depois de um report CONCLUIDO com --reply-to
    run(env, "send", "--from", "codex", "--to", "luiz", "--project", "lagu", "--reply-to", "1e2b9c0d4f55",
        "--kind", "report", "--state", "CONCLUIDO", "--body", "feito", "--no-auto-status")
    b4 = run(env, "brief", "--agent", "codex").stdout
    assert "1e2b9c0d4f55" not in b4 and "abertas=1" in b4, b4
    # ack de ack / anti-loop continua igual: o brief so conta o ack
    r = run(env, "ack", "bb00000000b2", "--from", "codex", "--no-auto-status")
    assert "anti-loop" in r.stdout, r.stdout
    print("OK: brief (saida exata do exemplo, sem proprias msgs, --mark-read, --limit/--width, T some com CONCLUIDO, --project, --json, heartbeat, nada mais muda)")

    # missao real: some de M com approve, volta com reject; task da missao nao vira T
    r = run(env, "mission", "new", "--project", "dove", "--title", "Teste de M", "--agents", "codex,hermes", "--from", "luiz")
    mid = re.search(r"missao (\w+) criada", r.stdout).group(1)
    o = run(env, "brief", "--agent", "codex", "--project", "dove", "--mark-read").stdout
    assert f"M {mid} dove aberta 0/2 \"Teste de M\"" in o and "novas=1" in o, o
    o = run(env, "brief", "--agent", "codex", "--project", "dove").stdout
    assert f"M {mid}" in o and not [l for l in o.splitlines() if l.startswith(("N ", "T "))], o
    run(env, "mission", "approve", mid, "--agent", "codex", "--evidence", "conferi")
    o = run(env, "brief", "--agent", "codex", "--project", "dove").stdout
    assert mid not in o and "aval=0" in o, o
    run(env, "mission", "reject", mid, "--agent", "codex", "--reason", "achei um bug")
    o = run(env, "brief", "--agent", "codex", "--project", "dove").stdout
    assert f"M {mid} dove reprovada 0/2" in o and "aval=1" in o, o
    assert not os.path.exists(os.path.join(tmp, "status", "luiz.json"))
    o = run(env, "brief", "--agent", "luiz")
    assert o.returncode == 0 and not os.path.exists(os.path.join(tmp, "status", "luiz.json")), "humano nao ganha status"
    print("OK: brief e missoes (some com approve, volta com reject, task da missao fora de T; humano sem status)")

    # vazio: exatamente as duas linhas
    tmp2 = tempfile.mkdtemp(); env2 = dict(os.environ, A2A_HOME=tmp2, PYTHONIOENCODING="utf-8")
    run(env2, "join", "--agent", "codex")
    o = run(env2, "brief", "--agent", "codex")
    assert o.returncode == 0 and o.stdout == "@codex idle ctx=- novas=0 abertas=0 aval=0\n(nada pendente)\n", repr(o.stdout)
    assert json.load(open(os.path.join(tmp2, "status", "codex.json")))["state"] == "idle"
    assert json.loads(run(env2, "brief", "--agent", "codex", "--json").stdout) == \
        {"agent": "codex", "state": "idle", "novas": 0, "abertas": 0, "aval": 0}
    # onboard usa o brief
    t = run(env2, "onboard", "--agent", "codex", "--project", "lagu").stdout
    assert "a2a brief --agent codex --mark-read" in t and "a2a inbox" not in t and "a2a whereami --agent codex" in t, t
    print("OK: brief vazio (duas linhas exatas, --json) e onboard com a2a brief")

def compact_fase():
    """read --compact (item 2): so campos com conteudo, body inteiro, sem a flag byte a byte igual, marca como lida."""
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("codex", "hermes"): run(env, "join", "--agent", ag)
    bus = os.path.join(tmp, "bus")
    def put(m):
        fn = m["data"].replace(":", "").replace("-", "") + "-" + m["msg_id"] + ".json"
        with open(os.path.join(bus, fn), "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False)
    base = {"task_id": "", "from": "luiz", "to": "codex", "project": "lagu", "in_reply_to": "", "kind": "task",
            "state": "", "result": "", "evidence": "", "pending": "", "next_action": ""}
    put(dict(base, data="2026-10-18T14:02:11Z", msg_id="1e2b9c0d4f55",
             body="Migrar o webhook de pagamentos para a assinatura nova (X-Signature).\nComeçar pelo handler e pelos testes."))
    put(dict(base, data="2026-10-18T14:20:45Z", msg_id="8b21e0f4a9c3", **{"from": "hermes", "project": "qlink",
             "in_reply_to": "1e2b9c0d4f55", "kind": "report", "state": "CONCLUIDO", "evidence": "e2e/report.html",
             "next_action": "corrigir regra de frete acima de R$ 199", "task_id": "t42",
             "body": "E2E staging: 148 ok, 2 falhas (frete grátis)."}))
    put(dict(base, data="2026-10-18T14:30:00Z", msg_id="9c9c9c9c9c9c", project="", body=""))
    seen = lambda: set(json.load(open(os.path.join(tmp, "cursor", "codex.json")))) if os.path.exists(os.path.join(tmp, "cursor", "codex.json")) else set()
    r = run(env, "read", "1e2b9c0d4f55", "--agent", "codex", "--compact")
    assert r.returncode == 0 and r.stdout == ("1e2b9c0d4f55 luiz->codex task proj=lagu 2026-10-18T14:02:11Z\n"
        "Migrar o webhook de pagamentos para a assinatura nova (X-Signature).\nComeçar pelo handler e pelos testes.\n"), r.stdout
    assert "1e2b9c0d4f55" in seen(), "--compact marca como lida"
    r = run(env, "read", "8b21e0f4a9c3", "--agent", "codex", "--compact")
    assert r.stdout == ("8b21e0f4a9c3 hermes->codex report/CONCLUIDO proj=qlink re=1e2b9c0d4f55 task=t42 2026-10-18T14:20:45Z\n"
        "E2E staging: 148 ok, 2 falhas (frete grátis).\nevidence: e2e/report.html\n"
        "next_action: corrigir regra de frete acima de R$ 199\n"), r.stdout
    for k in ("result:", "pending:", "in_reply_to", "task_id"): assert k not in r.stdout, k
    r = run(env, "read", "9c9c9c9c9c9c", "--compact")
    assert r.stdout == "9c9c9c9c9c9c luiz->codex task proj=- 2026-10-18T14:30:00Z\n", r.stdout  # body vazio: so o cabecalho
    # sem a flag: byte a byte o JSON indentado de antes; marca como lida igual
    r = run(env, "read", "8b21e0f4a9c3", "--agent", "hermes")
    src = json.load(open(next(os.path.join(bus, f) for f in os.listdir(bus) if "8b21e0f4a9c3" in f), encoding="utf-8"))
    assert r.stdout == json.dumps(src, ensure_ascii=False, indent=2) + "\n", r.stdout
    assert "8b21e0f4a9c3" in json.load(open(os.path.join(tmp, "cursor", "hermes.json")))
    # inexistente: mesmo erro e codigo, com e sem a flag
    for extra in ((), ("--compact",)):
        r = run(env, "read", "naoexiste000", "--agent", "codex", *extra)
        assert r.returncode == 1 and r.stderr == "nao encontrada\n" and r.stdout == "", (r.returncode, r.stderr)
        assert "naoexiste000" not in seen()
    # wait --compact usa o mesmo formato e marca como lida
    r = run(env, "wait", "--agent", "codex", "--timeout", "2", "--interval", "0.1", "--compact", "--no-auto-status")
    assert r.returncode == 0 and r.stdout == "9c9c9c9c9c9c luiz->codex task proj=- 2026-10-18T14:30:00Z\n", r.stdout
    assert "9c9c9c9c9c9c" in seen()
    t = run(env, "onboard", "--agent", "codex").stdout
    assert "a2a read <msg_id> --agent codex --compact" in t, t
    print("OK: read --compact (so campos com conteudo, body multilinha, sem flag identico, marca lida, erro igual, wait --compact)")

WAIT_PROBE = r"""
import argparse, json, os, sys, threading, time, io, contextlib
sys.path.insert(0, sys.argv[1]); import a2a
calls = {"all": 0, "passes": 0}
orig_all, orig_seen = a2a.all_messages, a2a.load_seen
def counted():
    calls["all"] += 1; return orig_all()
def seen(x):
    calls["passes"] += 1; return orig_seen(x)
a2a.all_messages, a2a.load_seen = counted, seen
def wait(timeout, interval=0.2):
    ns = argparse.Namespace(agent="codex", project=None, timeout=timeout, interval=interval, until=None,
                            no_auto_status=True, compact=True)
    buf, rc = io.StringIO(), 0
    with contextlib.redirect_stdout(buf):
        try: a2a.cmd_wait(ns)
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue()
out = {}
for i in range(200): a2a.post_message("hermes", "claude", f"ruido {i}", auto_status=False)
calls.update(all=0, passes=0)
rc, txt = wait(3)
out["idle"] = dict(calls, rc=rc, txt=txt)
# mensagem gravada no meio da espera: entregue em ate um --interval
calls.update(all=0, passes=0); t_write = {}
def later():
    time.sleep(1.0); t_write["t"] = time.time(); a2a.post_message("hermes", "codex", "chegou no meio", auto_status=False)
th = threading.Thread(target=later); th.start()
rc, txt = wait(5); t_done = time.time(); th.join()
out["mid"] = dict(calls, rc=rc, txt=txt, lag=t_done - t_write["t"])
# arquivo com nome mais antigo jogado direto no bus (relogio torto / a2a antigo) tambem chega
calls.update(all=0, passes=0)
def drop():
    time.sleep(0.6)
    m = {"data": "2020-01-01T00:00:00Z", "task_id": "", "msg_id": "velho0000001", "from": "hermes", "to": "codex",
         "project": "", "in_reply_to": "", "kind": "question", "state": "", "result": "", "evidence": "",
         "pending": "", "next_action": "", "body": "nome antigo"}
    a2a.write_json(os.path.join(a2a.BUS, "20200101T000000Z-velho0000001.json"), m)
threading.Thread(target=drop).start()
rc, txt = wait(4)
out["old"] = dict(calls, rc=rc, txt=txt)
# lida por outro processo antes de o wait ver: nao e entregue (cursor relido a cada volta)
calls.update(all=0, passes=0)
def read_elsewhere():
    time.sleep(0.6); a2a.mark_seen("codex", "lida0000000x")
    m = {"data": "2026-01-01T00:00:00Z", "task_id": "", "msg_id": "lida0000000x", "from": "hermes", "to": "codex",
         "project": "", "in_reply_to": "", "kind": "question", "state": "", "result": "", "evidence": "",
         "pending": "", "next_action": "", "body": "ja lida"}
    a2a.write_json(os.path.join(a2a.BUS, "20260101T000000Z-lida0000000x.json"), m)
threading.Thread(target=read_elsewhere).start()
rc, txt = wait(1.5)
out["seen"] = dict(calls, rc=rc, txt=txt)
print(json.dumps(out))
"""

def wait_fase():
    """wait sem reler o bus a toa (item 3): poucas leituras completas, entrega rapida, saida igual."""
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    run(env, "init")
    r = subprocess.run([sys.executable, "-c", WAIT_PROBE, str(ROOT)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    idle, mid, old, seen = o["idle"], o["mid"], o["old"], o["seen"]
    assert idle["rc"] == 2 and idle["txt"] == "(timeout)\n", idle
    assert idle["all"] <= 2 and 10 <= idle["passes"] <= 20, idle  # antes: 1 releitura completa por volta (~15)
    assert mid["rc"] == 0 and "chegou no meio" in mid["txt"] and mid["all"] <= 2, mid
    assert mid["lag"] < 0.2 + 0.25, mid  # em ate um --interval (com folga para o agendador)
    assert old["rc"] == 0 and "velho0000001" in old["txt"], old
    assert seen["rc"] == 2 and "lida0000000x" not in seen["txt"], seen
    # saida e marcacao iguais as de antes (JSON indentado sem --compact)
    run(env, "send", "--from", "hermes", "--to", "codex", "--body", "via cli", "--no-auto-status")
    w = run(env, "wait", "--agent", "codex", "--timeout", "2", "--interval", "0.1", "--no-auto-status")
    assert w.returncode == 0 and json.loads(w.stdout)["body"] == "via cli" and w.stdout.startswith("{\n  \"data\""), w.stdout
    w = run(env, "wait", "--agent", "codex", "--timeout", "0.5", "--interval", "0.1", "--no-auto-status")
    assert w.returncode == 2 and w.stdout == "(timeout)\n", w.stdout
    print(f"OK: wait sem reler o bus (timeout 3s/0.2s: {idle['all']} leitura(s) completa(s) em {idle['passes']} voltas; "
          f"entrega no meio em {mid['lag']:.2f}s; arquivo antigo e cursor relido)")

def archive_fase():
    """a2a archive (item 6): so o humano, dry-run nao move, fios abertos/nao lidos/recentes/de missao pendente ficam,
    read acha arquivada, --restore devolve tudo e as saidas voltam byte a byte."""
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex", "hermes"): run(env, "join", "--agent", ag)
    bus, now, seen = os.path.join(tmp, "bus"), time.time(), {"claude": [], "codex": [], "hermes": []}
    n = [0]
    def put(days, frm, to, kind, body, state="", reply="", task="", read=True):
        n[0] += 1; mid = "%012d" % n[0]; t = now - days * 86400 + n[0]
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
        m = {"data": ts, "task_id": task, "msg_id": mid, "from": frm, "to": to, "project": "lagu", "in_reply_to": reply,
             "kind": kind, "state": state, "result": "", "evidence": "", "pending": "", "next_action": "", "body": body}
        f = os.path.join(bus, ts.replace(":", "").replace("-", "") + "-" + mid + ".json")
        with open(f, "w", encoding="utf-8") as fh: json.dump(m, fh, ensure_ascii=False)
        os.utime(f, (t, t))
        if read:
            for a in (seen if to == "all" else [to]):
                if a in seen and a != frm: seen[a].append(mid)
        if frm in seen: seen[frm].append(mid)
        return mid
    def mission(mid, human):
        with open(os.path.join(tmp, "missions", mid + ".json"), "w") as f:
            json.dump({"id": mid, "project": "lagu", "title": "t " + mid, "description": "", "agents": ["hermes"],
                       "created_by": "luiz", "created": "2026-09-01T00:00:00Z",
                       "approvals": {"hermes": {"verdict": "approve", "ts": "x", "evidence": "ok", "reason": ""}},
                       "history": [], "human": {"by": "luiz", "ts": "x"} if human else None}, f)
    A = put(30, "luiz", "codex", "task", "A fechada"); A2 = put(30, "codex", "luiz", "ack", "recebido", reply=A)
    A3 = put(29, "codex", "luiz", "report", "A feita\nsegunda linha", state="CONCLUIDO", reply=A)
    A4 = put(29, "luiz", "codex", "ack", "ok", reply=A3)
    B = put(28, "claude", "hermes", "task", "B por task_id", task="tk2")
    B2 = put(28, "hermes", "claude", "report", "B feita", state="CONCLUIDO", task="tk2")
    B3 = put(28, "claude", "hermes", "ack", "ok", reply=B2)
    C = put(30, "luiz", "codex", "task", "C aberta")
    D = put(1, "claude", "codex", "task", "D recente"); D2 = put(1, "codex", "claude", "report", "D ok", state="CONCLUIDO", reply=D)
    E = put(30, "claude", "codex", "task", "E nao lida"); E2 = put(30, "codex", "claude", "report", "E ok", state="CONCLUIDO", reply=E, read=False)
    mission("mpend001", False); mission("mconf001", True)
    F = put(30, "luiz", "hermes", "task", "F missao pendente", task="mpend001")
    F2 = put(30, "hermes", "luiz", "report", "F aval", state="CONCLUIDO", reply=F, task="mpend001")
    G = put(30, "luiz", "hermes", "task", "G missao confirmada", task="mconf001")
    G2 = put(30, "hermes", "luiz", "report", "G aval", state="CONCLUIDO", reply=G, task="mconf001")
    H = put(30, "claude", "all", "question", "H broadcast sem task")
    I = put(30, "claude", "codex", "task", "I fechada"); I2 = put(30, "codex", "claude", "report", "I ok", state="CONCLUIDO", reply=I)
    I3 = put(29, "hermes", "codex", "task", "I filho aberto", reply=I2)
    for a, ids in seen.items():
        with open(os.path.join(tmp, "cursor", a + ".json"), "w") as f: json.dump(sorted(ids), f)
    listing = lambda d=bus: sorted(os.listdir(d)) if os.path.isdir(d) else []
    cmds = ("summary", "brief --agent codex --no-auto-status", "brief --agent hermes --no-auto-status",
            "inbox --agent codex --no-auto-status", "inbox --agent claude --no-auto-status", "log --limit 100",
            "summary --project lagu", "mission list")
    snap = lambda: {c: run(env, *c.split()).stdout for c in cmds}
    before, files0 = snap(), listing()
    # so o humano
    r = run(env, "archive", "--from", "codex")
    assert r.returncode == 1 and "so o humano" in r.stderr and listing() == files0, r.stderr
    r = run(env, "archive", "--from", "codex", "--restore")
    assert r.returncode == 1 and "so o humano" in r.stderr, r.stderr
    # dry-run: lista, nao move nada, nao posta nada
    r = run(env, "archive", "--from", "luiz", "--dry-run")
    assert r.returncode == 0 and r.stdout.startswith("arquivaria 9 mensagens (3 fios) em archive/"), r.stdout
    for x in (A, A4, B, B3, G2): assert x in r.stdout, (x, r.stdout)
    assert listing() == files0 and not os.path.exists(os.path.join(tmp, "archive")), "dry-run nao move"
    gone = {A, A2, A3, A4, B, B2, B3, G, G2}
    r = run(env, "archive", "--from", "luiz")
    assert r.returncode == 0 and r.stdout.startswith("arquivadas 9 mensagens (3 fios) em archive/"), r.stdout
    month = re.search(r"archive/(\d{4}-\d{2})/", r.stdout).group(1)
    in_bus = {f.split("-")[-1][:-5] for f in listing()}
    in_arc = {f.split("-")[-1][:-5] for f in listing(os.path.join(tmp, "archive", month))}
    assert in_arc == gone, in_arc
    for x in (C, D, D2, E, E2, F, F2, H, I, I2, I3): assert x in in_bus, x  # aberta, recente, nao lida, missao pendente, sem task, filho aberto
    rep = [json.load(open(os.path.join(bus, f), encoding="utf-8")) for f in listing()]
    rep = [m for m in rep if m["from"] == "luiz" and "arquivou 9 mensagens" in m["body"]]
    assert len(rep) == 1 and rep[0]["to"] == "all" and rep[0]["kind"] == "report", rep
    assert f"--restore {month}" in rep[0]["body"] and not os.path.exists(os.path.join(tmp, "status", "luiz.json"))
    assert len(os.listdir(os.path.join(tmp, "missions"))) == 2, "missoes intocadas"
    # nada mais para arquivar; arquivo intacto (mesmo conteudo)
    assert run(env, "archive", "--from", "luiz").stdout.startswith("nada para arquivar"), "segunda vez nao move"
    # read acha a arquivada (JSON igual ao arquivo; --compact; marca como lida)
    r = run(env, "read", A3, "--agent", "luiz")
    src = next(os.path.join(tmp, "archive", month, f) for f in listing(os.path.join(tmp, "archive", month)) if A3 in f)
    assert r.returncode == 0 and r.stdout == json.dumps(json.load(open(src, encoding="utf-8")), ensure_ascii=False, indent=2) + "\n", r.stdout
    r = run(env, "read", A3, "--compact")
    assert r.stdout.startswith(f"{A3} codex->luiz report/CONCLUIDO proj=lagu re={A} ") and "segunda linha" in r.stdout, r.stdout
    assert run(env, "read", "000000000999").returncode == 1
    # restore: tudo volta; com os 2 reports do luiz lidos, as saidas sao byte a byte as de antes
    r = run(env, "archive", "--from", "luiz", "--restore", "1999-01")
    assert r.returncode == 1 and "nada arquivado" in r.stderr, r.stderr
    assert run(env, "archive", "--from", "luiz", "--restore", "abc").returncode == 1
    r = run(env, "archive", "--from", "luiz", "--restore", month)
    assert r.returncode == 0 and r.stdout.startswith(f"restauradas 9 mensagens de archive/{month}/"), r.stdout
    assert not os.path.exists(os.path.join(tmp, "archive", month)), "pasta vazia do mes sai"
    reps = [f.split("-")[-1][:-5] for f in listing() if f not in files0]
    assert len(reps) == 2 and set(files0) <= set(listing()), reps
    for rid in reps:
        for a in ("claude", "codex", "hermes"): run(env, "read", rid, "--agent", a)
    after = snap()
    for c in cmds:
        if c.startswith("log"): continue  # o log mostra os 2 reports novos do luiz
        assert after[c] == before[c], (c, before[c], after[c])
    # --restore sem mes devolve tudo
    run(env, "archive", "--from", "luiz", "--older-than-days", "0.5")
    r = run(env, "archive", "--from", "luiz", "--restore")
    assert r.returncode == 0 and r.stdout.startswith("restauradas "), r.stdout
    assert not [x for x in os.listdir(os.path.join(tmp, "archive"))], os.listdir(os.path.join(tmp, "archive"))
    print("OK: archive (so o humano, dry-run nao move, abertos/recentes/nao lidos/missao pendente ficam, read acha arquivada, restore volta byte a byte)")

INDEX_PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1]); import a2a
reads = {"n": 0}; orig = a2a.read_msg
def counted(f):
    reads["n"] += 1; return orig(f)
a2a.read_msg = counted
st = a2a.panel_state(); st.pop("generated")
for x in st["agents"]: x.pop("age")  # depende do relogio
print(json.dumps({"state": st, "reads": reads["n"]}, sort_keys=True))
"""

def index_fase():
    """index.json (item 5): mesmas saidas com e sem indice num bus de 2.000, corrompido e ignorado e refeito,
    arquivo jogado direto no bus aparece, index check ok depois de send/ack/missao/archive/restore."""
    sys.path.insert(0, str(ROOT / "tests")); import measure_bus
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    measure_bus.seed_home(tmp, 2000)
    idx = os.path.join(tmp, "index.json")
    cmds = ("summary", "brief --agent codex --no-auto-status", "brief --agent hermes --limit 0 --no-auto-status",
            "inbox --agent codex --no-auto-status", "inbox --agent claude --no-auto-status", "log --limit 3000", "mission list")
    def outs(): return {c: run(env, *c.split()).stdout for c in cmds}
    def state():
        r = subprocess.run([sys.executable, "-c", INDEX_PROBE, str(ROOT)], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    def drop():
        if os.path.exists(idx): os.remove(idx)
    drop(); cold_state = state()  # sem indice: le todos os arquivos (e grava o indice)
    assert cold_state["reads"] >= 2000 and os.path.exists(idx), cold_state["reads"]
    warm_state = state()
    assert warm_state["reads"] == 0 and warm_state["state"] == cold_state["state"], "indice quente: nenhum arquivo do bus lido"
    ref = {}
    for c in cmds: drop(); ref[c] = run(env, *c.split()).stdout  # cada comando sem indice
    assert outs() == ref, "com indice as saidas sao iguais"
    assert all(ref[c] for c in cmds)
    # indice corrompido/estranho: ignorado e refeito, sem efeito visivel
    for junk in (b"{nao e json", b"", b'{"v": 2, "n": 1, "last": "", "msgs": []}', b'{"v":1,"n":"x","last":"","msgs":[]}',
                 b'[1, 2]', json.dumps({"v": 1, "n": 2000, "last": "zz", "msgs": [{"x": 1}]}).encode()):
        with open(idx, "wb") as f: f.write(junk)
        assert run(env, "summary").stdout == ref["summary"], junk
        assert json.load(open(idx, encoding="utf-8"))["n"] == 2000, junk
    with open(idx, "wb") as f: f.write(b"\x00\xff garbage")
    assert state()["state"] == cold_state["state"]
    r = run(env, "index", "check"); assert r.returncode == 0 and r.stdout.startswith("ok (2000 mensagens)"), r.stdout
    # arquivo jogado direto no bus (a2a antigo): aparece na chamada seguinte
    m = {"data": "2026-10-19T00:00:00Z", "task_id": "", "msg_id": "direto000001", "from": "hermes", "to": "codex", "project": "lagu",
         "in_reply_to": "", "kind": "question", "state": "", "result": "", "evidence": "", "pending": "", "next_action": "",
         "body": "escrito direto no bus"}
    with open(os.path.join(tmp, "bus", "20261019T000000Z-direto000001.json"), "w") as f: json.dump(m, f)
    r = run(env, "index", "check"); assert r.returncode == 1 and "desatualizado" in r.stdout, r.stdout
    assert "escrito direto no bus" in run(env, "inbox", "--agent", "codex", "--no-auto-status").stdout
    assert run(env, "index", "check").returncode == 0
    # send acrescenta ao indice sem precisar refazer; check ok depois de send/ack/missao/archive/restore
    n0 = json.load(open(idx))["n"]
    r = run(env, "send", "--from", "claude", "--to", "codex", "--project", "lagu", "--body", "novo", "--no-auto-status")
    mid = r.stdout.split()[1]; j = json.load(open(idx))
    assert j["n"] == n0 + 1 and j["msgs"][-1]["msg_id"] == mid and j["last"].endswith(mid + ".json"), j["last"]
    steps = (("ack", mid, "--from", "codex", "--no-auto-status"),
             ("mission", "new", "--project", "lagu", "--title", "idx", "--agents", "codex,hermes", "--from", "luiz"),
             ("archive", "--from", "luiz"), ("send", "--from", "hermes", "--to", "all", "--body", "depois do archive"),
             ("archive", "--from", "luiz", "--restore"), ("send", "--from", "codex", "--to", "luiz", "--body", "fim",
             "--state", "CONCLUIDO", "--reply-to", mid))
    for st in steps:
        r = run(env, *st); assert r.returncode == 0, (st, r.stderr)
        if st[0] == "mission" and st[1] == "new":
            mm = re.search(r"missao (\w+) criada", r.stdout).group(1)
            assert run(env, "mission", "approve", mm, "--agent", "codex", "--evidence", "ok").returncode == 0
        c = run(env, "index", "check"); assert c.returncode == 0, (st, c.stdout)
    # indice adulterado com n/last certos: so o check percebe
    j = json.load(open(idx)); j["msgs"][5]["body"] = "adulterado"
    with open(idx, "w") as f: json.dump(j, f)
    c = run(env, "index", "check"); assert c.returncode == 1 and "mensagens diferem" in c.stdout, c.stdout
    r = run(env, "index", "rebuild"); assert r.returncode == 0 and r.stdout.startswith("indice reconstruido: "), r.stdout
    assert run(env, "index", "check").returncode == 0
    # indice que nao da para gravar: tudo funciona igual
    os.remove(idx); os.mkdir(idx)
    assert run(env, "summary").stdout == run(env, "summary").stdout and run(env, "summary").returncode == 0
    r = run(env, "send", "--from", "claude", "--to", "codex", "--body", "sem indice", "--no-auto-status")
    assert r.returncode == 0 and "sem indice" in run(env, "inbox", "--agent", "codex", "--no-auto-status").stdout
    os.rmdir(idx)
    print("OK: index.json (2.000 msgs iguais com/sem indice, painel sem ler o bus, corrompido refeito, arquivo direto aparece, check apos send/ack/missao/archive/restore)")

def files_fase():
    """send --file (item 4): path/sha/lines certos, erro sem gravar, sem --file sem a chave, caminhos recusados,
    +Narq no brief, file: no --compact, /api/state com as mesmas chaves e /api/send sem files."""
    import hashlib
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=os.path.join(tmp, "home"), PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex"): run(env, "join", "--agent", ag)
    work = os.path.join(tmp, "work"); os.makedirs(os.path.join(work, "sub"))
    code = "".join(f"linha {i}\n" for i in range(1, 11)).encode()
    open(os.path.join(work, "a.py"), "wb").write(code); open(os.path.join(work, "sub", "b.py"), "wb").write(b"x\ny\n")
    outside = os.path.join(tmp, "fora.py"); open(outside, "wb").write(b"segredo\n")
    sha = lambda b: hashlib.sha1(b).hexdigest()[:6]
    bus = os.path.join(env["A2A_HOME"], "bus")
    last = [""]
    def send(*extra, cwd=work, frm="claude"):
        r = subprocess.run([sys.executable, str(A2A), "send", "--from", frm, "--to", "codex", "--body", "veja", "--no-auto-status", *extra],
                           capture_output=True, text=True, env=env, cwd=cwd)
        if r.returncode == 0: last[0] = r.stdout.split()[1]
        return r
    def last_msg():
        f = next(f for f in os.listdir(bus) if last[0] in f); return json.load(open(os.path.join(bus, f), encoding="utf-8"))
    # sem projeto: base = pasta atual
    r = send("--file", "a.py:3-5", "--file", "./sub//b.py", "--file", "a.py:7"); assert r.returncode == 0, r.stderr
    m = last_msg()
    assert m["files"] == [{"path": "a.py", "sha": sha(code), "lines": "3-5"}, {"path": "sub/b.py", "sha": sha(b"x\ny\n"), "lines": ""},
                          {"path": "a.py", "sha": sha(code), "lines": "7"}], m["files"]
    with_files = m["msg_id"]
    # sem --file: os mesmos 14 campos, sem a chave files
    r = send(); assert r.returncode == 0 and "files" not in last_msg() and len(last_msg()) == 14, last_msg()
    plain = last_msg()["msg_id"]
    # erros: nada gravado
    n0 = len(os.listdir(bus))
    for spec, err in (("nao_existe.py", "arquivo nao encontrado"), ("a.py:0-2", "fora do arquivo"), ("a.py:5-3", "fora do arquivo"),
                      ("a.py:9-11", "fora do arquivo"), ("../fora.py", "'..'"), ("sub/../a.py", "'..'"), (outside, "absoluto"),
                      ("/etc/passwd", "absoluto"), ("C:\\x\\a.py", "absoluto"), ("sub", "arquivo nao encontrado")):
        r = send("--file", "a.py", "--file", spec)
        assert r.returncode == 1 and err in r.stderr and len(os.listdir(bus)) == n0, (spec, r.returncode, r.stderr)
    if hasattr(os, "symlink"):
        os.symlink(outside, os.path.join(work, "link.py"))
        r = send("--file", "link.py"); assert r.returncode == 1 and "fora de" in r.stderr and len(os.listdir(bus)) == n0, r.stderr
    # projeto registrado: base = pasta do projeto (ou a copia do agente), nao a pasta atual
    run(env, "project", "add", "lagu", work)
    r = send("--project", "lagu", "--file", "sub/b.py:2", cwd=tmp); assert r.returncode == 0, r.stderr
    assert last_msg()["files"] == [{"path": "sub/b.py", "sha": sha(b"x\ny\n"), "lines": "2"}]
    wt = os.path.join(tmp, "work-claude"); os.makedirs(wt); open(os.path.join(wt, "c.py"), "wb").write(b"c\n")
    pj = os.path.join(env["A2A_HOME"], "projects.json"); ps = json.load(open(pj))
    ps[0]["worktrees"] = {"claude": {"path": wt, "branch": "dove/claude", "base": "main"}}; json.dump(ps, open(pj, "w"))
    r = send("--project", "lagu", "--file", "c.py", cwd=tmp); assert r.returncode == 0 and last_msg()["files"][0]["path"] == "c.py", r.stderr
    r = send("--project", "lagu", "--file", "a.py", cwd=work); assert r.returncode == 1 and "nao encontrado" in r.stderr, r.stderr  # a.py nao esta na copia
    # leitores: brief +Narq, --json, compact, read JSON, verify-files
    b = run(env, "brief", "--agent", "codex", "--limit", "0", "--no-auto-status").stdout
    line = next(l for l in b.splitlines() if with_files in l); assert line.endswith('"veja" +3arq'), line
    assert next(l for l in b.splitlines() if plain in l).endswith('"veja"'), b
    j = json.loads(run(env, "brief", "--agent", "codex", "--json", "--no-auto-status").stdout)
    assert [x.get("files") for x in j["new"][:2]] == [3, None], j["new"][:2]
    c = run(env, "read", with_files, "--compact").stdout.splitlines()
    assert c[-3:] == [f"file: a.py:3-5 sha={sha(code)}", f"file: sub/b.py sha={sha(b'x' + chr(10).encode() + b'y' + chr(10).encode())}",
                      f"file: a.py:7 sha={sha(code)}"], c
    assert json.loads(run(env, "read", with_files).stdout)["files"][0]["lines"] == "3-5"
    open(os.path.join(work, "a.py"), "ab").write(b"mais\n")
    v = subprocess.run([sys.executable, str(A2A), "read", with_files, "--compact", "--verify-files"], capture_output=True, text=True, env=env, cwd=work).stdout
    assert f"verify: a.py:3-5 sha={sha(code)} mudou desde a mensagem (agora {sha(code + b'mais' + chr(10).encode())})" in v and "verify: sub/b.py" in v and " ok" in v, v
    # painel: /api/state com as mesmas chaves e files dentro da mensagem; /api/send ignora files
    port = free_port(); p, tok = start_panel(env, port)
    try:
        st, data = req(port, "GET", "/api/state")
        assert set(data) == {"version", "agents", "registered", "human", "agent_meta", "messages", "messages_total",
                             "messages_has_more", "messages_project", "projects", "missions", "summary", "config", "generated"}, set(data)
        assert next(x for x in data["messages"] if x["msg_id"] == with_files)["files"][0]["path"] == "a.py"
        assert "files" not in next(x for x in data["messages"] if x["msg_id"] == plain)
        st, res = req(port, "POST", "/api/send", {"to": "codex", "body": "do painel", "files": [{"path": "x", "sha": "1", "lines": ""}]}, tok)
        last[0] = res["message"]["msg_id"]
        assert st == 200 and "files" not in res["message"] and "files" not in last_msg(), res
    finally:
        p.terminate(); p.wait(timeout=5)
    t = run(env, "onboard", "--agent", "codex").stdout
    assert "Para apontar código, use `--file caminho[:linhas]` em vez de colar o conteúdo na mensagem." in t, t
    print("OK: send --file (path/sha/lines, erro sem gravar, 14 campos sem --file, ../absoluto/symlink recusados, base no projeto/copia, +Narq, compact, verify, /api/state)")

PROMPT_INPROC = r"""
import os, subprocess, sys, time
mode, root = sys.argv[1], sys.argv[2]
if mode.startswith("clock+"):
    real = time.time; d = float(mode[6:]); time.time = lambda: real() + d
def boom(*a, **k): raise AssertionError("a2a prompt tentou executar um processo")
subprocess.Popen = subprocess.run = subprocess.call = subprocess.check_output = os.system = boom
for f in ("execv", "execvp", "execve", "spawnv", "spawnvp", "posix_spawn", "startfile"):
    if hasattr(os, f): setattr(os, f, boom)
sys.path.insert(0, root); import a2a
if mode == "core": a2a.AGENTS_MD_CORE += "- linha nova no nucleo.\n"
if mode == "role": a2a.PROMPT_ROLE = a2a.PROMPT_ROLE.replace("vigia do Dove", "vigia")
a2a.main(sys.argv[3:])
"""
def prompt_fase():
    """a2a prompt (item 3): camadas na ordem, prefixo sem data/estado e com o mesmo hash apesar de bus/status/relogio,
    hash muda com o nucleo/papel/agente/--for, cauda cortada, so leitura (cursor/status/bus intactos), nunca executa nada."""
    import hashlib
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex", "hermes"): run(env, "join", "--agent", ag)
    def inproc(mode, *args):
        r = subprocess.run([sys.executable, "-c", PROMPT_INPROC, mode, str(ROOT), *args], capture_output=True, env=env)
        assert r.returncode == 0, (mode, args, r.stderr.decode("utf-8", "replace"))
        return r.stdout.decode("utf-8")
    def send(*args):
        r = run(env, "send", "--no-auto-status", *args); assert r.returncode == 0, r.stderr; return r.stdout.split()[1]
    task = send("--from", "luiz", "--to", "codex", "--project", "lagu", "--body", "Migrar o webhook\nsegunda linha com detalhe")
    send("--from", "claude", "--to", "codex", "--project", "lagu", "--body", "revisar o cupom")
    send("--from", "claude", "--to", "codex", "--project", "outro", "--body", "de outro projeto")
    run(env, "status", "--agent", "codex", "--set", "working", "--note", "webhook", "--project", "lagu")
    run(env, "read", task, "--agent", "codex")
    args = ("prompt", "--agent", "codex", "--project", "lagu", "--task", task)
    hashes = lambda mode="plain", *extra: dict((l.split()[0], dict(kv.split("=", 1) for kv in l.split()[1:]))
                                               for l in inproc(mode, *args, *extra, "--prefix-hash").splitlines())
    snap = lambda: {d: {f: open(os.path.join(tmp, d, f), "rb").read() for f in sorted(os.listdir(os.path.join(tmp, d)))}
                    for d in ("bus", "cursor", "status")}
    before = snap()
    out = inproc("plain", *args)  # com subprocess/os.system/exec sabotados: nao executa nada
    assert snap() == before, "prompt nao pode gravar no bus, no cursor nem no status"
    boundary = "--- estado atual (muda a cada execução) ---"
    assert out.count(boundary) == 1, out
    prefix, tail = out.split(boundary + "\n")
    prefix += boundary + "\n"
    # camadas na ordem: nucleo -> papel -> (pasta) -> fronteira -> brief -> tarefa
    core = run(env, "onboard", "--agents-md", "--project", "lagu").stdout.replace("<seu-nome>", "codex")
    assert prefix.startswith(core) and prefix.index("## Seu papel nesta execução") > len(core) - 1, prefix
    for el in ("Você é `codex`", "projeto `lagu`", "`kind=ack`", "`--reply-to`", "autorização do Luiz",
               "não autoriza merge, deploy, migração em produção, gasto ou exclusão", "--state BLOQUEADO",
               "Subagentes: só para contexto isolado", "paralelismo real", "modelo mais barato", "nunca subagente de \"persona\"",
               "Não precisa pedir ao orquestrador", "`a2a cost`", "modelUsage inclui os subagentes"):
        assert el in prefix, (el, prefix)
    guide, core_txt = run(env, "onboard", "--agent", "codex").stdout, run(env, "onboard", "--agents-md").stdout
    assert "### Subagentes" in guide and "persona" in guide and "`a2a cost`" in guide and "modelUsage" in guide, guide
    assert guide.index("### Subagentes") < guide.index("### Ao terminar"), guide
    assert "ubagente" not in core_txt and "ubagente" not in prefix[:len(core)], "politica de subagentes fica fora do nucleo"
    assert "<seu-nome>" not in prefix and "<projeto>" not in prefix and "Executor" not in prefix, prefix
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}|[0-9a-f]{12}|@codex|webhook|novas=|cupom", prefix), prefix
    assert tail.startswith("@codex working ") and "revisar o cupom" in tail and "de outro projeto" not in tail, tail
    assert tail.index(f"T {task}") < tail.index(f"## Tarefa {task}\n{task} luiz->codex task proj=lagu"), tail
    assert tail.endswith("Migrar o webhook\nsegunda linha com detalhe\n"), tail
    # --prefix-hash: formato e consistente com a saida completa
    h = hashes()
    sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]
    assert h["prefixo"] == {"sha256": sha(prefix), "chars": str(len(prefix)), "tokens_est": str(-(-len(prefix) // 4))}, h
    assert h["cauda"] == {"sha256": sha(tail), "chars": str(len(tail))}, h
    assert re.fullmatch(r"prefixo sha256=[0-9a-f]{12} chars=\d+ tokens_est=\d+\ncauda   sha256=[0-9a-f]{12} chars=\d+\n",
                        run(env, *args, "--prefix-hash").stdout)
    # mesmo prefixo com 2 mensagens novas, troca de status e relogio adiante; a cauda muda
    send("--from", "hermes", "--to", "codex", "--project", "lagu", "--body", "nova 1")
    send("--from", "claude", "--to", "all", "--project", "lagu", "--body", "nova 2")
    run(env, "status", "--agent", "codex", "--set", "blocked", "--note", "falta a chave", "--project", "lagu", "--context", "85")
    h2 = hashes("clock+7200")
    assert h2["prefixo"] == h["prefixo"] and h2["cauda"]["sha256"] != h["cauda"]["sha256"], (h, h2)
    out2 = inproc("clock+7200", *args)
    assert out2.startswith(prefix) and "nova 1" in out2 and "falta a chave (stale, era blocked)" in out2 and " 2h " in out2, out2
    # muda o texto estrutural (nucleo, papel), o agente ou o --for: muda o hash do prefixo
    for mode, extra, ag in (("core", (), "codex"), ("role", (), "codex"), ("plain", ("--for", "codex"), "codex"), ("plain", (), "claude")):
        a = ["prompt", "--agent", ag, "--project", "lagu", "--prefix-hash", *extra]
        hp = dict(kv.split("=", 1) for kv in inproc(mode, *a).splitlines()[0].split()[1:])
        assert hp["sha256"] != h["prefixo"]["sha256"], (mode, extra, ag)
    f = run(env, *args, "--for", "codex").stdout
    assert "- Executor: `codex exec`" in f.split(boundary)[0], f
    # quase fixa: pasta do projeto registrado ou a copia do agente (estavel entre execucoes)
    work = os.path.join(tmp, "lagu"); os.makedirs(work); run(env, "project", "add", "lagu", work)
    p1 = run(env, *args).stdout.split(boundary)[0]
    assert f"Pasta do projeto: `{work}`." in p1 and p1.index("Pasta do projeto") > p1.index("## Seu papel"), p1
    pj = os.path.join(tmp, "projects.json"); ps = json.load(open(pj))
    ps[0]["worktrees"] = {"codex": {"path": work + "-codex", "branch": "dove/codex", "base": "main"}}; json.dump(ps, open(pj, "w"))
    p2 = run(env, *args).stdout.split(boundary)[0]
    assert f"Sua pasta de trabalho: `{work}-codex` (branch `dove/codex`)." in p2 and "Pasta do projeto" not in p2, p2
    assert p2 == run(env, *args).stdout.split(boundary)[0]
    # --max-tail-chars: corta o brief primeiro (cabecalho fica), depois a tarefa; 0 = sem corte
    for i in range(30): send("--from", "claude", "--to", "codex", "--project", "lagu", "--body", f"mensagem {i} " + "x" * 80)
    full = run(env, *args, "--max-tail-chars", "0").stdout.split(boundary + "\n")[1]
    assert len(full) > 1500 and "novas (a2a brief --limit 0 para todas)" in full and full == run(env, *args).stdout.split(boundary + "\n")[1], len(full)
    t4 = run(env, *args, "--max-tail-chars", "1500").stdout.split(boundary + "\n")[1]
    assert len(t4) <= 1500 and t4.startswith("@codex ") and "linhas do brief cortadas (a2a brief --agent codex --project lagu)" in t4, t4
    assert t4.endswith("segunda linha com detalhe\n"), t4
    t1 = run(env, *args, "--max-tail-chars", "150").stdout.split(boundary + "\n")[1]
    assert len(t1) <= 150 and t1.startswith("@codex ") and f"cortado em 150 chars (a2a read {task} --agent codex --compact)" in t1, t1
    # erros
    r = run(env, "prompt", "--agent", "codex", "--project", "lagu", "--task", "naoexiste"); assert r.returncode == 1 and "nao encontrada" in r.stderr, r.stderr
    assert run(env, "prompt", "--agent", "codex").returncode == 2 and run(env, "prompt", "--project", "lagu").returncode == 2
    r = run(env, "prompt", "--agent", "codex", "--project", "lagu", "--for", "bash"); assert r.returncode == 2, r.stderr
    h = run(env, "prompt", "--help").stdout
    assert "exemplos:\n" in h and "| codex exec -" in h and "--prefix-hash" in h and "nunca executa" in h, h
    print("OK: a2a prompt (camadas, prefixo sem data/estado com hash igual apos msgs/status/relogio, hash muda com nucleo/papel/agente/--for, pasta, corte, so leitura, nao executa nada)")

INSTR_INPROC = r"""
import sys
sys.path.insert(0, sys.argv[1]); import a2a
a2a.AGENTS_MD_CORE += "- linha nova no nucleo.\n"
a2a.main(sys.argv[2:])
"""
def instructions_fase():
    """a2a instructions / onboard --global-core / project which: arquivos globais com HOME temporario e overrides."""
    import glob as _glob
    tmp = tempfile.mkdtemp(); home = os.path.join(tmp, "home"); os.makedirs(home)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "HERMES_HOME")}
    env.update(HOME=home, USERPROFILE=home, A2A_HOME=os.path.join(tmp, "a2a"), PYTHONIOENCODING="utf-8")
    def a2a(*args, e=None, code=0):
        r = subprocess.run([sys.executable, str(A2A), *args], capture_output=True, env=e or env)
        out = r.stdout.decode("utf-8") + r.stderr.decode("utf-8")
        assert r.returncode == code, (args, r.returncode, out)
        return out
    claude, codex = os.path.join(home, ".claude", "CLAUDE.md"), os.path.join(home, ".codex", "AGENTS.md")
    B, E = "<!-- dove:inicio (gerado por a2a instructions; nao edite entre estes marcadores) -->", "<!-- dove:fim -->"
    rb = lambda p: open(p, "rb").read()
    # nucleo global: mesmo texto do nucleo do AGENTS.md, com o nome do agente e <projeto> explicado; curto e estavel
    core = a2a("onboard", "--agents-md"); g = a2a("onboard", "--agent", "claude", "--global-core")
    assert g == a2a("onboard", "--agent", "claude", "--global-core") and len(g.splitlines()) <= 12, g
    assert "<seu-nome>" not in g and "Seu nome: `claude`." in g and "`a2a project which`" in g and "Claude Code →" not in g, g
    for l in core.splitlines():
        if "Seu nome:" not in l and "Sem `a2a`" not in l: assert l.replace("<seu-nome>", "claude") in g.splitlines(), (l, g)
    cond = ("Este bloco só vale quando a pasta atual pertence a um projeto registrado no Dove: rode `a2a project which`; "
            "se ele falhar (exit 1) ou `a2a` não existir, ignore este bloco inteiro e trabalhe normalmente.")
    assert g.splitlines()[2] == cond and "Avise o Luiz" not in g, g  # a condicao vem logo depois do titulo
    assert not re.search(r"\d{4}-\d{2}-\d{2}", g)
    a2a("onboard", "--global-core", code=2); a2a("onboard", "--agent", "claude", "--global-core", "--project", "x", code=1)
    # dry-run nao grava nada
    out = a2a("instructions", "install", "--dry-run")
    assert "(dry-run) criado: " + claude in out and "+" + B in out and not os.path.exists(os.path.join(home, ".claude")), out
    assert not os.path.exists(os.path.join(tmp, "a2a", "instructions.json"))
    # do zero: cria arquivo e pasta; o bloco e o nucleo global entre marcadores
    os.makedirs(os.path.dirname(codex))
    orig = b"# minhas regras\r\nnao mexa\r\n\r\nfim sem quebra"  # CRLF, sem quebra no fim
    open(codex, "wb").write(orig)
    out = a2a("instructions", "install")
    assert f"claude: criado: {claude}" in out and f"codex: adicionado: {codex} (backup: {codex}.dove-bak-" in out, out
    assert rb(claude).decode("utf-8") == B + "\n" + g + E + "\n", rb(claude)
    cx = rb(codex)
    assert cx.startswith(orig + b"\r\n\r\n" + B.encode() + b"\r\n") and cx.endswith(E.encode() + b"\r\n"), cx
    assert b"\n" not in cx.replace(b"\r\n", b""), "CRLF virou LF"
    assert cx.decode("utf-8").replace("\r\n", "\n").endswith(a2a("onboard", "--agent", "codex", "--global-core") + E + "\n")
    baks = _glob.glob(codex + ".dove-bak-*"); assert len(baks) == 1 and rb(baks[0]) == orig, baks
    # idempotente
    out = a2a("instructions", "install"); assert out.count("ja atualizado") == 2, out
    assert rb(codex) == cx and len(_glob.glob(codex + ".dove-bak-*")) == 1
    # status
    st = a2a("instructions", "status")
    assert re.search(rf"claude +{re.escape(claude)}  existe=sim bloco=sim atualizado=sim backups=0", st), st
    assert re.search(rf"codex +{re.escape(codex)}  existe=sim bloco=sim atualizado=sim backups=1", st) and "backup: " + baks[0] in st, st
    assert "hermes" in st and "existe=nao bloco=nao atualizado=- backups=0" in st, st
    assert a2a("instructions", "check") == st.replace(st[st.index("hermes"):], "")  # check: claude,codex; sai 0 em dia
    # onboard --check: bloco global e secao do AGENTS.md do projeto
    assert "igual ao nucleo global de codex" in a2a("onboard", "--check", codex)
    pmd = os.path.join(tmp, "AGENTS.md")
    open(pmd, "w", encoding="utf-8").write("# Projeto\n\n" + a2a("onboard", "--agents-md", "--project", "lagu") + "\n## Outra\nx\n")
    assert "igual ao nucleo do AGENTS.md (projeto lagu)" in a2a("onboard", "--check", pmd)
    open(pmd, "w", encoding="utf-8").write("## Canal A2A — Dove\n\ntexto antigo\n")
    out = a2a("onboard", "--check", pmd, code=1); assert "divergente" in out and "+- Aprove missão só com evidência real." in out, out
    open(pmd, "w", encoding="utf-8").write("nada\n"); assert "sem bloco do Dove" in a2a("onboard", "--check", pmd, code=1)
    # o nucleo mudou: status mostra desatualizado; install troca o bloco no lugar, sem novo backup, resto intacto
    def inproc(*args):
        r = subprocess.run([sys.executable, "-c", INSTR_INPROC, str(ROOT), *args], capture_output=True, env=env)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace"); return r.stdout.decode("utf-8")
    open(codex, "ab").write(b"depois do bloco\r\n")  # o usuario escreveu depois do bloco
    assert "atualizado=nao" in inproc("instructions", "status", "--agents", "codex")
    out = inproc("instructions", "install")
    assert f"claude: atualizado: {claude}" in out and f"codex: atualizado: {codex}" in out and "backup" not in out, out
    new = rb(codex); assert new.startswith(orig + b"\r\n\r\n" + B.encode()) and b"- linha nova no nucleo.\r\n" + E.encode() + b"\r\ndepois do bloco\r\n" in new, new
    assert len(_glob.glob(codex + ".dove-bak-*")) == 1
    assert "atualizado=sim" in inproc("instructions", "status", "--agents", "codex") and "atualizado=nao" in a2a("instructions", "status", "--agents", "codex")
    out = a2a("instructions", "check", "--agents", "codex", code=1); assert "desatualizado" in out, out
    assert "divergente do nucleo global de codex" in a2a("onboard", "--check", codex, code=1)
    a2a("instructions", "install")  # volta ao nucleo atual
    # remove: so o bloco (e a linha em branco que ele pos); arquivo criado pelo Dove e vazio some (com a pasta)
    out = a2a("instructions", "remove", "--dry-run"); assert rb(codex).count(B.encode()) == 1 and os.path.exists(claude), out
    out = a2a("instructions", "uninstall")  # alias de remove
    assert f"claude: arquivo removido: {claude}" in out and f"codex: removido: {codex}" in out, out
    assert rb(codex) == orig + b"depois do bloco\r\n", rb(codex)
    assert not os.path.exists(claude) and not os.path.exists(os.path.dirname(claude))
    a2a("instructions", "check", code=1)
    assert "sem bloco" in a2a("instructions", "remove", "--agents", "codex") and "nao existe" in a2a("instructions", "remove", "--agents", "claude")
    # remove devolve o original exato (o usuario nao escreveu depois do bloco); backup continua um so
    open(codex, "wb").write(orig); a2a("instructions", "install", "--agents", "codex"); a2a("instructions", "remove", "--agents", "codex")
    assert rb(codex) == orig and len(_glob.glob(codex + ".dove-bak-*")) == 1
    # arquivo LF com conteudo e BOM: bloco em LF, BOM mantido (nunca acrescentado), conteudo fora dos marcadores intacto
    lf = "﻿regra global\n".encode("utf-8"); open(codex, "wb").write(lf)
    a2a("instructions", "install", "--agents", "codex"); x = rb(codex)
    assert x.startswith(lf + b"\n" + B.encode() + b"\n") and b"\r" not in x, x
    a2a("instructions", "remove", "--agents", "codex"); assert rb(codex) == lf
    a2a("instructions", "install", "--agents", "claude"); assert not rb(claude).startswith(b"\xef\xbb\xbf")
    # marcadores quebrados: erro e nada muda
    open(codex, "wb").write(b"x\n" + B.encode() + b"\nsem fim\n"); before = rb(codex)
    assert "sem o de fim" in a2a("instructions", "install", "--agents", "codex", code=1) and rb(codex) == before
    # overrides: CLAUDE_CONFIG_DIR / CODEX_HOME / HERMES_HOME; hermes so explicito, com nota
    e2 = dict(env, CLAUDE_CONFIG_DIR=os.path.join(tmp, "cc"), CODEX_HOME=os.path.join(tmp, "cx"), HERMES_HOME=os.path.join(tmp, "hh"))
    out = a2a("instructions", "install", e=e2)
    assert os.path.isfile(os.path.join(tmp, "cc", "CLAUDE.md")) and os.path.isfile(os.path.join(tmp, "cx", "AGENTS.md")), out
    assert "hermes" not in out and not os.path.exists(os.path.join(tmp, "hh")), out
    out = a2a("instructions", "install", "--agents", "hermes", e=e2)
    assert "hermes: criado: " + os.path.join(tmp, "hh", "SOUL.md") in out and "SOUL.md" in out and "--agents hermes" in out, out
    assert "Seu nome: `hermes`." in open(os.path.join(tmp, "hh", "SOUL.md"), encoding="utf-8").read()
    open(os.path.join(tmp, "cx", "AGENTS.override.md"), "w").write("temporario\n")
    assert "AGENTS.override.md" in a2a("instructions", "status", "--agents", "codex", e=e2)
    a2a("instructions", "install", "--agents", "gemini", e=e2, code=1)
    # project which: exato, subpasta, copia de trabalho, nenhum -> sai 1
    proj = os.path.join(tmp, "lagu"); os.makedirs(os.path.join(proj, "src", "a")); os.makedirs(proj + "-codex")
    a2a("project", "add", "lagu", proj); a2a("project", "add", "lagu-docs", os.path.join(proj, "src", "a"))
    pj = os.path.join(tmp, "a2a", "projects.json"); ps = json.load(open(pj))
    ps[0]["worktrees"] = {"codex": {"path": proj + "-codex", "branch": "dove/codex", "base": "main"}}; json.dump(ps, open(pj, "w"))
    assert a2a("project", "which", "--path", proj) == "lagu\n"
    assert a2a("project", "which", "--path", os.path.join(proj, "src")) == "lagu\n"
    assert a2a("project", "which", "--path", os.path.join(proj, "src", "a", "b")) == "lagu-docs\n"  # o mais especifico
    assert a2a("project", "which", "--path", proj + "-codex") == "lagu\n"
    assert subprocess.run([sys.executable, str(A2A), "project", "which"], capture_output=True, text=True, env=env,
                          cwd=os.path.join(proj, "src")).stdout == "lagu\n"
    out = a2a("project", "which", "--path", proj + "x", code=1); assert "nenhum projeto registrado contem" in out, out
    a2a("project", "which", "--path", tmp, code=1)
    sys.path.insert(0, str(ROOT)); import importlib; os.environ["A2A_HOME"] = os.path.join(tmp, "a2a")
    import a2a as mod; importlib.reload(mod)
    assert mod.project_which(proj.upper() + "/SRC", windows=True) == ("lagu", "")  # Windows: sem diferenciar maiusculas
    assert mod.project_which(proj.upper(), windows=False) == (None, "")
    assert mod.project_which(proj + "-codex/x", windows=True) == ("lagu", "codex")
    del os.environ["A2A_HOME"]
    print("OK: a2a instructions (cria, preserva fora dos marcadores, CRLF/BOM, idempotente, atualiza, 1 backup, remove exato, "
          "status, dry-run, overrides, hermes so explicito) + onboard --global-core + project which")

FACT_INPROC = r"""
import sys, time
fixed = float(sys.argv[2])
if fixed: time.time = lambda: fixed
sys.path.insert(0, sys.argv[1]); import a2a
a2a.main(sys.argv[3:])
"""
def fact_fase():
    """a2a fact (memoria do projeto): validacao, tetos, TTL com relogio injetado, escopos, condensacao, prune so do humano,
    linhas F no brief, nada muda sem memoria."""
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    NOW = time.time()
    def a2a(*args, now=0, code=0):
        r = subprocess.run([sys.executable, "-c", FACT_INPROC, str(ROOT), str(now), *args], capture_output=True, env=env)
        out = r.stdout.decode("utf-8") + r.stderr.decode("utf-8")
        assert r.returncode == code, (args, r.returncode, out)
        return out
    for ag in ("claude", "codex", "hermes"): a2a("join", "--agent", ag)
    task = a2a("send", "--from", "luiz", "--to", "codex", "--project", "lagu", "--body", "rodar contrato").split()[1]
    a2a("read", task, "--agent", "codex")
    a2a("status", "--agent", "codex", "--set", "working", "--note", "x", "--project", "lagu")
    brief = lambda *x, now=NOW: a2a("brief", "--agent", "codex", "--no-auto-status", *x, now=now)
    # sem memoria: brief, brief --json e brief --project sem nenhuma linha/chave nova; a pasta memory/ nao nasce sozinha
    plain = {x: brief(*x) for x in ((), ("--json",), ("--project", "lagu"), ("--project", "lagu", "--json"))}
    assert not any(l.startswith("F ") for v in plain.values() for l in v.splitlines()) and '"facts"' not in plain[("--json",)]
    a2a("fact", "list", "--project", "lagu"); a2a("summary"); assert not os.path.exists(os.path.join(tmp, "memory"))
    nbus = len(os.listdir(os.path.join(tmp, "bus")))
    # validacao
    add = lambda *x, code=0, now=NOW, who="claude": a2a("fact", "add", "--project", "lagu", "--from", who, *x, code=code, now=now)
    for bad, msg in ((("x" * 201,), "201 caracteres"), (("linha 1\nlinha 2",), "uma linha so"), (("tab\x07",), "controle"),
                     (("--scope", "geral", "x"), "escopo invalido"), (("--scope", "missao:mnaoexis", "x"), "nao encontrada"),
                     (("--scope", "tarefa:naoexiste", "x"), "nao e uma tarefa"), (("--ttl", "91d", "x"), "maximo de 90d"),
                     (("--ttl", "3x", "x"), "--ttl invalido"), (("--scope", f"tarefa:{task}", "--ttl", "8d", "x"), "maximo de 7d"),
                     (("",), "vazio")):
        assert msg in add(*bad, code=1), (bad, msg)
    assert not os.path.exists(os.path.join(tmp, "memory", "lagu.jsonl"))
    out = add("--ttl", "30d", "--source", "9be1c0a", 'Webhook usa X-Signature "HMAC"; a antiga vale ate 2026-10-26')
    m = re.fullmatch(r"fato (f[0-9a-f]{5}) \(lagu, projeto\) vale até (\d{4}-\d{2}-\d{2}) · vigentes 1/30, 60/3000 chars\n", out)
    assert m and m.group(2) == time.strftime("%Y-%m-%d", time.gmtime(NOW + 30 * 86400)), out
    f1 = m.group(1)
    line = json.loads(open(os.path.join(tmp, "memory", "lagu.jsonl"), encoding="utf-8").read().splitlines()[0])
    assert {k: line[k] for k in ("v", "id", "project", "scope", "by", "source", "state")} == {"v": 1, "id": f1, "project": "lagu",
        "scope": "projeto", "by": "claude", "source": "9be1c0a", "state": "vigente"} and "'HMAC'" in line["text"], line
    assert len(os.listdir(os.path.join(tmp, "bus"))) == nbus, "fato nao vai para o bus"
    f_h = add("--ttl", "1h", "valido por uma hora").split()[1]
    out = add("--scope", f"tarefa:{task}", "contrato em tests/contract", who="hermes"); f_t = out.split()[1]
    assert "vale até fechar (no máximo " in out, out
    mid = a2a("mission", "new", "--project", "lagu", "--title", "Frete", "--agents", "codex,claude").split()[1]
    f_m = add("--scope", f"missao:{mid}", "Cupom frete gratis: limite R$ 199", who="codex").split()[1]
    assert "vale até concluir (no máximo" in add("--scope", f"missao:{mid}", "segundo fato da missao", who="codex")
    b = brief("--project", "lagu")
    fl = [l for l in b.splitlines() if l.startswith("F ")]
    assert fl[0] == f"F {f1} \"Webhook usa X-Signature 'HMAC'; a antiga vale ate 2026-10-26\"" and fl[1] == f'F {f_h} "valido por uma hora"', fl
    assert fl[2] == f'F {f_t} {task} "contrato em tests/contract"' and fl[3] == f'F {f_m} {mid} "Cupom frete gratis: limite R$ 199"', fl
    ls = b.splitlines(); assert ls.index(fl[0]) > max(i for i, l in enumerate(ls) if l.startswith(("M ", "T "))), b
    assert re.fullmatch(r"@codex working ctx=- novas=\d+ abertas=\d+ aval=\d+", b.splitlines()[0]), b  # cabecalho igual ao de sempre
    j = json.loads(brief("--project", "lagu", "--json"))
    assert j["facts"][0] == {"id": f1, "scope": "projeto", "text": "Webhook usa X-Signature 'HMAC'; a antiga vale ate 2026-10-26"}, j
    assert not any(l.startswith("F ") for l in brief().splitlines()) and '"facts"' not in brief("--json")  # sem --project
    assert not any(l.startswith("F ") for l in brief("--project", "lagu", "--facts", "0").splitlines())
    b2 = brief("--project", "lagu", "--facts", "2"); assert sum(l.startswith("F ") for l in b2.splitlines()) == 2
    assert "… +3 fatos (a2a fact list --project lagu)" in b2, b2
    assert not any(l.startswith("F ") for l in a2a("brief", "--agent", "codex", "--project", "outro", "--no-auto-status").splitlines())
    # list: formato, escopo, rodape
    lst = a2a("fact", "list", "--project", "lagu", now=NOW)
    assert re.search(rf"^{f1} projeto +até \d{{4}}-\d\d-\d\d  claude  Webhook .* \[9be1c0a\]$", lst, re.M), lst
    assert re.search(rf"^{f_t} tarefa:{task[:6]}… +até fechar +hermes  contrato", lst, re.M) and f"missao:{mid} até concluir" in lst, lst
    tot = sum(len(json.loads(l)["text"]) for l in open(os.path.join(tmp, "memory", "lagu.jsonl"), encoding="utf-8"))
    assert lst.rstrip().endswith(f"5 vigentes · {tot}/3.000 chars"), lst
    assert a2a("fact", "list", "--project", "lagu", "--scope", f"missao:{mid}").count("\n") == 3
    # TTL de 1h com relogio injetado: some do brief depois de 1h (sem regravar o arquivo)
    raw = open(os.path.join(tmp, "memory", "lagu.jsonl"), "rb").read()
    assert f_h in brief("--project", "lagu", now=NOW + 3500) and f_h not in brief("--project", "lagu", now=NOW + 3700)
    assert open(os.path.join(tmp, "memory", "lagu.jsonl"), "rb").read() == raw
    assert "1 vencidos (a2a fact list --project lagu --all)" in a2a("fact", "list", "--project", "lagu", now=NOW + 3700)
    # heartbeat: add/expire renovam sem mudar estado nem nota; list nao
    st = lambda: json.load(open(os.path.join(tmp, "status", "codex.json")))
    s0 = st(); a2a("fact", "list", "--project", "lagu", now=NOW + 50); assert st() == s0
    a2a("fact", "expire", f_h, "--from", "codex", "--reason", "nao vale mais", now=NOW + 60)
    assert st()["state"] == "working" and st()["note"] == "x" and st()["ts"] == NOW + 60, st()
    assert "ja esta vencido" in a2a("fact", "expire", f_h, "--from", "codex", code=1)
    assert "nao encontrado" in a2a("fact", "expire", "fabcde", "--from", "codex", code=1)
    # tarefa: some quando chega o CONCLUIDO com --reply-to
    a2a("send", "--from", "codex", "--to", "luiz", "--project", "lagu", "--reply-to", task, "--kind", "report", "--state", "CONCLUIDO", "--body", "ok")
    assert f_t not in brief("--project", "lagu")
    assert "ja foi fechada" in add("--scope", f"tarefa:{task}", "tarde demais", code=1)
    # teto: 30 fatos vigentes e 3.000 chars
    assert "ainda nao foi concluida" in a2a("fact", "condense", "--mission", mid, "--from", "codex", "--line", "x", code=1)
    n = int(re.search(r"(\d+) vigentes", a2a("fact", "list", "--project", "lagu")).group(1))
    for i in range(30 - n): add(f"fato de enchimento {i:02d}")
    out = add("o trigesimo primeiro", code=1)
    assert "lagu já tem 30 fatos vigentes (teto 30). Vença um (a2a fact expire <id> --from claude) ou condense uma missão concluída" in out, out
    tmp2 = tempfile.mkdtemp(); env2 = dict(env, A2A_HOME=tmp2)
    for i in range(15):
        r = subprocess.run([sys.executable, str(A2A), "fact", "add", "--project", "big", "--from", "claude", "y" * 199], env=env2, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr  # 15 x 199 = 2985 chars
    r = subprocess.run([sys.executable, str(A2A), "fact", "add", "--project", "big", "--from", "claude", "z" * 100], env=env2, capture_output=True, text=True)
    assert r.returncode == 1 and "passaria de 3000 chars vigentes (2985 + 100)" in r.stderr, r.stderr
    # missao concluida: o alerta vai so para o primeiro agente (missao criada pelo humano); condense resume e tira do brief
    for ag in ("codex", "claude"): a2a("mission", "approve", mid, "--agent", ag, "--evidence", "ok")
    a2a("mission", "done", mid, "--from", "luiz")
    alert = f"! missão {mid} concluída com 2 fatos: condensar (a2a fact condense --mission {mid} ...)"
    assert alert in brief("--project", "lagu") and f_m not in brief("--project", "lagu", "--facts", "0")
    assert alert not in a2a("brief", "--agent", "claude", "--project", "lagu", "--no-auto-status")
    assert alert not in brief(), "sem --project nada de memoria"
    for i in range(2): a2a("fact", "expire", re.search(r"^(f[0-9a-f]{5}) projeto .*enchimento", a2a("fact", "list", "--project", "lagu"), re.M).group(1), "--from", "luiz")
    assert "de 1 a 3 --line" in a2a("fact", "condense", "--mission", mid, "--from", "codex", *sum((["--line", f"l{i}"] for i in range(4)), []), code=1)
    assert "(maximo 200)" in a2a("fact", "condense", "--mission", mid, "--from", "codex", "--line", "a" * 120, "--line", "b" * 90, code=1)
    out = a2a("fact", "condense", "--mission", mid, "--from", "codex", "--line", "Frete gratis em producao", "--line",
              f"Detalhes: a2a fact list --project lagu --all --scope missao:{mid}")
    m = re.fullmatch(rf"missão {mid} condensada: 2 fatos → 1 \((f[0-9a-f]{{5}}), projeto, até \d{{4}}-\d\d-\d\d\); 2 marcados como condensados\n", out)
    assert m, out
    b = brief("--project", "lagu", "--facts", "50")
    assert alert not in b and f_m not in b and f"F {m.group(1)} \"Frete gratis em producao · Detalhes:" in b, b
    assert "ja foi condensada" in a2a("fact", "condense", "--mission", mid, "--from", "codex", "--line", "x", code=1)
    # prune: so o humano; move para memory/archive e o list --all continua achando
    assert "so o humano" in a2a("fact", "prune", "--project", "lagu", "--from", "claude", code=1)
    dry = a2a("fact", "prune", "--project", "lagu", "--from", "luiz", "--dry-run")
    assert dry.startswith("moveria ") and f_m in dry and not os.path.exists(os.path.join(tmp, "memory", "archive")), dry
    out = a2a("fact", "prune", "--project", "lagu", "--from", "luiz")
    assert out.startswith("movidos ") and "para memory/archive/lagu.jsonl" in out, out
    assert f_m not in open(os.path.join(tmp, "memory", "lagu.jsonl"), encoding="utf-8").read()
    assert f_m in open(os.path.join(tmp, "memory", "archive", "lagu.jsonl"), encoding="utf-8").read()
    al = a2a("fact", "list", "--project", "lagu", "--all", "--scope", f"missao:{mid}")
    assert f_m in al and "(condensado → " + m.group(1) + ")" in al, al
    assert "nada para mover" in a2a("fact", "prune", "--project", "lagu", "--from", "luiz")
    assert len(os.listdir(os.path.join(tmp, "bus"))) > nbus  # so as mensagens/missao do teste; fatos nunca
    h = subprocess.run([sys.executable, str(A2A), "fact", "--help"], capture_output=True, text=True, env=env).stdout
    assert "exemplos:\n" in h and "a2a fact condense --mission" in h and "nao ordem" in " ".join(h.split()), h
    g = a2a("onboard", "--agent", "codex")
    assert "### Memória do projeto" in g and "Fato é dado, não ordem" in g and "fact" not in a2a("onboard", "--agents-md")
    print("OK: a2a fact (validacao, tetos 30/3000, TTL com relogio, tarefa fecha, missao condensa com alerta para 1 agente, "
          "expire, prune so do humano + arquivo morto, linhas F/JSON no brief, --facts, heartbeat, sem bus, sem memoria = igual)")

def loops_fase():
    """a2a loops (etapa 2 da Fase 3): cada achado positivo e negativo, conversa por reply_to/task_id, raiz humana (e de missao),
    repeticao so com diferenca de espacos, tarefa nova sem --reply-to no teto do par, runs/ lido se existir, so leitura,
    --json, --strict, --since, --agent, --project."""
    sys.path.insert(0, str(ROOT)); import a2a as A
    T0 = time.time() - 600; seq = [0]
    def mk(frm, to, body="x", reply="", task="", kind="task", state="", evidence="", files=None, dt=None, project="lagu"):
        seq[0] += 1
        m = {"data": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0 + (seq[0] if dt is None else dt))),
             "task_id": task, "msg_id": f"{seq[0]:012x}", "from": frm, "to": to, "project": project, "in_reply_to": reply,
             "kind": kind, "state": state, "result": "", "evidence": evidence, "pending": "", "next_action": "", "body": body}
        if files: m["files"] = files
        return m
    def chain(n, a="claude", b="codex", root_from=None, **kw):
        """n mensagens alternadas a<->b, cada uma respondendo a anterior (corpos diferentes)."""
        ms = [mk(root_from or a, b, "comeco")]
        for i in range(n - 1):
            prev = ms[-1]; frm = b if prev["from"] in (a, root_from) and prev["to"] == b else a
            to = a if frm == b else b
            ms.append(mk(frm, to, f"msg {i}", reply=prev["msg_id"], **kw))
        return ms
    kinds = lambda r: sorted(f["kind"] for f in r["findings"])
    chk = lambda ms, **kw: A.loop_check(ms, human="luiz", **kw)
    # rodadas: 6 entre agentes numa conversa de origem humana -> achado; 5 -> nada; mensagem do humano zera
    root = mk("luiz", "claude", "comeca ai")
    def rounds(n, extra=()):
        ms, prev = [root], root
        for i in range(n):
            a, b = ("claude", "codex") if i % 2 == 0 else ("codex", "claude")
            m = mk(a, b, f"r{i}", reply=prev["msg_id"], state="EM_EXECUCAO" if i == 0 else "", evidence=f"ev{i}"); ms.append(m); prev = m
            if i in extra: m = mk("luiz", "claude", f"humano {i}", reply=prev["msg_id"]); ms.append(m); prev = m
        return ms
    r = chk(rounds(6)); assert kinds(r) == ["rodadas"], r
    f = r["findings"][0]; assert f["root"] == root["msg_id"] and f["agents"] == ["claude", "codex"] and f["count"] == 6, f
    assert kinds(chk(rounds(5))) == [] and kinds(chk(rounds(8, extra=(3,)))) == [], "humano no meio zera as rodadas"
    assert kinds(chk(rounds(6), limits={"rounds": 7})) == []
    # report de agente para o humano nao conta como rodada nem zera; acks nao contam
    ms = rounds(5); ms.append(mk("codex", "luiz", "relatorio", reply=ms[-1]["msg_id"], kind="report"))
    ms.append(mk("claude", "codex", "ok", reply=ms[-2]["msg_id"], kind="ack"))
    assert kinds(chk(ms)) == []
    ms.append(mk("claude", "codex", "mais uma", reply=ms[-3]["msg_id"], evidence="nova")); assert kinds(chk(ms)) == ["rodadas"]
    # conversa = reply_to transitivo + mesmo task_id
    a1 = mk("luiz", "codex", "tarefa", task="t1"); others = [mk("codex", "claude", f"q{i}", task="t1", evidence=f"e{i}") for i in range(6)]
    r = chk([a1] + others); assert kinds(r) == ["rodadas"] and r["findings"][0]["root"] == a1["msg_id"], r
    assert len(A.loop_conversations([a1] + others)) == 1 and len(A.loop_conversations([a1, mk("codex", "claude", "solta")])) == 2
    # sem origem humana: raiz de agente com 4 saltos -> achado; 3 -> nada; raiz humana -> nada; missao do humano -> nada
    def agent_rooted(n, task=""):
        ms = [mk("codex", "claude", "raiz do agente", task=task, evidence="e-raiz")]
        for i in range(n - 1):
            a, b = ("claude", "codex") if i % 2 == 0 else ("codex", "claude")
            ms.append(mk(a, b, f"s{i}", reply=ms[-1]["msg_id"], evidence=f"e{i}"))
        return ms
    r = chk(agent_rooted(4)); assert kinds(r) == ["sem-origem-humana"] and "raiz de codex, saltos=4/4" in r["findings"][0]["detail"], r
    assert kinds(chk(agent_rooted(3))) == []
    hr = agent_rooted(4); hr[0] = dict(hr[0], **{"from": "luiz"}); assert kinds(chk(hr)) == []
    assert kinds(chk(agent_rooted(4, task="mabc1234"), missions={"mabc1234": "luiz"})) == []
    assert kinds(chk(agent_rooted(4, task="mabc1234"), missions={"mabc1234": "codex"})) == ["sem-origem-humana"]
    # repeticao: so espacos diferentes = repeticao; texto diferente nao; humano repetindo nao
    rt = mk("luiz", "claude", "vai")
    a = mk("claude", "codex", "pode  revisar\no PR?", reply=rt["msg_id"], evidence="e1")
    b = mk("claude", "codex", " pode revisar o\tPR? ", reply=a["msg_id"], evidence="e2")
    r = chk([rt, a, b]); assert kinds(r) == ["repeticao"] and r["findings"][0]["count"] == 2 and r["findings"][0]["agents"] == ["claude"], r
    assert r["findings"][0]["msg_ids"] == [a["msg_id"], b["msg_id"]]
    c = mk("claude", "codex", "pode revisar o PR?!", reply=a["msg_id"]); assert kinds(chk([rt, a, c])) == []
    d = mk("claude", "codex", "Pode revisar o PR?", reply=a["msg_id"]); assert kinds(chk([rt, a, d])) == [], "so espacos sao normalizados"
    e = mk("codex", "claude", "pode revisar o PR?", reply=a["msg_id"]); assert kinds(chk([rt, a, e])) == [], "outro remetente"
    h1, h2 = mk("luiz", "claude", "e ai?"), None; h2 = mk("luiz", "claude", "e  ai?", reply=h1["msg_id"]); assert kinds(chk([h1, h2])) == []
    other = mk("claude", "codex", "pode revisar o PR?", evidence="z"); assert kinds(chk([rt, a, other])) == [], "outra conversa"
    # ping-pong: 4 alternadas sem progresso -> achado; com estado rumo a CONCLUIDO, evidencia nova ou arquivo novo -> nada
    def pp(n, mid=None, root_from="luiz"):
        ms = [mk(root_from, "claude", "comeco")]; prev = None
        for i in range(n):
            a_, b_ = ("claude", "codex") if i % 2 == 0 else ("codex", "claude")
            kw = mid(i) if mid else {}
            m = mk(a_, b_, f"p{i}", reply=ms[-1]["msg_id"], **kw); ms.append(m)
        return ms
    r = chk(pp(4)); assert kinds(r) == ["pingpong"] and r["findings"][0]["count"] == 4 and r["findings"][0]["agents"] == ["claude", "codex"], r
    assert kinds(chk(pp(3))) == []
    assert kinds(chk(pp(4, lambda i: {"state": ["ACEITO", "", "EM_EXECUCAO", ""][i]}))) == []
    assert kinds(chk(pp(4, lambda i: {"evidence": "commit abc" if i == 2 else ""}))) == []
    assert kinds(chk(pp(4, lambda i: {"files": [{"path": "x.py", "sha": f"{i:06x}", "lines": ""}]}))) == []
    assert kinds(chk(pp(4, lambda i: {"state": "BLOQUEADO"} if i else {"state": "BLOQUEADO"}))) == ["pingpong"], "BLOQUEADO nao e progresso"
    assert kinds(chk(pp(4, lambda i: {"evidence": "mesma"}))) == [], "a primeira evidencia conta como progresso"
    assert kinds(chk(pp(5, lambda i: {"evidence": "mesma"}))) == ["pingpong"], "a mesma evidencia repetida nao e progresso"
    assert kinds(chk(pp(4, lambda i: {"state": "CONCLUIDO"} if i == 3 else {}))) == []
    # tetos por hora: agente, par (tarefa nova sem --reply-to conta) e global
    tasks = [mk("claude", "codex", f"tarefa nova {i}", dt=60 * i) for i in range(9)]  # 9 raizes, nenhuma com reply_to
    r = chk(tasks); f = [x for x in r["findings"] if x["kind"] == "teto"]
    assert len(f) == 1 and f[0]["scope"] == "par" and f[0]["agents"] == ["claude", "codex"] and "par claude>codex 9/8 por hora" in f[0]["detail"], r
    assert kinds(chk(tasks[:8])) == []
    spread = [mk("claude", "codex", f"tarefa {i}", dt=500 * i) for i in range(9)]  # 9 em 4000s: nunca 9 na mesma hora
    assert kinds(chk(spread)) == []
    many = [mk("claude", ["codex", "hermes", "ana", "bia"][i % 4], f"n{i}", dt=10 * i) for i in range(13)]
    f = [x for x in chk(many)["findings"] if x["kind"] == "teto"]; assert [x["scope"] for x in f] == ["agente"] and "agente claude 13/12" in f[0]["detail"], f
    crowd = [mk(f"ag{i % 5}", f"bg{i % 7}", f"g{i}", dt=5 * i) for i in range(31)]
    f = [x for x in chk(crowd)["findings"] if x["kind"] == "teto"]; assert [x["scope"] for x in f] == ["global"] and f[0]["agents"] == ["*"], f
    hum = [mk("luiz", "codex", f"humano {i}", dt=i) for i in range(40)]; assert kinds(chk(hum)) == [], "humano nao conta nos tetos"
    acks = [mk("claude", "codex", "ok", kind="ack", dt=i) for i in range(40)]; assert kinds(chk(acks)) == [], "ack nao conta"
    # since e now: janela fora do periodo nao conta
    assert kinds(chk(tasks, now=T0 + 600 + 3 * 3600, since=1)) == []
    assert kinds(chk(tasks, since=2)) == ["teto"]
    # runs: gatilhos ja acionados
    r = chk(pp(4), runs=[{"trigger_ids": [pp(4)[0]["msg_id"]]}, "lixo", {"trigger_ids": "x"}])
    assert r["runs"] == 3 and r["findings"][0].get("acted") == 0 and len(r["acted_on"]) == 1, r
    ms = pp(4); r = chk(ms, runs=[{"trigger_ids": [ms[1]["msg_id"], ms[2]["msg_id"]]}]); assert r["findings"][0]["acted"] == 2
    assert chk(ms)["runs"] is None and "acted" not in chk(ms)["findings"][0]
    print("OK: loop_check puro (rodadas, repeticao, pingpong, sem-origem-humana, tetos agente/par/global, since, runs)")

    # CLI num bus de verdade (arquivos gravados como o send grava), so leitura
    tmp = tempfile.mkdtemp(); env = dict(os.environ, A2A_HOME=tmp, PYTHONIOENCODING="utf-8")
    for ag in ("claude", "codex"): run(env, "join", "--agent", ag)
    def put(ms):
        for m in ms:
            fn = m["data"].replace(":", "").replace("-", "") + "-" + m["msg_id"] + ".json"
            p = os.path.join(tmp, "bus", fn); json.dump(m, open(p, "w", encoding="utf-8"))
            t = A.msg_epoch(m); os.utime(p, (t, t))
    os.makedirs(os.path.join(tmp, "bus"), exist_ok=True)
    clean = run(env, "loops"); assert clean.returncode == 0 and clean.stdout == "loops: 0 achados (rodadas>=6: 0, repeticao: 0, pingpong: 0, sem-origem-humana: 0, teto: 0)\n", clean.stdout
    assert run(env, "loops", "--strict").returncode == 0
    put(pp(4) + tasks + [mk("codex", "claude", "x", project="outro", evidence="e"), *agent_rooted(4)])
    run(env, "send", "--from", "luiz", "--to", "claude", "--project", "lagu", "--body", "mensagem pelo send")  # indice valido
    run(env, "read", os.listdir(os.path.join(tmp, "bus"))[0][-17:-5], "--agent", "claude")
    run(env, "status", "--agent", "claude", "--set", "working", "--note", "x")
    def snap():
        out = {}
        for d in ("bus", "cursor", "status", "agents"):
            for f in sorted(os.listdir(os.path.join(tmp, d))): out[d + "/" + f] = open(os.path.join(tmp, d, f), "rb").read()
        out["index"] = open(os.path.join(tmp, "index.json"), "rb").read() if os.path.exists(os.path.join(tmp, "index.json")) else None
        out["dirs"] = sorted(os.listdir(tmp)); return out
    run(env, "index", "rebuild"); before = snap(); time.sleep(0.05)
    out = run(env, "loops")
    assert out.returncode == 0, out.stderr
    assert snap() == before, "loops nao pode gravar bus, cursor, status, agentes nem index.json"
    lines = out.stdout.splitlines()
    assert all(re.fullmatch(r"LOOP (rodadas|repeticao|pingpong|sem-origem-humana|teto) (\S+) \S+ .+", l) for l in lines[:-1]), lines
    assert lines[-1] == "loops: 4 achados (rodadas>=6: 0, repeticao: 0, pingpong: 1, sem-origem-humana: 1, teto: 2)", lines
    assert any(l.startswith("LOOP teto - claude,codex par claude>codex 13/8 por hora") for l in lines), lines
    assert any(l.startswith("LOOP teto - claude agente claude 13/12 por hora") for l in lines), lines
    assert run(env, "loops", "--strict").returncode == 1
    j = run(env, "loops", "--json"); d = json.loads(j.stdout)
    assert j.stdout.count("\n") == 1 and ": " not in j.stdout and d["total"] == 4 and d["counts"]["teto"] == 2 and d["limits"]["rounds"] == 6, j.stdout
    assert json.loads(run(env, "loops", "--project", "outro", "--json").stdout)["total"] == 0
    ag = json.loads(run(env, "loops", "--agent", "codex", "--json").stdout); assert ag["total"] == 3
    assert json.loads(run(env, "loops", "--agent", "hermes", "--json").stdout)["total"] == 0
    # indice desatualizado: loops rele o bus, mas nao regrava o index.json
    open(os.path.join(tmp, "index.json"), "w").write("{}"); before = snap()
    assert run(env, "loops").stdout == out.stdout and snap() == before
    # runs/ (do vigia, futuro): lido se existir, so leitura; arquivo ruim ignorado
    os.makedirs(os.path.join(tmp, "runs", "2026-10")); f0 = d["findings"][0]
    json.dump({"trigger_ids": [f0["root"]]}, open(os.path.join(tmp, "runs", "2026-10", "r1.json"), "w"))
    open(os.path.join(tmp, "runs", "2026-10", "ruim.json"), "w").write("{nao json")
    before = snap(); o2 = run(env, "loops")
    assert "runs: 1 execucoes do vigia lidas, 1 gatilhos ja acionados" in o2.stdout and snap() == before, o2.stdout
    assert any(l.startswith(f"LOOP {f0['kind']} {f0['root']} ") and l.endswith("(ja acionadas: 1)") for l in o2.stdout.splitlines()), o2.stdout
    # A2A_HOME que nao existe continua nao existindo
    ghost = os.path.join(tempfile.mkdtemp(), "nada"); r = run(dict(env, A2A_HOME=ghost), "loops")
    assert r.returncode == 0 and "loops: 0 achados" in r.stdout and not os.path.exists(ghost), (r.stdout, r.stderr)
    h = run(env, "loops", "--help").stdout
    assert "exemplos:\n" in h and "a2a loops --project lagu --since 24" in h and "--strict" in h, h
    g = run(env, "onboard", "--agent", "codex").stdout
    assert "a2a loops" in g and "loops" not in run(env, "onboard", "--agents-md").stdout
    print("OK: a2a loops (linhas LOOP + resumo, --json, --strict, --project, --agent, runs/, so leitura: bus/cursor/status/indice intactos)")

FAKE_CLI = r'''
import json, os, sys
name, args = os.path.splitext(os.path.basename(sys.argv[0]))[0], sys.argv[1:]
with open(os.environ["FAKE_SPY"], "a", encoding="utf-8") as f: f.write(json.dumps([name] + args) + "\n")
old = os.environ.get("FAKE_CLAUDE_OLD") == "1"
if args == ["--version"]:
    print({"claude": "2.1.300 (Claude Code)", "codex": "codex-cli 0.50.0", "hermes": "Hermes Agent v0.9.0"}[name])
elif name == "claude" and args == ["auth", "status"]:
    m = os.environ.get("FAKE_CLAUDE_AUTH", "claude.ai"); print(json.dumps({"loggedIn": m != "none", "authMethod": m}))
    sys.exit(1 if m == "none" else 0)
elif args == ["--help"]:
    print("Usage: claude [options]\n  --permission-mode <mode>\n" + ("" if old else "  --permission-prompts <target>\n"))
else:
    print("fake: comando inesperado", args, file=sys.stderr); sys.exit(3)
'''
WATCH_INPROC = r"""
import sys
mode, root = sys.argv[1], sys.argv[2]
sys.path.insert(0, root); import a2a
if "win" in mode: a2a._watch_windows = lambda: True
if "bad" in mode: a2a.WATCH_RUNNERS["claude"]["allow"] += ("Bash(python *)", "Bash(git push *)")
if mode == "table":
    import json; print(json.dumps({"bad": a2a.watch_forbidden(), "runners": {k: {"argv": list(v["argv"]), "allow": list(v["allow"]),
          "mode": v["permission_mode"], "enabled": v["enabled"]} for k, v in a2a.WATCH_RUNNERS.items()},
          "subcmds": list(a2a.WATCH_A2A_SUBCMDS)})); sys.exit(0)
a2a.main(sys.argv[3:])
"""
def watch_fase():
    """a2a watch check (etapa 5 da Fase 3): so leitura, executaveis falsos num PATH temporario, espiao de argv."""
    import shutil
    tmp = tempfile.mkdtemp(); home = os.path.join(tmp, "home"); fake = os.path.join(tmp, "bin"); os.makedirs(fake)
    spy = os.path.join(tmp, "spy.jsonl"); open(spy, "w").close()
    gitdir = os.path.dirname(shutil.which("git"))
    gcfg = os.path.join(tmp, "gitconfig")
    open(gcfg, "w").write("[user]\n\tname = Teste\n\temail = teste@example.com\n[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
    base = {k: v for k, v in os.environ.items() if k not in ("A2A_RUNNER", "ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_POWERSHELL_TOOL",
                                                               "CODEX_HOME", "HERMES_HOME", "FAKE_CLAUDE_OLD", "FAKE_CLAUDE_AUTH")}
    env = dict(base, A2A_HOME=home, PYTHONIOENCODING="utf-8", PATH=fake + os.pathsep + gitdir, FAKE_SPY=spy,
               GIT_CONFIG_GLOBAL=gcfg, GIT_CONFIG_NOSYSTEM="1", CODEX_HOME=os.path.join(tmp, "codexhome"),
               HERMES_HOME=os.path.join(tmp, "hermeshome"))
    real = {n: shutil.which(n, path=gitdir) for n in ("claude", "codex", "hermes")}  # na pasta do git (nao deveria haver)
    def check(*args, e=None, mode="plain", code=None):
        r = subprocess.run([sys.executable, "-c", WATCH_INPROC, mode, str(ROOT), "watch", "check", *args],
                           capture_output=True, env=e or env)
        out = r.stdout.decode("utf-8")
        if code is not None: assert r.returncode == code, (args, r.returncode, out, r.stderr.decode("utf-8", "replace"))
        return out, r.returncode
    def rows(*args, **kw):
        out, rc = check("--json", *args, **kw); j = json.loads(out)
        return {(x["agent"], x["check"]): (x["level"], x["detail"]) for x in j["checks"]}, j, rc
    def put_fake(name):
        py = os.path.join(fake, name + ".py"); open(py, "w").write(FAKE_CLI)
        if os.name == "nt": open(os.path.join(fake, name + ".cmd"), "w").write(f'@"{sys.executable}" "{py}" %*\n')
        else:
            p = os.path.join(fake, name); open(p, "w").write(f"#!{sys.executable}\n" + FAKE_CLI); os.chmod(p, 0o755)
    # 1) sem executaveis: claude/codex ERRO, hermes PULADO (desabilitado), sai 1
    run(env, "init")
    if not real["claude"] and not real["codex"]:
        r, j, rc = rows()
        assert rc == 1 and not j["ready"] and r[("claude", "executavel")][0] == "ERRO" and r[("codex", "executavel")][0] == "ERRO", r
        assert r[("claude", "versao")][0] == "PULADO" and r[("hermes", "vigia")][0] == "AVISO", r
        assert "nao encontrado no PATH" in r[("codex", "executavel")][1] and r[("dove", "copias")][0] == "PULADO", r
    for n in ("claude", "codex", "hermes"): put_fake(n)
    # 2) tudo presente (fora do Windows): pronto
    r, j, rc = rows(code=0)
    assert j["ready"] and j["counts"]["ERRO"] == 0, j
    assert r[("claude", "versao")] == ("OK", "2.1.300 (Claude Code)") and r[("codex", "versao")] == ("OK", "codex-cli 0.50.0"), r
    assert r[("claude", "auth")][0] == "OK" and "assinatura" in r[("claude", "auth")][1] and "--bare" in r[("claude", "auth")][1], r
    assert r[("claude", "--permission-prompts")][0] == "OK" and r[("codex", "sandbox")][0] == "OK", r
    assert r[("codex", "commit")][0] == "AVISO" and ".git so leitura" in r[("codex", "commit")][1], r
    assert r[("hermes", "versao")][0] == "OK" and r[("hermes", "vigia")] == ("AVISO", "desabilitado no vigia ate o Luiz confirmar as flags de contencao"), r
    assert r[("dove", "tabela")][0] == "OK" and r[("dove", "STOP")][0] == "OK" and ("dove", "A2A_RUNNER") not in r, r
    out, _ = check(code=0)
    assert out.startswith("dove watch check - ") and "OK     claude: versao: 2.1.300 (Claude Code)\n" in out and "-- " in out, out
    # 3) claude antigo (sem --permission-prompts), chave de API, nao logado
    r, _, rc = rows(e=dict(env, FAKE_CLAUDE_OLD="1", FAKE_CLAUDE_AUTH="api_key"), code=1)
    assert r[("claude", "--permission-prompts")][0] == "ERRO" and "2.1.259" in r[("claude", "--permission-prompts")][1], r
    assert r[("claude", "auth")][0] == "AVISO" and "chave de API" in r[("claude", "auth")][1], r
    r, _, _ = rows(e=dict(env, FAKE_CLAUDE_AUTH="none"), code=1)
    assert r[("claude", "auth")] == ("ERRO", "nao logado: rode claude auth login"), r
    # 4) Windows simulado: codex sem [windows] sandbox -> nao pronto; com sandbox -> ok; PowerShell explicado
    os.makedirs(env["CODEX_HOME"]); cfg = os.path.join(env["CODEX_HOME"], "config.toml")
    open(cfg, "w").write('model = "gpt-5"\n[profiles.x]\nsandbox = "elevated"\n')
    r, j, rc = rows("--agent", "codex", mode="win", code=1)
    assert r[("codex", "sandbox")][0] == "ERRO" and "nao pronto" in r[("codex", "sandbox")][1] and cfg in r[("codex", "sandbox")][1], r
    assert not any(a == "claude" for a, _ in r), "--agent codex: so o codex (e o dove)"
    open(cfg, "w").write('model = "gpt-5"\n\n[windows]\nsandbox = "elevated" # nativo\n')
    r, _, _ = rows("--agent", "codex", mode="win", code=0)
    assert r[("codex", "sandbox")] == ("OK", f'[windows] sandbox = "elevated" em {cfg}'), r
    r, _, _ = rows("--agent", "claude", mode="win", code=0)
    assert "PowerShell e o shell principal" in r[("claude", "powershell")][1] and "PowerShell(...)" in r[("claude", "powershell")][1], r
    r, _, _ = rows("--agent", "claude", mode="win", e=dict(env, CLAUDE_CODE_USE_POWERSHELL_TOOL="0"), code=0)
    assert r[("claude", "powershell")][1].startswith("CLAUDE_CODE_USE_POWERSHELL_TOOL=0"), r
    # 5) copias de trabalho: sem copia (ERRO para agente do vigia), limpa (OK), suja (AVISO); STOP; A2A_RUNNER
    def g(cwd, *a):
        x = subprocess.run(["git", *a], cwd=cwd, env=env, capture_output=True, text=True); assert x.returncode == 0, (a, x.stderr)
    lagu = os.path.join(tmp, "lagu"); os.makedirs(lagu); g(lagu, "init", "-q", "-b", "main")
    open(os.path.join(lagu, "a.txt"), "w").write("a\n"); g(lagu, "add", "."); g(lagu, "commit", "-qm", "inicio")
    for ag in ("claude", "codex"): run(env, "join", "--agent", ag)
    assert run(env, "project", "add", "lagu", lagu).returncode == 0
    x = run(env, "worktree", "create", "--project", "lagu", "--agent", "claude", "--from", "luiz"); assert x.returncode == 0, x.stderr
    wt = lagu + "-claude"
    r, _, rc = rows("--project", "lagu", code=1)
    assert r[("dove", "copia claude")] == ("OK", f"{wt} limpa"), r
    assert r[("dove", "copia codex")][0] == "ERRO" and "o vigia recusaria" in r[("dove", "copia codex")][1], r
    r, _, _ = rows("--project", "lagu", "--agent", "claude", code=0)
    assert ("dove", "copia codex") not in r and r[("dove", "copia claude")][0] == "OK", r
    open(os.path.join(wt, "novo.txt"), "w").write("x\n")
    open(os.path.join(home, "STOP"), "w").close()
    r, j, _ = rows("--project", "lagu", "--agent", "claude", e=dict(env, A2A_RUNNER="watch"), code=0)
    assert r[("dove", "copia claude")][0] == "AVISO" and "copia suja: vigia esperaria" in r[("dove", "copia claude")][1], r
    assert r[("dove", "STOP")][0] == "AVISO" and "nao iniciaria" in r[("dove", "STOP")][1], r
    assert r[("dove", "A2A_RUNNER")][0] == "AVISO", r
    os.remove(os.path.join(home, "STOP")); os.remove(os.path.join(wt, "novo.txt"))
    # 6) a tabela nunca tem padroes proibidos; cada subcomando nas formas Bash e PowerShell; check acusa tabela adulterada
    t = json.loads(subprocess.run([sys.executable, "-c", WATCH_INPROC, "table", str(ROOT)], capture_output=True, env=env).stdout)
    assert t["bad"] == [] and set(t["runners"]) == {"claude", "codex", "hermes"}, t
    forbidden = re.compile(r"python|\ba2a \*|git push|git merge|git -C|bypassPermissions|danger-full-access|--yolo|dangerously", re.I)
    for ag, rr in t["runners"].items():
        for s in rr["argv"] + rr["allow"] + [rr["mode"]]: assert not forbidden.search(s), (ag, s)
    allow = t["runners"]["claude"]["allow"]
    for sh in ("Bash", "PowerShell"):
        for c in t["subcmds"] + ["git status", "git diff", "git log"]: assert f"{sh}({'' if c.startswith('git') else 'a2a '}{c} *)" in allow, (sh, c)
    assert set(t["subcmds"]) == {"send", "brief", "read", "status", "ack", "whereami", "mission approve", "mission reject",
                                 "fact add", "fact list", "project which"}, t["subcmds"]
    assert t["runners"]["claude"]["mode"] == "dontAsk" and "--permission-mode" in t["runners"]["claude"]["argv"], t
    assert t["runners"]["codex"]["argv"] == ["exec", "--json", "-s", "workspace-write", "-C", "{worktree}", "--add-dir", "{a2a_home}", "-"], t
    assert t["runners"]["hermes"]["enabled"] is False and t["runners"]["claude"]["enabled"] and t["runners"]["codex"]["enabled"], t
    r, _, _ = rows("--agent", "claude", mode="bad", code=1)
    assert r[("dove", "tabela")][0] == "ERRO" and "Bash(python *)" in r[("dove", "tabela")][1] and "Bash(git push *)" in r[("dove", "tabela")][1], r
    # 7) --show-command: argv exato sem rodar nada (o espiao nao muda)
    before = open(spy, encoding="utf-8").read()
    out, _ = check("--project", "lagu", "--show-command", code=0)
    assert open(spy, encoding="utf-8").read() == before, "--show-command nao pode executar nada"
    lines = out.splitlines()
    cl = next(l for l in lines if l.startswith("claude "))
    assert cl.startswith("claude -p --output-format json --permission-mode dontAsk --permission-prompts none --max-turns 30 --allowedTools "), cl
    assert "Bash(git diff *)" in cl and "PowerShell(a2a mission approve *)" in cl and "python" not in cl and "--bare" not in cl, cl
    assert f"# claude · pasta: {wt} · stdin:" in out and "# codex · pasta: <copia de codex>" in out, out
    cx = next(l for l in lines if l.startswith("codex "))
    assert cx.startswith("codex exec --json -s workspace-write -C ") and "--add-dir" in cx and home in cx and cx.endswith(" -"), cx
    assert "# hermes (desabilitado ate o Luiz confirmar)" in out and any(l.startswith("hermes chat --oneshot") for l in lines), out
    j = json.loads(check("--show-command", "--json", "--agent", "claude", code=0)[0])
    assert j["commands"][0]["argv"][:2] == ["claude", "-p"] and j["commands"][0]["argv"][-1] == ",".join(allow), j
    assert open(spy, encoding="utf-8").read() == before
    # 8) espiao: nada alem de --version, --help e auth status
    calls = [json.loads(l) for l in open(spy, encoding="utf-8") if l.strip()]
    assert calls and {tuple(c[1:]) for c in calls} <= {("--version",), ("--help",), ("auth", "status")}, calls
    assert {c[0] for c in calls} == {"claude", "codex", "hermes"}, calls
    h = run(env, "watch", "check", "--help").stdout
    assert "exemplos:\n" in h and "--show-command" in h and "a2a watch check --project lagu" in h, h
    print("OK: a2a watch check (exe ausente, versao, auth assinatura/API/nao logado, --permission-prompts, Windows sem sandbox = "
          "nao pronto, PowerShell, copia limpa/suja/ausente, STOP, A2A_RUNNER, tabela sem padroes proibidos, --show-command, "
          "espiao: so --version/--help/auth status)")

if __name__ == "__main__":
    main()
    fase1()
    robustez()
    fase2()
    git_fase()
    brief_fase()
    compact_fase()
    wait_fase()
    archive_fase()
    index_fase()
    files_fase()
    prompt_fase()
    instructions_fase()
    fact_fase()
    loops_fase()
    watch_fase()
