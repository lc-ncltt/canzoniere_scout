#!/usr/bin/env python3
"""Genera build/canzoniere.tex da data/canti.json + latex/template.tex.

Ogni canto inizia su una pagina nuova (due colonne): la pagina stampata di
ogni canto e' quindi prevedibile e si legge dal file .aux con sync_pages.py.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

from common import (CANTI_PATH, CATEGORIE, META_PATH, ROOT, carica_json,
                    carica_meta, parse_chordpro, valida)

ESCAPE = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(testo):
    return "".join(ESCAPE.get(c, c) for c in testo)


def riga_latex(segmenti):
    """L'accordo si aggancia alla prima parola/sillaba che lo segue; il resto
    del testo resta normale e quindi puo' andare a capo."""
    parti = []
    for accordo, testo in segmenti:
        if accordo is None:
            parti.append(esc(testo))
            continue
        m = re.match(r"(\S*)(.*)$", testo, re.S)
        parti.append(rf"\ch{{{esc(accordo)}}}{{{esc(m.group(1))}}}{esc(m.group(2))}")
    return r"\rigo{" + "".join(parti) + "}"


def tag_branche(c):
    return "".join("\\b" + b for b in c.get("branche", []))


def fiamme(c):
    return "\\fiamme{%d}" % c["intensita"] if c.get("intensita") else ""


def pagine_iniziali(meta):
    """Pagine scritte a mano in latex/front/*.tex, inserite in ordine alfabetico di nome file."""
    pezzi = []
    for f in sorted((ROOT / "latex" / "front").glob("*.tex")):
        pezzi.append(f.read_text(encoding="utf-8").replace(
            "<<SEZIONI>>", ", ".join(esc(s) for s in meta["sezioni"])))
    return "\n\n".join(pezzi)


def canto_latex(c):
    out = [rf"\cantotesta{{{c['id']}}}{{{esc(c['titolo'])}}}{{{esc(c['categoria'])}}}"
           rf"{{{esc(c.get('autore', ''))}}}{{{tag_branche(c)}}}{{{fiamme(c)}}}",
           r"\begin{multicols}{2}"]
    in_ritornello = False
    ultima_vuota = True
    for el in parse_chordpro(c["testo_accordi"]):
        if el[0] == "vuota":
            if not ultima_vuota:
                out.append(r"\strofa")
            ultima_vuota = True
            continue
        ultima_vuota = False
        if el[0] == "commento":
            out.append(rf"\commento{{{esc(el[1])}}}")
            continue
        _, segmenti, ritornello = el
        if ritornello and not in_ritornello:
            out.append(r"\begin{ritornello}")
        elif not ritornello and in_ritornello:
            out.append(r"\end{ritornello}")
        in_ritornello = ritornello
        out.append(riga_latex(segmenti))
    if in_ritornello:
        out.append(r"\end{ritornello}")
    out.append(r"\end{multicols}")
    return "\n".join(out)


def chiave_ordinamento(titolo):
    """Minuscolo, senza accenti e senza punteggiatura iniziale (es. "Fra' Martino")."""
    s = unicodedata.normalize("NFKD", titolo)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"^[^a-z0-9]+", "", s)


def voce(c):
    return rf"\voce{{{c['id']}}}{{{esc(c['titolo'])}}}"


def indice_alfabetico(canti):
    righe = [r"\titolosezione{Indice alfabetico}", r"\begingroup\small",
             r"\begin{multicols}{2}"]
    lettera = None
    for c in sorted(canti, key=lambda c: chiave_ordinamento(c["titolo"])):
        iniziale = (chiave_ordinamento(c["titolo"]) or "#")[0].upper()
        if iniziale != lettera:
            lettera = iniziale
            righe.append(rf"\lettera{{{lettera}}}")
        righe.append(voce(c))
    righe += [r"\end{multicols}", r"\endgroup"]
    return "\n".join(righe)


def indice_tematico(canti):
    righe = [r"\titolosezione{Indice per categoria}", r"\begingroup\small",
             r"\begin{multicols}{2}"]
    categorie = CATEGORIE + sorted({c["categoria"] for c in canti} - set(CATEGORIE))
    for cat in categorie:
        gruppo = [c for c in canti if c["categoria"] == cat]
        if not gruppo:
            continue
        righe.append(rf"\categoriaindice{{{esc(cat)}}}")
        righe += [voce(c) for c in sorted(gruppo, key=lambda c: chiave_ordinamento(c["titolo"]))]
    righe += [r"\end{multicols}", r"\endgroup"]
    return "\n".join(righe)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--canti", default=str(CANTI_PATH))
    ap.add_argument("--meta", default=str(META_PATH))
    ap.add_argument("--template", default=str(ROOT / "latex" / "template.tex"))
    ap.add_argument("--out", default=str(ROOT / "overleaf" / "canzoniere.tex"))
    ap.add_argument("--qr", default="qr.pdf", help="file del QR, relativo alla cartella del .tex")
    args = ap.parse_args()

    canti = sorted(carica_json(args.canti), key=lambda c: c["id"])
    errori, avvisi = valida(canti)
    for a in avvisi:
        print("AVVISO:", a)
    if errori:
        sys.exit("\n".join("ERRORE: " + e for e in errori) + "\nCorreggi data/canti.json e riprova.")

    meta = carica_meta(args.meta)
    sostituzioni = {
        "TITOLO": esc(meta["titolo"]),
        "SOTTOTITOLO": esc(meta["sottotitolo"]),
        "DEDICA": esc(meta["dedica"]),
        "ANNO": esc(meta["anno"]),
        "PAGINE_INIZIALI": pagine_iniziali(meta),
        "CANTI": "\n\n".join(canto_latex(c) for c in canti),
        "INDICE_ALFABETICO": indice_alfabetico(canti),
        "INDICE_TEMATICO": indice_tematico(canti),
        "QR_FILE": args.qr,
        "URL": meta["url"],
    }
    if not meta["url"] or "NOMEUTENTE" in meta["url"]:
        print("AVVISO: data/meta.json contiene ancora un URL segnaposto: aggiornalo prima di stampare")

    testo = Path(args.template).read_text(encoding="utf-8")
    for chiave, valore in sostituzioni.items():
        testo = testo.replace(f"<<{chiave}>>", valore)
    residui = re.findall(r"<<[A-Z_]+>>", testo)
    if residui:
        sys.exit(f"Segnaposto non risolti nel template: {residui}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(testo, encoding="utf-8", newline="\n")
    print(f"Scritto {out} ({len(canti)} canti)")
    if not (out.parent / args.qr).exists():
        print(f"AVVISO: {out.parent / args.qr} non esiste: esegui scripts/make_qr.py prima di compilare")


if __name__ == "__main__":
    main()
