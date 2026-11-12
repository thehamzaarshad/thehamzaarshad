"""
Contribution Pulse v2 - bedside-monitor style GitHub activity card.

Activity   -> heart rate (continuous drift, decays like a real vital sign)
Inactivity -> bradycardia -> irregular rhythm (PVCs) -> asystole
Streak     -> SpO2 (active days in last 7)

Output: assets/ecg.svg (SMIL-animated SVG, works inside a GitHub README <img>)

Testing every state (no network, no token needed):
    python3 scripts/ecg.py --demo all --out-dir demo     # then open demo/index.html
    python3 scripts/ecg.py --demo tachy --out /tmp/t.svg
    python3 scripts/ecg.py --demo normal --still --out /tmp/n.svg   # static, for PNG preview
States: normal tachy brady irregular critical spo2low artifact leadsoff asystole
"""
import os, sys, json, math, random, argparse, datetime, urllib.request

# ------------------------------------------------------------- geometry
W, H = 1200, 364
TX, TW = 24, 832                 # trace panel x / width
PY, PH = 76, 268                 # trace panel y / height
ECG_Y, PPG_Y = 165, 322          # baselines
T_SWEEP = 5.2                    # seconds for the cursor to cross the panel
V = TW / T_SWEEP                 # px / s
CYCLE = 2 * T_SWEEP              # two alternating sweeps (A, B) so old/new traces differ
GAP = 64.0                       # erase bar width (px)
DT = 0.01                        # sample step (s)
N = int(round(T_SWEEP / DT))
STEP = TW / N
NKNOT = 8                        # displayed vitals update 8x per cycle
PLETH_DELAY = 0.22               # R-peak -> pleth upstroke (s)

LOW_W, HIGH_W, LOW_C, HIGH_C = 50, 120, 40, 140
SPO2_W, SPO2_C = 92, 88

TAU = 2 * math.pi
clamp = lambda v, a, b: max(a, min(b, v))
g = lambda dt, c, w: math.exp(-((dt - c) / w) ** 2)

LEVEL_COL = {2: "#ff4d5e", 1: "#fbbf24"}
THEME = {0: ("#22d3a0", "#38bdf8"), 1: ("#fbbf24", "#fb923c"), 2: ("#ff4d5e", "#ff8a5e")}

# ------------------------------------------------------------------ data
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

WEIGHT = {"PushEvent": 1.0, "PullRequestEvent": 1.6, "PullRequestReviewEvent": 1.2,
          "IssuesEvent": 0.8, "IssueCommentEvent": 0.6, "CreateEvent": 0.6}

def activity_stats(events, now):
    rows = []
    for e in events:
        t = datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        rows.append(((now - t).total_seconds() / 3600, t, e))
    hours = min((r[0] for r in rows), default=9999.0)
    score = sum(WEIGHT.get(e["type"], 0.4) * math.exp(-age / 30) for age, _, e in rows)
    n24 = sum(1 for age, _, _ in rows if age < 24)
    repos7 = len({e.get("repo", {}).get("name") for age, _, e in rows if age < 168})
    days = {t.date() for _, t, _ in rows}
    today = now.date()
    active7 = sum(1 for k in range(7) if today - datetime.timedelta(days=k) in days)
    d = today if today in days else today - datetime.timedelta(days=1)
    streak = 0
    while d in days:
        streak += 1
        d -= datetime.timedelta(days=1)
    return dict(hours=hours, score=score, n24=n24, repos7=repos7, streak=streak, active7=active7)

# ---------------------------------------------------------------- states
def alarms_for(bpm, ir, spo2):
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
    return a

def rhythm_of(bpm, ir):
    if ir > 0.3:    return "IRREGULAR RHYTHM"
    if bpm < 60:    return "BRADYCARDIA"
    if bpm >= 100:  return "TACHYCARDIA"
    return "NORMAL SINUS RHYTHM"

