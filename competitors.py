"""Competitor normalisation and evidence helpers."""
from typing import List, Dict
from sources import source

def competitor_sources(competitors: List[Dict]) -> List[Dict]:
    out = []
    for c in competitors:
        if c.get("url"):
            out.append(source(
                "competitor",
                c["url"],
                c.get("title") or c.get("description") or "Competitor page"
            ))
    return out
