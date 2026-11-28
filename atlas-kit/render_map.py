from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import json, os, math, argparse

import vector_lib

KIT = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simkai.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if os.path.exists(p)), FONT_CANDIDATES[0])
FONT_UI = next((p for p in FONT_CANDIDATES if os.path.exists(p)), FONT_CANDIDATES[0])


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifest():
    m = load_json(os.path.join(KIT, "manifest.json"))
    return m, {a["id"]: a for a in m["assets"]}


def hex_rgba(value, alpha=255):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def shade_color(rgb, factor):
    return tuple(max(0, min(255, int(round(c * factor)))) for c in rgb)


def dashed_line(draw, points, fill, width=2, dash=10, gap=8):
    """Legacy helper retained for compatibility; new routes use vector_lib."""
    for p0, p1 in zip(points, points[1:]):
        x0, y0 = p0
        x1, y1 = p1
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist <= 0:
            continue
        n = max(1, int(dist / (dash + gap)) + 1)
        for i in range(n):
            s = i * (dash + gap)
            e = min(s + dash, dist)
            if s >= dist:
                break
            t0, t1 = s / dist, e / dist
            draw.line(
                [(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0),
                 (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)],
                fill=fill, width=width,
            )


def draw_water_body(base, item, theme, size):
    """Soft watercolor sea/lake from a polygon; no fixed sea stamp needed."""
    W, H = size
    pts = [(p[0] * W, p[1] * H) for p in item["points"]]
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    feather = float(item.get("feather", 0.035))
    mask = mask.filter(ImageFilter.GaussianBlur(max(2, int(min(W, H) * feather))))

    fill = hex_rgba(item.get("fill", theme.get("water", "#6E8E96")))
    opacity = float(item.get("opacity", 0.52))
    layer = Image.new("RGBA", (W, H), fill[:3] + (0,))
    layer.putalpha(mask.point(lambda v: int(v * opacity)))
    base.alpha_composite(layer)

    # A darker, slightly blurred coastal band gives the wash an edge without
    # turning it into a hard vector shape.
    min_side = min(W, H)
    edge_size = max(3, int(min_side * 0.010))
    if edge_size % 2 == 0:
        edge_size += 1
    inner = mask.filter(ImageFilter.MinFilter(edge_size))
    edge = ImageChops.subtract(mask, inner).filter(ImageFilter.GaussianBlur(max(2, int(min_side * 0.010))))
    edge_layer = Image.new("RGBA", (W, H), shade_color(fill[:3], 0.82) + (0,))
    edge_layer.putalpha(edge.point(lambda v: int(v * 0.20)))
    base.alpha_composite(edge_layer)

    # Subtle top-to-bottom light shift, masked by the coast.
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(34 * (1 - y / max(1, H - 1))))
    grad = grad.resize((W, H), Image.Resampling.BILINEAR)
    light_layer = Image.new("RGBA", (W, H), shade_color(fill[:3], 1.16) + (0,))
    light_layer.putalpha(ImageChops.multiply(grad, mask))
    base.alpha_composite(light_layer)

    # Low-frequency paper-like mottling; still code-generated, no PNG texture.
    noise = Image.effect_noise((max(1, W // 12), max(1, H // 12)), 38)
    noise = noise.resize((W, H), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(max(4, int(min_side * 0.014))))
    mottle = noise.point(lambda v: max(0, abs(int(v) - 128)) // 3)
    mottle_layer = Image.new("RGBA", (W, H), shade_color(fill[:3], 1.10) + (0,))
    mottle_layer.putalpha(ImageChops.multiply(mottle, mask).point(lambda v: int(v * 0.45)))
    base.alpha_composite(mottle_layer)

    # Optional hand-painted water texture, still masked by the code-defined coast.
    texture = item.get("texture")
    if texture:
        path = os.path.join(KIT, texture)
        if os.path.exists(path):
            tex = Image.open(path).convert("RGBA")
            # Cover-fit rather than stretch.
            scale = max(W / tex.width, H / tex.height)
            tex = tex.resize((int(tex.width * scale) + 1, int(tex.height * scale) + 1), Image.Resampling.LANCZOS)
            left = (tex.width - W) // 2
            top = (tex.height - H) // 2
            tex = tex.crop((left, top, left + W, top + H))
            tex_alpha = ImageChops.multiply(tex.getchannel("A"), mask)
            tex.putalpha(tex_alpha.point(lambda v: int(v * float(item.get("texture_opacity", 0.42)))))
            base.alpha_composite(tex)

    if item.get("waves", True):
        wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wave)
        wave_color = hex_rgba(item.get("wave_color", theme.get("ink", "#3B332A")), 38)
        top = min(p[1] for p in pts)
        bottom = max(p[1] for p in pts)
        left = min(p[0] for p in pts)
        right = max(p[0] for p in pts)
        count = int(item.get("wave_count", 7))
        for i in range(count):
            y = top + (bottom - top) * (i + 1) / (count + 1)
            amp = (bottom - top) * 0.008
            wave_pts = []
            for k in range(61):
                x = left + (right - left) * k / 60
                yy = y + amp * math.sin(k * 0.55 + i * 1.7)
                wave_pts.append((x, yy))
            wd.line(wave_pts, fill=wave_color, width=max(1, int(W * 0.0011)))
        wave.putalpha(ImageChops.multiply(wave.getchannel("A"), mask))
        base.alpha_composite(wave)


def make_paper(world, size):
    W, H = size
    theme = world.get("theme", {})
    paper_image = theme.get("paper_image")
    if paper_image:
        path = os.path.join(KIT, paper_image)
        if os.path.exists(path):
            paper = Image.open(path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
        else:
            paper = Image.new("RGBA", (W, H), hex_rgba(theme.get("paper", "#E8DCC5")))
    else:
        paper = Image.new("RGBA", (W, H), hex_rgba(theme.get("paper", "#E8DCC5")))

    tint = theme.get("paper_tint")
    if tint:
        overlay = Image.new("RGBA", (W, H), hex_rgba(tint, int(255 * float(theme.get("paper_tint_alpha", 0.04)))))
        paper = Image.alpha_composite(paper, overlay)
    return paper


def png_file(asset):
    """Return the PNG path for a raster asset, or its legacy hand-painted stamp."""
    if asset.get("media") == "vector":
        return asset.get("legacy_png")
    return asset.get("file")


def paste_asset(base, asset, x, y, w, opacity=1.0, rotate=0):
    W, H = base.size
    path = png_file(asset)
    if not path:
        return
    path = os.path.join(KIT, path)
    if not os.path.exists(path):
        return
    im = Image.open(path).convert("RGBA")
    if rotate:
        im = im.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
        pivot = (0.5, 0.5)
    else:
        pivot = asset.get("pivot", [0.5, 0.5])
    target_w = max(1, int(w * W))
    target_h = max(1, int(im.height * target_w / im.width))
    im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if opacity < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * opacity))
        im.putalpha(a)
    px = int(pivot[0] * im.width)
    py = int(pivot[1] * im.height)
    base.paste(im, (int(x * W) - px, int(y * H) - py), im)


def draw_label(draw, text, x, y, size_px, fill, paper, font_path=FONT_PATH):
    font = ImageFont.truetype(font_path, max(8, int(size_px)))
    stroke = max(1, int(size_px * 0.10))
    draw.text(
        (int(x), int(y)), text, font=font, fill=fill, anchor="mm",
        stroke_width=stroke, stroke_fill=paper,
    )


def theme_colors(theme):
    colors = dict(vector_lib.DEFAULT_COLORS)
    colors.update({
        "ink": theme.get("ink", colors["ink"]),
        "accent": theme.get("accent", colors["accent"]),
        "seal": theme.get("seal", colors["seal"]),
        "paper": theme.get("paper", colors["paper"]),
        "water": theme.get("water", colors["water"]),
        "route": theme.get("route", colors["route"]),
    })
    return colors


def marker_type_of(item):
    return item.get("type") or vector_lib.MARKER_ID_TO_TYPE.get(item.get("asset"), "city")


def draw_vector_layer(world, size, theme, supersample=2):
    """Draw routes/markers/UI/labels on a supersampled transparent layer."""
    W, H = size
    S = max(1, int(supersample))
    W2, H2 = W * S, H * S
    layer = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colors = theme_colors(theme)
    paper_rgba = vector_lib.rgba(colors["paper"], 1.0)
    layers = world.get("layers", {})

    for item in layers.get("routes", []):
        pts = [(p[0] * W2, p[1] * H2) for p in item["points"]]
        vector_lib.draw_route(
            draw, pts,
            width_px=max(2, W2 * 0.00205),
            colors=colors,
            style=item.get("style", "land"),
            opacity=float(item.get("opacity", 1.0)),
        )

    for item in layers.get("markers", []):
        if item.get("style") == "png" and item.get("asset"):
            continue  # handled by paste_asset pass
        marker_type = marker_type_of(item)
        mx = item.get("marker_x", item["x"]) * W2
        my = item.get("marker_y", item["y"] + 0.015) * H2
        vector_lib.draw_marker(
            draw, marker_type,
            mx, my,
            item.get("w", 0.03) * W2,
            colors=colors, font_path=FONT_PATH,
            opacity=float(item.get("opacity", 1.0)),
        )
        if item.get("label"):
            draw_label(draw, item["label"], mx,
                       my + H2 * 0.041, H2 * 0.022,
                       vector_lib.rgba(colors["ink"], 0.92), paper_rgba, FONT_PATH)

    for item in layers.get("labels", []):
        size_px = item.get("size", 0.04) * H2
        fill = vector_lib.rgba(colors["accent"] if item.get("kind") == "accent" else colors["ink"], 1.0)
        draw_label(draw, item["text"], item["x"] * W2, item["y"] * H2,
                   size_px, fill, paper_rgba, FONT_PATH)

    for item in layers.get("ui", []):
        if item.get("style") == "png" and item.get("asset"):
            continue
        ui_type = item.get("type")
        cx, cy = item["x"] * W2, item["y"] * H2
        width = item.get("w", 0.08) * W2
        opacity = float(item.get("opacity", 1.0))
        if ui_type == "cartouche":
            vector_lib.draw_cartouche(draw, cx, cy, width, item.get("text", ""),
                                      colors=colors, font_path=FONT_PATH, opacity=opacity)
        elif ui_type == "seal":
            vector_lib.draw_seal(draw, cx, cy, width, item.get("text", ""),
                                 colors=colors, font_path=FONT_PATH, opacity=opacity)
        elif ui_type == "compass":
            vector_lib.draw_compass(draw, cx, cy, width, colors=colors, font_path=FONT_PATH, opacity=0.72 * opacity)

    return layer.resize((W, H), Image.Resampling.LANCZOS)


def render(world_path, out_path, size=(1600, 900), svg_out=None, supersample=2):
    if not os.path.isabs(world_path) and not os.path.exists(world_path):
        world_path = os.path.join(KIT, world_path)
    manifest, assets = load_manifest()
    world = load_json(world_path)
    W, H = size
    theme = world.get("theme", {})
    ink = hex_rgba(theme.get("ink", "#3B332A"))
    seal_color = hex_rgba(theme.get("seal", "#A93828"))

    paper = make_paper(world, size)
    draw = ImageDraw.Draw(paper)
    layers = world.get("layers", {})

    for item in layers.get("water_bodies", []):
        draw_water_body(paper, item, theme, size)

    # Hand-painted PNG layer: terrain, water, architecture, vegetation.
    for layer_name in ("terrain", "water", "architecture", "vegetation"):
        for item in layers.get(layer_name, []):
            asset = assets.get(item["asset"])
            if not asset or asset.get("media") == "vector":
                continue
            paste_asset(paper, asset, item["x"], item["y"], item["w"],
                        float(item.get("opacity", 1.0)), float(item.get("rotate", 0)))

    # Optional legacy hand-painted route stamps. Default worlds do not use these.
    for item in layers.get("route_stamps", []):
        asset = assets.get(item["asset"])
        if not asset:
            continue
        paste_asset(paper, asset, item["x"], item["y"], item["w"],
                    float(item.get("opacity", 1.0)), float(item.get("rotate", 0)))

    # Optional explicitly PNG-styled markers/UI, kept for hand-painted special cases.
    for item in layers.get("markers", []):
        if item.get("style") != "png":
            continue
        asset = assets.get(item["asset"])
        if asset:
            paste_asset(paper, asset, item["x"], item["y"], item.get("w", 0.03),
                        float(item.get("opacity", 1.0)))
    for item in layers.get("ui", []):
        if item.get("style") != "png":
            continue
        asset = assets.get(item["asset"])
        if asset:
            paste_asset(paper, asset, item["x"], item["y"], item.get("w", 0.08),
                        float(item.get("opacity", 1.0)))

    vector_layer = draw_vector_layer(world, size, theme, supersample=supersample)
    paper = Image.alpha_composite(paper, vector_layer)
    draw = ImageDraw.Draw(paper)

    caption = world.get("caption")
    if caption:
        draw.text((W * 0.045, H * 0.945), caption,
                  font=ImageFont.truetype(FONT_UI, max(10, int(H * 0.016))),
                  fill=hex_rgba(theme.get("ink", "#3B332A"), 150))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    paper.convert("RGB").save(out_path, "PNG")
    if svg_out:
        svg = vector_lib.overlay_svg(world, size, theme_colors(theme))
        os.makedirs(os.path.dirname(os.path.abspath(svg_out)), exist_ok=True)
        with open(svg_out, "w", encoding="utf-8") as f:
            f.write(svg)
    print("rendered", out_path, paper.size, "svg_out", svg_out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--svg-out", default=None)
    parser.add_argument("--supersample", type=int, default=2)
    args = parser.parse_args()
    render(args.world, args.out, (args.width, args.height), args.svg_out, args.supersample)
