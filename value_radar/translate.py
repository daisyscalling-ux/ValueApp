"""
translate.py — optionale Uebersetzung (Englisch -> Deutsch) fuer News.

Nutzt deep-translator (Google-Backend, kostenlos, kein Key). Ist das Paket
nicht installiert oder schlaegt ein Aufruf fehl, wird der Originaltext
zurueckgegeben (sauberes Degradieren).

Installation:  pip install deep-translator
"""
from __future__ import annotations

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


def available() -> bool:
    return GoogleTranslator is not None


def translate_text(text, target: str = "de") -> str:
    if not text or GoogleTranslator is None:
        return text or ""
    try:
        t = text if len(text) <= 4900 else text[:4900]
        return GoogleTranslator(source="auto", target=target).translate(t) or text
    except Exception:
        return text
