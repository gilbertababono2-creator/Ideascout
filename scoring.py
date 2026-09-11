from typing import Dict, Any, List

DEFAULT_WEIGHTS={"pain_level":.25,"market_size":.20,"competition_gap":.15,"monetisation_potential":.20,"trend_velocity":.10,"ease_of_creation":.10}
LABELS={"pain_level":"Pain Score","market_size":"Market Score","competition_gap":"Competition Gap Score","monetisation_potential":"Monetisation Score","trend_velocity":"Trend Velocity Score","ease_of_creation":"Ease Score"}

def normalize_weights(weights: Dict[str,float])->Dict[str,float]:
    total=sum(max(0,float(v)) for v in weights.values()) or 1
    return {k:max(0,float(v))/total for k,v in weights.items()}

def weighted_score(scores: Dict[str,Any], weights: Dict[str,float])->float:
    w=normalize_weights(weights)
    vals=[]
    for k,wt in w.items():
        try: vals.append(float(scores.get(k,5))*wt)
        except: vals.append(5*wt)
    return round(sum(vals),2)

def rescore(ranked: List[Dict[str,Any]], weights: Dict[str,float])->List[Dict[str,Any]]:
    out=[]
    for r in ranked:
        x=dict(r); x["weighted_score"]=weighted_score(x.get("scores",{}),weights); out.append(x)
    return sorted(out,key=lambda x:x["weighted_score"],reverse=True)
