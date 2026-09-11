import json, os, random, time, logging
from typing import Any
from groq import Groq, RateLimitError, APIConnectionError, APIStatusError

log=logging.getLogger(__name__)
PRIMARY_MODEL="llama-3.3-70b-versatile"
FALLBACK_MODEL="llama-3.1-8b-instant"

class GroqClientError(RuntimeError): pass

def _key():
    key=os.getenv("GROQ_API_KEY", "")
    if key: return key
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY", "")
    except Exception: return ""

class GroqClient:
    def __init__(self):
        key=_key()
        if not key: raise GroqClientError("GROQ_API_KEY is missing. Add it to Streamlit Secrets or your .env file.")
        self.client=Groq(api_key=key)

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: int=3000):
        last=None
        for model in (PRIMARY_MODEL,FALLBACK_MODEL):
            for attempt in range(4):
                try:
                    r=self.client.chat.completions.create(model=model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],response_format={"type":"json_object"},temperature=0.2,max_completion_tokens=max_tokens)
                    raw=r.choices[0].message.content or "{}"
                    return json.loads(raw)
                except RateLimitError as exc:
                    last=exc; wait=min(30,2**attempt+random.random()); time.sleep(wait)
                except (APIConnectionError,APIStatusError, json.JSONDecodeError) as exc:
                    last=exc; time.sleep(min(12,2**attempt))
            log.warning("Groq model %s exhausted; trying fallback.",model)
        raise GroqClientError(f"Groq failed after retries: {last}")
