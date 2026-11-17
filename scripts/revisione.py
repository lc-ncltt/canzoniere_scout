#!/usr/bin/env python3
"""Revisione dei testi, un canto alla volta, nel browser (solo in locale).

    python scripts/revisione.py            apre http://127.0.0.1:8765

A sinistra il testo (ChordPro) da correggere, a destra l'anteprima come nel libro stampato
(senza accordi, ritornello in grassetto, ripetizioni in "Rit."). Salva direttamente in testi/<slug>.cho.
  Ctrl+Invio   salva, segna come rivisto (toglie "# DA RIVEDERE" e "# VERIFICA") e passa al successivo
  Ctrl+S       salva senza segnare come rivisto
  Alt+→ / Alt+←  canto successivo / precedente (senza salvare)
Lo stato della revisione e' in data/revisione.json. L'ordine e' quello del libro (data/canti.json):
dopo la revisione rilancia build_canti.py, compila e sync_pages.py come al solito.
"""
import json
import re
import sys
import threading
import webbrowser
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import CANTI_PATH, ROOT, parse_chordpro
from generate_latex import ritornelli, senza_accordi
from build_canti import slug

TESTI = ROOT / "testi"
STATO = ROOT / "data" / "revisione.json"
PORTA = 8765
_SLUG_OK = re.compile(r"^[a-z0-9-]+$")
_NOTE_DA_TOGLIERE = re.compile(r"^#\s*(DA RIVEDERE|VERIFICA)\b.*$", re.I | re.M)
_NOTA = r"(?:DO|RE|MI|FA|SOL|LA|SI)"
_RIGA_ACCORDI_IT = re.compile(rf"^(?:\s*{_NOTA}(?:\s?[#b])?(?:-|m|7|\d|sus|dim|\+)*\s*)+$")


