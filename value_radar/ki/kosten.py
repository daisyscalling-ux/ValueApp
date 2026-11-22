"""Gemeinsames Kostenprotokoll aller KI-Funktionen (seit 22.11.2026, Testmonat des Nutzers).

daten/ki_kosten.json je Kalendermonat: usd, laeufe, tokens und je Funktion usd/laeufe. Gleiches Format wie
nachrichten_trends/ki_einordnung.py. Monatsbudget KI_BUDGET_USD über alle Funktionen; die Ausgabegrenze in der
Anthropic Console (2 $) greift zusätzlich. Preise: Claude Haiku 5.5 bei Prompts bis 100.000 Tokens.
"""
import json
from pathlib import Path

MODELL = 'claude-haiku-5-5'
PREIS_EIN, PREIS_AUS = 0.10 / 1e6, 0.50 / 1e6
PROMPT_MAX_TOKENS = 90_000
# Feste Anteile je Funktion (seit 22.11.2026, Entscheidungen des Nutzers): keine Funktion verdrängt die anderen.
# News-Briefing (dreimal täglich, ersetzt Themen des Tages) 0,70 $; zusammen 2,10 $, dazu 0,30 $ für die Fair-Value-Erklärung
# in Cloudflare = 2,40 $ unter der Console-Grenze von 3 $ (vom Nutzer am 22.11.2026 erhöht). KI-Portfolio seit 22.11. zweistufig: 0,55 $.
ANTEILE = {'risiko_ereignisse': 0.90, 'news_briefing': 0.70, 'ki_portfolio': 0.55, 'trends_einordnung': 0.10}
KI_BUDGET_USD = round(sum(ANTEILE.values()), 2)


def lies(pfad):
 p = Path(pfad)
 return json.loads(p.read_text(encoding='utf8')) if p.exists() else {'schema': 1, 'monate': {}}


def monat_usd(pfad, monat):
 return lies(pfad)['monate'].get(monat, {}).get('usd', 0.0)


def funktion_usd(pfad, monat, funktion):
 return lies(pfad)['monate'].get(monat, {}).get('funktionen', {}).get(funktion, {}).get('usd', 0.0)


def passt(pfad, monat, input_tokens, max_tokens, funktion):
 """Höchstschätzung des Aufrufs gegen den Anteil der Funktion und gegen die Summe. Unbekannte Funktion: kein Budget."""
 hoechstens = input_tokens * PREIS_EIN + max_tokens * PREIS_AUS
 anteil = ANTEILE.get(funktion)
 if anteil is None:
  return False
 return funktion_usd(pfad, monat, funktion) + hoechstens <= anteil and monat_usd(pfad, monat) + hoechstens <= KI_BUDGET_USD


def buchen(pfad, monat, funktion, tokens_ein, tokens_aus):
 usd = tokens_ein * PREIS_EIN + tokens_aus * PREIS_AUS
 d = lies(pfad)
 m = d['monate'].get(monat, {'usd': 0.0, 'laeufe': 0, 'funktionen': {}, 'tokens': {'ein': 0, 'aus': 0}})
 f = m.get('funktionen', {}).get(funktion, {'usd': 0.0, 'laeufe': 0})
 t = m.get('tokens', {'ein': 0, 'aus': 0})
 d['monate'][monat] = {'usd': round(m['usd'] + usd, 6), 'laeufe': m['laeufe'] + 1,
                       'funktionen': {**m.get('funktionen', {}), funktion: {'usd': round(f['usd'] + usd, 6), 'laeufe': f['laeufe'] + 1}},
                       'tokens': {'ein': t['ein'] + tokens_ein, 'aus': t['aus'] + tokens_aus}}
 p = Path(pfad); p.parent.mkdir(parents=True, exist_ok=True)
 tmp = p.with_suffix('.tmp'); tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf8'); tmp.replace(p)
 return usd
