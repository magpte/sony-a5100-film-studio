# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Original badge artwork and patching logic only; see LICENSING.md and NOTICE.
"""Build small, distinct filter badges without adding Android resource IDs.

The pinned APK is decoded with apktool -r. Its resources.arsc therefore stays
binary and cannot discover newly named drawables. Reuse the thirteen original
effect-menu icon slots and two original illustration-submenu slots instead.
Those slots have no executable-smali/compiled-layout references in the pinned
input, and their original MenuData subtree is replaced by build_apk.patch_menu.

All artwork below is original, drawn from rectangles and a tiny bitmap alphabet;
it uses no photographs, logos, external fonts or image libraries. The badges
identify presets, rather than purporting to show their rendered colour effects.
PNG decoding and resource loading work on the camera's Android API 10 runtime.
"""
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib


WIDTH, HEIGHT = 70, 60
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
MENU_PREFIX = 'p_16_dd_parts_pe_menu_icon_normal_'

# Stable IDs and resource names keep icon assignments independent of menu order.
# The two large letters remain distinguishable without relying on colour alone.
BADGES = {
    'pop-color':      ('PV', 'F', (89, 182, 140), MENU_PREFIX + 'pop_color'),
    'fuji-velvia':    ('VV', 'F', (233, 133, 69), MENU_PREFIX + 'hdr'),
    'fuji-astia':     ('AS', 'F', (220, 158, 167), MENU_PREFIX + 'soft_focus'),
    'fuji-chrome':    ('CC', 'F', (112, 165, 183), MENU_PREFIX + 'retro'),
    'fuji-reala':     ('RA', 'F', (158, 185, 117), MENU_PREFIX + 'miniature_plus'),
    'fuji-proneg':    ('PN', 'F', (210, 175, 138), MENU_PREFIX + 'soft_high_key_plus'),
    'fuji-negative':  ('CN', 'F', (197, 149, 90), MENU_PREFIX + 'toycamera_plus'),
    'fuji-eterna':    ('ET', 'F', (146, 165, 146), MENU_PREFIX + 'part_color_plus'),
    'fuji-bleach':    ('EB', 'F', (168, 174, 177), MENU_PREFIX + 'posterization'),
    'fuji-acros':     ('AC', 'F', (228, 228, 228), MENU_PREFIX + 'rich_tone_mono'),
    'ricoh-positive': ('RP', 'R', (120, 188, 207), MENU_PREFIX + 'watercolor'),
    'ricoh-negative': ('RN', 'R', (218, 179, 116), MENU_PREFIX + 'illustration'),
    'ricoh-hcbw':     ('HC', 'R', (250, 250, 250), MENU_PREFIX + 'high_contrast_mono'),
    'ricoh-daido':    ('MD', 'R', (174, 174, 174),
                      'p_16_dd_parts_specialscreen_icon_pictureeffect_illust_high_normal'),
    'ricoh-cross':    ('XP', 'R', (170, 176, 235),
                      'p_16_dd_parts_specialscreen_icon_pictureeffect_illust_low_normal'),
    'custom-lut':     ('CL', 'C', (230, 126, 34),
                      'p_16_dd_parts_specialscreen_icon_pictureeffect_illust_mid_normal'),
}

# Original 5x7 glyphs. Only the small set of letters needed by the badges is used.
FONT = {
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'B': ('11110', '10001', '10001', '11110', '10001', '10001', '11110'),
    'C': ('01111', '10000', '10000', '10000', '10000', '10000', '01111'),
    'D': ('11110', '10001', '10001', '10001', '10001', '10001', '11110'),
    'E': ('11111', '10000', '10000', '11110', '10000', '10000', '11111'),
    'F': ('11111', '10000', '10000', '11110', '10000', '10000', '10000'),
    'H': ('10001', '10001', '10001', '11111', '10001', '10001', '10001'),
    'L': ('10000', '10000', '10000', '10000', '10000', '10000', '11111'),
    'M': ('10001', '11011', '10101', '10101', '10001', '10001', '10001'),
    'N': ('10001', '11001', '11001', '10101', '10011', '10011', '10001'),
    'P': ('11110', '10001', '10001', '11110', '10000', '10000', '10000'),
    'R': ('11110', '10001', '10001', '11110', '10100', '10010', '10001'),
    'S': ('01111', '10000', '10000', '01110', '00001', '00001', '11110'),
    'T': ('11111', '00100', '00100', '00100', '00100', '00100', '00100'),
    'V': ('10001', '10001', '10001', '10001', '10001', '01010', '00100'),
    'X': ('10001', '10001', '01010', '00100', '01010', '10001', '10001'),
}


def _rectangle(pixels, width, x, y, w, h, color):
    rgba = bytes((*color, 255)) if len(color) == 3 else bytes(color)
    for row in range(y, y + h):
        start = (row * width + x) * 4
        pixels[start:start + w * 4] = rgba * w


