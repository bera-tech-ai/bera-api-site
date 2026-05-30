"""
AI scraping module for Bruce Bera AI API.
Queries free AI sources and returns clean text responses.
Falls back through multiple providers.
"""
import asyncio
import hashlib
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "30"))

# ─── Simple in-memory cache (TTL: 1 hour) ──────────────────────────────────
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 3600  # seconds


def _cache_key(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def _get_cached(query: str) -> Optional[str]:
    key = _cache_key(query)
    entry = _cache.get(key)
    if entry and (time.time() - entry[1]) < _CACHE_TTL:
        return entry[0]
    return None


def _set_cache(query: str, answer: str):
    _cache[_cache_key(query)] = (answer, time.time())


# ─── Provider 1: DuckDuckGo instant answers (no key, no scrape) ────────────
async def _query_duckduckgo(query: str, client: httpx.AsyncClient) -> Optional[str]:
    """Use DDG's instant answer API as a lightweight fallback."""
    try:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
            timeout=SCRAPE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("AbstractText") or data.get("Answer") or ""
        if answer and len(answer) > 30:
            return answer.strip()
        # Try related topics
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                if len(topic["Text"]) > 50:
                    return topic["Text"].strip()
        return None
    except Exception as e:
        logger.debug("DuckDuckGo failed: %s", e)
        return None


# ─── Provider 2: Pollinations AI (free, no key) ────────────────────────────
async def _query_pollinations(query: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Pollinations offers a free text generation endpoint.
    GET https://text.pollinations.ai/{prompt}
    """
    try:
        import urllib.parse
        encoded = urllib.parse.quote(query)
        resp = await client.get(
            f"https://text.pollinations.ai/{encoded}",
            timeout=SCRAPE_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        if text and len(text) > 20:
            return text
        return None
    except Exception as e:
        logger.debug("Pollinations failed: %s", e)
        return None


# ─── Provider 3: Open-Meteo / Wikipedia summary via REST ───────────────────
async def _query_wikipedia(query: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Wikipedia REST API search + summary — always free.
    Great fallback for factual/encyclopedic questions.
    """
    try:
        search_resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": "3",
            },
            timeout=SCRAPE_TIMEOUT,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return None

        title = results[0]["title"]
        summary_resp = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
            timeout=SCRAPE_TIMEOUT,
        )
        summary_resp.raise_for_status()
        data = summary_resp.json()
        extract = data.get("extract", "")
        if extract and len(extract) > 40:
            return extract.strip()
        return None
    except Exception as e:
        logger.debug("Wikipedia failed: %s", e)
        return None


# ─── Provider 4: Gemini (if GEMINI_API_KEY env var set) ────────────────────
async def _query_gemini(query: str, client: httpx.AsyncClient) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": query}]}]},
            timeout=SCRAPE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return text.strip() if text else None
    except Exception as e:
        logger.debug("Gemini failed: %s", e)
        return None


# ─── Provider 5: Groq (if GROQ_API_KEY env var set) ────────────────────────
async def _query_groq(query: str, client: httpx.AsyncClient) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 512,
            },
            timeout=SCRAPE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text if text else None
    except Exception as e:
        logger.debug("Groq failed: %s", e)
        return None


# ─── Main entry point ───────────────────────────────────────────────────────

_PROVIDERS = [
    ("Gemini", _query_gemini),
    ("Groq", _query_groq),
    ("Pollinations", _query_pollinations),
    ("Wikipedia", _query_wikipedia),
    ("DuckDuckGo", _query_duckduckgo),
]


async def get_ai_answer(query: str) -> str:
    """
    Try each provider in order until one succeeds.
    Results are cached for 1 hour to avoid repeated network calls.
    Returns a fallback message if all providers fail.
    """
    cached = _get_cached(query)
    if cached:
        logger.debug("Cache hit for query: %.60s", query)
        return cached

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; BruceBerAI/1.0; +https://github.com/brucebera)"
            )
        },
        follow_redirects=True,
    ) as client:
        for name, provider_fn in _PROVIDERS:
            try:
                result = await provider_fn(query, client)
                if result and len(result.strip()) > 20:
                    logger.info("AI answer from %s (%.60s...)", name, result)
                    _set_cache(query, result)
                    return result
            except Exception as e:
                logger.warning("Provider %s raised unexpectedly: %s", name, e)

    fallback = (
        "I'm having trouble connecting to my AI sources right now. "
        "Please try again in a moment."
    )
    return fallback
