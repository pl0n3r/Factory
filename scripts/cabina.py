#!/usr/bin/env python3
"""Cabina de mando de la fábrica: genera una página estática con el estado de todos los proyectos.

Solo lectura: consulta la API de GitHub y los /health públicos de cada sitio.
Uso: GH_TOKEN=... python3 scripts/cabina.py  (escribe site/index.html)
"""

from __future__ import annotations

import base64
import html
import importlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
VERSION_PATH = "config/version.php"
BOGOTA = timezone(timedelta(hours=-5))


class CollectionError(RuntimeError):
    """Una fuente externa no pudo verificarse."""


@dataclass
class Proyecto:
    nombre: str
    repo: str
    descripcion: str
    sitio: str | None
    health: str | None
    version_path: str
    version_re: str
    roadmap: int | None
    en: bool = False  # etiquetas en inglés (BRVTAL)
    etiquetas: dict[str, str] = field(default_factory=dict)


def etiquetas(en: bool) -> dict[str, str]:
    if en:
        return {
            "incidente": "type: incident",
            "critica": "priority: critical",
            "bloqueado": "status: blocked",
            "decision": "decision: owner",
        }
    return {
        "incidente": "tipo: incidente",
        "critica": "prioridad: crítica",
        "bloqueado": "estado: bloqueado",
        "decision": "decisión: dueño",
    }


PROYECTOS = [
    Proyecto("Condor", "pl0n3r/Condor", "Plataforma multi-empresa: catálogo, inventario, pedidos y tienda",
             "https://www.condorapp.com.co", "/health", VERSION_PATH,
             r"'version'\s*=>\s*'([^']+)'", 1),
    Proyecto("GrindFlow", "pl0n3r/GrindFlow", "SaaS de gestión corporativa",
             "https://www.grindflow.com.co", "/health", VERSION_PATH,
             r"'number'\s*=>\s*'([^']+)'", 2),
    Proyecto("BRVTAL", "pl0n3r/brvtal", "Sitio público y panel editorial DISCADMIN",
             "https://www.brvtal.com.co", "/api/health.php", VERSION_PATH,
             r"BRVTAL_APP_VERSION\s*=\s*'([^']+)'", 533, en=True),
    Proyecto("factory", "pl0n3r/factory", "Reglas, kit común y plan de agentes de la fábrica",
             None, None, "", "", 13),
    Proyecto("ControlBot", "pl0n3r/ControlBot", "Centro de control privado de la fábrica",
             None, None, "", "", 1),
]
for _p in PROYECTOS:
    _p.etiquetas = etiquetas(_p.en)


def http_json(url: str, token: str | None = None, timeout: float = 15) -> tuple[int, object]:
    headers = {"User-Agent": "fabrica-cabina", "Accept": "application/vnd.github+json"}
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cuerpo = resp.read(2_000_000)
            try:
                return resp.status, json.loads(cuerpo)
            except ValueError:
                return resp.status, None
    except urllib.error.HTTPError as err:
        return err.code, None
    except OSError:
        return 0, None


def gh(path: str, token: str) -> object:
    status, data = http_json(API + path, token)
    if status != 200 or data is None:
        raise CollectionError("GitHub API no disponible.")
    return data


def version_main(p: Proyecto, token: str) -> str | None:
    if not p.version_path:
        return None
    data = gh(f"/repos/{p.repo}/contents/{p.version_path}", token)
    if not isinstance(data, dict) or "content" not in data:
        return None
    texto = base64.b64decode(data["content"]).decode("utf-8", "replace")
    m = re.search(p.version_re, texto)
    return m.group(1) if m else None


