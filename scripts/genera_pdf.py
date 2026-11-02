#!/usr/bin/env python3
"""Genera un PDF A4 per ogni canto (titolo, testo e accordi), senza sfondi: solo nero su bianco.

Impaginazione ispirata ai fogli di canto classici: titolo centrato in grassetto, eventuale nota sotto,
strofe con gli accordi sopra la sillaba, ritornello in corsivo, etichette (es. "Esploratori:") in
grassetto corsivo; una colonna per i canti brevi, due per quelli lunghi.

  {c: Nota introduttiva}   riga di commento seguita da una riga vuota = nota sotto il titolo
  {c: Esploratori:}        commento attaccato alle righe = etichetta della strofa

Richiede: pip install reportlab
"""
import argparse
import re
import unicodedata
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from common import CANTI_PATH, ROOT, carica_json, carica_meta, parse_chordpro

TESTO, TESTO_I, TITOLO, ACCORDO = "Times-Roman", "Times-Italic", "Times-Bold", "Times-BoldItalic"
CORPO, CORPO_ACCORDO = 12.5, 10
ALTEZZA_ACCORDI, ALTEZZA_RIGA, ALTEZZA_ETICHETTA, SPAZIO_STROFE = 14, 15.5, 18, 9
MARGINE_X, MARGINE_SU, MARGINE_GIU, SPAZIO_COLONNE, RIENTRO = 48, 50, 58, 26, 14


def pulisci(s):
    """I font standard del PDF coprono solo Windows-1252: il resto viene semplificato."""
    out = []
    for c in unicodedata.normalize("NFC", s):
        try:
            c.encode("cp1252")
            out.append(c)
        except UnicodeEncodeError:
            out.append(unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode() or "?")
    return "".join(out)


def parole_riga(segmenti):
    """Ogni parola e' una lista di (accordo|None, testo): l'accordo sta sulla prima sillaba che segue."""
    pezzi = []
    for accordo, testo in segmenti:
        usato = False
        for t in re.split(r"(\s+)", testo):
            if t == "":
                continue
            if t.isspace():
                if accordo and not usato:
                    pezzi.append((accordo, ""))
                    usato = True
                pezzi.append(None)
            else:
                pezzi.append((None if usato else accordo, t))
                usato = True
        if accordo and not usato:
            pezzi.append((accordo, ""))
    parole, corrente = [], []
    for p in pezzi:
        if p is None:
            if corrente:
                parole.append(corrente)
                corrente = []
        else:
            corrente.append(p)
    if corrente:
        parole.append(corrente)
    return parole


def impagina_riga(segmenti, larghezza, font):
    """Spezza la riga in sottorighe che stanno in `larghezza`. -> [[(x, [(accordo, testo, w)])]]"""
    spazio = stringWidth(" ", font, CORPO)
    righe, x = [[]], 0.0
    for parola in parole_riga(segmenti):
        pezzi, wp = [], 0.0
        for accordo, testo in parola:
            a, t = pulisci(accordo) if accordo else None, pulisci(testo)
            w = max(stringWidth(t, font, CORPO), stringWidth(a, ACCORDO, CORPO_ACCORDO) + 3 if a else 0)
            pezzi.append((a, t, w))
            wp += w
        if x > 0 and x + spazio + wp > larghezza:
            righe.append([])
            x = RIENTRO
        elif x > 0:
            x += spazio
        righe[-1].append((x, pezzi))
        x += wp
    return righe


def costruisci(testo, larghezza):
    """Restituisce (nota, gruppi). Un gruppo = una strofa con etichetta (non si spezza tra colonne)."""
    elementi = parse_chordpro(testo)
    nota, gruppi, corrente = [], [], None

    def nuovo():
        g = {"righe": [], "h": 0.0}
        gruppi.append(g)
        return g

    for i, el in enumerate(elementi):
        if el[0] == "vuota":
            corrente = None
        elif el[0] == "commento":
            seguente = elementi[i + 1][0] if i + 1 < len(elementi) else "vuota"
            if not gruppi and corrente is None and seguente == "vuota":
                nota.append(pulisci(el[1]))
                continue
            corrente = corrente or nuovo()
            corrente["righe"].append({"tipo": "etichetta", "testo": pulisci(el[1]), "h": ALTEZZA_ETICHETTA})
        else:
            _, segmenti, ritornello = el
            corrente = corrente or nuovo()
            font = TESTO_I if ritornello else TESTO
            for sotto in impagina_riga(segmenti, larghezza - (RIENTRO if ritornello else 0), font):
                con_accordi = any(a for _, pezzi in sotto for a, _, _ in pezzi)
                corrente["righe"].append({
                    "tipo": "riga", "parole": sotto, "font": font, "accordi": con_accordi,
                    "x0": RIENTRO if ritornello else 0,
                    "h": ALTEZZA_RIGA + (ALTEZZA_ACCORDI if con_accordi else 0)})
    for g in gruppi:
        g["h"] = sum(r["h"] for r in g["righe"])
    return nota, [g for g in gruppi if g["righe"]]


def spezza(gruppo, capienza):
    parti, riga_h, corrente = [], 0.0, []
    for r in gruppo["righe"]:
        if corrente and riga_h + r["h"] > capienza:
            parti.append({"righe": corrente, "h": riga_h})
            corrente, riga_h = [], 0.0
        corrente.append(r)
        riga_h += r["h"]
    parti.append({"righe": corrente, "h": riga_h})
    return parti


