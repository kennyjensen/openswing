"""Chained reconciliation must retain the chosen attempt's exact raw file."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.reconcile_isae_ae2_retry_chain import raw_path
from scripts.retry_isae_ae2_original import pin


class ChainedRetrySources(unittest.TestCase):
    name = 'AE-2-b01-ias004-m80'

    def fixture(self, root, run):
        folder = root/run/'jobs'/hashlib.sha256(self.name.encode()).hexdigest()[:20]
        folder.mkdir(parents=True)
        path = folder/'result.json'; path.write_text('{}')
        return path

    def test_original_artifact_and_original_unsupported_layout(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); path = self.fixture(root, 'original')
            base = root/'original/snapshot'
            view = dict(artifact_root=str(path.parent/'artifacts'))
            self.assertEqual(raw_path(self.name, view, base, {}), path)
            self.assertEqual(raw_path(self.name, {}, base, {}), path)

    def test_chained_report_keeps_prior_retry_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); path = self.fixture(root, 'earlier-retry/run')
            ledger = dict(retry_strict_source_reconstruction=dict(strict_files=[pin(path)]))
            view = dict(artifact_root=str(path.parent/'artifacts'))
            self.assertEqual(raw_path(self.name, view, root/'derived', ledger), path)
            # Metadata-only unavailable rows have no artifact_root.
            self.assertEqual(raw_path(self.name, {}, root/'derived', ledger), path)

    def test_new_declared_attempt_has_its_own_location(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); path = self.fixture(root, 'new/run')
            view = dict(artifact_root=str(path.parent/'artifacts'))
            self.assertEqual(raw_path(self.name, view, root/'base', {}, root/'new/run'), path)
            with self.assertRaises(AssertionError):
                raw_path(self.name, view, root/'base', {}, root/'different/run')

    def test_conflicting_missing_and_changed_provenance_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); old = self.fixture(root, 'original'); new = self.fixture(root, 'retry')
            view = dict(artifact_root=str(new.parent/'artifacts'))
            ledger = dict(retry_strict_source_reconstruction=dict(strict_files=[pin(old)]))
            with self.assertRaises(AssertionError):
                raw_path(self.name, view, root/'derived', ledger)
            with self.assertRaises(AssertionError):
                raw_path(self.name, {}, root/'derived', dict(retry_strict_source_reconstruction=dict(strict_files=[])))
            ledger['retry_strict_source_reconstruction']['strict_files'].append(pin(new))
            with self.assertRaises(AssertionError):
                raw_path(self.name, {}, root/'derived', ledger)
            ledger['retry_strict_source_reconstruction']['strict_files'] = [pin(new)]
            new.write_text('{"changed":true}')
            with self.assertRaises(AssertionError):
                raw_path(self.name, view, root/'derived', ledger)


if __name__ == '__main__':
    unittest.main()
