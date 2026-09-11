import math
from typing import Any, Dict, List
from urllib.parse import quote_plus


def _slope(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
    return sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values)) / den


def velocity_score(values: List[float]) -> int:
    if len(values) < 4 or max(values) == 0:
        return 5
    recent = values[-min(13, len(values)):]
    slope = _slope(recent)
    scale = max(1.0, sum(recent) / len(recent))
    normalized = slope / scale * 100
    score = round(5 + normalized * 1.5)
    return max(1, min(10, score))


def direction(values: List[float]) -> str:
    if len(values) < 4:
        return "Unknown"
    recent = values[-min(13, len(values)):]
    slope = _slope(recent)
    scale = max(1.0, sum(recent) / len(recent))
    pct = slope / scale
    if pct > 0.025:
        return "Rising"
    if pct < -0.025:
        return "Declining"
    return "Flat"


def trend_url(keyword: str) -> str:
    return "https://trends.google.com/trends/explore?q=" + quote_plus(keyword)


def fetch_keyword(keyword: str, geo: str = "") -> Dict[str, Any]:
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        pytrends.build_payload([keyword], timeframe="today 12-m", geo=geo)
        df = pytrends.interest_over_time()
        if df is None or df.empty or keyword not in df.columns:
            return {"keyword": keyword, "has_data": False, "error": "No Trends data", "url": trend_url(keyword)}
        values = [float(v) for v in df[keyword].fillna(0).tolist()]
        dates = [str(x.date()) for x in df.index]
        last90_values = values[-min(13, len(values)):]
        return {
            "keyword": keyword,
            "has_data": True,
            "values": values,
            "dates": dates,
            "last90_values": last90_values,
            "direction": direction(values),
            "velocity_score": velocity_score(values),
            "url": trend_url(keyword),
            "error": "",
        }
    except Exception as exc:
        return {"keyword": keyword, "has_data": False, "error": str(exc), "url": trend_url(keyword)}
