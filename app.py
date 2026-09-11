import os, json, logging
from pathlib import Path
import pandas as pd
import streamlit as st

from groq_client import GroqClient,GroqClientError
from agents import DiscoveryAgent,CompetitorAgent,ResearchAgent
from scoring import DEFAULT_WEIGHTS,LABELS,normalize_weights,rescore
import database

try:
 from dotenv import load_dotenv; load_dotenv()
except Exception: pass

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Nexus IdeaScout V2",page_icon="🧭",layout="wide")

st.title("🧭 Nexus IdeaScout V2")
st.warning("**This tool finds and ranks opportunities. It does not guarantee sales. You must validate demand manually before building.**")
st.caption("Research assistant for freelancers and real-estate operators. Evidence is limited by free-source availability and should be manually verified.")

@st.cache_resource
def client(): return GroqClient()
try:g=client()
except GroqClientError as e: st.error(str(e)); st.stop()

with st.sidebar:
 st.header("Research settings")
 num=st.slider("Ideas",5,15,8)
 st.subheader("Reddit")
 subs=st.text_input("Target subreddits (comma separated)","realtors,realestate")
 manual=st.text_area("Optional manual Reddit evidence",height=100,help="Use this when Reddit blocks cloud requests.")
 st.subheader("Competitors")
 comp_urls=st.text_area("Competitor URLs (one per line)",height=90)
 comp_names=st.text_input("Competitor/product names (comma separated)")
 comp_notes=st.text_area("Optional pasted competitor/review notes",height=90)
 st.subheader("Weights")
 weights={k:st.slider(LABELS[k],0.0,1.0,float(v),0.05) for k,v in DEFAULT_WEIGHTS.items()}
 weights=normalize_weights(weights)
 st.caption("Weights are normalized automatically.")
 st.divider()
 if st.button("Clear history/cache"):database.clear_history();st.success("History cleared.")

with st.expander("⚙️ Niche profile / keyword configuration"):
 profile_path=Path(__file__).with_name("profiles.json")
 try:profiles=json.loads(profile_path.read_text())
 except Exception:profiles={}
 pname=st.selectbox("Load profile",["Custom"]+list(profiles.keys()))
 if pname!="Custom" and st.button("Load selected profile"):
  p=profiles[pname]; st.session_state["profile"]=p; st.rerun()
 profile=st.session_state.get("profile",{})
 niche=st.text_input("Niche",profile.get("niche", ""))
 keywords=st.text_area("Trend keywords (one per line)","\n".join(profile.get("keywords",[])))
 if st.button("Save current profile"):
  key=(niche.strip().lower().replace(" ","_")[:40] or "profile")
  profiles[key]={"subreddits":[x.strip() for x in subs.split(",") if x.strip()],"keywords":[x.strip() for x in keywords.splitlines() if x.strip()],"competitor_urls":[x.strip() for x in comp_urls.splitlines() if x.strip()],"competitor_names":[x.strip() for x in comp_names.split(",") if x.strip()],"weights":weights}
  profile_path.write_text(json.dumps(profiles,indent=2)); st.success(f"Saved profile: {key}")

run=st.button("🚀 Run Research",type="primary",disabled=not niche.strip())
if run:
 subs_list=[x.strip() for x in subs.split(",") if x.strip()]
 kws=[x.strip() for x in keywords.splitlines() if x.strip()]
 urls=[x.strip() for x in comp_urls.splitlines() if x.strip()]
 names=[x.strip() for x in comp_names.split(",") if x.strip()]
 with st.status("Researching...",expanded=True) as status:
  discovery=DiscoveryAgent(g).run(niche,subs_list,manual); st.write(f"🔎 Reddit: {len(discovery['posts'])} evidence items, {len(discovery['quotes'])} quotes")
  # Initial trend scan on user keywords; idea-specific keywords are fetched after generation.
  from agents import TrendAgent
  trend=TrendAgent().run(kws[:8]); st.write(f"📈 Trends: {sum(1 for x in trend.values() if x.get('has_data'))}/{len(trend)} keywords returned data")
  competitors=CompetitorAgent().run(niche,urls,names,comp_notes); st.write(f"🏁 Competitors: {len(competitors['competitors'])} analyzed")
  ranked,trend_by=ResearchAgent(g).generate_and_score(niche,discovery['pain_points'],trend,competitors['competitors'],num)
  # apply current UI weights locally
  ranked=rescore(ranked,weights)
  payload={"pain_points":discovery["pain_points"],"quotes":discovery["quotes"],"reddit_posts":discovery["posts"],"trends":trend_by,"competitors":competitors,"ranked":ranked}
  run_id=database.save_run(niche,weights,payload)
  st.session_state["result"]=payload; st.session_state["run_id"]=run_id
  status.update(label=f"Complete — run #{run_id}",state="complete")

