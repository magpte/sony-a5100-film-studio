# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Resource-link, image-decoding and fail-before-write checks for filter badges."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

from filter_icons import BADGES, PNG_SIGNATURE, badge_png, patch_icons, verify_icons


def decode_png(data):
    """Independent chunk/CRC reader to validate the actual generated files."""
    if data[:8] != PNG_SIGNATURE:
        raise AssertionError('Bad PNG signature')
    offset, compressed, dimensions = 8, b'', None
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])[0]
        if crc != zlib.crc32(kind + payload) & 0xffffffff:
            raise AssertionError('Bad PNG CRC')
        if kind == b'IHDR':
            width, height, *formats = struct.unpack('>IIBBBBB', payload)
            if formats != [8, 6, 0, 0, 0]:
                raise AssertionError('Unsupported PNG format')
            dimensions = (width, height)
        elif kind == b'IDAT':
            compressed += payload
        offset += length + 12
        if kind == b'IEND':
            break
    if offset != len(data) or dimensions is None or kind != b'IEND':
        raise AssertionError('Truncated PNG')
    width, height = dimensions
    raw = zlib.decompress(compressed)
    stride = width * 4 + 1
    if len(raw) != height * stride or any(raw[y * stride] for y in range(height)):
        raise AssertionError('Invalid scanlines')
    return dimensions, b''.join(raw[y * stride + 1:(y + 1) * stride] for y in range(height))


class FilterIconTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        (self.base / 'assets').mkdir()
        self.profiles = [{'id': preset_id} for preset_id in BADGES]
        root = ET.Element('Root')
        parent = ET.SubElement(root, 'Layer1', ItemId='ApplicationTop')
        for preset_id in BADGES:
            ET.SubElement(parent, 'Layer2', ItemId=preset_id, IconRes='old',
                          SelectedIconRes='old', OptionStr='old_sample')
        ET.SubElement(root, 'Layer1', ItemId='FujiStrength', IconRes='settings')
        ET.ElementTree(root).write(self.base / 'assets/MenuData.xml')
        # Use two existing resource configurations, as in the pinned APK.
        for qualifier in ('drawable-long-nodpi', 'drawable-notlong-nodpi'):
            directory = self.base / 'res' / qualifier
            directory.mkdir(parents=True)
            for _, _, _, slot in BADGES.values():
                (directory / (slot + '.png')).write_bytes(badge_png('pop-color'))
        (self.base / 'resources.arsc').write_bytes(b'opaque binary resource table')

    def snapshot(self):
        return {file.relative_to(self.base).as_posix(): file.read_bytes()
                for file in self.base.rglob('*') if file.is_file()}

    def test_all_images_decode_and_have_distinct_letter_shapes(self):
        # Compare white letter masks, ignoring all palette colours and family tag.
        masks = set()
        for preset_id in BADGES:
            dimensions, raw = decode_png(badge_png(preset_id))
            self.assertEqual(dimensions, (70, 60))
            self.assertEqual(raw[:4], b'\0\0\0\0')
            masks.add(bytes(raw[(y * 70 + x) * 4:(y * 70 + x) * 4 + 3] == b'\xf7\xf7\xf2'
                            for y in range(21, 42) for x in range(18, 51)))
        self.assertEqual(len(masks), len(BADGES))

    def test_all_configurations_linked_without_changing_resource_table(self):
        before = (self.base / 'resources.arsc').read_bytes()
        manifest = patch_icons(self.base, self.profiles)
        self.assertEqual(verify_icons(self.base, self.profiles), len(BADGES))
        self.assertEqual((self.base / 'resources.arsc').read_bytes(), before)
        self.assertEqual(len(manifest['presets']), len(BADGES))
        self.assertEqual(len({entry['resource'] for entry in manifest['presets']}), len(BADGES))
        self.assertEqual(len({entry['sha256'] for entry in manifest['presets']}), len(BADGES))
        for entry in manifest['presets']:
            self.assertEqual(len(entry['files']), 2)
            for name in entry['files']:
                data = (self.base / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                self.assertEqual(decode_png(data)[0], (70, 60))
        settings = next(node for node in ET.parse(self.base / 'assets/MenuData.xml').iter()
                        if node.get('ItemId') == 'FujiStrength')
        self.assertEqual(settings.get('IconRes'), 'settings')

    def test_missing_resource_aborts_before_any_write(self):
        missing = BADGES['ricoh-cross'][3]
        for file in (self.base / 'res').glob('drawable*/' + missing + '.png'):
            file.unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Missing original PNG'):
            patch_icons(self.base, self.profiles)
        self.assertEqual(self.snapshot(), before)

    def test_outside_menu_resource_reuse_aborts_before_any_write(self):
        path = self.base / 'assets/MenuData.xml'
        tree = ET.parse(path)
        ET.SubElement(tree.getroot(), 'Layer1', ItemId='another_feature',
                      IconRes='drawable/' + BADGES['ricoh-cross'][3])
        tree.write(path)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'another menu item'):
            patch_icons(self.base, self.profiles)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_preset_requires_explicit_design(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'unique, known'):
            patch_icons(self.base, self.profiles + [{'id': 'new-filter'}])
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_output_is_detected(self):
        manifest = patch_icons(self.base, self.profiles)
        (self.base / manifest['presets'][0]['files'][0]).write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError, 'changed badge PNG'):
            verify_icons(self.base, self.profiles)


if __name__ == '__main__':
    unittest.main()
