"""Verify completed SA-11 results without repeatedly reading the 18 MB plan."""
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/isae/sa11-complete-scope-20261108'
spec = importlib.util.spec_from_file_location(
    'refresh_sa11', ROOT / 'scripts/refresh-sa11-complete-scope.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
original_sha = driver.sha
plan = OUT / 'plan.json'


def identity(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


initial_identity = identity(plan)
digest = original_sha(plan)
cache_hits = 0


def cached_sha(path):
    global cache_hits
    if path == plan:
        assert identity(plan) == initial_identity, 'Plan changed during aggregation'
        cache_hits += 1
        return digest
    return original_sha(path)


driver.sha = cached_sha
driver.analyze(OUT)
assert identity(plan) == initial_identity and original_sha(plan) == digest
driver.check(driver.read(plan))
driver.write(OUT / 'aggregation-receipt.json', dict(
    observed_utc=driver.utc(), plan_sha256=digest,
    wrapper_sha256=original_sha(Path(__file__)),
    driver_sha256=original_sha(Path(driver.__file__)),
    plan_digest_cache_hits=cache_hits,
    plan_verified_before_and_after=True,
    cached_results_or_acceptance=False,
    analysis_sha256=original_sha(OUT / 'analysis.json')))
