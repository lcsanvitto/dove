#!/usr/bin/env python3
"""a2a (Dove) - canal de mensagens agente-a-agente, local e global."""
import argparse, glob, hmac, json, os, re, secrets, sys, time, uuid
from datetime import datetime, timezone

HOME = os.environ.get("A2A_HOME", os.path.expanduser("~/.a2a"))
BUS, CURSOR, AGENTS, STATUS, MISSIONS = (os.path.join(HOME, d) for d in
                                         ("bus", "cursor", "agents", "status", "missions"))
PROJECTS, CONFIG = os.path.join(HOME, "projects.json"), os.path.join(HOME, "config.json")
UI_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "index.html")
STATES = ["AGUARDANDO_ACEITE","ACEITO","EM_EXECUCAO","BLOQUEADO",
          "AGUARDANDO_APROVACAO","EM_REVISAO","CONCLUIDO","CANCELADO"]
KINDS = ["task","report","question","correction","ack"]
AGENT_STATES = ["working","idle","blocked","done","unknown"]  # vocabulario herdr
MSG_TO_AGENT = {"ACEITO": "working", "EM_EXECUCAO": "working", "BLOQUEADO": "blocked",
                "AGUARDANDO_APROVACAO": "blocked", "CONCLUIDO": "done", "CANCELADO": "done"}  # auto-status
HUMAN = "luiz"          # humano padrao (painel e missoes)
CTX_HIGH = 80           # contexto >= isto: preparar handoff
CLOSED = ("CONCLUIDO", "CANCELADO")

class DoveError(Exception): pass

def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ensure_dirs():
    for d in (BUS, CURSOR, AGENTS, STATUS, MISSIONS): os.makedirs(d, exist_ok=True)
def read_json(p, default=None):
    """Le JSON em UTF-8; cai para a codificacao local (arquivos antigos gravados no Windows)."""
    try:
        with open(p, "rb") as f: raw = f.read()
    except OSError: return default
    for enc in ("utf-8", None):
        try: return json.loads(raw.decode(enc) if enc else raw.decode())
        except (UnicodeDecodeError, ValueError): continue
    return default
def write_json(p, obj):
    """Grava atomico (tmp + replace) em UTF-8."""
    tmp = f"{p}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)
    for i in range(10):  # Windows: replace falha se outro processo esta lendo
        try: os.replace(tmp, p); return
        except PermissionError:
            if i == 9: raise
            time.sleep(0.05)
class FileLock:
    """Trava simples por arquivo .lock (O_EXCL); quebra trava velha (>10s)."""
    def __init__(self, path, timeout=5.0): self.p, self.timeout = path + ".lock", timeout
    def __enter__(self):
        t0 = time.time()
        while True:
            try: os.close(os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)); return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.p) > 10: os.remove(self.p); continue
                except OSError: pass
                if time.time() - t0 > self.timeout: raise DoveError(f"arquivo travado: {self.p}")
                time.sleep(0.05)
    def __exit__(self, *x):
        try: os.remove(self.p)
        except OSError: pass
def fail(msg): print(msg, file=sys.stderr); sys.exit(1)

def seen_path(a): return os.path.join(CURSOR, a + ".json")
def load_seen(a):
    v = read_json(seen_path(a), [])
    return set(v) if isinstance(v, list) else set()
def mark_seen(a, mid):
    s = load_seen(a); s.add(mid); write_json(seen_path(a), sorted(s))
def _chrono(f):  # ts do nome do arquivo; desempate pela ordem de escrita (mtime)
    try: return (os.path.basename(f)[:16], os.path.getmtime(f))
    except OSError: return (os.path.basename(f)[:16], 0)
def all_messages():
    out = []
    for f in sorted(glob.glob(os.path.join(BUS, "*.json")), key=_chrono):
        m = read_json(f)
        if isinstance(m, dict) and "msg_id" in m: out.append(m)
    return out
def visible_for(m, agent, project=None):
    if m["to"] not in (agent, "all"): return False
    if m["from"] == agent: return False
    if project and m.get("project") != project: return False
    return True
def registered_agents():
    ensure_dirs(); return sorted(n for n in os.listdir(AGENTS) if not n.startswith("."))

def cmd_init(a): ensure_dirs(); print(f"a2a pronto em {HOME}")
def cmd_join(a):
    ensure_dirs(); open(os.path.join(AGENTS, a.agent), "w").close()
    print(f"agente '{a.agent}' registrado. Caixa global: {HOME}")
def cmd_agents(a):
    n = registered_agents()
    print("\n".join(n) if n else "(nenhum agente registrado)")
def post_message(_from, to, body, kind="task", project="", task="", reply_to="", state="", result="",
                 evidence="", pending="", next_action="", auto_status=True):
    """Caminho unico de escrita no bus (CLI, missoes e painel)."""
    ensure_dirs(); mid = uuid.uuid4().hex[:12]; ts = now_iso()
    msg = {"data": ts, "task_id": task or "", "msg_id": mid, "from": _from,
           "to": to, "project": project or "", "in_reply_to": reply_to or "",
           "kind": kind, "state": state or "", "result": result or "",
           "evidence": evidence or "", "pending": pending or "",
           "next_action": next_action or "", "body": body or ""}
    fn = f"{ts.replace(':','').replace('-','')}-{mid}.json"
    write_json(os.path.join(BUS, fn), msg)
    mark_seen(_from, mid)
    if auto_status: touch_status(_from, MSG_TO_AGENT.get(state or ""), project)
    return msg
def cmd_send(a):
    m = post_message(a._from, a.to, a.body, a.kind, a.project, a.task, a.reply_to, a.state, a.result,
                     a.evidence, a.pending, a.next_action, not getattr(a, "no_auto_status", False))
    print(f"enviado {m['msg_id']} ({a._from} -> {a.to})")
def auto(a, agent):
    if not getattr(a, "no_auto_status", False): touch_status(agent)
