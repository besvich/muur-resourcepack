"""Approximate textured preview of a player wearing the muur kit (no game needed).

Software renderer: every part is a textured cuboid (player skin, armour layers inflated like the game does, and the
cuboid item models used for the item_display entities). Orthographic, painter's algorithm, nearest-neighbour textures.
It checks shapes, proportions, UV placement and colours; it does NOT reproduce game lighting, animation or the exact
display-entity anchoring (that needs a real client).

    python tools/render_player.py              -> preview/player_*.png

Units: 1 unit = 1 player-model pixel (player is 32 units tall, front faces -Z, the character's right is +X).
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
PACK = BASE / 'muur' / 'assets' / 'muur'
OUT = BASE / 'preview'
SKIN = BASE / 'tools' / 'ref' / 'steve.png'
OUT.mkdir(exist_ok=True)

TINTS = {'white': (255, 255, 255), 'orange': (232, 140, 60), 'black': (70, 70, 80), 'sky': (120, 170, 235)}


# ------------------------------------------------------------------ geometry
class Quad:
    def __init__(self, p0, u, v, image, normal, tint=None, light=1.0):
        self.p0, self.u, self.v, self.image, self.normal, self.tint, self.light = p0, u, v, image, normal, tint, light


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vmul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def face_regions(u, v, w, h, d):
    return {
        'top': (u + d, v, w, d), 'bottom': (u + d + w, v, w, d),
        'right': (u, v + d, d, h), 'front': (u + d, v + d, w, h),
        'left': (u + d + w, v + d, d, h), 'back': (u + 2 * d + w, v + d, w, h),
    }


def box_quads(tex, lo, size, uv, inflate=0.0, mirror=False, tint=None):
    """Cuboid in player-skin UV layout. lo = min corner, size = (w, h, d)."""
    w, h, d = size
    x0, y0, z0 = lo[0] - inflate, lo[1] - inflate, lo[2] - inflate
    x1, y1, z1 = lo[0] + w + inflate, lo[1] + h + inflate, lo[2] + d + inflate
    W, H, D = w + 2 * inflate, h + 2 * inflate, d + 2 * inflate
    regions = face_regions(uv[0], uv[1], w, h, d)
    geo = {
        'front': ((x1, y1, z0), (-W, 0, 0), (0, -H, 0), (0, 0, -1)),
        'back': ((x0, y1, z1), (W, 0, 0), (0, -H, 0), (0, 0, 1)),
        'right': ((x1, y1, z1), (0, 0, -D), (0, -H, 0), (1, 0, 0)),
        'left': ((x0, y1, z0), (0, 0, D), (0, -H, 0), (-1, 0, 0)),
        'top': ((x1, y1, z1), (-W, 0, 0), (0, 0, -D), (0, 1, 0)),
        'bottom': ((x1, y0, z0), (-W, 0, 0), (0, 0, D), (0, -1, 0)),
    }
    quads = []
    for name, (p0, uvec, vvec, normal) in geo.items():
        region_name = name
        flip = False
        if mirror:
            flip = True
            if name == 'right':
                region_name = 'left'
            elif name == 'left':
                region_name = 'right'
        rx, ry, rw, rh = regions[region_name]
        crop = tex.crop((rx, ry, rx + rw, ry + rh)).convert('RGBA')
        if flip:
            crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
        quads.append(Quad(p0, uvec, vvec, crop, normal, tint))
    return quads


def model_quads(model_path, parts, anchor, tint):
    """Cuboid elements of a block-style item model; model point (8,8,8) is placed at `anchor`."""
    data = json.loads(Path(model_path).read_text(encoding='utf-8'))
    quads = []
    for el in data['elements']:
        (x0, y0, z0), (x1, y1, z1) = el['from'], el['to']

        def P(x, y, z):
            return (anchor[0] + x - 8, anchor[1] + y - 8, anchor[2] + z - 8)

        geo = {
            'north': (P(x1, y1, z0), (-(x1 - x0), 0, 0), (0, -(y1 - y0), 0), (0, 0, -1)),
            'south': (P(x0, y1, z1), (x1 - x0, 0, 0), (0, -(y1 - y0), 0), (0, 0, 1)),
            'east': (P(x1, y1, z1), (0, 0, -(z1 - z0)), (0, -(y1 - y0), 0), (1, 0, 0)),
            'west': (P(x0, y1, z0), (0, 0, z1 - z0), (0, -(y1 - y0), 0), (-1, 0, 0)),
            'up': (P(x1, y1, z1), (-(x1 - x0), 0, 0), (0, 0, -(z1 - z0)), (0, 1, 0)),
            'down': (P(x1, y0, z0), (-(x1 - x0), 0, 0), (0, 0, z1 - z0), (0, -1, 0)),
        }
        for name, (p0, uvec, vvec, normal) in geo.items():
            face = el['faces'][name]
            u0, v0, u1, v1 = face['uv']
            crop = parts.crop((int(u0), int(v0), int(u1), int(v1))).convert('RGBA')
            quads.append(Quad(p0, uvec, vvec, crop, normal, tint if face.get('tintindex') == 0 else None))
    return quads


# ------------------------------------------------------------------ rasteriser
def render(quads, yaw_deg=0.0, pitch_deg=12.0, size=(520, 640), scale=15.0, centre=(0, 16, 0), bg=(58, 62, 74, 255)):
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    cy, sy_ = math.cos(yaw), math.sin(yaw)
    d = (0.0, -math.sin(pitch), math.cos(pitch))

    def rot(p):
        x, y, z = p[0] - centre[0], p[1] - centre[1], p[2] - centre[2]
        return (x * cy + z * sy_, y, -x * sy_ + z * cy)

    def rot_dir(p):
        return (p[0] * cy + p[2] * sy_, p[1], -p[0] * sy_ + p[2] * cy)

    def screen(p):
        return (size[0] / 2 + p[0] * scale, size[1] / 2 - (p[1] * math.cos(pitch) + p[2] * math.sin(pitch)) * scale)

    items = []
    for q in quads:
        n = rot_dir(q.normal)
        if n[0] * d[0] + n[1] * d[1] + n[2] * d[2] >= 0:
            continue
        corners = [q.p0, vadd(q.p0, q.u), vadd(q.p0, vadd(q.u, q.v)), vadd(q.p0, q.v)]
        rc = [rot(c) for c in corners]
        depth = sum(c[0] * d[0] + c[1] * d[1] + c[2] * d[2] for c in rc) / 4
        items.append((depth, q, rc, n))
    canvas = Image.new('RGBA', size, bg)
    for depth, q, rc, n in sorted(items, key=lambda t: -t[0]):
        s0, s1, s3 = screen(rc[0]), screen(rc[1]), screen(rc[3])
        su, sv = (s1[0] - s0[0], s1[1] - s0[1]), (s3[0] - s0[0], s3[1] - s0[1])
        det = su[0] * sv[1] - su[1] * sv[0]
        if abs(det) < 1e-3:
            continue
        w, h = q.image.size
        inv = (sv[1] / det, -sv[0] / det, -su[1] / det, su[0] / det)  # inverse of [su sv] columns
        a1, a2 = w * inv[0], w * inv[1]
        b1, b2 = h * inv[2], h * inv[3]
        a3 = -(a1 * s0[0] + a2 * s0[1])
        b3 = -(b1 * s0[0] + b2 * s0[1])
        layer = q.image.transform(size, Image.AFFINE, (a1, a2, a3, b1, b2, b3), resample=Image.NEAREST)
        light = 0.62 + 0.38 * max(0.0, n[0] * -0.35 + n[1] * 0.75 + n[2] * -0.55)
        px = layer.load()
        tint = q.tint
        for yy in range(size[1]):
            for xx in range(size[0]):
                r, g, b, a = px[xx, yy]
                if a == 0:
                    continue
                if tint is not None:
                    r, g, b = r * tint[0] // 255, g * tint[1] // 255, b * tint[2] // 255
                px[xx, yy] = (int(r * light), int(g * light), int(b * light), a)
        canvas.alpha_composite(layer)
    return canvas


# ------------------------------------------------------------------ scene
def load(path):
    return Image.open(path).convert('RGBA')


def player_quads(skin, collar=None, paws=None, tint=(255, 255, 255), hat_layer=True):
    quads = []
    parts = {  # name: (lo, size, skin uv, overlay uv, mirror-for-armour)
        'head': ((-4, 24, -4), (8, 8, 8), (0, 0), (32, 0), False),
        'body': ((-4, 12, -2), (8, 12, 4), (16, 16), (16, 32), False),
        'rarm': ((4, 12, -2), (4, 12, 4), (40, 16), (40, 32), False),
        'larm': ((-8, 12, -2), (4, 12, 4), (32, 48), (48, 48), True),
        'rleg': ((0, 0, -2), (4, 12, 4), (0, 16), (0, 32), False),
        'lleg': ((-4, 0, -2), (4, 12, 4), (16, 48), (0, 48), True),
    }
    for name, (lo, size, uv, ov, mirror_armour) in parts.items():
        quads += box_quads(skin, lo, size, uv)
        if hat_layer:
            quads += box_quads(skin, lo, size, ov, inflate=0.5 if name == 'head' else 0.25)
    # armour layers use the 64x32 layout: left limbs reuse the right limb UV, mirrored
    armour_uv = {'head': (0, 0), 'body': (16, 16), 'rarm': (40, 16), 'larm': (40, 16), 'rleg': (0, 16), 'lleg': (0, 16)}
    for piece, wanted in (('collar', ('body', 'rarm', 'larm')), ('paws', ('rleg', 'lleg'))):
        textures = collar if piece == 'collar' else paws
        if textures is None:
            continue
        base, overlay = textures
        for name in wanted:
            lo, size, _, _, mirror_armour = parts[name]
            for tex, tinted in ((base, tint), (overlay, None)):
                quads += box_quads(tex, lo, size, armour_uv[name], inflate=1.0, mirror=mirror_armour, tint=tinted)
    return quads


def scene(tint_name="white", kit=True, ears=True, tail=True, yaw=0, pitch=12, size=(520, 640), scale=15.0, centre=(0, 16, 0)):
    skin = load(SKIN)
    parts = load(PACK / 'textures/item/parts.png')
    tint = TINTS[tint_name]
    d = PACK / 'textures/entity/equipment/humanoid'
    collar = (load(d / 'collar.png'), load(d / 'collar_overlay.png')) if kit else None
    paws = (load(d / 'paws.png'), load(d / 'paws_overlay.png')) if kit else None
    quads = player_quads(skin, collar, paws, tint)
    if ears:  # anchored at the head centre
        quads += model_quads(PACK / 'models/item/ears_3d.json', parts, (0, 28, 0), tint)
    if tail:  # anchored at the body centre
        quads += model_quads(PACK / 'models/item/tail_3d.json', parts, (0, 18, 0), tint)
    return render(quads, yaw, pitch, size, scale, centre)


def sheet(path, specs, cols, size=(520, 640), scale=15.0, centre=(0, 16, 0)):
    rows = (len(specs) + cols - 1) // cols
    img = Image.new('RGBA', (size[0] * cols, size[1] * rows), (40, 44, 54, 255))
    for i, spec in enumerate(specs):
        img.paste(scene(size=size, scale=scale, centre=centre, **spec), ((i % cols) * size[0], (i // cols) * size[1]))
    img.save(path)


if __name__ == '__main__':
    sheet(OUT / 'player_views_white.png', [dict(yaw=y) for y in (0, 40, 90, 180)], 4)
    sheet(OUT / 'player_tints.png', [dict(tint_name=t, yaw=30) for t in ('white', 'orange', 'black', 'sky')], 4)
    # head close-up from three angles
    sheet(OUT / 'player_head.png', [dict(yaw=y, pitch=8) for y in (0, 35, 90)], 3, size=(560, 560), scale=38.0, centre=(0, 30, 0))
    print('rendered into', OUT)