def _health_payload_valid(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    status = str(data.get("status", "")).lower()
    return data.get("ok") is True or status in {"ok", "healthy"}


def salud(p: Proyecto) -> dict[str, object]:
    if not p.sitio or not p.health:
        return {"estado": "na"}
    codigo, data = http_json(p.sitio + p.health)
    info: dict[str, object] = {"codigo": codigo}
    if codigo >= 500:
        info["estado"] = "caido"
        return info
    if codigo != 200 or not _health_payload_valid(data):
        info["estado"] = "desconocido"
        return info

    assert isinstance(data, dict)
    dep = data.get("deployment") if isinstance(data.get("deployment"), dict) else {}
    info["version"] = data.get("version") or dep.get("version")
    info["sha"] = data.get("release_sha") or data.get("commit") or dep.get("commit")
    if "schema_up_to_date" in data:
        info["esquema"] = data.get("schema_up_to_date")
    info["estado"] = "ok"
    return info


def issues(p: Proyecto, token: str, etiqueta: str) -> list[dict]:
    q = urllib.parse.quote(etiqueta)
    data = gh(f"/repos/{p.repo}/issues?state=open&per_page=50&labels={q}", token)
    return [i for i in data if isinstance(i, dict) and "pull_request" not in i] if isinstance(data, list) else []


def auto_abiertos(p: Proyecto, token: str) -> list[dict]:
    data = gh(f"/repos/{p.repo}/issues?state=open&per_page=100", token)
    if not isinstance(data, list):
        return []
    return [i for i in data if "pull_request" not in i and str(i.get("title", "")).startswith("[AUTO]")]


def ci_main(p: Proyecto, token: str) -> dict[str, object] | None:
    data = gh(
        f"/repos/{p.repo}/actions/runs?branch=main&event=push&per_page=30",
        token,
    )
    runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
    for run in runs:
        if "ci" not in str(run.get("name", "")).lower():
            continue
        status = str(run.get("status") or "unknown")
        return {
            "status": status,
            "conclusion": (
                run.get("conclusion") if status == "completed" else None
            ),
            "url": run.get("html_url"),
            "sha": str(run.get("head_sha", ""))[:7],
        }
    return None


def contar_prs(p: Proyecto, token: str, desde: str) -> tuple[int, int]:
    abiertos = gh(f"/search/issues?q={urllib.parse.quote(f'repo:{p.repo} is:pr is:open')}&per_page=1", token)
    integrados = gh(f"/search/issues?q={urllib.parse.quote(f'repo:{p.repo} is:pr is:merged merged:>={desde}')}&per_page=1", token)
    a = abiertos.get("total_count", 0) if isinstance(abiertos, dict) else 0
    i = integrados.get("total_count", 0) if isinstance(integrados, dict) else 0
    return int(a), int(i)


def recolectar(token: str) -> dict:
    desde = (
        datetime.now(timezone.utc) - timedelta(days=7)
    ).strftime("%Y-%m-%d")
    salida = []
    for p in PROYECTOS:
        health = salud(p)
        github_ok = True
        try:
            principal = gh(f"/repos/{p.repo}/commits/main", token)
            sha_main = (
                principal.get("sha", "")
                if isinstance(principal, dict)
                else ""
            )
            et = p.etiquetas
            incidentes = issues(p, token, et["incidente"])
            vistos = {item["number"] for item in incidentes}
            incidentes += [
                item
                for item in auto_abiertos(p, token)
                if item["number"] not in vistos
            ]
            abiertos, integrados = contar_prs(p, token, desde)
            version = version_main(p, token)
            ci = ci_main(p, token)
            criticos = issues(p, token, et["critica"])
            bloqueados = issues(p, token, et["bloqueado"])
            decisiones = (
                issues(p, token, "decisión: dueño")
                + issues(p, token, "decision: owner")
            )
        except CollectionError:
            github_ok = False
            sha_main = ""
            incidentes = []
            abiertos = 0
            integrados = 0
            version = None
            ci = None
            criticos = []
            bloqueados = []
            decisiones = []

        salida.append({
            "p": p,
            "version_main": version,
            "sha_main": sha_main,
            "salud": health,
            "github_ok": github_ok,
            "ci": ci,
            "incidentes": incidentes,
            "criticos": criticos,
            "bloqueados": bloqueados,
            "decisiones": decisiones,
            "prs_abiertos": abiertos,
            "prs_semana": integrados,
        })
    return {
        "proyectos": salida,
        "generado": datetime.now(timezone.utc),
    }


def semaforo(d: dict) -> tuple[str, str]:
    s = d["salud"]
    if s.get("estado") == "na":
        return "gris", "Sin sitio"
    if s.get("estado") == "caido":
        codigo = s.get("codigo") or "sin respuesta"
        return "rojo", f"Caído (HTTP {codigo})"
    if s.get("estado") != "ok":
        return "gris", "Health no verificable"
    if not d.get("github_ok", True):
        return "gris", "Datos GitHub no disponibles"
    if s.get("esquema") is False:
        return "amarillo", "Esquema de BD atrasado"
    if d["incidentes"]:
        return "amarillo", f"{len(d['incidentes'])} incidente(s) abierto(s)"
    vm, vp = d["version_main"], s.get("version")
    if vm and vp and str(vm) != str(vp):
        return "amarillo", f"Producción en V {vp}; main en V {vm}"
    return "verde", "Sano"


def e(x: object) -> str:
    return html.escape(str(x), quote=True)


def lista(items: list[dict], vacio: str) -> str:
    if not items:
        return f'<p class="vacio">{e(vacio)}</p>'
    filas = "".join(
        f'<li><a href="{e(i["html_url"])}">#{i["number"]} {e(i["title"])}</a></li>' for i in items[:6]
    )
    extra = f'<li class="mas">y {len(items) - 6} más</li>' if len(items) > 6 else ""
    return f"<ul>{filas}{extra}</ul>"


def _render_ci(ci: dict[str, object] | None) -> str:
    """Renderiza el estado del CI más reciente sin ocultar ejecuciones pendientes."""
    if not ci:
        return "—"
    status = str(ci.get("status") or "unknown")
    url = e(ci.get("url") or "#")
    if status != "completed":
        return f'<a href="{url}">⏳ {e(status)}</a>'
    conclusion = ci.get("conclusion")
    icono = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⚪",
    }.get(str(conclusion), "⚠️")
    return f'<a href="{url}">{icono} {e(conclusion)}</a>'


