"""Live market research with Tavily web search.

Nemotron Lightning writes the search queries during intake; Tavily returns sources; the
results are summarised into a market snapshot and passed to the review as cited evidence.
Without a TAVILY_API_KEY this step is skipped (we never show invented sources).
"""
import time

import httpx

from .. import config


def enabled() -> bool:
    return bool(config.TAVILY_API_KEY)


def search(queries: list[str], per_query=4) -> dict:
    started = time.perf_counter()
    results, seen = [], set()
    for q in queries[:3]:
        r = httpx.post("https://api.tavily.com/search", timeout=40,
                       headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
                       json={"query": q, "search_depth": "advanced", "max_results": per_query,
                             "include_answer": False})
        r.raise_for_status()
        for item in r.json().get("results", []):
            if item.get("url") in seen:
                continue
            seen.add(item.get("url"))
            results.append({"query": q, "title": item.get("title", ""), "url": item.get("url", ""),
                            "content": (item.get("content") or "")[:700]})
    return {"results": results, "latency_ms": int((time.perf_counter() - started) * 1000)}
