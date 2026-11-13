#!/usr/bin/env python3
"""Generate every README SVG asset in the quranwbw theme.

Light = Golden Glint (theme-1), Dark = Mocha Night (theme-5).
Run from the repo root:  python scripts/build_assets.py
Writes assets/<name>-light.svg and assets/<name>-dark.svg (same file names the README already uses).
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"

# ---------- editable content ----------
NAME = "HAMZA ARSHAD"
TYPING_LINES = ["Assalam-o-Alaikum!"]
GITHUB_LABEL = "thehamzaarshad"
LINKEDIN_LABEL = "your-profile"
EMAIL_LABEL = "your@email.com"
HEADINGS = {
    "about-me": "About Me",
    "contribution-pulse": "Contribution Pulse",
    "github-engineering-stats": "GitHub Engineering Stats",
    "contribution-analytics": "Contribution Analytics",
    "contribution-activity": "Contribution Activity",
}
SKILLS = ["python", "javascript", "git"]

# ---------- theme tokens (from quranwbw app.html / tailwind config) ----------
# surface = accent @ 6% over bg, strong = accent @ 18% over bg
THEMES = {
    "light": dict(bg="#FFFFFF", accent="#B1901F", text="#000000", surface="#FAF8F2", strong="#F1EBD7"),
    "dark": dict(bg="#20161F", accent="#DCA54C", text="#DCA54C", surface="#2B1F22", strong="#423027"),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif"


def svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}" role="img">{body}</svg>\n'
    )


def diamond(cx, cy, r, fill, opacity=1):
    return f'<path d="M{cx} {cy - r} L{cx + r} {cy} L{cx} {cy + r} L{cx - r} {cy} Z" fill="{fill}" opacity="{opacity}"/>'


def pill(w, h, t, fill_key="surface"):
    return (
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{h / 2}" '
        f'fill="{t[fill_key]}" stroke="{t["accent"]}" stroke-opacity="0.22"/>'
    )


# ---------- assets ----------
def banner(t):
    W, H = 1000, 160
    a = t["accent"]
    deco = (
        '<g fill="none" stroke="{a}" stroke-opacity="0.3" stroke-width="1.2">'
        '<rect x="-30" y="-30" width="60" height="60"/>'
        '<rect x="-30" y="-30" width="60" height="60" transform="rotate(45)"/>'
        '<rect x="-18" y="-18" width="36" height="36" transform="rotate(45)"/></g>'
    ).format(a=a)
    body = (
        pill(W, H, t)
        + f'<g transform="translate(96 80)">{deco}</g><g transform="translate(904 80)">{deco}</g>'
        + f'<text x="506" y="86" text-anchor="middle" font-size="38" font-weight="700" '
        f'letter-spacing="12" fill="{a}">{escape(NAME)}</text>'
        + f'<line x1="400" y1="112" x2="600" y2="112" stroke="{a}" stroke-opacity="0.5"/>'
        + diamond(500, 112, 3.5, a)
    )
    return svg(W, H, body)


def typing(t):
    W, H = 1000, 80
    a = t["accent"]
    n = len(TYPING_LINES)
    slot = 6.0
    T = n * slot
    defs, body = "", ""
    for i, line in enumerate(TYPING_LINES):
        size = 34
        est = round(len(line) * size * 0.56)
        x0 = round((W - est) / 2)
        s = i * slot / T
        ta = s + 2.0 / T
        tb = s + 4.6 / T
        tc = s + 5.4 / T
        kt = ";".join(f"{v:.4f}" for v in (0, s, ta, tb, tc, 1))
        defs += (
            f'<clipPath id="c{i}"><rect x="{x0 - 2}" y="0" height="{H}" width="0">'
            f'<animate attributeName="width" values="0;0;{est + 4};{est + 4};0;0" keyTimes="{kt}" '
            f'dur="{T}s" repeatCount="indefinite"/></rect></clipPath>'
        )
        body += (
            f'<text x="{x0}" y="52" font-size="{size}" font-weight="600" fill="{a}" '
            f'textLength="{est}" lengthAdjust="spacing" clip-path="url(#c{i})">{escape(line)}</text>'
            f'<g><animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
            f'<rect x="{x0}" y="22" width="3" height="40" rx="1.5" fill="{a}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;1;0;0" keyTimes="{kt}" dur="{T}s" repeatCount="indefinite"/>'
            f'<animate attributeName="x" values="{x0};{x0};{x0 + est + 4};{x0 + est + 4};{x0};{x0}" keyTimes="{kt}" '
            f'dur="{T}s" repeatCount="indefinite"/></rect></g>'
        )
    return svg(W, H, f"<defs>{defs}</defs>{body}")


def divider(t):
    W, H = 1200, 24
    a = t["accent"]
    defs = (
        f'<linearGradient id="g" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{a}" stop-opacity="0"/>'
        f'<stop offset="0.15" stop-color="{a}" stop-opacity="0.55"/>'
        f'<stop offset="0.85" stop-color="{a}" stop-opacity="0.55"/>'
        f'<stop offset="1" stop-color="{a}" stop-opacity="0"/></linearGradient>'
    )
    body = (
        f"<defs>{defs}</defs>"
        f'<line x1="0" y1="12" x2="1200" y2="12" stroke="url(#g)" stroke-width="1.5"/>'
        + diamond(600, 12, 5, a)
    )
    return svg(W, H, body)


def heading(t, title):
    W, H = 1000, 64
    a = t["accent"]
    body = (
        pill(W, H, t)
        + diamond(44, 32, 6, a)
        + diamond(956, 32, 6, a)
        + f'<text x="500" y="42" text-anchor="middle" font-size="28" font-weight="600" fill="{t["text"]}">{escape(title)}</text>'
    )
    return svg(W, H, body)


# icons are drawn around (0,0), roughly 18x18
def icon_python(t):
    a = t["accent"]
    return (
        f'<rect x="-8" y="-8" width="10" height="10" rx="3" fill="{a}"/>'
        f'<rect x="-2" y="-2" width="10" height="10" rx="3" fill="{a}" opacity="0.6"/>'
    )


def icon_javascript(t):
    return (
        f'<rect x="-9" y="-9" width="18" height="18" rx="4" fill="{t["accent"]}"/>'
        f'<text x="0" y="3.6" text-anchor="middle" font-size="10" font-weight="800" fill="{t["strong"]}">JS</text>'
    )


def icon_git(t):
    a = t["accent"]
    return (
        f'<g fill="none" stroke="{a}" stroke-width="1.7" stroke-linecap="round">'
        f'<circle cx="-5" cy="-6" r="2.2"/><circle cx="-5" cy="6" r="2.2"/><circle cx="6" cy="-1" r="2.2"/>'
        f'<path d="M-5 -3.8 V3.8"/><path d="M-5 1.5 C-5 -1 1 -1 3.8 -1"/></g>'
    )


def icon_github(t):
    a = t["accent"]
    return (
        f'<g fill="none" stroke="{a}" stroke-width="1.7" stroke-linecap="round">'
        f'<circle cx="0" cy="0" r="9"/><circle cx="-2.5" cy="-3.5" r="1.4"/><circle cx="-2.5" cy="3.5" r="1.4"/>'
        f'<circle cx="3" cy="-1" r="1.4"/><path d="M-2.5 -2.1 V2.1"/><path d="M-2.5 1 C-2.5 -1 0 -1 1.6 -1"/></g>'
    )


def icon_linkedin(t):
    return (
        f'<rect x="-9" y="-9" width="18" height="18" rx="4" fill="{t["accent"]}"/>'
        f'<text x="0" y="4" text-anchor="middle" font-size="11" font-weight="800" fill="{t["strong"]}">in</text>'
    )


def icon_email(t):
    a = t["accent"]
    return (
        f'<g fill="none" stroke="{a}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f'<rect x="-9" y="-6.5" width="18" height="13" rx="2.5"/><path d="M-8.5 -5 L0 2 L8.5 -5"/></g>'
    )


ICONS = {
    "python": icon_python, "javascript": icon_javascript, "git": icon_git,
    "github": icon_github, "linkedin": icon_linkedin, "email": icon_email,
}


def skill(t, key):
    label = key.upper()
    H = 44
    est = round(len(label) * 11.5)
    W = 16 + 28 + 12 + est + 22
    body = (
        pill(W, H, t)
        + f'<circle cx="30" cy="22" r="14" fill="{t["strong"]}"/>'
        + f'<g transform="translate(30 22)">{ICONS[key](t)}</g>'
        + f'<text x="56" y="27.5" font-size="14" font-weight="700" letter-spacing="2" fill="{t["text"]}" '
        f'textLength="{est}" lengthAdjust="spacing">{label}</text>'
    )
    return svg(W, H, body)


def social(t, key, label):
    H = 52
    est = round(len(label) * 9)
    W = 18 + 36 + 14 + est + 26
    body = (
        pill(W, H, t)
        + f'<circle cx="36" cy="26" r="17" fill="{t["strong"]}"/>'
        + f'<g transform="translate(36 26)">{ICONS[key](t)}</g>'
        + f'<text x="62" y="31.5" font-size="16" font-weight="600" fill="{t["text"]}" '
        f'textLength="{est}" lengthAdjust="spacing">{escape(label)}</text>'
    )
    return svg(W, H, body)


def footer(t):
    W, H = 1000, 56
    a = t["accent"]
    body = (
        pill(W, H, t)
        + diamond(466, 28, 4, a, 0.6)
        + diamond(500, 28, 7, a)
        + diamond(534, 28, 4, a, 0.6)
    )
    return svg(W, H, body)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [("banner", banner), ("typing", typing), ("divider", divider), ("footer", footer)]
    count = 0
    for mode, t in THEMES.items():
        files = {}
        for name, fn in jobs:
            files[name] = fn(t)
        for slug, title in HEADINGS.items():
            files[f"heading-{slug}"] = heading(t, title)
        for key in SKILLS:
            files[f"skill-{key}"] = skill(t, key)
        files["social-github"] = social(t, "github", GITHUB_LABEL)
        files["social-linkedin"] = social(t, "linkedin", LINKEDIN_LABEL)
        files["social-email"] = social(t, "email", EMAIL_LABEL)
        for name, content in files.items():
            (OUT / f"{name}-{mode}.svg").write_text(content, encoding="utf-8")
            count += 1
    print(f"wrote {count} files to {OUT}")


if __name__ == "__main__":
    main()