def cmd_inbox(a):
    ensure_dirs(); auto(a, a.agent); seen = load_seen(a.agent)
    msgs = [m for m in all_messages()
            if visible_for(m, a.agent, a.project) and m["msg_id"] not in seen]
    if not msgs: print("(caixa vazia)"); return
    for m in msgs:
        print(f"[{m['data']}] {m['msg_id']} de {m['from']} "
              f"({m['kind']}/{m.get('state','')}) proj={m.get('project','')}: {m['body'][:80]}")
def cmd_read(a):
    for m in all_messages():
        if m["msg_id"] == a.msg_id:
            print(json.dumps(m, ensure_ascii=False, indent=2))
            if a.agent: mark_seen(a.agent, a.msg_id)
            return
    print("nao encontrada", file=sys.stderr); sys.exit(1)
def cmd_wait(a):
    ensure_dirs(); auto(a, a.agent); deadline = time.time() + a.timeout if a.timeout else None
    if a.until:
        while True:
            st = load_status(a.agent)
            if st and st.get("state") == a.until:
                print(json.dumps(st, ensure_ascii=False, indent=2)); return
            if deadline and time.time() > deadline: print("(timeout)"); sys.exit(2)
            time.sleep(a.interval)
    while True:
        seen = load_seen(a.agent)
        for m in all_messages():
            if visible_for(m, a.agent, a.project) and m["msg_id"] not in seen:
                print(json.dumps(m, ensure_ascii=False, indent=2))
                mark_seen(a.agent, m["msg_id"]); return
        if deadline and time.time() > deadline: print("(timeout)"); sys.exit(2)
        time.sleep(a.interval)
def cmd_ack(a):
    orig = next((m for m in all_messages() if m["msg_id"] == a.msg_id), None)
    if not orig: print("original nao encontrada", file=sys.stderr); sys.exit(1)
    if orig["kind"] == "ack": print("nao se responde ack de ack (anti-loop)"); return
    mark_seen(a._from, a.msg_id); auto(a, a._from)
    cmd_send(argparse.Namespace(no_auto_status=True, _from=a._from, to=orig["from"], task=orig.get("task_id"),
        project=orig.get("project"), reply_to=a.msg_id, kind="ack", state=None,
        result=None, evidence=None, pending=None, next_action=None,
        body=a.body or "recebido"))

# ---------------------------------------------------------------- status (modo herdr)
def status_path(a): return os.path.join(STATUS, a + ".json")
def load_status(a):
    st = read_json(status_path(a))
    return st if isinstance(st, dict) else None
def fmt_age(ts):
    if not ts: return "-"
    s = max(0, time.time() - ts)
    if s < 60: return f"{int(s)}s"
    if s < 3600: return f"{int(s // 60)}m"
    if s < 86400: return f"{int(s // 3600)}h"
    return f"{int(s // 86400)}d"
def write_status(st):
    st.update(updated=now_iso(), ts=time.time())
    write_json(status_path(st["agent"]), st)
def touch_status(agent, state=None, project=None, note=None):
    """Auto-status: com state grava o estado; sem state so renova o ts (heartbeat)."""
    ensure_dirs(); st = load_status(agent)
    if st is None: st = {"agent": agent, "state": state or "idle", "note": "", "project": ""}
    elif state: st["state"] = state
    if state and note is not None: st["note"] = note
    if state and project: st["project"] = project
    if st.get("state") not in AGENT_STATES: st["state"] = "unknown"
    write_status(st)
def effective_status(name, st, stale_min):
    """Estado efetivo (com staleness) - usado pelo quadro da CLI e pelo painel."""
    if not st: return {"agent": name, "state": "unknown", "age": "-", "project": "", "note": "",
                       "updated": "", "stale": False, "context": None, "model": ""}
    state, ts = st.get("state", "unknown"), st.get("ts") or 0
    note, stale = st.get("note", ""), not ts or time.time() - ts > stale_min * 60
    if stale: note = (note + " " if note else "") + f"(stale, era {state})"; state = "unknown"
    ctx = st.get("context")
    return {"agent": name, "state": state, "age": fmt_age(ts), "project": st.get("project") or "",
            "note": note, "updated": st.get("updated", ""), "stale": bool(stale),
            "context": ctx if isinstance(ctx, int) else None, "model": st.get("model") or ""}
def board_data(stale_min, agent=None):
    ensure_dirs()
    names = [agent] if agent else sorted(set(registered_agents()) |
                                         {f[:-5] for f in os.listdir(STATUS) if f.endswith(".json")})
    return [effective_status(n, load_status(n), stale_min) for n in names]
def status_line(name, st, stale_min):
    if not st: return f"{name:<12} {'unknown':<8} {'-':>4}"
    e = effective_status(name, st, stale_min)
    ctx = f"ctx {e['context']}%  " if e["context"] is not None else ""
    return f"{name:<12} {e['state']:<8} {e['age']:>4}  {e['project'] or '-':<10} {ctx}{e['note']}".rstrip()
def pct(v):
    try: n = int(v)
    except (TypeError, ValueError): raise argparse.ArgumentTypeError("use um inteiro de 0 a 100")
    if not 0 <= n <= 100: raise argparse.ArgumentTypeError("use um inteiro de 0 a 100")
    return n
def cmd_status(a):
    ensure_dirs()
    if a.set or a.context is not None or a.model:
        if not a.agent: print("--set/--context/--model exigem --agent", file=sys.stderr); sys.exit(1)
        old = load_status(a.agent) or {}
        if a.set: st = {"agent": a.agent, "state": a.set, "note": a.note or "", "project": a.project or ""}
        else:
            st = dict(old, agent=a.agent); st.setdefault("state", "idle")
            if a.note is not None: st["note"] = a.note
            if a.project: st["project"] = a.project
        for k in ("context", "model"):  # contexto/modelo persistem ate o proximo informe
            v = getattr(a, k)
            if v is not None and v != "": st[k] = v
            elif k in old: st[k] = old[k]
        write_status(st)
        extra = f" ctx {st['context']}%" if st.get("context") is not None else ""
        print(f"status de '{a.agent}': {st['state']}{extra}" + (f" ({st.get('note')})" if st.get("note") else ""))
        return
    if a.agent: print(status_line(a.agent, load_status(a.agent), a.stale_minutes)); return
    names = [e["agent"] for e in board_data(a.stale_minutes)]
    if not names: print("(nenhum agente)"); return
    for n in names: print(status_line(n, load_status(n), a.stale_minutes))

