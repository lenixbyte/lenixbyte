#!/usr/bin/env python3
"""Generate the profile README's SVG cards.

Every glyph is baked into vector paths, and every brand icon is inlined, so the
cards render identically everywhere — no webfonts, no external requests.

    python3 tools/build_assets.py

Fonts (SIL OFL) and icons (Simple Icons, CC0) are downloaded once into
tools/.cache/ and reused.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache"
OUT = ROOT / "assets"

GF = "https://raw.githubusercontent.com/google/fonts/main"
ICON_CDN = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons"

# ---------------------------------------------------------------- palette ---
BG0, BG1 = "#0A0E14", "#111823"
BORDER = "#1E2A38"
TEXT = "#E6EDF3"
MUTED = "#8B98A9"
DIM = "#5A6675"
ACCENT = "#5EEAD4"   # teal
ACCENT2 = "#A78BFA"  # violet
CHIP_BG = "#151D29"
CHIP_BORDER = "#232F3F"

W = 1000  # card width for both assets


# ------------------------------------------------------------------ fonts ---
def _fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
    return dest


# The type system: a script face for the name, Syne for anything that should catch the
# eye, Space Grotesk for labels that just need to be read.
SCRIPT = "KaushanScript-Regular"
DISPLAY = "Syne-800"
LABEL = "SpaceGrotesk-500"
LABEL_BOLD = "SpaceGrotesk-700"

# name -> (variable font url, wght) or (static font url, None)
FONTS = {
    SCRIPT: (f"{GF}/ofl/kaushanscript/KaushanScript-Regular.ttf", None),
    DISPLAY: (f"{GF}/ofl/syne/Syne%5Bwght%5D.ttf", 800),
    LABEL: (f"{GF}/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf", 500),
    LABEL_BOLD: (f"{GF}/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf", 700),
}


def font(name: str) -> Path:
    """Return a static TTF, downloading (and instancing, if variable) on first use."""
    dest = CACHE / "fonts" / f"{name}.ttf"
    if dest.exists():
        return dest
    url, weight = FONTS[name]
    if weight is None:
        return _fetch(url, dest)
    family = name.split("-")[0]
    var = _fetch(url, CACHE / "fonts" / f"{family}-var.ttf")
    f = TTFont(var)
    instancer.instantiateVariableFont(f, {"wght": weight}, inplace=True)
    f.save(dest)
    return dest


_cache: dict[str, tuple] = {}


def _load(name: str):
    if name not in _cache:
        f = TTFont(font(name))
        _cache[name] = (f, f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm)
    return _cache[name]


def text_path(s: str, name: str, size: float, x: float = 0, y: float = 0,
              tracking: float = 0) -> tuple[str, float]:
    """Draw `s` as SVG path data with its baseline start at (x, y). -> (d, width)."""
    f, glyphs, cmap, upem = _load(name)
    scale = size / upem
    hmtx = f["hmtx"]
    kern = {}
    if "kern" in f:
        for st in f["kern"].kernTables:
            kern.update(st.kernTable)

    pen = SVGPathPen(glyphs)
    cursor, prev = x, None
    for ch in s:
        gname = cmap.get(ord(ch))
        if gname is None:
            cursor += size * 0.3
            prev = None
            continue
        if prev is not None:
            cursor += kern.get((prev, gname), 0) * scale
        glyphs[gname].draw(TransformPen(pen, Transform(scale, 0, 0, -scale, cursor, y)))
        cursor += hmtx[gname][0] * scale + tracking
        prev = gname
    return pen.getCommands(), cursor - x


def measure(s: str, name: str, size: float, tracking: float = 0) -> float:
    """Advance width of `s`. Proportional faces need this measured, not estimated."""
    f, glyphs, cmap, upem = _load(name)
    hmtx, scale = f["hmtx"], size / upem
    kern = {}
    if "kern" in f:
        for st in f["kern"].kernTables:
            kern.update(st.kernTable)
    total, prev = 0.0, None
    for ch in s:
        gname = cmap.get(ord(ch))
        if gname is None:
            total += size * 0.3
            prev = None
            continue
        if prev is not None:
            total += kern.get((prev, gname), 0) * scale
        total += hmtx[gname][0] * scale + tracking
        prev = gname
    return total


def t(s: str, name: str, size: float, x: float, y: float, fill: str,
      tracking: float = 0, opacity: float | None = None) -> str:
    d, _ = text_path(s, name, size, x, y, tracking)
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<path d="{d}" fill="{fill}"{op}/>'


# ------------------------------------------------------------------ icons ---
def icon_paths(slug: str) -> str | None:
    """Inline path data for a Simple Icons brand mark (24x24 viewBox)."""
    dest = CACHE / "icons" / f"{slug}.svg"
    if not dest.exists():
        try:
            _fetch(f"{ICON_CDN}/{slug}.svg", dest)
        except Exception:
            return None
    svg = dest.read_text()
    return "".join(re.findall(r'<path\s+d="([^"]+)"', svg)) or None


# ------------------------------------------------------------------ chips ---
# (label, simple-icons slug or None, colour on a dark card)
GROUPS: list[tuple[str, list[tuple[str, str | None, str]]]] = [
    ("languages", [
        ("Python", "python", "#4B8BBE"),
        ("TypeScript", "typescript", "#3178C6"),
        ("JavaScript", "javascript", "#F7DF1E"),
        ("C++", "cplusplus", "#649AD2"),
    ]),
    ("ai / agents", [
        ("LangChain", "langchain", "#5EEAD4"),
        ("LangGraph", None, "#5EEAD4"),
        ("AI Workflows", None, "#5EEAD4"),
        ("MCP", "anthropic", "#D97757"),
        ("A2A", None, "#5EEAD4"),
        ("RAG", None, "#5EEAD4"),
        ("Transformers", "huggingface", "#FFD21E"),
        ("Vertex AI", "googlecloud", "#4285F4"),
        ("Azure OpenAI", "openai", "#A78BFA"),
        ("Pinecone", None, "#A78BFA"),
        ("pgvector", "postgresql", "#4169E1"),
        ("LLMOps", None, "#A78BFA"),
    ]),
    ("backend", [
        ("FastAPI", "fastapi", "#009688"),
        ("Flask", "flask", "#C9D1D9"),
        ("Django", "django", "#44B78B"),
        ("Node.js", "nodejs", "#5FA04E"),
        ("Fastify", "fastify", "#C9D1D9"),
        ("Express", "express", "#C9D1D9"),
        ("GraphQL", "graphql", "#E10098"),
        ("Hasura", "hasura", "#5A9BF0"),
        ("Auth", "auth0", "#EB5424"),
        ("WebSockets", "socketdotio", "#C9D1D9"),
        ("MQTT", "mqtt", "#B36BB3"),
        ("Kafka", "apachekafka", "#C9D1D9"),
        ("Redis", "redis", "#FF4438"),
    ]),
    ("data", [
        ("PostgreSQL", "postgresql", "#4169E1"),
        ("MySQL", "mysql", "#7FA9CC"),
        ("MongoDB", "mongodb", "#47A248"),
        ("Firestore", "firebase", "#FFCA28"),
        ("ClickHouse", "clickhouse", "#FFCC00"),
    ]),
    ("cloud / ops", [
        ("AWS", "amazonwebservices", "#FF9900"),
        ("GCP", "googlecloud", "#4285F4"),
        ("Azure", "microsoftazure", "#3B9EEA"),
        ("Docker", "docker", "#2496ED"),
        ("Kubernetes", "kubernetes", "#4C86E8"),
        ("VPS", "linux", "#FCC624"),
        ("Nginx", "nginx", "#009639"),
        ("CI/CD", "githubactions", "#2088FF"),
    ]),
    ("frontend", [
        ("React", "react", "#61DAFB"),
        ("Next.js", "nextdotjs", "#C9D1D9"),
        ("Three.js", "threedotjs", "#C9D1D9"),
        ("Redux", "redux", "#764ABC"),
        ("Tailwind", "tailwindcss", "#06B6D4"),
        ("MUI", "mui", "#007FFF"),
    ]),
]

CHIP_H = 32
CHIP_GAP = 8
ROW_GAP = 10
ICON = 15
LABEL_SIZE = 12.5
LABEL_TRACK = 0.2
PAD_X = 11


def chip(label: str, slug: str | None, colour: str, x: float, y: float) -> tuple[str, float]:
    """Render one chip with its top-left at (x, y). -> (svg, width)."""
    d = icon_paths(slug) if slug else None
    text_w = measure(label, LABEL, LABEL_SIZE, LABEL_TRACK)
    glyph_w = ICON if d else 7
    w = PAD_X * 2 + glyph_w + 7 + text_w

    parts = [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{CHIP_H}" rx="8" '
             f'fill="{CHIP_BG}" stroke="{CHIP_BORDER}"/>']
    gx, gy = x + PAD_X, y + (CHIP_H - ICON) / 2
    if d:
        s = ICON / 24
        parts.append(f'<g transform="translate({gx:.1f},{gy:.1f}) scale({s:.4f})">'
                     f'<path d="{d}" fill="{colour}"/></g>')
    else:
        parts.append(f'<circle cx="{gx + 3.5:.1f}" cy="{y + CHIP_H / 2:.1f}" r="3" fill="{colour}"/>')
    baseline = y + CHIP_H / 2 + LABEL_SIZE * 0.36
    parts.append(t(label, LABEL, LABEL_SIZE, gx + glyph_w + 7, baseline, TEXT, LABEL_TRACK))
    return "".join(parts), w


# ------------------------------------------------------------------ cards ---
def card(width: int, height: int) -> str:
    return (f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" '
            f'fill="url(#bg)" stroke="{BORDER}"/>'
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" '
            f'fill="url(#dots)"/>')


DEFS = f'''<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/>
</linearGradient>
<linearGradient id="name" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{TEXT}"/><stop offset="0.55" stop-color="{ACCENT}"/>
  <stop offset="1" stop-color="{ACCENT2}"/>
</linearGradient>
<linearGradient id="sig" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#2DD4BF"/><stop offset="0.55" stop-color="#5B8DEF"/>
  <stop offset="1" stop-color="#8B5CF6"/>
</linearGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
  <circle cx="1" cy="1" r="1" fill="#8B98A9" opacity="0.07"/>
</pattern>
</defs>'''


def agent_flow(ox: float, oy: float) -> str:
    """An agent graph read left to right: request fans out to workers, then merges.

    Coordinates are local to (ox, oy), which is the entry node.
    """
    lane_x, out_x = 78, 156          # worker column, merge node
    lanes = (-42, 0, 42)             # worker rows
    node_w, node_h = 38, 22

    def edge(x1, y1, x2, y2) -> str:
        mx = (x1 + x2) / 2
        return f"M{x1:.0f} {y1:.0f} C {mx:.0f} {y1:.0f}, {mx:.0f} {y2:.0f}, {x2:.0f} {y2:.0f}"

    p = [f'<g transform="translate({ox},{oy})">']

    # edges first, so nodes sit on top of them
    paths = []
    for y in lanes:
        paths.append(edge(8, 0, lane_x - node_w / 2, y))
    for y in lanes:
        paths.append(edge(lane_x + node_w / 2, y, out_x - 8, 0))
    for d in paths:
        p.append(f'<path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="1.1" opacity="0.22"/>')

    # a request travelling along each edge, staggered so the graph looks busy
    for i, d in enumerate(paths):
        p.append(f'<circle r="2.1" fill="{ACCENT if i < 3 else ACCENT2}">'
                 f'<animateMotion dur="2.8s" begin="{i * 0.42:.2f}s" repeatCount="indefinite" '
                 f'path="{d}"/>'
                 f'<animate attributeName="opacity" values="0;1;1;0" dur="2.8s" '
                 f'begin="{i * 0.42:.2f}s" repeatCount="indefinite"/></circle>')

    # worker nodes — small task cards
    for i, y in enumerate(lanes):
        x = lane_x - node_w / 2
        top = y - node_h / 2
        p.append(f'<rect x="{x:.0f}" y="{top:.0f}" width="{node_w}" height="{node_h}" rx="6" '
                 f'fill="{CHIP_BG}" stroke="{ACCENT2}" stroke-width="1.3" opacity="0.95"/>')
        p.append(f'<circle cx="{x + 9:.0f}" cy="{y:.0f}" r="2.6" fill="{ACCENT2}">'
                 f'<animate attributeName="opacity" values="0.4;1;0.4" dur="{2.4 + i * 0.4:.1f}s" '
                 f'repeatCount="indefinite"/></circle>')
        p.append(f'<rect x="{x + 16:.0f}" y="{y - 3.5:.0f}" width="15" height="2" rx="1" '
                 f'fill="{MUTED}" opacity="0.75"/>')
        p.append(f'<rect x="{x + 16:.0f}" y="{y + 1.5:.0f}" width="9" height="2" rx="1" '
                 f'fill="{MUTED}" opacity="0.45"/>')

    # entry and merge nodes
    for x, colour, dur in ((0, ACCENT, 2.8), (out_x, ACCENT, 3.4)):
        p.append(f'<circle cx="{x}" cy="0" r="16" fill="none" stroke="{colour}" '
                 f'stroke-width="1" opacity="0.18"/>')
        p.append(f'<circle cx="{x}" cy="0" r="8.5" fill="{BG0}" stroke="{colour}" stroke-width="1.7"/>')
        p.append(f'<circle cx="{x}" cy="0" r="3.4" fill="{colour}">'
                 f'<animate attributeName="opacity" values="0.5;1;0.5" dur="{dur}s" '
                 f'repeatCount="indefinite"/></circle>')

    p.append("</g>")
    return "".join(p)


def build_header() -> None:
    h = 232
    name_size = 62
    name_y = 122
    name_d, name_w = text_path("Priyanka Bhardwaj", SCRIPT, name_size, 56, name_y)

    sub = "system design  ·  backend infrastructure  ·  agentic ai"

    swash = (f'<path d="M58 {name_y + 20} C {58 + name_w * 0.3:.0f} {name_y + 32}, '
             f'{58 + name_w * 0.62:.0f} {name_y + 8}, {58 + name_w * 0.96:.0f} {name_y + 22}" '
             f'fill="none" stroke="url(#name)" stroke-width="2.4" stroke-linecap="round" opacity="0.75"/>')

    dots = "".join(f'<circle cx="{28 + i * 15}" cy="26" r="4.5" fill="{c}" opacity="0.55"/>'
                   for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" role="img" aria-label="Priyanka Bhardwaj — '
        f'system design, backend infrastructure, agentic AI">',
        DEFS, card(W, h), dots,
        t("~/lenixbyte", LABEL, 12, 82, 30, DIM, 0.4),
        f'<path d="{name_d}" fill="url(#name)"/>', swash,
        t(sub, DISPLAY, 13.5, 58, 186, "#AAB6C4", 0.7),
        agent_flow(790, 116),
        "</svg>",
    ]
    (OUT / "header.svg").write_text("".join(parts))
    print("assets/header.svg")


def build_stack() -> None:
    label_x, chips_x = 34, 172
    y = 74
    body = []
    for title, items in GROUPS:
        row_y = y
        cx, rows = chips_x, 1
        for label, slug, colour in items:
            svg, w = chip(label, slug, colour, cx, row_y)
            if cx + w > W - 34 and cx > chips_x:  # wrap
                row_y += CHIP_H + ROW_GAP
                rows += 1
                cx = chips_x
                svg, w = chip(label, slug, colour, cx, row_y)
            body.append(svg)
            cx += w + CHIP_GAP
        block_h = rows * CHIP_H + (rows - 1) * ROW_GAP
        body.append(t(title, DISPLAY, 12.5, label_x, y + 21, ACCENT, 0.9))
        rule_w = max(measure(title, DISPLAY, 12.5, 0.9) + 6, 92)
        body.append(f'<line x1="{label_x}" y1="{y + 32}" x2="{label_x + rule_w:.0f}" y2="{y + 32}" '
                    f'stroke="{BORDER}"/>')
        y += block_h + 26
    h = int(y + 12)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" role="img" aria-label="Tech stack">',
        DEFS, card(W, h),
        t("// stack", DISPLAY, 15, 34, 42, TEXT, 0.7),
        t("things i reach for", LABEL, 12,
          34 + measure("// stack", DISPLAY, 15, 0.7) + 14, 42, DIM, 0.3),
        f'<line x1="34" y1="56" x2="{W - 34}" y2="56" stroke="{BORDER}"/>',
        *body,
        "</svg>",
    ]
    (OUT / "stack.svg").write_text("".join(parts))
    print("assets/stack.svg")


LANGS_QUERY = """
{ user(login: "%s") { repositories(first: 100, privacy: PUBLIC, isFork: false, ownerAffiliations: OWNER) {
  nodes { languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
    edges { size node { name color } } } } } } }
