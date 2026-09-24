#!/usr/bin/env python3
"""Reintenta un conjunto cerrado de operaciones externas idempotentes."""
from __future__ import annotations
import argparse,re,subprocess,sys,time

OPERATIONS={
    "composer-install":["composer","install","--no-interaction","--prefer-dist","--no-progress"],
    "composer-audit":["composer","audit","--locked","--no-interaction"],
    "npm-ci":["npm","ci","--ignore-scripts","--no-audit","--no-fund"],
    "npm-audit":["npm","audit","--audit-level=high"],
}
TRANSIENT_EXIT_CODES={75}
TRANSIENT_PATTERNS=(
    re.compile(r"\btimed?\s*out\b",re.I),re.compile(r"\btimeout\b",re.I),
    re.compile(r"connection reset(?: by peer)?",re.I),re.compile(r"\beconnreset\b",re.I),
    re.compile(r"\betimedout\b",re.I),re.compile(r"\beconnrefused\b",re.I),
    re.compile(r"\bHTTP(?:/\S+)?\s+(?:429|502|503|504)\b",re.I),
    re.compile(r"socket hang up",re.I),
)
def operation_command(name:str)->list[str]:
    try: return list(OPERATIONS[name])
    except KeyError as exc: raise ValueError("Operación de retry no permitida.") from exc
def transient(code:int,out:str)->bool:
    return code in TRANSIENT_EXIT_CODES or any(p.search(out) for p in TRANSIENT_PATTERNS)
def run(name:str,attempts:int,base_delay:float)->int:
    if attempts<1 or attempts>5 or base_delay<0 or base_delay>30: raise ValueError("Parámetros de retry fuera de rango.")
    command=operation_command(name)
    for attempt in range(1,attempts+1):
        result=subprocess.run(command,check=False,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace")
        output=result.stdout or ""
        if output: print(output,end="" if output.endswith("\n") else "\n")
        if result.returncode==0: return 0
        if not transient(result.returncode,output) or attempt==attempts: return result.returncode
        time.sleep(min(30,base_delay*(2**(attempt-1))))
    return 1
def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--operation",required=True,choices=sorted(OPERATIONS)); p.add_argument("--attempts",type=int,default=3); p.add_argument("--base-delay",type=float,default=2); a=p.parse_args()
    try: return run(a.operation,a.attempts,a.base_delay)
    except ValueError as exc: print(f"ERROR: {exc}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
