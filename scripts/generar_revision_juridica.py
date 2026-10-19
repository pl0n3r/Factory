#!/usr/bin/env python3
"""Exportación exacta de textos legales sin aprobarlos ni modificar sus fuentes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["docs/cumplimiento-datos-licencias.md","legal/reglas-datos.yml","legal/plantillas/aviso-privacidad.md.tpl","legal/plantillas/canal-derechos.md.tpl","legal/plantillas/politica-tratamiento.md.tpl","legal/plantillas/registro-tratamientos.md.tpl","legal/plantillas/retencion.md.tpl","legal/plantillas/terminos-condiciones.md.tpl"]
DESCRIPTIONS = ["Cumplimiento de privacidad y licencias","Reglas de detección de categorías de datos y señales de proveedores","Aviso, consentimiento y autorización","Canal de derechos, trámites y plazos","Política de tratamiento, finalidades y bases","Inventario de tratamientos reales","Retención y eliminación","Términos, responsabilidad y jurisdicción"]
TEMPLATE = "Última actualización automática: @@DATE@@ | SHA de origen: @@SHA@@\n\n# Carpeta para revisión jurídica — Factory\n\nEstado: documented_not_legally_approved. Esta documentación NO está aprobada jurídicamente.\n\nVersión del repositorio: @@VERSION@@. SHA del checkout origen: @@SHA@@. Fecha UTC: @@DATE@@.\n\nEntregue todos los archivos de esta carpeta al abogado, o el archivo paquete-completo.md como documento único. Las plantillas .tpl conservan variables sin rellenar y NO deben publicarse como documentos jurídicos definitivos.\n\n## Documentos y revisión requerida\n\n@@TABLE@@\n\n## Hechos del responsable por confirmar (nunca inventar)\n\n- [ ] Nombre o razón social del responsable.\n- [ ] Identificación o NIT aplicable.\n- [ ] Dirección física y jurisdicción efectiva.\n- [ ] Contacto/canal para ejercer derechos.\n- [ ] Tratamientos, finalidades y bases efectivas por producto.\n- [ ] Autorizaciones, excepciones y evidencia real.\n- [ ] Retenciones y mecanismos de eliminación.\n- [ ] Contratos de encargados/subprocesadores y transferencias.\n- [ ] Condiciones comerciales, licencias y responsabilidades.\n- [ ] Aprobación jurídica previa a cualquier live.\n\n## Servicios observados en la configuración técnica\n\n- GitHub / GitHub Actions: repositorios y automatizaciones.\n- SonarCloud: controles de calidad y seguridad de código.\n- CodeRabbit: análisis automatizado de pull requests.\n\nEstos servicios técnicos NO prueban transferencia de datos personales de clientes ni son un inventario validado de encargados. El abogado debe comprobar el uso real y las relaciones jurídicas. Las señales de Google Analytics, Sentry, Supabase, Dropbox y Google Drive en legal/reglas-datos.yml sirven para detección y NO significan que estos servicios estén activos.\n\n## Límites\n\nEste paquete conserva bytes de las fuentes; no crea hechos legales, consentimientos ni plazos. El SHA de origen identifica el checkout desde el que se exportó el paquete y puede diferir del SHA de main después de un squash merge sin que exista desfase de documentos.\n"
DIR = "revision-juridica"
INDEX = DIR + "/00-LEEME.md"
PACK = DIR + "/paquete-completo.md"
HEADER = re.compile(r"^Última actualización automática: (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \| SHA de origen: ([a-f0-9]{40})$")


class RevisionError(ValueError):
    pass


def read_source(root: Path, name: str) -> bytes:
    target = root / name
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 2_000_000:
        raise RevisionError("Fuente ausente o insegura: " + name)
    return target.read_bytes()


def expected(root: Path, fecha: str, sha: str) -> dict[str, bytes]:
    if not HEADER.fullmatch(f"Última actualización automática: {fecha} | SHA de origen: {sha}"):
        raise RevisionError("Fecha o SHA inválido")
    try:
        datetime.fromisoformat(fecha.replace("Z", "+00:00"))
        version = json.loads(read_source(root, "config/version.json"))["version"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RevisionError("Versión o fecha inválida") from exc
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RevisionError("Versión inválida")
    sources = {p: read_source(root, p) for p in SOURCES}
    table = "\n".join([
        "| Documento fuente copiado | Verificación del abogado |",
        "| --- | --- |",
        *["| " + p + " | " + DESCRIPTIONS[i] + " |" for i, p in enumerate(SOURCES)],
    ])
    readme = (TEMPLATE.replace("@@DATE@@", fecha).replace("@@SHA@@", sha)
              .replace("@@VERSION@@", version).replace("@@TABLE@@", table))
    package = ("# Paquete para revisión jurídica — Factory\n\n"
               "Estado: documented_not_legally_approved\n\n"
               f"Origen: {sha} · Fecha: {fecha}\n\n---\n\n").encode("utf-8")
    for p in SOURCES:
        package += ("## Fuente: " + p + "\n\n").encode("utf-8")
        package += sources[p] + b"\n\n---\n\n"
    result = {DIR + "/" + p: data for p, data in sources.items()}
    result[INDEX] = readme.encode("utf-8")
    result[PACK] = package
    return result


def metadata(root: Path) -> tuple[str, str]:
    first = read_source(root, INDEX).decode("utf-8").splitlines()[0]
    match = HEADER.fullmatch(first)
    if match is None:
        raise RevisionError("El índice no declara fecha y SHA válidos")
    return match.group(1), match.group(2)


def check(root: Path) -> list[str]:
    fecha, sha = metadata(root)
    files = expected(root, fecha, sha)
    directory = root / DIR
    if directory.is_symlink() or not directory.is_dir():
        raise RevisionError("Carpeta de salida ausente o insegura")
    found = set()
    for p in directory.rglob("*"):
        if p.is_symlink():
            raise RevisionError("Enlace simbólico prohibido")
        if p.is_file():
            found.add(p.relative_to(root).as_posix())
    return ([name for name, data in files.items()
             if name not in found or (root / name).read_bytes() != data]
            + sorted(found - set(files)))


def generate(root: Path, fecha: str, sha: str) -> None:
    files = expected(root, fecha, sha)
    folder = root / DIR
    if folder.is_symlink():
        raise RevisionError("Salida insegura")
    if folder.exists():
        for p in folder.rglob("*"):
            if p.is_symlink() or (p.is_file() and p.relative_to(root).as_posix() not in files):
                raise RevisionError("Archivo ajeno a la entrega: no borrar automáticamente")
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.is_symlink():
            raise RevisionError("Destino inseguro")
        if not p.exists() or p.read_bytes() != data:
            p.write_bytes(data)


def main(args=None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fecha")
    parser.add_argument("--sha")
    opts = parser.parse_args(args)
    try:
        if opts.check:
            if opts.fecha or opts.sha:
                raise RevisionError("--check es de solo lectura")
            pending = check(root)
            if pending:
                print("Desfase jurídico: " + ", ".join(pending), file=sys.stderr)
                return 1
            print("Paquete jurídico íntegro")
            return 0
        fecha = opts.fecha or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        sha = opts.sha or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        generate(root, fecha, sha)
        return 0
    except (RevisionError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
