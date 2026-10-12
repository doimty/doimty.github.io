#!/usr/bin/env python3
"""Offline negative controls for the public Pages publication boundary."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('pages', Path(__file__).with_name('prepare-pages.py'))
pages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pages)


class PublicationBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.output = Path(self.tmp.name) / 'site'
        for name in pages.ROOT_ASSETS:
            (self.root / name).write_text('<html></html>' if name.endswith('.html') else 'fixture')
        (self.root / 'sources').mkdir()
        self.name = 'public-source.tar.gz'
        content = b'public-source-fixture'
        (self.root / 'sources' / self.name).write_bytes(content)
        self.registry = {self.name: ('owner/public', hashlib.sha256(content).hexdigest())}
        self.checked = []
        self.mock = patch.object(pages, 'PUBLIC_ARCHIVES', self.registry)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def public(self, repo):
        self.checked.append(repo)
        return True

    def run_stage(self, lookup=None):
        return pages.stage(self.root, self.output, self.public if lookup is None else lookup)

    def rejected(self, pattern, lookup=None):
        with self.assertRaisesRegex(ValueError, pattern):
            self.run_stage(lookup)
        self.assertFalse(self.output.exists(), 'failure must not create any deployment artifact')

    def test_public_archive_copied_byte_for_byte(self):
        report = self.run_stage()
        self.assertEqual(self.checked, ['owner/public'])
        self.assertEqual(report['public_source_archives'], [self.name])
        self.assertEqual((self.output / 'sources' / self.name).read_bytes(), b'public-source-fixture')

    def test_unknown_private_archive_rejected(self):
        (self.root / 'sources' / 'private-source.zip').write_bytes(b'private')
        self.rejected('unapproved repository file')

    def test_known_name_with_changed_content_rejected(self):
        (self.root / 'sources' / self.name).write_bytes(b'private')
        self.rejected('hash mismatch')

    def test_private_origin_rejected(self):
        self.rejected('not verifiably public', lambda repo: False)

    def test_non_boolean_origin_rejected(self):
        self.rejected('not verifiably public', lambda repo: 'public')

    def test_unavailable_api_fail_closed(self):
        def unavailable(repo):
            raise OSError('API unavailable')
        with self.assertRaises(OSError):
            self.run_stage(unavailable)
        self.assertFalse(self.output.exists())

    def test_private_html_source_link_rejected(self):
        (self.root / 'index.html').write_text('<a href="https://github.com/owner/private/archive/HEAD.zip">source</a>')
        self.rejected('not verifiably public', lambda repo: repo != 'owner/private')

    def test_public_html_link_checked(self):
        (self.root / 'index.html').write_text('<a href="https://github.com/other/public/tree/main">source</a>')
        self.run_stage()
        self.assertEqual(self.checked, ['other/public', 'owner/public'])

    def test_private_source_hidden_in_depiction_rejected(self):
        folder = self.root / 'depictions' / 'plugin'
        folder.mkdir(parents=True)
        (folder / 'private.xm').write_text('private source')
        self.rejected('unapproved repository file')

    def test_root_archive_rejected(self):
        (self.root / 'private.tar.gz').write_bytes(b'private')
        self.rejected('unapproved repository file')

    def test_symlink_rejected(self):
        (self.root / 'unsafe').symlink_to(self.root / 'sources' / self.name)
        self.rejected('symlink rejected')

    def test_missing_index_rejected(self):
        (self.root / 'Packages').unlink()
        self.rejected('required APT site asset missing')

    def test_missing_public_archive_rejected(self):
        (self.root / 'sources' / self.name).unlink()
        self.rejected('inventory mismatch')

    def test_stale_output_rejected(self):
        self.output.mkdir()
        (self.output / 'private.zip').write_bytes(b'private')
        with self.assertRaisesRegex(ValueError, 'output must be new'):
            self.run_stage()

    def test_metadata_and_scripts_not_uploaded(self):
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts' / 'tool.py').write_text('print("maintenance")')
        (self.root / 'scripts' / 'index-overrides.json').write_text('{}')
        (self.root / 'README.md').write_text('maintenance notes')
        self.run_stage()
        self.assertFalse((self.output / 'scripts').exists())
        self.assertFalse((self.output / 'README.md').exists())

    def test_scripts_unknown_type_rejected(self):
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts' / 'notes.txt').write_text('maintenance')
        self.rejected('unapproved repository file')


if __name__ == '__main__':
    unittest.main(verbosity=2)