def _render_card(d: dict) -> tuple[str, str]:
    """Construye una tarjeta y devuelve también su color agregado."""
    p: Proyecto = d["p"]
    color, texto = semaforo(d)
    s = d["salud"]
    ci_txt = _render_ci(d.get("ci"))
    version_prod = s.get("version") or "—"
    sitio = (
        f'<a href="{e(p.sitio)}">'
        f'{e(urllib.parse.urlparse(p.sitio).netloc)}</a>'
        if p.sitio
        else "—"
    )
    roadmap = (
        f'<a href="https://github.com/{p.repo}/issues/{p.roadmap}">'
        f'Roadmap #{p.roadmap}</a>'
        if p.roadmap
        else ""
    )
    card = f"""
<article class="tarjeta {color}">
  <header>
    <span class="punto" aria-hidden="true"></span>
    <div><h2><a href="https://github.com/{e(p.repo)}">{e(p.nombre)}</a></h2><p class="desc">{e(p.descripcion)}</p></div>
  </header>
  <p class="estado">{e(texto)}</p>
  <dl>
    <div><dt>Sitio</dt><dd>{sitio}</dd></div>
    <div><dt>Producción</dt><dd>V {e(version_prod)}</dd></div>
    <div><dt>main</dt><dd>V {e(d["version_main"] or "—")} · <code>{e(d["sha_main"][:7])}</code></dd></div>
    <div><dt>CI de main</dt><dd>{ci_txt}</dd></div>
    <div><dt>PRs</dt><dd>{d["prs_abiertos"]} abiertos · {d["prs_semana"]} integrados en 7 días</dd></div>
  </dl>
  <details {"open" if d["incidentes"] else ""}><summary>Incidentes ({len(d["incidentes"])})</summary>{lista(d["incidentes"], "Sin incidentes abiertos.")}</details>
  <details><summary>Prioridad crítica ({len(d["criticos"])})</summary>{lista(d["criticos"], "Nada crítico pendiente.")}</details>
  <details><summary>Bloqueados ({len(d["bloqueados"])})</summary>{lista(d["bloqueados"], "Nada bloqueado.")}</details>
  <footer>{roadmap} · <a href="https://github.com/{e(p.repo)}/security">Seguridad</a> · <a href="https://github.com/{e(p.repo)}/pulls">PRs</a></footer>
</article>"""
    return color, card


def _render_decisions(datos: dict) -> tuple[list[tuple[Proyecto, dict]], str]:
    """Renderiza la cola explícita de decisiones del dueño."""
    decisiones = [
        (d["p"], item)
        for d in datos["proyectos"]
        for item in d["decisiones"]
    ]
    if not decisiones:
        return decisiones, (
            '<p class="vacio">No hay decisiones pendientes. '
            'Todo lo demás lo resuelven los agentes.</p>'
        )
    rendered = "<ul>" + "".join(
        f'<li><strong>{e(project.nombre)}</strong> · '
        f'<a href="{e(item["html_url"])}">'
        f'#{item["number"]} {e(item["title"])}</a></li>'
        for project, item in decisiones
    ) + "</ul>"
    return decisiones, rendered


def _headline(colors: list[str]) -> str:
    """Resume los colores sin afirmar verde cuando hay estados por revisar."""
    if colors and all(color == "verde" for color in colors):
        return "Todo en verde"
    red_count = sum(color == "rojo" for color in colors)
    if red_count:
        return f"{red_count} proyecto(s) caído(s)"
    return "Sin caídas · hay estados por revisar"