def make_state(name, **kw):
    S = dict(name=name, bpm=76, rate=None, ir=0.0, spo2=98, mode="normal", art=0.0,
             side=dict(n24=4, streak=9, repos7=14), extra=[], rhythm=None)
    S.update(kw)
    if S["rate"] is None:
        S["rate"] = S["bpm"] or 0
    if S["mode"] == "asystole":
        S["alarms"] = [(2, "ASYSTOLE - NO ACTIVITY")]
        S["rhythm"] = "ASYSTOLE"
    else:
        S["alarms"] = sorted(alarms_for(S["bpm"], S["ir"], S["spo2"]) + S["extra"], key=lambda a: -a[0])
        S["rhythm"] = S["rhythm"] or rhythm_of(S["bpm"], S["ir"])
    S["level"] = S["alarms"][0][0] if S["alarms"] else 0
    return S

def state_from_activity(st):
    side = dict(n24=st["n24"], streak=st["streak"], repos7=st["repos7"])
    hours = st["hours"]
    if hours >= 168:
        return make_state("live", bpm=None, rate=0, ir=1.0, spo2=None, mode="asystole", side=side)
    bpm = 40 + 50 * (1 - math.exp(-st["score"] / 3)) + 1.5 * max(0, st["score"] - 20)
    if hours > 48:
        bpm *= 1 - 0.75 * (hours - 48) / 120
    bpm = int(round(clamp(bpm, 10, 150)))
    ir = clamp((hours - 48) / 120, 0, 1)
    spo2 = int(round(86 + 13 * st["active7"] / 7))
    return make_state("live", bpm=bpm, ir=ir, spo2=spo2, side=side)

DEMOS = {
    "normal":    dict(),
    "tachy":     dict(bpm=134),
    "brady":     dict(bpm=44),
    "irregular": dict(bpm=62, ir=0.6),
    "critical":  dict(bpm=34, ir=0.8, spo2=90),              # 3 alarms -> banner cycles
    "spo2low":   dict(bpm=88, spo2=89),
    "artifact":  dict(art=1.0, extra=[(1, "ECG ARTIFACT")], rhythm="ARTIFACT"),
    "leadsoff":  dict(bpm=None, rate=74, mode="leadsoff", extra=[(1, "ECG LEADS OFF")], rhythm="LEADS OFF"),
    "asystole":  dict(bpm=None, rate=0, spo2=None, mode="asystole", side=dict(n24=0, streak=0, repos7=0)),
}

