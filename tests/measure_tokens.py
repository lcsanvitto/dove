#!/usr/bin/env python3
"""Medicao reprodutivel de tokens (proposta docs/propostas/2026-10-19-economia-de-tokens.md, secao "Como medir").

Unidade: chars = len(texto), bytes = len(texto.encode("utf-8")), tokens_est = ceil(chars / 4), medido no stdout
de cada comando. Cenarios fixos (ids, textos, relogio e datas de commit fixos) num A2A_HOME temporario: a mesma saida
a cada execucao.

M1. Nucleo x guia: `a2a onboard --agents-md --project lagu` (o que vai no AGENTS.md, carregado em toda sessao) x
    `a2a onboard --agent codex --project lagu` (o guia completo, lido sob demanda); e o nucleo global
    (`a2a onboard --agent claude --global-core`, o que `a2a instructions` grava nos arquivos globais). Com --agents-md CAMINHO tambem
    mede a secao do Dove de um AGENTS.md real (de "## Canal A2A" ate o proximo "## " ou o fim).
M2. Estabilidade do prefixo: `a2a prompt --prefix-hash` duas vezes no cenario do measure_brief.py, com 2 mensagens
    novas, uma troca de status e o relogio 10 minutos adiante entre as execucoes. Esperado: prefixo igual, cauda muda.
M3. Custo de relembrar o projeto: missao com 12 mensagens e 3 decisoes. Antes: `mission show` + `read --compact` de
    cada mensagem. Depois: `brief --project` com as linhas F (memoria do projeto, `a2a fact`).
M4. Mapa: repositorio sintetico com 60 arquivos em 5 linguagens. Antes: `git ls-files` + `head -40` de cada arquivo.
    Depois: `a2a map show`; e, apos mudar 1 arquivo e fazer commit, `a2a map build` deve dizer 1 refeito.
Medidas cujo comando ainda nao existe nesta versao do a2a aparecem como "pendente" (com o "antes" ja medido).

Uso: python3 tests/measure_tokens.py [--agents-md CAMINHO] [--show]   (--show imprime as saidas brutas). So stdlib.
"""
import calendar, hashlib, json, math, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from measure_brief import A2A, AGENT, B, a2a, measure, seed_home, write_msg  # mesmo cenario e mesmas contas
from measure_bus import has_cmd

NOW = calendar.timegm((2026, 10, 19, 12, 0, 0))  # relogio fixo dos cenarios (M2, M3)
SHOW = []  # (titulo, texto) para --show

