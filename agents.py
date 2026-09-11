from typing import Any,Dict,List,Optional
from groq_client import GroqClient
from prompts import discovery_prompt,ideas_prompt,competitor_prompt,scoring_prompt
from data_sources import fetch_reddit_posts,fetch_page_text,search_web
from trends import fetch_keyword
from scoring import weighted_score,DEFAULT_WEIGHTS
from sources import reddit_sources,web_sources,trend_source,dedupe

class DiscoveryAgent:
    def __init__(self,g):self.g=g
    def run(self,niche,subreddits=None,manual_text=""):
        posts=[]
        error=""
        if manual_text.strip():
            # Manual evidence is converted to one synthetic record so quotes can still be cited.
            posts=[{"title":"Manual Reddit evidence","selftext":manual_text.strip(),"subreddit":"manual","score":0,"permalink":""}]
        else:
            try: posts=fetch_reddit_posts(niche,subreddits)
            except Exception as e:error=str(e)
        if not posts:return {"posts":[],"pain_points":[],"quotes":[],"sources":[],"error":error or "No Reddit evidence."}
        sys,user=discovery_prompt(niche,posts); data=self.g.complete_json(sys,user,2200)
        quotes=data.get("quotes",[]); pains=data.get("pain_points",[])
        return {"posts":posts,"pain_points":pains,"quotes":quotes,"sources":dedupe(reddit_sources(posts)),"error":error}

class TrendAgent:
    def run(self,keywords:List[str]):
        out={}
        for kw in keywords[:12]:
            if kw.strip(): out[kw.strip()]=fetch_keyword(kw.strip())
        return out

class CompetitorAgent:
    def run(self,niche,urls=None,names=None,notes=""):
        urls=urls or []; names=names or []
        items=[]
        for u in urls[:10]:
            page=fetch_page_text(u.strip())
            items.append({"url":u,"title":page.get("title",""),"text":page.get("text","")[:10000],"error":page.get("error","")})
        for name in names[:10]:
            items.extend(search_web(f"{name} pricing features reviews",max_results=3))
        if not items: items=search_web(f"{niche} tool app template pricing reviews",max_results=8)
        if notes.strip():items.append({"url":"","title":"User supplied competitor notes","text":notes[:10000]})
        if not items:return {"competitors":[],"gap_report":"No competitor evidence available.","sources":[]}
        sys,user=competitor_prompt(items); data=self.g.complete_json(sys,user,3000)
        comps=data.get("competitors",[])
        src=dedupe(web_sources(items)+[{"source_type":"Competitor","url":c.get("url",""),"snippet":c.get("name","")} for c in comps if c.get("url")])
        return {"competitors":comps,"gap_report":data.get("gap_report",""),"sources":src}

class ResearchAgent:
    def __init__(self,g):self.g=g
    def generate_and_score(self,niche,pains,trends,competitors,n):
        sys,user=ideas_prompt(niche,pains,trends,competitors,n); ideas=self.g.complete_json(sys,user,2600).get("ideas",[])
        keywords=[]
        for i in ideas:
            kw=i.get("core_keyword","").strip()
            if kw and kw.lower() not in [x.lower() for x in keywords]:keywords.append(kw)
        trend_by=self._missing_trends(keywords,trends)
        sys,user=scoring_prompt(niche,ideas,pains,trend_by,competitors); raw=self.g.complete_json(sys,user,3200).get("scores",[])
        by={x.get("title","").strip().lower():x for x in raw}; ranked=[]
        for idea in ideas:
            s=by.get(idea.get("title","").strip().lower(),{})
            # Trend score is anchored to Python-measured velocity when available.
            t=trend_by.get(idea.get("core_keyword",""),{})
            scores={k:s.get(k,5) for k in ("pain_level","market_size","competition_gap","monetisation_potential","trend_velocity","ease_of_creation")}
            if t.get("has_data"):scores["trend_velocity"]=t.get("velocity_score",5)
            ranked.append({**idea,"scores":scores,"weighted_score":weighted_score(scores,DEFAULT_WEIGHTS),"reasoning":s.get("reasoning","")})
        return ranked,trend_by
    def _missing_trends(self,keywords,existing):
        out=dict(existing or {})
        for kw in keywords:
            if kw not in out:out[kw]=fetch_keyword(kw)
        return out
