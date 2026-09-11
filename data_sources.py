import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
import requests

logger = logging.getLogger(__name__)
TIMEOUT = 15
UA = "NexusIdeaScout/2.0 research-assistant/1.0"


def _get(url: str, **kwargs):
    headers = {"User-Agent": UA, **kwargs.pop("headers", {})}
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                last = f"HTTP {r.status_code}"
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            last = str(exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(last or "request failed")


def fetch_reddit_posts(niche: str, subreddits: Optional[List[str]] = None, limit: int = 30) -> List[Dict[str, Any]]:
    # Prefer PRAW when credentials are configured; otherwise use public JSON.
    try:
        import os, praw
        cid = os.getenv("REDDIT_CLIENT_ID", "")
        secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        ua = os.getenv("REDDIT_USER_AGENT", UA)
        if cid and secret:
            reddit = praw.Reddit(client_id=cid, client_secret=secret, user_agent=ua, check_for_async=False)
            out = []
            targets = subreddits or [None]
            for sub in targets:
                source = reddit.subreddit(sub) if sub else reddit.subreddit("all")
                for p in source.search(niche, sort="new", time_filter="year", limit=limit):
                    out.append({"title": p.title, "selftext": p.selftext or "", "subreddit": str(p.subreddit), "score": int(p.score), "num_comments": int(p.num_comments), "permalink": f"https://www.reddit.com{p.permalink}", "created_utc": getattr(p, "created_utc", 0)})
            if out:
                return out
    except Exception as exc:
        logger.warning("PRAW Reddit fetch failed; falling back to public JSON: %s", exc)

    headers = {"User-Agent": UA}
    out = []
    targets = subreddits or [None]
    for sub in targets:
        if sub:
            sub = sub.strip().removeprefix("r/")
            url = f"https://www.reddit.com/r/{quote_plus(sub)}/search.json?q={quote_plus(niche)}&restrict_sr=1&sort=new&limit={limit}&t=year"
        else:
            url = f"https://www.reddit.com/search.json?q={quote_plus(niche)}&sort=new&limit={limit}&t=year"
        try:
            data = _get(url, headers=headers).json()
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                out.append({"title": d.get("title", ""), "selftext": d.get("selftext", "") or "", "subreddit": d.get("subreddit", ""), "score": int(d.get("score", 0) or 0), "num_comments": int(d.get("num_comments", 0) or 0), "permalink": f"https://www.reddit.com{d.get('permalink','')}" if d.get("permalink") else "", "created_utc": d.get("created_utc", 0)})
        except Exception as exc:
            logger.warning("Reddit request failed for %s: %s", sub, exc)
    if not out:
        raise RuntimeError("Reddit returned no usable posts. Use manual Reddit text as a fallback.")
    return out[:limit * max(1, len(targets))]


def search_web(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
    except Exception as exc:
        logger.warning("DDGS search failed: %s", exc)
        return []


def fetch_page_text(url: str, max_chars: int = 12000) -> Dict[str, str]:
    try:
        from bs4 import BeautifulSoup
        r = _get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NexusIdeaScout/2.0)"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        text = " ".join(soup.stripped_strings)
        return {"url": url, "title": title, "text": text[:max_chars], "error": ""}
    except Exception as exc:
        return {"url": url, "title": "", "text": "", "error": str(exc)}