"""

# fallback so the build works without gh/network; refresh with --langs
LANGS_SNAPSHOT = [
    ("TypeScript", "#3178c6", 244014), ("Python", "#3572A5", 109174),
    ("HTML", "#e34c26", 87416), ("Shell", "#89e051", 40582),
    ("JavaScript", "#f1e05a", 40346), ("Ruby", "#701516", 33914),
    ("CSS", "#663399", 31016), ("Java", "#b07219", 30135),
    ("C++", "#f34b7d", 14553),
]


def fetch_langs(user: str = "lenixbyte") -> list[tuple[str, str, int]]:
    """Language bytes across the user's public, non-fork repos, via gh. Falls back to the snapshot."""
    import json
    import subprocess
    try:
        out = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={LANGS_QUERY % user}"],
            capture_output=True, text=True, check=True, timeout=40).stdout
        totals: dict[str, tuple[str, int]] = {}
        for repo in json.loads(out)["data"]["user"]["repositories"]["nodes"]:
            for e in repo["languages"]["edges"]:
                name, colour = e["node"]["name"], e["node"]["color"] or MUTED
                prev = totals.get(name, (colour, 0))
                totals[name] = (colour, prev[1] + e["size"])
        ranked = sorted(((n, c, b) for n, (c, b) in totals.items()), key=lambda r: -r[2])
        return ranked[:9] or LANGS_SNAPSHOT
    except Exception as exc:  # offline, no gh, rate-limited
        print(f"  (using language snapshot: {type(exc).__name__})")
        return LANGS_SNAPSHOT


