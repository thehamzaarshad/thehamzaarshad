# Source: quranwbw app.html (theme-1, theme-5, theme-9), tailwind.config.js, commonClasses.js
THEMES = {
    "light": {"bg": (255, 255, 255), "accent": (177, 144, 31), "text": (0, 0, 0)},
    "dark": {"bg": (32, 22, 31), "accent": (220, 165, 76), "text": (220, 165, 76)},
    "dark_luxury": {"bg": (9, 9, 11), "accent": (220, 165, 76), "text": (220, 165, 76)},
}
FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif'

COMPONENTS = {
    "button":  {"fill": 5, "stroke": 0,  "radius": 24,   "px": 16, "py": 8,  "font": 16, "line": 24, "weight": 400},
    "outline": {"fill": 0, "stroke": 20, "radius": 24,   "px": 16, "py": 8,  "font": 16, "line": 24, "weight": 400},
    "label":   {"fill": 5, "stroke": 0,  "radius": 9999, "px": 10, "py": 2,  "font": 14, "line": 20, "weight": 400},
    "tab":     {"fill": 0, "stroke": 0,  "radius": 24,   "px": 16, "py": 8,  "font": 12, "line": 16, "weight": 400},
    "card":    {"fill": 0, "stroke": 20, "radius": 8,    "px": 20, "py": 20, "font": 16, "line": 24, "weight": 400, "border": 2},
}


def hexc(c):
    return "#%02X%02X%02X" % c


def tw(mode, token, n=100):
    """Tailwind 'bg-theme-<token>/<n>' blended over the theme bg, returns hex."""
    t = THEMES[mode]
    a = n / 100
    return hexc(tuple(round(f * a + b * (1 - a)) for f, b in zip(t[token], t["bg"])))