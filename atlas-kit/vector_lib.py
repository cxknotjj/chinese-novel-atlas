"""Small vector component library for the atlas kit.

The same primitive definitions feed two outputs:
1. PIL rendering for the sample PNG maps;
2. standalone SVG files / an SVG overlay for web use.

Only the nine "variable" pieces live here: land route, sea route, compass,
cartouche frame, seal frame, and four marker icons. Terrain, water, buildings,
and vegetation remain hand-painted PNG assets.
"""

from __future__ import annotations

import html
import math
import os
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

DEFAULT_COLORS = {
    "ink": "#3B332A",
    "accent": "#A66A45",
    "seal": "#A93828",
    "paper": "#E8DCC5",
    "water": "#6E8E96",
    "route": "#8A7254",
    "muted": "#8D8070",
}

MARKER_NAMES = {
    "city": "城",
    "sect": "宗门",
    "secret": "秘境",
    "danger": "危险",
}

MARKER_ID_TO_TYPE = {
    "marker_city_01": "city",
    "marker_sect_01": "sect",
    "marker_secret_01": "secret",
    "marker_danger_01": "danger",
}


def rgba(color: str, alpha: float = 1.0):
    """Convert #RRGGBB (or a token) to a Pillow RGBA tuple."""
    color = DEFAULT_COLORS.get(color, color)
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    a = max(0, min(255, int(round(255 * float(alpha)))))
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def _spiral_points():
    points = []
    turns = 3.35
    samples = 52
    for i in range(samples + 1):
        t = i / samples
        radius = 3.5 + 24.0 * t
        angle = -math.pi / 2 + turns * math.tau * t
        points.append([50 + radius * math.cos(angle), 50 + radius * math.sin(angle)])
    return points


def _ring_ticks():
    ticks = []
    for i in range(24):
        angle = math.tau * i / 24 - math.pi / 2
        r0, r1 = 31.5, 39.0
        ticks.append(
            {
                "op": "line",
                "x1": 50 + r0 * math.cos(angle),
                "y1": 50 + r0 * math.sin(angle),
                "x2": 50 + r1 * math.cos(angle),
                "y2": 50 + r1 * math.sin(angle),
                "stroke": "ink",
                "width": 0.9,
                "alpha": 0.42,
            }
        )
    return ticks