# ------------------------------------------------------------ waveforms
def build_waves(S, rng):
    rate, ir, mode, art, spo2 = S["rate"], S["ir"], S["mode"], S["art"], S["spo2"]
    KD = CYCLE / NKNOT

    # slow +-2 random walk of the displayed value; the trace follows the same curve
    walk, cur = [], 0
    for _ in range(NKNOT):
        cur = clamp(cur + rng.choice((-1, 0, 0, 1)), -2, 2)
        walk.append(cur)
    phi = rng.uniform(0, TAU)
    rsa = min(3.0, rate * 0.03) * (1 - ir)

    def hr(t):
        x = t / KD - 0.5
        i = int(math.floor(x)); f = x - i
        a = walk[clamp(i, 0, NKNOT - 1)]; b = walk[clamp(i + 1, 0, NKNOT - 1)]
        return rate + a + (b - a) * f + rsa * math.sin(TAU * 0.27 * t + phi)

    # beat clock: one list drives both ECG R-peaks and PLETH upstrokes
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
                gap = 1.38 * rr                                   # compensatory pause
            else:
                gap = rr * (1 + rng.uniform(-1, 1) * (0.025 + 0.28 * ir))
                if p_pvc and rng.random() < p_pvc:
                    gap, nxt = 0.62 * rr, True                    # premature beat follows
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

    sc = 1.0 if spo2 is None else clamp(1 - (95 - spo2) * 0.035, 0.5, 1.0)   # low perfusion -> small pleth

    def ppg_beats(t):
        y = 0.0
        for b in beats:
            dt = t - b["t"] - PLETH_DELAY
            if dt < -0.3 or dt > 0.55:
                continue
            pa = 0.55 if b["pvc"] else b["amp"]
            y += 46 * sc * pa * (g(dt, 0, .063) + 0.32 * g(dt, .158, .054))
        return y

    # noise: respiration wander + AR(1) muscle jitter (+ bursts and baseline steps in artifact)
    hf = 0.6 + 0.8 * ir
    wamp = 2.4 + 1.0 * ir
    ph1, ph2 = rng.uniform(0, TAU), rng.uniform(0, TAU)
    bursts = [(rng.uniform(0, CYCLE - 1), rng.uniform(.4, 1.0), rng.uniform(2.5, 5.0)) for _ in range(5)] if art else []
    steps = [(rng.uniform(0, CYCLE), rng.choice((-1, 1)) * rng.uniform(8, 14)) for _ in range(3)] if art else []

    def wander(t, st=True):
        w = wamp * (math.sin(TAU * 0.27 * t + ph1) + 0.4 * math.sin(TAU * 0.09 * t + ph2))
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
    return dict(ecgA=path(eA), ppgA=path(pA), ecgB=path(eB), ppgB=path(pB),
                rtimes=[b["t"] for b in beats if 0 < b["t"] < CYCLE], disp=disp, spo2=sp)

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
    for k, (s, a, b) in enumerate(runs):
        if a == 0:
            kts, vs = [0, b, 1], ["visible", "hidden", "hidden"]
        elif b >= 1:
            kts, vs = [0, a, 1], ["hidden", "visible", "visible"]
        else:
            kts, vs = [0, a, b, 1], ["hidden", "visible", "hidden", "hidden"]
        out.append(f'<g{"" if a == 0 else " visibility=\"hidden\""}><animate attributeName="visibility" calcMode="discrete" '
                   f'dur="{dur:.2f}s" repeatCount="indefinite" keyTimes="{";".join(f"{x:.4f}" for x in kts)}" '
                   f'values="{";".join(vs)}"/>{s}</g>')
    return "".join(out)

def pulse_track(times, base, peak, rise=0.05, fall=0.22):
    pts, last = [(0.0, base)], 0.0
    for t in times:
        if t <= last + 0.01 or t + fall >= CYCLE - 0.01:
            continue
        pts += [(t, base), (t + rise, peak), (t + fall, base)]
        last = t + fall
    pts.append((CYCLE, base))
    return ";".join(f"{t / CYCLE:.5f}" for t, _ in pts), ";".join(f"{v}" for _, v in pts)

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
        blink = (f'<animate attributeName="opacity" values="1;.35;1" dur=".9s" repeatCount="indefinite"/>' if lvl == 2 else
                 f'<animate attributeName="opacity" values="1;.7;1" dur="2s" repeatCount="indefinite"/>')
        items.append(f'<rect x="{cx - bw // 2}" y="{y}" width="{bw}" height="32" rx="8" fill="{col}">{blink}</rect>'
                     f'<text x="{cx}" y="{y + 22}" fill="{"#fff" if lvl == 2 else "#0b0f16"}" font-size="14" '
                     f'font-weight="800" text-anchor="middle" letter-spacing="1.5">\u25B2 {t}</text>')
    return cycle(items, 2.4 * len(items))

def card(x, label, val, unit):
    cx = x + 46
    return (f'<rect x="{x}" y="280" width="92" height="64" rx="12" fill="#0b121c" stroke="#fff" stroke-opacity=".08"/>'
            f'<text x="{cx}" y="297" fill="#8b98a8" font-size="10" font-weight="700" text-anchor="middle" letter-spacing="2">{label}</text>'
            f'<text x="{cx}" y="324" fill="#e6edf3" font-size="28" font-weight="800" text-anchor="middle" font-family="ui-monospace,Consolas,monospace">{val}</text>'
            f'<text x="{cx}" y="338" fill="#6b7a8c" font-size="9" text-anchor="middle" letter-spacing="1">{unit}</text>')

