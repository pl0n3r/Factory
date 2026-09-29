#!/usr/bin/env python3
"""Bootstrap gobernado del caller de coordinación en repositorios existentes."""
from __future__ import annotations
import base64, hashlib, json, os, re, sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API, OWNER = "https://api.github.com", "pl0n3r"
GOVERNANCE_REF = "pl0n3r/factory@v1"
CALLER_PATH = ".github/workflows/work-coordination.yml"
TEST_PATH = "tests/test_factory_coordination_adoption.py"
CALLER_TEMPLATE = Path("governance/template/.github/workflows/coordinacion.yml")
ALLOWED_PATHS = {CALLER_PATH, TEST_PATH, "AGENTS.md"}
REPO_RE = re.compile(r"^pl0n3r/[A-Za-z0-9_.-]{1,100}$")
SHA_RE, KEY_RE = re.compile(r"^[0-9a-f]{40}$"), re.compile(r"^[0-9a-f]{64}$")
MAX_FILE, MAX_TOTAL = 120_000, 240_000

class BootstrapError(RuntimeError): pass

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

def adoption_test() -> str:
    return '''import unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass FactoryCoordinationAdoptionTests(unittest.TestCase):\n    def test_caller_uses_factory_v1_spanish_profile_only(self):\n        text = (ROOT / ".github/workflows/work-coordination.yml").read_text(encoding="utf-8")\n        self.assertIn("pl0n3r/factory/.github/workflows/coordinacion.yml@v1", text)\n        self.assertIn("profile: es", text)\n        self.assertNotIn("@main", text)\n        self.assertNotIn("coordinar_trabajo.py", text)\n        self.assertIn("startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')", text)\n        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)\n        self.assertIn("github.event.pull_request.author_association == 'OWNER'", text)\n        self.assertIn("require_reservation: true", text)\n        self.assertIn("operation: pr", text)\n        for event in ("issue_comment:", "issues:", "pull_request:", "workflow_dispatch:", "schedule:"):\n            self.assertIn(event, text)\n'''

def validate_patch(patch: Any) -> None:
    if not isinstance(patch, dict) or not patch or not set(patch).issubset(ALLOWED_PATHS): raise BootstrapError("Patch fuera de la allowlist.")
    total = 0
    for path, content in patch.items():
        rel = Path(path)
        if rel.is_absolute() or ".." in rel.parts or ".git" in rel.parts or not isinstance(content, str): raise BootstrapError("Patch inválido.")
        total += len(content.encode())
        if len(content.encode()) > MAX_FILE or total > MAX_TOTAL: raise BootstrapError("Patch excede límites.")
    if CALLER_PATH not in patch or TEST_PATH not in patch: raise BootstrapError("Patch incompleto.")

