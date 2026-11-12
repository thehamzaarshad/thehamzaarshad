"""
Contribution Pulse - patient-monitor style GitHub activity card.

Activity  -> heart rate (continuous, decays like a real vital sign)
Inactivity -> bradycardia -> irregular rhythm -> asystole (flatline)
Output    -> assets/ecg.svg  (animated SVG, works inside a GitHub README)
"""
import os, json, math, random, datetime, urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]

W, H = 1200, 340            # canvas
TX, TW = 24, 832            # trace panel x / width
ECG_Y, PPG_Y = 170, 292     # baselines of the two traces
SPEED = 240.0               # scroll speed px/s  (72 bpm -> 200 px per beat)

# ------------------------------------------------------------------ data
def fetch_events():
    out = []
    for page in (1, 2, 3):
        req = urllib.request.Request(
            f"https://api.github.com/users/{USER}/events/public?per_page=100&page={page}",
            headers={"Authorization": f"Bearer {TOKEN}",
                     "Accept": "application/vnd.github+json"})
        batch = json.load(urllib.request.urlopen(req))
        out += batch
        if len(batch) < 100:
            break
    return out

events = fetch_events()
now = datetime.datetime.now(datetime.timezone.utc)

WEIGHT = {"PushEvent": 1.0, "PullRequestEvent": 1.6, "PullRequestReviewEvent": 1.2,
          "IssuesEvent": 0.8, "IssueCommentEvent": 0.6, "CreateEvent": 0.6}
rows = []
for e in events:
    t = datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
    rows.append(((now - t).total_seconds() / 3600, t, e))

hours = min((r[0] for r in rows), default=9999.0)
score = sum(WEIGHT.get(e["type"], 0.4) * math.exp(-age / 30) for age, _, e in rows)
n24 = sum(1 for age, _, _ in rows if age < 24)
repos7 = len({e.get("repo", {}).get("name") for age, _, e in rows if age < 168})
days = {t.date() for _, t, _ in rows}
d = now.date()
if d not in days:
    d -= datetime.timedelta(days=1)
streak = 0
while d in days:
    streak += 1
    d -= datetime.timedelta(days=1)

# ------------------------------------------------------------ diagnosis
clamp = lambda v, a, b: max(a, min(b, v))
asystole = hours >= 168

if asystole:
    bpm, ir = 0, 1.0
else:
    bpm = 40 + 50 * (1 - math.exp(-score / 3)) + 1.5 * max(0, score - 20)
    if hours > 48:                                   # fading out
        bpm *= 1 - 0.75 * (hours - 48) / 120
    bpm = int(round(clamp(bpm, 10, 150)))
    ir = clamp((hours - 48) / 120, 0, 1)             # rhythm irregularity 0..1

LOW_W, HIGH_W, LOW_C, HIGH_C = 50, 120, 40, 140
if asystole:
    level, alarm, rhythm = 2, "ASYSTOLE - NO ACTIVITY", "ASYSTOLE"
else:
    if bpm < LOW_C:      level, alarm = 2, "HR CRITICAL LOW"
    elif bpm >= HIGH_C:  level, alarm = 2, "HR CRITICAL HIGH"
    elif bpm < LOW_W:    level, alarm = 1, "HR TOO LOW"
    elif bpm >= HIGH_W:  level, alarm = 1, "HR TOO HIGH"
    elif ir > 0.3:       level, alarm = 1, "IRREGULAR RHYTHM"
    else:                level, alarm = 0, None
    if ir > 0.3:     rhythm = "IRREGULAR RHYTHM"
    elif bpm < 60:   rhythm = "BRADYCARDIA"
    elif bpm >= 100: rhythm = "TACHYCARDIA"
    else:            rhythm = "NORMAL SINUS RHYTHM"

C, C2 = {0: ("#22d3a0", "#38bdf8"),
         1: ("#fbbf24", "#fb923c"),
         2: ("#ff4d5e", "#ff8a5e")}[level]