def log_data(limit=20, project=None, agent=None, msgs=None):
    """Mensagens recentes de todos os agentes, em ordem cronologica (mais nova por ultimo)."""
    msgs = [m for m in (all_messages() if msgs is None else msgs) if (not project or m.get("project") == project)
            and (not agent or agent in (m.get("from"), m.get("to")))]
    return msgs[-limit:] if limit and limit > 0 else msgs
def short(t, n=70):
    t = " ".join((t or "").split()); return t if len(t) <= n else t[:n - 3] + "..."
def cmd_log(a):
    ensure_dirs(); msgs = log_data(a.limit, a.project, a.agent)
    if not msgs: print("(nenhuma mensagem)"); return
    for m in msgs:
        ks = m.get("kind", "") + ("/" + m["state"] if m.get("state") else "")
        print(f"[{m.get('data','')}] {m.get('msg_id','')} {m.get('from','')} -> {m.get('to','')} "
              f"({ks}) proj={m.get('project') or '-'}: {short(m.get('body'))}")

# ---------------------------------------------------------------- config e projetos
def load_config():
    c = read_json(CONFIG, {}); return c if isinstance(c, dict) else {}
def save_config(**kv):
    ensure_dirs()
    with FileLock(CONFIG):
        c = load_config(); c.update(kv); write_json(CONFIG, c)
def human_name(): return load_config().get("human") or HUMAN
def load_projects():
    p = read_json(PROJECTS, [])
    return [x for x in p if isinstance(x, dict) and x.get("name")] if isinstance(p, list) else []
def sorted_projects(ps): return sorted(ps, key=lambda p: (not p.get("pinned"), p["name"].lower()))
def norm_path(p): return os.path.normcase(os.path.abspath(os.path.expanduser(p)))
def unique_name(name, path, taken):
    if name not in taken: return name
    parent = os.path.basename(os.path.dirname(os.path.abspath(path))) or "x"
    cand, i = f"{name}-{parent}", 2
    while cand in taken: cand, i = f"{name}-{parent}-{i}", i + 1
    return cand
def project_add(name, path, auto_name=False):
    name, path = (name or "").strip(), (path or "").strip()
    if not path: raise DoveError("caminho vazio")
    if not name: name = os.path.basename(os.path.abspath(os.path.expanduser(path)).rstrip("\\/"))
    if not name or "/" in name or "\\" in name: raise DoveError(f"nome de projeto invalido: '{name}'")
    full = os.path.abspath(os.path.expanduser(path)); ensure_dirs()
    with FileLock(PROJECTS):
        ps = load_projects(); taken = {p["name"] for p in ps}
        if any(norm_path(p["path"]) == norm_path(full) for p in ps):
            raise DoveError(f"caminho ja registrado: {full}")
        if name in taken:
            if not auto_name: raise DoveError(f"projeto '{name}' ja existe")
            name = unique_name(name, full, taken)
        p = {"name": name, "path": full, "pinned": False, "added": now_iso()}
        ps.append(p); write_json(PROJECTS, ps)
    return p
def project_remove(name):
    with FileLock(PROJECTS):
        ps = load_projects(); keep = [p for p in ps if p["name"] != name]
        if len(keep) == len(ps): raise DoveError(f"projeto '{name}' nao encontrado")
        write_json(PROJECTS, keep)
def project_pin(name, on=True):
    with FileLock(PROJECTS):
        ps = load_projects(); hit = [p for p in ps if p["name"] == name]
        if not hit: raise DoveError(f"projeto '{name}' nao encontrado")
        hit[0]["pinned"] = bool(on); write_json(PROJECTS, ps)
    return hit[0]

SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", "vendor"}
def _read_text(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: return f.read()
    except OSError: return ""
def remote_host(url):
    url = (url or "").strip()
    if "://" in url:
        net = url.split("://", 1)[1].split("/", 1)[0]
        return net.rsplit("@", 1)[-1].split(":", 1)[0]
    m = re.match(r"^[^@/]+@([^:/]+):", url)
    return m.group(1) if m else ""
def git_info(repo, dot_git):
    """Le branch/remote/atividade direto dos arquivos do .git (sem rodar git)."""
    gitdir = dot_git
    if os.path.isfile(dot_git):  # worktree/submodulo: "gitdir: <caminho>"
        m = re.match(r"gitdir:\s*(.+)", _read_text(dot_git).strip())
        if m: gitdir = os.path.normpath(os.path.join(repo, m.group(1).strip()))
    common = gitdir
    cd = _read_text(os.path.join(gitdir, "commondir")).strip()
    if cd: common = os.path.normpath(os.path.join(gitdir, cd))
    head = _read_text(os.path.join(gitdir, "HEAD")).strip()
    branch = head[16:] if head.startswith("ref: refs/heads/") else (head[:7] if head else "")
    url, in_origin = "", False
    for line in _read_text(os.path.join(common, "config")).splitlines():
        s = line.strip()
        if s.startswith("["): in_origin = bool(re.match(r'\[remote\s+"origin"\]', s)); continue
        if in_origin and re.match(r"url\s*=", s): url = s.split("=", 1)[1].strip(); break
    ts = 0.0
    for f in ("HEAD", "index"):
        try: ts = max(ts, os.path.getmtime(os.path.join(gitdir, f)))
        except OSError: pass
    return {"name": os.path.basename(repo) or repo, "path": repo, "branch": branch, "remote": url,
            "host": remote_host(url), "last_activity": ts,
            "last_activity_iso": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""}
def scan_repos(root, depth=3):
    """Acha repos git (pasta com .git) sob root ate depth niveis, sem descer em repos achados."""
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root): raise DoveError(f"pasta nao encontrada: {root}")
    found = []
    def walk(d, level):
        try:
            with os.scandir(d) as it: entries = list(it)
        except OSError: return
        for e in entries:
            if e.name == ".git": found.append(git_info(d, e.path)); return
        if level >= depth: return
        for e in entries:
            if e.name in SKIP_DIRS or e.name.startswith("."): continue
            try:
                if not e.is_dir(follow_symlinks=False): continue
            except OSError: continue
            walk(e.path, level + 1)
    walk(root, 0)
    reg = {norm_path(p["path"]) for p in load_projects()}
    for r in found: r["registered"] = norm_path(r["path"]) in reg
    return sorted(found, key=lambda r: r["path"].lower())
