"""
Contribution Pulse v5 - ICU bedside-monitor card driven by REAL GitHub data.
Theme: gold (dark + light), writes assets/ecg-dark.svg and assets/ecg-light.svg

Human-like live model:
  Every recent GitHub event adds "exertion" that ramps up (~3 min) and recovers (~15 min).
  effort = 1 - exp(-load / 4)           0 = rested, ~1 = working hard

  Vital     rest            working (effort=1)
  HR        70 BPM          130 BPM
  NIBP      118/76 mmHg     148/82 mmHg
  SpO2      97-99 %         96-98 %
  RESP      14 rpm          24 rpm
  HRV       35-60 ms        ~10-15 ms (falls with effort)

  Heart icon + header dot beat at exactly 60 / BPM seconds.
  Header shows LAST ACTIVITY (date/time of last GitHub activity); in asystole
  the same time is shown as TIME OF DEATH.

  TEST BRANCH: ASYSTOLE_MIN defaults to 1 minute of inactivity (real value: 168 * 60).

Testing (no network / token needed):
    python3 scripts/ecg.py --demo all --out-dir demo       # open demo/index.html
    python3 scripts/ecg.py --demo working --out /tmp/o.svg   # -> /tmp/o-dark.svg, /tmp/o-light.svg
States: normal working tachy brady irregular critical spo2low overload bplow artifact leadsoff asystole
"""
import os, sys, re, json, math, random, argparse, datetime, urllib.request

# ------------------------------------------------------------- geometry
W, H = 1200, 420
TX, TW = 24, 832
PY, PH = 76, 268
ECG_Y, PPG_Y = 165, 322
T_SWEEP = 5.2
V = TW / T_SWEEP
CYCLE = 2 * T_SWEEP
GAP = 64.0
DT = 0.01
N = int(round(T_SWEEP / DT))
STEP = TW / N
NKNOT = 8
PLETH_DELAY = 0.22

LOW_W, HIGH_W, LOW_C, HIGH_C = 50, 120, 40, 140
SPO2_W, SPO2_C = 92, 88

# live heart model
REST, PEAK = 70, 130        # resting / maximum working BPM
TAU_REC = 15.0              # minutes: recovery time constant after activity
TAU_RISE = 3.0              # minutes: ramp-up after an event
K_LOAD = 4.0                # load needed for ~63% of max effort
ASYSTOLE_MIN = float(os.environ.get("ASYSTOLE_MIN", 1))   # TEST: 1 minute (real value: 168 * 60)

TAU = 2 * math.pi
clamp = lambda v, a, b: max(a, min(b, v))
g = lambda dt, c, w: math.exp(-((dt - c) / w) ** 2)

MONO = "ui-monospace,Consolas,monospace"

def fmt_last(dt, exact):
    """Last activity as text. exact=False means only the date is known."""
    if dt is None:
        return "NO ACTIVITY ON RECORD"
    return dt.strftime("%d %b %Y %H:%M UTC" if exact else "%d %b %Y").upper()

# ---------------------------------------------------------------- theme
PALETTES = {
  "dark": dict(
    theme={0: ("#DCA54C", "#F0CB7A"), 1: ("#FF8A3D", "#FFB070"), 2: ("#FF4D5E", "#FF8A8A")},
    level={2: "#FF4D5E", 1: "#FF8A3D"},
    line="#DCA54C",
    swap={"#0d1420": "#1A160C", "#05080e": "#0F0C06", "#070b12": "#130F08",
          "#0b121c": "#211B0E", "#e6edf3": "#F5E9C8", "#6b7a8c": "#8C7C54",
          "#8b98a8": "#A89868"}),
  "light": dict(
    theme={0: ("#B1901F", "#7A6212"), 1: ("#D9600F", "#B8480A"), 2: ("#D62839", "#B01E2E")},
    level={2: "#D62839", 1: "#D9600F"},
    line="#B1901F",
    swap={"#0d1420": "#F9F6EE", "#05080e": "#F1EBD6", "#070b12": "#FFFFFF",
          "#0b121c": "#FFFFFF", "#e6edf3": "#2B2410", "#6b7a8c": "#8A7A45",
          "#8b98a8": "#6B5D2E"}),
}

def set_theme(name):
    global THEME, LEVEL_COL, LINE, SWAP
    p = PALETTES[name]
    THEME, LEVEL_COL, LINE, SWAP = p["theme"], p["level"], p["line"], p["swap"]

def skin(svg):
    svg = svg.replace('stroke="#fff"', f'stroke="{LINE}"')
    return re.sub("|".join(SWAP), lambda m: SWAP[m.group(0)], svg)

set_theme("dark")

