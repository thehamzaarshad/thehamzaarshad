import os, json, datetime, urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
DAYS = 30
W, H, BASE = 40, 140, 70

now = datetime.datetime.utcnow()
q = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
vars_ = {"login": USER,
         "from": (now - datetime.timedelta(days=DAYS + 2)).strftime("%Y-%m-%dT00:00:00Z"),
         "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps({"query": q, "variables": vars_}).encode(),
    headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
res = json.load(urllib.request.urlopen(req))
weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
days = sorted((d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"])
days = days[-DAYS:]

green, red = [f"M0,{BASE}"], []
for i, (date, c) in enumerate(days):
    x = i * W
    if c > 0:
        a = min(50, 18 + c * 4)
        pts = [(8, 0), (11, -6), (14, 0), (17, 0), (19, 8), (22, -a),
               (25, a * 0.4), (28, 0), (31, 0), (34, -7), (37, 0), (W, 0)]
        for dx, dy in pts:
            green.append(f"L{x+dx},{BASE+dy:.1f}")
    else:
        green.append(f"L{x+W},{BASE}")
        red.append(f"M{x},{BASE} L{x+W},{BASE}")

total = DAYS * W
today_c = days[-1][1]
streak = 0
for _, c in reversed(days):
    if c > 0: streak += 1
    else: break
active_days = sum(1 for _, c in days if c > 0)
total_contrib = sum(c for _, c in days)
active = today_c > 0
status = f"ACTIVE TODAY · {today_c} CONTRIBUTIONS" if active else "NO ACTIVITY TODAY"
scol = "#22c55e" if active else "#ef4444"
path = " ".join(green)

grid = "".join(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#12301f" stroke-width="1"/>' for x in range(0, total + 1, W))
grid += "".join(f'<line x1="0" y1="{y}" x2="{total}" y2="{y}" stroke="#12301f" stroke-width="1"/>' for y in range(10, H, 30))
redpaths = "".join(f'<path d="{r}" stroke="#ef4444" stroke-width="2.5" fill="none"/>' for r in red)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {H+40}" width="100%">
<rect width="{total}" height="{H+40}" fill="#0b0f14" rx="10"/>
<g>{grid}</g>
<defs><clipPath id="c"><rect x="0" y="0" height="{H}" width="0">
<animate attributeName="width" from="0" to="{total}" dur="6s" repeatCount="indefinite"/></rect></clipPath></defs>
<g clip-path="url(#c)">
<path d="{path}" stroke="#22c55e" stroke-width="2.5" fill="none" stroke-linejoin="round"/>
{redpaths}
</g>
<circle r="4" fill="#fff"><animateMotion dur="6s" repeatCount="indefinite" path="{path}"/></circle>
<text x="12" y="{H+26}" fill="{scol}" font-family="monospace" font-size="16" font-weight="bold">{status}</text>
<text x="{total-12}" y="{H+26}" fill="#94a3b8" font-family="monospace" font-size="14" text-anchor="end">Streak: {streak} days · Active: {active_days}/{DAYS} days · Total: {total_contrib}</text>
</svg>'''
os.makedirs("assets", exist_ok=True)
open("assets/ecg.svg", "w").write(svg)
