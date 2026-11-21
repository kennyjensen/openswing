"""Path reuse must preserve strict behavior and reject changed resolution."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import assess_isae_ae2_resolved as driver
from scripts.assess_isae_ae2_resolved import ResolutionTransaction


class AuditResolutionTransaction(unittest.TestCase):
    def test_result_parity_and_fresh_final_resolution(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'file').write_text('same')
            (root/'link').symlink_to('file')
            calls = []
            def fresh(path, strict=False):
                calls.append((str(path), strict))
                return Path.resolve(path, strict=strict)
            cache = ResolutionTransaction(fresh)
            path = root/'link'
            self.assertEqual(cache.resolve(path), path.resolve())
            self.assertEqual(cache.resolve(path), path.resolve())
            self.assertEqual(len(calls), 1)
            self.assertEqual(cache.finish(), [dict(path=str(path), strict=False,
                resolved=str(path.resolve()))])
            self.assertEqual(len(calls), 2)

    def test_retargeted_symlink_with_identical_bytes_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['first', 'second']:
                (root/name).write_text('identical')
            link = root/'link'; link.symlink_to('first')
            cache = ResolutionTransaction(Path.resolve); cache.resolve(link)
            link.unlink(); link.symlink_to('second')
            with self.assertRaisesRegex(AssertionError, 'resolution changed'):
                cache.finish()

    def test_strictness_is_not_reused_from_nonstrict_lookup(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'absent'
            cache = ResolutionTransaction(Path.resolve)
            self.assertEqual(cache.resolve(path), path.resolve())
            with self.assertRaises(FileNotFoundError):
                cache.resolve(path, strict=True)
            path.write_text('present')
            self.assertEqual(cache.resolve(path, strict=True), path.resolve(strict=True))
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                cache.finish()

    def test_relative_working_directory_change_is_rejected(self):
        before = os.getcwd()
        with TemporaryDirectory() as directory:
            cache = ResolutionTransaction(Path.resolve)
            cache.resolve(Path('relative'))
            try:
                os.chdir(directory)
                with self.assertRaisesRegex(AssertionError, 'working directory'):
                    cache.resolve(Path('relative'))
                with self.assertRaisesRegex(AssertionError, 'working directory'):
                    cache.finish()
            finally:
                os.chdir(before)

    def test_changed_path_cannot_publish_and_global_resolver_is_restored(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); link = root/'link'
            (root/'first').write_text('identical')
            (root/'second').write_text('identical')
            link.symlink_to('first')
            output = root/'assessment.json'; original = Path.resolve
            def inner(runs, candidate, recoveries):
                link.resolve()
                link.unlink(); link.symlink_to('second')
                candidate.write_text('{}')
            with patch.object(driver.cached, 'assess', side_effect=inner):
                with self.assertRaisesRegex(AssertionError, 'resolution changed'):
                    driver.assess([], output, [])
            self.assertFalse(output.exists())
            self.assertIs(Path.resolve, original)


if __name__ == '__main__':
    unittest.main()
