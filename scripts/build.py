"""Regenerates every SVG under assets/ from live GitHub data.

Run locally with `.venv/bin/python scripts/build.py`; the daily workflow runs
the same thing and commits whatever changed."""

import json
import math
import os
import random
import subprocess
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from svgkit import MONO, MONO_M, SANS, SANS_B, SANS_M, SERIF_I, Doc, anim, r, svg, window

USER = "wxtsky"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
TZ = timezone(timedelta(hours=8))

INK = "#f4f4f5"
DIM = "#a1a6ae"
FAINT = "#5d636c"
CORAL = "#ff7a45"
AMBER = "#ffb547"
MINT = "#3ddc97"
SKY = "#7aa7ff"


# ── data ────────────────────────────────────────────────────────────────────


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()


def gh(path, body=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"bearer {token()}", "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch():
    repos = gh(f"/users/{USER}/repos?per_page=100&type=owner")
    own = {x["name"]: x for x in repos if not x["fork"]}
    q = """query($u:String!){user(login:$u){followers{totalCount}
      contributionsCollection{contributionCalendar{totalContributions
      weeks{contributionDays{date contributionCount}}}}}}"""
    user = gh("/graphql", {"query": q, "variables": {"u": USER}})["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    return {
        "stars": sum(x["stargazers_count"] for x in own.values()),
        "followers": user["followers"]["totalCount"],
        "codeisland": own["CodeIsland"],
        "byob": own["byob"],
        "total": cal["totalContributions"],
        "weeks": [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]],
    }


def num(n):
    return f"{n:,}"


# ── shared bits ─────────────────────────────────────────────────────────────


def star_path(cx, cy, ro, ri=None):
    ri = ri or ro * 0.45
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rad = ro if i % 2 == 0 else ri
        pts.append(f"{r(cx + rad * math.cos(a))},{r(cy + rad * math.sin(a))}")
    return "M" + " L".join(pts) + "Z"


def check(x, y, s, color, w=2):
    return (
        f'<path d="M{r(x)},{r(y + s * 0.5)} L{r(x + s * 0.38)},{r(y + s * 0.86)} L{r(x + s)},{r(y + s * 0.1)}" '
        f'fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


MASCOT = ["..XXXX..", ".XXXXXX.", "XXoXXoXX", "XXXXXXXX", "XXXXXXXX", ".X.XX.X."]


def mascot(x, y, color, px=2, bob=True):
    """The pixel buddy CodeIsland gives every agent."""
    cells = []
    for j, row in enumerate(MASCOT):
        for i, c in enumerate(row):
            if c == "X":
                cells.append(f'<rect x="{x + i * px}" y="{y + j * px}" width="{px}" height="{px}" fill="{color}"/>')
            elif c == "o":
                cells.append(f'<rect x="{x + i * px}" y="{y + j * px}" width="{px}" height="{px}" fill="#000"/>')
    move = (
        '<animateTransform attributeName="transform" type="translate" values="0 0;0 -1.5;0 0" '
        'dur="0.7s" repeatCount="indefinite"/>'
        if bob
        else ""
    )
    return f'<g>{move}{"".join(cells)}</g>'


def bars(x, y, color, n=3):
    out = []
    for i in range(n):
        d = 0.5 + i * 0.13
        out.append(
            f'<rect x="{x + i * 4.5}" y="{y - 10}" width="2.6" height="10" rx="1.3" fill="{color}">'
            f'<animate attributeName="height" values="3;10;5;9;3" dur="{d}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{y - 3};{y - 10};{y - 5};{y - 9};{y - 3}" dur="{d}s" repeatCount="indefinite"/>'
            "</rect>"
        )
    return "".join(out)


def cursor(color="#fff"):
    return (
        f'<path d="M0,0 L0,17 L4.6,12.8 L7.6,19.6 L10.4,18.4 L7.5,11.7 L13.4,11.4 Z" '
        f'fill="{color}" stroke="#000" stroke-width="1.2" stroke-linejoin="round"/>'
    )


def notch(cx, w, h, rb, ear=9):
    L, R = cx - w / 2, cx + w / 2
    return (
        f"M{r(L - ear)},0 Q{r(L)},0 {r(L)},{ear} L{r(L)},{r(h - rb)} Q{r(L)},{r(h)} {r(L + rb)},{r(h)} "
        f"L{r(R - rb)},{r(h)} Q{r(R)},{r(h)} {r(R)},{r(h - rb)} L{r(R)},{ear} Q{r(R)},0 {r(R + ear)},0 Z"
    )


def starfield(rng, n, x0, y0, x1, y1, twinkle=0.12, color="#cfd8ff"):
    out = []
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        rad = rng.choice([0.5, 0.6, 0.7, 0.9, 1.1])
        op = rng.uniform(0.12, 0.55)
        tw = ""
        if rng.random() < twinkle:
            d = rng.uniform(2.5, 6)
            tw = (
                f'<animate attributeName="opacity" values="{op:.2f};{op * 0.2:.2f};{op:.2f}" '
                f'dur="{d:.1f}s" begin="{-rng.uniform(0, d):.1f}s" repeatCount="indefinite"/>'
            )
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad}" fill="{color}" opacity="{op:.2f}">{tw}</circle>')
    return "".join(out)


# ── hero: a MacBook screen whose notch is busy running agents ──────────────


