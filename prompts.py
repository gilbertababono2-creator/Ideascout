from typing import Any,Dict,List

DISCOVERY_SYSTEM="""You are a rigorous market-research analyst. Extract recurring pain, desires and unmet needs from Reddit evidence. Never invent quotes, URLs, upvotes or facts. Return JSON only."""
IDEA_SYSTEM="""You are an indie product strategist. Generate differentiated, buildable digital product opportunities from the supplied evidence. Prefer products that solve repeated painful problems. Return JSON only."""
SCORE_SYSTEM="""You are a skeptical product-market analyst. Score only from the supplied evidence. Higher Competition Gap means more whitespace, not more competition. Higher Trend Velocity means stronger recent growth. Do not invent sources. Return JSON only."""
COMP_SYSTEM="""You are a competitive intelligence analyst. Extract price, core features, target audience, and stated weaknesses only when supported by supplied page/search/review text. Mark unknown when absent. Then identify what competitors cover, miss, and possible differentiation. Return JSON only."""

def discovery_prompt(niche:str,posts:List[Dict[str,Any]]):
    evidence="\n\n".join([f"[{i}] r/{p.get('subreddit','')} | {p.get('score',0)} upvotes | {p.get('permalink','')}\nTITLE: {p.get('title','')}\nBODY: {p.get('selftext','')}" for i,p in enumerate(posts)])[:24000]
    return DISCOVERY_SYSTEM,f"Niche: {niche}\nREDDIT EVIDENCE:\n{evidence}\n\nReturn {{\"pain_points\":[{{\"label\":\"...\",\"description\":\"...\",\"frequency\":\"low|medium|high\",\"quote_indices\":[0,1]}}],\"quotes\":[{{\"text\":\"short exact quote from evidence\",\"subreddit\":\"...\",\"upvotes\":0,\"permalink\":\"...\",\"pain_label\":\"...\"}}]}}. Quote text must be copied only from the evidence and kept under 30 words."

def ideas_prompt(niche:str,pains:List[Dict[str,Any]],trends:Dict[str,Any],competitors:List[Dict[str,Any]],n:int):
    return IDEA_SYSTEM,f"Niche: {niche}\nPAINS: {pains}\nTRENDS: {trends}\nCOMPETITORS: {competitors}\nGenerate exactly {n} ideas. Return {{\"ideas\":[{{\"title\":\"...\",\"description\":\"...\",\"target_audience\":\"...\",\"suggested_format\":\"...\",\"core_keyword\":\"2-5 word keyword for Trends\",\"target_pain_points\":[\"...\"]}}]}}"

def competitor_prompt(items:List[Dict[str,Any]]):
    return COMP_SYSTEM,f"Analyze these competitor records:\n{items}\nReturn {{\"competitors\":[{{\"name\":\"...\",\"url\":\"...\",\"price\":\"unknown or supported price\",\"core_features\":[\"...\"],\"target_audience\":\"...\",\"stated_weaknesses\":[\"...\"]}}],\"gap_report\":\"what is covered, missing, and how a new product could differentiate\"}}"

def scoring_prompt(niche:str,ideas:List[Dict[str,Any]],pains:List[Dict[str,Any]],trend_by_keyword:Dict[str,Any],comp:Dict[str,Any]):
    return SCORE_SYSTEM,f"Niche: {niche}\nIDEAS: {ideas}\nPAINS: {pains}\nTRENDS: {trend_by_keyword}\nCOMPETITOR ANALYSIS: {comp}\nScore each idea 1-10 for pain_level, market_size, competition_gap, monetisation_potential, trend_velocity, ease_of_creation. Use supplied trend velocity when available. Return {{\"scores\":[{{\"title\":\"exact title\",\"pain_level\":1,\"market_size\":1,\"competition_gap\":1,\"monetisation_potential\":1,\"trend_velocity\":1,\"ease_of_creation\":1,\"reasoning\":\"...\"}}]}}"
