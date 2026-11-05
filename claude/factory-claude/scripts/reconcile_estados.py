#!/usr/bin/env python3
"""Propone correcciones de la etiqueta `estado:` de los issues abiertos. Solo lectura: no cambia nada."""
import collections, json, os, re, subprocess, sys

OWNER = "pl0n3r"
REPOS = ["Condor", "GrindFlow", "brvtal", "Factory", "ControlBot", "AutoFactory", "FactoryRunner"]
EN = {"available": "disponible", "blocked": "bloqueado", "reserved": "reservado", "in review": "en revisión",
      "planned": "planificado", "needs recovery": "requiere recuperación", "completed": "completado", "cancelled": "cancelado"}
ES2EN = {v: k for k, v in EN.items()}
KIT = os.environ.get("FACTORY_SCRIPTS") or os.path.join(os.path.expanduser("~"), "Desktop", "Factory", "scripts")
DUENO = os.environ.get("DUENO_ISSUES", "")
import datetime
RECIENTE = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")


def gh_json(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise SystemExit(f"gh falló: {r.stderr[:200]}")
    return json.loads(r.stdout or "[]")


def main():
    sys.path.insert(0, KIT)
    import aceptacion_kit as k
    try:
        own = {(x["repo"], x["n"]) for x in json.load(open(DUENO))}
    except Exception:
        own = set()
    repos = [a for a in sys.argv[1:] if a in REPOS] or REPOS
    total = 0
    for r in repos:
        issues = {i["number"]: i for i in gh_json("issue", "list", "-R", f"{OWNER}/{r}", "--state", "open", "-L", "300",
                                                    "--json", "number,title,body,labels,comments")}
        prs = gh_json("pr", "list", "-R", f"{OWNER}/{r}", "--state", "open", "-L", "200", "--json", "number,body")
        por_issue = collections.defaultdict(list)
        for p in prs:
            for n in {int(x) for x in re.findall(r"(?:Closes|Fixes|Resolves|Refs?)\s+#(\d+)", p["body"] or "", re.I)}:
                por_issue[n].append(p["number"])
        for n, i in sorted(issues.items()):
            cur = next((EN.get(l["name"].split(": ", 1)[1], l["name"].split(": ", 1)[1]) for l in i["labels"]
                        if re.match(r"(estado|status):", l["name"])), None)
            body = i["body"] or ""
            try:
                k.parse_contract(body)
                valido = True
            except Exception:
                valido = False
            m = re.search(r"<!-- factory-plan-task (\{.*?\}) -->", body, re.S)
            deps = []
            if m:
                try:
                    deps = [d for d in json.loads(m.group(1)).get("depends_on", []) if isinstance(d, int)]
                except Exception:
                    pass
            abiertas = [d for d in deps if d in issues]
            rs = [c for c in i["comments"] if "condor-reserva" in c["body"] or "work-reservation" in c["body"]]
            activa = bool(rs) and '"active":true' in rs[-1]["body"]
            if n in por_issue:
                want, why = "en revisión", f"PR abierto #{por_issue[n][0]}"
            elif activa:
                want, why = "reservado", "reserva activa"
            elif cur == "planificado":
                continue
            elif (r, n) in own:
                want, why = "bloqueado", "espera al dueño"
            elif abiertas:
                want, why = "bloqueado", f"dependencia abierta #{abiertas[0]}"
            elif not valido:
                want, why = "bloqueado", "contrato inválido"
            else:
                want, why = "disponible", "sin dependencias abiertas y contrato válido"
            if want != cur:
                total += 1
                es = r != "brvtal"
                pre = "estado" if es else "status"
                nom = (lambda x: x) if es else (lambda x: ES2EN.get(x, x))
                aviso = ""
                if cur == "bloqueado" and want == "disponible":
                    ev = subprocess.run(["gh", "api", f"repos/{OWNER}/{r}/issues/{n}/events", "--paginate", "--jq",
                                         '[.[]|select(.event=="labeled" and (.label.name|test("bloqueado|blocked")))|.created_at]|last // ""'],
                                        capture_output=True, text=True).stdout.strip()
                    if ev and ev >= RECIENTE:
                        aviso = f"  [REVISAR: alguien lo bloqueó el {ev[:10]}; no lo liberes sin leer el motivo]"
                print(f"{r}#{n}: {cur} -> {want} ({why}) | {i['title'][:50]}{aviso}")
                print(f"   gh issue edit {n} -R {OWNER}/{r} --add-label '{pre}: {nom(want)}'" + (f" --remove-label '{pre}: {nom(cur)}'" if cur else ""))
    print(f"\n{total} cambios propuestos (nada aplicado).")


if __name__ == "__main__":
    main()