def hero(data, today):
    W, H, LOOP, CX = 1000, 520, 18, 500
    doc = Doc()
    t = doc.text
    rng = random.Random(7)

    idle, compact, big = (188, 34, 12), (470, 34, 14), (500, 168, 28)
    shape = lambda s: notch(CX, *s)
    over_c, over_b = (484, 35, 14), (514, 174, 28)
    morph = anim(
        "d",
        [(2.0, shape(idle)), (2.45, shape(over_c)), (2.62, shape(compact)), (6.4, shape(compact)),
         (6.95, shape(over_b)), (7.15, shape(big)), (11.9, shape(big)), (12.45, shape(compact)),
         (15.3, shape(compact)), (15.85, shape(idle))],
        LOOP,
        ease="0.3 0.8 0.4 1",
    )

    glow_frames = [(2.0, SKY), (2.6, CORAL), (6.4, CORAL), (7.1, AMBER), (10.2, AMBER), (10.5, MINT),
                   (15.3, MINT), (15.9, SKY)]
    glow_op = [(2.0, 0.4), (2.6, 0.6), (6.4, 0.6), (7.1, 0.95), (11.9, 0.9), (12.5, 0.55), (15.3, 0.55), (15.9, 0.4)]

    L, R = CX - big[0] / 2 + 24, CX + big[0] / 2 - 24  # content box inside the expanded island
    wing_l, wing_r = CX - idle[0] / 2 - 10, CX + idle[0] / 2 + 10

    # compact A: Claude Code is working
    cl = wing_l - SANS_M.width("Claude Code", 13) - 2
    compact_a = (
        f'<g opacity="0">{window(2.55, 6.25, LOOP, 0.25)}'
        f'<g transform="translate({r(cl - 24)} 11)">{mascot(0, 0, CORAL)}</g>'
        f'{t(SANS_M, "Claude Code", cl, 22, 13, INK)}'
        f'{t(MONO, "README.md", wing_r + 2, 22, 12, DIM)}'
        f'{bars(wing_r + 4 + MONO.width("README.md", 12) + 8, 22, CORAL)}'
        "</g>"
    )

    # compact B: everything finished
    cb = wing_l - SANS_M.width("3 agents", 13) - 2
    compact_b = (
        f'<g opacity="0">{window(12.45, 15.2, LOOP, 0.25)}'
        f'<g transform="translate({r(cb - 24)} 11)">{mascot(0, 0, MINT)}</g>'
        f'{t(SANS_M, "3 agents", cb, 22, 13, INK)}'
        f'{t(MONO, "all done", wing_r + 2, 22, 12, MINT)}'
        f'{check(wing_r + 4 + MONO.width("all done", 12) + 8, 12.5, 11, MINT, 1.8)}'
        "</g>"
    )

    # expanded: Codex asks to push, the cursor approves
    cx_l = wing_l - SANS_M.width("Codex", 13) - 2
    head_wait = (
        f'<g opacity="0">{window(7.0, 10.25, LOOP, 0.3)}'
        f'<g transform="translate({r(cx_l - 24)} 11)">{mascot(0, 0, AMBER)}</g>'
        f'{t(SANS_M, "Codex", cx_l, 22, 13, INK)}'
        f'<circle cx="{wing_r + 6}" cy="17.5" r="3.2" fill="{AMBER}">'
        '<animate attributeName="opacity" values="1;0.25;1" dur="1s" repeatCount="indefinite"/></circle>'
        f'{t(MONO, "needs approval", wing_r + 16, 22, 12, AMBER)}'
        "</g>"
    )
    head_ok = (
        f'<g opacity="0">{window(10.3, 11.75, LOOP, 0.25)}'
        f'<g transform="translate({r(cx_l - 24)} 11)">{mascot(0, 0, MINT)}</g>'
        f'{t(SANS_M, "Codex", cx_l, 22, 13, INK)}'
        f'{check(wing_r + 2, 12.5, 11, MINT, 1.8)}'
        f'{t(MONO, "approved", wing_r + 20, 22, 12, MINT)}'
        "</g>"
    )
    bw = (R - L - 16) / 3
    btn_y, btn_h = 114, 36
    allow_cx, allow_cy = L + 2 * (bw + 8) + bw / 2, btn_y + btn_h / 2
    buttons = []
    for i, (label, fill, ink) in enumerate([("Deny", "#17191d", DIM), ("Always allow", "#17191d", DIM), ("Allow", INK, "#000")]):
        bx = L + i * (bw + 8)
        btn = (
            f'<rect x="{r(bx)}" y="{btn_y}" width="{r(bw)}" height="{btn_h}" rx="18" fill="{fill}" '
            f'stroke="{"none" if i == 2 else "#24272d"}"/>'
        )
        if i == 2:
            lw = SANS_M.width("Allow", 14) + 8 + MONO.width("↵", 13)
            btn += t(SANS_M, "Allow", bx + bw / 2 - lw / 2, btn_y + 23, 14, ink)
            btn += t(MONO, "↵", bx + bw / 2 + lw / 2, btn_y + 23, 13, "#555", anchor="end")
            btn = (
                f'<g transform="translate({r(allow_cx)} {r(allow_cy)})"><g>'
                + anim("transform", [(9.7, "1"), (9.8, "0.94"), (10.0, "1")], LOOP, tag="animateTransform", extra='type="scale"')
                + f'<g transform="translate({r(-allow_cx)} {r(-allow_cy)})">{btn}</g></g></g>'
            )
        else:
            btn += t(SANS_M, label, bx + bw / 2, btn_y + 23, 14, ink, anchor="middle")
        buttons.append(btn)
    cmd_y = 64
    body_wait = (
        f'<g opacity="0">{window(7.2, 10.2, LOOP, 0.3)}'
        f'{t(SANS, "wants to run a command", L, 52, 13, FAINT)}'
        f'<rect x="{L}" y="{cmd_y}" width="{R - L}" height="40" rx="11" fill="#0e0f12" stroke="#22252b"/>'
        f'{t(MONO, "$", L + 16, cmd_y + 25, 14, FAINT)}'
        f'{t(MONO_M, "git push", L + 34, cmd_y + 25, 14, INK)}'
        f'{t(MONO, "origin main", L + 34 + MONO_M.width("git push ", 14), cmd_y + 25, 14, SKY)}'
        f'{"".join(buttons)}'
        "</g>"
    )
    ok_w = 26 + 12 + SANS_M.width("Pushed to main", 17)
    ok_x = CX - ok_w / 2
    body_ok = (
        f'<g opacity="0">{window(10.45, 11.7, LOOP, 0.3)}'
        f'<circle cx="{r(ok_x + 13)}" cy="92" r="13" fill="{MINT}" opacity="0.15"/>'
        f'{check(ok_x + 7, 86, 12, MINT, 2.2)}'
        f'{t(SANS_M, "Pushed to main", ok_x + 38, 98, 17, INK)}'
        f'{t(MONO, "a3f9c21  main → origin/main  ·  0.8s", CX, 126, 12, FAINT, anchor="middle")}'
        "</g>"
    )
    ripple = (
        f'<circle cx="{r(allow_cx)}" cy="{r(allow_cy)}" r="0" fill="none" stroke="#fff" stroke-width="1.5" opacity="0">'
        + anim("r", [(9.75, 2), (10.3, 30)], LOOP, ease="0.2 0.6 0.3 1")
        + anim("opacity", [(9.74, 0), (9.75, 0.6), (10.3, 0)], LOOP)
        + "</circle>"
    )
    path_frames = [(8.3, "300 210"), (9.55, f"{r(allow_cx - 6)} {r(allow_cy - 4)}"), (10.3, f"{r(allow_cx - 6)} {r(allow_cy - 4)}"),
                   (11.2, f"{r(allow_cx + 60)} {r(allow_cy + 90)}")]
    pointer = (
        "<g>"
        + anim("transform", path_frames, LOOP, tag="animateTransform", extra='type="translate"', ease="0.45 0 0.2 1")
        + f'<g opacity="0">{window(8.3, 10.5, LOOP, 0.35)}<g>'
        + anim("transform", [(9.68, "1"), (9.78, "0.85"), (9.95, "1")], LOOP, tag="animateTransform", extra='type="scale"')
        + cursor()
        + "</g></g></g>"
    )

    # menu bar
    menu = [f'<rect width="{W}" height="34" fill="#fff" opacity="0.035"/>',
            f'<rect y="34" width="{W}" height="1" fill="#fff" opacity="0.06"/>',
            t(SANS_B, USER, 24, 22, 13.5, INK)]
    mx = 24 + SANS_B.width(USER, 13.5) + 22
    for item in ("Ship", "Agents", "Browser", "Notes"):
        menu.append(t(SANS, item, mx, 22, 13.5, "#c9ccd3"))
        mx += SANS.width(item, 13.5) + 20
    day = today.strftime("%a %b ") + str(today.day)
    rx = W - 24 - SANS_M.width(day, 13.5)
    menu.append(t(SANS_M, day, rx, 22, 13.5, "#e3e5e8"))
    rx -= 22 + 24  # battery
    menu.append(
        f'<rect x="{rx}" y="11.5" width="22" height="11" rx="3.2" fill="none" stroke="#c9ccd3" stroke-opacity=".7"/>'
        f'<rect x="{rx + 2}" y="13.5" width="14" height="7" rx="1.6" fill="#e3e5e8"/>'
        f'<rect x="{rx + 23}" y="15" width="1.6" height="4" rx=".8" fill="#c9ccd3" opacity=".7"/>'
    )
    rx -= 26  # wifi
    wcx, wcy = rx + 8, 23
    for i, rad in enumerate((10, 6.6, 3.2)):
        a = math.radians(44)
        menu.append(
            f'<path d="M{r(wcx - rad * math.sin(a))},{r(wcy - rad * math.cos(a))} A{rad},{rad} 0 0 1 '
            f'{r(wcx + rad * math.sin(a))},{r(wcy - rad * math.cos(a))}" fill="none" stroke="#e3e5e8" '
            f'stroke-width="1.9" stroke-linecap="round"/>'
        )
    menu.append(f'<circle cx="{wcx}" cy="{wcy - 0.6}" r="1.4" fill="#e3e5e8"/>')
    stars = num(data["stars"])
    rx -= 18 + MONO.width(stars, 12.5) + 16
    menu.append(f'<path d="{star_path(rx + 6, 17, 6)}" fill="{AMBER}"/>')
    menu.append(t(MONO, stars, rx + 16, 21.5, 12.5, "#e3e5e8"))

    # wordmark
    WM = 196
    w_wxt, w_sky = SERIF_I.width("wxt", WM), SERIF_I.width("sky", WM)
    wx = CX - (w_wxt + w_sky) / 2 - 6
    WY = 318
    sky_mask = t(SERIF_I, "sky", wx + w_wxt, WY, WM, "#fff")
    wordmark = (
        t(SERIF_I, "wxt", wx, WY, WM, INK)
        + f'<rect x="{r(wx + w_wxt - 20)}" y="{WY - 170}" width="{r(w_sky + 60)}" height="230" fill="url(#skyfill)" mask="url(#skym)"/>'
    )
    wordmark_mask = t(SERIF_I, "wxt", wx, WY, WM, "#fff") + sky_mask

    pill_txt = "now shipping CodeIsland & byob"
    pw = MONO.width(pill_txt, 12) + 44
    pill = (
        f'<rect x="{r(CX - pw / 2)}" y="104" width="{r(pw)}" height="28" rx="14" fill="#fff" fill-opacity=".04" stroke="#fff" stroke-opacity=".1"/>'
        f'<circle cx="{r(CX - pw / 2 + 18)}" cy="118" r="3.5" fill="{MINT}"/>'
        f'<circle cx="{r(CX - pw / 2 + 18)}" cy="118" r="3.5" fill="none" stroke="{MINT}">'
        '<animate attributeName="r" values="3.5;9" dur="2s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values=".8;0" dur="2s" repeatCount="indefinite"/></circle>'
        f'{t(MONO, pill_txt, CX - pw / 2 + 30, 122.5, 12, "#c9ccd3")}'
    )

    defs = f"""
      <clipPath id="screen"><rect width="{W}" height="{H}" rx="22"/></clipPath>
      <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stop-color="{SKY}" stop-opacity=".85">{anim("stop-color", glow_frames, LOOP)}</stop>
        <stop offset="0.45" stop-color="{SKY}" stop-opacity=".22">{anim("stop-color", glow_frames, LOOP)}</stop>
        <stop offset="1" stop-color="{SKY}" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="skyfill" x1="0" y1="0.15" x2="1" y2="0.85">
        <stop offset="0" stop-color="#a9c8ff"/><stop offset=".55" stop-color="#c7b6ff"/><stop offset="1" stop-color="#ffb38a"/>
      </linearGradient>
      <linearGradient id="rim" x1="0" x2="1">
        <stop offset="0" stop-color="#8fb4ff" stop-opacity="0"/><stop offset=".5" stop-color="#b9cfff" stop-opacity=".75"/>
        <stop offset="1" stop-color="#8fb4ff" stop-opacity="0"/>
      </linearGradient>
      <radialGradient id="haze" cx=".5" cy="1" r=".6">
        <stop offset="0" stop-color="#3b5bdb" stop-opacity=".28"/><stop offset="1" stop-color="#3b5bdb" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="sheen" gradientUnits="userSpaceOnUse" x1="-300" y1="0" x2="0" y2="0">
        <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".55"/>
        <stop offset="1" stop-color="#fff" stop-opacity="0"/>
        {anim("gradientTransform", [(12.6, "0 0"), (14.4, "1300 0")], LOOP, tag="animateTransform", extra='type="translate"', ease="0.4 0 0.2 1")}
      </linearGradient>
      <mask id="skym"><rect width="{W}" height="{H}" fill="#000"/>{sky_mask}</mask>
      <mask id="wm"><rect width="{W}" height="{H}" fill="#000"/>{wordmark_mask}</mask>
    """

    body = f"""
    <g clip-path="url(#screen)">
      <rect width="{W}" height="{H}" fill="#050608"/>
      {starfield(rng, 150, 0, 40, W, 440)}
      <ellipse cx="{CX}" cy="0" rx="560" ry="330" fill="url(#glow)" opacity=".4">{anim("opacity", glow_op, LOOP)}</ellipse>
      <rect y="320" width="{W}" height="200" fill="url(#haze)"/>
      <ellipse cx="{CX}" cy="1260" rx="1150" ry="800" fill="#06070a"/>
      <ellipse cx="{CX}" cy="1260" rx="1150" ry="800" fill="none" stroke="url(#rim)" stroke-width="1.4"/>
      {"".join(menu)}
      {pill}
      {wordmark}
      <rect width="{W}" height="{H}" fill="url(#sheen)" mask="url(#wm)"/>
      {t(SANS, "Building tools that make human × AI collaboration feel native.", CX, 370, 21, DIM, anchor="middle")}
      {t(MONO, "SWIFT · MACOS · IOS · WATCHOS · MCP · CHROME · TYPESCRIPT", CX, 410, 11.5, FAINT, anchor="middle", ls=2.2)}
      {t(MONO, "↓  things I've shipped", CX, 496, 11.5, "#3d424a", anchor="middle", ls=0.6)}
      <path d="{shape(idle)}" fill="#000">{morph}</path>
      <circle cx="{CX}" cy="15" r="3.6" fill="#0b0d14"/><circle cx="{CX - 1}" cy="14" r="1.1" fill="#24314f"/>
      {compact_a}{head_wait}{body_wait}{ripple}{head_ok}{body_ok}{compact_b}{pointer}
    </g>
    <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" stroke="#fff" stroke-opacity=".08"/>
    """
    title = f"{USER} — Building tools that make human × AI collaboration feel native."
    return svg(W, H, f"<defs>{defs}</defs>{body}", doc, title=title)