# Marker primitives use a 0..100 square viewBox. Coordinates are deliberately
# simple: icon recognition at 40–60 px matters more than detail at 640 px.
MARKERS = {
    "city": [
        {"op": "circle", "cx": 50, "cy": 50, "r": 44, "stroke": "ink", "width": 1.8, "alpha": 0.38},
        {"op": "circle", "cx": 50, "cy": 50, "r": 40, "fill": "paper", "alpha": 0.22},
        {"op": "polyline", "points": [[27, 64], [27, 50], [32, 50], [32, 46], [38, 46], [38, 50],
                                      [44, 50], [44, 46], [50, 46], [50, 50], [56, 50], [56, 46],
                                      [62, 46], [62, 50], [68, 50], [68, 64], [27, 64]],
         "stroke": "ink", "width": 2.4, "alpha": 0.84},
        {"op": "line", "x1": 27, "y1": 57, "x2": 68, "y2": 57, "stroke": "ink", "width": 1.6, "alpha": 0.50},
        {"op": "polyline", "points": [[46, 64], [46, 58], [47.5, 55.5], [50, 54.5], [52.5, 55.5], [54, 58], [54, 64]],
         "stroke": "ink", "width": 2.0, "alpha": 0.88},
        {"op": "polygon", "points": [[47.4, 64], [47.4, 59], [49.0, 57.5], [50, 57.5], [51, 57.5], [52.6, 59], [52.6, 64]],
         "fill": "seal", "alpha": 0.45},
    ],
    "sect": [
        {"op": "circle", "cx": 50, "cy": 50, "r": 44, "stroke": "ink", "width": 1.8, "alpha": 0.38},
        {"op": "circle", "cx": 50, "cy": 50, "r": 40, "fill": "paper", "alpha": 0.22},
        {"op": "polyline", "points": [[29, 49], [35, 44], [42, 41.5], [50, 40.5], [58, 41.5],
                                      [65, 44], [71, 49]],
         "stroke": "ink", "width": 2.8, "alpha": 0.84},
        {"op": "polyline", "points": [[27, 51], [34, 46.5], [42, 44.5], [50, 44], [58, 44.5],
                                      [66, 46.5], [73, 51]],
         "stroke": "ink", "width": 1.8, "alpha": 0.68},
        {"op": "line", "x1": 27, "y1": 51, "x2": 24, "y2": 48, "stroke": "ink", "width": 1.8, "alpha": 0.68},
        {"op": "line", "x1": 73, "y1": 51, "x2": 76, "y2": 48, "stroke": "ink", "width": 1.8, "alpha": 0.68},
        {"op": "line", "x1": 40, "y1": 51, "x2": 40, "y2": 67, "stroke": "ink", "width": 2.0, "alpha": 0.76},
        {"op": "line", "x1": 60, "y1": 51, "x2": 60, "y2": 67, "stroke": "ink", "width": 2.0, "alpha": 0.76},
        {"op": "line", "x1": 36, "y1": 67, "x2": 64, "y2": 67, "stroke": "ink", "width": 2.2, "alpha": 0.60},
        {"op": "polyline", "points": [[46, 67], [46, 59], [47, 56], [50, 55], [53, 56], [54, 59], [54, 67]],
         "stroke": "ink", "width": 2.0, "alpha": 0.82},
        {"op": "polygon", "points": [[47, 67], [47, 60], [49, 58], [50, 58], [51, 58], [53, 60], [53, 67]],
         "fill": "accent", "alpha": 0.60},
    ],
    "secret": [
        {"op": "circle", "cx": 50, "cy": 50, "r": 44, "stroke": "ink", "width": 1.8, "alpha": 0.38},
        {"op": "circle", "cx": 50, "cy": 50, "r": 40, "fill": "paper", "alpha": 0.22},
        {"op": "polyline", "points": _spiral_points(), "stroke": "ink", "width": 2.2, "alpha": 0.78},
        {"op": "circle", "cx": 68, "cy": 30, "r": 2.2, "fill": "accent", "alpha": 0.55},
        {"op": "circle", "cx": 73, "cy": 40, "r": 1.8, "fill": "accent", "alpha": 0.42},
        {"op": "circle", "cx": 50, "cy": 50, "r": 2.4, "fill": "seal", "alpha": 0.72},
    ],
    "danger": [
        {"op": "circle", "cx": 50, "cy": 50, "r": 44, "stroke": "ink", "width": 1.8, "alpha": 0.34},
        {"op": "circle", "cx": 50, "cy": 50, "r": 40, "fill": "paper", "alpha": 0.22},
        {"op": "polyline", "points": [[50, 26], [74, 68], [26, 68], [50, 26]],
         "stroke": "seal", "width": 2.8, "alpha": 0.84},
        {"op": "line", "x1": 50, "y1": 43, "x2": 50, "y2": 56, "stroke": "seal", "width": 2.4, "alpha": 0.86},
        {"op": "circle", "cx": 50, "cy": 61, "r": 2.2, "fill": "seal", "alpha": 0.86},
    ],
}

COMPASS_SHAPES = [
    {"op": "circle", "cx": 50, "cy": 50, "r": 46, "stroke": "ink", "width": 1.8, "alpha": 0.36},
    {"op": "circle", "cx": 50, "cy": 50, "r": 40, "stroke": "ink", "width": 1.2, "alpha": 0.46},
    {"op": "circle", "cx": 50, "cy": 50, "r": 31, "stroke": "ink", "width": 1.0, "alpha": 0.34},
    *_ring_ticks(),
    {"op": "polygon", "points": [[50, 50], [46.3, 26], [50, 18], [53.7, 26]], "fill": "seal", "alpha": 0.55},
    {"op": "polygon", "points": [[50, 50], [46.3, 74], [50, 82], [53.7, 74]], "fill": "ink", "alpha": 0.42},
    {"op": "circle", "cx": 50, "cy": 50, "r": 2.6, "fill": "ink", "alpha": 0.72},
]


