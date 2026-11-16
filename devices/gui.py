"""Tiny embedded web GUI for a device. Standard library only (no extra deps), runs in a
daemon thread so it never blocks the device loop. Each device opts in with --gui PORT.

    run_gui(port, title, kind, state_fn, actions)

- state_fn()  -> a dict of {label: value}; booleans render as On/Off pills, numbers as
                 values, a "temperature" key also gets a live sparkline.
- actions     -> {button label: callable()}; each POST /action/<label> runs it, then the
                 page re-reads state. Parameterless, so it works the same on every device.

This is the Level-1 stand-in for the self-hosted page a real ESP32 would serve.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
 :root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#6b7685;--line:#e2e6eb;--accent:#2563eb;--ok:#16a34a;--bad:#dc2626}
 @media(prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1a2029;--ink:#e7ebf0;--mute:#8d99a8;--line:#2a323d;--accent:#60a5fa;--ok:#4ade80;--bad:#f87171}}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 system-ui,sans-serif}
 main{max-width:440px;margin:0 auto;padding:28px 18px}
 header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
 h1{font-size:20px;margin:0}.badge{font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--mute);border:1px solid var(--line);border-radius:99px;padding:2px 9px}
 .mute{color:var(--mute);font-size:13px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--bad);margin-right:6px}.dot.ok{background:var(--ok)}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-top:16px}
 .stat{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-top:1px solid var(--line)}.stat:first-child{border-top:0}
 .k{font-size:13px;color:var(--mute);text-transform:capitalize}.v{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}
 .pill{display:inline-block;padding:3px 12px;border-radius:99px;font-size:15px;font-weight:600;border:1px solid var(--line);color:var(--mute)}.pill.on{color:var(--ok);border-color:var(--ok)}
 svg{width:100%;height:56px;display:block;margin-top:8px}svg polyline{fill:none;stroke:var(--accent);stroke-width:2}
 .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
 button{font:inherit;padding:8px 16px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer;font-weight:600}
 button:hover{border-color:var(--accent)}button:active{transform:translateY(1px)}
</style></head><body><main>
 <header><h1>%%TITLE%%</h1><span class="badge">%%KIND%%</span></header>
 <div class="mute"><span class="dot" id="dot"></span><span id="conn">connecting</span></div>
 <div class="card" id="stats"></div>
 <div class="card" id="controls" style="display:none"><div class="k" style="margin-bottom:10px">Controls</div><div class="row" id="btns"></div></div>
<script>
 const ACTIONS = %%ACTIONS%%;
 const $ = (id)=>document.getElementById(id); const hist=[];
 async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(r.status);const t=await r.text();return t?JSON.parse(t):null;}
 function render(s){
   const box=$("stats"); box.replaceChildren();
   for(const [k,v] of Object.entries(s)){
     const row=document.createElement("div"); row.className="stat";
     const kk=document.createElement("span"); kk.className="k"; kk.textContent=k;
     const vv=document.createElement("span");
     if(typeof v==="boolean"){vv.className="pill"+(v?" on":"");vv.textContent=v?"On":"Off";}
     else{vv.className="v";vv.textContent=(typeof v==="number")?(Number.isInteger(v)?v:v.toFixed(1)):v;}
     row.append(kk,vv); box.append(row);
   }
   if(typeof s.temperature==="number"){
     hist.push(s.temperature); if(hist.length>60)hist.shift();
     const lo=Math.min(...hist),hi=Math.max(...hist),sp=Math.max(hi-lo,1);
     const pts=hist.map((x,i)=>`${(i/Math.max(hist.length-1,1))*200},${52-((x-lo)/sp)*46}`).join(" ");
     const svg=`<svg viewBox="0 0 200 56" preserveAspectRatio="none"><polyline points="${pts}"/></svg>`;
     box.insertAdjacentHTML("beforeend",svg);
   }
 }
 async function poll(){try{const s=await j("/state");render(s);$("dot").className="dot ok";$("conn").textContent="live";}
   catch(e){$("dot").className="dot";$("conn").textContent="offline";}}
 function mkButtons(){if(!ACTIONS.length)return;$("controls").style.display="";
   $("btns").replaceChildren(...ACTIONS.map((name)=>{const b=document.createElement("button");b.textContent=name;
     b.onclick=async()=>{try{await j("/action/"+encodeURIComponent(name),{method:"POST"});poll();}catch(e){$("conn").textContent="command failed";}};return b;}));}
 mkButtons(); poll(); setInterval(poll,1500);
</script></main></body></html>"""


def run_gui(port, title, kind, state_fn, actions=None, host="0.0.0.0"):
    actions = actions or {}
    page = (_PAGE.replace("%%TITLE%%", title).replace("%%KIND%%", kind)
            .replace("%%ACTIONS%%", json.dumps(list(actions.keys()))))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the device console quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/" or self.path == "":
                self._send(200, page, "text/html")
            elif self.path == "/state":
                self._send(200, json.dumps(state_fn()))
            else:
                self._send(404, "{}")

        def do_POST(self):
            if self.path.startswith("/action/"):
                name = unquote(self.path[len("/action/"):])
                fn = actions.get(name)
                if fn:
                    fn()
                    return self._send(200, json.dumps(state_fn()))
            self._send(404, "{}")

    srv = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"gui on http://{host}:{port}", flush=True)
    return srv