# --------------------------------------------------------------- render
def render(S, user, now, rng, still=False):
    C, C2 = THEME[S["level"]]
    Wv = build_waves(S, rng)
    mono = "ui-monospace,Consolas,monospace"
    leads_off = S["mode"] == "leadsoff"

    # numbers
    if S["bpm"]:
        hr_items = [f'<text x="1122" y="172" fill="{C}" font-size="72" font-weight="800" text-anchor="end" font-family="{mono}">{v}</text>' for v in Wv["disp"]]
        hr_txt = cycle(hr_items, CYCLE / NKNOT * NKNOT)
    else:
        hr_txt = f'<text x="1122" y="172" fill="{C}" font-size="72" font-weight="800" text-anchor="end" font-family="{mono}">--</text>'
    if Wv["spo2"]:
        sp_items = [f'<text x="1122" y="262" fill="{C2}" font-size="38" font-weight="800" text-anchor="end" font-family="{mono}">{v}</text>' for v in Wv["spo2"]]
        sp_txt = cycle(sp_items, CYCLE)
    else:
        sp_txt = f'<text x="1122" y="262" fill="{C2}" font-size="38" font-weight="800" text-anchor="end" font-family="{mono}">--</text>'

    # heart + dot pulse on the same R-peak times the cursor draws
    rt = Wv["rtimes"] if S["bpm"] else []
    hk, hv = pulse_track(rt, 1, 1.22)
    dk, dv = pulse_track(rt, 0.25, 1)
    heart_anim = f'<animateTransform attributeName="transform" type="scale" keyTimes="{hk}" values="{hv}" dur="{CYCLE:.2f}s" repeatCount="indefinite"/>' if rt else ""
    dot_anim = f'<animate attributeName="opacity" keyTimes="{dk}" values="{dv}" dur="{CYCLE:.2f}s" repeatCount="indefinite"/>' if rt else ""

    ecg_style = (f'stroke="{C}" stroke-width="1.8" stroke-dasharray="7 6" opacity=".7"' if leads_off else None)
    def group(cid, e, p):
        if leads_off:
            ecg = f'<use href="#{e}" xlink:href="#{e}" {ecg_style}/>'
        else:
            ecg = (f'<use href="#{e}" xlink:href="#{e}" stroke="{C}" stroke-width="7" opacity=".3" filter="url(#glow)"/>'
                   f'<use href="#{e}" xlink:href="#{e}" stroke="url(#line)" stroke-width="2.4"/>')
        return (f'<g clip-path="url(#{cid})">{ecg}'
                f'<use href="#{p}" xlink:href="#{p}" stroke="{C2}" stroke-width="2.2" opacity=".92"/></g>')

    leads_txt = (f'<text x="{TX + TW // 2}" y="{ECG_Y - 18}" fill="{C}" font-size="13" font-weight="800" '
                 f'text-anchor="middle" letter-spacing="3" font-family="{mono}">ECG LEADS OFF</text>') if leads_off else ""
    sp_lim = f"LIMITS {SPO2_W}-100"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="100%">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#070b12"/></linearGradient>
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
 <text x="62" y="60" fill="#6b7a8c" font-size="12" letter-spacing="1" font-family="{mono}">@{user} \u00b7 LEAD II \u00b7 {S["rhythm"]}</text>
 {banner_svg(S, C)}
 <text x="{W - 24}" y="40" fill="#6b7a8c" font-size="12" text-anchor="end" letter-spacing="1" font-family="{mono}">UPDATED {now.strftime("%H:%M")} UTC</text>
</g>

<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="#070b12" fill-opacity=".7" stroke="#fff" stroke-opacity=".08"/>
<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="url(#g1)"/>
<rect x="{TX}" y="{PY}" width="{TW}" height="{PH}" rx="14" fill="url(#g2)"/>
<line x1="{TX + 12}" y1="232" x2="{TX + TW - 12}" y2="232" stroke="#fff" stroke-opacity=".07"/>
<g font-family="{mono}" font-size="12" font-weight="700" letter-spacing="2">
 <text x="{TX + 16}" y="100" fill="{C}">II</text>
 <text x="{TX + 16}" y="250" fill="{C2}">PLETH</text>
 <text x="{TX + TW - 16}" y="{PY + PH - 10}" fill="#6b7a8c" font-size="10" text-anchor="end">25 mm/s</text>
