"""Bounded execution must retain pending comparisons and never replay results."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("isae_batch_runner", ROOT / "scripts/run-isae-suite.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def worker_stub(monkeypatch):
    """Exercise supervisor scheduling with no process or numerical imports."""
    state = dict(started=[], live=0, peak=0)

    async def launch(*command, **kwargs):
        request, output = map(Path, command[-2:])
        job = json.loads(request.read_text())["job"]
        state["started"].append(job["id"])
        state["live"] += 1
        state["peak"] = max(state["peak"], state["live"])
        assert all(kwargs["env"][name] == "1" for name in
                   ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"))

        class Process:
            returncode = None
            pid = -1  # Any attempted OS signal is an error in this fixture.

            async def wait(self):
                if self.returncode is None:
                    await asyncio.sleep(0)
                    progress = json.loads((request.parents[2] / "progress.json").read_text())
                    assert job["id"] in progress["active"]
                    assert job["id"] in progress["batch"]["started_job_ids"]
                    runner.write_json(output, dict(status="computed", numerical_pass=True,
                        reference_checks=[dict(name="CL", expected=1., predicted=1.,
                                               tolerance=.01, passed=True)]))
                    state["live"] -= 1
                    self.returncode = 0
                return self.returncode

        return Process()

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "8")
    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    monkeypatch.setenv("MKL_NUM_THREADS", "8")
    return state


def plan():
    return dict(code_sha256={}, jobs=[dict(id=f"SA-7:{i}", case_id="SA-7",
                adapter="polars", expected_outputs=1) for i in range(4)])


@pytest.mark.parametrize("workers", [1, 3])
def test_limit_keeps_pending_outputs_and_obeys_concurrency(tmp_path, worker_stub, workers):
    jobs = plan()
    results = {}
    batch = asyncio.run(runner.execute(jobs, tmp_path,
        SimpleNamespace(workers=workers, timeout_seconds=1, max_new_jobs=2), results))
    assert worker_stub["started"] == ["SA-7:0", "SA-7:1"]
    assert worker_stub["peak"] == min(workers, 2) and worker_stub["live"] == 0
    assert batch["status"] == "batch_limit_reached"
    assert batch["finished_new"] == batch["remaining"] == 2
    assert all(r["process_reaped"] and r["execution_completed"] for r in results.values())
    counts = runner.output_totals(jobs["jobs"], results)
    assert counts["required"] == 4 and counts["unrun"] == 2 and counts["passed"] == 2
    assert json.loads((tmp_path / "progress.json").read_text())["active"] == []


def test_resume_advances_without_repeating_success_or_failure(tmp_path, worker_stub):
    jobs = plan()
    # A terminal failed comparison is retained rather than retried automatically.
    results = {"SA-7:0": runner.checked_result(jobs["jobs"][0], dict(status="timeout"))}
    args = SimpleNamespace(workers=1, timeout_seconds=1, max_new_jobs=1)
    batch = asyncio.run(runner.execute(jobs, tmp_path, args, results))
    assert batch["resumed_finished"] == 1 and batch["remaining"] == 2
    assert worker_stub["started"] == ["SA-7:1"]
    args.max_new_jobs = 2
    batch = asyncio.run(runner.execute(jobs, tmp_path, args, results))
    assert batch["status"] == "selected_jobs_complete" and batch["remaining"] == 0
    assert worker_stub["started"] == ["SA-7:1", "SA-7:2", "SA-7:3"]
    assert results["SA-7:0"]["status"] == "timeout"
    counts = runner.output_totals(jobs["jobs"], results)
    assert counts["required"] == 4 and counts["passed"] == 3 and counts["unrun"] == 0
    batch = asyncio.run(runner.execute(jobs, tmp_path, args, results))
    assert batch["started_job_ids"] == [] and batch["finished_new"] == 0
    assert len(worker_stub["started"]) == 3


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_invalid_limit_rejected_before_start(tmp_path, worker_stub, limit):
    with pytest.raises(ValueError, match="max-new-jobs"):
        asyncio.run(runner.execute(plan(), tmp_path,
            SimpleNamespace(workers=1, timeout_seconds=1, max_new_jobs=limit), {}))
    assert worker_stub["started"] == []


def test_blocker_counts_toward_batch_and_does_not_start_solver(tmp_path, monkeypatch):
    jobs = plan()
    jobs["jobs"][0]["execution_route"] = "unsupported"
    monkeypatch.setattr(runner.importlib, "import_module", lambda name:
        SimpleNamespace(validate_blocked=lambda root, job: dict(status="unsupported",
            reference_checks=[dict(name="CL", expected=1., predicted=None,
                                   tolerance=.01, passed=False)])))

    async def forbidden(*args, **kwargs):
        raise AssertionError("A later numerical job must remain pending")

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", forbidden)
    results = {}
    batch = asyncio.run(runner.execute(jobs, tmp_path,
        SimpleNamespace(workers=1, timeout_seconds=1, max_new_jobs=1), results))
    assert batch["finished_new"] == 1 and batch["remaining"] == 3
    assert results["SA-7:0"]["physical_solver_calls"] == 0
    assert not results["SA-7:0"]["subprocess_started"]