# ------------------------------------------------------------ waveforms
rng = random.Random(7)
g = lambda dx, c, w: math.exp(-((dx - c) / w) ** 2)

beats = []                                           # dicts: x0, sp, pvc, amp, r0
if asystole:
    L = 960.0
else:
    base = 14400.0 / bpm
    nb = int(clamp(round(1800 / base), 2, 12))
    pvc = set()
    if ir > 0.3 and nb >= 4:
        pvc.add(rng.randrange(1, nb - 1))
        if ir > 0.7 and nb >= 7:
            pvc.add(rng.randrange(1, nb - 1))
    x = 0.0
    for i in range(nb):
        if i + 1 in pvc:   sp = base * 0.62          # premature beat follows
        elif i in pvc:     sp = base * 1.40          # compensatory pause
        else:              sp = base * (1 + rng.uniform(-1, 1) * (0.03 + 0.40 * ir))
        amp = (1 - 0.40 * ir) * (1 + rng.uniform(-0.05, 0.05))
        is_pvc = i in pvc
        r0 = 40.0 if is_pvc else min(96.0, 0.48 * sp)
        beats.append(dict(x0=x, sp=sp, pvc=is_pvc, amp=1.0 if is_pvc else amp, r0=r0))
        x += sp
    L = x

noise_amp = 0.9 + 2.6 * ir
NOISE = [(max(1, round(L / p)), rng.uniform(0, 6.283), rng.uniform(.5, 1.0))
         for p in (6, 9, 13, 19, 27, 41)]
m_wander = max(1, round(L / 960))

def noise(x, k=1.0):
    n = sum(a * math.sin(6.283185 * m * x / L + ph) for m, ph, a in NOISE)
    n *= noise_amp * k / 2.2
    return n + 2.5 * math.sin(6.283185 * m_wander * x / L)

def ecg_y(x):
    y = 0.0
    for b in beats:
        for k in (-L, 0.0, L):
            dx = x - (b["x0"] + k)
            if dx < -80 or dx > 240:
                continue
            a, r0 = b["amp"], b["r0"]
            if b["pvc"]:
                y += -78 * a * g(dx, r0, 13) + 46 * a * g(dx, r0 + 30, 17) + 22 * a * g(dx, r0 + 78, 22)
            else:
                K = min(1.0, b["sp"] / 200) ** 0.6
                y += (-9 * a * g(dx, r0 - 51 * K, 9 * K + 2)
                      + 9 * a * g(dx, r0 - 7, 2.6)
                      - 70 * a * g(dx, r0, 3.4)
                      + 24 * a * g(dx, r0 + 8, 3.8)
                      - 17 * a * g(dx, r0 + 54 * K, 15 * K + 4))
    return ECG_Y + y + noise(x)

def ppg_y(x):
    y = 0.0
    for b in beats:
        for k in (-L, 0.0, L):
            dx = x - (b["x0"] + k) - (b["r0"] + 48)
            if dx < -60 or dx > 140:
                continue
            pa = 0.55 if b["pvc"] else b["amp"]
            y += 46 * pa * (g(dx, 0, 15) + 0.32 * g(dx, 38, 13))
    return PPG_Y - y + noise(x + 17, 0.35) * 0.6

STEP = 2.0
N = int(L / STEP)
reps = math.ceil(TW / L) + 1

def path(fn):
    ys = [fn(i * STEP) for i in range(N)]
    out = [f"M0,{ys[0]:.1f}"]
    for r in range(reps):
        for i in range(N):
            if r == 0 and i == 0:
                continue
            out.append(f"L{r * L + i * STEP:.1f},{ys[i]:.1f}")
    out.append(f"L{reps * L:.1f},{ys[0]:.1f}")
    return " ".join(out)

ecg_d, ppg_d = path(ecg_y), path(ppg_y)
dur = L / SPEED
beat_s = (60.0 / bpm) if bpm else 0

