#!/usr/bin/env python3
"""a2a (Dove) - canal de mensagens agente-a-agente, local e global."""
import argparse, glob, json, os, sys, time, uuid
from datetime import datetime, timezone

HOME = os.environ.get("A2A_HOME", os.path.expanduser("~/.a2a"))
BUS, CURSOR, AGENTS = (os.path.join(HOME, d) for d in ("bus", "cursor", "agents"))
STATES = ["AGUARDANDO_ACEITE","ACEITO","EM_EXECUCAO","BLOQUEADO",
          "AGUARDANDO_APROVACAO","EM_REVISAO","CONCLUIDO","CANCELADO"]
KINDS = ["task","report","question","correction","ack"]

def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ensure_dirs():
    for d in (BUS, CURSOR, AGENTS): os.makedirs(d, exist_ok=True)
def seen_path(a): return os.path.join(CURSOR, a + ".json")
def load_seen(a):
    p = seen_path(a)
    try: return set(json.load(open(p))) if os.path.exists(p) else set()
    except Exception: return set()
def mark_seen(a, mid):
    s = load_seen(a); s.add(mid); json.dump(sorted(s), open(seen_path(a), "w"))
def all_messages():
    out = []
    for f in sorted(glob.glob(os.path.join(BUS, "*.json"))):
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
    print(f"enviado {mid} ({a._from} -> {a.to})")
def cmd_inbox(a):
    ensure_dirs(); seen = load_seen(a.agent)
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
    ensure_dirs(); deadline = time.time() + a.timeout if a.timeout else None
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
    mark_seen(a._from, a.msg_id)
    cmd_send(argparse.Namespace(_from=a._from, to=orig["from"], task=orig.get("task_id"),
        project=orig.get("project"), reply_to=a.msg_id, kind="ack", state=None,
        result=None, evidence=None, pending=None, next_action=None,
        body=a.body or "recebido"))

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
    s.set_defaults(func=cmd_send)
    i = sub.add_parser("inbox"); i.add_argument("--agent", required=True); i.add_argument("--project")
    i.set_defaults(func=cmd_inbox)
    r = sub.add_parser("read"); r.add_argument("msg_id"); r.add_argument("--agent"); r.set_defaults(func=cmd_read)
    w = sub.add_parser("wait"); w.add_argument("--agent", required=True); w.add_argument("--project")
    w.add_argument("--timeout", type=float, default=0); w.add_argument("--interval", type=float, default=2.0)
    w.set_defaults(func=cmd_wait)
    k = sub.add_parser("ack"); k.add_argument("msg_id"); k.add_argument("--from", dest="_from", required=True)
    k.add_argument("--body"); k.set_defaults(func=cmd_ack)
    return p

if __name__ == "__main__":
    args = build_parser().parse_args(); args.func(args)
