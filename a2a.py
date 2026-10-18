#!/usr/bin/env python3
"""a2a (Dove) - canal de mensagens agente-a-agente, local e global."""
import argparse, glob, json, os, sys, time, uuid
from datetime import datetime, timezone

HOME = os.environ.get("A2A_HOME", os.path.expanduser("~/.a2a"))
BUS, CURSOR, AGENTS, STATUS = (os.path.join(HOME, d) for d in ("bus", "cursor", "agents", "status"))
STATES = ["AGUARDANDO_ACEITE","ACEITO","EM_EXECUCAO","BLOQUEADO",
          "AGUARDANDO_APROVACAO","EM_REVISAO","CONCLUIDO","CANCELADO"]
KINDS = ["task","report","question","correction","ack"]
AGENT_STATES = ["working","idle","blocked","done","unknown"]  # vocabulario herdr
MSG_TO_AGENT = {"ACEITO": "working", "EM_EXECUCAO": "working", "BLOQUEADO": "blocked",
                "AGUARDANDO_APROVACAO": "blocked", "CONCLUIDO": "done", "CANCELADO": "done"}  # auto-status

def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ensure_dirs():
    for d in (BUS, CURSOR, AGENTS, STATUS): os.makedirs(d, exist_ok=True)
def seen_path(a): return os.path.join(CURSOR, a + ".json")
def load_seen(a):
    p = seen_path(a)
    try: return set(json.load(open(p))) if os.path.exists(p) else set()
    except Exception: return set()
def mark_seen(a, mid):
    s = load_seen(a); s.add(mid); json.dump(sorted(s), open(seen_path(a), "w"))
def _chrono(f):  # ts do nome do arquivo; desempate pela ordem de escrita (mtime)
    try: return (os.path.basename(f)[:16], os.path.getmtime(f))
    except OSError: return (os.path.basename(f)[:16], 0)
def all_messages():
    out = []
    for f in sorted(glob.glob(os.path.join(BUS, "*.json")), key=_chrono):
        try: out.append(json.load(open(f)))
        except Exception: pass
    return out
def visible_for(m, agent, project=None):
    if m["to"] not in (agent, "all"): return False
    if m["from"] == agent: return False
    if project and m.get("project") != project: return False
    return True

def cmd_init(a): ensure_dirs(); print(f"a2a pronto em {HOME}")
def cmd_join(a):
    ensure_dirs(); open(os.path.join(AGENTS, a.agent), "w").close()
    print(f"agente '{a.agent}' registrado. Caixa global: {HOME}")
def cmd_agents(a):
    ensure_dirs(); n = sorted(os.listdir(AGENTS))
    print("\n".join(n) if n else "(nenhum agente registrado)")
def cmd_send(a):
    ensure_dirs(); mid = uuid.uuid4().hex[:12]; ts = now_iso()
    msg = {"data": ts, "task_id": a.task or "", "msg_id": mid, "from": a._from,
           "to": a.to, "project": a.project or "", "in_reply_to": a.reply_to or "",
           "kind": a.kind, "state": a.state or "", "result": a.result or "",
           "evidence": a.evidence or "", "pending": a.pending or "",
           "next_action": a.next_action or "", "body": a.body or ""}
    fn = f"{ts.replace(':','').replace('-','')}-{mid}.json"
    json.dump(msg, open(os.path.join(BUS, fn), "w"), ensure_ascii=False, indent=2)
    mark_seen(a._from, mid)
    if not getattr(a, "no_auto_status", False):
        touch_status(a._from, MSG_TO_AGENT.get(a.state or ""), a.project)
    print(f"enviado {mid} ({a._from} -> {a.to})")
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

def status_path(a): return os.path.join(STATUS, a + ".json")
def load_status(a):
    p = status_path(a)
    try: return json.load(open(p)) if os.path.exists(p) else None
    except Exception: return None
