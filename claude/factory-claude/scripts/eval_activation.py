#!/usr/bin/env python3
"""Evals de activación (proxy determinista, sin modelo).

Para cada prompt de `evals/activation.json` puntúa las skills por solapamiento
de palabras con su `description` y exige que gane la esperada con margen. Un
prompt con `skill: null` no debe superar el umbral (control negativo).
No mide la activación real de Claude: detecta descripciones que se solapan o
que dejan de cubrir su caso, y sirve de red de seguridad al editarlas.
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
STOP = set("""de la el en y a los las un una que por con para se del al es lo como o su sus este esta
mi me si no ya más mas the and or of to in for is use usala cuando al antes sin entre hasta""".split())
MIN_SCORE = 2
MIN_MARGIN = 1


def tokens(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return {w[:6] for w in re.findall(r"[a-z0-9]+", text) if len(w) > 2 and w not in STOP}


def load_descriptions():
    out = {}
    skills = os.path.join(PLUGIN, "skills")
    for name in sorted(os.listdir(skills)):
        text = open(os.path.join(skills, name, "SKILL.md"), encoding="utf-8").read()
        desc = re.search(r"^description: (.*)$", text, re.M).group(1)
        out[name] = tokens(name.replace("-", " ") + " " + desc)
    return out


def rank(prompt, descriptions):
    p = tokens(prompt)
    return sorted(((len(p & d), name) for name, d in descriptions.items()), reverse=True)


def evaluate(cases=None, descriptions=None):
    cases = cases if cases is not None else json.load(open(os.path.join(PLUGIN, "evals", "activation.json"), encoding="utf-8"))
    descriptions = descriptions or load_descriptions()
    failures = []
    for case in cases:
        ranked = rank(case["prompt"], descriptions)
        (top, top_name), (second, _) = ranked[0], ranked[1]
        if case["skill"] is None:
            if top >= MIN_SCORE:
                failures.append((case["prompt"], f"control negativo activó {top_name} ({top})"))
        elif top_name != case["skill"] or top < MIN_SCORE or top - second < MIN_MARGIN:
            failures.append((case["prompt"], f"esperaba {case['skill']}, ganó {top_name} ({top} vs {second})"))
    return failures, len(cases)


def main():
    failures, total = evaluate()
    for prompt, why in failures:
        print(f"FALLA: {prompt!r}: {why}")
    print(f"{total - len(failures)}/{total} casos")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
