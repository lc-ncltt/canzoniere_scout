#!/usr/bin/env python3
"""Costruisce data/canti.json da data/elenco.csv + testi/*.cho.

  data/elenco.csv   una riga per canto (si modifica con Excel/Fogli Google, separatore ;)
                    colonne: titolo;categoria;sottosezione;branche;intensita;autore;anno;durata;note;url_audio;url_spartito
                    branche = sigle separate da / (LC/EG/RS), intensita = 1..5 (opzionale)
  testi/<slug>.cho  testo con accordi in ChordPro; lo slug e' il titolo in minuscolo con i trattini
                    (es. "Fra' Martino" -> fra-martino.cho). I canti senza file (o con file vuoto)
                    restano nell'elenco ma NON entrano in libro e web app finche' non hanno il testo.

Ordine nel libro: sezione (come in meta.json), sottosezione, poi l'ordinamento della sezione
(meta.json "ordinamento": elenco | branca | titolo; default intensita crescente, poi titolo).
Gli id si assegnano di conseguenza; le pagine si rileggono con sync_pages.py dopo la compilazione.
"""
import argparse
import csv
import re
import sys
import unicodedata

from common import (_META, CANTI_PATH, CATEGORIE, ROOT, SEGNAPOSTO_TESTO, SOTTOSEZIONI,
                    salva_json, valida)

COLONNE = ["titolo", "categoria", "sottosezione", "branche", "intensita", "autore", "anno", "durata", "note",
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
    ap.add_argument("--includi-senza-testo", action="store_true",
                    help="include anche i canti senza testo (nel libro restano pagine con segnaposto)")
    args = ap.parse_args()

    from pathlib import Path
    cartella = Path(args.testi)
    righe = leggi_csv(Path(args.elenco))
    if not righe or "titolo" not in righe[0]:
        sys.exit("elenco.csv: serve almeno la colonna 'titolo'")

    canti = []
    da_classificare = []
    da_rivedere = []
    for n_riga, r in enumerate(righe):
        categoria = r.get("categoria") or args.default_sezione
        if not categoria:  # non ancora classificato: resta in elenco, fuori dal libro
            da_classificare.append(r["titolo"])
            if (cartella / f"{slug(r['titolo'])}.cho").exists():
                sys.exit(f"'{r['titolo']}' ha un testo ma nessuna categoria in elenco.csv: classificalo")
            continue
        canto = {
            "titolo": r["titolo"],
            "categoria": categoria,
            "pagina": None,  # la riempie sync_pages.py dopo la compilazione
            "url_audio": r.get("url_audio") or None,
            "url_spartito": r.get("url_spartito") or None,
            "_riga": n_riga,
        }
        if r.get("sottosezione"):
            canto["sottosezione"] = r["sottosezione"]
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

    senza_testo = [c for c in canti if c["testo_accordi"].startswith(SEGNAPOSTO_TESTO)]
    if not args.includi_senza_testo:
        canti = [c for c in canti if c not in senza_testo]
    if not canti:
        sys.exit("Nessun canto ha ancora un file testi/<titolo>.cho con del testo")

    ordine = {s: i for i, s in enumerate(CATEGORIE)}
    senza_sub = _META.get("posizione_senza_sottosezione", {})
    ordinamento = _META.get("ordinamento", {})

    def posizione_sub(c):  # senza sottosezione: alla posizione indicata in meta.json, altrimenti per ultimi
        subs = SOTTOSEZIONI.get(c["categoria"], [])
        if c.get("sottosezione") in subs:
            return subs.index(c["sottosezione"]) * 2 + 1
        return senza_sub.get(c["categoria"], len(subs)) * 2

    def chiave_interna(c):
        # "Sezione/Sottosezione" in meta.json ha la precedenza su "Sezione"
        modo = (ordinamento.get(f"{c['categoria']}/{c.get('sottosezione', '')}")
                or ordinamento.get(c["categoria"], "intensita"))
        if modo == "elenco":  # ordine delle righe in elenco.csv
            return (c["_riga"],)
        if modo == "branca":  # LC -> EG -> RS -> per tutti
            prima = (c.get("branche") or [""])[0]
            return ({"LC": 0, "EG": 1, "RS": 2}.get(prima, 3), normalizza(c["titolo"]))
        if modo == "titolo":
            return (normalizza(c["titolo"]),)
        return (c.get("intensita") or 0, normalizza(c["titolo"]))

    obbligatoria = set(_META.get("sottosezione_obbligatoria", []))
    for c in canti:
        if c["categoria"] in obbligatoria and not c.get("sottosezione"):
            print(f"AVVISO: '{c['titolo']}' ({c['categoria']}) senza sottosezione/fase: va in fondo")
    canti.sort(key=lambda c: (ordine.get(c["categoria"], len(ordine)), posizione_sub(c), chiave_interna(c)))
    for c in canti:
        c.pop("_riga", None)
    for i, c in enumerate(canti, 1):
        c["id"] = i
    canti = [{"id": c["id"], **{k: v for k, v in c.items() if k != "id"}} for c in canti]

    errori, avvisi = valida(canti)
    if errori:
        sys.exit("\n".join("ERRORE: " + e for e in errori))
    salva_json(args.out, canti)

    totali = {}
    for c in senza_testo:
        totali[c["categoria"]] = totali.get(c["categoria"], 0) + 1
    print(f"{len(canti)} canti scritti in {args.out} (di {len(righe)} in elenco)")
    if senza_testo:
        stato = "inclusi con segnaposto" if args.includi_senza_testo else "esclusi finché manca testi/<titolo>.cho"
        print(f"  senza testo ({stato}): " + ", ".join(f"{k} {v}" for k, v in totali.items()))
    if da_rivedere:
        print(f"  bozze scaricate DA RIVEDERE: {len(da_rivedere)} (cancella la riga '# DA RIVEDERE' nel .cho dopo il controllo)")
    if da_classificare:
        print(f"  da classificare (categoria vuota in elenco.csv): {len(da_classificare)}")
    print(f"  audio mancante: {sum(not c['url_audio'] for c in canti)}"
          f"   spartito mancante: {sum(not c['url_spartito'] for c in canti)}")

if __name__ == "__main__":
    main()
