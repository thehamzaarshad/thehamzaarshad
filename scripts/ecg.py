import os, json, math, datetime, urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
W, H, BASE = 1200, 240, 130
SPEED = 240  # px/sec scroll speed (72 BPM => 200px per beat)

# ---------------------------------------------------------------- data
req = urllib.request.Request(
    f"https://api.github.com/users/{USER}/events/public?per_page=100",
    headers={"Authorization": f"Bearer {TOKEN}"})
events = json.load(urllib.request.urlopen(req))
now = datetime.datetime.now(datetime.timezone.utc)
times = [datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) for e in events]
hours = (now - max(times)).total_seconds() / 3600 if times else 9999
n24 = sum(1 for t in times if (now - t).total_seconds() < 86400)

if not times: ago = "30d+"
elif hours < 1: ago = "just now"
elif hours < 48: ago = f"{int(hours)}h"
else: ago = f"{int(hours // 24)}d"

# ---------------------------------------------------------- diagnosis
# state: (label, colour1, colour2, blink-seconds)
if hours >= 168:                       # 7+ days  -> dead
    state = "FLATLINE"
elif hours >= 72:                      # 3-7 days -> irregular, unstable
    state = "ARRHYTHMIA"
elif hours >= 24:                      # 1-3 days -> slow, weak
    state = "BRADYCARDIA"
elif n24 >= 14:                        # very busy -> fast
    state = "TACHYCARDIA"
else:                                  # normal sinus rhythm
    state = "NORMAL"

STYLE = {
    "NORMAL":      ("#22d3a0", "#38bdf8", 1.2),
    "TACHYCARDIA": ("#fbbf24", "#f97316", 0.6),
    "BRADYCARDIA": ("#fb923c", "#f59e0b", 1.8),
    "ARRHYTHMIA":  ("#ff6b4a", "#ef4444", 0.5),
    "FLATLINE":    ("#ff4d5e", "#ff8a5e", 0),
}
C, C2, blink = STYLE[state]

# ---------------------------------------------------------- waveforms
SHAPE = [(0,0),(40,0),(52,-8),(64,0),(80,0),(88,10),(96,-64),(106,28),
         (114,0),(140,0),(152,-14),(168,0),(200,0)]          # P-QRS-T
PVC = [(0,0),(20,-6),(44,-78),(70,52),(92,26),(120,-18),(150,-6),(170,0)]  # wide ectopic beat

def beat(x0, spacing, amp=1.0):
    sx = min(1.0, spacing / 200)
    pts = [(x0 + dx * sx, BASE + dy * amp) for dx, dy in SHAPE]
    pts.append((x0 + spacing, BASE))
    return pts

def pvc(x0, amp=1.0):
    return [(x0 + dx, BASE + dy * amp) for dx, dy in PVC]

def build_pattern():
    """Returns list of (kind, spacing, amp). One full pattern loops seamlessly."""
    if state == "NORMAL":
        bpm = 60 + n24 * 3                       # 1 event -> 63 bpm ... 13 events -> 99 bpm
        return [("n", 14400 / bpm, 1.0)]
    if state == "TACHYCARDIA":
        bpm = min(160, 100 + (n24 - 13) * 4)     # more activity -> faster
        return [("n", 14400 / bpm, 0.9)]
    if state == "BRADYCARDIA":
        return [("n", 300, 0.75)]                # ~48 bpm, weaker amplitude
    if state == "ARRHYTHMIA":                    # irregular spacing + ectopic beat + low amplitude
        return [("n", 300, 0.55), ("p", 170, 0.9), ("n", 420, 0.5),
                ("n", 240, 0.6), ("n", 520, 0.45)]
    return []

pattern = build_pattern()

if pattern:
    L = sum(s for _, s, _ in pattern)
    bpm = round(len(pattern) * 60 / (L / SPEED))
    reps = math.ceil(W / L) + 2
    pts = ["M0,%d" % BASE]
    x = 0.0
    for _ in range(reps):
        for kind, sp, amp in pattern:
            seg = pvc(x, amp) if kind == "p" else beat(x, sp, amp)
            for px, py in seg:
                pts.append(f"L{px:.1f},{py:.1f}")
            x += sp
    wave = " ".join(pts)
    dur = L / SPEED
    trace = f'''
<g mask="url(#fade)">
 <g>
  <path d="{wave}" stroke="{C}" stroke-width="7" fill="none" opacity=".35" filter="url(#glow)" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{wave}" stroke="url(#line)" stroke-width="3" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  <animateTransform attributeName="transform" type="translate" from="0 0" to="-{L:.1f} 0" dur="{dur:.2f}s" repeatCount="indefinite"/>
 </g>
</g>'''
    sub = f"Last activity {ago} ago · {n24} in 24h"
    badge_anim = f'<animate attributeName="opacity" values="1;.25;1" dur="{blink}s" repeatCount="indefinite"/>'
else:
    bpm = 0
    trace = f'''
<g mask="url(#fade)">
 <path d="M0,{BASE} L{W},{BASE}" stroke="{C}" stroke-width="7" fill="none" opacity=".3" filter="url(#glow)"/>
 <path d="M0,{BASE} L{W},{BASE}" stroke="{C}" stroke-width="3" fill="none" stroke-dasharray="14 10">
  <animate attributeName="opacity" values="1;.35;1" dur="2s" repeatCount="indefinite"/>
 </path>
</g>'''
    sub = f"No activity for {ago}"
    badge_anim = ""

label = state
lw = 34 + len(label) * 11

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
 <rect x="30" y="206" width="{lw}" height="26" rx="13" fill="{C}" fill-opacity=".14" stroke="{C}" stroke-opacity=".5"/>
 <text x="{30 + lw//2}" y="224" fill="{C}" font-size="13" font-weight="700" text-anchor="middle" letter-spacing="2">{label}</text>
 <text x="{W-30}" y="224" fill="#8b98a8" font-size="14" text-anchor="end" font-family="ui-monospace,Consolas,monospace">{sub} · @{USER}</text>
</g>
</svg>'''
os.makedirs("assets", exist_ok=True)
open("assets/ecg.svg", "w").write(svg)
