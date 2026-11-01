"""Tiny software renderer for old-format 317 models (preview images only)."""
import colorsys, math
from PIL import Image, ImageDraw, ImageFont
from cache317 import Model, hsl


def rgb(c):
    h, s, l = hsl(c)
    r, g, b = colorsys.hls_to_rgb(h / 64.0 + 1 / 128.0, min(0.98, l / 128.0 + 1 / 256.0), s / 8.0 + 1 / 16.0)
    return r, g, b


class _Merged:
    def __init__(self, models):
        self.xs, self.ys, self.zs, self.tris, self.cols, self.ftype = [], [], [], [], [], []
        self.textured = True
        for m in models:
            base = len(self.xs)
            self.xs += m.xs; self.ys += m.ys; self.zs += m.zs
            self.tris += [(a + base, b + base, c + base) for a, b, c in m.tris]
            self.cols += [m.color(i) for i in range(m.nt)]
            self.ftype += m.ftype

    def color(self, i):
        return self.cols[i]


def render(data, size=220, yaw=30, pitch=-12):
    m = _Merged([Model(d) for d in data]) if isinstance(data, (list, tuple)) else Model(data)
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    pts = []
    for x, y, z in zip(m.xs, m.ys, m.zs):
        x1, z1 = x * cy - z * sy, x * sy + z * cy
        y2, z2 = y * cp - z1 * sp, y * sp + z1 * cp
        pts.append((x1, y2, z2))
    if not pts:
        return Image.new("RGB", (size, size), (24, 24, 28))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    sc = (size * 0.86) / span
    ox = size / 2 - (max(xs) + min(xs)) / 2 * sc
    oy = size / 2 - (max(ys) + min(ys)) / 2 * sc
    img = Image.new("RGB", (size, size), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    faces = []
    for i, (a, b, c) in enumerate(m.tris):
        if m.textured and (m.ftype[i] & 2):
            col = (0.5, 0.5, 0.5)
        else:
            col = rgb(m.color(i))
        pa, pb, pc = pts[a], pts[b], pts[c]
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
        shade = 0.45 + 0.55 * abs((nx * -0.3 + ny * -0.5 + nz * -0.8) / ln)
        depth = (pa[2] + pb[2] + pc[2]) / 3
        faces.append((depth, [(p[0] * sc + ox, p[1] * sc + oy) for p in (pa, pb, pc)], tuple(int(255 * min(1, v * shade)) for v in col)))
    for _, poly, col in sorted(faces, key=lambda f: -f[0]):
        dr.polygon(poly, fill=col)
    return img


def sheet(items, path, cols=6, size=200):
    """items: list of (label, model bytes)."""
    rows = (len(items) + cols - 1) // cols
    out = Image.new("RGB", (cols * size, rows * (size + 18)), (16, 16, 20))
    d = ImageDraw.Draw(out)
    for k, (label, data) in enumerate(items):
        x, y = (k % cols) * size, (k // cols) * (size + 18)
        try:
            out.paste(render(data, size), (x, y))
        except Exception as e:
            d.text((x + 6, y + 6), "render failed", fill=(255, 80, 80))
        d.text((x + 6, y + size + 2), label[:30], fill=(230, 230, 230))
    out.save(path)
