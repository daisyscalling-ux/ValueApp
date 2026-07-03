"""
intel.py — Katalysator- & Intel-Layer (das "Portal").

Bündelt News, Peers, Supply-Chain (Best-Effort), Insider-Aktivität und
Schätzungsrevisionen. Leitet daraus einen groben Catalyst-Score (0-100) ab,
der ins Scoring einfließen kann.

Ehrliche Grenze: echte Kunden/Lieferanten-Graphen sind institutionelle
Premiumdaten. Ohne Finnhub-Premium bleiben customers/suppliers leer und
werden im Report transparent als "n/a" gekennzeichnet.
"""
from __future__ import annotations
from typing import Any
import providers


# einfache Schlagwort-Heuristik für News-Sentiment (Frühindikator-Proxy)
POSITIVE = {"beat", "raises", "raise", "upgrade", "record", "surge", "wins",
            "win", "expands", "expansion", "guidance up", "strong", "demand",
            "backlog", "design win", "capacity", "partnership", "approval"}
NEGATIVE = {"miss", "misses", "cuts", "cut", "downgrade", "warns", "warning",
            "lawsuit", "probe", "decline", "weak", "recall", "delay", "loss",
            "guidance down", "layoffs", "default"}


def _news_sentiment(news: list[dict]) -> float:
    """grobe -1..+1 Sentiment-Schätzung aus Headlines."""
    if not news:
        return 0.0
    score = 0
    for n in news:
        h = (n.get("headline") or "").lower()
        score += sum(1 for w in POSITIVE if w in h)
        score -= sum(1 for w in NEGATIVE if w in h)
    return max(-1.0, min(1.0, score / max(len(news), 1)))


def gather(ticker: str, name: str = None) -> dict[str, Any]:
    """Sammelt den kompletten Intel-Datensatz für einen Ticker."""
    news = providers.get_news(ticker, name=name)
    peers = providers.get_peers(ticker)
    supply = providers.get_supply_chain(ticker)
    insider = providers.get_insider_activity(ticker)
    revisions = providers.get_estimate_revisions(ticker)
    analyst = providers.get_analyst_ratings(ticker)
    sentiment = _news_sentiment(news)

    return {
        "ticker": ticker.upper(),
        "news": news,
        "news_sentiment": round(sentiment, 2),
        "peers": peers,
        "supply_chain": supply,
        "insider": insider,
        "estimate_revisions": revisions,
        "analyst": analyst,
        "catalyst_score": _catalyst_score(sentiment, insider, analyst),
    }


def _catalyst_score(sentiment: float, insider, analyst) -> float:
    """0-100. Kombiniert News-Sentiment, Insider-Käufe, Analysten-Schräglage."""
    score = 50.0 + sentiment * 25.0

    if insider and insider.get("n"):
        buys, sells = insider.get("recent_buys", 0), insider.get("recent_sells", 0)
        if buys + sells > 0:
            score += ((buys - sells) / (buys + sells)) * 10

    if analyst:
        bull = (analyst.get("buy", 0) or 0)
        bear = (analyst.get("sell", 0) or 0)
        if bull + bear > 0:
            score += ((bull - bear) / (bull + bear)) * 15

    return round(max(0.0, min(100.0, score)), 1)


def format_report(intel: dict) -> str:
    """Menschenlesbarer Intel-Block."""
    lines = [f"\n=== INTEL: {intel['ticker']} ===",
             f"Catalyst-Score: {intel['catalyst_score']}/100  "
             f"(News-Sentiment: {intel['news_sentiment']:+.2f})"]

    peers = intel.get("peers") or []
    lines.append(f"\nPeers/Wettbewerber: {', '.join(peers) if peers else 'n/a (Key noetig)'}")

    sc = intel.get("supply_chain", {})
    cust = sc.get("customers") or []
    supp = sc.get("suppliers") or []
    lines.append(f"Kunden:     {', '.join(map(str, cust)) if cust else 'n/a (Premium-Daten noetig)'}")
    lines.append(f"Lieferanten: {', '.join(map(str, supp)) if supp else 'n/a (Premium-Daten noetig)'}")

    ins = intel.get("insider")
    if ins:
        lines.append(f"Insider (30T): {ins.get('recent_buys',0)} Kaeufe / "
                     f"{ins.get('recent_sells',0)} Verkaeufe")

    an = intel.get("analyst")
    if an:
        lines.append(f"Analysten: Buy {an.get('buy')} / Hold {an.get('hold')} / "
                     f"Sell {an.get('sell')}")

    lines.append("\nNews (neueste):")
    for n in (intel.get("news") or [])[:8]:
        lines.append(f"  - {n.get('headline')}  [{n.get('source')}]")
    if not intel.get("news"):
        lines.append("  (keine News verfuegbar)")
    return "\n".join(lines)
