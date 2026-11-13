import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gsheets import _find_credentials, _parse_sheet_id


class PortableSheetsTests(unittest.TestCase):
    def write_key(self, path):
        path.write_text(json.dumps({'type': 'service_account'}))

    def test_moved_workspace_ignores_old_machine_and_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = root / 'old'
            old.mkdir()
            self.write_key(old / 'credentials.json')
            moved = root / 'new machine' / 'renamed workspace'
            moved.parent.mkdir()
            old.rename(moved)
            with patch.dict(os.environ, {'EAGLE_WORKSPACE': str(moved)}):
                self.assertEqual(_find_credentials(), moved / 'credentials.json')

    def test_explicit_workspace_prefers_local_key_and_skips_other_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'credentials.json').write_text('invalid')
            (root / 'config.json').write_text('[]')
            self.write_key(root / 'service-account.json')
            self.assertEqual(_find_credentials(root), root / 'service-account.json')

    def test_missing_key_explains_reconnection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('pathlib.Path.home', return_value=root):
                with self.assertRaisesRegex(FileNotFoundError, 'Import Sheet Credentials'):
                    _find_credentials(root)

    def test_shared_key_remains_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = root / '.config/gsheets/credentials.json'
            key.parent.mkdir(parents=True)
            self.write_key(key)
            with patch('pathlib.Path.home', return_value=root):
                self.assertEqual(_find_credentials(root / 'workspace'), key)

    def test_account_specific_sheet_url_and_query(self):
        self.assertEqual(_parse_sheet_id(' https://docs.google.com/spreadsheets/u/0/d/example_ID?usp=sharing '), 'example_ID')

    def test_url_retains_sheet_id_after_transfer(self):
        self.assertEqual(_parse_sheet_id('https://docs.google.com/spreadsheets/d/example_ID/edit#gid=123'), 'example_ID')


if __name__ == '__main__':
    unittest.main()