def smooth_points(points: Iterable[Iterable[float]], samples: int = 16):
    """Catmull-Rom smoothing for a polyline. Returns float (x, y) tuples."""
    pts = [tuple(float(v) for v in p) for p in points]
    if len(pts) < 3:
        return pts
    padded = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out


def _polyline_lengths(points):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return lengths


def _point_at(points, lengths, dist):
    if dist <= 0:
        return points[0]
    if dist >= lengths[-1]:
        return points[-1]
    for i in range(1, len(lengths)):
        if lengths[i] >= dist:
            a, b = points[i - 1], points[i]
            span = lengths[i] - lengths[i - 1]
            t = (dist - lengths[i - 1]) / span if span else 0
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    return points[-1]


def dashed_polyline(draw, points, fill, width, dash, gap, round_caps=True):
    lengths = _polyline_lengths(points)
    total = lengths[-1]
    if total <= 0:
        return
    dist = 0.0
    cap = max(1, int(round(width / 2)))
    while dist < total:
        end = min(dist + dash, total)
        a = _point_at(points, lengths, dist)
        b = _point_at(points, lengths, end)
        draw.line([a, b], fill=fill, width=max(1, int(round(width))))
        if round_caps:
            for x, y in (a, b):
                draw.ellipse(
                    [x - cap, y - cap, x + cap, y + cap],
                    fill=fill,
                )
        dist += dash + gap


def draw_shape(draw, shape, box, colors, font_path, opacity=1.0):
    """Draw one primitive into a rectangle box=(x, y, w, h)."""
    x0, y0, w, h = box
    sx, sy = w / 100.0, h / 100.0
    unit = min(sx, sy)

    def X(v):
        return x0 + v * sx

    def Y(v):
        return y0 + v * sy

    alpha = float(shape.get("alpha", 1.0)) * float(opacity)
    stroke = shape.get("stroke")
    fill = shape.get("fill")
    width = max(1, int(round(float(shape.get("width", 1.0)) * unit)))
    op = shape.get("op")

    if op == "circle":
        bbox = [X(shape["cx"] - shape["r"]), Y(shape["cy"] - shape["r"]),
                X(shape["cx"] + shape["r"]), Y(shape["cy"] + shape["r"])]
        draw.ellipse(
            bbox,
            fill=rgba(fill, alpha) if fill else None,
            outline=rgba(stroke, alpha) if stroke else None,
            width=width if stroke else 1,
        )
    elif op == "line":
        draw.line(
            [(X(shape["x1"]), Y(shape["y1"])), (X(shape["x2"]), Y(shape["y2"]))],
            fill=rgba(stroke, alpha),
            width=width,
        )
    elif op in ("polyline", "polygon"):
        pts = [(X(p[0]), Y(p[1])) for p in shape["points"]]
        if op == "polygon":
            if fill:
                draw.polygon(pts, fill=rgba(fill, alpha))
            if stroke:
                draw.line(pts + [pts[0]], fill=rgba(stroke, alpha), width=width, joint="curve")
        else:
            draw.line(pts, fill=rgba(stroke, alpha), width=width, joint="curve")
    elif op == "rect":
        bbox = [X(shape["x"]), Y(shape["y"]), X(shape["x"] + shape["w"]), Y(shape["y"] + shape["h"])]
        draw.rectangle(
            bbox,
            fill=rgba(fill, alpha) if fill else None,
            outline=rgba(stroke, alpha) if stroke else None,
            width=width if stroke else 1,
        )
    elif op == "text":
        size_px = max(1, int(round(float(shape.get("size", 8)) * unit)))
        font = ImageFont.truetype(font_path, size_px)
        draw.text(
            (X(shape["x"]), Y(shape["y"])),
            shape["text"],
            font=font,
            fill=rgba(shape.get("fill", "ink"), alpha),
            anchor=shape.get("anchor", "mm"),
        )