def build_patch(template: str) -> dict[str, str]:
    patch = {CALLER_PATH: caller_content(template), TEST_PATH: adoption_test()}; validate_patch(patch); return patch

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
    def delete_branch(self,name: str,branch: str)->None:
        self._request("DELETE",f"/repos/{name}/git/refs/heads/{quote(branch,safe='')}")
    def create_pr(self,name: str,branch: str,title: str,body: str)->int:
        try:
            pr=self._request("POST",f"/repos/{name}/pulls",{"title":title,"head":branch,"base":"main","body":body})
            if not isinstance(pr,dict) or not isinstance(pr.get("base"),dict) or pr["base"].get("ref")!="main" or not isinstance(pr.get("head"),dict) or pr["head"].get("ref")!=branch or not isinstance(pr.get("number"),int):
                raise BootstrapError("PR bootstrap inválido.")
            return pr["number"]
        except BootstrapError:
            self.delete_branch(name,branch)
            raise
    def file_text(self,name: str, path: str, ref: str)->str|None:
        value=self._request("GET",f"/repos/{name}/contents/{path}?ref={quote(ref,safe='')}",allow=(404,))
        if value is None: return None
        if not isinstance(value,dict) or value.get("type") not in (None,"file") or value.get("encoding")!="base64": raise BootstrapError("Path remoto no es archivo regular.")
        try: return base64.b64decode(value["content"]).decode()
        except (KeyError,TypeError,ValueError) as exc: raise BootstrapError("Contenido remoto ilegible.") from exc
    def branch_matches(self,name: str,branch: str, patch: dict[str,str])->bool: return all(self.file_text(name,p,branch)==v for p,v in patch.items())
    def commit_matches(self,name: str,sha: str,req: dict[str,Any])->bool:
        value=self._request("GET",f"/repos/{name}/git/commits/{sha}")
        parents=value.get("parents",[]) if isinstance(value,dict) else []
        compare=self._request("GET",f"/repos/{name}/compare/{req['expected_main_sha']}...{sha}") or {}
        paths={row.get("filename") for row in compare.get("files",[])} if isinstance(compare,dict) else set()
        return bool(isinstance(value,dict) and f"Factory-Bootstrap-Identity: {identity(req)}" in value.get("message","") and len(parents)==1 and parents[0].get("sha")==req["expected_main_sha"] and paths=={CALLER_PATH,TEST_PATH})
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

def reuse_existing(req: dict[str,Any],gateway: Any,patch: dict[str,str],branch: str,bsha: str|None,gpr: dict[str,Any]|None)->dict[str,Any]|None:
    if bsha is None and gpr is None: return None
    name=req["target_repository"]
    if bsha is None or not gateway.commit_matches(name,bsha,req) or not gateway.branch_matches(name,branch,patch):
        raise BootstrapError("La rama bootstrap pertenece a otra intención.")
    if gpr is None:
        if gateway.main_sha(name)!=req["expected_main_sha"]:
            gateway.delete_branch(name,branch)
            raise BootstrapError("main cambió antes de crear PR; rama bootstrap revertida.")
        pr=gateway.create_pr(name,branch,f"chore(factory): restaurar coordinación (#{req['target_issue']})",marker(req))
        return {"status":"confirmed","branch":branch,"pr":pr,"created":True}
    if marker(req) not in str(gpr.get("body") or ""): raise BootstrapError("El PR bootstrap pertenece a otra intención.")
    return {"status":"confirmed","branch":branch,"pr":gpr.get("number"),"created":False}

def bootstrap(raw: dict[str,str],gateway: Any,template: str)->dict[str,Any]:
    req=validate_request(raw); gateway.authorize(); gateway.repository(req["target_repository"])
    name=req["target_repository"]
    if not gateway.issue_open(name,req["target_issue"]): raise BootstrapError("Issue objetivo no está abierto.")
    if gateway.main_sha(name)!=req["expected_main_sha"]: raise BootstrapError("expected_main_sha no coincide con main.")
    patch,branch=build_patch(template),branch_name(req)
    existing=reuse_existing(req,gateway,patch,branch,gateway.branch_sha(name,branch),gateway.open_pr(name,branch))
    if existing is not None: return existing
    if gateway.file_text(name,CALLER_PATH,"main")==patch[CALLER_PATH] and gateway.file_text(name,TEST_PATH,"main")==patch[TEST_PATH]:
        return {"status":"already_bootstrapped","branch":None,"pr":None,"created":False}
    _,pr=gateway.materialize(req,patch)
    return {"status":"created","branch":branch,"pr":pr,"created":True}

def main()->int:
    raw={name:os.getenv(name.upper(),"") for name in ("target_repository","target_issue","expected_main_sha","governance_ref","idempotency_key")}
    try: result=bootstrap(raw,GitHubGateway(os.getenv("FACTORY_PROVISION_TOKEN","")),CALLER_TEMPLATE.read_text(encoding="utf-8"))
    except (OSError,BootstrapError) as exc: print(f"ERROR: {exc}",file=sys.stderr); return 2
    print(json.dumps(result,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
