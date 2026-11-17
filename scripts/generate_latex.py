#!/usr/bin/env python3
"""Genera build/canzoniere.tex da data/canti.json + latex/template.tex.

Ogni sezione ha una pagina divisoria; i canti scorrono di seguito su due colonne
(i corti non si spezzano). La pagina stampata di ogni canto si legge dal .aux con sync_pages.py.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

from common import (CANTI_PATH, CATEGORIE, META_PATH, ROOT, SOTTOSEZIONI, carica_json,
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


def pagine_iniziali(meta):
    """Pagine scritte a mano in latex/front/*.tex, inserite in ordine alfabetico di nome file."""
    pezzi = []
    for f in sorted((ROOT / "latex" / "front").glob("*.tex")):
        pezzi.append(f.read_text(encoding="utf-8").replace(
            "<<SEZIONI>>", ", ".join(esc(s) for s in meta["sezioni"])))
    return "\n\n".join(pezzi)


CARATTERI_PER_RIGA = 40  # circa, in una colonna di A5 orizzontale a corpo 11


def altezza_stimata(elementi, con_accordi):
    """Altezza del canto in pt (titolo compreso), per non spezzare i canti corti tra due colonne."""
    interlinea = 18 if con_accordi else 13.6
    righe = strofe = 0
    for el in elementi:
        if el[0] == "riga":
            testo = "".join(t for _, t in el[1])
            righe += max(1, -(-len(testo) // CARATTERI_PER_RIGA))
        elif el[0] == "commento":
            righe += 1
        elif el[0] == "vuota":
            strofe += 1
    return 30 + righe * interlinea + strofe * 7


ACCORDI = False  # il libro stampato e' senza accordi (restano nella web app); --accordi per includerli


def senza_accordi(elementi):
    """Toglie gli accordi; le righe di soli accordi (intro, giri) spariscono."""
    out = []
    for el in elementi:
        if el[0] == "riga":
            testo = "".join(t for _, t in el[1])
            if not testo.strip():
                continue
            el = ("riga", [(None, testo)], el[2])
        out.append(el)
    return out


_RIT = re.compile(r"^\s*rit(?:ornello)?\.?\s*:?\s*", re.I)


def _chiave(blocco):
    testo = " ".join("".join(t for _, t in e[1]) for e in blocco if e[0] == "riga")
    return re.sub(r"[^a-z0-9]+", " ", _RIT.sub("", testo).lower()).strip()


def ritornelli(elementi):
    """Solo per la stampa: il ritornello va in grassetto la prima volta, le ripetizioni diventano "Rit.".
    E' ritornello una strofa marcata {soc}/{eoc}, una che inizia con "Rit.", oppure (se il canto non ne
    marca nessuna) una strofa ripetuta identica. Anche "{c: Rit.}" e una riga "Rit." da sola diventano "Rit."."""
    blocchi, cur = [], []
    for el in elementi:
        if el[0] == "vuota":
            if cur:
                blocchi.append(cur)
            cur = []
        else:
            cur.append(el)
    if cur:
        blocchi.append(cur)

    def nota_rit(e):
        return e[0] == "commento" and _RIT.fullmatch(e[1] + " ")

    def marcato(b):
        prima = next((e for e in b if e[0] == "riga"), None)
        return any(e[0] == "riga" and e[2] for e in b) or (prima is not None and (
            (_RIT.match("".join(t for _, t in prima[1])) and _chiave([prima])) or nota_rit(b[0])))

    chiavi = [_chiave(b) for b in blocchi]
    nessun_marcato = not any(marcato(b) for b in blocchi)
    ripetute = {k for k in chiavi if k and chiavi.count(k) > 1}
    visti, out = [], []
    for b, k in zip(blocchi, chiavi):
        solo_rit = all(e[0] == "commento" and _RIT.fullmatch(e[1] + " ") for e in b) or (
            len(b) == 1 and b[0][0] == "riga" and not _chiave(b) and _RIT.match("".join(t for _, t in b[0][1])))
        troncato = (len(b) == 1 and b[0][0] == "riga" and k and re.search(r"(\.\.\.|…)\s*$", "".join(t for _, t in b[0][1]))
                    and any(v.startswith(k) and v != k for v in visti))
        if solo_rit or troncato or (k and k in visti):
            out.append([("rit",)])
            continue
        if k and (marcato(b) or (nessun_marcato and k in ripetute)):
            nuovo = []
            for e in b:
                if nota_rit(e):  # "{c: Rit.}" sopra il testo del ritornello: basta il grassetto
                    continue
                if e[0] == "riga":
                    segs = list(e[1])
                    if not nuovo and segs:  # toglie "Rit." davanti alla prima riga: lo dice il grassetto
                        a, t = segs[0]
                        segs[0] = (a, _RIT.sub("", t, count=1))
                    e = ("riga", segs, True)
                nuovo.append(e)
            b = nuovo
            visti.append(k)
        out.append(b)
    risultato = []
    for i, b in enumerate(out):
        if i:
            risultato.append(("vuota",))
        risultato += b
    return risultato


def canto_latex(c):
    elementi = parse_chordpro(c["testo_accordi"])
    if not ACCORDI:
        elementi = senza_accordi(elementi)
    elementi = ritornelli(elementi)
    con_accordi = any(a for el in elementi if el[0] == "riga" for a, _ in el[1])
    # basta che ci stiano titolo e 3 righe: il canto puo' iniziare a meta' colonna e continuare nella successiva
    altezza = min(altezza_stimata(elementi, con_accordi), 85)
    out = [r"\begingroup" + ("" if con_accordi else r"\senzaaccordi"),
           rf"\cantotesta{{{c['id']}}}{{{esc(c['titolo'])}}}{{{esc(c.get('autore', ''))}}}"
           rf"{{{tag_branche(c)}}}{{{altezza:.0f}pt}}"]
    in_ritornello = False
    ultima_vuota = True
    for el in elementi:
        if el[0] == "vuota":
            if not ultima_vuota:
                out.append(r"\strofa")
            ultima_vuota = True
            continue
        ultima_vuota = False
        if el[0] in ("commento", "rit") and in_ritornello:
            out.append(r"\end{ritornello}")
            in_ritornello = False
        if el[0] == "rit":
            out.append(r"\rit")
            continue
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
    out.append(r"\par\endgroup")
    return "\n".join(out)


def slug(testo):
    s = unicodedata.normalize("NFKD", testo)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def canti_latex(canti, accordi=False):
    global ACCORDI
    ACCORDI = accordi
    """Per ogni sezione: pagina divisoria (con latex/sezioni/<slug>.tex se esiste), poi i canti
    di seguito su due colonne, con un titoletto a ogni cambio di sottosezione (fase / momento)."""
    out = []
    for cat in dict.fromkeys(c["categoria"] for c in canti):
        intro = ROOT / "latex" / "sezioni" / f"{slug(cat)}.tex"
        testo_intro = intro.read_text(encoding="utf-8").strip() if intro.exists() else ""
        out += [rf"\sezione{{{esc(cat)}}}{{{testo_intro}}}", r"\begin{multicols}{2}\raggedcolumns"]
        sub_prec = None
        for c in (c for c in canti if c["categoria"] == cat):
            sub = c.get("sottosezione")
            if sub and sub != sub_prec:
                out.append(rf"\sottosezione{{{esc(sub)}}}")
            sub_prec = sub
            out.append(canto_latex(c))
        out.append(r"\end{multicols}")
    return "\n\n".join(out)


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
        subs = SOTTOSEZIONI.get(cat, [])
        for sub in subs + [""]:
            voci_sub = [c for c in gruppo if c.get("sottosezione", "") == sub]
            if not voci_sub:
                continue
            if sub:
                righe.append(rf"\sottocategoriaindice{{{esc(sub)}}}")
            righe += [voce(c) for c in sorted(voci_sub, key=lambda c: chiave_ordinamento(c["titolo"]))]
    righe += [r"\end{multicols}", r"\endgroup"]
    return "\n".join(righe)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--canti", default=str(CANTI_PATH))
    ap.add_argument("--meta", default=str(META_PATH))
    ap.add_argument("--template", default=str(ROOT / "latex" / "template.tex"))
    ap.add_argument("--out", default=str(ROOT / "overleaf" / "canzoniere.tex"))
    ap.add_argument("--qr", default="qr.pdf", help="file del QR, relativo alla cartella del .tex")
    ap.add_argument("--accordi", action="store_true", help="stampa anche gli accordi (di norma solo online)")
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
        "CANTI": canti_latex(canti, args.accordi),
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