def fmt_age(ts):
    if not ts: return "-"
    s = max(0, time.time() - ts)
    if s < 60: return f"{int(s)}s"
    if s < 3600: return f"{int(s // 60)}m"
    if s < 86400: return f"{int(s // 3600)}h"
    return f"{int(s // 86400)}d"
def write_status(st):
    st.update(updated=now_iso(), ts=time.time())
    json.dump(st, open(status_path(st["agent"]), "w"), ensure_ascii=False, indent=2)
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
                       "updated": "", "stale": False}
    state, ts = st.get("state", "unknown"), st.get("ts") or 0
    note, stale = st.get("note", ""), not ts or time.time() - ts > stale_min * 60
    if stale: note = (note + " " if note else "") + f"(stale, era {state})"; state = "unknown"
    return {"agent": name, "state": state, "age": fmt_age(ts), "project": st.get("project") or "",
            "note": note, "updated": st.get("updated", ""), "stale": bool(stale)}
def board_data(stale_min, agent=None):
    ensure_dirs()
    names = [agent] if agent else sorted(set(os.listdir(AGENTS)) |
                                         {f[:-5] for f in os.listdir(STATUS) if f.endswith(".json")})
    return [effective_status(n, load_status(n), stale_min) for n in names]
def status_line(name, st, stale_min):
    if not st: return f"{name:<12} {'unknown':<8} {'-':>4}"
    e = effective_status(name, st, stale_min)
    return f"{name:<12} {e['state']:<8} {e['age']:>4}  {e['project'] or '-':<10} {e['note']}".rstrip()
def cmd_status(a):
    ensure_dirs()
    if a.set:
        if not a.agent: print("--set exige --agent", file=sys.stderr); sys.exit(1)
        write_status({"agent": a.agent, "state": a.set, "note": a.note or "", "project": a.project or ""})
        print(f"status de '{a.agent}': {a.set}" + (f" ({a.note})" if a.note else "")); return
    if a.agent: print(status_line(a.agent, load_status(a.agent), a.stale_minutes)); return
    names = [e["agent"] for e in board_data(a.stale_minutes)]
    if not names: print("(nenhum agente)"); return
    for n in names: print(status_line(n, load_status(n), a.stale_minutes))

def log_data(limit=20, project=None, agent=None):
    """Mensagens recentes de todos os agentes, em ordem cronologica (mais nova por ultimo)."""
    msgs = [m for m in all_messages() if (not project or m.get("project") == project)
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

PANEL_HTML = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dove - painel A2A</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--mut:#6b7280;--bd:#e3e6ea;--working:#1f9d55;--idle:#6b7280;
--blocked:#d97706;--done:#2563eb;--unknown:#9ca3af}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--fg:#e6e8eb;--mut:#9aa1ab;--bd:#2c313a;
--working:#34c77b;--idle:#8b929c;--blocked:#f0a340;--done:#5b8cf5;--unknown:#6b7280}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;align-items:baseline;gap:12px;padding:16px 24px;border-bottom:1px solid var(--bd)}
h1{font-size:18px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 10px}
#gen{color:var(--mut);font-size:12px;margin-left:auto}main{padding:20px 24px;display:grid;gap:24px;max-width:1200px}
section{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;overflow-x:auto}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--bd);vertical-align:top}
th{font-weight:600;color:var(--mut);font-size:12px}tr:last-child td{border-bottom:0}
.b{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:600;color:#fff;background:var(--unknown)}
.b.working{background:var(--working)}.b.idle{background:var(--idle)}.b.blocked{background:var(--blocked)}.b.done{background:var(--done)}
.mut{color:var(--mut)}.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}.body{white-space:pre-wrap;word-break:break-word}
</style></head><body>
<header><h1>Dove</h1><span class="mut">painel A2A (somente leitura)</span><span id="gen"></span></header>
<main>
<section><h2>Agentes</h2><table><thead><tr><th>Agente</th><th>Estado</th><th>Idade</th><th>Projeto</th><th>Nota</th></tr></thead>
<tbody id="agents"></tbody></table></section>
<section><h2>Mensagens recentes</h2><table><thead><tr><th>Hora</th><th>De &rarr; Para</th><th>Tipo/estado</th><th>Projeto</th><th>Mensagem</th></tr></thead>
<tbody id="msgs"></tbody></table></section>
</main>
<script>
function td(text,cls){var c=document.createElement("td");c.textContent=text==null?"":String(text);if(cls)c.className=cls;return c}
function fill(id,rows,empty,cols){var tb=document.getElementById(id);tb.replaceChildren();
 if(!rows.length){var tr=document.createElement("tr"),c=td(empty,"mut");c.colSpan=cols;tr.appendChild(c);tb.appendChild(tr)}
 return tb}