# ---------------------------------------------------------------- layout
banner = ("\u25B2 " + alarm) if alarm else rhythm
bw = int(len(banner) * 11 + 40)
if level:
    banner_svg = (f'<rect x="520" y="16" width="{bw}" height="32" rx="8" fill="{C}"'
                  f'>{"<animate attributeName=\"opacity\" values=\"1;.55;1\" dur=\"1s\" repeatCount=\"indefinite\"/>" if level == 2 else ""}</rect>'
                  f'<text x="{520 + bw // 2}" y="38" fill="{"#fff" if level == 2 else "#0b0f16"}" font-size="14" font-weight="800" '
                  f'text-anchor="middle" letter-spacing="1.5">{banner}</text>')
else:
    banner_svg = (f'<rect x="520" y="16" width="{bw}" height="32" rx="16" fill="{C}" fill-opacity=".12" stroke="{C}" stroke-opacity=".55"/>'
                  f'<text x="{520 + bw // 2}" y="38" fill="{C}" font-size="13" font-weight="700" text-anchor="middle" letter-spacing="2">{banner}</text>')

dot_anim = (f'<animate attributeName="opacity" values="1;.2;1" dur="{max(beat_s, .4):.2f}s" repeatCount="indefinite"/>' if bpm else "")
heart_anim = (f'<animateTransform attributeName="transform" type="scale" values="1;1.22;1;1" keyTimes="0;.12;.3;1" dur="{beat_s:.2f}s" repeatCount="indefinite"/>' if bpm else "")
bpm_txt = str(bpm) if bpm else "--"

def card(x, label, val, unit):
    cx = x + 46
    return (f'<rect x="{x}" y="216" width="92" height="100" rx="12" fill="#0b121c" stroke="#fff" stroke-opacity=".08"/>'
            f'<text x="{cx}" y="238" fill="#8b98a8" font-size="11" font-weight="700" text-anchor="middle" letter-spacing="2">{label}</text>'
            f'<text x="{cx}" y="284" fill="#e6edf3" font-size="40" font-weight="800" text-anchor="middle" font-family="ui-monospace,Consolas,monospace">{val}</text>'
            f'<text x="{cx}" y="304" fill="#6b7a8c" font-size="11" text-anchor="middle" letter-spacing="1">{unit}</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="100%">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#070b12"/></linearGradient>
 <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C}" stop-opacity=".7"/><stop offset="1" stop-color="{C2}" stop-opacity=".7"/></linearGradient>
 <linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C}"/><stop offset="1" stop-color="{C2}"/></linearGradient>
 <linearGradient id="m" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000"/><stop offset=".07" stop-color="#fff"/><stop offset=".93" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
 <mask id="fade"><rect x="{TX}" y="76" width="{TW}" height="240" fill="url(#m)"/></mask>
 <clipPath id="clip"><rect x="{TX}" y="80" width="{TW}" height="232"/></clipPath>
 <radialGradient id="halo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{C}" stop-opacity=".14"/><stop offset="1" stop-color="{C}" stop-opacity="0"/></radialGradient>
 <pattern id="g1" x="{TX}" y="76" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M10,0 L0,0 L0,10" fill="none" stroke="#fff" stroke-opacity=".03"/></pattern>
 <pattern id="g2" x="{TX}" y="76" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M50,0 L0,0 L0,50" fill="none" stroke="#fff" stroke-opacity=".06"/></pattern>
 <filter id="glow" x="-2%" y="-40%" width="104%" height="180%"><feGaussianBlur stdDeviation="5"/></filter>
 <path id="ecg" d="{ecg_d}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
 <path id="ppg" d="{ppg_d}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
</defs>

