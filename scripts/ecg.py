import os, json, datetime, urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
LIMIT_H = 24          # itne ghante baad flatline
W, H, BASE, BEAT = 1200, 140, 70, 200

req = urllib.request.Request(
    f"https://api.github.com/users/{USER}/events/public",
    headers={"Authorization": f"Bearer {TOKEN}"})
events = json.load(urllib.request.urlopen(req))
now = datetime.datetime.now(datetime.timezone.utc)
times = [datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) for e in events]
hours = (now - max(times)).total_seconds() / 3600 if times else 9999
alive = hours < LIMIT_H

pts = [(60,0),(66,-6),(72,0),(90,0),(94,8),(99,-50),(104,16),(109,0),(125,0),(132,-9),(140,0),(BEAT,0)]
green = [f"M0,{BASE}"]
for i in range(W // BEAT):
    for dx, dy in pts:
        green.append(f"L{i*BEAT+dx},{BASE+dy}")
path = " ".join(green)
red = f"M0,{BASE} L{W},{BASE}"

grid = "".join(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#12301f"/>' for x in range(0, W+1, 40))
grid += "".join(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#12301f"/>' for y in range(10, H, 30))

if alive:
    body = f'''<defs><clipPath id="c"><rect x="0" y="0" height="{H}" width="0">
<animate attributeName="width" from="0" to="{W}" dur="6s" repeatCount="indefinite"/></rect></clipPath></defs>
<g clip-path="url(#c)"><path d="{path}" stroke="#22c55e" stroke-width="2.5" fill="none" stroke-linejoin="round"/></g>
<circle r="4" fill="#fff"><animateMotion dur="6s" repeatCount="indefinite" path="{path}"/></circle>'''
    status, col = f"ALIVE · LAST ACTIVITY {int(hours)}H AGO", "#22c55e"
else:
    body = f'<path d="{red}" stroke="#ef4444" stroke-width="2.5" fill="none"/>'
    status, col = f"FLATLINE · NO ACTIVITY FOR {int(hours)}H", "#ef4444"

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H+40}" width="100%">
<rect width="{W}" height="{H+40}" fill="#0b0f14" rx="10"/>
<g>{grid}</g>
{body}
<text x="12" y="{H+26}" fill="{col}" font-family="monospace" font-size="16" font-weight="bold">{status}</text>
</svg>'''
os.makedirs("assets", exist_ok=True)
open("assets/ecg.svg", "w").write(svg)