function render(s){
 var tb=fill("agents",s.agents,"(nenhum agente)",5);
 s.agents.forEach(function(a){var tr=document.createElement("tr");tr.appendChild(td(a.agent));
  var c=document.createElement("td"),b=document.createElement("span");b.className="b "+String(a.state).replace(/[^a-z]/g,"");
  b.textContent=a.state;c.appendChild(b);tr.appendChild(c);
  tr.appendChild(td(a.age,"mut"));tr.appendChild(td(a.project||"-"));tr.appendChild(td(a.note,"mut"));tb.appendChild(tr)});
 tb=fill("msgs",s.messages,"(nenhuma mensagem)",5);
 s.messages.slice().reverse().forEach(function(m){var tr=document.createElement("tr");
  tr.appendChild(td((m.data||"").replace("T"," ").replace("Z",""),"mono mut"));
  tr.appendChild(td((m.from||"")+" \u2192 "+(m.to||"")));
  tr.appendChild(td((m.kind||"")+(m.state?"/"+m.state:""),"mono"));
  tr.appendChild(td(m.project||"-"));tr.appendChild(td(m.body,"body"));tb.appendChild(tr)});
 document.getElementById("gen").textContent="atualizado "+s.generated}
function tick(){fetch("/api/state",{cache:"no-store"}).then(function(r){return r.json()}).then(render)
 .catch(function(){document.getElementById("gen").textContent="sem conexao com o painel"})}
tick();setInterval(tick,3000);
</script></body></html>"""
def panel_state(stale_min=30, limit=30):
    return {"agents": board_data(stale_min), "messages": log_data(limit), "generated": now_iso()}
def cmd_panel(a):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    ensure_dirs()
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/": body, ctype = PANEL_HTML.encode("utf-8"), "text/html; charset=utf-8"
            elif path == "/api/state":
                body = json.dumps(panel_state(a.stale_minutes), ensure_ascii=False).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            else: self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *x): pass
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"AVISO: escutando em {a.host} - o painel fica visivel na rede (sem autenticacao)", file=sys.stderr)
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(f"Painel em http://{a.host}:{a.port} (Ctrl+C para sair)", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\npainel encerrado")
    finally: srv.server_close()

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
    t.add_argument("--stale-minutes", dest="stale_minutes", type=float, default=30)
    t.set_defaults(func=cmd_status)
    k = sub.add_parser("ack"); k.add_argument("msg_id"); k.add_argument("--from", dest="_from", required=True)
    k.add_argument("--body"); k.add_argument("--no-auto-status", dest="no_auto_status", action="store_true")
    k.set_defaults(func=cmd_ack)
    g = sub.add_parser("log", help="feed de mensagens recentes de todos os agentes")
    g.add_argument("--limit", type=int, default=20); g.add_argument("--project"); g.add_argument("--agent")
    g.set_defaults(func=cmd_log)
    pn = sub.add_parser("panel", help="painel web local (somente leitura)")
    pn.add_argument("--port", type=int, default=8765); pn.add_argument("--host", default="127.0.0.1")
    pn.add_argument("--stale-minutes", dest="stale_minutes", type=float, default=30)
    pn.set_defaults(func=cmd_panel)
    return p

if __name__ == "__main__":
    args = build_parser().parse_args(); args.func(args)
