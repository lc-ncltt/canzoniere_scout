#!/usr/bin/env python3
"""Legge build/canzoniere.aux (dopo la compilazione) e aggiorna il campo
'pagina' di data/canti.json con le pagine realmente stampate."""
import argparse
import re
import sys

from common import CANTI_PATH, ROOT, carica_json, salva_json

LABEL = re.compile(r"\\newlabel\{canto:(\d+)\}\{\{[^}]*\}\{(\d+)\}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aux", default=str(ROOT / "build" / "canzoniere.aux"))
    ap.add_argument("--canti", default=str(CANTI_PATH))
    ap.add_argument("--check", action="store_true", help="non scrive: esce con 1 se ci sono differenze")
    args = ap.parse_args()

    try:
        with open(args.aux, encoding="utf-8", errors="replace") as f:
            pagine = {int(i): int(p) for i, p in LABEL.findall(f.read())}
    except OSError as e:
        sys.exit(f"Impossibile leggere {args.aux}: {e}")

    canti = carica_json(args.canti)
    diff = 0
    for c in canti:
        nuova = pagine.get(c["id"])
        if nuova is None:
            print(f"AVVISO: canto {c['id']} non trovato nel .aux")
        elif c["pagina"] != nuova:
            print(f"canto {c['id']}: pagina {c['pagina']} -> {nuova}")
            c["pagina"] = nuova
            diff += 1

    if args.check:
        sys.exit(1 if diff else 0)
    if diff:
        salva_json(args.canti, canti)
    print(f"{diff} pagine aggiornate")


if __name__ == "__main__":
    main()
