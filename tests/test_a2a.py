import json, os, socket, subprocess, sys, tempfile, time, pathlib, urllib.request

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
        print("OK: install.sh (symlink, shebang, agentes, idempotente)")

    # install.ps1: checagem estatica (shims .cmd e Git Bash, ASCII puro)
    raw = (ROOT / "install.ps1").read_bytes()
    assert all(b < 128 for b in raw), "install.ps1 tem bytes nao-ASCII"
    txt = raw.decode("ascii")
    for needle in ("a2a.cmd", "#!/bin/sh", "UTF8Encoding($false)"):
        assert needle in txt, needle
    print("OK: install.ps1 (estatico: a2a.cmd, shim Git Bash, ASCII)")

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

if __name__ == "__main__":
    main()
