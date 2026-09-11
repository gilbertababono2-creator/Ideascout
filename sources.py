from typing import Any, Dict, List
from urllib.parse import urlparse


def reddit_sources(posts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out=[]
    for p in posts:
        if p.get("permalink"):
            snippet = (p.get("selftext") or p.get("title") or "")[:300]
            out.append({"source_type":"Reddit","url":p["permalink"],"snippet":snippet})
    return out


def trend_source(keyword: str, url: str) -> Dict[str, str]:
    return {"source_type":"Google Trends","url":url,"snippet":f"Google Trends interest for keyword: {keyword}"}


def web_sources(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out=[]
    for x in items:
        if x.get("url"):
            out.append({"source_type":"Web","url":x["url"],"snippet":(x.get("snippet") or x.get("text") or x.get("description") or "")[:300]})
    return out


def dedupe(items: List[Dict[str,str]]) -> List[Dict[str,str]]:
    seen=set(); out=[]
    for x in items:
        key=(x.get("url",""),x.get("snippet",""))
        if key not in seen:
            seen.add(key); out.append(x)
    return out