# ── project cards ───────────────────────────────────────────────────────────


def card_frame(doc, W, H, vis_h, visual, title, repo, desc, chips, accent):
    t = doc.text
    stars, forks = num(repo["stargazers_count"]), num(repo["forks_count"])
    sx = W - 32 - MONO_M.width(stars, 17)
    stat = f'<path d="{star_path(sx - 13, 260.5, 8)}" fill="{AMBER}"/>' + t(MONO_M, stars, sx, 267, 17, INK)
    fx = sx - 32 - MONO.width(forks, 15)
    stat += (
        f'<g transform="translate({r(fx - 18)} 252)" fill="none" stroke="{FAINT}" stroke-width="1.6" stroke-linecap="round">'
        '<circle cx="3" cy="2.5" r="2.2"/><circle cx="11" cy="2.5" r="2.2"/><circle cx="7" cy="14.5" r="2.2"/>'
        '<path d="M3,4.7 V6.5 Q3,8.5 5,8.5 H9 Q11,8.5 11,6.5 V4.7 M7,8.5 V12.3"/></g>'
    ) + t(MONO, forks, fx, 266.5, 15, FAINT)
    lines = "".join(t(SANS, ln, 32, 302 + i * 24, 16.5, DIM) for i, ln in enumerate(desc))
    cx, chip_svg = 32, []
    for c in chips:
        cw = MONO.width(c, 12) + 24
        chip_svg.append(
            f'<rect x="{r(cx)}" y="344" width="{r(cw)}" height="28" rx="14" fill="#fff" fill-opacity=".035" stroke="#fff" stroke-opacity=".08"/>'
            + t(MONO, c, cx + 12, 362.5, 12, "#b4b8bf")
        )
        cx += cw + 8
    return f"""
    <defs><clipPath id="card"><rect width="{W}" height="{H}" rx="20"/></clipPath>
      <clipPath id="vis"><rect width="{W}" height="{vis_h}"/></clipPath>
      <linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{accent}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{accent}" stop-opacity=".9"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>
    <g clip-path="url(#card)">
      <rect width="{W}" height="{H}" fill="#0a0b0e"/>
      <g clip-path="url(#vis)">{visual}</g>
      <rect y="{vis_h}" width="{W}" height="1" fill="url(#edge)" opacity=".7"/>
      {t(SANS_B, title, 32, 268, 30, INK)}
      {stat}{lines}{"".join(chip_svg)}
    </g>
    <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="#fff" stroke-opacity=".09"/>
    """


