"""Bootstrap generator for the 'muur' resource pack (textures, models, item definitions, equipment layers).

Run once to create the source assets; after that the files under resourcepacks/muur are the source of truth and
can be repainted by hand (do NOT re-run this over hand-edited art; it overwrites). Everything is deterministic.

Design: fur is a near-white shaded texture that is tinted by the item's `minecraft:dyed_color` (customisable
colour); pink details live in separate untinted layers, so they stay pink whatever the fur colour is.
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / 'muur'
ASSETS = ROOT / 'assets' / 'muur'
PACK_FORMAT = 97  # client 26.3 version.json pack_version.resource_major

PINK = (255, 148, 190, 255)
PINK_D = (224, 104, 152, 255)
PINK_L = (255, 196, 218, 255)
GOLD = (255, 205, 60, 255)
GOLD_D = (196, 142, 24, 255)
CLEAR = (0, 0, 0, 0)


def noise(x, y, salt=0):
    return ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0xFFFF


def fur(x, y, base=238, salt=0):
    v = max(0, min(255, base + noise(x, y, salt) % 15 - 9))
    return (v, v, v, 255)


def save(img, rel):
    path = ASSETS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def write_json(rel, data, root=ASSETS):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def rect(img, x0, y0, x1, y1, colour_fn):
    """Inclusive pixel rectangle; colour_fn(x, y) -> RGBA."""
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            img.putpixel((x, y), colour_fn(x, y))


def solid(colour):
    return lambda x, y: colour


# ------------------------------------------------------------------ armour layers (64x32 humanoid layout)
def armour_layers():
    # Collar (chest piece): 2-row band at the top of the torso: fur trim above, pink band below.
    base = Image.new('RGBA', (64, 32), CLEAR)
    over = Image.new('RGBA', (64, 32), CLEAR)
    for x0, x1 in ((21, 26), (33, 38)):  # centred 6 px strips on the front and back of the torso only
        rect(base, x0, 20, x1, 20, lambda x, y: fur(x, y, 240, 1))
        rect(base, x0, 21, x1, 21, lambda x, y: fur(x, y, 224, 2))
        rect(over, x0, 21, x1, 21, solid(PINK))
    # the bell sits on the band: a 2x2 pixel gold bell (light top row, darker flare), nothing hangs below it
    rect(over, 23, 21, 24, 21, solid((255, 226, 120, 255)))
    rect(over, 23, 22, 24, 22, solid(GOLD_D))
    save(base, 'textures/entity/equipment/humanoid/collar.png')
    save(over, 'textures/entity/equipment/humanoid/collar_overlay.png')

    # Paws (boots): fluffy cuff on the lower leg, toe beans on the sole and the front of the foot.
    base = Image.new('RGBA', (64, 32), CLEAR)
    over = Image.new('RGBA', (64, 32), CLEAR)
    for x0, x1 in ((0, 3), (4, 7), (8, 11), (12, 15)):  # outer, front, inner, back of the leg
        for x in range(x0, x1 + 1):
            if x % 2 == 0:
                base.putpixel((x, 28), fur(x, 28, 240, 3))  # scalloped top edge of the cuff
        rect(base, x0, 29, x1, 31, lambda x, y: fur(x, y, 232 if y < 31 else 220, 4))
    rect(base, 8, 16, 11, 19, lambda x, y: fur(x, y, 226, 5))  # sole
    rect(over, 9, 17, 10, 18, solid(PINK))  # main pad
    for p in ((8, 16), (11, 16)):
        over.putpixel(p, PINK_L)  # toes
    for x, y, c in ((4, 30, PINK_L), (7, 30, PINK_L), (5, 31, PINK), (6, 31, PINK)):  # toe beans on the front of the foot
        over.putpixel((x, y), c)
    save(base, 'textures/entity/equipment/humanoid/paws.png')
    save(over, 'textures/entity/equipment/humanoid/paws_overlay.png')

    for name in ('collar', 'paws'):
        write_json(f'equipment/{name}.json', {'layers': {'humanoid': [
            {'texture': f'muur:{name}', 'dyeable': {'color_when_undyed': -1}},
            {'texture': f'muur:{name}_overlay'},
        ]}})


# ------------------------------------------------------------------ 16x16 inventory icons (fur layer + pink layer)
def icons():
    def new():
        return Image.new('RGBA', (16, 16), CLEAR)

    def dilate(img, colour_fn):
        out = img.copy()
        for y in range(16):
            for x in range(16):
                if img.getpixel((x, y))[3] == 0:
                    near = any(0 <= x + dx < 16 and 0 <= y + dy < 16 and img.getpixel((x + dx, y + dy))[3] > 0
                               for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                    if near:
                        out.putpixel((x, y), colour_fn(x, y))
        return out

    # ears
    fur_i, pink_i = new(), new()
    for side in (0, 1):
        steps = [(2, 6), (2, 5), (2, 4), (2, 3), (2, 2)]
        for i, (a, b) in enumerate(steps):
            y = 12 - i
            xs = range(a, b + 1) if side == 0 else range(15 - b, 15 - a + 1)
            for x in xs:
                fur_i.putpixel((x, y), fur(x, y, 240, 6))
        for i, (a, b) in enumerate([(3, 5), (3, 4), (3, 3)]):
            y = 12 - i
            xs = range(a, b + 1) if side == 0 else range(15 - b, 15 - a + 1)
            for x in xs:
                pink_i.putpixel((x, y), PINK)
    save(fur_i, 'textures/item/ears_fur.png')
    save(pink_i, 'textures/item/ears_pink.png')

    # collar
    fur_i, pink_i = new(), new()
    rect(fur_i, 2, 5, 13, 7, lambda x, y: fur(x, y, 240, 7))
    rect(fur_i, 3, 8, 12, 8, lambda x, y: fur(x, y, 226, 7))
    rect(pink_i, 3, 7, 12, 7, solid(PINK))
    rect(pink_i, 3, 8, 12, 8, solid(PINK_D))
    rect(pink_i, 7, 7, 8, 7, solid((255, 226, 120, 255)))  # the bell sits on the band, 2x2 like on the worn layer
    rect(pink_i, 7, 8, 8, 8, solid(GOLD_D))
    save(fur_i, 'textures/item/collar_fur.png')
    save(pink_i, 'textures/item/collar_pink.png')

    # paws: toe-bean print
    pads = new()
    rect(pads, 6, 8, 9, 8, solid(PINK))
    rect(pads, 5, 9, 10, 11, solid(PINK))
    rect(pads, 6, 12, 9, 12, solid(PINK))
    for x0, y0 in ((3, 5), (6, 3), (9, 3), (12, 5)):
        rect(pads, x0, y0, x0 + 1, y0 + 1, solid(PINK_L))
    fur_i = dilate(pads, lambda x, y: fur(x, y, 240, 8))
    save(fur_i, 'textures/item/paws_fur.png')
    save(pads, 'textures/item/paws_pink.png')

    # tail (same spiral as the 3D model, scaled into the 16x16 icon)
    fur_i, pink_i = new(), new()
    path = tail_path(40)
    zs, ys = [q[0] for q in path], [q[1] for q in path]
    zmin, zmax, ymin, ymax = min(zs), max(zs), min(ys), max(ys)
    scale = 11.0 / max(zmax - zmin, ymax - ymin)
    for z, y, th, tip in path:
        cx = 2.5 + (z - zmin) * scale
        cy = 13.5 - (y - ymin) * scale
        for dy in (0, 1):
            for dx in (0, 1):
                px, py = int(cx) + dx, int(cy) + dy
                if 0 <= px < 16 and 0 <= py < 16:
                    (pink_i if tip else fur_i).putpixel((px, py), PINK if tip else fur(px, py, 238, 9))
    save(fur_i, 'textures/item/tail_fur.png')
    save(pink_i, 'textures/item/tail_pink.png')

    # 3D model swatches: fur | pink / gold | dark gold (8x8 each)
    parts = Image.new('RGBA', (16, 16), CLEAR)
    rect(parts, 0, 0, 7, 7, lambda x, y: fur(x, y, 240, 10))
    rect(parts, 8, 0, 15, 7, solid(PINK))
    rect(parts, 0, 8, 7, 15, lambda x, y: tuple(max(0, c - noise(x, y, 11) % 12) for c in GOLD[:3]) + (255,))
    rect(parts, 8, 8, 15, 15, solid(GOLD_D))
    save(parts, 'textures/item/parts.png')


# ------------------------------------------------------------------ 3D models (axis-aligned cuboids, no rotations)
SWATCH = {'fur': [0, 0, 8, 8], 'pink': [8, 0, 16, 8], 'gold': [0, 8, 8, 16], 'gold_d': [8, 8, 16, 16]}


def box(a, b, swatch, tint=None):
    face = {'uv': SWATCH[swatch], 'texture': '#0'}
    if tint is not None:
        face['tintindex'] = tint
    return {'from': list(a), 'to': list(b), 'faces': {d: dict(face) for d in ('north', 'east', 'south', 'west', 'up', 'down')}}


def shift(elements, dx=0.0, dy=0.0, dz=0.0):
    for el in elements:
        el['from'] = [el['from'][0] + dx, el['from'][1] + dy, el['from'][2] + dz]
        el['to'] = [el['to'][0] + dx, el['to'][1] + dy, el['to'][2] + dz]
    return elements


HEAD_DEFAULT = {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1, 1, 1]}
# Vanilla's CustomHeadLayer renders a head-slot item with translate(0,-0.25,0) (head centre), Y 180, scale(0.625,-0.625,-0.625).
# So the model centre (8,8,8) lands on the head centre, the model must be turned 180 deg to face forward, and 1.6x scale
# makes one model unit equal one player-model pixel.
HEAD_EARS = {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1.6, 1.6, 1.6]}


def model(elements, head=None):
    return {
        'textures': {'0': 'muur:item/parts', 'particle': 'muur:item/parts'},
        'elements': elements,
        'display': {
            'fixed': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1, 1, 1]},
            'gui': {'rotation': [25, 140, 0], 'translation': [0, 0, 0], 'scale': [0.7, 0.7, 0.7]},
            'head': head or HEAD_DEFAULT,
        },
    }


# Coordinates: 1 unit = 1 player-model pixel; the model centre (8, 8, 8) is the entity position; the model faces -Z.
def tail_path(steps=13):
    """Short thin tail that always moves AWAY from the body (z only grows), so it cannot clip into the torso or legs.
    heading(t) = 12 + 48*sin(2*pi*1.25*t) + 38*t**3 degrees (0 = straight back, 90 = up): it rises, flattens, dips and curls up at the
    tip. Returns [(z, y, thickness, is_tip)] in model units (body anchor, hip at y=4); the body back face is at z=10."""
    import math
    z, y = 10.6, 4.0
    out = []
    for i in range(steps):
        t = i / (steps - 1)
        theta = math.radians(12 + 48 * math.sin(2 * math.pi * 1.25 * t) + 38 * t ** 3)
        thickness = 1.7 - 0.5 * t
        out.append((z, y, thickness, False))
        z += 0.95 * max(math.cos(theta), 0.12)   # never step back towards the body
        y += 0.95 * math.sin(theta)
    return out


def models():
    # ears: 5 stair steps, slightly leaning outwards, 2.2 px thick, pink inner slab on the front face
    ears = []
    for i, width in enumerate((3.2, 2.4, 1.6, 0.8)):
        y = 12 + i
        lean = 0.2 * i
        a, b = 4.2 - lean, 4.2 - lean + width
        ears.append(box((a, y, 5.0), (b, y + 1, 7.2), 'fur', 0))
        ears.append(box((16 - b, y, 5.0), (16 - a, y + 1, 7.2), 'fur', 0))
    for i, width in enumerate((1.9, 1.3, 0.7)):
        y = 12 + i
        a = 4.9 - 0.2 * i
        ears.append(box((a, y, 4.95), (a + width, y + 1, 5.0), 'pink'))
        ears.append(box((16 - a - width, y, 4.95), (16 - a, y + 1, 5.0), 'pink'))
    write_json('models/item/ears_3d.json', model(shift(ears, dy=0.5, dz=2.6), head=HEAD_EARS))

    # tail: a thin curled tail, voxels along tail_path(); the last fifth is the pink tip
    tail = []
    for z, y, th, tip in tail_path():
        half = th / 2
        tail.append(box((8 - half, y - half, z - half), (8 + half, y + half, z + half), 'pink' if tip else 'fur', None if tip else 0))
    write_json('models/item/tail_3d.json', model(tail))

    # flat inventory icons
    for name, layers in (('ears', 2), ('collar', 2), ('paws', 2), ('tail', 2)):
        write_json(f'models/item/{name}_icon.json', {
            'parent': 'minecraft:item/generated',
            'textures': {'layer0': f'muur:item/{name}_fur', 'layer1': f'muur:item/{name}_pink'},
        })


# ------------------------------------------------------------------ item definitions (what `minecraft:item_model` points at)
def item_definitions():
    dye = [{'type': 'minecraft:dye', 'default': -1}]
    for name in ('collar', 'paws', 'tail'):
        write_json(f'items/{name}.json', {'model': {'type': 'minecraft:model', 'model': f'muur:item/{name}_icon', 'tints': dye}})
    # ears: vanilla renders the head-slot item itself, so the 3D model is used only in the 'head' context
    write_json('items/ears.json', {'model': {
        'type': 'minecraft:select', 'property': 'minecraft:display_context',
        'cases': [{'when': 'head', 'model': {'type': 'minecraft:model', 'model': 'muur:item/ears_3d', 'tints': dye}}],
        'fallback': {'type': 'minecraft:model', 'model': 'muur:item/ears_icon', 'tints': dye}}})
    # the tail is a follower display entity (no vanilla slot renders it)
    write_json('items/tail_3d.json', {'model': {'type': 'minecraft:model', 'model': 'muur:item/tail_3d', 'tints': dye}})


def pack_meta():
    write_json('pack.mcmeta', {'pack': {
        'description': 'Мур-комплект',
        'pack_format': PACK_FORMAT, 'min_format': PACK_FORMAT, 'max_format': PACK_FORMAT,
    }}, root=ROOT)


if __name__ == '__main__':
    pack_meta()
    armour_layers()
    icons()
    models()
    item_definitions()
    print('generated into', ROOT)