def scan_add(repos):
    added = []
    for r in repos:
        if r.get("registered"): continue
        try: added.append(project_add(r["name"], r["path"], auto_name=True))
        except DoveError: pass
    return added

def cmd_project(a):
    try:
        if a.pcmd == "add":
            p = project_add(a.name, a.path)
            if not os.path.isdir(p["path"]): print(f"AVISO: pasta nao existe (ainda): {p['path']}", file=sys.stderr)
            print(f"projeto '{p['name']}' adicionado: {p['path']}")
        elif a.pcmd == "remove": project_remove(a.name); print(f"projeto '{a.name}' removido")
        elif a.pcmd == "pin":
            project_pin(a.name, not a.off); print(f"projeto '{a.name}' " + ("desafixado" if a.off else "fixado"))
        elif a.pcmd == "list":
            ps = sorted_projects(load_projects())
            if not ps: print("(nenhum projeto) - use: a2a project add NOME CAMINHO  ou  a2a project scan RAIZ"); return
            for p in ps: print(f"{'*' if p.get('pinned') else ' '} {p['name']:<20} {p['path']}")
        elif a.pcmd == "scan":
            t0 = time.time(); repos = scan_repos(a.root, a.depth); dt = time.time() - t0
            save_config(scan_root=os.path.abspath(os.path.expanduser(a.root)))
            for r in repos:
                age = fmt_age(r["last_activity"]) if r["last_activity"] else "-"
                print(f"{r['name']:<24} {r['branch'] or '-':<14} {r['host'] or '-':<14} {age:>4}  {r['path']}"
                      + ("  [registrado]" if r["registered"] else ""))
            print(f"{len(repos)} repositorios em {dt:.2f}s")
            if a.add:
                added = scan_add(repos)
                for p in added: print(f"adicionado: {p['name']} ({p['path']})")
                print(f"{len(added)} projetos adicionados")
    except DoveError as e: fail(f"erro: {e}")

# ---------------------------------------------------------------- missoes com aval de todos
def mission_path(mid): return os.path.join(MISSIONS, re.sub(r"[^A-Za-z0-9_-]", "", mid) + ".json")
def load_mission(mid):
    m = read_json(mission_path(mid)) if mid else None
    if not isinstance(m, dict): raise DoveError(f"missao '{mid}' nao encontrada")
    return m
def all_missions():
    ensure_dirs(); out = []
    for f in glob.glob(os.path.join(MISSIONS, "*.json")):
        m = read_json(f)
        if isinstance(m, dict) and m.get("id"): out.append(m)
    return sorted(out, key=lambda m: m.get("created", ""))
def mission_status(m):
    ap = m.get("approvals") or {}
    v = [(ap.get(a) or {}).get("verdict") for a in m.get("agents", [])]
    if "reject" in v: return "reprovada"
    if v and all(x == "approve" for x in v): return "concluida" if m.get("human") else "aval_completo"
    return "aberta"
def mission_view(m):
    ap = m.get("approvals") or {}
    return dict(m, status=mission_status(m),
                approved=sum(1 for a in m.get("agents", []) if (ap.get(a) or {}).get("verdict") == "approve"),
                total=len(m.get("agents", [])))
def mission_new(project, title, desc="", agents=None, created_by=HUMAN):
    project, title = (project or "").strip(), (title or "").strip()
    if not project: raise DoveError("missao exige --project")
    if not title: raise DoveError("missao exige --title")
    ags = [x.strip() for x in (agents or []) if x and x.strip()] or registered_agents()
    ags = list(dict.fromkeys(ags))
    if not ags: raise DoveError("nenhum agente participante (registre com a2a join ou use --agents)")
    created_by = (created_by or HUMAN).strip() or HUMAN
    mid = "m" + uuid.uuid4().hex[:7]; ensure_dirs()
    m = {"id": mid, "project": project, "title": title, "description": desc or "", "agents": ags,
         "created_by": created_by, "created": now_iso(), "approvals": {}, "history": [], "human": None}
    write_json(mission_path(mid), m)
    human = created_by == human_name()
    for ag in ags:
        post_message(created_by, ag, f"Missao {mid}: {title}" + (f"\n{desc}" if desc else "") +
                     f"\nVerifique e de seu aval: a2a mission approve {mid} --agent {ag} --evidence \"...\""
                     f" (ou: a2a mission reject {mid} --agent {ag} --reason \"...\")",
                     kind="task", project=project, task=mid, auto_status=not human)
    return m
