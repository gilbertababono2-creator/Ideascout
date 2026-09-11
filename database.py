import json, sqlite3, time
from pathlib import Path
from typing import Any, Dict, List
DB=Path(__file__).with_name("nexus_history.db")

def conn():
    c=sqlite3.connect(DB); c.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, niche TEXT, weights TEXT, payload TEXT)"); c.commit(); return c

def save_run(niche:str,weights:Dict[str,float],payload:Dict[str,Any])->int:
    with conn() as c:
        cur=c.execute("INSERT INTO runs(created_at,niche,weights,payload) VALUES(?,?,?,?)",(time.time(),niche,json.dumps(weights),json.dumps(payload)))
        c.commit(); return cur.lastrowid

def list_runs(limit=30):
    with conn() as c:
        return c.execute("SELECT id,created_at,niche,weights FROM runs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()

def get_run(run_id:int):
    with conn() as c:
        row=c.execute("SELECT id,created_at,niche,weights,payload FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row:return None
    return {"id":row[0],"created_at":row[1],"niche":row[2],"weights":json.loads(row[3]),"payload":json.loads(row[4])}

def clear_history():
    with conn() as c:c.execute("DELETE FROM runs"); c.commit()
