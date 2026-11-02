# Canzoniere di Clan

30 copie stampate (A5 orizzontale, rilegatura a viti cieche) + una web app statica su GitHub Pages,
raggiungibile da un unico QR code sull'ultima pagina. Si lavora su due cose: l'elenco (`data/elenco.csv`) e un file di testo per canto (`testi/*.cho`).

```
data/elenco.csv          elenco canti: titolo, sezione, branche, intensità (Excel/Fogli Google)
testi/*.cho              testo + accordi di ogni canto (ChordPro)
data/canti.json          GENERATO da build_canti.py (schema: canti.schema.json)
latex/front/*.tex        pagine iniziali: dedica, come usare, fuoco di bivacco, cantare insieme
data/meta.json           titolo, dedica, anno, URL della web app
scripts/                 Python (solo libreria standard, tranne `segno` per il QR)
latex/template.tex       impaginazione A5 landscape
webapp/                  HTML + CSS + JS vanilla, nessuna dipendenza
.github/workflows/       pubblicazione automatica su GitHub Pages
build/                   (generato) .tex, .pdf, QR      _site/  (generato) sito pubblicato
```

## Flusso di lavoro

```bash
pip install segno
python scripts/build_canti.py           # elenco.csv + testi/*.cho -> data/canti.json (e report di cosa manca)
python scripts/validate_canti.py        # convalida (aggiungi --check-urls per testare i link)
python scripts/make_qr.py               # build/qr.pdf (+ svg, eps, png) con livello di correzione H
python scripts/generate_latex.py        # build/canzoniere.tex
cd build && pdflatex canzoniere.tex && pdflatex canzoniere.tex && cd ..   # 2 passate: gli indici usano \pageref
python scripts/sync_pages.py            # copia nel JSON le pagine realmente stampate
python scripts/build_site.py --serve    # anteprima web app su http://localhost:8000
```

Con `latexmk`: `latexmk -pdf -outdir=build build/canzoniere.tex`.

### Importare l'elenco completo

1. Apri `data/elenco.csv` in Excel/Fogli Google (separatore `;`) e incolla i titoli. Colonne:
   `titolo;categoria;branche;intensita;autore;note;url_audio;url_spartito`.
   `categoria` è una delle sezioni di `data/meta.json`; `branche` sono sigle separate da `/`
   (`LC/EG/RS`, vuoto = per tutti); `intensita` va da 1 (raccolto) a 5 (esplosivo).
   Se all'inizio hai solo i titoli: `python scripts/build_canti.py --default-sezione Tradizione`.
2. `python scripts/build_canti.py --crea-testi` crea in `testi/` un file `.cho` vuoto per ogni canto
   (nome = titolo in minuscolo con trattini). Incolla lì testo e accordi.
3. Rilancia `build_canti.py`: ordina per sezione, poi intensità, poi titolo; assegna i numeri.
   **Un canto entra in libro e web app solo quando ha un file `testi/<titolo>.cho` con del testo**:
   gli altri restano nell'elenco (la lista di cose da fare) e il report ne indica il numero per sezione.
   I numeri cambiano finché si aggiungono canti: vanno considerati definitivi solo a elenco chiuso.
   `--includi-senza-testo` li include con un segnaposto.

### Scaricare testi da internet (bozze)

1. Compila `data/fonti.csv` (`titolo;url`): per ogni canto l'indirizzo della pagina con testo e accordi.
2. `python scripts/importa_testi.py --max 30` scarica le pagine, converte gli accordi (anche quelli scritti
   sopra il testo) in ChordPro e crea `testi/<titolo>.cho` con in testa `# DA RIVEDERE`.
   Rispetta robots.txt, aspetta 3 s tra le richieste e si ferma al primo 403/429.
   Se la pagina non ha un blocco `<pre>`, serve `pip install trafilatura`.
3. Controlla ogni bozza (accordi spostati, strofe mancanti, pubblicità), poi cancella la riga `# DA RIVEDERE`.
   `build_canti.py` ti dice quante bozze restano da rivedere. Le righe `#` non finiscono mai nel libro né nel sito.
4. Per un testo incollato a mano con gli accordi sopra: `python scripts/accordi.py incolla.txt > testi/titolo.cho`.

Per i testi coperti da copyright usa fonti che puoi legittimamente copiare (i tuoi libri, canzonieri
della tua associazione); online conviene cercare solo i **link** a audio e spartiti per le colonne
`url_audio` e `url_spartito`.

### Formato di `testo_accordi` (ChordPro)

```
[Am]Parole con l'ac[G]cordo sopra la sillaba
{soc}            ritornello (corsivo con barra)
{eoc}
{c: Canone a 2 voci}   nota in corsivo
(riga vuota)     separa le strofe
```

Sono accettati anche accordi all'italiana (`[Do]`, `[Sol7]`, `[Lam]`).

## Overleaf + GitHub