def build_langs(live: bool = True) -> None:
    """A most-used-languages card — the shared github-readme-stats instance is unreliable,
    so this renders the same information locally and always loads."""
    langs = fetch_langs() if live else LANGS_SNAPSHOT
    total = sum(b for _, _, b in langs) or 1

    h = 196
    bar_x, bar_w, bar_y, bar_h = 34, W - 68, 78, 16
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" role="img" aria-label="Most used languages">',
        DEFS, card(W, h),
        t("// most used languages", DISPLAY, 15, 34, 42, TEXT, 0.7),
        t("by bytes across public repos", LABEL, 12,
          34 + measure("// most used languages", DISPLAY, 15, 0.7) + 14, 42, DIM, 0.3),
        f'<line x1="34" y1="56" x2="{W - 34}" y2="56" stroke="{BORDER}"/>',
    ]

    # stacked bar, rounded at the two outer ends via a clip
    parts.append(f'<clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" '
                 f'height="{bar_h}" rx="{bar_h / 2}"/></clipPath>')
    parts.append(f'<g clip-path="url(#barclip)">')
    x = float(bar_x)
    for _, colour, b in langs:
        seg = bar_w * b / total
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{seg + 0.5:.2f}" height="{bar_h}" fill="{colour}"/>')
        x += seg
    parts.append("</g>")

    # legend: three columns
    col_w, lx, ly = (W - 68) / 3, 34, 128
    for i, (name, colour, b) in enumerate(langs):
        cx = lx + (i % 3) * col_w
        cy = ly + (i // 3) * 26
        pct = 100 * b / total
        parts.append(f'<circle cx="{cx + 5:.0f}" cy="{cy - 4:.0f}" r="5" fill="{colour}"/>')
        parts.append(t(name, LABEL, 13, cx + 18, cy, TEXT, 0.2))
        parts.append(t(f"{pct:.1f}%", DISPLAY, 12.5, cx + col_w - 82, cy, MUTED, 0.2))
    parts.append("</svg>")

    (OUT / "langs.svg").write_text("".join(parts))
    print("assets/langs.svg")


def build_footer() -> None:
    """A small script-font sign-off. Transparent, so it works in either GitHub theme."""
    size, h = 34, 78
    d, w = text_path("thanks for stopping by", SCRIPT, size, 0, 44)
    width = int(w + 40)
    swash = (f'<path d="M14 {58} C {w * 0.32:.0f} {68}, {w * 0.66:.0f} {50}, {w * 0.94:.0f} {60}" '
             f'fill="none" stroke="url(#sig)" stroke-width="2" stroke-linecap="round" opacity="0.6"/>')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" '
        f'viewBox="0 0 {width} {h}" role="img" aria-label="thanks for stopping by">',
        DEFS,
        f'<g transform="translate(20,0)"><path d="{d}" fill="url(#sig)"/>{swash}</g>',
        "</svg>",
    ]
    (OUT / "footer.svg").write_text("".join(parts))
    print("assets/footer.svg")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build_header()
    build_stack()
    build_langs()
    build_footer()