<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="22" fill="url(#bg)" stroke="url(#stroke)" stroke-width="1.5"/>
<ellipse cx="440" cy="{ECG_Y}" rx="430" ry="120" fill="url(#halo)"/>

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <circle cx="44" cy="34" r="6" fill="{C}">{dot_anim}</circle>
 <text x="62" y="40" fill="#e6edf3" font-size="19" font-weight="700" letter-spacing="3">CONTRIBUTION PULSE</text>
 <text x="62" y="60" fill="#6b7a8c" font-size="12" letter-spacing="1" font-family="ui-monospace,Consolas,monospace">@{USER} \u00b7 LEAD II \u00b7 {rhythm}</text>
 {banner_svg}
 <text x="{W-24}" y="40" fill="#6b7a8c" font-size="12" text-anchor="end" letter-spacing="1" font-family="ui-monospace,Consolas,monospace">UPDATED {now.strftime("%H:%M")} UTC</text>
</g>

<rect x="{TX}" y="76" width="{TW}" height="240" rx="14" fill="#070b12" fill-opacity=".7" stroke="#fff" stroke-opacity=".08"/>
<rect x="{TX}" y="76" width="{TW}" height="240" rx="14" fill="url(#g1)"/>
<rect x="{TX}" y="76" width="{TW}" height="240" rx="14" fill="url(#g2)"/>
<line x1="{TX+12}" y1="224" x2="{TX+TW-12}" y2="224" stroke="#fff" stroke-opacity=".07"/>
<g font-family="ui-monospace,Consolas,monospace" font-size="12" font-weight="700" letter-spacing="2">
 <text x="{TX+16}" y="100" fill="{C}">II</text>
 <text x="{TX+16}" y="242" fill="{C2}">PLETH</text>
</g>

<g clip-path="url(#clip)"><g mask="url(#fade)"><g transform="translate({TX},0)">
 <g>
  <use href="#ecg" xlink:href="#ecg" stroke="{C}" stroke-width="7" opacity=".35" filter="url(#glow)"/>
  <use href="#ecg" xlink:href="#ecg" stroke="url(#line)" stroke-width="2.6"/>
  <use href="#ppg" xlink:href="#ppg" stroke="{C2}" stroke-width="2.2" opacity=".9"/>
  <animateTransform attributeName="transform" type="translate" from="0 0" to="-{L:.1f} 0" dur="{dur:.2f}s" repeatCount="indefinite"/>
 </g>
</g></g></g>

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <rect x="876" y="76" width="300" height="128" rx="14" fill="#0b121c" stroke="{C}" stroke-opacity=".4"/>
 <text x="892" y="100" fill="{C}" font-size="13" font-weight="800" letter-spacing="2">ECG <tspan fill="#8b98a8" font-weight="600">\u00b7 PULSE</tspan></text>
 <text x="1160" y="100" fill="#6b7a8c" font-size="12" text-anchor="end" font-family="ui-monospace,Consolas,monospace">LIMITS {LOW_W}-{HIGH_W}</text>
 <g transform="translate(922,152)"><g>{heart_anim}<path d="M0,15 C-30,-5 -18,-30 0,-14 C18,-30 30,-5 0,15 Z" fill="{C}" fill-opacity=".9"/></g></g>
 <text x="1122" y="182" fill="{C}" font-size="82" font-weight="800" text-anchor="end" font-family="ui-monospace,Consolas,monospace">{bpm_txt}</text>
 <text x="1160" y="182" fill="#8b98a8" font-size="14" font-weight="600" text-anchor="end" letter-spacing="1">BPM</text>
 {card(876, "EVENTS", n24, "LAST 24H")}
 {card(980, "STREAK", streak, "DAYS")}
 {card(1084, "REPOS", repos7, "LAST 7D")}
</g>
</svg>'''

os.makedirs("assets", exist_ok=True)
with open("assets/ecg.svg", "w", encoding="utf-8") as f:
    f.write(svg)
print(f"state={rhythm} bpm={bpm} level={level} hours={hours:.1f} n24={n24} streak={streak} size={len(svg)//1024}KB")
