import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)
TIMEOUT = 15
UA = "NexusIdeaScout/2.1 research-assistant/1.0"


def _get(url: str, **kwargs):
    """GET with retries for transient errors; callers decide how to handle failure."""
    headers = {"User-Agent": UA, **kwargs.pop("headers", {})}
    last: Optional[str] = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {response.status_code}"
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = str(exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(last or "request failed")


def _hacker_news_fallback(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Use Hacker News' public Algolia API when Reddit is unavailable."""
    url = "https://hn.algolia.com/api/v1/search_by_date"
    try:
        response = _get(
            url,
            params={"query": query, "tags": "story,comment", "hitsPerPage": min(limit, 50)},
            headers={"User-Agent": UA},
        )
        hits = response.json().get("hits", [])
        out: List[Dict[str, Any]] = []
        for hit in hits:
            text = (hit.get("story_text") or hit.get("comment_text") or "").strip()
            title = (hit.get("title") or hit.get("story_title") or "").strip()
            if not text and not title:
                continue
            object_id = hit.get("objectID", "")
            out.append({
                "title": title,
                "selftext": text,
                "subreddit": "Hacker News",
                "score": int(hit.get("points") or 0),
                "num_comments": 0,
                "permalink": f"https://news.ycombinator.com/item?id={object_id}" if object_id else "",
                "created_utc": hit.get("created_at_i", 0),
                "source_type": "Hacker News",
            })
        return out
    except Exception as exc:
        logger.warning("Hacker News fallback failed: %s", exc)
        return []


def fetch_reddit_posts(
    niche: str,
    subreddits: Optional[List[str]] = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch Reddit evidence, then gracefully fall back to Hacker News.

    The function never lets a Reddit 403/429 crash the research run. If both
    sources fail, it raises a concise error that the UI can display.
    """
    reddit_errors: List[str] = []

    # Prefer PRAW when credentials are configured.
    try:
        import os
        import praw

        cid = os.getenv("REDDIT_CLIENT_ID", "")
        secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        ua = os.getenv("REDDIT_USER_AGENT", UA)
        if cid and secret:
            reddit = praw.Reddit(
                client_id=cid,
                client_secret=secret,
                user_agent=ua,
                check_for_async=False,
            )
            out: List[Dict[str, Any]] = []
            targets = subreddits or [None]
            for sub in targets:
                try:
                    source = reddit.subreddit(sub) if sub else reddit.subreddit("all")
                    for post in source.search(
                        niche,
                        sort="new",
                        time_filter="year",
                        limit=limit,
                    ):
                        out.append({
                            "title": post.title,
                            "selftext": post.selftext or "",
                            "subreddit": str(post.subreddit),
                            "score": int(post.score),
                            "num_comments": int(post.num_comments),
                            "permalink": f"https://www.reddit.com{post.permalink}",
                            "created_utc": getattr(post, "created_utc", 0),
                            "source_type": "Reddit",
                        })
                except Exception as exc:
                    reddit_errors.append(f"r/{sub or 'all'}: {exc}")
            if out:
                return out
    except Exception as exc:
        reddit_errors.append(f"PRAW: {exc}")
        logger.warning("PRAW Reddit fetch failed: %s", exc)

    # Public Reddit JSON fallback. Streamlit Cloud IPs can be blocked, so this
    # is intentionally wrapped and followed by the HN fallback.
    headers = {"User-Agent": UA}
    out: List[Dict[str, Any]] = []
    targets = subreddits or [None]
    for sub in targets:
        try:
            if sub:
                clean_sub = sub.strip().removeprefix("r/")
                url = (
                    f"https://www.reddit.com/r/{quote_plus(clean_sub)}/search.json"
                    f"?q={quote_plus(niche)}&restrict_sr=1&sort=new&limit={limit}&t=year"
                )
            else:
                url = (
                    f"https://www.reddit.com/search.json"
                    f"?q={quote_plus(niche)}&sort=new&limit={limit}&t=year"
                )

            data = _get(url, headers=headers).json()
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                out.append({
                    "title": d.get("title", ""),
                    "selftext": d.get("selftext", "") or "",
                    "subreddit": d.get("subreddit", ""),
                    "score": int(d.get("score", 0) or 0),
                    "num_comments": int(d.get("num_comments", 0) or 0),
                    "permalink": (
                        f"https://www.reddit.com{d.get('permalink', '')}"
                        if d.get("permalink") else ""
                    ),
                    "created_utc": d.get("created_utc", 0),
                    "source_type": "Reddit",
                })
        except Exception as exc:
            reddit_errors.append(f"Reddit {sub or 'all'}: {exc}")
            logger.warning("Reddit request failed for %s: %s", sub or "all", exc)

    if out:
        return out[: limit * max(1, len(targets))]

    # Graceful fallback: HN has a public Algolia API and does not require API keys.
    hn = _hacker_news_fallback(niche, limit=limit)
    if hn:
        logger.warning("Reddit unavailable; using Hacker News fallback.")
        return hn

    detail = "; ".join(reddit_errors[-3:])
    raise RuntimeError(
        "Reddit blocked or unavailable, and Hacker News fallback returned no evidence. "
        "Use the manual community-evidence field in the app."
        + (f" Details: {detail}" if detail else "")
    )


def search_web(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search the web without scraping a search-engine HTML page.

    Prefer the duckduckgo_search package when installed. The newer ddgs package
    is also supported because duckduckgo_search has been renamed/superseded in
    recent environments. If both fail, return an empty list instead of crashing.
    """
    errors: List[str] = []

    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                }
                for r in results
            ]
    except Exception as exc:
        errors.append(f"duckduckgo_search: {exc}")
        logger.warning("duckduckgo_search failed: %s", exc)

    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                }
                for r in results
            ]
    except Exception as exc:
        errors.append(f"ddgs: {exc}")
        logger.warning("DDGS fallback failed: %s", exc)

    logger.warning("Web search unavailable; returning no search results. %s", "; ".join(errors))
    return []


def fetch_page_text(url: str, max_chars: int = 12000) -> Dict[str, str]:
    """Fetch and strip readable text from a competitor URL without crashing."""
    try:
        from bs4 import BeautifulSoup

        response = _get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NexusIdeaScout/2.1)"},
        )
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        text = " ".join(soup.stripped_strings)
        return {
            "url": url,
            "title": title,
            "text": text[:max_chars],
            "error": "",
        }
    except Exception as exc:
        logger.warning("Competitor page fetch failed for %s: %s", url, exc)
        return {
            "url": url,
            "title": "",
            "text": "",
            "error": str(exc),
        }
