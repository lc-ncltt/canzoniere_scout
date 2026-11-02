#!/usr/bin/env python3
"""Importa una cartella di file ChordPro (*.cho, *.pro, *.txt) in data/canti.json.

Gli id seguono l'ordine alfabetico dei nomi file (es. 001-fra-martino.cho).
Direttive di metadati lette (e rimosse dal testo):
  {title: ...} {categoria: ...} {autore: ...} {audio: https://...mp3} {spartito: https://...pdf}
"""
import argparse
import re
import sys
from pathlib import Path

from common import CANTI_PATH, salva_json, valida

META = re.compile(r"^\{\s*(title|categoria|autore|audio|spartito)\s*:\s*(.*?)\s*\}\s*$", re.I)


def leggi(percorso, cid):
    meta, righe = {}, []
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        m = META.match(riga.strip())
        if m:
            meta[m.group(1).lower()] = m.group(2)
        else:
            righe.append(riga)
    canto = {
        "id": cid,
        "titolo": meta.get("title", percorso.stem),
        "categoria": meta.get("categoria", "Tradizione"),
        "pagina": None,
        "url_audio": meta.get("audio") or None,
        "url_spartito": meta.get("spartito") or None,
        "testo_accordi": "\n".join(righe).strip() + "\n",
    }
    if "autore" in meta:
        canto["autore"] = meta["autore"]
    return canto


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cartella")
    ap.add_argument("--out", default=str(CANTI_PATH))
    args = ap.parse_args()

    file = sorted(p for p in Path(args.cartella).iterdir() if p.suffix.lower() in (".cho", ".pro", ".txt"))
    canti = [leggi(p, i) for i, p in enumerate(file, 1)]
    errori, avvisi = valida(canti)
    for a in avvisi:
        print("AVVISO:", a)
    if errori:
        sys.exit("\n".join("ERRORE: " + e for e in errori))
    salva_json(args.out, canti)
    print(f"Importati {len(canti)} canti in {args.out}")


if __name__ == "__main__":
    main()