</g>
{leads_txt}
<g transform="translate({TX},0)"><g clip-path="url(#outer)">
 {group("cA", "ecgA", "ppgA")}
 {group("cB", "ecgB", "ppgB")}
</g></g>

<g font-family="'Segoe UI',system-ui,-apple-system,sans-serif">
 <rect x="876" y="76" width="300" height="120" rx="14" fill="#0b121c" stroke="{C}" stroke-opacity=".4"/>
 <text x="892" y="100" fill="{C}" font-size="13" font-weight="800" letter-spacing="2">ECG <tspan fill="#8b98a8" font-weight="600">\u00b7 HR</tspan></text>
 <text x="1160" y="100" fill="#6b7a8c" font-size="12" text-anchor="end" font-family="{mono}">LIMITS {LOW_W}-{HIGH_W}</text>
 <g transform="translate(924,146)"><g>{heart_anim}<path d="M0,15 C-30,-5 -18,-30 0,-14 C18,-30 30,-5 0,15 Z" fill="{C}" fill-opacity="{".9" if S["bpm"] else ".25"}"/></g></g>
 {hr_txt}
 <text x="1160" y="172" fill="#8b98a8" font-size="14" font-weight="600" text-anchor="end" letter-spacing="1">BPM</text>

 <rect x="876" y="206" width="300" height="64" rx="14" fill="#0b121c" stroke="{C2}" stroke-opacity=".35"/>
 <text x="892" y="230" fill="{C2}" font-size="13" font-weight="800" letter-spacing="2">SPO2</text>
 <text x="892" y="256" fill="#6b7a8c" font-size="11" font-family="{mono}">{sp_lim}</text>
 {sp_txt}
 <text x="1160" y="262" fill="#8b98a8" font-size="14" font-weight="600" text-anchor="end">%</text>

 {card(876, "EVENTS", S["side"]["n24"], "LAST 24H")}
 {card(980, "STREAK", S["side"]["streak"], "DAYS")}
 {card(1084, "REPOS", S["side"]["repos7"], "LAST 7D")}
</g>
</svg>'''

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
        os.makedirs(a.out_dir if a.demo == "all" else os.path.dirname(a.out) or ".", exist_ok=True)
        cells = []
        for n in names:
            S = make_state(n, **DEMOS[n])
            svg = render(S, "demo", now, random.Random(7), a.still)
            path = os.path.join(a.out_dir, f"{n}.svg") if a.demo == "all" else a.out
            open(path, "w", encoding="utf-8").write(svg)
            alarms = ", ".join(t for _, t in S["alarms"]) or "-"
            print(f"{n:10s} bpm={S['bpm']} spo2={S['spo2']} level={S['level']} alarms=[{alarms}] size={len(svg) // 1024}KB")
            cells.append(f'<figure><img src="{n}.svg"><figcaption>{n}</figcaption></figure>')
        if a.demo == "all":
            open(os.path.join(a.out_dir, "index.html"), "w", encoding="utf-8").write(
                '<!doctype html><meta charset="utf-8"><body style="background:#0d1117;color:#8b98a8;font:13px monospace;'
                'display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px;margin:0">' + "".join(cells))
        return

    user, token = os.environ["GH_USER"], os.environ["GH_TOKEN"]
    S = state_from_activity(activity_stats(fetch_events(user, token), now))
    rng = random.Random(int(now.strftime("%Y%m%d%H")))
    svg = render(S, user, now, rng, a.still)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(svg)
    print(f"state={S['rhythm']} bpm={S['bpm']} spo2={S['spo2']} level={S['level']} size={len(svg) // 1024}KB")

if __name__ == "__main__":
    main()
