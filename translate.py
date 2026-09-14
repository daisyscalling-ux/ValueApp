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
    cached = _CACHE.get((text, target))
    if cached is not None:
        return cached
    try:
        t = text if len(text) <= 4900 else text[:4900]
        out = GoogleTranslator(source="auto", target=target).translate(t) or text
    except Exception:
        out = text
    _CACHE[(text, target)] = out
    return out


_CACHE = {}


def translate_batch(texts, target: str = "de") -> list:
    """Mehrere Texte in EINEM Aufruf uebersetzen (statt je Text eine eigene
    Netzwerkanfrage). Bereits uebersetzte Texte kommen aus dem Cache. Das ist der
    grosse Hebel: 30 einzelne Uebersetzungsaufrufe -> ein bis zwei Batch-Aufrufe."""
    texts = list(texts)
    if GoogleTranslator is None:
        return texts
    out = [None] * len(texts)
    todo, todo_idx = [], []
    for i, t in enumerate(texts):
        if not t:
            out[i] = t or ""
        elif (t, target) in _CACHE:
            out[i] = _CACHE[(t, target)]
        else:
            todo.append(t if len(t) <= 4900 else t[:4900])
            todo_idx.append(i)
    if todo:
        try:
            res = GoogleTranslator(source="auto", target=target).translate_batch(todo)
        except Exception:
            res = None
        for j, i in enumerate(todo_idx):
            val = (res[j] if res and j < len(res) and res[j] else texts[i])
            out[i] = val
            _CACHE[(texts[i], target)] = val
    return out