def cycle(start, length, loop, d=0.3):
    """Opacity frames for a slot that may wrap past the end of the loop."""
    s = start % loop
    e = s + length
    if e <= loop:
        return window(s, e - d, loop, d)
    e -= loop
    return anim("opacity", [(0, 1), (e - d, 1), (e, 0), (s, 0), (s + d, 1)], loop)


def card_codeisland(data):
    W, H, VIS, LOOP = 600, 400, 222, 9
    doc = Doc()
    t = doc.text
    CX, PW = 300, 380
    rows = [("Claude Code", CORAL), ("Codex", AMBER), ("Gemini CLI", SKY)]
    states = [("thinking…", CORAL), ("needs approval", AMBER), ("done", MINT)]
    L, R = CX - PW / 2 + 22, CX + PW / 2 - 22
    row_svg = []
    for i, (name, col) in enumerate(rows):
        y = 58 + i * 42
        row_svg.append(f'<rect x="{L - 8}" y="{y - 15}" width="{R - L + 16}" height="34" rx="10" fill="#fff" fill-opacity=".04"/>')
        row_svg.append(f'<g transform="translate({L + 4} {y - 4})">{mascot(0, 0, col)}</g>')
        row_svg.append(t(SANS_M, name, L + 30, y + 6, 14, INK))
        for k, (label, scol) in enumerate(states):
            slot = cycle(i * 3 + k * 3, 3, LOOP)
            mark = (
                check(R - MONO.width(label, 12) - 18, y - 4, 10, scol, 1.8)
                if label == "done"
                else f'<circle cx="{r(R - MONO.width(label, 12) - 12)}" cy="{y + 1.5}" r="3" fill="{scol}">'
                '<animate attributeName="opacity" values="1;.3;1" dur="1.1s" repeatCount="indefinite"/></circle>'
            )
            row_svg.append(f'<g opacity="0">{slot}{mark}{t(MONO, label, R, y + 6, 12, scol, anchor="end")}</g>')
    visual = f"""
      <defs><linearGradient id="wall" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#16245e"/><stop offset=".5" stop-color="#4b2a7b"/><stop offset="1" stop-color="#c25a6e"/></linearGradient>
        <radialGradient id="wglow" cx=".25" cy=".9" r=".7"><stop offset="0" stop-color="#ff9b6a" stop-opacity=".5"/>
        <stop offset="1" stop-color="#ff9b6a" stop-opacity="0"/></radialGradient></defs>
      <rect width="{W}" height="{VIS}" fill="url(#wall)"/>
      <rect width="{W}" height="{VIS}" fill="url(#wglow)"/>
      <rect width="{W}" height="24" fill="#000" opacity=".18"/>
      <path d="{notch(CX, PW, 186, 26)}" fill="#000"/>
      <circle cx="{CX}" cy="12" r="3" fill="#0b0d14"/>
      {t(MONO, "3 sessions", L - 6, 17, 11, FAINT)}
      {t(MONO, "30+ tools", R + 6, 17, 11, FAINT, anchor="end")}
      {"".join(row_svg)}
    """
    body = card_frame(
        doc, W, H, VIS, visual, "CodeIsland", data["codeisland"],
        ["Your AI coding agents, live in the MacBook notch —", "approve tool calls without leaving your window."],
        ["Swift", "macOS", "iPhone", "Watch", "30+ agents"], AMBER,
    )
    return svg(W, H, body, doc, title="CodeIsland — Your AI coding agents, live in the MacBook notch.")


