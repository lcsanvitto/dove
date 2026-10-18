import json, os, subprocess, sys, tempfile, time, pathlib

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
    inb = run(env, "inbox", "--agent", "hermes")
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

if __name__ == "__main__":
    main()