def draw_marker(draw, marker_type, cx, cy, size_px, colors=None, font_path=None, opacity=1.0):
    colors = colors or DEFAULT_COLORS
    box = (cx - size_px / 2, cy - size_px / 2, size_px, size_px)
    for shape in MARKERS.get(marker_type, MARKERS["city"]):
        draw_shape(draw, shape, box, colors, font_path or "", opacity)


def draw_compass(draw, cx, cy, size_px, colors=None, font_path=None, opacity=0.72):
    colors = colors or DEFAULT_COLORS
    box = (cx - size_px / 2, cy - size_px / 2, size_px, size_px)
    for shape in COMPASS_SHAPES:
        draw_shape(draw, shape, box, colors, font_path or "", opacity)


def cartouche_metrics(width, char_count):
    n = max(1, int(char_count))
    font_size = max(14.0, width * 0.26)
    pad = max(6.0, width * 0.10)
    height = n * font_size * 1.19 + 2 * pad + font_size * 0.18
    return font_size, height, pad


def draw_cartouche(draw, cx, cy, width, text, colors=None, font_path=None, opacity=1.0):
    colors = colors or DEFAULT_COLORS
    font_size, height, pad = cartouche_metrics(width, len(text))
    left, top = cx - width / 2, cy - height / 2
    right, bottom = cx + width / 2, cy + height / 2
    ink = rgba(colors["ink"], opacity)
    paper = rgba(colors["paper"], 0.20 * opacity)

    draw.rounded_rectangle([left, top, right, bottom], radius=max(2, width * 0.025),
                           fill=paper, outline=ink, width=max(2, int(width * 0.045)))
    inset = max(3, int(width * 0.06))
    draw.rounded_rectangle([left + inset, top + inset, right - inset, bottom - inset],
                           radius=max(1, width * 0.018), outline=rgba(colors["ink"], 0.55 * opacity),
                           width=max(1, int(width * 0.022)))

    # Side rails and four small corner hooks give it a "book label" feel.
    rail = max(2, int(width * 0.04))
    draw.line([(left + inset * 2, top + inset * 3), (left + inset * 2, bottom - inset * 3)],
              fill=rgba(colors["muted"], 0.34 * opacity), width=rail)
    draw.line([(right - inset * 2, top + inset * 3), (right - inset * 2, bottom - inset * 3)],
              fill=rgba(colors["muted"], 0.34 * opacity), width=rail)
    hook = max(4, int(width * 0.09))
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        hx = right - inset if sx > 0 else left + inset
        hy = bottom - inset if sy > 0 else top + inset
        draw.line([(hx - sx * hook, hy), (hx, hy), (hx, hy - sy * hook)],
                  fill=rgba(colors["accent"], 0.55 * opacity), width=max(1, rail))

    font = ImageFont.truetype(font_path or "", max(10, int(font_size)))
    start_y = top + pad + font_size * 0.58
    for i, ch in enumerate(text):
        draw.text((cx, start_y + i * font_size * 1.19), ch, font=font,
                  fill=rgba(colors["ink"], 0.94 * opacity), anchor="mm")


def draw_seal(draw, cx, cy, size_px, text, colors=None, font_path=None, opacity=1.0):
    colors = colors or DEFAULT_COLORS
    half = size_px / 2
    left, top, right, bottom = cx - half, cy - half, cx + half, cy + half
    seal = rgba(colors["seal"], opacity)
    draw.rounded_rectangle([left, top, right, bottom], radius=max(2, size_px * 0.05),
                           outline=seal, width=max(3, int(size_px * 0.10)))
    inset = max(4, int(size_px * 0.13))
    draw.rounded_rectangle([left + inset, top + inset, right - inset, bottom - inset],
                           radius=max(1, size_px * 0.025),
                           outline=rgba(colors["seal"], 0.62 * opacity),
                           width=max(1, int(size_px * 0.035)))
    if not text:
        return
    n = len(text)
    font_size = min(size_px * 0.54, size_px * 1.15 / max(1, n))
    font = ImageFont.truetype(font_path or "", max(10, int(font_size)))
    if n <= 2:
        step = font_size * 1.10
        start = cy - step * (n - 1) / 2
        for i, ch in enumerate(text):
            draw.text((cx, start + i * step), ch, font=font, fill=seal, anchor="mm")
    else:
        # Compact two-column layout, still readable at 40–60 px.
        step = size_px * 0.25
        start = cy - step / 2
        for i, ch in enumerate(text):
            col = i % 2
            row = i // 2
            draw.text((cx - step / 2 + col * step, start + row * step * 1.05), ch,
                      font=font, fill=seal, anchor="mm")


