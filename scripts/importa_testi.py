#!/usr/bin/env python3
"""Scarica testi (e accordi, se presenti) da pagine web e li salva come BOZZE in testi/<titolo>.cho.

  data/fonti.csv     titolo;url   (una riga per canto; il titolo deve coincidere con elenco.csv)

Per ogni riga senza testo: scarica la pagina, prende il blocco <pre> piu' lungo (tipico dei siti con
accordi sopra il testo) oppure il testo principale della pagina (richiede `pip install trafilatura`),
converte gli accordi in ChordPro e scrive il file con in testa "# DA RIVEDERE".
Educato col sito: rispetta robots.txt, attende tra una richiesta e l'altra e si FERMA al primo
403/429 (non insiste e non aggira i blocchi). Il risultato e' una bozza da controllare a occhio.
"""
import argparse
import html
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from accordi import da_accordi_sopra
from build_canti import leggi_csv, slug
from common import ROOT

UA = "canzoniere-scout-bot (progetto privato senza scopo di lucro)"


class _Pre(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocchi, self._dentro, self._buf = [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self._dentro += 1
        elif tag == "br" and self._dentro:
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag == "pre" and self._dentro:
            self._dentro -= 1
            if not self._dentro:
                self.blocchi.append("".join(self._buf))
                self._buf = []

    def handle_data(self, data):
        if self._dentro:
            self._buf.append(data)


def estrai_testo(pagina):
    p = _Pre()
    p.feed(pagina)
    if p.blocchi:
        migliore = max(p.blocchi, key=len)
        if len(migliore.strip().splitlines()) >= 4:
            return migliore
    try:
        import trafilatura
    except ImportError:
        sys.exit("Questa pagina non ha un blocco <pre>: installa `pip install trafilatura` per estrarne il testo")
    return trafilatura.extract(pagina, favor_recall=True, include_comments=False, include_tables=False) or ""


def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        grezzo = r.read()
        codifica = r.headers.get_content_charset() or "utf-8"
    return grezzo.decode(codifica, "replace")


_robots = {}


def permesso(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None  # robots.txt irraggiungibile: nessuna restrizione dichiarata
        _robots[host] = rp
    return _robots[host] is None or _robots[host].can_fetch(UA, url)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonti", default=str(ROOT / "data" / "fonti.csv"))
    ap.add_argument("--testi", default=str(ROOT / "testi"))
    ap.add_argument("--attesa", type=float, default=3.0, help="secondi tra una richiesta e l'altra")
    ap.add_argument("--max", type=int, default=50, help="massimo di canti per esecuzione")
    args = ap.parse_args()

    cartella = Path(args.testi)
    cartella.mkdir(exist_ok=True)
    fatti = 0
    for r in leggi_csv(Path(args.fonti)):
        titolo, url = r.get("titolo", ""), r.get("url", "")
        if not titolo or not url:
            continue
        destinazione = cartella / f"{slug(titolo)}.cho"
        if destinazione.exists() and destinazione.read_text(encoding="utf-8").strip():
            continue
        if fatti >= args.max:
            print(f"Raggiunto il massimo di {args.max}: rilancia per continuare")
            break
        if not permesso(url):
            print(f"SALTATO (robots.txt lo vieta): {titolo}  {url}")
            continue
        try:
            pagina = scarica(url)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                sys.exit(f"{url}: HTTP {e.code}, il sito rifiuta le richieste automatiche. Mi fermo.")
            print(f"ERRORE {e.code}: {titolo}  {url}")
            continue
        except Exception as e:
            print(f"ERRORE ({e}): {titolo}  {url}")
            continue

        testo = da_accordi_sopra(html.unescape(estrai_testo(pagina)))
        if len(testo.split()) < 8:
            print(f"TESTO TROPPO CORTO, non salvato: {titolo}  {url}")
        else:
            destinazione.write_text(
                f"# fonte: {url}\n# DA RIVEDERE: controlla testo e accordi, poi cancella questa riga\n{testo}",
                encoding="utf-8", newline="\n")
            fatti += 1
            print(f"ok: {titolo}")
        time.sleep(args.attesa)
    print(f"{fatti} bozze scritte in {cartella}")


if __name__ == "__main__":
    main()
