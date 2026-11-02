#!/usr/bin/env python3
"""Costruisce data/canti.json da data/elenco.csv + testi/*.cho.

  data/elenco.csv   una riga per canto (si modifica con Excel/Fogli Google, separatore ;)
                    colonne: titolo;categoria;branche;intensita;autore;anno;durata;note;url_audio;url_spartito
                    branche = sigle separate da / (LC/EG/RS), intensita = 1..5 (opzionale)
  testi/<slug>.cho  testo con accordi in ChordPro; lo slug e' il titolo in minuscolo con i trattini
                    (es. "Fra' Martino" -> fra-martino.cho). Se manca, resta un segnaposto.

Ordine nel libro: sezione (come in meta.json), poi intensita crescente, poi titolo.
Gli id si assegnano di conseguenza; le pagine si rileggono con sync_pages.py dopo la compilazione.
"""
import argparse
import csv
import re
import sys
import unicodedata

from common import (CANTI_PATH, CATEGORIE, ROOT, SEGNAPOSTO_TESTO, salva_json,
                    valida)

COLONNE = ["titolo", "categoria", "branche", "intensita", "autore", "anno", "durata", "note",
           "url_audio", "url_spartito"]


def normalizza(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def slug(titolo):
    return re.sub(r"[^a-z0-9]+", "-", normalizza(titolo)).strip("-")


def leggi_csv(percorso):
    grezzo = percorso.read_bytes()
    try:
        testo = grezzo.decode("utf-8-sig")
    except UnicodeDecodeError:  # Excel italiano salva spesso in Windows-1252
        testo = grezzo.decode("cp1252")
    righe = testo.splitlines()
    delim = ";" if ";" in righe[0] else ","
    lettore = csv.DictReader(righe, delimiter=delim)
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            for r in lettore if any((v or "").strip() for v in r.values())]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elenco", default=str(ROOT / "data" / "elenco.csv"))
    ap.add_argument("--testi", default=str(ROOT / "testi"))
    ap.add_argument("--out", default=str(CANTI_PATH))
    ap.add_argument("--default-sezione", help="sezione per le righe senza categoria (poi da riclassificare)")
    ap.add_argument("--crea-testi", action="store_true",
                    help="crea in testi/ un file .cho vuoto per ogni canto che non ne ha")
    args = ap.parse_args()

    from pathlib import Path
    cartella = Path(args.testi)
    righe = leggi_csv(Path(args.elenco))
    if not righe or "titolo" not in righe[0]:
        sys.exit("elenco.csv: serve almeno la colonna 'titolo'")

    canti = []
    for r in righe:
        categoria = r.get("categoria") or args.default_sezione
        if not categoria:
            sys.exit(f"'{r['titolo']}': categoria mancante (usa --default-sezione per un import iniziale)")
        canto = {
            "titolo": r["titolo"],
            "categoria": categoria,
            "pagina": None,  # la riempie sync_pages.py dopo la compilazione
            "url_audio": r.get("url_audio") or None,
            "url_spartito": r.get("url_spartito") or None,
        }
        branche = [b.strip().upper() for b in re.split(r"[/,; ]+", r.get("branche", "")) if b.strip()]
        if branche:
            canto["branche"] = branche
        if r.get("intensita"):
            if not r["intensita"].isdigit():
                sys.exit(f"'{r['titolo']}': intensita deve essere un numero 1-5")
            canto["intensita"] = int(r["intensita"])
        if r.get("anno"):
            if not r["anno"].isdigit():
                sys.exit(f"'{r['titolo']}': anno deve essere un numero (es. 1947)")
            canto["anno"] = int(r["anno"])
        if r.get("durata"):
            canto["durata"] = r["durata"]
        for campo in ("autore", "note"):
            if r.get(campo):
                canto[campo] = r[campo]

        file_testo = cartella / f"{slug(r['titolo'])}.cho"
        if file_testo.exists():
            canto["testo_accordi"] = file_testo.read_text(encoding="utf-8").strip() + "\n"
        else:
            canto["testo_accordi"] = SEGNAPOSTO_TESTO + "\n"
            if args.crea_testi:
                cartella.mkdir(exist_ok=True)
                file_testo.write_text("", encoding="utf-8")
        canti.append(canto)

    ordine = {s: i for i, s in enumerate(CATEGORIE)}
    canti.sort(key=lambda c: (ordine.get(c["categoria"], len(ordine)), c.get("intensita") or 0,
                              normalizza(c["titolo"])))
    for i, c in enumerate(canti, 1):
        c["id"] = i
    canti = [{"id": c["id"], **{k: v for k, v in c.items() if k != "id"}} for c in canti]

    errori, avvisi = valida(canti)
    if errori:
        sys.exit("\n".join("ERRORE: " + e for e in errori))
    salva_json(args.out, canti)

    mancanti = [c["titolo"] for c in canti if c["testo_accordi"].startswith(SEGNAPOSTO_TESTO)]
    print(f"{len(canti)} canti scritti in {args.out}")
    print(f"  testo mancante: {len(mancanti)}   audio mancante: {sum(not c['url_audio'] for c in canti)}"
          f"   spartito mancante: {sum(not c['url_spartito'] for c in canti)}")
    for t in mancanti[:15]:
        print("   - senza testo:", t)
    if len(mancanti) > 15:
        print(f"   ... e altri {len(mancanti) - 15}")


if __name__ == "__main__":
    main()
