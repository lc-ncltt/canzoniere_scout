"""Funzioni condivise: caricamento, validazione e parsing ChordPro dei canti."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANTI_PATH = ROOT / "data" / "canti.json"
META_PATH = ROOT / "data" / "meta.json"

# Ordine di questa lista = ordine dell'indice tematico. Per aggiungere una
# categoria basta aggiungerla qui (la web app la legge dinamicamente dal JSON).
CATEGORIE = ["Cammino", "Liturgici", "Bivacco", "Tradizione"]

OBBLIGATORI = {
    "id": int,
    "titolo": str,
    "categoria": str,
    "pagina": (int, type(None)),
    "url_audio": (str, type(None)),
    "url_spartito": (str, type(None)),
    "testo_accordi": str,
}
OPZIONALI = {"autore": str, "note": str}

_NOTE = r"(?:[A-G]|Do|Re|Mi|Fa|Sol|La|Si)"
_ACCORDO_OK = re.compile(rf"^(?:{_NOTE}[#b]?[A-Za-z0-9#b+\-()/.]*|N\.?C\.?)$")
_DIRETTIVA = re.compile(r"^\{\s*([A-Za-z_]+)\s*(?::\s*(.*?))?\s*\}$")
_ACCORDO = re.compile(r"\[([^\]]*)\]")


def carica_json(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def salva_json(percorso, dati):
    with open(percorso, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
        f.write("\n")


def carica_meta(percorso=META_PATH):
    meta = {
        "titolo": "Canzoniere",
        "sottotitolo": "",
        "dedica": "",
        "anno": "",
        "url": "",
        "nota": "",
    }
    if Path(percorso).exists():
        meta.update(carica_json(percorso))
    return meta


# --------------------------------------------------------------- ChordPro

def segmenti_riga(riga):
    """'[Am]pa[G]role' -> [(None, ''), ('Am', 'pa'), ('G', 'role')] senza i vuoti iniziali."""
    parti = _ACCORDO.split(riga)
    segmenti = []
    if parti[0]:
        segmenti.append((None, parti[0]))
    for i in range(1, len(parti), 2):
        segmenti.append((parti[i].strip(), parti[i + 1]))
    return segmenti


def parse_chordpro(testo):
    """Restituisce una lista di elementi:
    ('riga', segmenti, in_ritornello) | ('vuota',) | ('commento', testo)."""
    out = []
    ritornello = False
    for grezza in testo.splitlines():
        riga = grezza.strip()
        if riga.startswith("#"):
            continue
        if not riga:
            out.append(("vuota",))
            continue
        m = _DIRETTIVA.match(riga)
        if m:
            nome, arg = m.group(1).lower(), (m.group(2) or "").strip()
            if nome in ("soc", "start_of_chorus"):
                ritornello = True
            elif nome in ("eoc", "end_of_chorus"):
                ritornello = False
            elif nome in ("c", "comment", "ci", "comment_italic"):
                out.append(("commento", arg))
            continue
        out.append(("riga", segmenti_riga(riga), ritornello))
    return out


# ------------------------------------------------------------ Validazione

def _controlla_url(valore, campo, et, estensione, errori, avvisi):
    if not valore:
        return
    if not valore.startswith("https://"):
        errori.append(
            f"{et}: {campo} deve iniziare con https:// (un link http viene "
            "bloccato dai browser su una pagina https)"
        )
        return
    if "archive.org/details/" in valore:
        avvisi.append(
            f"{et}: {campo} è una pagina 'details' di archive.org, "
            "serve il link diretto .../download/<id>/<file>"
        )
    elif not valore.split("?")[0].lower().endswith(estensione):
        avvisi.append(f"{et}: {campo} non termina con {estensione}")


def valida(canti):
    """Restituisce (errori, avvisi) per la lista di canti."""
    errori, avvisi = [], []
    if not isinstance(canti, list) or not canti:
        return ["La radice deve essere una lista non vuota di canti."], avvisi

    ids = set()
    pagina_prec = None
    for pos, c in enumerate(canti, 1):
        et = f"canto in posizione {pos}"
        if not isinstance(c, dict):
            errori.append(f"{et}: non è un oggetto JSON")
            continue
        if isinstance(c.get("id"), int):
            et = f"canto {c['id']}"

        for campo, tipo in OBBLIGATORI.items():
            if campo not in c:
                errori.append(f"{et}: manca il campo '{campo}'")
            elif not isinstance(c[campo], tipo) or isinstance(c[campo], bool):
                errori.append(f"{et}: il campo '{campo}' ha tipo errato")
        for campo, tipo in OPZIONALI.items():
            if campo in c and not isinstance(c[campo], tipo):
                errori.append(f"{et}: il campo '{campo}' ha tipo errato")
        for campo in c:
            if campo not in OBBLIGATORI and campo not in OPZIONALI:
                avvisi.append(f"{et}: campo sconosciuto '{campo}'")

        cid = c.get("id")
        if isinstance(cid, int):
            if cid < 1:
                errori.append(f"{et}: id deve essere >= 1")
            if cid in ids:
                errori.append(f"{et}: id duplicato")
            ids.add(cid)

        if isinstance(c.get("titolo"), str) and not c["titolo"].strip():
            errori.append(f"{et}: titolo vuoto")
        if isinstance(c.get("categoria"), str) and c["categoria"] not in CATEGORIE:
            errori.append(
                f"{et}: categoria '{c['categoria']}' non ammessa "
                f"(ammesse: {', '.join(CATEGORIE)}; si estende in scripts/common.py)"
            )

        pagina = c.get("pagina")
        if isinstance(pagina, int) and not isinstance(pagina, bool):
            if pagina < 1:
                errori.append(f"{et}: pagina deve essere >= 1")
            elif pagina_prec is not None and pagina <= pagina_prec:
                avvisi.append(
                    f"{et}: pagina {pagina} non successiva a quella del canto "
                    "precedente (eseguire sync_pages.py dopo la compilazione)"
                )
            if pagina >= 1:
                pagina_prec = pagina

        _controlla_url(c.get("url_audio"), "url_audio", et, ".mp3", errori, avvisi)
        _controlla_url(c.get("url_spartito"), "url_spartito", et, ".pdf", errori, avvisi)

        testo = c.get("testo_accordi")
        if isinstance(testo, str):
            if not testo.strip():
                errori.append(f"{et}: testo_accordi vuoto")
            for n, riga in enumerate(testo.splitlines(), 1):
                if riga.count("[") != riga.count("]") or re.search(r"\[[^\]]*\[", riga):
                    errori.append(f"{et}, riga {n}: parentesi [ ] non bilanciate")
                    continue
                for accordo in _ACCORDO.findall(riga):
                    if not accordo.strip():
                        errori.append(f"{et}, riga {n}: accordo vuoto []")
                    elif not _ACCORDO_OK.match(accordo.strip()):
                        avvisi.append(f"{et}, riga {n}: accordo insolito '{accordo}'")

    if ids:
        mancanti = sorted(set(range(1, max(ids) + 1)) - ids)
        if mancanti:
            avvisi.append(f"numerazione con buchi: mancano gli id {mancanti}")
    return errori, avvisi