def card_byob(data):
    W, H, VIS, LOOP = 600, 400, 222, 9
    doc = Doc()
    t = doc.text
    bx, by, bw = 46, 26, 508
    star_x, star_y, sw, sh = bx + bw - 108, by + 86, 84, 30
    tgt = f"{star_x + 30} {star_y + 18}"
    log = [
        ("browser_navigate", "github.com/wxtsky/byob", 0.2, 1.7),
        ("browser_click", "“Star”", 1.7, 3.6),
        ("✓", "done — in your own signed-in Chrome", 3.6, 8.2),
    ]
    log_svg = []
    for fn, arg, a, b in log:
        if fn == "✓":
            w = 18 + MONO.width(arg, 12)
            x0 = W / 2 - w / 2
            inner = check(x0, 191, 10, MINT, 1.8) + t(MONO, arg, x0 + 18, 200, 12, "#c9ccd3")
        else:
            w = MONO_M.width(fn, 12) + 10 + MONO.width(arg, 12)
            x0 = W / 2 - w / 2
            inner = t(MONO_M, fn, x0, 200, 12, CORAL) + t(MONO, arg, x0 + MONO_M.width(fn, 12) + 10, 200, 12, "#c9ccd3")
        log_svg.append(f'<g opacity="0">{window(a, b - 0.25, LOOP, 0.25)}'
                       f'<rect x="{r(W / 2 - w / 2 - 16)}" y="182" width="{r(w + 32)}" height="28" rx="14" fill="#000" fill-opacity=".75" stroke="#fff" stroke-opacity=".12"/>'
                       f"{inner}</g>")
    skeleton = "".join(
        f'<rect x="{bx + 24}" y="{by + 138 + i * 16}" width="{w}" height="7" rx="3.5" fill="#fff" opacity=".07"/>'
        for i, w in enumerate((300, 360, 250, 330))
    )
    visual = f"""
      <defs><pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse">
        <path d="M22,0 H0 V22" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern>
        <radialGradient id="bglow" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="{CORAL}" stop-opacity=".22"/>
        <stop offset="1" stop-color="{CORAL}" stop-opacity="0"/></radialGradient></defs>
      <rect width="{W}" height="{VIS}" fill="#0d0e12"/>
      <rect width="{W}" height="{VIS}" fill="url(#grid)"/>
      <rect width="{W}" height="{VIS}" fill="url(#bglow)"/>
      <rect x="{bx}" y="{by}" width="{bw}" height="260" rx="12" fill="#16181d" stroke="#fff" stroke-opacity=".1"/>
      <circle cx="{bx + 18}" cy="{by + 17}" r="4.5" fill="#ff5f57"/><circle cx="{bx + 33}" cy="{by + 17}" r="4.5" fill="#febc2e"/>
      <circle cx="{bx + 48}" cy="{by + 17}" r="4.5" fill="#28c840"/>
      <path d="M{bx + 66},{by + 32} V{by + 10} Q{bx + 66},{by + 6} {bx + 70},{by + 6} H{bx + 216} Q{bx + 220},{by + 6} {bx + 220},{by + 10} V{by + 32} Z" fill="#202329"/>
      {t(SANS_M, "wxtsky/byob", bx + 80, by + 23, 12, INK)}
      {t(SANS, "Inbox (3)", bx + 236, by + 23, 12, FAINT)}
      {t(SANS, "Calendar", bx + 320, by + 23, 12, FAINT)}
      <rect x="{bx}" y="{by + 32}" width="{bw}" height="34" fill="#202329"/>
      <rect x="{bx + 14}" y="{by + 39}" width="{bw - 64}" height="21" rx="10.5" fill="#121418"/>
      <path d="M{bx + 28},{by + 47} v-2 a3,3 0 0 1 6,0 v2 M{bx + 26.5},{by + 47} h9 v6.5 h-9 z" fill="none" stroke="{FAINT}" stroke-width="1.2"/>
      {t(MONO, "github.com/wxtsky/byob", bx + 44, by + 54, 11.5, "#c9ccd3")}
      <circle cx="{bx + bw - 26}" cy="{by + 49}" r="10" fill="url(#bglow)"/>
      <circle cx="{bx + bw - 26}" cy="{by + 49}" r="9" fill="#2a2f3a"/>
      {t(SANS_B, "W", bx + bw - 26, by + 53.5, 11, INK, anchor="middle")}
      <circle cx="{bx + bw - 19}" cy="{by + 56}" r="3.4" fill="{MINT}" stroke="#202329" stroke-width="1.5"/>
      {t(SANS_M, "wxtsky", bx + 24, by + 107, 17, DIM)}{t(SANS_B, " / byob", bx + 24 + SANS_M.width("wxtsky", 17), by + 107, 17, INK)}
      {t(MONO, "Public · MCP server · Chrome extension", bx + 24, by + 127, 11, FAINT)}
      {skeleton}
      <g>
        <rect x="{star_x}" y="{star_y}" width="{sw}" height="{sh}" rx="8" fill="#21252c" stroke="#fff" stroke-opacity=".12"/>
        <g opacity="1">{anim("opacity", [(2.55, 1), (2.6, 0), (8.3, 0), (8.5, 1)], LOOP)}
          <path d="{star_path(star_x + 20, star_y + 15, 6.5)}" fill="none" stroke="{DIM}" stroke-width="1.3" stroke-linejoin="round"/>
          {t(SANS_M, "Star", star_x + 33, star_y + 19.5, 12.5, "#d7dade")}</g>
        <g opacity="0">{anim("opacity", [(2.55, 0), (2.6, 1), (8.3, 1), (8.5, 0)], LOOP)}
          <path d="{star_path(star_x + 16, star_y + 15, 6.5)}" fill="{AMBER}"/>
          {t(SANS_M, "Starred", star_x + 28, star_y + 19.5, 12.5, AMBER)}</g>
      </g>
      <circle cx="{star_x + 30}" cy="{star_y + 18}" r="0" fill="none" stroke="{CORAL}" stroke-width="1.6" opacity="0">
        {anim("r", [(2.5, 2), (3.1, 26)], LOOP, ease="0.2 0.6 0.3 1")}{anim("opacity", [(2.49, 0), (2.5, .8), (3.1, 0)], LOOP)}</circle>
      {"".join(log_svg)}
      <g>{anim("transform", [(0.8, "150 205"), (2.3, tgt), (4.4, tgt), (5.6, "430 250"), (8.6, "430 250"), (8.7, "150 205")], LOOP, tag="animateTransform", extra='type="translate"', ease="0.45 0 0.2 1")}
        <g opacity="0">{anim("opacity", [(0.5, 0), (0.8, 1), (5.2, 1), (5.6, 0)], LOOP)}
          <g>{anim("transform", [(2.45, "1"), (2.55, "0.85"), (2.7, "1")], LOOP, tag="animateTransform", extra='type="scale"')}{cursor()}</g>
          <rect x="12" y="18" width="{r(MONO_M.width("agent", 11) + 14)}" height="18" rx="9" fill="{CORAL}"/>
          {t(MONO_M, "agent", 19, 30.5, 11, "#1a0d06")}
        </g>
      </g>
    """
    body = card_frame(
        doc, W, H, VIS, visual, "byob", data["byob"],
        ["Bring Your Own Browser — let your AI agent drive", "the Chrome you already have open and signed in."],
        ["MCP", "Chrome MV3", "JavaScript", "local-first"], CORAL,
    )
    return svg(W, H, body, doc, title="byob — Bring Your Own Browser: let your AI agent use the Chrome you already have open.")