def draw_route(draw, points, width_px, colors=None, style="land", opacity=1.0):
    colors = colors or DEFAULT_COLORS
    if len(points) < 2:
        return
    pts = smooth_points(points, samples=18)
    route_color = colors["water"] if style == "sea" else colors["route"]
    base_width = max(2, int(width_px * 1.55))
    dash_width = max(2, int(width_px))

    # Soft wash under the dashes; on sea this reads as a faint wake.
    draw.line(pts, fill=rgba(route_color, 0.13 * opacity), width=base_width, joint="curve")

    if style == "sea":
        dashed_polyline(draw, pts, rgba(route_color, 0.88 * opacity), dash_width,
                        dash=max(8, width_px * 2.8), gap=max(4, width_px * 1.5))
    else:
        dashed_polyline(draw, pts, rgba(route_color, 0.85 * opacity), dash_width,
                        dash=max(6, width_px * 2.3), gap=max(4, width_px * 1.35))

    # Endpoint dots make routes read as connections rather than stray strokes.
    for p in (pts[0], pts[-1]):
        r = max(2, int(width_px * 0.92))
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r],
                     fill=rgba(route_color, 0.55 * opacity))


# ---------------------------------------------------------------------------
# SVG output
# ---------------------------------------------------------------------------

def _svg_color(token, colors):
    return colors.get(token, token)


def _fmt(value):
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def svg_shape(shape, colors):
    op = shape.get("op")
    alpha = float(shape.get("alpha", 1.0))
    stroke = _svg_color(shape["stroke"], colors) if shape.get("stroke") else None
    fill = _svg_color(shape["fill"], colors) if shape.get("fill") else None
    common = f' opacity="{_fmt(alpha)}"'
    if op == "circle":
        s = f' stroke="{stroke}" stroke-width="{_fmt(shape.get("width", 1.0))}"' if stroke else ""
        f = f' fill="{fill}"' if fill else ' fill="none"'
        return f'<circle cx="{_fmt(shape["cx"])}" cy="{_fmt(shape["cy"])}" r="{_fmt(shape["r"])}"{f}{s}{common}/>'
    if op == "line":
        return (f'<line x1="{_fmt(shape["x1"])}" y1="{_fmt(shape["y1"])}" '
                f'x2="{_fmt(shape["x2"])}" y2="{_fmt(shape["y2"])}" '
                f'stroke="{stroke}" stroke-width="{_fmt(shape.get("width", 1.0))}"{common}/>')
    if op in ("polyline", "polygon"):
        pts = " ".join(f"{_fmt(p[0])},{_fmt(p[1])}" for p in shape["points"])
        tag = "polyline" if op == "polyline" else "polygon"
        s = f' stroke="{stroke}" stroke-width="{_fmt(shape.get("width", 1.0))}"' if stroke else ""
        f = f' fill="{fill}"' if fill else ' fill="none"'
        return f'<{tag} points="{pts}"{f}{s}{common}/>'
    if op == "rect":
        s = f' stroke="{stroke}" stroke-width="{_fmt(shape.get("width", 1.0))}"' if stroke else ""
        f = f' fill="{fill}"' if fill else ' fill="none"'
        return (f'<rect x="{_fmt(shape["x"])}" y="{_fmt(shape["y"])}" '
                f'width="{_fmt(shape["w"])}" height="{_fmt(shape["h"])}"{f}{s}{common}/>')
    if op == "text":
        text = html.escape(str(shape["text"]))
        return (f'<text x="{_fmt(shape["x"])}" y="{_fmt(shape["y"])}" '
                f'font-size="{_fmt(shape.get("size", 8))}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="{_svg_color(shape.get("fill", "ink"), colors)}"'
                f' font-family="KaiTi, STKaiti, serif"{common}>{text}</text>')
    return ""