def mission_verdict(mid, agent, verdict, text):
    text = (text or "").strip()
    if not text: raise DoveError("aprovar exige --evidence (o que voce conferiu)" if verdict == "approve"
                                 else "reprovar exige --reason")
    with FileLock(mission_path(mid)):
        m = load_mission(mid)
        if agent not in m.get("agents", []):
            raise DoveError(f"'{agent}' nao participa da missao {mid} (participantes: {', '.join(m['agents'])})")
        if m.get("human"): raise DoveError(f"missao {mid} ja foi concluida")
        v = {"verdict": verdict, "ts": now_iso(), "evidence": text if verdict == "approve" else "",
             "reason": text if verdict == "reject" else ""}
        m.setdefault("approvals", {})[agent] = v  # o ultimo veredito de cada agente vale
        m.setdefault("history", []).append(dict(v, agent=agent))
        write_json(mission_path(mid), m)
    task = next((x for x in reversed(all_messages()) if x.get("task_id") == mid and x.get("to") == agent
                 and x.get("kind") == "task"), None)
    ok = verdict == "approve"
    post_message(agent, m["created_by"], f"Missao {mid} " + ("aprovada" if ok else "reprovada") +
                 f" por {agent}: {m['title']}" + ("" if ok else f"\nMotivo: {text}"),
                 kind="report", project=m["project"], task=mid, reply_to=task["msg_id"] if task else "",
                 state="CONCLUIDO" if ok else "BLOQUEADO", evidence=text if ok else "", auto_status=False)
    touch_status(agent)  # heartbeat; dar aval nao muda o estado do agente
    return m
def mission_done(mid, by=HUMAN):
    by = (by or "").strip() or HUMAN
    with FileLock(mission_path(mid)):
        m = load_mission(mid); st = mission_status(m)
        if st == "concluida": raise DoveError(f"missao {mid} ja estava concluida")
        if st != "aval_completo":
            raise DoveError(f"missao {mid} esta '{st}': a conclusao so vale com o aval de todos os agentes")
        m["human"] = {"by": by, "ts": now_iso()}; write_json(mission_path(mid), m)
    return m
def mission_line(m):
    v = mission_view(m)
    return f"{v['id']}  {v['status']:<13} {v['approved']}/{v['total']}  {v['project']:<12} {v['title']}"
def cmd_mission(a):
    try:
        if a.mcmd == "new":
            ags = [x for x in (a.agents or "").split(",") if x.strip()]
            m = mission_new(a.project, a.title, a.desc, ags, a._from)
            print(f"missao {m['id']} criada ({', '.join(m['agents'])}): {m['title']}")
        elif a.mcmd == "approve":
            m = mission_verdict(a.id, a.agent, "approve", a.evidence)
            print(f"aval de '{a.agent}' registrado na missao {a.id} -> {mission_status(m)}")
        elif a.mcmd == "reject":
            m = mission_verdict(a.id, a.agent, "reject", a.reason)
            print(f"reprovacao de '{a.agent}' registrada na missao {a.id} -> {mission_status(m)}")
        elif a.mcmd == "done":
            mission_done(a.id, a._from); print(f"missao {a.id} concluida (confirmada por {a._from})")
        elif a.mcmd == "list":
            ms = [m for m in all_missions() if not a.project or m.get("project") == a.project]
            if not ms: print("(nenhuma missao)"); return
            for m in ms: print(mission_line(m))
        elif a.mcmd == "show":
            v = mission_view(load_mission(a.id))
            print(f"{v['id']}  {v['title']}\nprojeto: {v['project']}  status: {v['status']}  "
                  f"avais: {v['approved']}/{v['total']}  criada por {v['created_by']} em {v['created']}")
            if v.get("description"): print(f"descricao: {v['description']}")
            for ag in v["agents"]:
                x = (v.get("approvals") or {}).get(ag)
                if not x: print(f"  {ag:<12} pendente")
                elif x["verdict"] == "approve": print(f"  {ag:<12} aprovado  {x['ts']}  evidencia: {x['evidence']}")
                else: print(f"  {ag:<12} reprovado {x['ts']}  motivo: {x['reason']}")
            if v.get("human"): print(f"conclusao confirmada por {v['human']['by']} em {v['human']['ts']}")
    except DoveError as e: fail(f"erro: {e}")

# ---------------------------------------------------------------- "onde estamos" (resumo deterministico)
def open_tasks(msgs):
    """Tarefas (kind=task) sem resposta CONCLUIDO/CANCELADO (via in_reply_to, ou mesmo task_id vindo do destinatario)."""
    closed_ids, closed_tasks = set(), set()
    for m in msgs:
        if m.get("state") in CLOSED:
            if m.get("in_reply_to"): closed_ids.add(m["in_reply_to"])
            if m.get("task_id"): closed_tasks.add((m["task_id"], m.get("from")))
    return [m for m in msgs if m.get("kind") == "task" and m["msg_id"] not in closed_ids
            and not (m.get("task_id") and (m["task_id"], m.get("to")) in closed_tasks)]
def summary_data(project=None, msgs=None, agents=None, missions=None, stale_min=30):
    msgs = all_messages() if msgs is None else msgs
    agents = board_data(stale_min) if agents is None else agents
    missions = all_missions() if missions is None else missions
    if project:
        msgs = [m for m in msgs if m.get("project") == project]
        missions = [m for m in missions if m.get("project") == project]
        agents = [a for a in agents if a.get("project") == project]
    hn = human_name(); agents = [a for a in agents if a["agent"] != hn]
    item = lambda m: {"msg_id": m["msg_id"], "from": m.get("from", ""), "to": m.get("to", ""),
                      "project": m.get("project", ""), "data": m.get("data", ""), "body": short(m.get("body"), 120)}
    ot, mids = open_tasks(msgs), {m["id"] for m in missions}
    by_status = {s: 0 for s in ("aberta", "reprovada", "aval_completo", "concluida")}
    for m in missions: by_status[mission_status(m)] += 1
    done = [{"type": "message", "when": m.get("data", ""), "who": m.get("from", ""), "project": m.get("project", ""),
             "text": short(m.get("body"), 120)} for m in msgs if m.get("state") == "CONCLUIDO"
            and m.get("task_id") not in mids]  # avais de missao nao sao "conclusoes"
    done += [{"type": "mission", "when": m["human"]["ts"], "who": m["human"]["by"], "project": m.get("project", ""),
              "text": "Missao concluida: " + m.get("title", "")} for m in missions if mission_status(m) == "concluida"]
    done.sort(key=lambda x: x["when"])
    return {"project": project or "", "open_tasks": [item(m) for m in ot],
            "blocked": [{"agent": a["agent"], "note": a["note"]} for a in agents if a["state"] == "blocked"],
            "stale": [{"agent": a["agent"], "note": a["note"]} for a in agents if a["stale"]],
            "high_context": [{"agent": a["agent"], "context": a["context"]} for a in agents
                             if a["context"] is not None and a["context"] >= CTX_HIGH],
            "missions": by_status, "recent_done": done[-5:][::-1]}
