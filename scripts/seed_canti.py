#!/usr/bin/env python3
"""Crea data/canti.json (e data/meta.json) con un set iniziale di esempio.

Sono usati solo testi di pubblico dominio / tradizionali. Sostituirli con i
propri canti: verificare sempre i diritti dei testi coperti da copyright.
"""
import argparse
import sys

from common import CANTI_PATH, META_PATH, salva_json, valida

ESEMPI = [
    {
        "id": 1,
        "titolo": "Fra' Martino",
        "categoria": "Bivacco",
        "pagina": 1,
        "url_audio": None,
        "url_spartito": None,
        "autore": "Tradizionale",
        "note": "Canone a più voci. Esempio: sostituire.",
        "testo_accordi": (
            "{c: Canone a 2-4 voci}\n"
            "[C]Fra' Mar[G]tino cam[C]panaro,\n"
            "[C]dormi [G]tu? [C]Dormi [G]tu?\n"
            "[G]Suona le cam[C]pane, [G]suona le cam[C]pane,\n"
            "[C]din don [G]dan, [C]din don [G]dan.\n"
        ),
    },
    {
        "id": 2,
        "titolo": "Quel mazzolin di fiori",
        "categoria": "Cammino",
        "pagina": 2,
        "url_audio": None,
        "url_spartito": None,
        "autore": "Tradizionale",
        "note": "Esempio: sostituire.",
        "testo_accordi": (
            "[G]Quel mazzolin di [D]fiori\n"
            "che [D7]vien dalla mon[G]tagna,\n"
            "[G]bada che non si [D]bagni\n"
            "che [D7]lo voglio rega[G]lar.\n"
            "\n"
            "[G]Lo voglio regalare\n"
            "per[D7]ché l'è un bel maz[G]zetto,\n"
            "[G]lo voglio dare al mio mo[D]retto\n"
            "[D7]questa sera quando [G]vien.\n"
        ),
    },
    {
        "id": 3,
        "titolo": "Il Canto degli Italiani",
        "categoria": "Tradizione",
        "pagina": 3,
        "url_audio": None,
        "url_spartito": None,
        "autore": "G. Mameli - M. Novaro (1847)",
        "note": "Pubblico dominio. Esempio: sostituire.",
        "testo_accordi": (
            "[C]Fratelli d'Italia,\n"
            "l'Italia s'è [G]desta,\n"
            "dell'elmo di [C]Scipio\n"
            "s'è cinta la [G]testa.\n"
            "Dov'è la Vit[C]toria?\n"
            "Le porga la [G]chioma,\n"
            "ché schiava di [C]Roma\n"
            "Iddio la cre[G]ò.\n"
            "\n"
            "{soc}\n"
            "[C]Stringiamci a coorte,\n"
            "siam [G]pronti alla morte,\n"
            "siam [C]pronti alla morte,\n"
            "l'Italia chia[G]mò. [C]Sì!\n"
            "{eoc}\n"
        ),
    },
    {
        "id": 4,
        "titolo": "Salve Regina",
        "categoria": "Liturgici",
        "pagina": 4,
        "url_audio": None,
        "url_spartito": None,
        "autore": "Antifona mariana (gregoriano)",
        "note": "Pubblico dominio. Esempio: sostituire.",
        "testo_accordi": (
            "[Am]Salve, Re[G]gina, mater miseri[Am]cordiae,\n"
            "vita, dul[F]cedo et spes no[E]stra, sal[Am]ve.\n"
            "Ad te cla[G]mamus, ex[Am]sules fi[F]lii He[E]vae.\n"
        ),
    },
]

META = {
    "titolo": "Canzoniere",
    "sottotitolo": "Clan - Gruppo Scout",
    "dedica": "Per la tua Partenza: che questi canti ti accompagnino sempre.",
    "anno": "2026",
    "url": "https://NOMEUTENTE.github.io/canzoniere/",
    "nota": "",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="sovrascrive i file esistenti")
    args = ap.parse_args()

    errori, avvisi = valida(ESEMPI)
    if errori:
        sys.exit("\n".join(errori))
    for a in avvisi:
        print("AVVISO:", a)

    for percorso, dati in ((CANTI_PATH, ESEMPI), (META_PATH, META)):
        if percorso.exists() and not args.force:
            print(f"{percorso} esiste già (usa --force per sovrascrivere)")
            continue
        percorso.parent.mkdir(parents=True, exist_ok=True)
        salva_json(percorso, dati)
        print(f"Scritto {percorso}")


if __name__ == "__main__":
    main()
