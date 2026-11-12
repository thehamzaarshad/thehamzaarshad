import os, json, datetime, urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
LIMIT_H = 24
W, H, BASE = 1200, 240, 130

req = urllib.request.Request(
    f"https://api.github.com/users/{USER}/events/public",
    headers={"Authorization": f"Bearer {TOKEN}"})
events = json.load(urllib.request.urlopen(req))
now = datetime.datetime.now(datetime.timezone.utc)
times = [datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) for e in events]
hours = (now - max(times)).total_seconds() / 3600 if times else 9999
alive = hours < LIMIT_H

if hours < 1: ago = "just now"
elif hours < 48: ago = f"{int(hours)}h ago"
else: ago = f"{int(hours // 24)}d ago"

beat = [(0,0),(40,0),(52,-8),(64,0),(80,0),(88,10),(96,-64),(106,28),(114,0),(140,0),(152,-14),(168,0),(200,0)]
pts = ["M0,%d" % BASE]
for i in range(10):
    for dx, dy in beat:
        pts.append(f"L{i*200+dx},{BASE+dy}")
wave = " ".join(pts)

C = "#22d3a0" if alive else "#ff4d5e"
C2 = "#38bdf8" if alive else "#ff8a5e"

if alive:
    trace = f'''
<g mask="url(#fade)">
 <g>
  <path d="{wave}" stroke="{C}" stroke-width="7" fill="none" opacity=".35" filter="url(#glow)" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{wave}" stroke="url(#line)" stroke-width="3" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  <animateTransform attributeName="transform" type="translate" from="0 0" to="-600 0" dur="3s" repeatCount="indefinite"/>
 </g>
</g>'''
    bpm, label, sub = "72", "ALIVE", f"Last activity {ago}"
    badge_anim = '<animate attributeName="opacity" values="1;.25;1" dur="1.2s" repeatCount="indefinite"/>'
else:
    trace = f'''
<g mask="url(#fade)">
 <path d="M0,{BASE} L{W},{BASE}" stroke="{C}" stroke-width="7" fill="none" opacity=".3" filter="url(#glow)"/>
 <path d="M0,{BASE} L{W},{BASE}" stroke="{C}" stroke-width="3" fill="none" stroke-dasharray="14 10">
  <animate attributeName="opacity" values="1;.35;1" dur="2s" repeatCount="indefinite"/>
 </path>
</g>'''
    bpm, label, sub = "0", "FLATLINE", f"No activity for {ago.replace(' ago','')}"
    badge_anim = ""

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#070b12"/>
 </linearGradient>
 <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C}" stop-opacity=".7"/><stop offset="1" stop-color="{C2}" stop-opacity=".7"/>
 </linearGradient>
 <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C}"/><stop offset="1" stop-color="{C2}"/>
 </linearGradient>
 <linearGradient id="m" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#000"/><stop offset=".1" stop-color="#fff"/>
  <stop offset=".9" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
 </linearGradient>
 <mask id="fade"><rect x="0" y="70" width="{W}" height="130" fill="url(#m)"/></mask>
 <radialGradient id="halo" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="{C}" stop-opacity=".18"/><stop offset="1" stop-color="{C}" stop-opacity="0"/>
 </radialGradient>
 <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse" y="10">
  <path d="M30,0 L0,0 L0,30" fill="none" stroke="#ffffff" stroke-opacity=".045"/>
 </pattern>
 <filter id="glow" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
</defs>

<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="20" fill="url(#bg)" stroke="url(#stroke)" stroke-width="1.5"/>
<ellipse cx="600" cy="{BASE}" rx="560" ry="90" fill="url(#halo)"/>
<rect x="20" y="70" width="{W-40}" height="130" fill="url(#grid)"/>

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <circle cx="44" cy="40" r="6" fill="{C}">{badge_anim}</circle>
 <text x="60" y="46" fill="#e6edf3" font-size="20" font-weight="700" letter-spacing="3">CONTRIBUTION PULSE</text>
 <text x="{W-40}" y="40" fill="{C}" font-size="34" font-weight="800" text-anchor="end" font-family="ui-monospace,Consolas,monospace">{bpm}<tspan fill="#8b98a8" font-size="14" font-weight="600" dx="6">BPM</tspan></text>
</g>

{trace}

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <rect x="30" y="206" width="{34 + len(label)*11}" height="26" rx="13" fill="{C}" fill-opacity=".14" stroke="{C}" stroke-opacity=".5"/>
 <text x="{30 + (34 + len(label)*11)//2}" y="224" fill="{C}" font-size="13" font-weight="700" text-anchor="middle" letter-spacing="2">{label}</text>
 <text x="{W-30}" y="224" fill="#8b98a8" font-size="14" text-anchor="end" font-family="ui-monospace,Consolas,monospace">{sub} · @{USER}</text>
</g>
</svg>'''
os.makedirs("assets", exist_ok=True)
open("assets/ecg.svg", "w").write(svg)