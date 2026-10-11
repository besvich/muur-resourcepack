"""Validate a resource pack folder and build a byte-reproducible zip.

    python build.py muur            -> resourcepacks/dist/muur.zip + muur.json (sha1, size, push snippet)

Reproducible on purpose: sorted entries, fixed timestamps, fixed compression, so the SHA-1 only changes when the
content changes (the server sends that hash to clients; a changing hash forces every client to re-download).
Future packs are sibling folders of `muur` and build the same way; each gets its own stable pack id on the platform
(`resource_pack.push` derives the UUID from the pack name).
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent.parent


def fail(errors):
    print('\n'.join('ERROR ' + e for e in errors))
    sys.exit(1)


def ns_path(root, ref, kind, ext):
    namespace, _, path = ref.partition(':') if ':' in ref else ('minecraft', '', ref)
    return None if namespace == 'minecraft' else root / 'assets' / namespace / kind / (path + ext)


def validate(root):
    errors = []
    if not (root / 'pack.mcmeta').is_file():
        errors.append('pack.mcmeta missing')
    jsons = {}
    for path in sorted(root.rglob('*.json')) + sorted(root.rglob('*.mcmeta')):
        try:
            jsons[path] = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:  # noqa: BLE001 - report any parse problem
            errors.append(f'{path.relative_to(root)}: invalid JSON ({exc})')

    def need(ref, kind, ext, owner):
        target = ns_path(root, ref, kind, ext)
        if target is not None and not target.is_file():
            errors.append(f'{owner}: missing {kind}/{ref}{ext}')

    for path, data in jsons.items():
        rel = path.relative_to(root).as_posix()
        if '/models/' in rel and isinstance(data, dict):
            for ref in data.get('textures', {}).values():
                if not ref.startswith('#'):
                    need(ref, 'textures', '.png', rel)
            for element in data.get('elements', []):
                for face in element['faces'].values():
                    if face['texture'].startswith('#') and face['texture'][1:] not in data['textures']:
                        errors.append(f'{rel}: face uses undefined texture variable {face["texture"]}')
        if '/items/' in rel:
            stack = [data['model']]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    if node.get('type') == 'minecraft:model':
                        need(node['model'], 'models', '.json', rel)
                    stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
                elif isinstance(node, list):
                    stack.extend(node)
        if '/equipment/' in rel:
            for layer_type, layers in data['layers'].items():
                for layer in layers:
                    need(layer['texture'], f'textures/entity/equipment/{layer_type}', '.png', rel)
    for png in sorted(root.rglob('*.png')):
        rel = png.relative_to(root).as_posix()
        size = Image.open(png).size
        if '/entity/equipment/humanoid/' in rel and size != (64, 32):
            errors.append(f'{rel}: humanoid armour layer must be 64x32, is {size}')
        if '/textures/item/' in rel and size[0] != size[1]:
            errors.append(f'{rel}: item texture must be square, is {size}')
    return errors


def build(name):
    root = BASE / name
    if not root.is_dir():
        fail([f'no pack folder {root}'])
    errors = validate(root)
    if errors:
        fail(errors)
    dist = BASE / 'dist'
    dist.mkdir(exist_ok=True)
    target = dist / f'{name}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    data = target.read_bytes()
    sha1 = hashlib.sha1(data).hexdigest()
    meta = {'name': f'{name}:pack', 'file': target.name, 'bytes': len(data), 'sha1': sha1,
            'push': {'name': f'{name}:pack', 'url': 'REPLACE_WITH_HTTPS_URL_OF_THE_ZIP', 'hash': sha1, 'required': True,
                     'prompt': 'Ресурс-пак сервера (Мур-комплект)'}}
    (dist / f'{name}.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'OK {target} {len(data)} bytes sha1={sha1}')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'muur')
