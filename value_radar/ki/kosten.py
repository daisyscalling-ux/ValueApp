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
KI_BUDGET_USD = 1.00


def lies(pfad):
 p = Path(pfad)
 return json.loads(p.read_text(encoding='utf8')) if p.exists() else {'schema': 1, 'monate': {}}


def monat_usd(pfad, monat):
 return lies(pfad)['monate'].get(monat, {}).get('usd', 0.0)


def passt(pfad, monat, input_tokens, max_tokens):
 """Höchstschätzung des Aufrufs gegen das Monatsbudget."""
 return monat_usd(pfad, monat) + input_tokens * PREIS_EIN + max_tokens * PREIS_AUS <= KI_BUDGET_USD


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