# roda o a2a em processo com o relogio fixo (time.time); prompt/brief/status usam time.time para idades e heartbeat
INPROC = r"""
import sys, time
fixed = float(sys.argv[2]); time.time = lambda: fixed
sys.path.insert(0, sys.argv[1]); import a2a
a2a.main(sys.argv[3:])
"""
def a2a_at(home, now, *args):
    env = dict(os.environ, A2A_HOME=home, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", INPROC, os.path.dirname(A2A), str(now), *args], capture_output=True, env=env)
    assert r.returncode == 0, (args, r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8")

def stats(text):
    return {"lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1), **measure([("", text)])}

def table(rows, first="texto", width=40, lines=True):
    """rows: [(nome, stats)]; reducao contra a primeira linha."""
    base = rows[0][1]["tokens"]
    print(f"{first:<{width}} " + (f"{'linhas':>6} " if lines else "") + f"{'chars':>7} {'bytes':>7} {'tokens_est':>10} {'reducao':>8}")
    for i, (name, r) in enumerate(rows):
        red = "-" if i == 0 or not base else f"{100 * (1 - r['tokens'] / base):.1f}%"
        print(f"{name:<{width}} " + (f"{r['lines']:>6} " if lines else "") +
              f"{r['chars']:>7} {r['bytes']:>7} {r['tokens']:>10} {red:>8}")

def pending(what): print(f"  pendente: {what}")

# ---------------------------------------------------------------- M1
def dove_section(path):
    """Secao do Dove num AGENTS.md: de '## Canal A2A' ate o proximo titulo '## ' (ou o fim)."""
    with open(path, encoding="utf-8") as f: lines = f.read().replace("\r\n", "\n").split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("## Canal A2A")), None)
    if start is None: return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n") + "\n"

def m1(root, agents_md):
    home = os.path.join(root, "m1")
    core = a2a(home, "onboard", "--agents-md", "--project", "lagu")
    guide = a2a(home, "onboard", "--agent", AGENT, "--project", "lagu")
    rows = [("guia completo (onboard --agent codex)", stats(guide)), ("nucleo (onboard --agents-md)", stats(core))]
    glob_core = a2a(home, "onboard", "--agent", "claude", "--global-core") if "--global-core" in a2a(home, "onboard", "--help") else None
    if glob_core is not None:
        rows.append(("nucleo global (onboard --global-core)", stats(glob_core)))
        SHOW.append(("M1 nucleo global (claude)", glob_core))
    sec = dove_section(agents_md) if agents_md else None
    if sec is not None:
        name = os.path.basename(os.path.dirname(os.path.abspath(agents_md))) or "."
        rows.append((f"secao do Dove em {name}/AGENTS.md", stats(sec)))
        SHOW.append((f"M1 secao de {agents_md}", sec))
    print("M1. Nucleo do AGENTS.md x guia completo (o nucleo e carregado em toda sessao; o guia, sob demanda)")
    table(rows)
    print(f"  economia por sessao e por agente: ≈{rows[0][1]['tokens'] - rows[1][1]['tokens']} tokens_est "
          "(o que saiu do AGENTS.md para o guia)")
    if glob_core is not None:
        print("  nucleo global: o que a2a instructions grava em ~/.claude/CLAUDE.md e ~/.codex/AGENTS.md (uma vez para todos os projetos)")
    if sec is not None:
        print("  secao do AGENTS.md: " + ("igual ao nucleo" if sec == core else
              f"difere do nucleo ({rows[-1][1]['tokens'] - rows[1][1]['tokens']:+d} tokens_est; a2a onboard --agents-md --project <nome>)"))
    SHOW.extend((("M1 nucleo", core), ("M1 guia", guide)))

# ---------------------------------------------------------------- M2
def m2(root):
    print("\nM2. Estabilidade do prefixo (a2a prompt --prefix-hash; cenario do measure_brief.py, agente codex, projeto lagu)")
    if not has_cmd("prompt"):
        pending("a2a prompt ainda nao existe nesta versao (passo 3 da proposta)"); return
    home = os.path.join(root, "m2"); t_open = seed_home(home, now=NOW)
    args = ("prompt", "--agent", AGENT, "--project", "lagu", "--task", t_open)
    def run(now):
        hs = a2a_at(home, now, *args, "--prefix-hash").splitlines()
        full = a2a_at(home, now, *args)
        pre = dict(kv.split("=", 1) for kv in hs[0].split()[1:]); tail = dict(kv.split("=", 1) for kv in hs[1].split()[1:])
        return pre, tail, full, hs
    p1, c1, full1, h1 = run(NOW)
    # entre as execucoes: 2 mensagens novas para codex, troca de status e o relogio 10 minutos adiante
    for i, (frm, kind, body) in enumerate((("claude", "task", B["review"]), ("hermes", "report", B["perf"]))):
        t = NOW + 120 + 60 * i
        mid = hashlib.sha1(f"m2:{i}".encode()).hexdigest()[:12]
        write_msg(home, {"data": f"2026-10-19T12:0{2 + i}:00Z", "task_id": "", "msg_id": mid, "from": frm, "to": AGENT,
                         "project": "lagu", "in_reply_to": "", "kind": kind, "state": "", "result": "", "evidence": "",
                         "pending": "", "next_action": "", "body": body}, t)
    a2a_at(home, NOW + 300, "status", "--agent", AGENT, "--set", "blocked", "--note", "falta a credencial do banco", "--project", "lagu")
    p2, c2, full2, h2 = run(NOW + 600)
    print(f"{'execucao':<34} {'prefixo sha256':>14} {'chars':>6} {'tokens_est':>10} {'cauda sha256':>14} {'chars':>6}")
    for name, p, c in (("1a (12:00)", p1, c1), ("2a (12:10, +2 msgs, status novo)", p2, c2)):
        print(f"{name:<34} {p['sha256']:>14} {p['chars']:>6} {p['tokens_est']:>10} {c['sha256']:>14} {c['chars']:>6}")
    same = p1["sha256"] == p2["sha256"] and full1[:int(p1["chars"])] == full2[:int(p2["chars"])]
    total = stats(full2)
    print(f"  prefixo {'IDENTICO' if same else 'DIFERENTE'} entre as execucoes; cauda "
          f"{'mudou' if c1['sha256'] != c2['sha256'] else 'NAO mudou'}; prefixo = "
          f"{100 * int(p2['chars']) / total['chars']:.0f}% do prompt ({total['chars']} chars, {total['tokens']} tokens_est)")
    assert same and c1["sha256"] != c2["sha256"], (h1, h2)
    SHOW.extend((("M2 prompt (1a execucao)", full1), ("M2 prompt (2a execucao)", full2)))

# ---------------------------------------------------------------- M3
M3_MISSION = "m4c1e9a0"
M3_DECISIONS = ("Frete gratis acima de R$ 199 no carrinho e no checkout; regra antiga (R$ 249) removida",
                "Subtotal arredondado com Decimal ROUND_HALF_EVEN antes do desconto (commit 3c41d2e)",
                "Antifraude assincrono fica para outra tarefa; o checkout responde 202 enquanto analisa")

def m3_seed(home):
    """Missao com 3 agentes e 12 mensagens no fio (task_id = id da missao)."""
    for d in ("bus", "cursor", "agents", "status", "missions"): os.makedirs(os.path.join(home, d), exist_ok=True)
    for a in ("claude", "codex", "hermes"): open(os.path.join(home, "agents", a), "w").close()
    M = M3_MISSION; title = "Frete gratis acima de R$ 199"
    thread = [("luiz", ag, "task", "", f"Missao {M}: {title}\nVerifique e de seu aval: a2a mission approve {M} --agent {ag} "
               f"--evidence \"...\" (ou: a2a mission reject {M} --agent {ag} --reason \"...\")", "") for ag in ("claude", "codex", "hermes")]
    thread += [("claude", "codex", "task", "", B["cupom"], ""), ("codex", "claude", "report", "EM_EXECUCAO", B["ok"], ""),
               ("hermes", "codex", "report", "CONCLUIDO", B["e2e"], "e2e/report.html"), ("codex", "hermes", "question", "", B["q"], ""),
               ("claude", "codex", "report", "AGUARDANDO_APROVACAO", B["fix"], "commit 3c41d2e"),
               ("hermes", "claude", "report", "EM_EXECUCAO", B["perf"], ""), ("codex", "claude", "report", "CONCLUIDO", B["review"], ""),
               ("hermes", "luiz", "report", "CONCLUIDO", B["deploy"], "staging 9be1c0a"), ("claude", "luiz", "report", "CONCLUIDO", B["doc"], "")]
    ids = []
    for i, (frm, to, kind, state, body, evid) in enumerate(thread):
        t = NOW - 3 * 3600 + i * 600; mid = hashlib.sha1(f"m3:{i}".encode()).hexdigest()[:12]; ids.append(mid)
        write_msg(home, {"data": f"2026-10-19T{9 + i // 6:02d}:{(i % 6) * 10:02d}:00Z", "task_id": M, "msg_id": mid,
                         "from": frm, "to": to, "project": "lagu", "in_reply_to": "", "kind": kind, "state": state,
                         "result": "", "evidence": evid, "pending": "", "next_action": "", "body": body}, t)
    with open(os.path.join(home, "missions", M + ".json"), "w", encoding="utf-8") as f:
        json.dump({"id": M, "project": "lagu", "title": title, "description": "Regra de frete gratis nova em producao",
                   "agents": ["claude", "codex", "hermes"], "created_by": "luiz", "created": "2026-10-19T09:00:00Z",
                   "approvals": {a: {"verdict": "approve", "ts": "2026-10-19T11:00:00Z", "evidence": "testes ok", "reason": ""}
                                 for a in ("claude", "hermes")}, "history": [], "human": None}, f, ensure_ascii=False, indent=2)
    assert len(ids) == 12
    return ids

def m3(root):
    print(f"\nM3. Custo de relembrar o projeto (missao {M3_MISSION} com 12 mensagens e 3 decisoes)")
    home = os.path.join(root, "m3"); ids = m3_seed(home)
    antes = [("mission show", a2a(home, "mission", "show", M3_MISSION))]
    antes += [(f"read {i} --compact", a2a(home, "read", i, "--compact")) for i in ids]
    ra = measure(antes)
    rows = [(f"antes (mission show + 12 read --compact)", ra)]
    if has_cmd("fact"):
        for d in M3_DECISIONS:
            a2a(home, "fact", "add", "--project", "lagu", "--from", "claude", "--scope", f"missao:{M3_MISSION}", d)
        b = a2a_at(home, NOW, "brief", "--agent", AGENT, "--project", "lagu", "--no-auto-status")
        f_lines = "".join(l + "\n" for l in b.splitlines() if l.startswith("F "))
        rows += [("depois (brief --project, com linhas F)", measure([("", b)])), ("  so as linhas F", measure([("", f_lines)]))]
        SHOW.append(("M3 depois (brief)", b))
    print(f"{'sequencia':<42} {'cmds':>4} {'chars':>7} {'bytes':>7} {'tokens_est':>10} {'reducao':>8}")
    for i, (name, r) in enumerate(rows):
        red = "-" if i == 0 else f"{100 * (1 - r['tokens'] / ra['tokens']):.1f}%"
        print(f"{name:<42} {r['cmds']:>4} {r['chars']:>7} {r['bytes']:>7} {r['tokens']:>10} {red:>8}")
    if len(rows) > 1: print(f"  linhas F {'<=' if rows[-1][1]['chars'] <= 3000 else '>'} teto da memoria (3000 chars)")
    else: pending("a2a fact ainda nao existe nesta versao (passo 4 da proposta; precisa de aval do Luiz)")
    SHOW.append(("M3 antes", "".join(o for _, o in antes)))

# ---------------------------------------------------------------- M4
LANGS = {  # extensao -> gerador de arquivo com simbolos de topo (texto fixo)
    "py": lambda n, k: "".join(f"def func_{n}_{j}(pedido, taxa=0.{j:02d}):\n    total = pedido.subtotal * taxa\n"
                               f"    return round(total + pedido.frete, 2)  # regra {j}\n\n" for j in range(k)) + f"class Modelo{n}:\n    pass\n",
    "js": lambda n, k: "".join(f"export function rota{n}_{j}(req, res) {{\n  const total = req.body.itens.length * {j};\n"
                               f"  return res.json({{ total }});\n}}\n\n" for j in range(k)) + f"export const api{n} = {{ versao: {n} }};\n",
    "go": lambda n, k: f"package pkg{n}\n\n" + "".join(f"func Calcula{n}_{j}(v float64) float64 {{\n\tr := v * {j}.5\n"
                                                        f"\treturn r + {n}\n}}\n\n" for j in range(k)) + f"type Tipo{n} struct {{ ID int }}\n",
    "sh": lambda n, k: "#!/usr/bin/env bash\nset -e\n" + "".join(f"tarefa_{n}_{j}() {{\n  echo \"passo {j} do script {n}\"\n"
                                                                 f"  sleep 0\n}}\n\n" for j in range(k)),
    "md": lambda n, k: f"# Documento {n}\n\n" + "".join(f"## Secao {j}\n\nTexto da secao {j} do documento {n}, com detalhes "
                                                        f"sobre a regra de negocio numero {j}.\n\n" for j in range(k)),
}
def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="dove", GIT_AUTHOR_EMAIL="dove@example.com", GIT_COMMITTER_NAME="dove",
               GIT_COMMITTER_EMAIL="dove@example.com", GIT_AUTHOR_DATE="2026-10-19T12:00:00Z",
               GIT_COMMITTER_DATE="2026-10-19T12:00:00Z")
    r = subprocess.run(["git", "-c", "core.quotepath=false", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false",
                        *args], cwd=cwd, capture_output=True, env=env)
    assert r.returncode == 0, (args, r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8")

def m4_repo(repo):
    os.makedirs(repo)
    dirs = {"py": "src/api", "js": "web/src", "go": "svc", "sh": "scripts", "md": "docs"}
    for ext, gen in LANGS.items():
        for n in range(12):
            p = os.path.join(repo, dirs[ext], f"mod{n:02d}.{ext}"); os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f: f.write(gen(n, 4 + n % 5))
    git(repo, "init", "-q"); git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "repo sintetico")

