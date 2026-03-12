# web_search.py
# DuckDuckGo search wrapper — free, no API key required.

from __future__ import annotations


def search(query: str, max_results: int = 5) -> list[dict]:
    """Return up to *max_results* results from DuckDuckGo.

    Each result is a dict with keys: title, url, snippet.
    Returns an empty list on any error.
    """
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max(1, min(max_results, 10))))
        return [
            {
                "title":   r.get("title", ""),
                "url":     r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]
    except Exception:
        return []