L'output LaTeX vive in `overleaf/` (`canzoniere.tex`, `qr.pdf`) ed è **tracciato da git**. Ad ogni push su
`main` che tocca `data/`, `scripts/` o `latex/`, l'Action `latex.yml` rigenera `overleaf/` e lo committa.

Setup (una volta): in Overleaf *New Project → Import from GitHub* → scegli il repository →
*Menu → Settings → Main document* = `overleaf/canzoniere.tex`, compilatore pdfLaTeX.

Uso: modifica i dati (su GitHub o in locale) → push → attendi l'Action (~30 s) →
in Overleaf *Menu → Sync → Pull GitHub changes*.

**Limiti noti:** la sincronizzazione Overleaf↔GitHub non è in tempo reale: il pull/push è un
pulsante manuale in Overleaf (nemmeno col piano a pagamento ci sono webhook automatici).
`overleaf/canzoniere.tex` è un file generato: le modifiche fatte lì a mano vengono sovrascritte.
Per cambiare l'impaginazione modifica `latex/template.tex` (anche da Overleaf), poi *Push to GitHub*:
l'Action rigenera il `.tex`.

Per `sync_pages.py` scarica da Overleaf (*Menu → Download → Source* o *Logs and output files*) il file
`.aux` e lancia `python scripts/sync_pages.py --aux percorso/canzoniere.aux`.

## Scelte di impaginazione

- **Un canto per pagina, a due colonne.** Ogni canto parte su una pagina nuova, così il numero di pagina è
  stabile e il canto si trova dal numero stampato accanto al titolo. Se vedi troppo spazio vuoto, la
  variante "più canti per facciata" va fatta rimuovendo `\clearpage` da `\cantotesta` (ma allora la
  pagina di un canto va sempre riletta con `sync_pages.py`).
- **Margini.** I parametri richiesti (`left=15mm`, `bindingoffset=15mm`) sommati lasciano **30 mm** sul lato
  rilegato, 15 mm sull'altro. Se i fori risultano troppo lontani dal testo, riduci `left` o `bindingoffset`
  in `latex/template.tex`. Il documento è `twoside`: l'offset si alterna correttamente fronte/retro
  (stampa fronte-retro con ribaltamento sul **lato corto**).
- **Pagine pari.** Con la rilegatura a viti conviene un numero totale di pagine pari; controlla il PDF.
- **Prova prima di stampare 30 copie:** stampa una copia sola e forala.

## Spartiti PDF

Ogni canto con testo ha un PDF generato da `scripts/genera_pdf.py` (A4, nero su bianco, accordi sopra il testo, ritornello in corsivo, 1 o 2 colonne). `build_site.py` li crea in `_site/pdf/<id>.pdf` e la web app li offre con "Scarica PDF". Serve `pip install reportlab`. Un vero rigo musicale non si ricava dagli accordi: se in futuro vuoi le note, vanno fornite a parte.

## Web app

- Cerca per numero (`12`) o per titolo; filtri per categoria; link diretti `#/12`.
- `<audio preload="none">`: nessun byte di audio viene scaricato finché non premi play.
- Scarica PDF dello spartito (testo + accordi), accordi attivabili, dimensione testo, schermo sempre acceso, modo notte
  (segue il telefono, e si può forzare col pulsante).
- Un service worker salva testi e accordi: dopo la prima visita funzionano anche senza campo.
  L'audio e i PDF restano online.
- Zero dipendenze, nessun build step: i file in `webapp/` sono quelli che girano.

## Pubblicazione su GitHub Pages

1. Crea un repository **pubblico** (es. `canzoniere`) e fai push su `main`.
2. *Settings → Pages → Build and deployment → Source: **GitHub Actions***.
3. Ogni push su `main` convalida il JSON e pubblica. Se il JSON è sbagliato, il deploy fallisce e il sito
   online non cambia.
4. L'URL è `https://<utente>.github.io/<repo>/`: scrivilo in `data/meta.json` **prima** di generare il QR.
   Poi non rinominare il repository né l'utente, o il QR stampato smette di funzionare.

## Cose da sapere

- **Link audio/PDF.** Su archive.org usa il link diretto `https://archive.org/download/<id>/<file>.mp3`
  (non la pagina `details`). Solo `https://`. Lancia `validate_canti.py --check-urls` ogni tanto: i link
  esterni sono l'unica parte che può rompersi nel tempo.
- **Diritti.** I canti d'esempio sono tradizionali/pubblico dominio. Testi, accordi e registrazioni di
  brani coperti da copyright restano dei loro autori: per copie regalo non commerciali il rischio è
  basso, ma pubblicarli online su un sito pubblico è un'altra cosa. Valuta cosa mettere nella web app.
- **Manutenzione.** Il sito non ha server né database. Le versioni delle GitHub Actions
  (`actions/*@v4`) prima o poi vanno aggiornate; il sito già pubblicato continua a funzionare comunque.