# ------------------------------------------------------------------ data
def _post_json(url, payload, token):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def fetch_events(user, token):
    out = []
    for page in (1, 2, 3):
        req = urllib.request.Request(
            f"https://api.github.com/users/{user}/events/public?per_page=100&page={page}",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"})
        batch = json.load(urllib.request.urlopen(req, timeout=30))
        out += batch
        if len(batch) < 100:
            break
    return out

CAL_QUERY = """query($login:String!){user(login:$login){contributionsCollection{
contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""

def fetch_calendar(user, token):
    """Daily contribution counts for the last year: {date: count}. Empty dict on failure."""
    try:
        d = _post_json("https://api.github.com/graphql",
                       {"query": CAL_QUERY, "variables": {"login": user}}, token)
        weeks = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        return {datetime.date.fromisoformat(day["date"]): day["contributionCount"]
                for w in weeks for day in w["contributionDays"]}
    except Exception as ex:
        print("calendar unavailable, falling back to events:", ex, file=sys.stderr)
        return {}

WEIGHT = {"PushEvent": 1.0, "PullRequestEvent": 1.6, "PullRequestReviewEvent": 1.2,
          "IssuesEvent": 0.8, "IssueCommentEvent": 0.6, "CreateEvent": 0.6}

def activity_stats(events, cal, now):
    today = now.date()
    utc = datetime.timezone.utc
    rows = []
    for e in events:
        t = datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        rows.append(((now - t).total_seconds() / 3600, t, e))

    daily = dict(cal)
    if not daily:
        for _, t, _ in rows:
            daily[t.date()] = daily.get(t.date(), 0) + 1
    series = [daily.get(today - datetime.timedelta(days=k), 0) for k in range(89, -1, -1)]

    hours = min((r[0] for r in rows), default=9999.0)
    past = [d for d, c in daily.items() if c > 0 and d <= today]

    # LAST ACTIVITY: exact time from events if available, else only the calendar date
    last_dt, last_exact = None, False
    if rows:
        last_dt, last_exact = max(r[1] for r in rows), True
    if past:
        ld = max(past)
        if last_dt is None or ld > last_dt.date():
            last_dt, last_exact = datetime.datetime.combine(ld, datetime.time(0), utc), False

    if past:
        last = max(past)
        if last == today:
            h_cal = (now - datetime.datetime.combine(today, datetime.time(0), utc)).total_seconds() / 7200
        else:
            h_cal = (now - datetime.datetime.combine(last, datetime.time(12), utc)).total_seconds() / 3600
        hours = min(hours, h_cal)

    # LIVE LOAD: each event ramps up over ~3 min, then recovers over ~15 min
    load = 0.0
    for age_h, _, e in rows:
        m = max(age_h, 0.0) * 60
        load += WEIGHT.get(e["type"], 0.4) * (1 - math.exp(-m / TAU_RISE)) * math.exp(-m / TAU_REC)
    if not rows:                                    # events API down: mild fallback from calendar
        load = min(5.0, 0.2 * series[-1])

    n24 = sum(1 for age, _, _ in rows if age < 24) if rows else series[-1]
    repos7 = len({e.get("repo", {}).get("name") for age, _, e in rows if age < 168})
    act = lambda n: sum(1 for c in series[-n:] if c > 0)

    i, streak = len(series) - 1, 0
    if series[i] == 0:
        i -= 1
    while i >= 0 and series[i] > 0:
        streak += 1
        i -= 1

    m7, m30 = sum(series[-7:]) / 7, sum(series[-30:]) / 30
    return dict(hours=hours, load=load, n24=n24, repos7=repos7, streak=streak,
                active7=act(7), active30=act(30), m7=m7, m30=m30, series=series,
                last=last_dt, last_exact=last_exact)

# ---------------------------------------------------------------- states
def news2(hr, spo2, sbp, rr):
    """NHS NEWS2 banding (SpO2 scale 1, patient on air, alert). Returns (total, any_single_red)."""
    p = []
    if rr is not None:
        p.append(3 if rr <= 8 else 1 if rr <= 11 else 0 if rr <= 20 else 2 if rr <= 24 else 3)
    if spo2 is not None:
        p.append(3 if spo2 <= 91 else 2 if spo2 <= 93 else 1 if spo2 <= 95 else 0)
    if sbp is not None:
        p.append(3 if sbp <= 90 else 2 if sbp <= 100 else 1 if sbp <= 110 else 0 if sbp <= 219 else 3)
    if hr is not None:
        p.append(3 if hr <= 40 else 1 if hr <= 50 else 0 if hr <= 90 else 1 if hr <= 110 else 2 if hr <= 130 else 3)
    return sum(p), (3 in p)

def alarms_for(bpm, ir, spo2, sbp=None):
    a = []
    if bpm is not None:
        if bpm < LOW_C:       a.append((2, "HR CRITICAL LOW"))
        elif bpm >= HIGH_C:   a.append((2, "HR CRITICAL HIGH"))
        elif bpm < LOW_W:     a.append((1, "HR TOO LOW"))
        elif bpm >= HIGH_W:   a.append((1, "HR TOO HIGH"))
        if ir > 0.3:          a.append((1, "IRREGULAR RHYTHM"))
    if spo2 is not None:
        if spo2 < SPO2_C:     a.append((2, "SPO2 CRITICAL LOW"))
        elif spo2 < SPO2_W:   a.append((1, "SPO2 LOW"))
    if sbp is not None:
        if sbp < 90:          a.append((1, "NIBP LOW"))
        elif sbp >= 180:      a.append((1, "NIBP HIGH"))
    return a

def rhythm_of(bpm, ir):
    if ir > 0.3:    return "IRREGULAR RHYTHM"
    if bpm < 60:    return "BRADYCARDIA"
    if bpm >= 100:  return "TACHYCARDIA"
    return "NORMAL SINUS RHYTHM"

def make_state(name, **kw):
    S = dict(name=name, bpm=76, rate=None, ir=0.0, spo2=98, mode="normal", art=0.0, effort=0.0,
             sys=118, dia=76, rr=16, hrv=48, trend=None,
             side=dict(n24=4, streak=9, repos7=14), extra=[], rhythm=None,
             last=None, last_exact=True)
    S.update(kw)
    if S["rate"] is None:
        S["rate"] = S["bpm"] or 0
    if S["trend"] is None:
        r = random.Random(3)
        S["trend"] = [0] * 30 if S["mode"] == "asystole" else [max(0, int(r.gauss(4, 3))) for _ in range(30)]
    if S["mode"] == "asystole":
        S["sys"] = S["dia"] = S["rr"] = S["hrv"] = S["news"] = None
        S["alarms"] = [(2, "ASYSTOLE - NO ACTIVITY")]
        S["rhythm"] = "ASYSTOLE"
    else:
        pulse = S["bpm"] if S["bpm"] is not None else S["rate"]
        S["news"], red = news2(pulse, S["spo2"], S["sys"], S["rr"])
        extra = list(S["extra"])
        if S["news"] >= 7:
            extra.append((2, f"NEWS2 {S['news']} - ESCALATE"))
        elif S["news"] >= 5 or red:
            extra.append((1, f"NEWS2 {S['news']} - URGENT REVIEW"))
        S["alarms"] = sorted(alarms_for(S["bpm"], S["ir"], S["spo2"], S["sys"]) + extra, key=lambda a: -a[0])
        S["rhythm"] = S["rhythm"] or rhythm_of(S["bpm"], S["ir"])
    S["level"] = S["alarms"][0][0] if S["alarms"] else 0
    return S

def state_from_activity(st, rng):
    side = dict(n24=st["n24"], streak=st["streak"], repos7=st["repos7"])
    trend = st["series"][-30:]
    hours = st["hours"]
    if hours * 60 >= ASYSTOLE_MIN:
        return make_state("live", bpm=None, rate=0, ir=1.0, spo2=None, mode="asystole", side=side, trend=trend,
                          last=st["last"], last_exact=st["last_exact"])

    # effort: 0 = fully rested, ~1 = working hard right now
    effort = 1 - math.exp(-st["load"] / K_LOAD)

    # HEART RATE: 70 at rest -> 130 at full effort
    bpm = REST + (PEAK - REST) * effort
    if hours > 48:                                   # long inactivity: bradycardia -> irregular
        bpm *= 1 - 0.75 * (hours - 48) / 120
    bpm = int(round(clamp(bpm, 10, 150)))
    ir = clamp((hours - 48) / 120, 0, 1)

    # consistency (active days) only nudges SpO2 and HRV baseline a little
    cons = 0.7 * st["active7"] / 7 + 0.3 * st["active30"] / 30

    # SpO2: healthy 97-99 %, drops about 1 % at full effort
    spo2 = int(round(clamp(97 + 2 * cons - effort, 94, 100)))
    # BP: ~118/76 at rest. Systolic rises a lot with effort, diastolic barely moves (like a real person)
    sys_ = int(round(clamp(118 + 30 * effort + rng.randint(-3, 3), 70, 190)))
    dia = int(round(clamp(76 + 6 * effort + rng.randint(-2, 2), 40, 110)))
    # RESP: 14 rpm at rest -> 24 rpm at full effort
    rr = int(round(clamp(14 + 10 * effort + rng.choice((-1, 0, 0, 1)), 6, 28)))
    # HRV (RMSSD ms): 35-60 at rest, falls up to 75% while working
    hrv = int(round(clamp((35 + 25 * cons) * (1 - 0.75 * effort) + rng.randint(-2, 2), 5, 80)))

    return make_state("live", bpm=bpm, ir=ir, spo2=spo2, sys=sys_, dia=dia, rr=rr, effort=effort,
                      hrv=hrv, side=side, trend=trend, last=st["last"], last_exact=st["last_exact"])

DEMOS = {
    "normal":    dict(),
    "working":   dict(bpm=114, effort=0.7, spo2=97, sys=140, dia=80, rr=21, hrv=18),
    "tachy":     dict(bpm=134, effort=0.8, sys=145, dia=82, rr=22, hrv=14),
    "brady":     dict(bpm=44),
    "irregular": dict(bpm=62, ir=0.6),
    "critical":  dict(bpm=34, ir=0.8, spo2=90),
    "spo2low":   dict(bpm=88, spo2=89),
    "overload":  dict(bpm=124, spo2=90, sys=186, dia=104, rr=26, hrv=9, effort=1.0),
    "bplow":     dict(bpm=58, sys=84, dia=50, rr=9, hrv=30),
    "artifact":  dict(art=1.0, extra=[(1, "ECG ARTIFACT")], rhythm="ARTIFACT"),
    "leadsoff":  dict(bpm=None, rate=74, mode="leadsoff", extra=[(1, "ECG LEADS OFF")], rhythm="LEADS OFF"),
    "asystole":  dict(bpm=None, rate=0, spo2=None, mode="asystole", side=dict(n24=0, streak=0, repos7=0)),
}

# ------------------------------------------------------------ waveforms
def build_waves(S, rng):
    rate, ir, mode, art, spo2 = S["rate"], S["ir"], S["mode"], S["art"], S["spo2"]
    eff = S["effort"]
    fb = (S["rr"] or 16) / 60.0                      # breathing frequency (Hz) follows RESP
    KD = CYCLE / NKNOT

    walk, cur = [], 0
    for _ in range(NKNOT):
        cur = clamp(cur + rng.choice((-1, 0, 0, 1)), -2, 2)
        walk.append(cur)
    phi = rng.uniform(0, TAU)
    rsa = min(3.0, rate * 0.03) * (1 - ir) * (1 - 0.7 * eff)   # variability drops when working

    def hr(t):
        x = t / KD - 0.5
        i = int(math.floor(x)); f = x - i
        a = walk[clamp(i, 0, NKNOT - 1)]; b = walk[clamp(i + 1, 0, NKNOT - 1)]
        return rate + a + (b - a) * f + rsa * math.sin(TAU * fb * t + phi)

    beats = []
    if mode != "asystole" and rate:
        t = -0.7 + rng.uniform(0, 0.3)
        p_pvc = 0.0 if ir <= 0.3 else 0.12 + 0.25 * (ir - 0.3)
        pvc, prev_gap = False, 60.0 / rate
        while t < CYCLE + 0.9:
            amp = 1.0 if pvc else (1 - 0.35 * ir) * (1 + rng.uniform(-0.05, 0.05))
            beats.append(dict(t=t, pvc=pvc, amp=amp, k=min(1.0, prev_gap / 0.83) ** 0.6))
            rr = 60.0 / max(hr(t), 20.0)
            nxt = False
            if pvc:
                gap = 1.38 * rr
            else:
                gap = rr * (1 + rng.uniform(-1, 1) * (0.025 + 0.28 * ir))
                if p_pvc and rng.random() < p_pvc:
                    gap, nxt = 0.62 * rr, True
            t += gap; prev_gap = gap; pvc = nxt

    def ecg_beats(t):
        y = 0.0
        for b in beats:
            dt = t - b["t"]
            if dt < -0.45 or dt > 0.75:
                continue
            a, K = b["amp"], b["k"]
            if b["pvc"]:
                y += -78 * a * g(dt, 0, .054) + 46 * a * g(dt, .125, .071) + 22 * a * g(dt, .325, .092)
            else:
                y += (-9 * a * g(dt, -.2 * K, .04 * K + .008) + 9 * a * g(dt, -.03, .013)
                      - 70 * a * g(dt, 0, .018) + 24 * a * g(dt, .034, .017)
                      - 17 * a * g(dt, .225 * K, .06 * K + .016))
        return y

    sc = 1.0 if spo2 is None else clamp(1 - (95 - spo2) * 0.035, 0.5, 1.0)

    def ppg_beats(t):
        y = 0.0
        for b in beats:
            dt = t - b["t"] - PLETH_DELAY
            if dt < -0.3 or dt > 0.55:
                continue
            pa = 0.55 if b["pvc"] else b["amp"]
            y += 46 * sc * pa * (g(dt, 0, .063) + 0.32 * g(dt, .158, .054))
        return y

    hf = 0.6 + 0.8 * ir + 0.7 * eff                  # more muscle noise while working
    wamp = 2.4 + 1.0 * ir + 1.2 * eff                # bigger breathing sway while working
    ph1, ph2 = rng.uniform(0, TAU), rng.uniform(0, TAU)
    bursts = [(rng.uniform(0, CYCLE - 1), rng.uniform(.4, 1.0), rng.uniform(2.5, 5.0)) for _ in range(5)] if art else []
    steps = [(rng.uniform(0, CYCLE), rng.choice((-1, 1)) * rng.uniform(8, 14)) for _ in range(3)] if art else []

    def wander(t, st=True):
        w = wamp * (math.sin(TAU * fb * t + ph1) + 0.4 * math.sin(TAU * 0.09 * t + ph2))
        if st:
            for s, a in steps:
                if t >= s:
                    w += a * math.exp(-(t - s) / 0.45)
        return w

    def env(t):
        return sum(a * math.sin(math.pi * (t - s) / d) for s, d, a in bursts if s <= t < s + d)

    def sweep(t0):
        ye_l, yp_l, ar, ar2 = [], [], 0.0, 0.0
        for i in range(N + 1):
            t = t0 + i * DT
            e = env(t) if art else 0.0
            ar = 0.55 * ar + rng.gauss(0, hf * (1 + e * 1.2))
            ar2 = 0.6 * ar2 + rng.gauss(0, 0.3 * (1 + 0.5 * e))
            if mode == "leadsoff":
                ye = ECG_Y
            elif mode == "asystole":
                ye = ECG_Y + 0.25 * wander(t) + 0.25 * ar
            else:
                ye = ECG_Y + ecg_beats(t) + wander(t) + ar + e * 6 * math.sin(TAU * 11 * t)
            yp = PPG_Y + 0.2 * ar2 if mode == "asystole" else PPG_Y - ppg_beats(t) + 0.5 * wander(t + 0.8, False) + ar2
            ye_l.append(clamp(ye, PY + 10, 226)); yp_l.append(clamp(yp, 238, PY + PH - 4))
        return ye_l, yp_l

    def path(ys):
        return f"M0,{ys[0]:.1f} " + " ".join(f"L{i * STEP:.1f},{y:.1f}" for i, y in enumerate(ys) if i)

    eA, pA = sweep(0.0)
    eB, pB = sweep(T_SWEEP)
    disp = [int(clamp(round(rate + w), 10, 190)) for w in walk] if S["bpm"] else []
    sp = []
    if spo2 is not None:
        s = spo2
        for _ in range(NKNOT):
            if rng.random() < 0.35:
                s = clamp(s + rng.choice((-1, 1)), spo2 - 1, min(100, spo2 + 1))
            sp.append(int(s))
    return dict(ecgA=path(eA), ppgA=path(pA), ecgB=path(eB), ppgB=path(pB), disp=disp, spo2=sp)

# ------------------------------------------------------------- svg bits
def cycle(items, dur):
    """Show svg snippets one after another (discrete visibility), merging equal neighbours."""
    n = len(items)
    runs = []
    for i, s in enumerate(items):
        if runs and runs[-1][0] == s:
            runs[-1][2] = (i + 1) / n
        else:
            runs.append([s, i / n, (i + 1) / n])
    if len(runs) == 1:
        return runs[0][0]
    out = []
    for s, a, b in runs:
        if a == 0:
            kts, vs = [0, b, 1], ["visible", "hidden", "hidden"]
        elif b >= 1:
            kts, vs = [0, a, 1], ["hidden", "visible", "visible"]
        else:
            kts, vs = [0, a, b, 1], ["hidden", "visible", "hidden", "hidden"]
        hid = "" if a == 0 else ' visibility="hidden"'
        out.append(f'<g{hid}><animate attributeName="visibility" calcMode="discrete" '
                   f'dur="{dur:.2f}s" repeatCount="indefinite" keyTimes="{";".join(f"{x:.4f}" for x in kts)}" '
                   f'values="{";".join(vs)}"/>{s}</g>')
    return "".join(out)

def clip_defs(still):
    y, h = PY + 4, PH - 8
    def rect(a, anim=""):
        return f'<rect y="{y}" height="{h}" {a}>{anim}</rect>'
    def an(attr, vals, kts):
        return f'<animate attributeName="{attr}" dur="{CYCLE:.2f}s" repeatCount="indefinite" keyTimes="{kts}" values="{vals}"/>'
    tw, gp = f"{TW:g}", f"{GAP:g}"
    if still:
        ca = rect(f'x="0" width="{tw}"')
        cb = rect('x="0" width="0"')
    else:
        ca = (rect('x="0"', an("width", f"0;{tw};0;0", "0;.5;.5;1")) +
              rect(f'width="{TW + GAP:g}"', an("x", f"{tw};{tw};{gp};{TW + GAP:g}", "0;.5;.5;1")))
        cb = (rect('x="0"', an("width", f"0;0;{tw}", "0;.5;1")) +
              rect(f'width="{TW + GAP:g}"', an("x", f"{gp};{TW + GAP:g};{tw};{tw}", "0;.5;.5;1")))
    return (f'<clipPath id="outer"><rect x="0" y="{PY + 4}" width="{TW}" height="{PH - 8}"/></clipPath>'
            f'<clipPath id="cA">{ca}</clipPath><clipPath id="cB">{cb}</clipPath>')

def banner_svg(S, C):
    cx, y = 660, 16
    alarms = S["alarms"]
    if not alarms:
        t = S["rhythm"]; bw = int(len(t) * 10 + 44)
        return (f'<rect x="{cx - bw // 2}" y="{y}" width="{bw}" height="32" rx="16" fill="{C}" fill-opacity=".12" '
                f'stroke="{C}" stroke-opacity=".55"/><text x="{cx}" y="{y + 22}" fill="{C}" font-size="13" '
                f'font-weight="700" text-anchor="middle" letter-spacing="2">{t}</text>')
    bw = int(max(len(t) for _, t in alarms) * 11 + 56)
    items = []
    for lvl, t in alarms:
        col = LEVEL_COL[lvl]
        if lvl == 2:
            blink = '<animate attributeName="opacity" values="1;.35;1" dur=".9s" repeatCount="indefinite"/>'
        else:
            blink = '<animate attributeName="opacity" values="1;.7;1" dur="2s" repeatCount="indefinite"/>'
        tcol = "#fff" if lvl == 2 else "#0b0f16"
        items.append(f'<rect x="{cx - bw // 2}" y="{y}" width="{bw}" height="32" rx="8" fill="{col}">{blink}</rect>'
                     f'<text x="{cx}" y="{y + 22}" fill="{tcol}" font-size="14" '
                     f'font-weight="800" text-anchor="middle" letter-spacing="1.5">\u25B2 {t}</text>')
    return cycle(items, 2.4 * len(items))

def card(x, y, h, label, val, unit, col="#e6edf3", size=28):
    cx = x + 46
    if h >= 60:
        ly, vy, uy = y + 17, y + 44, y + 58
    else:
        ly, vy, uy = y + 16, y + 37, y + 48
    return (f'<rect x="{x}" y="{y}" width="92" height="{h}" rx="12" fill="#0b121c" stroke="#fff" stroke-opacity=".08"/>'
            f'<text x="{cx}" y="{ly}" fill="#8b98a8" font-size="10" font-weight="700" text-anchor="middle" letter-spacing="2">{label}</text>'
            f'<text x="{cx}" y="{vy}" fill="{col}" font-size="{size}" font-weight="800" text-anchor="middle" font-family="{MONO}">{val}</text>'
            f'<text x="{cx}" y="{uy}" fill="#6b7a8c" font-size="9" text-anchor="middle" letter-spacing="1">{unit}</text>')

def trend_svg(S, C, C2):
    """30-day contribution bars (real daily counts) under the traces."""
    series = S["trend"]
    y0, h0 = PY + PH + 12, 52
    x0, x1 = TX + 112, TX + TW - 16
    n = len(series)
    slot = (x1 - x0) / n
    bw = slot * 0.62
    mx = max(5, max(series))
    base, top = y0 + h0 - 6, y0 + 10
    out = [f'<rect x="{TX}" y="{y0}" width="{TW}" height="{h0}" rx="12" fill="#070b12" fill-opacity=".7" stroke="#fff" stroke-opacity=".08"/>',
           f'<text x="{TX + 16}" y="{y0 + 22}" fill="{C2}" font-size="10" font-weight="700" letter-spacing="2" font-family="{MONO}">30D TREND</text>',
           f'<text x="{TX + 16}" y="{y0 + 38}" fill="#6b7a8c" font-size="9" letter-spacing="1" font-family="{MONO}">{S["side"]["repos7"]} REPOS / 7D</text>']
    for i, c in enumerate(series):
        h = max(2.0, c / mx * (base - top)) if c > 0 else 2.0
        last = i == n - 1
        col = C if last else C2
        op = ".95" if last else (".65" if c > 0 else ".18")
        anim = '<animate attributeName="opacity" values=".95;.4;.95" dur="1.6s" repeatCount="indefinite"/>' if last and c > 0 else ""
        out.append(f'<rect x="{x0 + i * slot:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{col}" opacity="{op}">{anim}</rect>')
    return "".join(out)

def brackets(x, y, w, h, col, s=14):
    d = (f"M{x},{y + s} L{x},{y} L{x + s},{y} M{x + w - s},{y} L{x + w},{y} L{x + w},{y + s} "
         f"M{x + w},{y + h - s} L{x + w},{y + h} L{x + w - s},{y + h} M{x + s},{y + h} L{x},{y + h} L{x},{y + h - s}")
    return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6" stroke-opacity=".7" stroke-linecap="round"/>'

# --------------------------------------------------------------- render
def render(S, user, now, rng, still=False):
    C, C2 = THEME[S["level"]]
    Wv = build_waves(S, rng)
    leads_off = S["mode"] == "leadsoff"

    if S["bpm"]:
        hr_items = [f'<text x="1122" y="172" fill="{C}" font-size="72" font-weight="800" text-anchor="end" font-family="{MONO}">{v}</text>' for v in Wv["disp"]]
        hr_txt = cycle(hr_items, CYCLE)
    else:
        hr_txt = f'<text x="1122" y="172" fill="{C}" font-size="72" font-weight="800" text-anchor="end" font-family="{MONO}">--</text>'
    if Wv["spo2"]:
        sp_items = [f'<text x="1122" y="262" fill="{C2}" font-size="38" font-weight="800" text-anchor="end" font-family="{MONO}">{v}</text>' for v in Wv["spo2"]]
        sp_txt = cycle(sp_items, CYCLE)
    else:
        sp_txt = f'<text x="1122" y="262" fill="{C2}" font-size="38" font-weight="800" text-anchor="end" font-family="{MONO}">--</text>'

    # heart icon + header dot beat exactly at the displayed BPM (lub-dub every 60/BPM seconds)
    if S["bpm"]:
        per = 60.0 / S["bpm"]
        kt = "0;.08;.18;.28;.40;1"
        heart_anim = (f'<animateTransform attributeName="transform" type="scale" keyTimes="{kt}" '
                      f'values="1;1.22;1;1.12;1;1" dur="{per:.3f}s" repeatCount="indefinite"/>')
        dot_anim = (f'<animate attributeName="opacity" keyTimes="{kt}" values=".25;1;.25;.7;.25;.25" '
                    f'dur="{per:.3f}s" repeatCount="indefinite"/>')
    else:
        heart_anim = dot_anim = ""

    def group(cid, e, p):
        if leads_off:
            ecg = f'<use href="#{e}" xlink:href="#{e}" stroke="{C}" stroke-width="1.8" stroke-dasharray="7 6" opacity=".7"/>'
        else:
            ecg = (f'<use href="#{e}" xlink:href="#{e}" stroke="{C}" stroke-width="7" opacity=".3" filter="url(#glow)"/>'
                   f'<use href="#{e}" xlink:href="#{e}" stroke="url(#line)" stroke-width="2.4"/>')
        return (f'<g clip-path="url(#{cid})">{ecg}'
                f'<use href="#{p}" xlink:href="#{p}" stroke="{C2}" stroke-width="2.2" opacity=".92"/></g>')

    leads_txt = (f'<text x="{TX + TW // 2}" y="{ECG_Y - 18}" fill="{C}" font-size="13" font-weight="800" '
                 f'text-anchor="middle" letter-spacing="3" font-family="{MONO}">ECG LEADS OFF</text>') if leads_off else ""

    # LAST ACTIVITY (normal) / TIME OF DEATH (asystole): same timestamp, never changes until new activity
    dead = S["mode"] == "asystole"
    last_str = fmt_last(S["last"], S["last_exact"])
    lbl, lcol = ("TIME OF DEATH", LEVEL_COL[2]) if dead else ("LAST ACTIVITY", "#6b7a8c")
    last_svg = (f'<text x="{W - 24}" y="60" fill="{lcol}" font-size="12" text-anchor="end" '
                f'letter-spacing="1" font-family="{MONO}">{lbl} {last_str}</text>')
    tod_txt = (f'<text x="{TX + TW // 2}" y="{ECG_Y - 18}" fill="{LEVEL_COL[2]}" font-size="14" font-weight="800" '
               f'text-anchor="middle" letter-spacing="3" font-family="{MONO}">TIME OF DEATH {last_str}</text>') if dead else ""

    nibp = f'{S["sys"]}/{S["dia"]}' if S["sys"] else "--/--"
    rr_v = S["rr"] if S["rr"] else "--"
    hrv_v = S["hrv"] if S["hrv"] is not None else "--"
    nw = S["news"]
    if nw is None:
        n_val, n_col, n_unit = "--", "#8b98a8", "NO DATA"
    elif nw >= 7:
        n_val, n_col, n_unit = nw, LEVEL_COL[2], "HIGH RISK"
    elif nw >= 5:
        n_val, n_col, n_unit = nw, LEVEL_COL[1], "MEDIUM RISK"
    else:
        n_val, n_col, n_unit = nw, THEME[0][0], "LOW RISK"
    nibp_col = LEVEL_COL[1] if S["sys"] and (S["sys"] < 90 or S["sys"] >= 180) else "#e6edf3"
    cards = (card(876, 280, 64, "NIBP", nibp, "SYS/DIA mmHg", nibp_col, 20) +
             card(980, 280, 64, "RESP", rr_v, "RPM", "#e6edf3", 28) +
             card(1084, 280, 64, "HRV", hrv_v, "RMSSD ms", "#e6edf3", 28) +
             card(876, 356, 52, "NEWS2", n_val, n_unit, n_col, 22) +
             card(980, 356, 52, "STREAK", S["side"]["streak"], "DAYS", "#e6edf3", 22) +
             card(1084, 356, 52, "EVENTS", S["side"]["n24"], "LAST 24H", "#e6edf3", 22))

    scan = (f'<rect x="{TX}" y="{PY}" width="{TW}" height="2" fill="{C}" opacity=".08">'
            f'<animate attributeName="y" values="{PY};{PY + PH};{PY}" dur="7s" repeatCount="indefinite"/></rect>') if not still else ""

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="100%">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#05080e"/></linearGradient>
 <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C}" stop-opacity=".7"/><stop offset="1" stop-color="{C2}" stop-opacity=".7"/></linearGradient>
 <linearGradient id="line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{TW}" y2="0"><stop offset="0" stop-color="{C}"/><stop offset="1" stop-color="{C2}"/></linearGradient>
 <radialGradient id="halo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{C}" stop-opacity=".14"/><stop offset="1" stop-color="{C}" stop-opacity="0"/></radialGradient>
 <pattern id="g1" x="{TX}" y="{PY}" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M10,0 L0,0 L0,10" fill="none" stroke="#fff" stroke-opacity=".03"/></pattern>
 <pattern id="g2" x="{TX}" y="{PY}" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M50,0 L0,0 L0,50" fill="none" stroke="#fff" stroke-opacity=".06"/></pattern>
 <filter id="glow" x="-2%" y="-40%" width="104%" height="180%"><feGaussianBlur stdDeviation="4"/></filter>
 {clip_defs(still)}
 <path id="ecgA" d="{Wv["ecgA"]}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
 <path id="ppgA" d="{Wv["ppgA"]}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
 <path id="ecgB" d="{Wv["ecgB"]}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
 <path id="ppgB" d="{Wv["ppgB"]}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
</defs>

<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="url(#bg)" stroke="url(#stroke)" stroke-width="1.5"/>
<ellipse cx="440" cy="{ECG_Y}" rx="430" ry="130" fill="url(#halo)"/>

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <circle cx="44" cy="34" r="6" fill="{C}">{dot_anim}</circle>
 <text x="62" y="40" fill="#e6edf3" font-size="19" font-weight="700" letter-spacing="3">CONTRIBUTION PULSE</text>
 <text x="62" y="60" fill="#6b7a8c" font-size="12" letter-spacing="1" font-family="{MONO}">@{user} \u00b7 LEAD II \u00b7 {S["rhythm"]}</text>
 {banner_svg(S, C)}
 <text x="{W - 24}" y="40" fill="#6b7a8c" font-size="12" text-anchor="end" letter-spacing="1" font-family="{MONO}">UPDATED {now.strftime("%H:%M")} UTC</text>
 {last_svg}
</g>

<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="#070b12" fill-opacity=".7" stroke="#fff" stroke-opacity=".08"/>
<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="url(#g1)"/>
<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="url(#g2)"/>
{brackets(TX, PY, TW, PH, C)}
<line x1="{TX + 12}" y1="232" x2="{TX + TW - 12}" y2="232" stroke="#fff" stroke-opacity=".07"/>
<g font-family="{MONO}" font-size="12" font-weight="700" letter-spacing="2">
 <text x="{TX + 16}" y="100" fill="{C}">II</text>
 <text x="{TX + 16}" y="250" fill="{C2}">PLETH</text>
 <text x="{TX + TW - 16}" y="{PY + PH - 10}" fill="#6b7a8c" font-size="10" text-anchor="end">25 mm/s</text>
</g>
{leads_txt}
{tod_txt}
<g transform="translate({TX},0)"><g clip-path="url(#outer)">
 {group("cA", "ecgA", "ppgA")}
 {group("cB", "ecgB", "ppgB")}
</g></g>
{scan}
{trend_svg(S, C, C2)}

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <rect x="876" y="76" width="300" height="120" rx="14" fill="#0b121c" stroke="{C}" stroke-opacity=".4"/>
 <text x="892" y="100" fill="{C}" font-size="13" font-weight="800" letter-spacing="2">ECG <tspan fill="#8b98a8" font-weight="600">\u00b7 HR</tspan></text>
 <text x="1160" y="100" fill="#6b7a8c" font-size="12" text-anchor="end" font-family="{MONO}">LIMITS {LOW_W}-{HIGH_W}</text>
 <g transform="translate(924,146)"><g>{heart_anim}<path d="M0,15 C-30,-5 -18,-30 0,-14 C18,-30 30,-5 0,15 Z" fill="{C}" fill-opacity="{".9" if S["bpm"] else ".25"}"/></g></g>
 {hr_txt}
 <text x="1160" y="172" fill="#8b98a8" font-size="14" font-weight="600" text-anchor="end" letter-spacing="1">BPM</text>

 <rect x="876" y="206" width="300" height="64" rx="14" fill="#0b121c" stroke="{C2}" stroke-opacity=".35"/>
 <text x="892" y="230" fill="{C2}" font-size="13" font-weight="800" letter-spacing="2">SPO2</text>
 <text x="892" y="256" fill="#6b7a8c" font-size="11" font-family="{MONO}">LIMITS {SPO2_W}-100</text>
 {sp_txt}
 <text x="1160" y="262" fill="#8b98a8" font-size="14" font-weight="600" text-anchor="end">%</text>

 {cards}
</g>
</svg>'''

# ----------------------------------------------------------------- output
def write_themes(S, user, now, seed, still, out):
    """Render once per theme: assets/ecg.svg -> assets/ecg-dark.svg + assets/ecg-light.svg"""
    base, ext = os.path.splitext(out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    for name in ("dark", "light"):
        set_theme(name)
        svg = skin(render(S, user, now, random.Random(seed), still))
        path = f"{base}-{name}{ext}"
        open(path, "w", encoding="utf-8").write(svg)
        print(f"{name:5s} {path} {len(svg) // 1024}KB")

# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", help="state name or 'all' (no network)")
    ap.add_argument("--out", default="assets/ecg.svg")
    ap.add_argument("--out-dir", default="demo")
    ap.add_argument("--still", action="store_true", help="no animation, trace fully drawn (PNG preview)")
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc)

    if a.demo:
        names = list(DEMOS) if a.demo == "all" else [a.demo]
        cells = []
        for n in names:
            S = make_state(n, **DEMOS[n])
            S["last"] = now - datetime.timedelta(days=8 if n == "asystole" else 0, minutes=5)
            S["last_exact"] = True
            out = os.path.join(a.out_dir, f"{n}.svg") if a.demo == "all" else a.out
            write_themes(S, "demo", now, 7, a.still, out)
            alarms = ", ".join(t for _, t in S["alarms"]) or "-"
            print(f"{n:10s} bpm={S['bpm']} spo2={S['spo2']} news={S['news']} level={S['level']} alarms=[{alarms}]")
            cells.append(f'<figure><img src="{n}-dark.svg"><figcaption>{n} (dark)</figcaption></figure>'
                         f'<figure style="background:#F9F6EE"><img src="{n}-light.svg"><figcaption>{n} (light)</figcaption></figure>')
        if a.demo == "all":
            open(os.path.join(a.out_dir, "index.html"), "w", encoding="utf-8").write(
                '<!doctype html><meta charset="utf-8"><body style="background:#0d1117;color:#8b98a8;font:13px monospace;'
                'display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px;margin:0">' + "".join(cells))
        return

    user, token = os.environ["GH_USER"], os.environ["GH_TOKEN"]
    try:
        events = fetch_events(user, token)
    except Exception as ex:
        print("events unavailable:", ex, file=sys.stderr)
        events = []
    cal = fetch_calendar(user, token)
    st = activity_stats(events, cal, now)
    # seed changes every 5 minutes so the waveform and small vital jitter look fresh on each update
    seed = int(now.strftime("%Y%m%d%H")) * 60 + now.minute
    S = state_from_activity(st, random.Random(seed + 1))
    write_themes(S, user, now, seed, a.still, a.out)
    print(f"load={st['load']:.2f} effort={S['effort']:.2f} state={S['rhythm']} bpm={S['bpm']} spo2={S['spo2']} "
          f"nibp={S['sys']}/{S['dia']} rr={S['rr']} hrv={S['hrv']} news2={S['news']} level={S['level']} "
          f"last={fmt_last(S['last'], S['last_exact'])}")

if __name__ == "__main__":
    main()