def colloca(gruppi, ncol, cap_primo, cap_altre, limite=None):
    """Distribuisce i gruppi in colonne; la colonna k sta nella pagina k // ncol."""
    def cap(k):
        c = cap_primo if k // ncol == 0 else cap_altre
        return min(c, limite) if limite and k // ncol == 0 else c

    colonne, usato = [[]], 0.0
    for g in gruppi:
        for p in (spezza(g, cap(len(colonne) - 1)) if g["h"] > cap(len(colonne) - 1) else [g]):
            k = len(colonne) - 1
            gap = SPAZIO_STROFE if colonne[k] else 0
            if colonne[k] and usato + gap + p["h"] > cap(k):
                colonne.append([])
                usato, gap, k = 0.0, 0, k + 1
            colonne[k].append(p)
            usato += gap + p["h"]
    return colonne


def altezza_totale(gruppi):
    return sum(g["h"] for g in gruppi) + SPAZIO_STROFE * max(0, len(gruppi) - 1)


def disegna_gruppo(c, g, x, y):
    for r in g["righe"]:
        if r["tipo"] == "etichetta":
            c.setFont(ACCORDO, CORPO)
            c.drawString(x, y - 12, r["testo"])
        else:
            base = y - (ALTEZZA_ACCORDI if r["accordi"] else 0) - 11
            for px, pezzi in r["parole"]:
                cx = x + r["x0"] + px
                for accordo, testo, w in pezzi:
                    if accordo:
                        c.setFont(ACCORDO, CORPO_ACCORDO)
                        c.drawString(cx, base + 11, accordo)
                    c.setFont(r["font"], CORPO)
                    c.drawString(cx, base, testo)
                    cx += w
        y -= r["h"]
    return y


def genera_pdf(canto, meta, percorso):
    W, H = A4
    larg = W - 2 * MARGINE_X
    titolo = simpleSplit(pulisci(canto["titolo"]), TITOLO, 22, larg)
    sotto = pulisci(" · ".join(filter(None, [canto.get("autore"), str(canto["anno"]) if canto.get("anno") else ""])))
    nota, gruppi = costruisci(canto["testo_accordi"], larg)
    righe_nota = [r for n in nota for r in simpleSplit(n, TESTO_I, 10.5, 340)]
    testa = len(titolo) * 27 + (20 if sotto else 0) + (len(righe_nota) * 13 + 8 if righe_nota else 0) + 20
    cap_primo, cap_altre = H - MARGINE_SU - MARGINE_GIU - testa, H - 2 * MARGINE_SU - 10

    ncol, larg_col = 1, larg
    if altezza_totale(gruppi) > cap_primo * 0.6:
        ncol, larg_col = 2, (larg - SPAZIO_COLONNE) / 2
        nota, gruppi = costruisci(canto["testo_accordi"], larg_col)
    if ncol == 2:
        limite = altezza_totale(gruppi) / 2 + 30
        while True:
            colonne = colloca(gruppi, 2, cap_primo, cap_altre, limite)
            if len(colonne) <= 2 or limite >= cap_primo:
                break
            limite += 12
    else:
        colonne = colloca(gruppi, 1, cap_primo, cap_altre)
    pagine = (len(colonne) + ncol - 1) // ncol

    c = canvas.Canvas(str(percorso), pagesize=A4)
    c.setTitle(pulisci(canto["titolo"]))
    c.setAuthor(pulisci(meta.get("titolo", "Canzoniere")))
    piede = pulisci(" · ".join(filter(None, [meta.get("titolo"), meta.get("sottotitolo")])))
    for p in range(pagine):
        y = H - MARGINE_SU
        if p == 0:
            c.setFont(TITOLO, 22)
            for riga in titolo:
                c.drawCentredString(W / 2, y - 20, riga)
                y -= 27
            if sotto:
                c.setFont(TESTO_I, 11)
                c.drawCentredString(W / 2, y - 10, sotto)
                y -= 20
            if righe_nota:
                c.setFont(TESTO_I, 10.5)
                y -= 8
                for riga in righe_nota:
                    c.drawCentredString(W / 2, y - 8, riga)
                    y -= 13
            y -= 20
        for i in range(ncol):
            k = p * ncol + i
            if k >= len(colonne):
                break
            cy = y
            for g in colonne[k]:
                cy = disegna_gruppo(c, g, MARGINE_X + i * (larg_col + SPAZIO_COLONNE), cy) - SPAZIO_STROFE
        c.setFont(TESTO, 8.5)
        c.drawCentredString(W / 2, 34, piede)
        if meta.get("url"):
            c.drawCentredString(W / 2, 24, meta["url"].replace("https://", ""))
        if pagine > 1:
            c.drawRightString(W - MARGINE_X, 34, f"{p + 1}/{pagine}")
        c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canti", default=str(CANTI_PATH))
    ap.add_argument("--out", default=str(ROOT / "build" / "pdf"), help="cartella di destinazione (file <id>.pdf)")
    ap.add_argument("--solo", help="id del canto da generare")
    args = ap.parse_args()

    meta = carica_meta()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for canto in carica_json(args.canti):
        if args.solo and str(canto["id"]) != args.solo:
            continue
        genera_pdf(canto, meta, out / f"{canto['id']}.pdf")
        n += 1
    print(f"{n} PDF in {out}")


if __name__ == "__main__":
    main()