def carica_stato():
    try:
        return json.loads(STATO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salva_stato(stato):
    STATO.write_text(json.dumps(stato, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")


def avvisi(testo):
    """Controlli veloci su cose che di solito sono errori di importazione."""
    out = []
    for n, r in enumerate(testo.splitlines(), 1):
        s = r.strip()
        if not s or s.startswith("#"):
            continue
        if _RIGA_ACCORDI_IT.match(s) or re.search(rf"\b{_NOTA}\s?[#b-]?\d?\b.*\b{_NOTA}\b", s) and s.isupper():
            out.append(f"riga {n}: sembra una riga di accordi scritta come testo")
        if re.search(r"[<>]\s*Indice", s):
            out.append(f"riga {n}: residuo di pagina web")
        if re.search(r"\bRIT\b", s) and not s.upper().startswith("RIT"):
            out.append(f"riga {n}: 'RIT' dentro il testo")
        if r.count("[") != r.count("]"):
            out.append(f"riga {n}: parentesi [ ] non bilanciate")
    if "{soc}" in testo and testo.count("{soc}") != testo.count("{eoc}"):
        out.append("{soc} e {eoc} non appaiati")
    if re.search(r"(?im)^#\s*VERIFICA", testo):
        out.insert(0, "VERIFICA: controlla che sia proprio questo canto (titolo diverso nella fonte)")
    return out


def anteprima(testo, accordi=False):
    """HTML con le stesse regole del libro (generate_latex.py)."""
    elementi = parse_chordpro(testo)
    if not accordi:
        elementi = senza_accordi(elementi)
    elementi = ritornelli(elementi)
    html, strofa, ritornello = [], [], False

    def chiudi():
        if strofa:
            html.append('<div class="strofa">' + "".join(strofa) + "</div>")
            strofa.clear()

    for el in elementi:
        if el[0] == "vuota":
            chiudi()
        elif el[0] == "rit":
            strofa.append('<div class="riga rit">Rit.</div>')
        elif el[0] == "commento":
            strofa.append(f'<div class="nota">{escape(el[1])}</div>')
        else:
            pezzi = []
            for a, t in el[1]:
                if a and accordi:
                    pezzi.append(f'<span class="ch" data-ch="{escape(a)}">{escape(t) or "&nbsp;"}</span>')
                else:
                    pezzi.append(escape(t))
            classe = "riga ritornello" if el[2] else "riga"
            strofa.append(f'<div class="{classe}">{"".join(pezzi) or "&nbsp;"}</div>')
    chiudi()
    return "".join(html)


def elenco():
    stato = carica_stato()
    out = []
    for c in sorted(json.loads(CANTI_PATH.read_text(encoding="utf-8")), key=lambda c: c["id"]):
        s = slug(c["titolo"])
        f = TESTI / f"{s}.cho"
        testo = f.read_text(encoding="utf-8") if f.exists() else ""
        if s in stato:
            st = "rivisto"
        elif re.search(r"(?im)^#\s*VERIFICA", testo):
            st = "verifica"
        elif re.search(r"(?im)^#\s*DA RIVEDERE", testo):
            st = "bozza"
        else:
            st = "da rivedere"
        out.append({"id": c["id"], "titolo": c["titolo"], "slug": s, "stato": st,
                    "sezione": c["categoria"] + (" · " + c["sottosezione"] if c.get("sottosezione") else ""),
                    "branche": c.get("branche", []), "autore": c.get("autore", "")})
    return out


class Gestore(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _risposta(self, corpo, tipo="application/json", codice=200):
        dati = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(codice)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(dati)))
        self.end_headers()
        self.wfile.write(dati)

    def _json(self, oggetto, codice=200):
        self._risposta(json.dumps(oggetto, ensure_ascii=False), codice=codice)

    def do_GET(self):
        if self.path == "/":
            return self._risposta(PAGINA, "text/html")
        if self.path == "/api/canti":
            return self._json(elenco())
        m = re.fullmatch(r"/api/testo/([a-z0-9-]+)", self.path)
        if m:
            f = TESTI / f"{m.group(1)}.cho"
            testo = f.read_text(encoding="utf-8") if f.exists() else ""
            return self._json({"testo": testo, "avvisi": avvisi(testo)})
        self._json({"errore": "non trovato"}, 404)

    def do_POST(self):
        dati = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/anteprima":
            testo = dati.get("testo", "")
            return self._json({"html": anteprima(testo, bool(dati.get("accordi"))), "avvisi": avvisi(testo)})
        if self.path == "/api/salva":
            s = dati.get("slug", "")
            if not _SLUG_OK.match(s) or not (TESTI / f"{s}.cho").exists():
                return self._json({"errore": "canto sconosciuto"}, 400)
            testo = dati.get("testo", "").replace("\r\n", "\n")
            stato = carica_stato()
            if dati.get("rivisto"):
                testo = _NOTE_DA_TOGLIERE.sub("", testo)
                testo = re.sub(r"\A\n+", "", testo)
                stato[s] = str(date.today())
            elif dati.get("rivisto") is False:
                stato.pop(s, None)
            testo = testo.rstrip() + "\n" if testo.strip() else ""
            (TESTI / f"{s}.cho").write_text(testo, encoding="utf-8", newline="\n")
            salva_stato(stato)
            return self._json({"ok": True, "testo": testo})
        self._json({"errore": "non trovato"}, 404)


PAGINA = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Revisione canti</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a66;--line:#dddad3;--ok:#3f9a47;--warn:#c47f17;--bad:#c0392b;--acc:#2f5d8a}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink);height:100vh;display:flex;flex-direction:column}
header{display:flex;gap:12px;align-items:center;padding:8px 14px;border-bottom:1px solid var(--line);background:var(--card);flex-wrap:wrap}
header h1{font-size:15px;margin:0 8px 0 0}
.barra{flex:1;min-width:160px;height:8px;background:var(--line);border-radius:4px;overflow:hidden}.barra i{display:block;height:100%;background:var(--ok)}
select,button{font:inherit;padding:5px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);cursor:pointer}
button.primario{background:var(--ok);color:#fff;border-color:var(--ok)}button.pericolo{color:var(--bad)}
main{flex:1;display:grid;grid-template-columns:260px 1fr 1fr;min-height:0}
#lista{overflow:auto;border-right:1px solid var(--line);background:var(--card)}
#lista div{padding:4px 10px;cursor:pointer;display:flex;gap:6px;align-items:baseline;border-bottom:1px solid #f0eee9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#lista div.att{background:#e8eef5}#lista .n{color:var(--mute);width:2.4em;text-align:right;flex:none}
.pt{width:8px;height:8px;border-radius:50%;flex:none;display:inline-block}.rivisto{background:var(--ok)}.verifica{background:var(--bad)}.bozza{background:var(--warn)}.da-rivedere{background:#bbb}
section{display:flex;flex-direction:column;min-height:0;padding:10px 14px;gap:8px}
#testa{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
#titolo{font-size:18px;font-weight:700}#info{color:var(--mute);font-size:12px}
textarea{flex:1;width:100%;font:13px/1.5 Consolas,monospace;padding:10px;border:1px solid var(--line);border-radius:6px;resize:none;background:var(--card);color:var(--ink)}
#avvisi{font-size:12px;color:var(--bad);min-height:1em}#avvisi div:first-child{font-weight:600}
#anteprima{flex:1;overflow:auto;background:#fff;border:1px solid var(--line);border-radius:6px;padding:14px 18px;font:15px/1.35 Georgia,'Libertinus Serif',serif;color:#111}
.strofa{margin-bottom:.7em}.riga{padding-left:3mm;text-indent:-3mm}.ritornello,.rit{font-weight:700;margin-left:3mm}.nota{font-style:italic;color:#777;font-size:13px}
.ch{position:relative;display:inline-block;padding-top:1em}.ch::before{content:attr(data-ch);position:absolute;top:0;left:0;font:bold 11px system-ui;color:var(--acc)}
.azioni{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.tasti{color:var(--mute);font-size:12px}
#msg{font-size:12px;color:var(--ok)}
</style></head><body>
<header><h1>Revisione canti</h1><span id="conta"></span><div class="barra"><i id="prog"></i></div>
<label>Mostra <select id="filtro"><option value="tutti">tutti</option><option value="non">non rivisti</option><option value="verifica">da verificare</option></select></label>
<label><input type="checkbox" id="accordi"> accordi nell'anteprima</label></header>
<main><div id="lista"></div>
<section><div id="testa"><div><div id="titolo"></div><div id="info"></div></div></div>
<textarea id="testo" spellcheck="true" lang="it"></textarea><div id="avvisi"></div>
<div class="azioni"><button class="primario" id="ok">Salva e rivisto ▶</button><button id="salva">Salva</button><button id="prec">◀</button><button id="succ">▶</button>
<button id="nonrivisto">Segna non rivisto</button><span id="msg"></span></div>
<div class="tasti">Ctrl+Invio salva e passa al successivo · Ctrl+S salva · Alt+→ / Alt+← senza salvare · {soc}…{eoc} = ritornello · [Do] = accordo</div></section>
<section><div id="info2" style="color:var(--mute);font-size:12px">Anteprima come nel libro (senza accordi, ritornello in grassetto, ripetizioni in "Rit.")</div><div id="anteprima"></div></section></main>
<script>
let canti=[],att=-1,orig="",timer=null;
const $=id=>document.getElementById(id);
async function j(u,b){const r=await fetch(u,b?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)}:{});return r.json()}
function visibili(){const f=$("filtro").value;return canti.map((c,i)=>i).filter(i=>f=="tutti"||(f=="non"&&canti[i].stato!="rivisto")||(f=="verifica"&&canti[i].stato=="verifica"))}
function disegnaLista(){const v=visibili();$("lista").innerHTML=v.map(i=>{const c=canti[i];return `<div data-i="${i}" class="${i==att?'att':''}"><span class="pt ${c.stato.replace(' ','-')}"></span><span class="n">${c.id}</span>${c.titolo.replace(/</g,'&lt;')}</div>`}).join("");
 const r=canti.filter(c=>c.stato=="rivisto").length;$("conta").textContent=`${r} / ${canti.length} rivisti`;$("prog").style.width=(100*r/canti.length)+"%";
 const el=$("lista").querySelector(".att");if(el)el.scrollIntoView({block:"nearest"})}
async function apri(i){if(i<0||i>=canti.length)return;if(modificato()&&!confirm("Ci sono modifiche non salvate: le perdi?"))return;
 att=i;const c=canti[i];const d=await j("/api/testo/"+c.slug);orig=d.testo;$("testo").value=d.testo;
 $("titolo").textContent=c.id+"  "+c.titolo;$("info").textContent=[c.sezione,(c.branche||[]).join("/"),c.autore,"stato: "+c.stato].filter(Boolean).join(" · ");
 localStorage.setItem("ultimo",c.slug);disegnaLista();aggiorna();$("testo").focus()}
function modificato(){return att>=0&&$("testo").value!==orig}
async function aggiorna(){const d=await j("/api/anteprima",{testo:$("testo").value,accordi:$("accordi").checked});$("anteprima").innerHTML=d.html||"<i>(vuoto: il canto esce dal libro)</i>";$("avvisi").innerHTML=d.avvisi.map(a=>`<div>⚠ ${a.replace(/</g,'&lt;')}</div>`).join("")}
function prossimo(dir){const v=visibili();let k=v.indexOf(att);if(k<0){k=v.findIndex(i=>i>att)-(dir>0?1:0)}const n=v[k+dir];if(n!==undefined)apri(n)}
async function salva(rivisto,avanti){const c=canti[att];const d=await j("/api/salva",{slug:c.slug,testo:$("testo").value,rivisto});if(d.errore){alert(d.errore);return}
 orig=d.testo;$("testo").value=d.testo;if(rivisto===true)c.stato="rivisto";else if(rivisto===false)c.stato="da rivedere";
 $("msg").textContent="salvato "+new Date().toLocaleTimeString();disegnaLista();if(avanti)prossimo(1);else aggiorna()}
$("testo").addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(aggiorna,250)});
$("accordi").onchange=aggiorna;$("filtro").onchange=disegnaLista;
$("lista").onclick=e=>{const d=e.target.closest("[data-i]");if(d)apri(+d.dataset.i)};
$("ok").onclick=()=>salva(true,true);$("salva").onclick=()=>salva(null,false);$("nonrivisto").onclick=()=>salva(false,false);
$("prec").onclick=()=>prossimo(-1);$("succ").onclick=()=>prossimo(1);
document.addEventListener("keydown",e=>{if(e.ctrlKey&&e.key=="Enter"){e.preventDefault();salva(true,true)}
 else if(e.ctrlKey&&(e.key=="s"||e.key=="S")){e.preventDefault();salva(null,false)}
 else if(e.altKey&&e.key=="ArrowRight"){e.preventDefault();prossimo(1)}else if(e.altKey&&e.key=="ArrowLeft"){e.preventDefault();prossimo(-1)}});
window.addEventListener("beforeunload",e=>{if(modificato()){e.preventDefault();e.returnValue=""}});
(async()=>{canti=await j("/api/canti");const u=localStorage.getItem("ultimo");let i=canti.findIndex(c=>c.slug==u);
 if(i<0)i=canti.findIndex(c=>c.stato!="rivisto");apri(Math.max(i,0))})();
</script></body></html>"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORTA), Gestore)
    url = f"http://127.0.0.1:{PORTA}/"
    print(f"Revisione aperta su {url}  (Ctrl+C per chiudere)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiuso. Ricorda: build_canti.py, compilazione, sync_pages.py, commit.")


if __name__ == "__main__":
    main()