def cmd_summary(a):
    s = summary_data(a.project, stale_min=a.stale_minutes)
    print(f"Onde estamos ({a.project or 'todos os projetos'})")
    print(f"Tarefas abertas: {len(s['open_tasks'])}")
    for t in s["open_tasks"][-10:]:
        print(f"  - [{t['data']}] {t['from']} -> {t['to']} proj={t['project'] or '-'}: {short(t['body'], 70)}")
    fmt = lambda xs: ", ".join(x["agent"] + (f" ({x['note']})" if x.get("note") else "") for x in xs) or "-"
    print(f"Agentes bloqueados: {fmt(s['blocked'])}")
    print(f"Agentes stale: {', '.join(x['agent'] for x in s['stale']) or '-'}")
    print(f"Contexto alto (>={CTX_HIGH}%): " + (", ".join(f"{x['agent']} {x['context']}%" for x in s["high_context"]) or "-"))
    print("Missoes: " + ", ".join(f"{k} {v}" for k, v in s["missions"].items()))
    print("Ultimas conclusoes:" + ("" if s["recent_done"] else " -"))
    for d in s["recent_done"]: print(f"  - [{d['when']}] {d['who']}: {short(d['text'], 80)}")

# ---------------------------------------------------------------- painel web (app dove)
FALLBACK_HTML = """<!doctype html><meta charset="utf-8"><title>Dove</title>
<p>Dove: ui/index.html nao encontrado ao lado do a2a.py. Atualize o repo (git pull).</p>"""
def panel_state(stale_min=30, limit=400):
    msgs, agents, missions = all_messages(), board_data(stale_min), all_missions()
    projects = sorted_projects(load_projects()); hn = human_name()
    per = {p["name"]: summary_data(p["name"], msgs, agents, missions) for p in projects}
    for m in msgs + missions:
        n = m.get("project")
        if n and n not in per: per[n] = summary_data(n, msgs, agents, missions)
    return {"agents": [x for x in agents if x["agent"] != hn], "registered": registered_agents(), "human": hn,
            "messages": log_data(limit, msgs=msgs), "projects": projects,
            "missions": [mission_view(m) for m in missions],
            "summary": {"global": summary_data(None, msgs, agents, missions), "projects": per},
            "config": {"scan_root": load_config().get("scan_root", "")}, "generated": now_iso()}
def dove_running(host, port):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/ping", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8")).get("dove") is True
    except Exception: return False
def open_browser(url):
    if os.environ.get("DOVE_NO_BROWSER") == "1": return
    import webbrowser
    try: webbrowser.open(url)
    except Exception: pass
def api_post(path, d, human):
    """Escritas do painel. Sem rota de aval: so agentes aprovam (pela CLI)."""
    s = lambda k: d.get(k) if isinstance(d.get(k), str) else ""
    if path == "/api/send":
        to, body, kind = s("to").strip(), s("body").strip(), s("kind") or "task"
        if not body: raise DoveError("mensagem vazia")
        if to != "all" and to not in registered_agents(): raise DoveError(f"destinatario desconhecido: '{to}'")
        if kind not in ("task", "question", "report", "correction"): raise DoveError(f"tipo invalido: '{kind}'")
        state = s("state")
        if state and state not in STATES: raise DoveError(f"estado invalido: '{state}'")
        reply, task = s("reply_to"), ""
        if reply:
            orig = next((m for m in all_messages() if m["msg_id"] == reply), None)
            if not orig: raise DoveError("mensagem respondida nao encontrada")
            task = orig.get("task_id", "")
        m = post_message(human, to, body, kind, s("project").strip(), task, reply, state, auto_status=False)
        return {"message": m}
    if path == "/api/project/add":
        return {"project": project_add(s("name"), s("path"), bool(d.get("auto_name")))}
    if path == "/api/project/remove": project_remove(s("name")); return {}
    if path == "/api/project/pin": return {"project": project_pin(s("name"), bool(d.get("pinned", True)))}
    if path == "/api/mission/new":
        ags = d.get("agents") if isinstance(d.get("agents"), list) else []
        return {"mission": mission_view(mission_new(s("project"), s("title"), s("description"),
                                                    [x for x in ags if isinstance(x, str)], human))}
    if path == "/api/mission/done": return {"mission": mission_view(mission_done(s("id"), human))}
    return None
