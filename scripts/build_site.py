#!/usr/bin/env python3
"""Costruisce _site/ = webapp/ + data/canti.json (dopo averlo convalidato).

Usato sia in locale sia da GitHub Actions: un JSON non valido blocca la pubblicazione.
  python scripts/build_site.py --serve     # anteprima su http://localhost:8000
"""
import argparse
import functools
import hashlib
import http.server
import shutil
import sys
from pathlib import Path

from common import CANTI_PATH, ROOT, carica_json, valida


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()

    errori, avvisi = valida(carica_json(CANTI_PATH))
    for a in avvisi:
        print("AVVISO:", a)
    if errori:
        sys.exit("\n".join("ERRORE: " + e for e in errori))

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "webapp", out)
    shutil.copy(CANTI_PATH, out / "canti.json")
    (out / ".nojekyll").touch()

    # Versione della cache offline: cambia a ogni modifica di contenuti o codice.
    h = hashlib.sha256()
    for f in sorted(out.rglob("*")):
        if f.is_file() and f.name != "sw.js":
            h.update(f.read_bytes())
    sw = out / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8").replace("__BUILD__", h.hexdigest()[:12]),
                  encoding="utf-8", newline="\n")
    print(f"Sito pronto in {out}")

    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        print("Anteprima su http://localhost:8000 (Ctrl+C per fermare)")
        http.server.ThreadingHTTPServer(("localhost", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