def marker_svg(marker_type, colors=None, width=256):
    colors = colors or DEFAULT_COLORS
    body = "\n  ".join(svg_shape(s, colors) for s in MARKERS.get(marker_type, MARKERS["city"]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{width}" '
            f'viewBox="0 0 100 100" role="img" aria-label="atlas marker {marker_type}">\n  {body}\n</svg>\n')


def compass_svg(colors=None, width=256):
    colors = colors or DEFAULT_COLORS
    body = "\n  ".join(svg_shape(s, colors) for s in COMPASS_SHAPES)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{width}" '
            f'viewBox="0 0 100 100" role="img" aria-label="atlas compass">\n  {body}\n</svg>\n')


def cartouche_frame_svg(colors=None, width=180):
    colors = colors or DEFAULT_COLORS
    ink = colors["ink"]
    accent = colors["accent"]
    muted = colors["muted"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{int(width * 2.05)}" viewBox="0 0 100 205" role="img" aria-label="atlas cartouche frame">
  <rect x="5" y="5" width="90" height="195" rx="2.5" fill="{colors['paper']}" fill-opacity="0.20" stroke="{ink}" stroke-width="4"/>
  <rect x="11" y="11" width="78" height="183" rx="1.8" fill="none" stroke="{ink}" stroke-opacity="0.55" stroke-width="2"/>
  <line x1="17" y1="23" x2="17" y2="182" stroke="{muted}" stroke-opacity="0.34" stroke-width="3"/>
  <line x1="83" y1="23" x2="83" y2="182" stroke="{muted}" stroke-opacity="0.34" stroke-width="3"/>
  <path d="M20 16 H14 V22 M80 16 H86 V22 M20 189 H14 V183 M80 189 H86 V183" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="2"/>
</svg>
'''


def seal_frame_svg(colors=None, width=180):
    colors = colors or DEFAULT_COLORS
    seal = colors["seal"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{width}" viewBox="0 0 100 100" role="img" aria-label="atlas seal frame">
  <rect x="6" y="6" width="88" height="88" rx="4" fill="none" stroke="{seal}" stroke-width="9"/>
  <rect x="16" y="16" width="68" height="68" rx="2" fill="none" stroke="{seal}" stroke-opacity="0.62" stroke-width="3"/>
</svg>
'''


def route_style_svg(style="land", colors=None, width=560):
    colors = colors or DEFAULT_COLORS
    color = colors["water"] if style == "sea" else colors["route"]
    dash = "14 9" if style == "sea" else "12 8"
    if style == "sea":
        path = "M 24 78 C 80 24 120 118 176 66 C 220 26 270 78 318 48 C 360 24 410 36 446 66"
        wake = "M 24 86 C 80 32 120 126 176 74 C 220 34 270 86 318 56 C 360 32 410 44 446 74"
        extra = (f'<path d="{wake}" fill="none" stroke="{color}" stroke-opacity="0.18" '
                 f'stroke-width="5" stroke-linecap="round"/>')
    else:
        path = "M 24 84 C 74 20 126 108 182 56 C 226 18 276 72 320 46 C 366 20 414 32 446 62"
        extra = ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{int(width * 0.32)}" viewBox="0 0 470 150" role="img" aria-label="atlas route style {style}">
  {extra}
  <path d="{path}" fill="none" stroke="{color}" stroke-opacity="0.85" stroke-width="4" stroke-linecap="round" stroke-dasharray="{dash}"/>
  <circle cx="24" cy="84" r="4" fill="{color}" fill-opacity="0.55"/>
  <circle cx="446" cy="62" r="4" fill="{color}" fill-opacity="0.55"/>
</svg>
'''


def _path_d(points):
    return "M " + " L ".join(f"{_fmt(x)} {_fmt(y)}" for x, y in points)


def overlay_svg(world, size=(1600, 900), colors=None):
    """Transparent SVG overlay for a world, using only code/SVG components."""
    colors = colors or DEFAULT_COLORS
    W, H = size
    parts = []
    layers = world.get("layers", {})

    for item in layers.get("routes", []):
        pts = [(p[0] * W, p[1] * H) for p in item["points"]]
        pts = smooth_points(pts, samples=18)
        style = item.get("style", "land")
        color = colors["water"] if style == "sea" else colors["route"]
        dash = "18 10" if style == "sea" else "13 9"
        width = max(2, int(W * 0.0019))
        parts.append(f'<path d="{_path_d(pts)}" fill="none" stroke="{color}" stroke-opacity="0.14" stroke-width="{width * 2.2}" stroke-linecap="round"/>')
        parts.append(f'<path d="{_path_d(pts)}" fill="none" stroke="{color}" stroke-opacity="0.86" stroke-width="{width}" stroke-linecap="round" stroke-dasharray="{dash}"/>')

    for item in layers.get("markers", []):
        marker_type = item.get("type") or MARKER_ID_TO_TYPE.get(item.get("asset"), "city")
        size_px = item.get("w", 0.03) * W
        cx, cy = item.get("x", 0.5) * W, item.get("y", 0.5) * H
        parts.append(f'<g transform="translate({_fmt(cx - size_px / 2)} {_fmt(cy - size_px / 2)}) scale({_fmt(size_px / 100)})" opacity="{_fmt(item.get("opacity", 1.0))}">')
        for shape in MARKERS.get(marker_type, MARKERS["city"]):
            parts.append("  " + svg_shape(shape, colors))
        parts.append("</g>")
        if item.get("label"):
            label_size = H * 0.022
            parts.append(f'<text x="{_fmt(cx)}" y="{_fmt(cy + H * 0.038)}" font-size="{_fmt(label_size)}" text-anchor="middle" dominant-baseline="middle" fill="{colors["ink"]}" font-family="KaiTi, STKaiti, serif">{html.escape(item["label"])}</text>')

    for item in layers.get("labels", []):
        fill = colors["accent"] if item.get("kind") == "accent" else colors["ink"]
        size_px = item.get("size", 0.04) * H
        parts.append(f'<text x="{_fmt(item["x"] * W)}" y="{_fmt(item["y"] * H)}" font-size="{_fmt(size_px)}" text-anchor="middle" dominant-baseline="middle" fill="{fill}" font-family="KaiTi, STKaiti, serif" stroke="{colors["paper"]}" stroke-width="{_fmt(max(2, size_px * 0.10))}" paint-order="stroke fill">{html.escape(item["text"])}</text>')

    for item in layers.get("ui", []):
        ui_type = item.get("type")
        cx, cy = item.get("x", 0.5) * W, item.get("y", 0.5) * H
        width = item.get("w", 0.08) * W
        if ui_type == "compass":
            parts.append(f'<g transform="translate({_fmt(cx - width / 2)} {_fmt(cy - width / 2)}) scale({_fmt(width / 100)})" opacity="0.72">')
            for shape in COMPASS_SHAPES:
                parts.append("  " + svg_shape(shape, colors))
            parts.append("</g>")
        elif ui_type == "cartouche":
            text = item.get("text", "")
            font_size, height, pad = cartouche_metrics(width, len(text))
            left, top = cx - width / 2, cy - height / 2
            parts.append(f'<g opacity="{_fmt(item.get("opacity", 1.0))}">')
            parts.append(f'  <rect x="{_fmt(left)}" y="{_fmt(top)}" width="{_fmt(width)}" height="{_fmt(height)}" rx="{_fmt(width * 0.025)}" fill="{colors["paper"]}" fill-opacity="0.20" stroke="{colors["ink"]}" stroke-width="{_fmt(max(2, width * 0.045))}"/>')
            parts.append(f'  <rect x="{_fmt(left + width * 0.06)}" y="{_fmt(top + width * 0.06)}" width="{_fmt(width * 0.88)}" height="{_fmt(height - width * 0.12)}" rx="{_fmt(width * 0.018)}" fill="none" stroke="{colors["ink"]}" stroke-opacity="0.55" stroke-width="{_fmt(max(1, width * 0.022))}"/>')
            for i, ch in enumerate(text):
                ty = top + pad + font_size * 0.58 + i * font_size * 1.19
                parts.append(f'  <text x="{_fmt(cx)}" y="{_fmt(ty)}" font-size="{_fmt(font_size)}" text-anchor="middle" dominant-baseline="middle" fill="{colors["ink"]}" font-family="KaiTi, STKaiti, serif">{html.escape(ch)}</text>')
            parts.append("</g>")
        elif ui_type == "seal":
            seal_size = width
            half = seal_size / 2
            parts.append(f'<g opacity="{_fmt(item.get("opacity", 1.0))}">')
            parts.append(f'  <rect x="{_fmt(cx - half)}" y="{_fmt(cy - half)}" width="{_fmt(seal_size)}" height="{_fmt(seal_size)}" rx="{_fmt(seal_size * 0.05)}" fill="none" stroke="{colors["seal"]}" stroke-width="{_fmt(max(3, seal_size * 0.10))}"/>')
            parts.append(f'  <rect x="{_fmt(cx - half + seal_size * 0.13)}" y="{_fmt(cy - half + seal_size * 0.13)}" width="{_fmt(seal_size * 0.74)}" height="{_fmt(seal_size * 0.74)}" rx="{_fmt(seal_size * 0.025)}" fill="none" stroke="{colors["seal"]}" stroke-opacity="0.62" stroke-width="{_fmt(max(1, seal_size * 0.035))}"/>')
            text = item.get("text", "")
            if text:
                n = len(text)
                fs = min(seal_size * 0.54, seal_size * 1.15 / max(1, n))
                if n <= 2:
                    step = fs * 1.10
                    start = cy - step * (n - 1) / 2
                    for i, ch in enumerate(text):
                        parts.append(f'  <text x="{_fmt(cx)}" y="{_fmt(start + i * step)}" font-size="{_fmt(fs)}" text-anchor="middle" dominant-baseline="middle" fill="{colors["seal"]}" font-family="KaiTi, STKaiti, serif">{html.escape(ch)}</text>')
                else:
                    step = seal_size * 0.25
                    start = cy - step / 2
                    for i, ch in enumerate(text):
                        col, row = i % 2, i // 2
                        parts.append(f'  <text x="{_fmt(cx - step / 2 + col * step)}" y="{_fmt(start + row * step * 1.05)}" font-size="{_fmt(fs)}" text-anchor="middle" dominant-baseline="middle" fill="{colors["seal"]}" font-family="KaiTi, STKaiti, serif">{html.escape(ch)}</text>')
            parts.append("</g>")

    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            '<!-- Generated by atlas-kit/vector_lib.py; transparent overlay. -->\n  '
            + "\n  ".join(parts) + "\n</svg>\n").format(w=W, h=H)


def build_static_vectors(out_dir, colors=None):
    """Write the nine vector assets plus a small style sample sheet."""
    colors = colors or DEFAULT_COLORS
    os.makedirs(os.path.join(out_dir, "markers"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "ui"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "routes"), exist_ok=True)

    for marker_type in ("city", "sect", "secret", "danger"):
        with open(os.path.join(out_dir, "markers", f"marker_{marker_type}.svg"), "w", encoding="utf-8") as f:
            f.write(marker_svg(marker_type, colors))
    with open(os.path.join(out_dir, "ui", "compass.svg"), "w", encoding="utf-8") as f:
        f.write(compass_svg(colors))
    with open(os.path.join(out_dir, "ui", "cartouche_frame.svg"), "w", encoding="utf-8") as f:
        f.write(cartouche_frame_svg(colors))
    with open(os.path.join(out_dir, "ui", "seal_frame.svg"), "w", encoding="utf-8") as f:
        f.write(seal_frame_svg(colors))
    with open(os.path.join(out_dir, "routes", "route_land.svg"), "w", encoding="utf-8") as f:
        f.write(route_style_svg("land", colors))
    with open(os.path.join(out_dir, "routes", "route_sea.svg"), "w", encoding="utf-8") as f:
        f.write(route_style_svg("sea", colors))
