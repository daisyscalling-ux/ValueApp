"""
store.py — einfache lokale Persistenz fuer gespeicherte Portfolios.

Speichert in einer JSON-Datei im Home-Verzeichnis des Nutzers, sodass die
Portfolios Neustarts der App ueberleben. Jedes Portfolio ist eine Liste von
Positionen: {"ticker": str, "value": float, "date": "YYYY-MM-DD" | None}.
"""
from __future__ import annotations
import json
import os

PATH = os.path.join(os.path.expanduser("~"), ".value_radar_portfolios.json")


def load_all() -> dict:
    try:
        with open(PATH, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(d: dict) -> bool:
    try:
        with open(PATH, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def save(name: str, records: list) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    d = load_all()
    d[name] = records
    return _write(d)


def delete(name: str) -> bool:
    d = load_all()
    if name in d:
        d.pop(name, None)
        return _write(d)
    return False


def names() -> list:
    return sorted(load_all().keys())
