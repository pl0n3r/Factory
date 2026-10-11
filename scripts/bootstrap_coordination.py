#!/usr/bin/env python3
"""Bootstrap gobernado del caller de coordinación en repositorios existentes."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, subprocess, sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API, OWNER = "https://api.github.com", "pl0n3r"
GOVERNANCE_REF = "pl0n3r/factory@v1"
CALLER_PATH = ".github/workflows/work-coordination.yml"
LEGACY_CALLER_PATH = ".github/workflows/coordinacion.yml"
SUPPORTED_CALLER_PATHS = {CALLER_PATH, LEGACY_CALLER_PATH}
TEST_PATH = "tests/test_factory_coordination_adoption.py"
ACCEPTANCE_PATH = ".github/workflows/aceptacion.yml"
CALLER_TEMPLATE = Path("governance/template/.github/workflows/coordinacion.yml")
ALLOWED_PATHS = {*SUPPORTED_CALLER_PATHS, TEST_PATH, ACCEPTANCE_PATH, "AGENTS.md"}
BOOTSTRAP_PR_LABELS = (
    "tipo: infraestructura",
    "prioridad: alta",
    "estado: en revisión",
    "rol: arquitectura",
    "rol: ingenieria-software",
    "rol: infraestructura",
    "rol: seguridad",
    "rol: qa",
)
GRINDFLOW_REPO = "pl0n3r/GrindFlow"
VERSION_PATH = "config/version.php"
PACKAGE_PATH = "package.json"
LOCK_PATH = "package-lock.json"
README_PATH = "README.md"
README_METADATA_PATH = "readme/project.json"
README_UPDATER_PATH = "scripts/readme-dashboard.py"
GRINDFLOW_DELIVERY_PATHS = {CALLER_PATH, TEST_PATH, VERSION_PATH, PACKAGE_PATH, LOCK_PATH, README_PATH}
STRICT_CONTRACT_MARKERS = {VERSION_PATH, PACKAGE_PATH, LOCK_PATH, README_UPDATER_PATH}
REPO_RE = re.compile(r"^pl0n3r/[A-Za-z0-9_.-]{1,100}$")
SHA_RE, KEY_RE = re.compile(r"^[0-9a-f]{40}$"), re.compile(r"^[0-9a-f]{64}$")
MAX_FILE, MAX_TOTAL = 120_000, 240_000
GRINDFLOW_MAX_FILE, GRINDFLOW_MAX_TOTAL = 400_000, 500_000
PREPARED_FILE = Path(".factory-bootstrap-delivery.json")
PREPARED_DIR_ENV = "FACTORY_PREPARED_DIR"

class BootstrapError(RuntimeError): pass

def prepared_file_for_mode(apply: bool) -> Path:
    if not apply:
        return PREPARED_FILE
    raw=os.getenv(PREPARED_DIR_ENV,"").strip()
    if not raw:
        raise BootstrapError("Directorio de entrega preparada no configurado.")
    root=Path(raw)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise BootstrapError("Directorio de entrega preparada inseguro.")
    target=root/PREPARED_FILE.name
    if target.parent!=root:
        raise BootstrapError("Path de entrega preparada inválido.")
    return target

def validate_request(raw: Any) -> dict[str, Any]:
    keys = {"target_repository", "target_issue", "expected_main_sha", "governance_ref", "idempotency_key"}
    if not isinstance(raw, dict) or set(raw) != keys or any(not isinstance(raw[k], str) or not raw[k].strip() for k in keys):
        raise BootstrapError("Solicitud de bootstrap inválida.")
    req: dict[str, Any] = {k: raw[k].strip() for k in keys}
    if REPO_RE.fullmatch(req["target_repository"]) is None or ".." in req["target_repository"]:
        raise BootstrapError("Repositorio objetivo fuera del owner permitido.")
    try: issue = int(req["target_issue"])
    except ValueError as exc: raise BootstrapError("Issue objetivo inválido.") from exc
    if issue < 1 or str(issue) != req["target_issue"]: raise BootstrapError("Issue objetivo inválido.")
    if SHA_RE.fullmatch(req["expected_main_sha"]) is None: raise BootstrapError("expected_main_sha inválido.")
    if req["governance_ref"] != GOVERNANCE_REF or KEY_RE.fullmatch(req["idempotency_key"]) is None:
        raise BootstrapError("Gobernanza o idempotency_key inválida.")
    req["target_issue"] = issue
    return req

def identity(req: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(req, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def branch_name(req: dict[str, Any]) -> str: return f"factory/bootstrap-coordination-{req['target_issue']}"

def marker(req: dict[str, Any]) -> str:
    value = {"version":1, "identity":identity(req), "target_issue":req["target_issue"], "expected_main_sha":req["expected_main_sha"], "governance_ref":req["governance_ref"]}
    return "<!-- factory-coordination-bootstrap " + json.dumps(value, sort_keys=True, separators=(",", ":")) + " -->"

def parse_marker(body: Any) -> dict[str, Any] | None:
    if not isinstance(body, str):
        return None
    matches = re.findall(r"<!-- factory-coordination-bootstrap (\{[^\n]*\}) -->", body)
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0])
    except json.JSONDecodeError:
        return None
    required = {"version", "identity", "target_issue", "expected_main_sha", "governance_ref"}
    if not isinstance(value, dict) or set(value) != required:
        return None
    if value.get("version") != 1 or value.get("governance_ref") != GOVERNANCE_REF:
        return None
    if not isinstance(value.get("target_issue"), int) or value["target_issue"] < 1:
        return None
    if not isinstance(value.get("identity"), str) or KEY_RE.fullmatch(value["identity"]) is None:
        return None
    if not isinstance(value.get("expected_main_sha"), str) or SHA_RE.fullmatch(value["expected_main_sha"]) is None:
        return None
    return value

def guard_bootstrap_validation(value: str) -> str:
    validation = "  validar-pr:\n    if: github.event_name == 'pull_request'\n"
    guarded = (
        "  validar-pr:\n"
        "    if: >-\n"
        "      github.event_name == 'pull_request' &&\n"
        "      !(\n"
        "        startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-') &&\n"
        "        github.event.pull_request.head.repo.full_name == github.repository &&\n"
        "        github.event.pull_request.author_association == 'OWNER'\n"
        "      )\n"
    )
    if value.count(validation) != 1:
        raise BootstrapError("Caller v1 no expone validar-pr con el contrato esperado.")
    return value.replace(validation, guarded, 1)

def guard_bootstrap_acceptance(value: str) -> str:
    marker = "  bootstrap-acceptance:\n"
    required = (
        "uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1",
        "issue_number: 0",
    )
    if marker in value:
        if all(token in value for token in required) and value.count("factory/bootstrap-coordination-") == 2:
            return value
        raise BootstrapError("Caller de aceptación bootstrap inválido.")
    canonical = (
        "jobs:\n"
        "  acceptance:\n"
        "    uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1\n"
        "    with:\n"
        "      issue_number: 0\n"
    )
    if value.count(canonical) != 1:
        raise BootstrapError("Caller de aceptación no expone el contrato esperado.")
    guarded = (
        "jobs:\n"
        "  bootstrap-acceptance:\n"
        "    if: >-\n"
        "      startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-') &&\n"
        "      github.event.pull_request.head.repo.full_name == github.repository &&\n"
        "      github.event.pull_request.author_association == 'OWNER'\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 1\n"
        "    steps:\n"
        "      - run: 'true'\n"
        "  acceptance:\n"
        "    if: >-\n"
        "      !(\n"
        "        startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-') &&\n"
        "        github.event.pull_request.head.repo.full_name == github.repository &&\n"
        "        github.event.pull_request.author_association == 'OWNER'\n"
        "      )\n"
        "    uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1\n"
        "    with:\n"
        "      issue_number: 0\n"
    )
    return value.replace(canonical, guarded, 1)

def caller_content(template: str) -> str:
    required = "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1"
    if not isinstance(template, str) or len(template.encode()) > MAX_FILE or required not in template or "@main" in template or "coordinar_trabajo.py" in template:
        raise BootstrapError("Caller canónico inválido.")
    out, in_with, profile = [], False, False
    for line in template.splitlines():
        stripped = line.strip()
        if stripped == "with:": in_with, profile = True, False
        elif in_with and stripped.startswith("profile:"): profile = True
        elif in_with and stripped and len(line) - len(line.lstrip()) <= 4:
            if not profile: out.append("      profile: es")
            in_with, profile = False, False
        out.append(line)
    if in_with and not profile: out.append("      profile: es")
    value = guard_bootstrap_validation("\n".join(out).rstrip() + "\n")
    if "profile: es" not in value: raise BootstrapError("No fue posible fijar profile es.")
    return value

def adoption_test(caller_path: str = CALLER_PATH, acceptance_path: str | None = None) -> str:
    if caller_path not in SUPPORTED_CALLER_PATHS:
        raise BootstrapError("Ruta de caller no soportada.")
    if acceptance_path not in (None, ACCEPTANCE_PATH):
        raise BootstrapError("Ruta de aceptación no soportada.")
    value = '''import json\nimport os\nimport subprocess\nimport sys\nimport tempfile\nimport textwrap\nimport unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass FactoryCoordinationAdoptionTests(unittest.TestCase):\n    def test_caller_uses_factory_v1_spanish_profile_only(self):\n        text = (ROOT / "__FACTORY_CALLER_PATH__").read_text(encoding="utf-8")\n        self.assertIn("pl0n3r/factory/.github/workflows/coordinacion.yml@v1", text)\n        self.assertIn("profile: es", text)\n        self.assertNotIn("@main", text)\n        self.assertNotIn("coordinar_trabajo.py", text)\n        self.assertIn("startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')", text)\n        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)\n        self.assertIn("github.event.pull_request.author_association == 'OWNER'", text)\n        self.assertIn("require_reservation: true", text)\n\n    def test_caller_keeps_hardened_consumer_coordination_contract(self):\n        text = (ROOT / "__FACTORY_CALLER_PATH__").read_text(encoding="utf-8")\n        self.assertIn("types: [opened, reopened, synchronize, edited, ready_for_review, converted_to_draft, closed]", text)\n        self.assertIn("group: coordinacion-${{ github.repository }}", text)\n        self.assertIn("cancel-in-progress: false", text)\n        self.assertIn("queue: max", text)\n        comment = text.split("  comentario:", 1)[1].split("  etiqueta:", 1)[0]\n        self.assertIn("github.event_name == 'issue_comment'", comment)\n        self.assertIn("github.event.issue.pull_request == null", comment)\n        self.assertIn("github.event.sender.login == github.event.comment.user.login", comment)\n        self.assertIn("uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1", comment)\n        for permission in ("contents: write", "issues: write", "pull-requests: write", "checks: write"):\n            self.assertIn(permission, comment)\n        if "  preflight_comentario:\\n" in text:\n            preflight = text.split("  preflight_comentario:\\n", 1)[1].split("  comentario:\\n", 1)[0]\n            self.assertIn("github.event_name == 'issue_comment'", preflight)\n            self.assertIn("github.event.issue.pull_request == null", preflight)\n            self.assertIn("github.event.sender.login == github.event.comment.user.login", preflight)\n            self.assertIn("runs-on: ubuntu-latest", preflight)\n            self.assertIn("    timeout-minutes: 2", preflight.splitlines())\n            self.assertIn("permissions:", preflight)\n            permission_lines = preflight.split("    permissions:", 1)[1].split("    outputs:", 1)[0].splitlines()\n            self.assertEqual(["      contents: read"], [line for line in permission_lines if line.strip()])\n            for command in ("/tomar", "/liberar-forzado", "/adoptar-contrato-huerfana",\n                            "/liberar", "/transferir", "/migrar-contrato",\n                            "/renovar-contrato"):\n                self.assertIn('"' + command + '"', preflight)\n            self.assertIn("needs: preflight_comentario", comment)\n            self.assertIn("needs.preflight_comentario.outputs.route == 'true'", comment)\n            self.assertIn("outputs:", preflight)\n            self.assertIn("route: ${{ steps.route.outputs.route }}", preflight)\n            self.assertIn("- id: route", preflight)\n            self.assertIn('os.environ["GITHUB_EVENT_PATH"]', preflight)\n            self.assertNotIn("COMMENT_BODY", preflight)\n            self.assertNotIn("github.event.comment.body", preflight)\n            self.assertNotIn("contains(github.event.comment.body", comment)\n        else:\n            self.assertIn("github.event.comment.body == '/tomar'", comment)\n            self.assertIn("startsWith(github.event.comment.body, '/renovar-contrato ')", comment)\n        routes = {\n            "comentario": "operation: comment",\n            "etiqueta": "operation: label",\n            "pr": "operation: pr",\n            "validar-pr": "operation: validate",\n            "issue": "operation: issue",\n            "sweep": "operation: sweep",\n        }\n        names = list(routes)\n        for index, name in enumerate(names):\n            tail = text.split(f"  {name}:", 1)[1]\n            block = tail.split(f"  {names[index + 1]}:", 1)[0] if index + 1 < len(names) else tail\n            self.assertIn(routes[name], block)\n\n    def test_preflight_only_routes_actual_first_token(self):\n        text = (ROOT / "__FACTORY_CALLER_PATH__").read_text(encoding="utf-8")\n        if "  preflight_comentario:\\n" not in text:\n            return  # El caller legacy queda cubierto por el test anterior.\n        preflight = text.split("  preflight_comentario:\\n", 1)[1].split("  comentario:\\n", 1)[0]\n        embedded = preflight.split("python3 - <<'PY'\\n", 1)[1].split("\\n          PY", 1)[0]\n        script = textwrap.dedent(embedded)\n        with tempfile.TemporaryDirectory() as tmp:\n            event_path = Path(tmp) / "event.json"\n            output_path = Path(tmp) / "route"\n            for body, expected in (\n                ("Nota: no ejecuté /tomar ni /renovar-contrato", "route=false\\n"),\n                ("Información sobre /liberar-forzado", "route=false\\n"),\n                ("No solicité /adoptar-contrato-huerfana", "route=false\\n"),\n                ("Este texto menciona /liberar sin ejecutarlo", "route=false\\n"),\n                ("Información: /transferir todavía no solicitado", "route=false\\n"),\n                ("No ejecutar /migrar-contrato a partir de esta nota", "route=false\\n"),\n                ("/decidir A", "route=false\\n"),\n                ("/tomarlo", "route=false\\n"),\n                ("/reiniciar", "route=false\\n"),\n                ("/renovar-contrato-ejemplo", "route=false\\n"),\n                ("/TOMAR", "route=false\\n"),\n                ("/Liberar item", "route=false\\n"),\n                ("/RENOVAR-CONTRATO 123", "route=false\\n"),\n                (" /tomar\\t", "route=true\\n"),\n                (" /liberar-forzado ", "route=true\\n"),\n                (" /adoptar-contrato-huerfana ", "route=true\\n"),\n                (" /liberar x ", "route=true\\n"),\n                (" /transferir invalid-args ", "route=true\\n"),\n                (" /migrar-contrato invalid-args ", "route=true\\n"),\n                (" /renovar-contrato 12345678-abcd-1234-abcd-123456789abc ", "route=true\\n"),\n            ):\n                with self.subTest(body=body):\n                    event_path.write_text(json.dumps({"comment": {"body": body}}), encoding="utf-8")\n                    env = {**os.environ, "GITHUB_EVENT_PATH": str(event_path),\n                           "GITHUB_OUTPUT": str(output_path)}\n                    env.pop("COMMENT_BODY", None)\n                    result = subprocess.run(\n                        [sys.executable, "-c", script], env=env, capture_output=True,\n                        text=True, timeout=5, check=False,\n                    )\n                    self.assertEqual(result.returncode, 0, result.stderr)\n                    self.assertEqual(result.stdout, "")\n                    self.assertEqual(result.stderr, "")\n                    self.assertEqual(output_path.read_text(encoding="utf-8"), expected)\n                    output_path.unlink()\n'''
    value = value.replace("__FACTORY_CALLER_PATH__", caller_path)
    if acceptance_path is not None:
        value += '''\n    def test_bootstrap_acceptance_is_owner_same_repo_only(self):\n        text = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")\n        self.assertIn("bootstrap-acceptance:", text)\n        self.assertEqual(text.count("factory/bootstrap-coordination-"), 2)\n        self.assertEqual(text.count("github.event.pull_request.head.repo.full_name == github.repository"), 2)\n        self.assertEqual(text.count("github.event.pull_request.author_association == 'OWNER'"), 2)\n        self.assertIn("uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1", text)\n        self.assertIn("issue_number: 0", text)\n        self.assertIn("- run: 'true'", text)\n'''
    return value

def allowed_paths(scope: str | set[str] | None = None) -> set[str]:
    if isinstance(scope, set):
        return scope
    return GRINDFLOW_DELIVERY_PATHS if scope == GRINDFLOW_REPO else ALLOWED_PATHS

def validate_patch(patch: Any, scope: str | set[str] | None = None) -> None:
    allowed = allowed_paths(scope)
    if not isinstance(patch, dict) or not patch or not set(patch).issubset(allowed):
        raise BootstrapError("Patch fuera de la allowlist.")
    file_limit, total_limit = (
        (GRINDFLOW_MAX_FILE, GRINDFLOW_MAX_TOTAL)
        if allowed == GRINDFLOW_DELIVERY_PATHS
        else (MAX_FILE, MAX_TOTAL)
    )
    total = 0
    for path, content in patch.items():
        rel = Path(path)
        if rel.is_absolute() or ".." in rel.parts or ".git" in rel.parts or not isinstance(content, str):
            raise BootstrapError("Patch inválido.")
        size = len(content.encode())
        total += size
        if size > file_limit or total > total_limit:
            raise BootstrapError("Patch excede límites.")
    callers = set(patch) & SUPPORTED_CALLER_PATHS
    if len(callers) != 1 or TEST_PATH not in patch:
        raise BootstrapError("Patch incompleto o caller ambiguo.")

def build_patch(template: str, caller_path: str = CALLER_PATH, acceptance: str | None = None) -> dict[str, str]:
    if caller_path not in SUPPORTED_CALLER_PATHS:
        raise BootstrapError("Ruta de caller no soportada.")
    acceptance_path = ACCEPTANCE_PATH if acceptance is not None else None
    patch = {caller_path: caller_content(template), TEST_PATH: adoption_test(caller_path, acceptance_path)}
    if acceptance is not None:
        patch[ACCEPTANCE_PATH] = guard_bootstrap_acceptance(acceptance)
    validate_patch(patch)
    return patch

def legacy_patch(template: str) -> dict[str, str]:
    current = caller_content(template)
    trusted = (
        "  validar-pr:\n"
        "    if: >-\n"
        "      github.event_name == 'pull_request' &&\n"
        "      !(\n"
        "        startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-') &&\n"
        "        github.event.pull_request.head.repo.full_name == github.repository &&\n"
        "        github.event.pull_request.author_association == 'OWNER'\n"
        "      )\n"
    )
    legacy = (
        "  validar-pr:\n"
        "    if: >-\n"
        "      github.event_name == 'pull_request' &&\n"
        "      !startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')\n"
    )
    if current.count(trusted) != 1:
        raise BootstrapError("Caller actual no expone el guard bootstrap esperado.")
    caller = current.replace(trusted, legacy, 1)
    test = '''import unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass FactoryCoordinationAdoptionTests(unittest.TestCase):\n    def test_caller_uses_factory_v1_spanish_profile_only(self):\n        text = (ROOT / ".github/workflows/work-coordination.yml").read_text(encoding="utf-8")\n        self.assertIn("pl0n3r/factory/.github/workflows/coordinacion.yml@v1", text)\n        self.assertIn("profile: es", text)\n        self.assertNotIn("@main", text)\n        self.assertNotIn("coordinar_trabajo.py", text)\n        self.assertIn("!startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')", text)\n        self.assertIn("require_reservation: true", text)\n        self.assertIn("operation: pr", text)\n        for event in ("issue_comment:", "issues:", "pull_request:", "workflow_dispatch:", "schedule:"):\n            self.assertIn(event, text)\n'''
    patch = {CALLER_PATH: caller, TEST_PATH: test}; validate_patch(patch); return patch

def patch_sha(patch: dict[str,str]) -> str:
    allowed = GRINDFLOW_DELIVERY_PATHS if set(patch).issubset(GRINDFLOW_DELIVERY_PATHS) else ALLOWED_PATHS
    validate_patch(patch, allowed)
    return hashlib.sha256(json.dumps(patch,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def replacement_branch_name(req: dict[str,Any], patch: dict[str,str]) -> str:
    return f"{branch_name(req)}-{patch_sha(patch)[:12]}"


def _regular_text(root: Path, path: str, max_bytes: int = MAX_FILE) -> str:
    target=(root/path)
    if target.is_symlink() or not target.is_file():
        raise BootstrapError(f"Contrato consumidor inválido: {path}.")
    data=target.read_bytes()
    if len(data)>max_bytes:
        raise BootstrapError(f"Contrato consumidor excede límite: {path}.")
    try: return data.decode()
    except UnicodeDecodeError as exc: raise BootstrapError(f"Contrato consumidor no es UTF-8: {path}.") from exc

def _write_regular(root: Path, path: str, content: str) -> None:
    target=(root/path)
    if target.exists() and target.is_symlink():
        raise BootstrapError(f"Patch no admite symlinks: {path}.")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(content,encoding="utf-8")

def _grindflow_version(content: str) -> tuple[int,int,int]:
    matches=re.findall(r"'number'\s*=>\s*'(\d+)\.(\d+)\.(\d+)'",content)
    if len(matches)!=1: raise BootstrapError("GrindFlow exige una única versión.")
    value=tuple(int(part) for part in matches[0])
    if value[0]>=1: raise BootstrapError("GrindFlow bootstrap solo admite versión pre-1.0.")
    return value

def _json_object(content: str,label: str) -> dict[str,Any]:
    try: value=json.loads(content)
    except json.JSONDecodeError as exc: raise BootstrapError(f"{label} inválido.") from exc
    if not isinstance(value,dict): raise BootstrapError(f"{label} inválido.")
    return value

def _grindflow_readme_contract(root: Path, readme_text: str, current_str: str, next_str: str) -> tuple[str,bool]:
    metadata_path=root/README_METADATA_PATH
    if metadata_path.exists() or metadata_path.is_symlink():
        _json_object(_regular_text(root,README_METADATA_PATH),README_METADATA_PATH)
        if readme_text.count("<!-- factory:status:start -->")!=1 or readme_text.count("<!-- factory:status:end -->")!=1:
            raise BootstrapError("README Contract v1 de GrindFlow inválido.")
        return readme_text,True

    visible_current=f"v{current_str}"
    if visible_current not in readme_text:
        raise BootstrapError("README GrindFlow no coincide con Contract v1 ni legacy.")

    updater=_regular_text(root,README_UPDATER_PATH)
    if "README dashboard" not in updater or "--update" not in updater:
        raise BootstrapError("Updater README canónico de GrindFlow no reconocido.")
    return readme_text.replace(visible_current,f"v{next_str}"),False

def grindflow_delivery_patch(template: str, consumer_root: Path, expected_main_sha: str) -> dict[str,str]:
    root=consumer_root.resolve()
    try:
        head=subprocess.run(["git","rev-parse","HEAD"],cwd=root,check=True,text=True,capture_output=True).stdout.strip()
    except (OSError,subprocess.CalledProcessError) as exc:
        raise BootstrapError("Checkout GrindFlow inválido.") from exc
    if head!=expected_main_sha: raise BootstrapError("Checkout GrindFlow no coincide con expected_main_sha.")

    version_text=_regular_text(root,VERSION_PATH)
    package_text=_regular_text(root,PACKAGE_PATH)
    lock_text=_regular_text(root,LOCK_PATH,GRINDFLOW_MAX_FILE)
    _regular_text(root,README_PATH)
    current=_grindflow_version(version_text)
    package=_json_object(package_text,"package.json")
    lock=_json_object(lock_text,"package-lock.json")
    current_str=".".join(map(str,current))
    root_pkg=(lock.get("packages") or {}).get("") if isinstance(lock.get("packages"),dict) else None
    if package.get("version")!=current_str or lock.get("version")!=current_str or not isinstance(root_pkg,dict) or root_pkg.get("version")!=current_str:
        raise BootstrapError("Versiones GrindFlow fuera de paridad.")
    next_version=(current[0],current[1],current[2]+1)
    next_str=".".join(map(str,next_version))

    updated_version,count=re.subn(
        r"('number'\s*=>\s*')\d+\.\d+\.\d+(')",
        lambda m:m.group(1)+next_str+m.group(2),
        version_text,count=1,
    )
    if count!=1: raise BootstrapError("No fue posible preparar config/version.php.")
    package["version"]=next_str
    lock["version"]=next_str
    root_pkg["version"]=next_str

    base=build_patch(template)
    readme_text,contract_v1=_grindflow_readme_contract(
        root,_regular_text(root,README_PATH),current_str,next_str
    )

    prepared={
        **base,
        VERSION_PATH:updated_version,
        PACKAGE_PATH:json.dumps(package,ensure_ascii=False,indent=2)+"\n",
        LOCK_PATH:json.dumps(lock,ensure_ascii=False,indent=2)+"\n",
        "README.md":readme_text,
    }
    for path,content in prepared.items(): _write_regular(root,path,content)
    if not contract_v1:
        try:
            subprocess.run(
                [sys.executable,"scripts/readme-dashboard.py","--update","--base",expected_main_sha,"--head",expected_main_sha],
                cwd=root,check=True,text=True,capture_output=True,
                env={k:v for k,v in os.environ.items() if k!="FACTORY_PROVISION_TOKEN"},
            )
        except (OSError,subprocess.CalledProcessError) as exc:
            raise BootstrapError("Updater README canónico de GrindFlow falló.") from exc
        prepared[README_PATH]=_regular_text(root,README_PATH)
    validate_patch(prepared,GRINDFLOW_DELIVERY_PATHS)
    if set(prepared)!=GRINDFLOW_DELIVERY_PATHS:
        raise BootstrapError("Patch GrindFlow incompleto.")
    return prepared

def consumer_caller_path(root: Path) -> str:
    present = [
        path for path in sorted(SUPPORTED_CALLER_PATHS)
        if (root / path).exists() or (root / path).is_symlink()
    ]
    if len(present) > 1:
        raise BootstrapError("Consumidor con múltiples callers de coordinación soportados.")
    if not present:
        return CALLER_PATH
    path = present[0]
    _regular_text(root, path)
    return path

def prepare_delivery_patch(raw: dict[str,str], template: str, consumer_root: Path) -> dict[str,Any]:
    req=validate_request(raw)
    root=consumer_root.resolve()
    if req["target_repository"]==GRINDFLOW_REPO:
        patch=grindflow_delivery_patch(template,root,req["expected_main_sha"])
    else:
        present={path for path in STRICT_CONTRACT_MARKERS if (root/path).exists()}
        if present==STRICT_CONTRACT_MARKERS:
            raise BootstrapError("Consumidor estricto sin adapter soportado.")
        acceptance_file=root/ACCEPTANCE_PATH
        acceptance=None
        if acceptance_file.exists() or acceptance_file.is_symlink():
            acceptance=_regular_text(root,ACCEPTANCE_PATH)
        patch=build_patch(template, consumer_caller_path(root), acceptance)
    allowed=GRINDFLOW_DELIVERY_PATHS if req["target_repository"]==GRINDFLOW_REPO else ALLOWED_PATHS
    validate_patch(patch,allowed)
    return {
        "version":1,
        "identity":identity(req),
        "target_repository":req["target_repository"],
        "expected_main_sha":req["expected_main_sha"],
        "patch_sha256":patch_sha(patch),
        "patch":patch,
    }

def load_prepared_delivery(raw: dict[str,str], prepared: Any) -> dict[str,str]:
    req=validate_request(raw)
    if not isinstance(prepared,dict) or set(prepared)!={"version","identity","target_repository","expected_main_sha","patch_sha256","patch"}:
        raise BootstrapError("Entrega preparada inválida.")
    if prepared["version"]!=1 or prepared["identity"]!=identity(req) or prepared["target_repository"]!=req["target_repository"] or prepared["expected_main_sha"]!=req["expected_main_sha"]:
        raise BootstrapError("Entrega preparada no corresponde a la intención.")
    patch=prepared["patch"]
    allowed=GRINDFLOW_DELIVERY_PATHS if req["target_repository"]==GRINDFLOW_REPO else ALLOWED_PATHS
    validate_patch(patch,allowed)
    if patch_sha(patch)!=prepared["patch_sha256"]:
        raise BootstrapError("Entrega preparada cambió después de preparación.")
    return patch

class GitHubGateway:
    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip(): raise BootstrapError("FACTORY_PROVISION_TOKEN no configurado.")
        self.token = token.strip()
    def _request(self, method: str, path: str, payload: Any=None, allow: tuple[int,...]=()) -> Any:
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(API + path, data=data, method=method, headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {self.token}","X-GitHub-Api-Version":"2022-11-28","User-Agent":"factory-coordination-bootstrap"})
        try:
            with urlopen(req, timeout=30) as response:
                raw=response.read(); return None if not raw else json.loads(raw.decode())
        except HTTPError as exc:
            if exc.code in allow: return None
            raise BootstrapError(f"GitHub rechazó la operación ({exc.code}).") from exc
    def authorize(self) -> None:
        if (self._request("GET","/user") or {}).get("login") != OWNER: raise BootstrapError("Autoridad GitHub inválida.")
    def repository(self, name: str) -> None:
        repo=self._request("GET",f"/repos/{name}")
        if not isinstance(repo,dict) or repo.get("full_name")!=name or (repo.get("owner") or {}).get("login")!=OWNER or repo.get("default_branch")!="main": raise BootstrapError("Repositorio objetivo incompatible.")
    def issue_open(self,name: str,number: int)->bool:
        issue=self._request("GET",f"/repos/{name}/issues/{number}",allow=(404,)); return bool(isinstance(issue,dict) and issue.get("state")=="open" and "pull_request" not in issue)
    def main_sha(self,name: str)->str:
        ref=self._request("GET",f"/repos/{name}/git/ref/heads/main"); sha=(ref or {}).get("object",{}).get("sha") if isinstance(ref,dict) else None
        if not isinstance(sha,str) or SHA_RE.fullmatch(sha) is None: raise BootstrapError("main inválido.")
        return sha
    def branch_sha(self,name: str,branch: str)->str|None:
        ref=self._request("GET",f"/repos/{name}/git/ref/heads/{quote(branch,safe='')}",allow=(404,));
        if ref is None: return None
        sha=(ref or {}).get("object",{}).get("sha") if isinstance(ref,dict) else None
        if not isinstance(sha,str) or SHA_RE.fullmatch(sha) is None: raise BootstrapError("Branch bootstrap inválida.")
        return sha
    def open_pr(self,name: str,branch: str)->dict[str,Any]|None:
        value=self._request("GET",f"/repos/{name}/pulls?state=open&head={OWNER}:{quote(branch,safe='')}&base=main&per_page=10")
        if not isinstance(value,list) or len(value)>1: raise BootstrapError("Estado de PR ambiguo.")
        return value[0] if value else None
    def closed_pr(self,name: str,branch: str)->dict[str,Any]|None:
        value=self._request("GET",f"/repos/{name}/pulls?state=closed&head={OWNER}:{quote(branch,safe='')}&base=main&per_page=10")
        if not isinstance(value,list): raise BootstrapError("Estado histórico de PR ambiguo.")
        candidates=[]
        for item in value:
            number=item.get("number") if isinstance(item,dict) else None
            if not isinstance(number,int):
                raise BootstrapError("PR histórico inválido.")
            detail=self._request("GET",f"/repos/{name}/pulls/{number}")
            if not isinstance(detail,dict):
                raise BootstrapError("PR histórico inválido.")
            if detail.get("merged_at") is None:
                candidates.append(detail)
        if len(candidates)>1: raise BootstrapError("Estado histórico de PR ambiguo.")
        return candidates[0] if candidates else None
    def pr_matches(self,name: str,branch: str,pr: Any,req: dict[str,Any])->bool:
        return bool(
            isinstance(pr,dict)
            and isinstance(pr.get("number"),int)
            and pr.get("state","open")=="open"
            and isinstance(pr.get("base"),dict)
            and pr["base"].get("ref")=="main"
            and isinstance(pr.get("head"),dict)
            and pr["head"].get("ref")==branch
            and isinstance(pr["head"].get("repo"),dict)
            and pr["head"]["repo"].get("full_name")==name
            and marker(req) in str(pr.get("body") or "")
        )
    def main_descends_from(self,name: str,ancestor: str,current: str)->bool:
        if ancestor == current:
            return True
        value=self._request("GET",f"/repos/{name}/compare/{ancestor}...{current}") or {}
        merge_base=value.get("merge_base_commit",{}) if isinstance(value,dict) else {}
        return bool(
            isinstance(value,dict)
            and value.get("status")=="ahead"
            and value.get("behind_by")==0
            and isinstance(merge_base,dict)
            and merge_base.get("sha")==ancestor
        )
    def legacy_marker(self,name: str,branch: str,pr: Any,req: dict[str,Any])->dict[str,Any]|None:
        if not (
            isinstance(pr,dict)
            and isinstance(pr.get("number"),int)
            and pr.get("state","open") in ("open","closed")
            and not (pr.get("state")=="closed" and pr.get("merged_at") is not None)
            and isinstance(pr.get("base"),dict)
            and pr["base"].get("ref")=="main"
            and isinstance(pr.get("head"),dict)
            and pr["head"].get("ref")==branch
            and branch==branch_name(req)
            and isinstance(pr["head"].get("repo"),dict)
            and pr["head"]["repo"].get("full_name")==name
            and isinstance(pr.get("user"),dict)
            and pr["user"].get("login")==OWNER
        ):
            return None
        historical=parse_marker(pr.get("body"))
        if historical is None:
            return None
        if historical["target_issue"]!=req["target_issue"] or historical["governance_ref"]!=req["governance_ref"]:
            return None
        if pr["base"].get("sha")!=historical["expected_main_sha"]:
            return None
        if isinstance(pr["base"].get("repo"),dict) and pr["base"]["repo"].get("full_name")!=name:
            return None
        if not self.main_descends_from(name,historical["expected_main_sha"],req["expected_main_sha"]):
            return None
        return historical
    def commit_matches_marker(self,name: str,sha: str,historical: dict[str,Any],paths_expected: set[str])->bool:
        expected=historical["expected_main_sha"]
        compare=self._request("GET",f"/repos/{name}/compare/{expected}...{sha}") or {}
        commits=compare.get("commits",[]) if isinstance(compare,dict) else []
        merge_base=compare.get("merge_base_commit",{}) if isinstance(compare,dict) else {}
        paths={row.get("filename") for row in compare.get("files",[])} if isinstance(compare,dict) else set()
        ahead=compare.get("ahead_by") if isinstance(compare,dict) else None
        if not (
            isinstance(commits,list)
            and isinstance(ahead,int)
            and 1<=ahead<=10
            and len(commits)==ahead
            and compare.get("status")=="ahead"
            and compare.get("behind_by")==0
            and isinstance(merge_base,dict)
            and merge_base.get("sha")==expected
            and paths==set(paths_expected)
            and isinstance(commits[0],dict)
            and isinstance(commits[-1],dict)
            and commits[-1].get("sha")==sha
        ):
            return False
        previous=expected
        for item in commits:
            if not isinstance(item,dict):
                return False
            commit_sha=item.get("sha")
            parents=item.get("parents")
            if (
                not isinstance(commit_sha,str)
                or SHA_RE.fullmatch(commit_sha) is None
                or not isinstance(parents,list)
                or len(parents)!=1
                or not isinstance(parents[0],dict)
                or parents[0].get("sha")!=previous
            ):
                return False
            previous=commit_sha
        first_sha=commits[0].get("sha")
        first=self._request("GET",f"/repos/{name}/git/commits/{first_sha}")
        parents=first.get("parents",[]) if isinstance(first,dict) else []
        return bool(
            isinstance(first,dict)
            and f"Factory-Bootstrap-Identity: {historical['identity']}" in first.get("message","")
            and len(parents)==1
            and parents[0].get("sha")==expected
        )
    def legacy_pr_matches_exact(
        self,name: str,branch: str,number: int,req: dict[str,Any],legacy_sha: str|None=None,
        legacy_body: str|None=None,legacy_patch: dict[str,str]|None=None
    )->bool:
        pr=self.open_pr(name,branch) or self.closed_pr(name,branch)
        historical=self.legacy_marker(name,branch,pr,req)
        if historical is None or pr.get("number")!=number:
            return False
        if legacy_body is not None and str(pr.get("body") or "")!=legacy_body:
            return False
        if legacy_sha is not None:
            paths=set(legacy_patch) if legacy_patch is not None else set()
            if (
                self.branch_sha(name,branch)!=legacy_sha
                or pr["head"].get("sha")!=legacy_sha
                or not paths
                or not self.commit_matches_marker(name,legacy_sha,historical,paths)
            ):
                return False
        if legacy_patch is not None and not self.branch_matches(name,branch,legacy_patch):
            return False
        return True
    def delete_branch(self,name: str,branch: str)->None:
        self._request("DELETE",f"/repos/{name}/git/refs/heads/{quote(branch,safe='')}")
    def bootstrap_pr_labels(self,name: str)->list[str]:
        catalog=self._request("GET",f"/repos/{name}/labels?per_page=100")
        if not isinstance(catalog,list) or len(catalog)>=100:
            raise BootstrapError("Catálogo de labels bootstrap ambiguo.")
        names={row.get("name") for row in catalog if isinstance(row,dict) and isinstance(row.get("name"),str)}
        if not set(BOOTSTRAP_PR_LABELS).issubset(names):
            raise BootstrapError("Catálogo de labels bootstrap incompatible.")
        return list(BOOTSTRAP_PR_LABELS)
    def classify_bootstrap_pr(self,name: str,number: int)->None:
        labels=self.bootstrap_pr_labels(name)
        value=self._request("POST",f"/repos/{name}/issues/{number}/labels",{"labels":labels})
        applied={row.get("name") for row in value if isinstance(row,dict)} if isinstance(value,list) else set()
        if not set(labels).issubset(applied):
            raise BootstrapError("Clasificación de PR bootstrap incompleta.")
    def create_pr(self,name: str,branch: str,title: str,body: str)->int:
        number=None
        try:
            pr=self._request("POST",f"/repos/{name}/pulls",{"title":title,"head":branch,"base":"main","body":body})
            if not isinstance(pr,dict) or not isinstance(pr.get("base"),dict) or pr["base"].get("ref")!="main" or not isinstance(pr.get("head"),dict) or pr["head"].get("ref")!=branch or not isinstance(pr.get("number"),int):
                raise BootstrapError("PR bootstrap inválido.")
            number=pr["number"]
            self.classify_bootstrap_pr(name,number)
            return number
        except (BootstrapError,OSError):
            if number is not None:
                try:
                    self._request("PATCH",f"/repos/{name}/pulls/{number}",{"state":"closed"})
                except (BootstrapError,OSError):
                    pass
            try:
                self.delete_branch(name,branch)
            except (BootstrapError,OSError):
                pass
            raise
    def file_text(self,name: str, path: str, ref: str)->str|None:
        value=self._request("GET",f"/repos/{name}/contents/{path}?ref={quote(ref,safe='')}",allow=(404,))
        if value is None: return None
        if not isinstance(value,dict) or value.get("type") not in (None,"file") or value.get("encoding")!="base64": raise BootstrapError("Path remoto no es archivo regular.")
        try: return base64.b64decode(value["content"]).decode()
        except (KeyError,TypeError,ValueError) as exc: raise BootstrapError("Contenido remoto ilegible.") from exc
    def branch_matches(self,name: str,branch: str, patch: dict[str,str])->bool: return all(self.file_text(name,p,branch)==v for p,v in patch.items())
    def commit_matches(self,name: str,sha: str,req: dict[str,Any],paths_expected: set[str])->bool:
        value=self._request("GET",f"/repos/{name}/git/commits/{sha}")
        parents=value.get("parents",[]) if isinstance(value,dict) else []
        compare=self._request("GET",f"/repos/{name}/compare/{req['expected_main_sha']}...{sha}") or {}
        paths={row.get("filename") for row in compare.get("files",[])} if isinstance(compare,dict) else set()
        return bool(
            isinstance(value,dict)
            and f"Factory-Bootstrap-Identity: {identity(req)}" in value.get("message","")
            and len(parents)==1
            and parents[0].get("sha")==req["expected_main_sha"]
            and paths==set(paths_expected)
        )
    def tree_info(self,name: str,sha: str,paths: set[str])->str:
        commit=self._request("GET",f"/repos/{name}/git/commits/{sha}"); tree=(commit or {}).get("tree",{}).get("sha") if isinstance(commit,dict) else None
        if not isinstance(tree,str): raise BootstrapError("Árbol base inválido.")
        recursive=self._request("GET",f"/repos/{name}/git/trees/{tree}?recursive=1")
        for item in (recursive or {}).get("tree",[]) if isinstance(recursive,dict) else []:
            path=item.get("path","")
            if item.get("mode")=="120000" and any(p==path or p.startswith(path+"/") for p in paths): raise BootstrapError("Patch no admite symlinks.")
        return tree
    def materialize(self,req: dict[str,Any],patch: dict[str,str])->tuple[str,int]:
        name,branch,expected=req["target_repository"],branch_name(req),req["expected_main_sha"]
        base_tree=self.tree_info(name,expected,set(patch)); entries=[]
        if self.main_sha(name)!=expected: raise BootstrapError("main cambió antes del primer write.")
        for path,content in patch.items():
            blob=self._request("POST",f"/repos/{name}/git/blobs",{"content":content,"encoding":"utf-8"}); entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]})
        tree=self._request("POST",f"/repos/{name}/git/trees",{"base_tree":base_tree,"tree":entries})
        message=f"chore(factory): bootstrap coordinación #{req['target_issue']}\n\nFactory-Bootstrap-Identity: {identity(req)}"
        commit=self._request("POST",f"/repos/{name}/git/commits",{"message":message,"tree":tree["sha"],"parents":[expected]})
        if self.main_sha(name)!=expected: raise BootstrapError("main cambió antes de escribir.")
        self._request("POST",f"/repos/{name}/git/refs",{"ref":f"refs/heads/{branch}","sha":commit["sha"]})
        if self.main_sha(name)!=expected:
            self.delete_branch(name,branch)
            raise BootstrapError("main cambió antes de crear PR; rama bootstrap revertida.")
        pr=self.create_pr(name,branch,f"chore(factory): restaurar coordinación (#{req['target_issue']})",f"Bootstrap gobernado de coordinación para #{req['target_issue']}.\n\nBase exacta: `{expected}`\n\n{marker(req)}")
        return commit["sha"], pr
    def materialize_replacement(
        self,req: dict[str,Any],patch: dict[str,str],branch: str,legacy_branch: str,legacy_sha: str,
        legacy_pr: int,legacy_body: str,legacy_patch: dict[str,str]
    )->tuple[str,int]:
        name,expected=req["target_repository"],req["expected_main_sha"]
        base_tree=self.tree_info(name,expected,set(patch)); entries=[]
        if self.main_sha(name)!=expected or self.branch_sha(name,legacy_branch)!=legacy_sha or not self.legacy_pr_matches_exact(
            name,legacy_branch,legacy_pr,req,legacy_sha,legacy_body,legacy_patch
        ):
            raise BootstrapError("El bootstrap legacy cambió antes del primer write.")
        for path,content in patch.items():
            blob=self._request("POST",f"/repos/{name}/git/blobs",{"content":content,"encoding":"utf-8"}); entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]})
        tree=self._request("POST",f"/repos/{name}/git/trees",{"base_tree":base_tree,"tree":entries})
        message=f"chore(factory): reemplazo bootstrap coordinación #{req['target_issue']}\n\nFactory-Bootstrap-Identity: {identity(req)}"
        commit=self._request("POST",f"/repos/{name}/git/commits",{"message":message,"tree":tree["sha"],"parents":[expected]})
        if self.main_sha(name)!=expected or self.branch_sha(name,legacy_branch)!=legacy_sha or not self.legacy_pr_matches_exact(
            name,legacy_branch,legacy_pr,req,legacy_sha,legacy_body,legacy_patch
        ):
            raise BootstrapError("El bootstrap legacy cambió antes de crear replacement.")
        self._request("POST",f"/repos/{name}/git/refs",{"ref":f"refs/heads/{branch}","sha":commit["sha"]})
        if self.main_sha(name)!=expected or self.branch_sha(name,legacy_branch)!=legacy_sha or not self.legacy_pr_matches_exact(
            name,legacy_branch,legacy_pr,req,legacy_sha,legacy_body,legacy_patch
        ):
            try:
                self.delete_branch(name,branch)
            except (BootstrapError,OSError):
                pass
            raise BootstrapError("El bootstrap legacy cambió durante la migración.")
        body=f"Bootstrap gobernado de coordinación para #{req['target_issue']}.\n\nBase exacta: `{expected}`\n\nSupersedes bootstrap PR #{legacy_pr}.\n\n{marker(req)}"
        pr=self.create_pr(name,branch,f"chore(factory): endurecer bootstrap coordinación (#{req['target_issue']})",body)
        return commit["sha"],pr

def historical_patch_for_branch(
    gateway: Any,
    name: str,
    branch: str,
    branch_sha: str,
    historical: dict[str,Any] | None,
    candidates: dict[str,str] | tuple[dict[str,str], ...],
)->dict[str,str]:
    if historical is None:
        raise BootstrapError("La rama bootstrap pertenece a otra intención.")
    options=(candidates,) if isinstance(candidates,dict) else candidates
    matching=[
        candidate for candidate in options
        if gateway.commit_matches_marker(name,branch_sha,historical,set(candidate))
        and gateway.branch_matches(name,branch,candidate)
    ]
    if len(matching)!=1:
        raise BootstrapError("La rama bootstrap pertenece a otra intención.")
    return matching[0]

def reuse_existing(req: dict[str,Any],gateway: Any,patch: dict[str,str],legacy: dict[str,str] | tuple[dict[str,str], ...],branch: str,bsha: str|None,gpr: dict[str,Any]|None)->dict[str,Any]|None:
    if bsha is None and gpr is None: return None
    name=req["target_repository"]
    if bsha is not None and gateway.commit_matches(name,bsha,req,set(patch)) and gateway.branch_matches(name,branch,patch):
        if gpr is None:
            if gateway.main_sha(name)!=req["expected_main_sha"]:
                gateway.delete_branch(name,branch)
                raise BootstrapError("main cambió antes de crear PR; rama bootstrap revertida.")
            body=f"Bootstrap gobernado de coordinación para #{req['target_issue']}.\n\nBase exacta: `{req['expected_main_sha']}`\n\n{marker(req)}"
            pr=gateway.create_pr(name,branch,f"chore(factory): restaurar coordinación (#{req['target_issue']})",body)
            return {"status":"confirmed","branch":branch,"pr":pr,"created":True}
        if not gateway.pr_matches(name,branch,gpr,req): raise BootstrapError("El PR bootstrap pertenece a otra intención.")
        return {"status":"confirmed","branch":branch,"pr":gpr.get("number"),"created":False}

    if bsha is None:
        raise BootstrapError("La rama bootstrap pertenece a otra intención.")
    if gpr is None:
        gpr=gateway.closed_pr(name,branch)
    if gpr is None:
        raise BootstrapError("La rama bootstrap pertenece a otra intención.")
    historical=gateway.legacy_marker(name,branch,gpr,req)
    legacy=historical_patch_for_branch(gateway,name,branch,bsha,historical,legacy)
    legacy_body=str(gpr.get("body") or "")

    replacement=replacement_branch_name(req,patch)
    replacement_sha=gateway.branch_sha(name,replacement)
    replacement_pr=gateway.open_pr(name,replacement)
    if replacement_sha is not None or replacement_pr is not None:
        if replacement_sha is not None and replacement_pr is None and gateway.commit_matches(name,replacement_sha,req,set(patch)) and gateway.branch_matches(name,replacement,patch):
            if gateway.main_sha(name)!=req["expected_main_sha"] or not gateway.legacy_pr_matches_exact(
                name,branch,gpr["number"],req,bsha,legacy_body,legacy
            ):
                raise BootstrapError("El bootstrap legacy cambió antes de crear PR replacement.")
            body=f"Bootstrap gobernado de coordinación para #{req['target_issue']}.\n\nBase exacta: `{req['expected_main_sha']}`\n\nSupersedes bootstrap PR #{gpr['number']}.\n\n{marker(req)}"
            pr=gateway.create_pr(name,replacement,f"chore(factory): endurecer bootstrap coordinación (#{req['target_issue']})",body)
            return {"status":"confirmed","branch":replacement,"pr":pr,"created":True}
        if replacement_sha is None or replacement_pr is None or not gateway.commit_matches(name,replacement_sha,req,set(patch)) or not gateway.branch_matches(name,replacement,patch) or not gateway.pr_matches(name,replacement,replacement_pr,req) or f"Supersedes bootstrap PR #{gpr['number']}." not in str(replacement_pr.get("body") or ""):
            raise BootstrapError("Replacement bootstrap pertenece a otra intención.")
        if not gateway.legacy_pr_matches_exact(name,branch,gpr["number"],req,bsha,legacy_body,legacy):
            raise BootstrapError("El bootstrap legacy cambió después de crear replacement.")
        return {"status":"confirmed","branch":replacement,"pr":replacement_pr.get("number"),"created":False}

    if gateway.main_sha(name)!=req["expected_main_sha"] or not gateway.legacy_pr_matches_exact(
        name,branch,gpr["number"],req,bsha,legacy_body,legacy
    ):
        raise BootstrapError("El bootstrap legacy cambió antes de migrar.")
    _,pr=gateway.materialize_replacement(
        req,patch,replacement,branch,bsha,gpr["number"],legacy_body,legacy
    )
    return {"status":"confirmed","branch":replacement,"pr":pr,"created":True}

def bootstrap_prepared(raw: dict[str,str], gateway: Any, template: str, patch: dict[str,str]) -> dict[str,Any]:
    req = validate_request(raw)
    validate_patch(patch, GRINDFLOW_DELIVERY_PATHS if req["target_repository"] == GRINDFLOW_REPO else ALLOWED_PATHS)
    return bootstrap(raw, gateway, template, patch)

def bootstrap(raw: dict[str,str],gateway: Any,template: str,prepared_patch: dict[str,str] | None=None)->dict[str,Any]:
    req=validate_request(raw); gateway.authorize(); gateway.repository(req["target_repository"])
    name=req["target_repository"]
    if not gateway.issue_open(name,req["target_issue"]): raise BootstrapError("Issue objetivo no está abierto.")
    if gateway.main_sha(name)!=req["expected_main_sha"]: raise BootstrapError("expected_main_sha no coincide con main.")
    patch = prepared_patch if prepared_patch is not None else build_patch(template)
    validate_patch(patch, name if prepared_patch is not None else None)
    historical=(legacy_patch(template),build_patch(template,CALLER_PATH))
    branch=branch_name(req)
    existing=reuse_existing(req,gateway,patch,historical,branch,gateway.branch_sha(name,branch),gateway.open_pr(name,branch))
    if existing is not None: return existing
    if all(gateway.file_text(name,path,"main")==content for path,content in patch.items()):
        return {"status":"already_bootstrapped","branch":None,"pr":None,"created":False}
    _,pr=gateway.materialize(req,patch)
    return {"status":"created","branch":branch,"pr":pr,"created":True}

def _raw_request() -> dict[str, str]:
    return {name:os.getenv(name.upper(),"") for name in ("target_repository","target_issue","expected_main_sha","governance_ref","idempotency_key")}

def main()->int:
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true")
    mode.add_argument("--apply-prepared",action="store_true")
    parser.add_argument("--consumer-root",default="consumer")
    args=parser.parse_args()
    raw=_raw_request()
    try:
        template=CALLER_TEMPLATE.read_text(encoding="utf-8")
        target=prepared_file_for_mode(args.apply_prepared)
        if target.is_symlink() or target.is_dir():
            raise BootstrapError("Entrega preparada usa un path inseguro.")
        if args.prepare:
            if os.getenv("FACTORY_PROVISION_TOKEN"):
                raise BootstrapError("Preparación de consumidor no admite FACTORY_PROVISION_TOKEN.")
            prepared=prepare_delivery_patch(raw,template,Path(args.consumer_root))
            target.write_text(json.dumps(prepared,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
            result={"status":"prepared","paths":sorted(prepared["patch"]),"patch_sha":prepared["patch_sha256"]}
        else:
            if not target.is_file() or target.stat().st_size>GRINDFLOW_MAX_TOTAL*2:
                raise BootstrapError("Entrega preparada ausente o excesiva.")
            prepared=json.loads(target.read_text(encoding="utf-8"))
            patch=load_prepared_delivery(raw,prepared)
            result=bootstrap_prepared(raw,GitHubGateway(os.getenv("FACTORY_PROVISION_TOKEN","")),template,patch)
    except (OSError,json.JSONDecodeError,BootstrapError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 2
    print(json.dumps(result,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
