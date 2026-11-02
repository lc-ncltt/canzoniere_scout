#!/usr/bin/env python3
"""Cerca su canzonierescout.it il PDF (testi+spartito+accordi) dei canti di data/elenco.csv.

Scarica solo le pagine indice del sito, confronta i titoli e verifica con una richiesta HEAD che il
PDF esista. Non copia testi: scrive solo il link nella colonna url_spartito (se vuota).
Senza --applica mostra soltanto cosa farebbe. Le corrispondenze incerte non vengono mai applicate.
"""
import argparse
import csv
import difflib
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

from build_canti import COLONNE, leggi_csv, normalizza
from common import ROOT

BASE = "https://www.canzonierescout.it/"
INDICI = ["indfuoco.htm", "indcerimonia.htm", "indbranco.htm", "inddanze.htm", "indvarie.htm", "indpreghiere.htm"]
UA = {"User-Agent": "canzoniere-link-finder (progetto scout senza scopo di lucro)"}
SOGLIA_AUTO = 0.93
SOGLIA_VERIFICA = 0.80


def scarica(url, metodo="GET"):
    req = urllib.request.Request(url, headers=UA, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.headers.get("Content-Type", "")


def chiave(titolo):
    t = re.sub(r"\(.*?\)", "", titolo)
    return re.sub(r"[^a-z0-9]+", "", normalizza(html.unescape(t)))


def voci_indice(nome):
    pagina = scarica(BASE + nome)[0].decode("cp1252", "replace")
    voci = {}
    for href, testo in re.findall(r'<a[^>]+href="([^"#?]+\.htm)"[^>]*>(.*?)</a>', pagina, re.S | re.I):
        titolo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", testo))).strip()
        if titolo and not href.startswith(("ind", "http", "pagina")):
            voci[href[:-4]] = titolo
    return voci


def trova_pdf(stem):
    """Legge la pagina del canto, prende il link .pdf e verifica con HEAD che risponda."""
    try:
        pagina = scarica(f"{BASE}{stem}.htm")[0].decode("cp1252", "replace")
        link = re.search(r'href="([^"#?]+\.pdf)"', pagina, re.I)
        if not link:
            return None
        url = BASE + link.group(1).lstrip("/")
        _, tipo = scarica(url, "HEAD")
        return url if "pdf" in tipo.lower() else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elenco", default=str(ROOT / "data" / "elenco.csv"))
    ap.add_argument("--applica", action="store_true", help="scrive i link trovati in elenco.csv")
    args = ap.parse_args()

    sito = {}
    for nome in INDICI:
        try:
            sito.update(voci_indice(nome))
        except Exception as e:
            print(f"AVVISO: indice {nome} non leggibile ({e})")
        time.sleep(0.5)
    print(f"{len(sito)} canti trovati negli indici del sito")
    if not sito:
        sys.exit("Nessun canto letto dal sito: struttura cambiata o sito non raggiungibile")

    righe = leggi_csv(Path(args.elenco))
    applicati, da_verificare = [], []
    for r in righe:
        if r.get("url_spartito"):
            continue
        k = chiave(r["titolo"])
        migliore = max(sito.items(), key=lambda kv: difflib.SequenceMatcher(None, k, chiave(kv[1])).ratio())
        rapporto = difflib.SequenceMatcher(None, k, chiave(migliore[1])).ratio()
        if rapporto < SOGLIA_VERIFICA:
            continue
        stem, titolo_sito = migliore
        if rapporto >= SOGLIA_AUTO:
            time.sleep(0.3)
            url = trova_pdf(stem)
            if url:
                r["url_spartito"] = url
                applicati.append((r["titolo"], titolo_sito, r["url_spartito"]))
            else:
                da_verificare.append((r["titolo"], titolo_sito, "PDF non trovato"))
        else:
            da_verificare.append((r["titolo"], titolo_sito, f"{rapporto:.2f}"))

    print(f"\nCollegati ({len(applicati)}):")
    for t, s, u in applicati:
        print(f"  {t}  ->  {s}  {u}")
    print(f"\nDa verificare a mano, NON applicati ({len(da_verificare)}):")
    for t, s, nota in da_verificare:
        print(f"  {t}  ~  {s}  [{nota}]")

    if args.applica and applicati:
        with open(args.elenco, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLONNE, delimiter=";", restval="")
            w.writeheader()
            w.writerows([{k: r.get(k, "") for k in COLONNE} for r in righe])
        print(f"\nScritti {len(applicati)} link in {args.elenco}")
    elif applicati:
        print("\n(prova: aggiungi --applica per scrivere i link)")


if __name__ == "__main__":
    main()
