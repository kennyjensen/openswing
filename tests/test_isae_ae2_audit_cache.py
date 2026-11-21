"""Digest reuse cannot publish changed files or mutate its cached evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.assess_isae_ae2_cached import PinTransaction
from scripts.isae_suite_aeroelastic import _pin


class AuditDigestTransaction(unittest.TestCase):
    def test_pin_schemas_and_final_fresh_reads(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'source'; path.write_bytes(b'original')
            calls = []
            def fresh(p):
                calls.append(str(p))
                return _pin(p)
            cache = PinTransaction(fresh)
            expected = _pin(path)
            self.assertEqual(cache.with_bytes(path), expected)
            self.assertEqual(cache.plain(path), {k: expected[k] for k in ('path', 'sha256')})
            self.assertEqual(len(calls), 1)
            self.assertEqual(cache.finish(), [expected])
            self.assertEqual(len(calls), 2)

    def test_same_size_change_is_rejected_before_publication(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'source'; path.write_bytes(b'abc')
            cache = PinTransaction(_pin); before = cache.with_bytes(path)
            path.write_bytes(b'xyz')
            self.assertEqual(cache.with_bytes(path), before)
            with self.assertRaisesRegex(AssertionError, 'changed before publication'):
                cache.finish()

    def test_consumers_cannot_modify_cached_pin(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'source'; path.write_bytes(b'original')
            cache = PinTransaction(_pin)
            value = cache.with_bytes(path); value['sha256'] = 'changed'
            self.assertEqual(cache.with_bytes(path), _pin(path))
            self.assertEqual(cache.finish(), [_pin(path)])


if __name__ == '__main__':
    unittest.main()