# ── sky: a year of contributions as a night over a city ────────────────────


def moon_phase(d):
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    now = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
    return ((now - ref).total_seconds() / 86400 / 29.530588853) % 1


def moon(cx, cy, rad, p):
    k = abs(math.cos(2 * math.pi * p)) * rad
    top, bot = f"{cx},{cy - rad}", f"{cx},{cy + rad}"
    if p < 0.5:
        limb, term = 1, 0 if p < 0.25 else 1
    else:
        limb, term = 0, 0 if p < 0.75 else 1
    lit = f"M{top} A{rad},{rad} 0 0 {limb} {bot} A{r(k)},{rad} 0 0 {term} {top} Z"
    names = ["new moon", "waxing crescent", "first quarter", "waxing gibbous", "full moon",
             "waning gibbous", "last quarter", "waning crescent"]
    name = names[int((p * 8 + 0.5) % 8)]
    illum = round((1 - math.cos(2 * math.pi * p)) / 2 * 100)
    shape = (
        f'<circle cx="{cx}" cy="{cy}" r="{rad * 3.2}" fill="url(#moonglow)"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="#1a2030"/>'
        f'<path d="{lit}" fill="#f3ead2"/>'
    )
    return shape, f"{name} · {illum}%"


def moon_label_for(p):
    return moon(0, 0, 1, p)[1].upper()