def m4(root):
    print("\nM4. Mapa do repositorio (repositorio sintetico: 60 arquivos em 5 linguagens)")
    if not shutil.which("git"): pending("git nao encontrado"); return
    repo = os.path.join(root, "m4-repo"); m4_repo(repo)
    files = git(repo, "ls-files").splitlines(); assert len(files) == 60, len(files)
    heads = []
    for i, f in enumerate(files):  # o que `head -40 <arquivos...>` imprime
        with open(os.path.join(repo, f), encoding="utf-8") as fh: body = "".join(fh.readlines()[:40])
        heads.append(("\n" if i else "") + f"==> {f} <==\n" + body)
    antes = [("git ls-files", "".join(l + "\n" for l in files)), ("head -40 (60 arquivos)", "".join(heads))]
    rows = [("antes (git ls-files + head -40 de cada)", measure(antes))]
    if has_cmd("map"):
        home = os.path.join(root, "m4-home")
        a2a(home, "project", "add", "syn", repo); a2a(home, "map", "build", "--project", "syn")
        show = a2a(home, "map", "show", "--project", "syn"); rows.append(("depois (a2a map show)", measure([("", show)])))
        with open(os.path.join(repo, "src/api/mod00.py"), "a", encoding="utf-8", newline="\n") as f: f.write("def nova():\n    pass\n")
        git(repo, "commit", "-q", "-am", "muda 1 arquivo")
        rebuild = a2a(home, "map", "build", "--project", "syn")
        SHOW.append(("M4 depois (map show)", show))
    print(f"{'sequencia':<42} {'cmds':>4} {'chars':>7} {'bytes':>7} {'tokens_est':>10} {'reducao':>8}")
    for i, (name, r) in enumerate(rows):
        red = "-" if i == 0 else f"{100 * (1 - r['tokens'] / rows[0][1]['tokens']):.1f}%"
        print(f"{name:<42} {r['cmds']:>4} {r['chars']:>7} {r['bytes']:>7} {r['tokens']:>10} {red:>8}")
    if len(rows) > 1:
        print(f"  mapa {'<=' if rows[1][1]['tokens'] <= 1024 else '>'} 1024 tokens_est; rebuild apos 1 commit: "
              f"{'1 refeito' if '1 refeito' in rebuild else rebuild.strip().splitlines()[0]}")
    else: pending("a2a map ainda nao existe nesta versao (passo 5 da proposta; precisa de aval do Luiz)")

def main():
    agents_md = sys.argv[sys.argv.index("--agents-md") + 1] if "--agents-md" in sys.argv else None
    root = tempfile.mkdtemp(prefix="dove-tokens-")
    try:
        print("tokens_est = ceil(chars / 4); medido no stdout de cada comando; cenarios fixos (mesma saida a cada execucao)\n")
        m1(root, agents_md); m2(root); m3(root); m4(root)
        if "--show" in sys.argv:
            for title, text in SHOW: print(f"\n===== {title} =====\n{text}", end="" if text.endswith("\n") else "\n")
    finally:
        shutil.rmtree(root, ignore_errors=True)

if __name__ == "__main__":
    main()
