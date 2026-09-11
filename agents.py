from typing import Any, Dict, List, Optional
import logging

from groq_client import GroqClient
from prompts import discovery_prompt, ideas_prompt, competitor_prompt, scoring_prompt
from data_sources import fetch_reddit_posts, fetch_page_text, search_web
from trends import fetch_keyword
from scoring import weighted_score, DEFAULT_WEIGHTS
from sources import reddit_sources, web_sources, dedupe

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    def __init__(self, g: GroqClient):
        self.g = g

    def run(self, niche: str, subreddits: Optional[List[str]] = None, manual_text: str = ""):
        posts: List[Dict[str, Any]] = []
        error = ""

        if manual_text.strip():
            posts = [{
                "title": "Manual community evidence",
                "selftext": manual_text.strip(),
                "subreddit": "manual",
                "score": 0,
                "num_comments": 0,
                "permalink": "",
                "source_type": "Manual",
            }]
        else:
            try:
                posts = fetch_reddit_posts(niche, subreddits)
            except Exception as exc:
                error = str(exc)
                logger.warning("Community discovery failed: %s", exc)

        if not posts:
            return {
                "posts": [],
                "pain_points": [],
                "quotes": [],
                "sources": [],
                "error": error or "No community evidence available.",
            }

        try:
            system, user = discovery_prompt(niche, posts)
            data = self.g.complete_json(system, user, 2200)
        except Exception as exc:
            logger.exception("Discovery Groq call failed")
            return {
                "posts": posts,
                "pain_points": [],
                "quotes": [],
                "sources": dedupe(reddit_sources(posts)),
                "error": f"AI discovery failed: {exc}",
            }

        quotes = data.get("quotes", []) or []
        pains = data.get("pain_points", []) or []
        return {
            "posts": posts,
            "pain_points": pains,
            "quotes": quotes,
            "sources": dedupe(reddit_sources(posts)),
            "error": error,
        }


class TrendAgent:
    def run(self, keywords: List[str]):
        out: Dict[str, Any] = {}
        for kw in keywords[:12]:
            kw = kw.strip()
            if not kw:
                continue
            try:
                out[kw] = fetch_keyword(kw)
            except Exception as exc:
                logger.warning("Trend lookup failed for %s: %s", kw, exc)
                out[kw] = {
                    "keyword": kw,
                    "has_data": False,
                    "error": str(exc),
                }
        return out


class CompetitorAgent:
    """Collect competitor evidence and use the shared Groq client for analysis."""

    def __init__(self, g: GroqClient):
        # This was the missing attribute in the deployed version.
        self.g = g

    def run(
        self,
        niche: str,
        urls: Optional[List[str]] = None,
        names: Optional[List[str]] = None,
        notes: str = "",
    ):
        urls = urls or []
        names = names or []
        items: List[Dict[str, Any]] = []
        errors: List[str] = []

        for raw_url in urls[:10]:
            url = raw_url.strip()
            if not url:
                continue
            try:
                page = fetch_page_text(url)
                items.append({
                    "url": url,
                    "title": page.get("title", ""),
                    "text": page.get("text", "")[:10000],
                    "snippet": page.get("text", "")[:500],
                    "error": page.get("error", ""),
                })
                if page.get("error"):
                    errors.append(f"{url}: {page['error']}")
            except Exception as exc:
                logger.warning("Competitor URL fetch failed for %s: %s", url, exc)
                errors.append(f"{url}: {exc}")

        for name in names[:10]:
            name = name.strip()
            if not name:
                continue
            try:
                items.extend(search_web(f"{name} pricing features reviews", max_results=3))
            except Exception as exc:
                logger.warning("Competitor web search failed for %s: %s", name, exc)
                errors.append(f"{name}: {exc}")

        if not items:
            try:
                items = search_web(
                    f"{niche} tool app template pricing reviews",
                    max_results=8,
                )
            except Exception as exc:
                logger.warning("Fallback competitor search failed: %s", exc)
                errors.append(str(exc))

        if notes.strip():
            items.append({
                "url": "",
                "title": "User supplied competitor notes",
                "text": notes[:10000],
                "snippet": notes[:500],
                "source_type": "Manual",
            })

        if not items:
            return {
                "competitors": [],
                "gap_report": "No competitor evidence available. " + ("; ".join(errors) if errors else ""),
                "sources": [],
                "errors": errors,
            }

        try:
            system, user = competitor_prompt(items)
            data = self.g.complete_json(system, user, 3000)
        except Exception as exc:
            logger.exception("Competitor Groq call failed")
            return {
                "competitors": [],
                "gap_report": f"Competitor evidence was collected, but AI analysis failed: {exc}",
                "sources": dedupe(web_sources(items)),
                "errors": errors + [str(exc)],
            }

        comps = data.get("competitors", []) or []
        src = dedupe(web_sources(items))
        for c in comps:
            if c.get("url"):
                src.append({
                    "source_type": "Competitor",
                    "url": c["url"],
                    "snippet": c.get("name", ""),
                })
        return {
            "competitors": comps,
            "gap_report": data.get("gap_report", ""),
            "sources": dedupe(src),
            "errors": errors,
        }


class ResearchAgent:
    def __init__(self, g: GroqClient):
        self.g = g

    def generate_and_score(
        self,
        niche: str,
        pains: List[Dict[str, Any]],
        trends: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        n: int,
    ):
        system, user = ideas_prompt(niche, pains, trends, competitors, n)
        ideas = self.g.complete_json(system, user, 2600).get("ideas", []) or []

        keywords: List[str] = []
        for idea in ideas:
            kw = idea.get("core_keyword", "").strip()
            if kw and kw.lower() not in [x.lower() for x in keywords]:
                keywords.append(kw)

        trend_by = self._missing_trends(keywords, trends)
        system, user = scoring_prompt(niche, ideas, pains, trend_by, {"competitors": competitors})
        raw = self.g.complete_json(system, user, 3200).get("scores", []) or []

        by = {x.get("title", "").strip().lower(): x for x in raw}
        ranked: List[Dict[str, Any]] = []
        for idea in ideas:
            score = by.get(idea.get("title", "").strip().lower(), {})
            trend = trend_by.get(idea.get("core_keyword", ""), {})
            scores = {
                key: score.get(key, 5)
                for key in (
                    "pain_level",
                    "market_size",
                    "competition_gap",
                    "monetisation_potential",
                    "trend_velocity",
                    "ease_of_creation",
                )
            }
            if trend.get("has_data"):
                scores["trend_velocity"] = trend.get("velocity_score", 5)

            ranked.append({
                **idea,
                "scores": scores,
                "weighted_score": weighted_score(scores, DEFAULT_WEIGHTS),
                "reasoning": score.get("reasoning", ""),
            })

        return ranked, trend_by

    def _missing_trends(self, keywords: List[str], existing: Optional[Dict[str, Any]]):
        out = dict(existing or {})
        for kw in keywords:
            if kw not in out:
                try:
                    out[kw] = fetch_keyword(kw)
                except Exception as exc:
                    out[kw] = {
                        "keyword": kw,
                        "has_data": False,
                        "error": str(exc),
                    }
        return out