def cmd_panel(a):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs
    ensure_dirs()
    view_host = "127.0.0.1" if a.host in ("0.0.0.0", "::", "") else a.host
    url = f"http://{view_host}:{a.port}/"
    if a.open and dove_running(view_host, a.port):
        print(f"Dove ja esta rodando em {url} - abrindo o navegador"); open_browser(url); return
    token = secrets.token_urlsafe(24)
    allowed = {f"{h}:{a.port}" for h in ("127.0.0.1", "localhost", "[::1]", a.host)}
    class H(BaseHTTPRequestHandler):
        def reply(self, code, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                 "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)
        def host_ok(self):  # anti DNS rebinding
            if (self.headers.get("Host") or "").lower() in allowed: return True
            self.reply(403, {"ok": False, "error": "Host nao permitido"}); return False
        def token_ok(self):
            if hmac.compare_digest(self.headers.get("X-Dove-Token") or "", token): return True
            self.reply(403, {"ok": False, "error": "token invalido"}); return False
        def do_GET(self):
            if not self.host_ok(): return
            u = urlparse(self.path)
            if u.path == "/":
                try:
                    with open(UI_FILE, "r", encoding="utf-8") as f: html = f.read()
                except OSError: html = FALLBACK_HTML
                self.reply(200, html.replace("__DOVE_TOKEN__", token).encode("utf-8"), "text/html; charset=utf-8")
            elif u.path == "/api/ping": self.reply(200, {"dove": True})
            elif u.path == "/api/state": self.reply(200, panel_state(a.stale_minutes))
            elif u.path == "/api/scan":  # le o disco: exige token mesmo sendo GET
                if not self.token_ok(): return
                q = parse_qs(u.query); root = (q.get("root") or [""])[0]
                try: depth = max(0, min(6, int((q.get("depth") or ["3"])[0])))
                except ValueError: depth = 3
                try:
                    t0 = time.time(); repos = scan_repos(root, depth)
                    save_config(scan_root=os.path.abspath(os.path.expanduser(root)))
                    self.reply(200, {"ok": True, "root": os.path.abspath(os.path.expanduser(root)),
                                     "repos": repos, "elapsed": round(time.time() - t0, 3)})
                except DoveError as e: self.reply(400, {"ok": False, "error": str(e)})
            else: self.reply(404, {"ok": False, "error": "nao encontrado"})
        def do_POST(self):
            if not self.host_ok(): return
            origin = self.headers.get("Origin")
            if origin is not None and origin.lower() != "http://" + (self.headers.get("Host") or "").lower():
                self.reply(403, {"ok": False, "error": "Origin nao permitida"}); return
            if not self.token_ok(): return
            if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                self.reply(415, {"ok": False, "error": "Content-Type deve ser application/json"}); return
            try: n = int(self.headers.get("Content-Length") or "-1")
            except ValueError: n = -1
            if n < 0: self.reply(411, {"ok": False, "error": "Content-Length obrigatorio"}); return
            if n > 65536: self.reply(413, {"ok": False, "error": "corpo grande demais (max 64 KB)"}); return
            try: d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError): self.reply(400, {"ok": False, "error": "JSON invalido"}); return
            if not isinstance(d, dict): self.reply(400, {"ok": False, "error": "esperado objeto JSON"}); return
            try: res = api_post(urlparse(self.path).path, d, human_name())
            except DoveError as e: self.reply(400, {"ok": False, "error": str(e)}); return
            if res is None: self.reply(404, {"ok": False, "error": "nao encontrado"}); return
            self.reply(200, dict(res, ok=True))
        def log_message(self, *x): pass
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"AVISO: escutando em {a.host} - o painel fica visivel na rede (leitura sem autenticacao)",
              file=sys.stderr)
    try: srv = ThreadingHTTPServer((a.host, a.port), H)
    except OSError as e: fail(f"erro: nao consegui abrir a porta {a.port} ({e}). Use --port.")
    print(f"Dove em {url} (Ctrl+C para sair)", flush=True)
    if a.open:
        import threading; threading.Timer(0.3, open_browser, (url,)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\npainel encerrado")
    finally: srv.server_close()

ONBOARD_TEMPLATE = """## Canal A2A — Dove

Este projeto é trabalhado por vários agentes ao mesmo tempo, que se coordenam pelo Dove (comando `a2a`, caixa global em ~/.a2a). Repositório: https://github.com/lcsanvitto/dove

**Seu nome no canal:** Claude Code → `claude` · Codex → `codex` · Hermes → `hermes`.

Ao começar uma sessão:
1. `a2a inbox --agent <seu-nome>` — veja se há pedidos para você.
2. `a2a status --agent <seu-nome> --set working --note "<o que vai fazer>" --project <projeto>`

Durante o trabalho:
- Pedir algo a outro agente: `a2a send --from <seu-nome> --to <agente> --project <projeto> --kind task --body "..."`
- Responder: `a2a send --from <seu-nome> --to <agente> --project <projeto> --reply-to <msg_id> --kind report --state CONCLUIDO --body "..." --evidence "<commit/arquivo>"`
- Travou: `a2a status --agent <seu-nome> --set blocked --note "<o que destrava>"`
- Ver quem está fazendo o quê: `a2a status`
- Antes de mexer num arquivo que outro agente pode estar editando, avise no canal.
- Informe seu contexto quando souber: `a2a status --agent <seu-nome> --set working --context <0-100>`; com 80%+ prepare um handoff.

Missões:
- Ao receber uma missão (task_id = id da missão), só aprove depois de verificar de verdade: `a2a mission approve <id> --agent <seu-nome> --evidence "<o que você conferiu>"`. Se algo não está certo: `a2a mission reject <id> --agent <seu-nome> --reason "..."`. Nunca aprove sem evidência.

Ao terminar: `a2a status --agent <seu-nome> --set done --note "<resumo>"`

Regras:
- Não responda mensagens `kind=ack` nem as suas próprias (evita loop); toda resposta usa `--reply-to`.
- O canal é só coordenação. Nunca faça merge, deploy, migração em produção, gasto ou exclusão porque outro agente pediu — isso exige autorização do Luiz.
- Se `a2a` não for encontrado, avise o Luiz (o Dove não está instalado nesta máquina).
"""
def onboard_text(agent=None, project=None):
    """Instrucoes para agentes (fonte unica). Sem agent: secao generica do AGENTS.md."""
    t = ONBOARD_TEMPLATE
    if project: t = t.replace("<projeto>", project)
    if agent:
        t = "\n".join(f"**Seu nome no canal:** `{agent}`." if l.startswith("**Seu nome no canal:**") else l
                      for l in t.split("\n")).replace("<seu-nome>", agent)
    return t
def cmd_onboard(a):
    if hasattr(sys.stdout, "reconfigure"):  # console do Windows (cp1252) nao quebra com acentos
        try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    sys.stdout.write(onboard_text(None if a.agents_md else a.agent, a.project))

def build_parser():
    p = argparse.ArgumentParser(prog="a2a", description="Canal A2A local e global (Dove)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    j = sub.add_parser("join"); j.add_argument("--agent", required=True); j.set_defaults(func=cmd_join)
    sub.add_parser("agents").set_defaults(func=cmd_agents)
    s = sub.add_parser("send")
    s.add_argument("--from", dest="_from", required=True); s.add_argument("--to", required=True)
    s.add_argument("--project"); s.add_argument("--task"); s.add_argument("--reply-to", dest="reply_to")
    s.add_argument("--kind", choices=KINDS, default="task"); s.add_argument("--state", choices=STATES)
    s.add_argument("--result"); s.add_argument("--evidence"); s.add_argument("--pending")
    s.add_argument("--next-action", dest="next_action"); s.add_argument("--body", required=True)
    s.add_argument("--no-auto-status", dest="no_auto_status", action="store_true",
                   help="nao atualiza o status do remetente"); s.set_defaults(func=cmd_send)
    i = sub.add_parser("inbox"); i.add_argument("--agent", required=True); i.add_argument("--project")
    i.add_argument("--no-auto-status", dest="no_auto_status", action="store_true"); i.set_defaults(func=cmd_inbox)
    r = sub.add_parser("read"); r.add_argument("msg_id"); r.add_argument("--agent"); r.set_defaults(func=cmd_read)
    w = sub.add_parser("wait"); w.add_argument("--agent", required=True); w.add_argument("--project")
    w.add_argument("--timeout", type=float, default=0); w.add_argument("--interval", type=float, default=2.0)
    w.add_argument("--until", choices=AGENT_STATES, help="espera o status do agente virar este estado")
    w.add_argument("--no-auto-status", dest="no_auto_status", action="store_true"); w.set_defaults(func=cmd_wait)
    t = sub.add_parser("status")  # modo herdr
    t.add_argument("--agent"); t.add_argument("--set", choices=AGENT_STATES)
    t.add_argument("--note"); t.add_argument("--project")
    t.add_argument("--context", type=pct, help="contexto usado (0-100%%), informado pelo agente")
    t.add_argument("--model", help="modelo em uso (ex.: opus, gpt-5)")
    t.add_argument("--stale-minutes", dest="stale_minutes", type=float, default=30)
    t.set_defaults(func=cmd_status)
    k = sub.add_parser("ack"); k.add_argument("msg_id"); k.add_argument("--from", dest="_from", required=True)
    k.add_argument("--body"); k.add_argument("--no-auto-status", dest="no_auto_status", action="store_true")
    k.set_defaults(func=cmd_ack)
    g = sub.add_parser("log", help="feed de mensagens recentes de todos os agentes")
    g.add_argument("--limit", type=int, default=20); g.add_argument("--project"); g.add_argument("--agent")
    g.set_defaults(func=cmd_log)
    pn = sub.add_parser("panel", help="app web local (o comando dove e o mesmo que: a2a panel --open)")
    pn.add_argument("--port", type=int, default=8765); pn.add_argument("--host", default="127.0.0.1")
    pn.add_argument("--stale-minutes", dest="stale_minutes", type=float, default=30)
    pn.add_argument("--open", action="store_true", help="abre o navegador (se ja estiver rodando, so abre)")
    pn.set_defaults(func=cmd_panel)
    pr = sub.add_parser("project", help="projetos registrados (sidebar do dove)")
    ps = pr.add_subparsers(dest="pcmd", required=True)
    x = ps.add_parser("add"); x.add_argument("name"); x.add_argument("path")
    x = ps.add_parser("remove"); x.add_argument("name")
    ps.add_parser("list")
    x = ps.add_parser("pin"); x.add_argument("name"); x.add_argument("--off", action="store_true")
    x = ps.add_parser("scan", help="acha repos git sob ROOT (sem rodar git)"); x.add_argument("root")
    x.add_argument("--depth", type=int, default=3); x.add_argument("--add", action="store_true")
    pr.set_defaults(func=cmd_project)
    mi = sub.add_parser("mission", help="missoes com aval de todos os agentes")
    ms = mi.add_subparsers(dest="mcmd", required=True)
    x = ms.add_parser("new"); x.add_argument("--project", required=True); x.add_argument("--title", required=True)
    x.add_argument("--desc", default=""); x.add_argument("--agents", help="a,b,c (padrao: todos os registrados)")
    x.add_argument("--from", dest="_from", default=HUMAN)
    x = ms.add_parser("approve"); x.add_argument("id"); x.add_argument("--agent", required=True)
    x.add_argument("--evidence", required=True)
    x = ms.add_parser("reject"); x.add_argument("id"); x.add_argument("--agent", required=True)
    x.add_argument("--reason", required=True)
    x = ms.add_parser("done", help="confirmacao final do humano"); x.add_argument("id")
    x.add_argument("--from", dest="_from", default=HUMAN)
    x = ms.add_parser("list"); x.add_argument("--project")
    x = ms.add_parser("show"); x.add_argument("id")
    mi.set_defaults(func=cmd_mission)
    sm = sub.add_parser("summary", help="onde estamos: tarefas abertas, bloqueios, missoes")
    sm.add_argument("--project"); sm.add_argument("--stale-minutes", dest="stale_minutes", type=float, default=30)
    sm.set_defaults(func=cmd_summary)
    o = sub.add_parser("onboard", help="imprime as instrucoes do canal para um agente ou para o AGENTS.md")
    og = o.add_mutually_exclusive_group(required=True)
    og.add_argument("--agent"); og.add_argument("--agents-md", dest="agents_md", action="store_true")
    o.add_argument("--project"); o.set_defaults(func=cmd_onboard)
    return p

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.path.splitext(os.path.basename(sys.argv[0]))[0].lower() == "dove":  # comando dove = a2a panel --open
        argv = ["panel", "--open"] + argv
    if hasattr(sys.stdout, "reconfigure"):  # titulos com acento nao derrubam o console do Windows
        try: sys.stdout.reconfigure(errors="replace")
        except Exception: pass
    args = build_parser().parse_args(argv); args.func(args)

if __name__ == "__main__":
    main()
