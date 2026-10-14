"""Tiny SVG toolkit: text rendered as glyph paths (so every viewer sees the same
type) plus helpers for SMIL timelines that all share one loop."""

from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen

FONTS = Path(__file__).parent / "fonts"


class Font:
    def __init__(self, file, key, wght=None):
        face = hb.Face(hb.Blob.from_file_path(str(FONTS / file)))
        self.font = hb.Font(face)
        if wght:
            self.font.set_variations({"wght": wght})
        self.upem = face.upem
        self.key = key
        self._paths = {}

    def shape(self, s):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        return list(zip(buf.glyph_infos, buf.glyph_positions))

    def path(self, gid):
        if gid not in self._paths:
            pen = SVGPathPen(None, ntos=lambda v: str(round(v)))
            self.font.draw_glyph_with_pen(gid, pen)
            self._paths[gid] = pen.getCommands()
        return self._paths[gid]

    def width(self, s, size, ls=0):
        adv = sum(p.x_advance for _, p in self.shape(s))
        return adv * size / self.upem + ls * len(s)


SERIF_I = Font("InstrumentSerif-Italic.ttf", "si")
SERIF = Font("InstrumentSerif-Regular.ttf", "sr")
SANS = Font("Geist-VF.ttf", "s4", 400)
SANS_M = Font("Geist-VF.ttf", "s5", 500)
SANS_B = Font("Geist-VF.ttf", "s6", 620)
MONO = Font("GeistMono-VF.ttf", "m4", 400)
MONO_M = Font("GeistMono-VF.ttf", "m5", 520)


class Doc:
    """Collects glyphs used by one SVG so <defs> only carries what's drawn."""

    def __init__(self):
        self.used = {}

    def text(self, font, s, x, y, size, fill="#fff", anchor="start", ls=0, attrs=""):
        k = size / font.upem
        w = font.width(s, size, ls)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        uses, pen_x = [], 0.0
        ls_units = ls / k
        for info, pos in font.shape(s):
            d = font.path(info.codepoint)
            if d:
                gid = f"{font.key}{info.codepoint}"
                self.used[gid] = d
                uses.append(f'<use href="#{gid}" x="{round(pen_x + pos.x_offset)}"/>')
            pen_x += pos.x_advance + ls_units
        return (
            f'<g transform="translate({x:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})" '
            f'fill="{fill}" {attrs}>{"".join(uses)}</g>'
        )

    def defs(self):
        return "".join(f'<path id="{g}" d="{d}"/>' for g, d in self.used.items())


def svg(w, h, body, doc=None, style="", title=""):
    defs = doc.defs() if doc else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{title}"><title>{title}</title>'
        f"<style>{style}</style><defs>{defs}</defs>{body}</svg>\n"
    )


EASE = "0.32 0.72 0 1"


def anim(attr, frames, loop, ease=EASE, tag="animate", extra=""):
    """frames: [(seconds, value), ...] on a shared loop of `loop` seconds."""
    if frames[0][0] > 0:
        frames = [(0, frames[0][1])] + frames
    if frames[-1][0] < loop:
        frames = frames + [(loop, frames[-1][1])]
    kt = ";".join(f"{t / loop:.4f}" for t, _ in frames)
    vals = ";".join(str(v) for _, v in frames)
    splines = ";".join([ease] * (len(frames) - 1))
    return (
        f'<{tag} attributeName="{attr}" dur="{loop}s" repeatCount="indefinite" '
        f'keyTimes="{kt}" values="{vals}" calcMode="spline" keySplines="{splines}" {extra}/>'
    )


def window(t_in, t_out, loop, d=0.3, lo=0, hi=1):
    """Opacity frames: hidden, fade in at t_in, hold, fade out at t_out."""
    return anim("opacity", [(t_in, lo), (t_in + d, hi), (t_out, hi), (t_out + d, lo)], loop)


def r(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")
