import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from theme import THEMES, COMPONENTS, FONT, hexc

SKILLS = {"python": "Python", "javascript": "JavaScript", "git": "Git"}
SOCIALS = {"github": "thehamzaarshad", "linkedin": "LinkedIn", "email": "Email"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def pill(label, comp, mode):
    c = COMPONENTS[comp]
    t = THEMES[mode]
    h = c["line"] + 2 * c["py"]
    w = round(len(label) * c["font"] * 0.58 + 2 * c["px"])
    r = min(c["radius"], h / 2)
    acc = hexc(t["accent"])
    txt = hexc(t["text"])
    font = FONT.replace('"', "'")
    stroke = (
        f'stroke="{acc}" stroke-opacity="{c["stroke"] / 100}" stroke-width="1"'
        if c["stroke"]
        else 'stroke="none"'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{r}" '
        f'fill="{acc}" fill-opacity="{c["fill"] / 100}" {stroke}/>'
        f'<text x="{w / 2}" y="{h / 2}" text-anchor="middle" dominant-baseline="central" '
        f'font-family="{font}" font-size="{c["font"]}" font-weight="{c["weight"]}" '
        f'fill="{txt}">{escape(label)}</text></svg>'
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    for mode in ("light", "dark"):
        for key, label in SKILLS.items():
            with open(os.path.join(OUT, f"skill-{key}-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(pill(label, "label", mode))
        for key, label in SOCIALS.items():
            with open(os.path.join(OUT, f"social-{key}-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(pill(label, "button", mode))
    print("done")


main()