#!/usr/bin/env python3
"""Clasifica el log de un check fallido: transitorio, conflicto, dependencia o real.

Uso: gh run view <id> --log-failed | ci_triage.py   → JSON {class, evidence}.
Un fallo `transient` admite UN re-run (`gh run rerun --failed`); cualquier
otra clase exige corregir la causa y verificar sobre el nuevo HEAD.
"""
import json
import re
import sys

RULES = (
    ("conflict", r"CONFLICT \(|merge conflict|Automatic merge failed|is not mergeable"),
    ("transient", r"ECONNRESET|ETIMEDOUT|socket hang up|503 Service|502 Bad Gateway|"
                  r"rate limit|Could not resolve host|TLS handshake timeout|"
                  r"The operation was canceled|runner has received a shutdown signal|"
                  r"Unable to download|Temporary failure in name resolution"),
    ("dependency", r"Your requirements could not be resolved|Could not find a version|"
                   r"npm (ERR!|error) code (ERESOLVE|E404)|"
                   r"composer\.lock is not up to date|lock file.*out of date|ModuleNotFoundError|"
                   r"No matching distribution"),
    ("config", r"Invalid workflow file|actionlint|Unrecognized named-value|"
               r"Process completed with exit code 127|command not found|"
               r"Resource not accessible by integration"),
    ("test", r"FAILED|AssertionError|FAIL\b|\d+ failing|Tests:\s+\d+ failed|"
             r"PHPUnit.*(Failures|Errors)|error TS\d+|ParseError|Fatal error"),
)


def classify(log):
    for name, pattern in RULES:
        m = re.search(pattern, log or "", re.I if name == "transient" else 0)
        if m:
            return {"class": name, "evidence": m.group(0)[:120]}
    return {"class": "unknown", "evidence": ""}


def main():
    print(json.dumps(classify(sys.stdin.read())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
