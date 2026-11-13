from pathlib import Path
import tempfile
import unittest

from workspace_paths import photo_source_path


class PhotoSourceTests(unittest.TestCase):
    def test_default_photos_follow_moved_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'original'
            (original / 'Photos').mkdir(parents=True)
            moved = root / 'moved workspace'
            original.rename(moved)
            self.assertEqual(photo_source_path(moved), moved.resolve() / 'Photos')

    def test_relative_source_stays_in_workspace(self):
        root = Path('/private/tmp/new workspace')
        self.assertEqual(photo_source_path(root, 'Original Photos'), root / 'Original Photos')

    def test_external_source_is_preserved(self):
        self.assertEqual(photo_source_path('/private/tmp/workspace', '/Volumes/Photos'), Path('/Volumes/Photos'))


if __name__ == '__main__':
    unittest.main()
