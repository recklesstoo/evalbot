"""EvalBot experimental local signal-only HTTP service; Python standard library."""
import json, math, os, threading
from collections import defaultdict, deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.getenv("EVALBOT_HOST", "127.0.0.1")
PORT = int(os.getenv("EVALBOT_PORT", "8765"))
TOKEN = os.getenv("EVALBOT_TOKEN", "dev-local-change-me")
BARS = defaultdict(lambda: deque(maxlen=10000))
SIGNALS = deque(maxlen=200)
LOCK = threading.Lock()
LOG_DIR = Path(os.getenv("EVALBOT_LOG_DIR", str(Path(__file__).resolve().parents[1] / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

def atr(bars, n=14):
    if len(bars) < n + 1: return None
    return sum(max(b["high"]-b["low"], abs(b["high"]-a["close"]), abs(b["low"]-a["close"])) for a,b in zip(bars[-n-1:-1],bars[-n:]))/n

def ema(values,n):
    e=values[0]; alpha=2/(n+1)
    for v in values[1:]: e+=alpha*(v-e)
    return e

def regime(bars):
    if len(bars)<60: return "WARMUP"
    a=atr(bars)
    if not a: return "WAIT"
    c=[b["close"] for b in bars]
    slope=(ema(c[-21:],20)-ema(c[-41:-20],20))/a
    return "TREND_UP" if slope>1.5 else "TREND_DOWN" if slope< -1.5 else "RANGE"

def analyze(bars):
    if len(bars)<60: return None
    now=bars[-1]; prev=bars[-21:-1]; a=atr(bars)
    if not a: return None
    hi=max(b["high"] for b in prev); lo=min(b["low"] for b in prev)
    side="LONG" if now["low"]<lo-now["tick_size"] and now["close"]>lo and now["close"]>now["open"] else "SHORT" if now["high"]>hi+now["tick_size"] and now["close"]<hi and now["close"]<now["open"] else None
    mode=regime(bars)
    if not side or (side=="LONG" and mode=="TREND_DOWN") or (side=="SHORT" and mode=="TREND_UP"): return None
    step=now["tick_size"]; distance=math.ceil(max(1.5*a,4*step)/step)*step
    entry=now["close"]; sign=1 if side=="LONG" else -1
    return dict(symbol=now["symbol"],timestamp=now["timestamp"],side=side,regime=mode,entry_reference=entry,stop_reference=round(entry-sign*distance,8),target_reference=round(entry+sign*2*distance,8),status="MANUAL_REVIEW",model="deterministic_v0.1",probability=None)

def validate(obj):
    fields=("symbol","timestamp","open","high","low","close","volume","tick_size")
    if not isinstance(obj,dict) or any(k not in obj for k in fields): raise ValueError("Missing fields")
    if not isinstance(obj["symbol"],str) or not 1<=len(obj["symbol"])<=32: raise ValueError("Invalid symbol")
    dt=datetime.fromisoformat(obj["timestamp"].replace("Z","+00:00"))
    if dt.tzinfo is None: raise ValueError("Timestamp timezone required")
    for k in fields[2:]:
        v=obj[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError("Invalid "+k)
    if obj["tick_size"]<=0 or obj["volume"]<0 or obj["high"]<max(obj["open"],obj["close"],obj["low"]) or obj["low"]>min(obj["open"],obj["close"]): raise ValueError("Invalid OHLCV")
    return {k:obj[k] for k in fields}

def ingest(payload):
    bar=validate(payload)
    with LOCK:
        seq=BARS[bar["symbol"]]
        if seq and bar["timestamp"]<=seq[-1]["timestamp"]: return {"accepted":False,"reason":"duplicate_or_out_of_order"}
        seq.append(bar)
        with (LOG_DIR/"bars.jsonl").open("a",encoding="utf8") as f: f.write(json.dumps(bar)+"\n")
        signal=analyze(list(seq))
        if signal:
            SIGNALS.appendleft(signal)
            with (LOG_DIR/"signals.jsonl").open("a",encoding="utf8") as f: f.write(json.dumps(signal)+"\n")
        return {"accepted":True,"regime":regime(list(seq)),"signal":signal}

HTML='''<!doctype html><html lang="es"><meta charset="utf-8"><title>EvalBot AI</title><style>body{font:16px system-ui;background:#111b2b;color:#eee;max-width:960px;margin:40px auto}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #456}small{color:#bbb}</style><h1>EvalBot AI — Solo señales</h1><p id="state">Esperando datos…</p><table><thead><tr><th>UTC</th><th>Símbolo</th><th>Señal</th><th>Régimen</th><th>Entrada</th><th>SL</th><th>TP</th></tr></thead><tbody id="rows"></tbody></table><small>Experimental. Confirmación manual. Sin envío de órdenes.</small><script>async function refresh(){try{let d=await(await fetch("/api/state")).json();document.getElementById("state").textContent=JSON.stringify(d.symbols);document.getElementById("rows").replaceChildren(...d.signals.map(s=>{let tr=document.createElement("tr");for(let k of ["timestamp","symbol","side","regime","entry_reference","stop_reference","target_reference"]){let td=document.createElement("td");td.textContent=s[k];tr.append(td)}return tr}))}catch(e){document.getElementById("state").textContent="Sin conexión"}}refresh();setInterval(refresh,3000)</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def respond(self, obj, status=200, content_type="application/json"):
        raw=obj.encode("utf8") if isinstance(obj,str) else json.dumps(obj).encode("utf8")
        self.send_response(status);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=="/": return self.respond(HTML,content_type="text/html; charset=utf-8")
        if self.path=="/health": return self.respond({"ok":True,"mode":"SIGNALS_ONLY"})
        if self.path=="/api/state":
            with LOCK: data={"symbols":{s:{"bars":len(v),"regime":regime(list(v)),"last_timestamp":v[-1]["timestamp"] if v else None} for s,v in BARS.items()},"signals":list(SIGNALS)}
            return self.respond(data)
        return self.respond({"error":"not_found"},404)
    def do_POST(self):
        if self.path!="/api/bar": return self.respond({"error":"not_found"},404)
        if self.headers.get("X-EvalBot-Token")!=TOKEN: return self.respond({"error":"unauthorized"},401)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<8192: return self.respond({"error":"invalid_length"},400)
            return self.respond(ingest(json.loads(self.rfile.read(length))))
        except (ValueError,TypeError,KeyError) as e: return self.respond({"error":str(e)},400)

if __name__=="__main__":
    print("EvalBot signal-only:",HOST,PORT)
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
