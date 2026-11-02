#!/usr/bin/env python3
"""Genera il QR code della web app in overleaf/ (PDF vettoriale per pdflatex, più SVG, EPS, PNG).

Richiede: pip install segno
"""
import argparse
import sys
from pathlib import Path

from common import ROOT, carica_meta

try:
    import segno
except ImportError:
    sys.exit("Manca il pacchetto 'segno': pip install segno")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", help="default: campo 'url' di data/meta.json")
    ap.add_argument("--error", choices=["M", "Q", "H"], default="H",
                    help="correzione errore: H (30%%, più robusto alla stampa) o M (15%%, codice meno fitto)")
    ap.add_argument("--out-dir", default=str(ROOT / "overleaf"))
    ap.add_argument("--nome", default="qr")
    args = ap.parse_args()

    url = args.url or carica_meta()["url"]
    if not url.startswith("https://"):
        sys.exit("URL mancante o non valido: passa --url oppure compila 'url' in data/meta.json")

    qr = segno.make(url, error=args.error, micro=False)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # border=4 e' la "quiet zone" richiesta dallo standard: non ridurla.
    qr.save(out / f"{args.nome}.pdf", scale=10, border=4)
    qr.save(out / f"{args.nome}.svg", scale=10, border=4)
    qr.save(out / f"{args.nome}.eps", scale=10, border=4)
    qr.save(out / f"{args.nome}.png", scale=40, border=4)  # ~1500 px: >600 dpi a 40 mm
    print(f"QR versione {qr.version}, livello {qr.error}, per {url}")
    print(f"Scritti {out}/{args.nome}.(pdf|svg|eps|png)")


if __name__ == "__main__":
    main()
