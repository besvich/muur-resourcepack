"""Static previews for the muur pack (no game needed): armour layers on their UV sheet, icons, and isometric
renders of the cuboid models. Output goes to resourcepacks/preview/ (not part of the pack)."""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
PACK = BASE / 'muur' / 'assets' / 'muur'
OUT = BASE / 'preview'
OUT.mkdir(exist_ok=True)
TINTS = {'white': (255, 255, 255), 'orange': (232, 140, 60), 'black': (70, 70, 80)}


def tint(img, colour):
    img = img.convert('RGBA')
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            px[x, y] = (r * colour[0] // 255, g * colour[1] // 255, b * colour[2] // 255, a)
    return img


def over(bg, fg):
    bg = bg.copy()
    bg.alpha_composite(fg)
    return bg


def armour_sheet():
    names = ('collar', 'paws')
    scale = 8
    sheet = Image.new('RGBA', (64 * scale * len(names), 32 * scale * len(TINTS)), (60, 60, 70, 255))
    for row, (label, colour) in enumerate(TINTS.items()):
        for col, name in enumerate(names):
            d = PACK / 'textures/entity/equipment/humanoid'
            base = tint(Image.open(d / f'{name}.png'), colour)
            layer = over(base, Image.open(d / f'{name}_overlay.png').convert('RGBA'))
            tile = Image.new('RGBA', (64, 32), (255, 0, 255, 255))
            tile.alpha_composite(layer)
            sheet.paste(tile.resize((64 * scale, 32 * scale), Image.NEAREST), (col * 64 * scale, row * 32 * scale))
    sheet.save(OUT / 'armour_layers.png')


def icon_sheet():
    names = ('ears', 'collar', 'paws', 'tail')
    scale = 12
    sheet = Image.new('RGBA', (16 * scale * len(names), 16 * scale * len(TINTS)), (60, 60, 70, 255))
    for row, colour in enumerate(TINTS.values()):
        for col, name in enumerate(names):
            tile = Image.new('RGBA', (16, 16), (110, 110, 120, 255))
            tile.alpha_composite(tint(Image.open(PACK / f'textures/item/{name}_fur.png'), colour))
            tile.alpha_composite(Image.open(PACK / f'textures/item/{name}_pink.png').convert('RGBA'))
            sheet.paste(tile.resize((16 * scale, 16 * scale), Image.NEAREST), (col * 16 * scale, row * 16 * scale))
    sheet.save(OUT / 'icons.png')


def render(model_path, colour, yaw_deg, size=420, pitch_deg=22):
    data = json.loads(model_path.read_text(encoding='utf-8'))
    parts = Image.open(PACK / 'textures/item/parts.png').convert('RGBA')
    img = Image.new('RGBA', (size, size), (60, 60, 70, 255))
    draw = ImageDraw.Draw(img)
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    d = (0, -math.sin(pitch), math.cos(pitch))
    scale = size / 26

    def rot(p):
        x, y, z = p[0] - 8, p[1] - 8, p[2] - 8
        return (x * math.cos(yaw) + z * math.sin(yaw), y, -x * math.sin(yaw) + z * math.cos(yaw))

    def screen(p):
        return (size / 2 + p[0] * scale, size / 2 - (p[1] * math.cos(pitch) + p[2] * math.sin(pitch)) * scale + 20)

    faces = []
    normals = {'north': (0, 0, -1), 'south': (0, 0, 1), 'west': (-1, 0, 0), 'east': (1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
    for el in data['elements']:
        (x0, y0, z0), (x1, y1, z1) = el['from'], el['to']
        quads = {
            'north': [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
            'south': [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            'west': [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
            'east': [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
            'up': [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
            'down': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        }
        for name, quad in quads.items():
            face = el['faces'][name]
            n = rot((normals[name][0] + 8, normals[name][1] + 8, normals[name][2] + 8))
            if n[0] * d[0] + n[1] * d[1] + n[2] * d[2] >= 0:
                continue
            u0, v0, u1, v1 = face['uv']
            r, g, b, _ = parts.getpixel((int((u0 + u1) / 2), int((v0 + v1) / 2)))
            if face.get('tintindex') == 0:
                r, g, b = r * colour[0] // 255, g * colour[1] // 255, b * colour[2] // 255
            light = 0.55 + 0.45 * max(0.0, n[0] * -0.3 + n[1] * 0.8 + n[2] * -0.5)
            rq = [rot(p) for p in quad]
            depth = sum(p[0] * d[0] + p[1] * d[1] + p[2] * d[2] for p in rq) / 4
            faces.append((depth, [screen(p) for p in rq], (int(r * light), int(g * light), int(b * light))))
    for _, poly, col in sorted(faces, key=lambda f: -f[0]):
        draw.polygon(poly, fill=col, outline=(30, 30, 30))
    return img


def model_sheet():
    names = ('ears_3d', 'tail_3d')
    views = (0, 180, 90)  # front (-Z side), back, side
    size = 420
    sheet = Image.new('RGBA', (size * len(names), size * len(views)), (60, 60, 70, 255))
    for col, name in enumerate(names):
        for row, yaw in enumerate(views):
            sheet.paste(render(PACK / f'models/item/{name}.json', TINTS['white'], yaw), (col * size, row * size))
    sheet.save(OUT / 'models_white.png')
    row = Image.new('RGBA', (size * 3, size), (60, 60, 70, 255))
    for col, name in enumerate(('orange', 'black')):
        row.paste(render(PACK / 'models/item/ears_3d.json', TINTS[name], 0), (col * size, 0))
    row.paste(render(PACK / 'models/item/tail_3d.json', TINTS['orange'], 150), (size * 2, 0))
    row.save(OUT / 'models_tinted.png')


if __name__ == '__main__':
    armour_sheet()
    icon_sheet()
    model_sheet()
    print('previews in', OUT)
