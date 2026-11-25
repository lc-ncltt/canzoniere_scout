#!/usr/bin/env python3
"""Nessun canto deve girare pagina: a libro aperto ogni canto si deve vedere tutto
(pagina sinistra pari + pagina destra dispari).

    python scripts/impagina.py --tectonic percorso/tectonic.exe --qr percorso/qr.png

Compila, legge dal .aux dove inizia (canto:N) e dove finisce (fine:N) ogni canto e corregge
il primo che gira pagina, poi ricompila, finche' non ce ne sono piu':
  - se il canto inizia a meta' di una pagina destra, parte in cima alla pagina dopo (sinistra);
  - se e' gia' in cima a una pagina e non ci sta, va da solo sulla pagina a 3 colonne (testo a 10 pt);
  - se non ci sta neanche cosi', parte in cima alla pagina sinistra successiva (due pagine affiancate).
Il risultato va in data/impaginazione.json (letto da generate_latex.py, ricalcolato da zero a
ogni esecuzione). Dopo: sync_pages.py sul .aux finale e generate_latex.py come al solito.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import CANTI_PATH, ROOT, carica_json
from generate_latex import IMPAGINAZIONE, slug

LABEL = re.compile(r"\\newlabel\{(canto|fine):(\d+)\}\{\{[^}]*\}\{(\d+)\}")


def compila(cartella, tectonic):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_latex.py"), "--qr", "qr.png",
                    "--out", str(cartella / "canzoniere.tex")], check=True, capture_output=True)
    r = subprocess.run([tectonic, "-X", "compile", "--keep-logs", "--keep-intermediates", "canzoniere.tex"],
                       cwd=cartella, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit("Compilazione fallita:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    pagine = {"canto": {}, "fine": {}}
    for tipo, n, p in LABEL.findall((cartella / "canzoniere.aux").read_text(encoding="utf-8", errors="replace")):
        pagine[tipo][int(n)] = int(p)
    return pagine["canto"], pagine["fine"]


def gira_pagina(inizio, fine):
    """Si vede tutto se sta su una pagina, o su una pagina pari (sinistra) e la dispari che segue."""
    return not (fine == inizio or (inizio % 2 == 0 and fine == inizio + 1))


def code_corte(canti, inizio, fine, cartella, imp, provati, soglia=0.45):
    """Primo canto che sfora sulla pagina dopo con una coda corta (meno di `soglia` dell'altezza utile)
    e dopo il quale ne inizia un altro su una pagina successiva: va spostato intero sulla pagina dopo."""
    try:
        import pymupdf
        pdf = pymupdf.open(str(cartella / "canzoniere.pdf"))
    except Exception:
        return None
    prima = next(c for c in canti if c["id"] in inizio)
    off = next((i + 1 - inizio[prima["id"]] for i, pg in enumerate(pdf)
                if pg.get_text().startswith(f"{prima['id']} ")), None)
    if off is None:
        return None
    for i, c in enumerate(canti):
        n, s = c["id"], slug(c["titolo"])
        if n not in inizio or n not in fine or fine[n] == inizio[n] or s in provati or s in imp["nuova_pagina"]:
            continue
        prec = max((fine[x["id"]] for x in canti[:i] if x["id"] in fine), default=0)
        if prec < inizio[n]:
            continue  # parte gia' in cima alla pagina: spostarlo non serve
        succ = next((inizio[x["id"]] for x in canti[i + 1:] if x["id"] in inizio), None)
        if succ is not None and succ <= fine[n]:
            continue  # sulla pagina di coda c'e' anche un altro canto
        pg = pdf[fine[n] + off - 1]
        corpo = [b for b in pg.get_text("blocks") if b[3] < pg.rect.height * 0.88 and b[4].strip()]
        if corpo and (max(b[3] for b in corpo) - pg.rect.height * 0.08) < soglia * pg.rect.height * 0.8:
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tectonic", required=True)
    ap.add_argument("--qr", required=True, help="qr.png per la compilazione locale")
    ap.add_argument("--cartella", default=str(ROOT / "build" / "impagina"))
    ap.add_argument("--max", type=int, default=150, help="numero massimo di compilazioni")
    args = ap.parse_args()

    cartella = Path(args.cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    shutil.copy(args.qr, cartella / "qr.png")
    shutil.copy(ROOT / "latex" / "logo-fse.png", cartella / "logo-fse.png")
    canti = sorted(carica_json(CANTI_PATH), key=lambda c: c["id"])
    imp = {"nuova_pagina": [], "tre_colonne": [], "pagina_sinistra": []}
    provati = set()
    IMPAGINAZIONE.write_text(json.dumps(imp, indent=1) + "\n", encoding="utf-8", newline="\n")

    for giro in range(1, args.max + 1):
        inizio, fine = compila(cartella, args.tectonic)
        sbagliati = [c for c in canti if c["id"] in inizio and c["id"] in fine
                     and gira_pagina(inizio[c["id"]], fine[c["id"]])]
        print(f"giro {giro}: {len(sbagliati)} canti girano pagina", flush=True)
        if not sbagliati:
            c = code_corte(canti, inizio, fine, cartella, imp, provati)
            if not c:
                break
            s = slug(c["titolo"])
            imp["nuova_pagina"].append(s)
            provati.add(s)
            print(f"  {c['id']} {c['titolo']}: sfora di poche righe, va tutto sulla pagina dopo", flush=True)
            IMPAGINAZIONE.write_text(json.dumps(imp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                     newline="\n")
            continue
        c = sbagliati[0]
        s, n = slug(c["titolo"]), c["id"]
        prec = max((fine[x["id"]] for x in canti if x["id"] < n and x["id"] in fine), default=0)
        in_cima = prec < inizio[n]  # il canto precedente e' finito su una pagina prima: e' gia' in cima
        if s in imp["pagina_sinistra"]:
            sys.exit(f"Canto {n} {c['titolo']}: non sta neanche su due pagine affiancate, va sistemato a mano")
        if s in imp["tre_colonne"]:  # troppo lungo anche a 3 colonne: parte in cima alla pagina sinistra
            imp["tre_colonne"].remove(s)
            imp["pagina_sinistra"].append(s)
            print(f"  {n} {c['titolo']}: in cima alla pagina sinistra successiva")
        elif in_cima or s in imp["nuova_pagina"]:
            if s in imp["nuova_pagina"]:
                imp["nuova_pagina"].remove(s)
            imp["tre_colonne"].append(s)
            print(f"  {n} {c['titolo']}: da solo su una pagina, 3 colonne")
        else:
            imp["nuova_pagina"].append(s)
            print(f"  {n} {c['titolo']} (pag. {inizio[n]}-{fine[n]}): parte dalla pagina dopo")
        IMPAGINAZIONE.write_text(json.dumps(imp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                 newline="\n")
    else:
        sys.exit("Troppe compilazioni: controlla data/impaginazione.json")
    print(f"Fatto: {len(imp['nuova_pagina'])} a pagina nuova, {len(imp['tre_colonne'])} a 3 colonne, "
          f"{len(imp['pagina_sinistra'])} in cima a pagina sinistra. "
          f"Aux finale: {cartella / 'canzoniere.aux'}")


if __name__ == "__main__":
    main()