def sky(data, today):
    W, H = 1000, 380
    doc = Doc()
    t = doc.text
    rng = random.Random(11)
    weeks = data["weeks"]
    days = [d for w in weeks for d in w]
    counts = [c for _, c in days]
    peak = max(counts) or 1
    active = sum(1 for c in counts if c)
    best_day, best = max(days, key=lambda d: d[1])
    streak = run = 0
    for c in counts:
        run = run + 1 if c else 0
        streak = max(streak, run)

    x0, x1, y0, y1 = 44, 956, 128, 236
    dx, dy = (x1 - x0) / (len(weeks) - 1), (y1 - y0) / 6
    dust, stars, halos = [], [], []
    for wi, w in enumerate(weeks):
        for d_str, c in w:
            di = date.fromisoformat(d_str).weekday()
            di = (di + 1) % 7  # Sunday first, like GitHub
            jr = random.Random(d_str)
            x = x0 + wi * dx + jr.uniform(-4.5, 4.5)
            y = y0 + di * dy + jr.uniform(-5, 5)
            if not c:
                dust.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r=".8" opacity="{jr.uniform(.08, .2):.2f}"/>')
                continue
            s = math.sqrt(c / peak)
            rad = 1.2 + 2.6 * s
            op = 0.55 + 0.45 * s
            col = "#ffe2b8" if s > 0.6 else "#ffffff" if s > 0.3 else "#cddcff"
            dur = jr.uniform(2.4, 6)
            stars.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.2f}" fill="{col}" opacity="{op:.2f}">'
                f'<animate attributeName="opacity" values="{op:.2f};{op * .45:.2f};{op:.2f}" dur="{dur:.1f}s" '
                f'begin="{-jr.uniform(0, dur):.1f}s" repeatCount="indefinite"/></circle>'
            )
            if s > 0.3:
                halos.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad * 4:.1f}" fill="url(#halo)" opacity="{s:.2f}"/>')
                g = rad * 3.4
                halos.append(
                    f'<path d="M{x:.1f},{y - g:.1f} L{x + .7:.1f},{y:.1f} L{x:.1f},{y + g:.1f} L{x - .7:.1f},{y:.1f} Z '
                    f'M{x - g:.1f},{y:.1f} L{x:.1f},{y - .7:.1f} L{x + g:.1f},{y:.1f} L{x:.1f},{y + .7:.1f} Z" fill="#fff" opacity="{.5 * s:.2f}"/>'
                )

    # skyline: one block of towers per month, sized by that month's commits
    months = {}
    for wi, w in enumerate(weeks):
        for d_str, c in w:
            key = d_str[:7]
            m = months.setdefault(key, {"c": 0, "w": set()})
            m["c"] += c
            m["w"].add(wi)
    ground = 318
    top_month = max(m["c"] for m in months.values()) or 1
    towers, lights, labels = [], [], []
    for key, m in months.items():
        if len(m["w"]) < 2:
            continue
        a, b = min(m["w"]), max(m["w"])
        left, right = x0 + a * dx - dx / 2 + 3, x0 + b * dx + dx / 2 - 3
        mr = random.Random(key)
        share = math.sqrt(m["c"] / top_month)
        n = max(1, min(4, round((right - left) / 26)))
        cuts = sorted(mr.uniform(left + 12, right - 12) for _ in range(n - 1))
        edges = [left, *cuts, right]
        for i in range(n):
            tl, tr = edges[i] + 1.5, edges[i + 1] - 1.5
            h = 16 + 50 * share * mr.uniform(0.55, 1.0) + mr.uniform(0, 6)
            ty = ground - h
            towers.append(f'<rect x="{tl:.1f}" y="{ty:.1f}" width="{tr - tl:.1f}" height="{h:.1f}" fill="#0b1020"/>')
            towers.append(f'<rect x="{tl:.1f}" y="{ty:.1f}" width="{tr - tl:.1f}" height="1" fill="#2a3758" opacity=".8"/>')
            if mr.random() < 0.35 and h > 40:
                towers.append(f'<rect x="{(tl + tr) / 2 - .6:.1f}" y="{ty - 9:.1f}" width="1.2" height="9" fill="#2a3758"/>')
                towers.append(f'<circle cx="{(tl + tr) / 2:.1f}" cy="{ty - 9:.1f}" r="1.4" fill="#ff5a5a">'
                              f'<animate attributeName="opacity" values="1;.15;1" dur="{mr.uniform(1.6, 3):.1f}s" repeatCount="indefinite"/></circle>')
            cols = int((tr - tl - 4) // 6)
            rows = int((h - 8) // 8)
            for cy_ in range(rows):
                for cx_ in range(cols):
                    if mr.random() < 0.06 + 0.7 * share:
                        wx, wy = tl + 3 + cx_ * 6, ty + 6 + cy_ * 8
                        lights.append(f'<rect x="{wx:.1f}" y="{wy:.1f}" width="2.4" height="3.2" opacity="{mr.uniform(.45, .95):.2f}"/>')
        mname = date.fromisoformat(key + "-01").strftime("%b")
        labels.append(t(MONO, mname.upper(), (left + right) / 2, ground + 22, 10, "#3e4555", anchor="middle", ls=1))

    phase = moon_phase(today)
    stats = [(num(data["total"]), "CONTRIBUTIONS"), (str(active), "ACTIVE NIGHTS"),
             (str(best), "BRIGHTEST · " + date.fromisoformat(best_day).strftime("%b %-d").upper()), (None, "")]
    stat_svg, sx = [], 956
    for value, label in reversed(stats):
        if value is None:
            label = moon_label_for(phase)
            wv = MONO.width(label, 10, 1.2)
            shape, _ = moon(sx - wv / 2, 58, 11, phase)
            stat_svg.append(shape)
        else:
            wv = max(SANS_B.width(value, 26), MONO.width(label, 10, 1.2))
            stat_svg.append(t(SANS_B, value, sx, 68, 26, INK, anchor="end"))
        stat_svg.append(t(MONO, label, sx, 88, 10, FAINT, anchor="end", ls=1.2))
        sx -= wv + 30

    meteor = (
        '<g opacity="0">'
        + anim("opacity", [(3.0, 0), (3.15, 1), (3.8, 1), (4.0, 0)], 11)
        + "<g>" + anim("transform", [(3.0, "0 0"), (4.0, "260 95")], 11, tag="animateTransform", extra='type="translate"', ease="0.3 0 0.7 1")
        + '<line x1="160" y1="96" x2="230" y2="121" stroke="url(#meteor)" stroke-width="1.6" stroke-linecap="round"/></g></g>'
    )

    body = f"""
    <defs>
      <clipPath id="frame"><rect width="{W}" height="{H}" rx="20"/></clipPath>
      <linearGradient id="night" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#03050b"/><stop offset=".7" stop-color="#0a1226"/><stop offset="1" stop-color="#141c38"/></linearGradient>
      <radialGradient id="halo"><stop offset="0" stop-color="#cfe0ff" stop-opacity=".35"/><stop offset="1" stop-color="#cfe0ff" stop-opacity="0"/></radialGradient>
      <radialGradient id="moonglow"><stop offset="0" stop-color="#f3ead2" stop-opacity=".18"/><stop offset="1" stop-color="#f3ead2" stop-opacity="0"/></radialGradient>
      <radialGradient id="cityglow" cx=".5" cy="1" r=".7"><stop offset="0" stop-color="#ff9a5a" stop-opacity=".16"/><stop offset="1" stop-color="#ff9a5a" stop-opacity="0"/></radialGradient>
      <linearGradient id="meteor" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>
      <linearGradient id="groundline" x1="0" x2="1"><stop offset="0" stop-color="#3a4a78" stop-opacity="0"/>
        <stop offset=".5" stop-color="#5a6ea8" stop-opacity=".7"/><stop offset="1" stop-color="#3a4a78" stop-opacity="0"/></linearGradient>
    </defs>
    <g clip-path="url(#frame)">
      <rect width="{W}" height="{H}" fill="url(#night)"/>
      {starfield(rng, 90, 0, 0, W, 250, 0.08, "#9fb4ff")}
      <rect y="180" width="{W}" height="{ground - 180}" fill="url(#cityglow)"/>
      {t(SERIF_I, "a year of commits, as a night sky", 44, 66, 30, INK)}
      {t(MONO, "one star per day · brighter = busier", 44, 90, 11.5, FAINT)}
      {"".join(stat_svg)}
      <g fill="#cddcff">{"".join(dust)}</g>
      {"".join(halos)}{"".join(stars)}
      {meteor}
      {"".join(towers)}
      <g fill="#ffd27a">{"".join(lights)}</g>
      <rect x="0" y="{ground}" width="{W}" height="{H - ground}" fill="#05070d"/>
      <rect x="0" y="{ground}" width="{W}" height="1" fill="url(#groundline)"/>
      {"".join(labels)}
      {t(MONO, f"longest streak · {streak} days    ·    {num(data['followers'])} followers    ·    rebuilt {today.isoformat()}", W / 2, H - 14, 10, "#333a48", anchor="middle", ls=0.8)}
    </g>
    <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="#fff" stroke-opacity=".08"/>
    """
    title = f"{num(data['total'])} contributions in the last year, drawn as a night sky over a city"
    return svg(W, H, body, doc, title=title)


def main():
    data = fetch()
    today = datetime.now(TZ).date()
    ASSETS.mkdir(exist_ok=True)
    out = {
        "hero.svg": hero(data, today),
        "card-codeisland.svg": card_codeisland(data),
        "card-byob.svg": card_byob(data),
        "sky.svg": sky(data, today),
    }
    for name, content in out.items():
        (ASSETS / name).write_text(content)
        print(f"{name:22} {len(content) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
