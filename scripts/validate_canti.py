#!/usr/bin/env python3
"""Convalida data/canti.json. Esce con codice 1 se ci sono errori."""
import argparse
import sys
import urllib.request

from common import CANTI_PATH, carica_json, valida


def link_raggiungibile(url):
    richiesta = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "canzoniere-check"})
    try:
        with urllib.request.urlopen(richiesta, timeout=20) as r:
            return r.status < 400
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=str(CANTI_PATH))
    ap.add_argument("--strict", action="store_true", help="gli avvisi diventano errori")
    ap.add_argument("--check-urls", action="store_true", help="verifica online che i link rispondano")
    args = ap.parse_args()

    try:
        canti = carica_json(args.file)
    except (OSError, ValueError) as e:
        sys.exit(f"Impossibile leggere {args.file}: {e}")

    errori, avvisi = valida(canti)

    if args.check_urls and not errori:
        for c in canti:
            for campo in ("url_audio", "url_spartito"):
                if c[campo] and not link_raggiungibile(c[campo]):
                    errori.append(f"canto {c['id']}: {campo} non raggiungibile ({c[campo]})")

    for a in avvisi:
        print("AVVISO:", a)
    for e in errori:
        print("ERRORE:", e)
    print(f"{len(canti) if isinstance(canti, list) else 0} canti, {len(errori)} errori, {len(avvisi)} avvisi")
    sys.exit(1 if errori or (args.strict and avvisi) else 0)


if __name__ == "__main__":
    main()
