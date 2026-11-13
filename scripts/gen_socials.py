import os, re, pathlib
from xml.sax.saxutils import escape

README = pathlib.Path("README.md")
INPUT = pathlib.Path("socials.txt")
repo = os.environ.get("GITHUB_REPOSITORY", "thehamzaarshad/thehamzaarshad")
RAW = f"https://raw.githubusercontent.com/{repo}/main/assets"

FONT = "Poppins, 'Segoe UI', Helvetica, Arial, sans-serif"
S = 'stroke="FG" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"'

ICONS = {
 "github": f'<circle cx="10" cy="10" r="9" {S}/><path d="M7 6v8M7 11c0-2 2-3 6-3" {S}/><circle cx="7" cy="6" r="1.8" fill="FG"/><circle cx="7" cy="14" r="1.8" fill="FG"/><circle cx="13" cy="8" r="1.8" fill="FG"/>',
 "linkedin": f'<rect width="20" height="20" rx="4" fill="FG"/><text x="10" y="15" text-anchor="middle" font-family="{FONT}" font-weight="800" font-size="11" fill="BG">in</text>',
 "email": f'<rect x="0" y="3" width="20" height="14" rx="3" {S}/><path d="M1.5 5.5L10 11.5l8.5-6" {S}/>',
 "whatsapp": f'<path d="M10 1a9 9 0 0 0-7.7 13.6L1 19l4.5-1.2A9 9 0 1 0 10 1z" {S}/><path d="M7 6.5c0 3.8 3.2 7 7 7l1-1.8-2-1-.9.8c-1-.4-2-1.4-2.4-2.4l.8-.9-1-2z" fill="FG"/>',
 "website": f'<circle cx="10" cy="10" r="9" {S}/><ellipse cx="10" cy="10" rx="4" ry="9" {S}/><path d="M1 10h18" {S}/>',
 "x": f'<path d="M3 3l14 14M17 3L3 17" {S}/>',
 "instagram": f'<rect x="1" y="1" width="18" height="18" rx="5" {S}/><circle cx="10" cy="10" r="4.2" {S}/><circle cx="15" cy="5" r="1.2" fill="FG"/>',
 "youtube": '<rect y="3" width="20" height="14" rx="4" fill="FG"/><path d="M8 7l5 3-5 3z" fill="BG"/>',
 "telegram": f'<path d="M19 2L1 9l6 2.5L19 2zM7 11.5V17l3-3.5" {S}/>',
}
ALIAS = {"twitter": "x", "ig": "instagram", "yt": "youtube", "web": "website",
         "site": "website", "mail": "email", "gmail": "email", "wa": "whatsapp"}

URLS = {
 "github": "https://github.com/{}", "linkedin": "https://linkedin.com/in/{}",
 "x": "https://x.com/{}", "instagram": "https://instagram.com/{}",
 "youtube": "https://youtube.com/@{}", "facebook": "https://facebook.com/{}",
 "telegram": "https://t.me/{}", "tiktok": "https://tiktok.com/@{}",
 "medium": "https://medium.com/@{}", "devto": "https://dev.to/{}",
 "reddit": "https://reddit.com/user/{}", "twitch": "https://twitch.tv/{}",
 "kaggle": "https://kaggle.com/{}", "leetcode": "https://leetcode.com/u/{}",
 "threads": "https://threads.net/@{}", "snapchat": "https://snapchat.com/add/{}",
 "pinterest": "https://pinterest.com/{}", "behance": "https://behance.net/{}",
 "dribbble": "https://dribbble.com/{}", "gitlab": "https://gitlab.com/{}",
 "codepen": "https://codepen.io/{}", "stackoverflow": "https://stackoverflow.com/users/{}",
 "fiverr": "https://fiverr.com/{}", "upwork": "https://upwork.com/freelancers/{}",
 "hashnode": "https://hashnode.com/@{}", "huggingface": "https://huggingface.co/{}",
}

def icon_for(key):
    if key in ICONS:
        return ICONS[key]
    ch = escape((key[:1] or "?").upper())
    return (f'<rect width="20" height="20" rx="5" fill="FG"/><text x="10" y="15" text-anchor="middle" '
            f'font-family="{FONT}" font-weight="800" font-size="12" fill="BG">{ch}</text>')

def link_for(key, val):
    if val.startswith("http"):
        return val
    if key == "email":
        return "mailto:" + val
    if key == "whatsapp":
        return "https://wa.me/" + re.sub(r"\D", "", val)
    if key == "website":
        return "https://" + val
    if key in URLS:
        return URLS[key].format(val.lstrip("@"))
    return ""

items = []
for line in INPUT.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    k, v = line.split(":", 1)
    raw = re.sub(r"[^a-z0-9]+", "", k.lower())
    v = v.strip()
    if raw and v:
        items.append((ALIAS.get(raw, raw), v))

THEMES = {"light": ("#B1901F", "#FFFFFF"), "dark": ("#DCA54C", "#1A160C")}
out = pathlib.Path("assets"); out.mkdir(exist_ok=True)
keep, buttons = set(), []

for key, val in items:
    keep.add(key)
    label = key.title() if val.startswith("http") else val
    w = round(68 + 8.5 * len(label))
    t = escape(label)
    ic = icon_for(key)
    for theme, (bg, fg) in THEMES.items():
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 40" width="{w}" height="40" role="img" aria-label="{t}">\n'
               f'<rect width="{w}" height="40" rx="20" fill="{bg}"/>\n'
               f'<g transform="translate(18 10)">{ic.replace("FG", fg).replace("BG", bg)}</g>\n'
               f'<text x="50" y="25.5" font-family="{FONT}" font-weight="700" font-size="13" letter-spacing=".4" fill="{fg}">{t}</text>\n</svg>\n')
        (out / f"social-{key}-{theme}.svg").write_text(svg, encoding="utf-8")
    pic = (f'<picture>\n'
           f'  <source media="(prefers-color-scheme: dark)" srcset="{RAW}/social-{key}-dark.svg" />\n'
           f'  <img src="{RAW}/social-{key}-light.svg" alt="{escape(key.title())}" />\n</picture>')
    href = link_for(key, val)
    buttons.append(f'<a href="{escape(href, {chr(34): "&quot;"})}">{pic}</a>' if href else pic)

for f in out.glob("social-*-*.svg"):
    k = f.name[len("social-"):].rsplit("-", 1)[0]
    if k not in keep:
        f.unlink()

text = README.read_text(encoding="utf-8")
block = "<!-- SOCIALS-BUTTONS:START -->\n" + "\n".join(buttons) + "\n<!-- SOCIALS-BUTTONS:END -->"
new, n = re.subn(r"<!-- SOCIALS-BUTTONS:START -->.*?<!-- SOCIALS-BUTTONS:END -->",
                 lambda _: block, text, flags=re.S)
if not n:
    print("README mein SOCIALS-BUTTONS markers nahi mile, sirf SVGs bani hain")
elif new != text:
    README.write_text(new, encoding="utf-8")