def _letters(pixels, text, x, y, scale, color):
    for index, letter in enumerate(text):
        for row, bits in enumerate(FONT[letter]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    _rectangle(pixels, WIDTH, x + (index * 6 + col) * scale,
                               y + row * scale, scale, scale, color)


def badge_pixels(preset_id):
    """Return a 70x60 RGBA badge with a transparent margin for menu selection."""
    label, family, accent, _ = BADGES[preset_id]
    pixels = bytearray(WIDTH * HEIGHT * 4)
    _rectangle(pixels, WIDTH, 3, 5, 64, 50, accent)
    _rectangle(pixels, WIDTH, 5, 7, 60, 46, (17, 21, 24))
    _rectangle(pixels, WIDTH, 5, 7, 60, 9, accent)
    _letters(pixels, family, 9, 8, 1, (17, 21, 24))
    for x in (22, 32, 42, 52):
        _rectangle(pixels, WIDTH, x, 10, 5, 3, (17, 21, 24))
    _letters(pixels, label, 18, 21, 3, (247, 247, 242))
    for x in (12, 22, 32, 42, 52):
        _rectangle(pixels, WIDTH, x, 47, 5, 3, accent)
    return pixels


def encode_png(width, height, rgba):
    """Minimal standards-compliant, non-interlaced RGBA PNG using stdlib only."""
    if len(rgba) != width * height * 4:
        raise ValueError('Wrong RGBA buffer length')

    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))

    scanlines = b''.join(b'\0' + rgba[y * width * 4:(y + 1) * width * 4]
                        for y in range(height))
    return (PNG_SIGNATURE
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines, 9))
            + chunk(b'IEND', b''))


def badge_png(preset_id):
    return encode_png(WIDTH, HEIGHT, badge_pixels(preset_id))


def _menu(base, profiles):
    ids = [profile['id'] for profile in profiles]
    if len(ids) != len(set(ids)) or not ids or set(ids) - BADGES.keys():
        raise ValueError('Expected unique, known filter IDs')
    path = base / 'assets/MenuData.xml'
    tree = ET.parse(path)
    parents = [node for node in tree.iter() if node.get('ItemId') == 'ApplicationTop']
    if len(parents) != 1:
        raise ValueError('Expected exactly one filter menu')
    children = list(parents[0])
    if (len(children) != len(ids)
            or {node.get('ItemId') for node in children} != set(ids)):
        raise ValueError('Run patch_menu before patch_icons')
    return path, tree, {node.get('ItemId'): node for node in children}


def patch_icons(base, profiles):
    """Assign deterministic badges after patch_menu, before rename_package.

    Existing resource names/IDs and the binary resource table remain unchanged.
    Check all inputs before touching files, including accidental outside reuse
    of a reclaimed slot. Both normal and highlighted menu states use the badge;
    the original menu selection background supplies the focus indication.
    """
    base = Path(base)
    path, tree, items = _menu(base, profiles)
    slots = {BADGES[preset_id][3] for preset_id in items}
    item_nodes = set(items.values())
    for node in tree.iter():
        if node in item_nodes:
            continue
        if any(any(slot in value for slot in slots) for value in node.attrib.values()):
            raise ValueError('Filter icon resource is still used by another menu item')

    planned = []
    manifest = {'size': [WIDTH, HEIGHT], 'kind': 'preset identification badges', 'presets': []}
    for profile in profiles:
        preset_id = profile['id']
        label, family, _, slot = BADGES[preset_id]
        files = sorted((base / 'res').glob('drawable*/' + slot + '.png'))
        if not files or not all(file.read_bytes().startswith(PNG_SIGNATURE) for file in files):
            raise ValueError('Missing original PNG resource slot: ' + slot)
        data = badge_png(preset_id)
        planned.extend((file, data) for file in files)
        manifest['presets'].append(dict(
            id=preset_id, label=label, family=family, resource='drawable/' + slot,
            files=[file.relative_to(base).as_posix() for file in files],
            sha256=hashlib.sha256(data).hexdigest(),
        ))
    for entry in manifest['presets']:
        items[entry['id']].attrib.update(IconRes=entry['resource'],
                                       SelectedIconRes=entry['resource'], OptionStr='')
    for file, data in planned:
        file.write_bytes(data)
    tree.write(path, encoding='utf-8', xml_declaration=True)
    (base / 'assets/film-studio-icons.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def verify_icons(base, profiles):
    """Check decoded or assembled-then-decoded badges and menu resource links."""
    base = Path(base)
    _, _, items = _menu(base, profiles)
    for preset_id, item in items.items():
        slot = BADGES[preset_id][3]
        ref = 'drawable/' + slot
        if (item.get('IconRes') != ref or item.get('SelectedIconRes') != ref
                or item.get('OptionStr') != ''):
            raise ValueError('Wrong badge resource or stale sample: ' + preset_id)
        files = list((base / 'res').glob('drawable*/' + slot + '.png'))
        if not files or not all(file.read_bytes() == badge_png(preset_id) for file in files):
            raise ValueError('Missing or changed badge PNG: ' + preset_id)
    return len(items)


def contact_sheet(path):
    """Write a local design-review sheet; not packaged with the camera app."""
    width, height = 400, 210
    pixels = bytearray(bytes((35, 39, 43, 255)) * width * height)
    for index, preset_id in enumerate(BADGES):
        badge = badge_pixels(preset_id)
        left, top = (index % 5) * 80 + 5, (index // 5) * 70 + 5
        for y in range(HEIGHT):
            for x in range(WIDTH):
                src = (y * WIDTH + x) * 4
                if badge[src + 3]:
                    dest = ((top + y) * width + left + x) * 4
                    pixels[dest:dest + 4] = badge[src:src + 4]
    Path(path).write_bytes(encode_png(width, height, pixels))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheet', type=Path, required=True)
    contact_sheet(parser.parse_args().sheet)
