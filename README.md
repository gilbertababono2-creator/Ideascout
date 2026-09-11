# Nexus IdeaScout V2

Nexus IdeaScout V2 is a free-tier market-research assistant for freelancers and real-estate operators. It discovers Reddit pain points, measures Google Trends velocity, analyzes competitors, asks Groq to generate and score product opportunities, stores research runs locally in SQLite, and lets you rescore cached ideas with different weights.

## What changed from V1
- Real Reddit evidence + 3–5 community quotes per idea where evidence allows.
- PRAW support when Reddit credentials are configured; public JSON fallback when they are not.
- Idea-specific Google Trends keywords, recent velocity score (1–10), Rising/Flat/Declining direction, and sparkline.
- Competitor URLs/names plus pasted notes; Groq extracts price/features/audience/stated weaknesses and produces a gap report.
- Structured source evidence and CSV columns requested for Notion/Sheets.
- SQLite history with timestamp, niche, weights, cached evidence and scores.
- Load previous runs and rescore locally without refetching the research data.
- JSON niche profiles in `profiles.json`.
- Manual validation checklist and honest no-guarantee banner.

## Local setup
1. Create a Python 3.11+ environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`.
4. Optional: set Reddit credentials for PRAW.
5. `streamlit run app.py`

## Streamlit Community Cloud
Push this folder to GitHub and deploy `app.py`. In Streamlit Cloud Settings -> Secrets, add the values from `.streamlit/secrets.toml.example`.

SQLite is local to the app filesystem. Streamlit Community Cloud storage is not a durable database, so history can disappear after a rebuild/restart. For durable multi-user history, move the database to a hosted Postgres/Supabase/Neon service later.

## Free-source limitations
- Reddit and Google Trends access can be rate-limited or blocked from cloud IPs.
- DuckDuckGo search availability can change.
- JavaScript-heavy competitor sites may not expose useful HTML to `requests`.
- Groq free-tier limits change; this app retries 429s and falls back to the smaller model.
- Trend velocity is a heuristic, not a forecasting model.
- LLM scores are judgments, not market facts.

## Testing checklist
- Start with `real estate lead follow up`.
- Test with no Reddit credentials; verify graceful fallback/manual paste.
- Test with Reddit credentials; verify posts contain permalink/upvotes.
- Run 3 trend keywords and confirm direction/velocity.
- Add 2 competitor URLs and paste one review excerpt.
- Export CSV and import it into Google Sheets/Notion.
- Load a previous History run and change weights; confirm ideas are rescored without new source fetches.