def render(datos: dict) -> str:
    """Genera el HTML estático escapando toda evidencia externa."""
    generado = datos["generado"]
    local = generado.astimezone(BOGOTA)
    decisiones, dec = _render_decisions(datos)
    cards = [_render_card(d) for d in datos["proyectos"]]
    colors = [color for color, _ in cards]
    tarjetas = [card for _, card in cards]
    titular = _headline(colors)

    return f"""<!doctype html>
<html lang="es-CO">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Cabina de la fábrica</title>
<style>
:root {{ --fondo:#f6f6f4; --tarjeta:#fff; --texto:#1b1b1f; --suave:#6b6b75; --borde:#e3e3e0;
  --verde:#1f9d55; --amarillo:#c98a00; --rojo:#d0342c; --gris:#9a9aa3; --enlace:#2f5bd3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fondo:#0f0f12; --tarjeta:#18181c; --texto:#ececf1;
  --suave:#9d9daa; --borde:#2a2a31; --enlace:#8fb0ff; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--fondo); color:var(--texto); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:24px 16px 48px; }}
a {{ color:var(--enlace); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
h1 {{ font-size:1.6rem; margin:0; }} .sub {{ color:var(--suave); margin:4px 0 24px; }}
.panel {{ background:var(--tarjeta); border:1px solid var(--borde); border-radius:14px; padding:16px 18px; margin-bottom:20px; }}
.panel h2 {{ font-size:1rem; margin:0 0 8px; }}
.grid {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
.tarjeta {{ background:var(--tarjeta); border:1px solid var(--borde); border-top:4px solid var(--c); border-radius:14px; padding:16px 18px; display:flex; flex-direction:column; gap:10px; }}
.verde {{ --c:var(--verde); }} .amarillo {{ --c:var(--amarillo); }} .rojo {{ --c:var(--rojo); }} .gris {{ --c:var(--gris); }}
.tarjeta header {{ display:flex; gap:10px; align-items:flex-start; }}
.punto {{ width:12px; height:12px; border-radius:50%; background:var(--c); margin-top:7px; flex:none; }}
.tarjeta h2 {{ font-size:1.15rem; margin:0; }} .desc {{ margin:0; color:var(--suave); font-size:.85rem; }}
.estado {{ margin:0; font-weight:600; color:var(--c); }}
dl {{ margin:0; display:grid; gap:4px; }} dl div {{ display:flex; justify-content:space-between; gap:12px; font-size:.9rem; }}
dt {{ color:var(--suave); }} dd {{ margin:0; text-align:right; }}
details {{ border-top:1px solid var(--borde); padding-top:8px; font-size:.9rem; }} summary {{ cursor:pointer; font-weight:600; }}
ul {{ margin:6px 0 0; padding-left:18px; }} li {{ margin:2px 0; }} .vacio, .mas {{ color:var(--suave); margin:6px 0 0; }}
footer {{ margin-top:auto; font-size:.85rem; color:var(--suave); }}
code {{ font-size:.85em; }}
</style>
</head>
<body>
<main>
  <h1>🏭 Cabina de la fábrica · {e(titular)}</h1>
  <p class="sub">Actualizado {e(local.strftime("%d/%m/%Y %H:%M"))} (hora Colombia) · <span id="hace"></span> · se regenera cada hora</p>
  <section class="panel"><h2>🧭 Te toca decidir ({len(decisiones)})</h2>{dec}</section>
  <section class="grid">{"".join(tarjetas)}</section>
  <p class="sub" style="margin-top:24px">Errores de producción: <a href="https://pl0n3r.sentry.io/issues/">Sentry</a> · Plan de agentes: <a href="https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md">PLAN-AGENTES.md</a></p>
</main>
<script>
(function () {{
  var t = {int(generado.timestamp() * 1000)}, m = Math.round((Date.now() - t) / 60000);
  document.getElementById("hace").textContent = m < 1 ? "hace un momento" : m < 60 ? "hace " + m + " min" : "hace " + Math.round(m / 60) + " h";
}})();
</script>
</body>
</html>
"""


SALIDA = os.path.join("site", "index.html")


def main() -> int:
    # Ruta de salida fija: el workflow publica exactamente site/ y no se aceptan rutas por CLI.
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    datos = recolectar(token)
    os.makedirs("site", exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(render(datos))
    print(f"Cabina generada: {SALIDA}")
    return 0


def inicializar_sentry(env: dict[str, str] | None = None) -> object | None:
    """Inicializa Sentry solo con configuración explícita y minimización de datos."""
    source = os.environ if env is None else env
    dsn = str(source.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return None

    release = str(source.get("SENTRY_RELEASE") or "").strip()
    environment = str(source.get("SENTRY_ENVIRONMENT") or "").strip()
    if not release or not environment:
        return None

    try:
        sdk = importlib.import_module("sentry_sdk")
        sdk.init(
            dsn=dsn,
            release=release,
            environment=environment,
            send_default_pii=False,
            include_local_variables=False,
            include_source_context=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            traces_sample_rate=0.0,
            profiles_sample_rate=0.0,
            enable_logs=False,
            default_integrations=False,
            auto_enabling_integrations=False,
        )
    except Exception:
        return None
    return sdk


def ejecutar_con_observabilidad() -> int:
    """Ejecuta la cabina y reporta errores sin sustituir la excepción original."""
    sdk = inicializar_sentry()
    try:
        return main()
    except Exception as exc:
        if sdk is not None:
            try:
                sdk.capture_exception(exc)
                sdk.flush(timeout=2.0)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    raise SystemExit(ejecutar_con_observabilidad())
