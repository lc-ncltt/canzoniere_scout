#!/usr/bin/env python3
"""Converte testo con gli accordi sulla riga sopra (formato comune sui siti) in ChordPro.

    Am       G
    Quel mazzolin di fiori      ->   [Am]Quel mazzolin di [G]fiori

Uso: python scripts/accordi.py file.txt   (stampa il ChordPro)   oppure   ... < file.txt
Come modulo: da_accordi_sopra(testo) -> str
"""
import re
import sys

_NOTA = r"(?:[A-G]|Do|Re|Mi|Fa|Sol|La|Si)[#b]?"
_ACCORDO = re.compile(rf"^{_NOTA}(?:m|min|maj|M|dim|aug|sus|add)?\d*(?:[+\-]?\(?\d*[#b]?\d*\)?)*(?:/{_NOTA})?$")


def _e_riga_accordi(riga):
    token = riga.split()
    return bool(token) and all(_ACCORDO.match(t) for t in token)


def _inserisci(testo, accordi):
    """accordi: [(colonna, nome)]. Inserisce [nome] alla colonna, da destra a sinistra."""
    testo = testo.rstrip().ljust(max((c for c, _ in accordi), default=0))
    for colonna, nome in sorted(accordi, reverse=True):
        testo = testo[:colonna] + f"[{nome}]" + testo[colonna:]
    return testo.rstrip()


def da_accordi_sopra(testo):
    righe = testo.expandtabs(4).replace("\r", "").split("\n")
    out, i = [], 0
    while i < len(righe):
        riga = righe[i]
        if _e_riga_accordi(riga):
            accordi = [(m.start(), m.group()) for m in re.finditer(r"\S+", riga)]
            succ = righe[i + 1] if i + 1 < len(righe) else ""
            if succ.strip() and not _e_riga_accordi(succ):
                out.append(_inserisci(succ, accordi))
                i += 2
                continue
            out.append(" ".join(f"[{n}]" for _, n in accordi))  # riga di soli accordi (intro)
        else:
            out.append(riga.rstrip())
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


if __name__ == "__main__":
    sorgente = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    sys.stdout.write(da_accordi_sopra(sorgente))