result=st.session_state.get("result")
if result:
 ranked=result["ranked"]
 st.subheader("🏆 Ranked opportunities")
 rows=[]
 for r in ranked:
  s=r.get("scores",{}); rows.append({"Idea":r.get("title",""),"Pain Score":s.get("pain_level"),"Market Score":s.get("market_size"),"Competition Gap Score":s.get("competition_gap"),"Monetisation Score":s.get("monetisation_potential"),"Trend Velocity Score":s.get("trend_velocity"),"Ease Score":s.get("ease_of_creation"),"Final Weighted Score":r.get("weighted_score")})
 df=pd.DataFrame(rows)
 st.dataframe(df,use_container_width=True,hide_index=True)

 export_rows=[]
 for r in ranked:
  s=r.get("scores",{}); qs=[q for q in result.get("quotes",[]) if q.get("pain_label") in r.get("target_pain_points",[])]
  top=qs[0].get("text","") if qs else (result.get("quotes") or [{"text":""}])[0].get("text","")
  src=[]
  kw=r.get("core_keyword","")
  if kw in result.get("trends",{}):src.append(result["trends"][kw].get("url",""))
  src += [q.get("permalink","") for q in qs[:2] if q.get("permalink")]
  src += [c.get("url","") for c in result.get("competitors",{}).get("competitors",[])[:3] if c.get("url")]
  export_rows.append({"Idea":r.get("title",""),"Pain Score":s.get("pain_level"),"Market Score":s.get("market_size"),"Competition Gap Score":s.get("competition_gap"),"Monetisation Score":s.get("monetisation_potential"),"Trend Velocity Score":s.get("trend_velocity"),"Ease Score":s.get("ease_of_creation"),"Final Weighted Score":r.get("weighted_score"),"Top Quote":top,"Sources":" | ".join(dict.fromkeys([x for x in src if x])),"Reasoning":r.get("reasoning","")})
 export_df=pd.DataFrame(export_rows,columns=["Idea","Pain Score","Market Score","Competition Gap Score","Monetisation Score","Trend Velocity Score","Ease Score","Final Weighted Score","Top Quote","Sources","Reasoning"])
 st.download_button("⬇️ Download clean CSV",export_df.to_csv(index=False).encode(),f"nexus_ideascout_{st.session_state.get('run_id','run')}.csv","text/csv")
 st.write("**Notion / Airtable copy:** select the table below and copy; CSV is also directly importable.")
 st.dataframe(export_df,use_container_width=True,hide_index=True)

 for i,r in enumerate(ranked,1):
  with st.expander(f"#{i} — {r.get('title','')} · {r.get('weighted_score')}/10"):
   st.write(r.get("description","")); st.caption(f"Audience: {r.get('target_audience','')} · Format: {r.get('suggested_format','')} · Keyword: {r.get('core_keyword','')}")
   st.write("**Reasoning:**",r.get("reasoning",""))
   st.markdown("### Validation checklist")
   st.checkbox("Check search volume / Trends manually",key=f"sv_{st.session_state.get('run_id')}_{i}")
   st.checkbox("Ask 5–10 target users for feedback",key=f"fb_{st.session_state.get('run_id')}_{i}")
   st.checkbox("Attempt a pre-sale or waitlist",key=f"ps_{st.session_state.get('run_id')}_{i}")
   st.checkbox("Study at least 3 paid competitors",key=f"cp_{st.session_state.get('run_id')}_{i}")
   st.markdown("### Community evidence")
   qs=[q for q in result.get("quotes",[]) if q.get("pain_label") in r.get("target_pain_points",[])] or result.get("quotes",[])[:5]
   for q in qs[:5]:
    st.markdown(f"> {q.get('text','')}")
    st.caption(f"r/{q.get('subreddit','')} · {q.get('upvotes',0)} upvotes · {q.get('permalink','')}")
   st.markdown("### Trend")
   kw=r.get("core_keyword",""); t=result.get("trends",{}).get(kw,{})
   if t.get("has_data"):
    c1,c2=st.columns(2); c1.metric("Direction",t.get("direction")); c2.metric("Velocity",f"{t.get('velocity_score')}/10"); st.line_chart(t.get("values",[]))
    st.caption(t.get("url"))
   else: st.info("No reliable Trends data for this keyword.")

with st.expander("📚 Competitor gap report"):
 if result: st.write(result.get("competitors",{}).get("gap_report","No report."))
 else: st.info("Run research first.")

st.subheader("🕘 History")
runs=database.list_runs()
if runs:
 for rid,created,n,_w in runs:
  st.write(f"Run #{rid} · {n} · {pd.to_datetime(created,unit='s')}")
  if st.button(f"Load run #{rid}",key=f"load_{rid}"):
   x=database.get_run(rid); st.session_state["result"]=x["payload"]; st.session_state["run_id"]=rid; st.rerun()
else: st.caption("No saved runs yet.")

st.divider(); st.caption("Nexus IdeaScout is a research assistant, not a sales predictor. Free-source access can be rate-limited or incomplete; verify every important claim manually.")
