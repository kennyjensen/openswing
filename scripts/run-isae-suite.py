"""Run the exhaustive ISAE ledger and every registered archived-output adapter.

Unimplemented comparisons are visible gaps, never skips counted as passes.
The runner does not execute upstream shell scripts or fit physical parameters.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import fnmatch
import importlib
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
# The runner is also loaded through importlib by validation tools and tests.
# Keep sibling adapter imports available outside direct CLI execution.
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
ADAPTERS = {"polars": "isae_suite_polars", "components": "isae_suite_components",
            "extra_polars": "isae_suite_extra_polars", "structure": "isae_suite_structure",
            "modes": "isae_suite_modes", "aeroelastic": "isae_suite_aeroelastic",
            "sa6": "isae_suite_sa6", "sa11": "isae_suite_sa11", "sa12": "isae_suite_sa12",
            "st2": "isae_suite_st2", "ap1": "isae_suite_ap1", "ap2": "isae_suite_ap2",
            "ae1": "isae_suite_ae1", "ae3": "isae_suite_ae3", "st1": "isae_suite_st1",
            "sa13": "isae_suite_sa13", "unsteady": "isae_suite_unsteady",
            "st3_modal": "isae_suite_st3_modal", "ae4": "isae_suite_ae4", "ae6": "isae_suite_ae6",
            "p2": "isae_suite_p2", "ae5": "isae_suite_ae5", "ffwt3": "isae_suite_ffwt3",
            "st3": "isae_suite_st3_mechanics", "st4": "isae_suite_st4_mechanics", "st5": "isae_suite_st5_mechanics"}
HELPERS = {"polars": [], "components": ["verify-isae-p1.py"],
           "extra_polars": ["isae_suite_polars.py", "isae_suite_sa15.py"],
           "structure": ["verify-source-discrete-integration.py",
                         "verify-isae-st3-archived-output.py", "isae_st3_static_reference.py",
                         "verify-isae-st5-archived-output.py", "verify-isae-st5-load-cases.py",
                         "extract-isae-st5-load-cases.py", "verify-isae-st5-roller.py",
                         "verify-isae-st5-forward.py", "assess-isae-st5-roller.py"],
           "modes": ["verify-isae-st4-arnoldi.py", "verify-isae-st4-source-modes.py"],
           "aeroelastic": ["verify-source-coupled-integration.py", "verify-isae-ffwt-reference.py"],
           "sa6": ["isae_suite_polars.py", "isae_suite_sa6_controls.py", "isae_suite_sa6_states.py", "isae_suite_sa6_mass.py", "isae_suite_sa6_mass_math.py"],
           "sa11": ["isae_suite_polars.py", "isae_suite_extra_polars.py"],
           "sa12": ["isae_suite_polars.py", "isae_suite_extra_polars.py"],
           "st2": ["isae_st2_archive.py", "isae_suite_st2_modal.py", "isae_suite_st2_mechanics.py",
                   "verify_st2_static_curves.py", "verify_st2_modal_current.py", "verify_sa14_defaults.py",
                   "isae_suite_extra_polars.py", "isae_suite_polars.py", "isae_suite_sa15.py",
                   "isae_st2.py", "isae_st2_loaded_reference.py"], "ap1": [], "ap2": ["isae_suite_ap1.py"],
           "ae1": ["isae_suite_ap1.py"],
           "ae3": ["isae_suite_ap1.py", "isae_ae3_observables.py", "extract-isae-ae3-reference.py"], "st1": ["isae_suite_st1_mechanics.py"], "sa13": [], "unsteady": [],
           "st3_modal": [], "ae4": ["verify-isae-ae4-wall-modes.py", "isae_modal_classification.py", "isae_pencil_actions.py"], "ae6": ["verify-isae-ae6-anchor.py"], "p2": [], "ae5": [], "ffwt3": [],
           "st3": ["verify_st3_static_curves_current.py", "verify_st3_modal_current.py",
                   "verify_sa14_defaults.py", "isae_st3_curve_markers.py", "isae_st3_static_reference.py",
                   "isae_st3_reference.py", "isae_suite_st3_modal.py", "verify-isae-st3-still-air-reference.py",
                   "isae_suite_extra_polars.py", "isae_suite_polars.py", "isae_suite_sa15.py", "summarize-isae-suite.py"]}


from isae_suite_st4_mechanics import EXECUTION_HELPERS as ST4_HELPERS
HELPERS["st4"] = [*ST4_HELPERS, "summarize-isae-suite.py"]

HELPERS["st5"] = ["isae_st5_recurring_worker.py", "summarize-isae-suite.py"]

SOURCE_PAIRINGS = {"sa7-fore-f745fb40": "extra_polars"}
COMPARISON_SCOPES = {"sa6-f1-rigid": "sa6", "sa6-state-rigid": "sa6", "sa6-mass-rigid": "sa6",
                     "ae1-frozen-influences": "ae1", "sa15-declared-setup": "extra_polars",
                     "ae4-undeformed-alpha0": "ae4", "ae6-declared-airflow": "ae6",
                     "sa7-documented": "extra_polars", "st1-mechanics": "st1", "st2-mechanics": "st2",
                     "st3-mechanics": "st3", "st4-mechanics": "st4", "st4-native": "st4", "st5-mechanics": "st5"}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_pins(root, adapters=None):
    files = sorted((root / "openswing").glob("*.py"))
    names = {"run-isae-suite.py", "isae_suite_catalog.py", "isae_acceptance.py"}
    for adapter in ADAPTERS if adapters is None else adapters:
        names.add(ADAPTERS[adapter] + ".py")
        names.update(HELPERS[adapter])
    files += [root / "scripts" / name for name in sorted(names)]
    return {p.relative_to(root).as_posix(): digest(p) for p in files}


def stable_code(root, pins):
    kernels = {name for name in pins if name.startswith("openswing/")}
    if kernels and kernels != {p.relative_to(root).as_posix() for p in (root / "openswing").glob("*.py")}:
        return False
    return all((root / name).is_file() and digest(root / name) == expected
               for name, expected in pins.items())


def plan_jobs(root, adapters=None, *, source_pairings=(), comparison_scopes=()):
    adapters = list(ADAPTERS if adapters is None else adapters)
    if (len(set(source_pairings)) != len(source_pairings) or
            any(name not in SOURCE_PAIRINGS for name in source_pairings)):
        raise ValueError("Provide unique reviewed historical source pairings")
    if any(SOURCE_PAIRINGS[name] not in adapters for name in source_pairings):
        raise ValueError("Historical source pairing requires its owning adapter")
    if (len(set(comparison_scopes)) != len(comparison_scopes) or
            any(name not in COMPARISON_SCOPES for name in comparison_scopes)):
        raise ValueError("Provide unique reviewed supplemental comparison scopes")
    if any(COMPARISON_SCOPES[name] not in adapters for name in comparison_scopes):
        raise ValueError("Supplemental comparison scope requires its owning adapter")
    if "sa7-documented" in comparison_scopes and "polars" not in adapters:
        raise ValueError("Documented SA-7 scope requires both polars and extra_polars adapters")
    jobs = []
    for adapter in adapters:
        module = importlib.import_module(ADAPTERS[adapter])
        pairings = [name for name in source_pairings if SOURCE_PAIRINGS[name] == adapter]
        scopes = [name for name in comparison_scopes if COMPARISON_SCOPES[name] == adapter]
        options = {}
        if pairings:
            options['source_pairings'] = pairings
        if scopes:
            options['comparison_scopes'] = scopes
        planned = module.plan(root, **options)
        if isinstance(planned, dict):
            planned = planned["jobs"]
        for original in planned:
            job = dict(original)
            job["adapter"] = adapter
            if not isinstance(job.get("id"), str) or not isinstance(job.get("case_id"), str):
                raise ValueError("Every comparison must own a stable job and family ID")
            jobs.append(job)
    if len({job["id"] for job in jobs}) != len(jobs):
        raise ValueError("Duplicate comparison job IDs")
    if "sa7-documented" in comparison_scopes:
        module = importlib.import_module(ADAPTERS["extra_polars"])
        jobs = module.select_documented_sa7(jobs)
    if "st3-mechanics" in comparison_scopes:
        jobs = [job for job in jobs if job['case_id'] != 'ST-3' or job['adapter'] == 'st3']
    if {"st4-mechanics", "st4-native"} & set(comparison_scopes):
        jobs = [job for job in jobs if job["case_id"] != "ST-4" or job["adapter"] == "st4"]
    if "st5-mechanics" in comparison_scopes:
        jobs = [job for job in jobs if job["case_id"] != "ST-5" or job["adapter"] == "st5"]
    return jobs


def select_jobs(jobs, catalog, cases=None, job_patterns=None):
    """Filter execution units while retaining the complete source catalog."""
    for label, values in (("cases", cases), ("job patterns", job_patterns)):
        if values is not None and (not values or any(not isinstance(v, str) or not v for v in values)
                                   or len(set(values)) != len(values)):
            raise ValueError("Provide unique nonempty " + label)
    known = {case['id'] for case in catalog['cases']}
    if cases is not None and set(cases) - known:
        raise ValueError("Unknown family IDs: " + ", ".join(sorted(set(cases) - known)))
    selected = [job for job in jobs if cases is None or job['case_id'] in cases]
    if job_patterns is not None:
        unmatched = [pattern for pattern in job_patterns if not any(fnmatch.fnmatchcase(job['id'], pattern) for job in selected)]
        if unmatched:
            raise ValueError("Job patterns match no jobs in the selected families/adapters: " + ", ".join(unmatched))
        selected = [job for job in selected if any(fnmatch.fnmatchcase(job['id'], pattern) for pattern in job_patterns)]
    if cases is not None and set(cases) - {job['case_id'] for job in selected}:
        raise ValueError("Selected families have no matching jobs in the selected adapters: " +
                         ", ".join(sorted(set(cases) - {job['case_id'] for job in selected})))
    if not selected:
        raise ValueError("Selection contains no registered comparison jobs")
    return selected


def validate_resume_plan(path, plan, resume):
    if Path(path).exists() and (not resume or json.loads(Path(path).read_text()) != plan):
        raise ValueError("Existing run needs --resume and an identical plan, including selectors; use a new directory for changed code or scope")


def verify_registered_upstream_inputs(root, jobs, revision):
    cache = root / ".reference/isae-validation" / revision
    resolved_cache = cache.resolve()
    manifest = json.loads((cache.parent / "manifest.json").read_text())
    if manifest["revision"] != revision:
        raise ValueError("Reference manifest revision differs")
    checked = {}
    visited_paths = set()
    for job in jobs:
        for source in job.get("sources", job.get("source_pins", [])):
            path = Path(source["path"])
            if not path.is_absolute():
                path = root / path
            # Thousands of rows can share one model, driver and output table.
            # Resolve and hash each unique source once during this preflight.
            if path in visited_paths:
                continue
            visited_paths.add(path)
            try:
                relative = path.resolve().relative_to(resolved_cache).as_posix()
            except ValueError:
                continue  # External CP/decoded-figure provenance is checked by its adapter.
            if relative in checked:
                continue
            data = path.read_bytes()
            recorded = manifest["files"][relative]
            actual = hashlib.sha256(data).hexdigest()
            if actual != recorded["sha256"] or len(data) != recorded["bytes"]:
                raise ValueError("Registered reference differs from pinned upstream: " + relative)
            checked[relative] = {"bytes": len(data), "sha256": actual}
    return checked


def checked_result(job, result):
    """An adapter cannot pass a partial or empty set of required outputs."""
    result = dict(result)
    checks = result.get("reference_checks", [])
    names = [c.get("name") for c in checks]
    complete = (len(checks) == job["expected_outputs"]
                and all(isinstance(name, str) and name for name in names)
                and len(set(names)) == len(names))
    numerical = result.get("numerical_pass", result.get("numerical_passed", False)) is True
    consistent = True
    for check in checks:
        if check.get("relative_allowance_rule") is not None:
            consistent &= (job.get("adapter") == "st5" and job.get("comparison_scope") == "st5-mechanics"
                           and check["relative_allowance_rule"] == "add_printed_precision")
        x, y, tolerance = (check.get(k) for k in ("predicted", "expected", "tolerance"))
        available = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and math.isfinite(v) for v in (x, y, tolerance))
        operation = check.get("comparison", "<=")
        passed = bool(available and tolerance >= 0 and operation in ("<", "<=")
                      and (abs(x - y) < tolerance if operation == "<" else abs(x - y) <= tolerance))
        if (job.get("adapter") == "st1" and job.get("comparison_scope") != "st1-mechanics" or
                job.get("adapter") in ("st3_modal", "ae4", "ae6", "st4") or
                job.get("adapter") == "st3" and job.get("target_kind") == "modal" or job.get("adapter") == "st2" and
                job.get("target_kind") == "native_modal" or job.get("adapter") == "sa6" and
                job.get("target_kind") in ("native_control_derivatives", "native_state_derivatives", "native_mass_tensors")) and available:
            # These native contracts compare the decimal rendering of a prediction
            # against the original token interval. Preserve other adapters'
            # existing binary comparisons and never enlarge the interval.
            try:
                error = abs(Decimal(str(x)) - Decimal(check["exact_decimal_expected"]))
                half = Decimal(check["exact_decimal_tolerance"])
                passed = bool(operation == "<=" and half >= 0 and error <= half)
            except (KeyError, TypeError, ValueError, InvalidOperation):
                passed = False
                consistent = False
        if check.get("passed") is not passed:
            consistent = False
    blocked_st2_violation = (job.get("adapter") == "st2" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("numerical_passed") is True or
         result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls",
             "equilibrium_solves", "modal_solves", "production_imports"))))
    blocked_ap1_violation = (job.get("adapter") == "ap1" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks)))
    blocked_ap2_violation = (job.get("adapter") == "ap2" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls"))))
    blocked_ae1_violation = (job.get("adapter") == "ae1" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls", "production_imports"))))
    blocked_ae3_violation = (job.get("adapter") == "ae3" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls", "production_imports"))))
    blocked_st1_violation = (job.get("adapter") == "st1" and job.get("execution_route") == "unsupported" and
        (result.get("status") == "computed" or numerical or result.get("numerical_passed") is True or result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls", "production_imports"))))
    blocked_sa13_violation = (job.get("adapter") == "sa13" and
        (result.get("status") == "computed" or numerical or result.get("numerical_passed") is True or
         result.get("reference_match") is True or
         any(c.get("predicted") is not None or c.get("passed") is not False for c in checks) or
         any(result.get(key, 0) != 0 for key in ("physical_calls", "physical_solver_calls", "production_imports"))))
    contract_errors = {adapter: None for adapter in ("ap2", "ae1", "ae3", "ae4", "ae5", "ae6", "p2", "ffwt3", "st1", "st2", "st3", "st4", "st5", "sa13", "sa6", "unsteady", "st3_modal", "extra_polars")}
    adapter = job.get("adapter")
    if adapter in contract_errors and result.get("status") in ("computed", "unsupported"):
        try:
            module = importlib.import_module(ADAPTERS[adapter])
            if adapter == "st2":
                module.validate_record_contract(job)
            validator = module.validate_result_contract
            if validator(job, result) is False:
                raise ValueError(adapter.upper() + " result contract rejected the saved evidence")
        except Exception as exc:
            contract_errors[adapter] = type(exc).__name__ + ": " + str(exc)
    blocked_violation = (blocked_st2_violation or blocked_ap1_violation or blocked_ap2_violation
                         or blocked_ae1_violation or blocked_ae3_violation or blocked_st1_violation or blocked_sa13_violation)
    if blocked_violation or any(contract_errors.values()) or result.get("status") == "computed" and (not complete or not numerical or not consistent):
        result.update(status="adapter_contract_failure", reference_match=False,
                      contract_error={"complete_unique_outputs": complete,
                                      "numerical_checks_passed": numerical,
                                      "reported_precision_checks_consistent": consistent,
                                      "blocked_st2_registration_only": not blocked_st2_violation,
                                      "blocked_ap1_registration_only": not blocked_ap1_violation,
                                      "blocked_ap2_registration_only": not blocked_ap2_violation,
                                      "blocked_ae1_registration_only": not blocked_ae1_violation,
                                      "blocked_ae3_registration_only": not blocked_ae3_violation,
                                      "blocked_st1_registration_only": not blocked_st1_violation,
                                      "blocked_sa13_registration_only": not blocked_sa13_violation,
                                      **{name + "_result_contract_error": error for name, error in contract_errors.items()}})
        if blocked_violation or any(contract_errors.values()):
            result["numerical_pass"] = False
    result["reference_match"] = bool(result.get("status") == "computed" and complete
                                     and numerical and consistent
                                     and all(c.get("passed") is True for c in checks))
    finite = sum(isinstance(c.get("predicted"), (int, float))
                 and not isinstance(c.get("predicted"), bool)
                 and math.isfinite(c["predicted"]) for c in checks)
    result["output_accounting"] = {
        "required": job["expected_outputs"],
        "reported": len(checks),
        "finite": finite, "unavailable": len(checks) - finite,
        "numerically_valid": finite if result.get("status") == "computed" else 0,
        "passed": sum(c.get("passed") is True for c in checks) if result.get("status") == "computed" else 0,
        "missing": max(0, job["expected_outputs"] - len(checks))}
    return result


def output_totals(jobs, results):
    required = sum(j["expected_outputs"] for j in jobs)
    finished_required = sum(j["expected_outputs"] for j in jobs if j["id"] in results)
    selected_results = [results[j["id"]] for j in jobs if j["id"] in results]
    return {"required": required, "finished_required": finished_required,
            "unrun": required - finished_required,
            **{key: sum(r.get("output_accounting", {}).get(key, 0) for r in selected_results)
               for key in ("reported", "finite", "unavailable", "numerically_valid", "passed", "missing")}}


def summarize(catalog, jobs, results):
    by_case = defaultdict(list)
    for job in jobs:
        by_case[job["case_id"]].append(job)
    cases = []
    for item in catalog["cases"]:
        selected = by_case[item["id"]]
        done = [results[job["id"]] for job in selected if job["id"] in results]
        computed = [r for r in done if r.get("status") == "computed"]
        unsupported = [r for r in done if r.get("status") == "unsupported"]
        matches = sum(r.get("reference_match") is True for r in computed)
        if not selected:
            status = "NO_SELECTED_COMPARISON_JOBS"
        elif len(done) < len(selected):
            status = "INCOMPLETE_RUN"
        elif len(computed) + len(unsupported) < len(selected):
            status = "NUMERICAL_OR_INPUT_FAILURES"
        elif unsupported:
            status = "PARTLY_UNSUPPORTED" if computed else "UNSUPPORTED_COMPARISONS"
        elif (all(j.get('comparison_scope') == 'st3-mechanics' for j in selected)
              and (unavailable := sum(not r['source_available'] for j in selected for r in j['observations']))
              and output_totals(selected, results)['passed'] == sum(j['expected_outputs'] for j in selected)-unavailable):
            status = "AVAILABLE_REFERENCES_MATCH"
        elif matches < len(selected):
            status = "ARCHIVED_OUTPUT_DIFFERENCES"
        else:
            status = "SELECTED_SCOPE_MATCHES"
        cases.append({"id": item["id"], "path": item["path"], "status": status,
                      "jobs_planned": len(selected), "jobs_finished": len(done),
                      "jobs_computed": len(computed), "jobs_matching": matches,
                      "jobs_unsupported": len(unsupported),
                      "output_accounting": output_totals(selected, results),
                      "models": len(item["models"]),
                      "reference_candidates": len(item["reference_candidates"]),
                      "blockers": item.get("blockers", []),
                      "historical_evidence": item.get("historical_evidence", []),
                      "complete_family_reproduction": False})
        if (item['id'] in ('SA-6', 'AE-1', 'SA-15', 'AE-4', 'ST-1') or
                item['id'] in ('ST-2', 'ST-3', 'ST-4') and any(j.get('comparison_scope') in ('st2-mechanics', 'st3-mechanics', 'st4-mechanics', 'st4-native') for j in selected)):
            cases[-1]['comparison_scopes'] = {
                scope: output_totals([j for j in selected if j.get('comparison_scope', 'static') == scope], results)
                for scope in sorted({j.get('comparison_scope', 'static') for j in selected})}
    return cases


def mesh_diagnostics(jobs, results):
    """Report differences without inventing a new acceptance tolerance."""
    groups = defaultdict(list)
    for job in jobs:
        if job["adapter"] not in ("polars", "extra_polars", "sa11", "sa12"):
            continue
        pairing = job.get("source_pairing", {}).get("id", "")
        scope = job.get("comparison_scope", "")
        groups[(job["case_id"], job["table_path"], job["row_index"], pairing, scope)].append(job)
    comparisons = []
    for (case, table, row, pairing, scope), selected in groups.items():
        selected.sort(key=lambda j: j["settings"]["panels"])
        if len(selected) != 2:
            continue
        a, b = (results.get(job["id"], {}) for job in selected)
        record = {"case_id": case, "table_path": table, "row_index": row,
                  "panels": [j["settings"]["panels"] for j in selected]}
        if pairing:
            record.update(source_pairing_id=pairing, comparison_scope="supplemental_historical_source_pairing")
        elif scope:
            record.update(comparison_scope=scope)
        if a.get("status") != "computed" or b.get("status") != "computed":
            record.update(status="UNAVAILABLE", reason="Both original solves must succeed")
        else:
            ca = {x["name"]: x for x in a.get("reference_checks", [])}
            cb = {x["name"]: x for x in b.get("reference_checks", [])}
            changes = {}
            for key in ca.keys() & cb.keys():
                x, y = ca[key].get("predicted"), cb[key].get("predicted")
                if isinstance(x, (float, int)) and isinstance(y, (float, int)):
                    if math.isfinite(x) and math.isfinite(y):
                        changes[key] = abs(y - x)
            record.update(status="DIAGNOSTIC_ONLY", absolute_changes=changes)
        comparisons.append(record)
    return comparisons


def report(plan, results, root, elapsed):
    strict_totals = output_totals(plan["jobs"], results)
    policy = plan.get("reference_acceptance")
    if policy is not None:
        from isae_acceptance import apply_reference_acceptance
        results = {key: apply_reference_acceptance(
            value, relative_tolerance=policy["relative_tolerance"],
            tiny_reference=policy["tiny_reference"])
            for key, value in results.items()}
    cases = summarize(plan["catalog"], plan["jobs"], results)
    unchanged = stable_code(root, plan["code_sha256"])
    return {"format": "openswing-isae-current-suite", "version": 2,
            "status": "RECORDED_WITH_OPEN_COMPARISONS" if unchanged else "INVALID_CODE_CHANGED",
            "acceptance_target": "Original archived ASWING outputs, not experimental agreement",
            "reference_acceptance": policy,
            "strict_output_accounting": strict_totals,
            "full_suite_validated": False, "current_code_unchanged": unchanged,
            "repository": plan["catalog"].get("repository"),
            "revision": plan["catalog"].get("revision"),
            "inventory_counts": plan["catalog"].get("counts"),
            "runtime": plan["runtime"],
            "execution_policy": plan["execution_policy"],
            "selection_scope": plan.get("selection_scope"),
            "code_sha256": plan["code_sha256"], "case_families": len(cases),
            "jobs_planned": len(plan["jobs"]), "jobs_finished": len(results),
            "output_accounting": output_totals(plan["jobs"], results),
            "job_status_counts": dict(Counter(r.get("status", "unknown") for r in results.values())),
            "case_status_counts": dict(Counter(c["status"] for c in cases)),
            "seconds": elapsed, "cases": cases,
            "jobs": [{**j, "result": results.get(j["id"])} for j in plan["jobs"]],
            "mesh_diagnostics": mesh_diagnostics(plan["jobs"], results),
            "adapter_mesh_diagnostics": {
                adapter: module.mesh_diagnostics(
                    [j for j in plan["jobs"] if j["adapter"] == adapter], results)
                for adapter in plan["execution_policy"]["adapters"]
                if hasattr(module := importlib.import_module(ADAPTERS[adapter]), "mesh_diagnostics")},
            "limitations": [
                "Every upstream family is listed, including families without a current comparison adapter.",
                "Parsing, numerical convergence, output agreement and full historical reproduction are distinct.",
                "Registered adapters cover declared outputs only; other variants and output candidates remain open.",
                "Polar historical setup and node placement are not fully recovered; declared assumptions are retained per job.",
                "Printed-center checks do not account for unknown unrounded input coordinates.",
                "Two-mesh differences are diagnostics; no new agreement or mesh threshold is invented.",
                "Prior comparisons remain historical evidence, not current-source passes."]}


def markdown(data):
    lines = ["# Current ISAE regression suite", "",
             "Priority: compare **every ISAE family with archived ASWING output**. "
             "Experimental agreement is not required. The full suite is not yet reproduced.", "",
             f"This run accounts for **{data['case_families']} families** and "
             f"finishes **{data['jobs_finished']}/{data['jobs_planned']} registered jobs**. "
             "A job is a declared curve, polar row, static snapshot or unsupported comparison; it is not a family pass.", "",
             "| Family | Original models | Output candidates | Jobs computed / planned | Matching jobs | Current result |",
             "|---|---:|---:|---:|---:|---|"]
    for c in data["cases"]:
        lines.append(f"| {c['id']} | {c['models']} | {c['reference_candidates']} | "
                     f"{c['jobs_computed']} / {c['jobs_planned']} | {c['jobs_matching']} | {c['status']} |")
    policy = data.get("reference_acceptance")
    if policy is not None:
        lines += ["", f"Reference acceptance: **{100 * policy['relative_tolerance']:g}%** relative error "
                  "or the original absolute tolerance, whichever is larger. "
                  f"References with magnitude ≤ {policy['tiny_reference']:g} retain their original strict comparison. "
                  "Explicit per-check printed-precision additive rules (ST-5) are retained. "
                  "Numerical validity gates are unchanged. Original strict results remain in each job's result.json "
                  "and in the report's strict metadata. `--relative-tolerance 0` restores strict acceptance.", ""]
    lines += ["", "Output candidates are identified archive artifacts, not automatically proven model/output pairs. "
              "Families without selected comparison jobs remain visible. The catalog separately records every original model's "
              "hash and import result, the supplemental model outside case folders, and absent SA-9.", "",
              "Each registered adapter declares its original inputs, complete target rows and required outputs. "
              "Failures and timeouts remain in the denominator. Other variants and all unregistered families "
              "still need reviewed, executable archived-output comparisons.", "",
              "Run `npm run test:isae -- --output-dir PATH` for a fresh complete "
              "registered batch. Add `--plan-only` to inspect all inputs/jobs; `--resume` reuses only "
              "completed jobs from the identical pinned plan. Each job has an independent timeout, "
              "and the runner continues after a failed comparison. `--cases` and quoted `--job-pattern` globs select "
              "execution units while retaining the complete family/model catalog; omitted jobs are not validated.", ""]
    return "\n".join(lines)


def worker(job_path, output_path):
    packet = json.loads(Path(job_path).read_text())
    started = time.monotonic()
    job = packet["job"]
    try:
        if not stable_code(ROOT, packet["code_sha256"]):
            raise ValueError("Code changed after planning")
        result = importlib.import_module(ADAPTERS[job["adapter"]]).run(ROOT, job)
        result = checked_result(job, result)
        if not stable_code(ROOT, packet["code_sha256"]):
            raise ValueError("Code changed during solve")
    except Exception as exc:
        result = {"status": "error", "reference_match": False,
                  "error": type(exc).__name__ + ": " + str(exc),
                  "traceback": traceback.format_exc()}
    result.update(job_id=job["id"], seconds=time.monotonic() - started)
    write_json(output_path, result)


async def execute(plan, directory, args, results):
    semaphore = asyncio.Semaphore(args.workers)
    active = {}
    limit = getattr(args, "max_new_jobs", None)
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Provide a positive --max-new-jobs")
    resumed = len(results)
    pending = [job for job in plan["jobs"] if job["id"] not in results]
    scheduled = pending if limit is None else pending[:limit]
    batch = {"max_new_jobs": limit, "resumed_finished": resumed,
             "scheduled_job_ids": [job["id"] for job in scheduled], "started_job_ids": []}
    env = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    started = time.monotonic()
    if not stable_code(ROOT, plan["code_sha256"]):
        raise ValueError("Code changed before execution")

    def progress():
        write_json(directory / "progress.json", {"finished": len(results), "planned": len(plan["jobs"]),
                   "active": list(active), "status_counts": dict(Counter(r["status"] for r in results.values())),
                   "batch": {**batch, "finished_new": len(results)-resumed,
                             "remaining": len(plan["jobs"])-len(results)},
                   "seconds": time.monotonic() - started})

    async def stop(process):
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), 5)
        except asyncio.TimeoutError:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()

    async def one(job):
        if job["id"] in results:
            return
        async with semaphore:
            batch["started_job_ids"].append(job["id"])
            key = hashlib.sha256(job["id"].encode()).hexdigest()[:20]
            folder = directory / "jobs" / key
            folder.mkdir(parents=True, exist_ok=True)
            request, output = folder / "request.json", folder / "result.json"
            write_json(request, {"job": job, "code_sha256": plan["code_sha256"]})
            before = time.monotonic()
            if job.get("execution_route") == "unsupported":
                try:
                    result = importlib.import_module(ADAPTERS[job["adapter"]]).validate_blocked(ROOT, job)
                    if result.get("status") not in ("unsupported", "source_mismatch"):
                        raise ValueError("Inline blocker validator attempted a numerical comparison")
                except Exception as exc:
                    result = {"status": "error", "error": type(exc).__name__ + ": " + str(exc),
                              "traceback": traceback.format_exc()}
                result = checked_result(job, result)
                result.update(job_id=job["id"], supervisor_seconds=time.monotonic() - before,
                              execution_completed=True, execution_kind="inline_blocker_validation",
                              subprocess_started=False, physical_solver_calls=0)
                write_json(output, result)
                results[job["id"]] = result
                if len(results) % 50 == 0:
                    progress()
                await asyncio.sleep(0)
                return
            artifact_root = folder / "artifacts"
            artifact_root.mkdir(exist_ok=True)
            with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
                process = await asyncio.create_subprocess_exec(
                    sys.executable, str(Path(__file__).resolve()), "--worker", str(request), str(output),
                    stdout=stdout, stderr=stderr, cwd=ROOT,
                    env={**env, "TMPDIR": str(artifact_root)}, start_new_session=True)
                active[job["id"]] = process
                try:
                    progress()
                    await asyncio.wait_for(process.wait(), args.timeout_seconds)
                    if output.exists() and process.returncode == 0:
                        result = json.loads(output.read_text())
                    else:
                        result = {"status": "process_error", "reference_match": False,
                                  "exit_code": process.returncode}
                except asyncio.TimeoutError:
                    await stop(process)
                    result = {"status": "timeout", "reference_match": False,
                              "timeout_seconds": args.timeout_seconds}
                finally:
                    await stop(process)
                    active.pop(job["id"], None)
            result = checked_result(job, result)
            result.update(job_id=job["id"], supervisor_seconds=time.monotonic() - before,
                          process_exit_code=process.returncode, process_reaped=True,
                          execution_completed=True, execution_kind="subprocess", subprocess_started=True,
                          artifact_root=str(artifact_root))
            write_json(output, result)
            results[job["id"]] = result
            progress()
            if len(results) % 10 == 0 or result["status"] != "computed":
                print(f"{len(results)}/{len(plan['jobs'])}: {job['id']} {result['status']}", flush=True)

    progress()
    tasks = [asyncio.create_task(one(job)) for job in scheduled]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(stop(p) for p in list(active.values())))
        progress()
    return {**batch, "finished_new": len(results)-resumed,
            "remaining": len(plan["jobs"])-len(results),
            "status": "selected_jobs_complete" if len(results) == len(plan["jobs"]) else "batch_limit_reached"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent workers (default 1); each worker uses one BLAS thread")
    parser.add_argument("--max-new-jobs", type=int,
                        help="Run at most this many unfinished jobs, preserving the full plan for --resume")
    parser.add_argument("--timeout-seconds", type=float, default=180)
    from isae_acceptance import DEFAULT_RELATIVE_TOLERANCE
    parser.add_argument("--relative-tolerance", type=float, default=DEFAULT_RELATIVE_TOLERANCE,
                        help="Provisional relative reference allowance (default 0.05); 0 uses original strict tolerances")
    parser.add_argument("--adapters", nargs="+", choices=list(ADAPTERS), default=list(ADAPTERS))
    parser.add_argument("--cases", nargs="+", action="extend", help="Exact family IDs to execute; default is every registered family")
    parser.add_argument("--job-pattern", nargs="+", action="extend", help="Quoted, case-sensitive job-ID globs; default is every registered job")
    parser.add_argument("--source-pairing", action="append", choices=list(SOURCE_PAIRINGS),
                        help="Append an explicitly reviewed historical model pairing; existing default jobs remain")
    parser.add_argument("--comparison-scope", action="append", choices=list(COMPARISON_SCOPES),
                        help="Select a reviewed scope: st1-mechanics/st2-mechanics/st3-mechanics/st4-mechanics/st4-native/st5-mechanics select physical comparisons instead of archive ledgers; sa7-documented replaces the fore-wing input; other scopes append supplemental outputs")
    parser.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
        return
    if args.workers < 1 or args.timeout_seconds <= 0:
        parser.error("Provide positive --workers and --timeout-seconds")
    if args.comparison_scope and {'st1-mechanics','st2-mechanics','st3-mechanics','st4-mechanics','st4-native','st5-mechanics'} & set(args.comparison_scope) and args.workers != 1:
        parser.error("Structural mechanics scopes use one worker with bounded serial jobs")
    if args.max_new_jobs is not None and args.max_new_jobs < 1:
        parser.error("Provide a positive --max-new-jobs")
    from isae_acceptance import reference_acceptance_policy
    try:
        acceptance = reference_acceptance_policy(relative_tolerance=args.relative_tolerance)
    except ValueError as exc:
        parser.error(str(exc))
    if args.resume and args.output_dir is None:
        parser.error("--resume requires an explicit --output-dir")
    if len(set(args.adapters)) != len(args.adapters):
        parser.error("An adapter can only be selected once")
    if args.output_dir is None:
        args.output_dir = ROOT / "artifacts/isae" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    print("Checking the complete ISAE source catalog...", flush=True)
    from isae_suite_catalog import build_catalog
    catalog = build_catalog(ROOT)
    print(f"Source catalog recorded in {time.monotonic() - started:.2f} s "
          f"({len(catalog['cases'])} families).", flush=True)
    options = {}
    if args.source_pairing:
        options['source_pairings'] = args.source_pairing
    if args.comparison_scope:
        options['comparison_scopes'] = args.comparison_scope
    registered_jobs = plan_jobs(ROOT, args.adapters, **options)
    if set(j["case_id"] for j in registered_jobs) - set(c["id"] for c in catalog["cases"]):
        raise ValueError("An adapter names a family absent from the pinned inventory")
    jobs = select_jobs(registered_jobs, catalog, args.cases, args.job_pattern)
    plan = {"format": "openswing-isae-suite-plan", "version": 2,
            "reference_acceptance": acceptance,
            "runtime": {"python": platform.python_version(),
                        **{name: importlib.metadata.version(name) for name in ("numpy", "scipy")}},
            "verified_registered_upstream_inputs": verify_registered_upstream_inputs(ROOT, jobs, catalog["revision"]),
            "execution_policy": {"adapters": args.adapters, "workers": args.workers,
                                 "cases": args.cases, "job_patterns": args.job_pattern,
                                 "timeout_seconds": args.timeout_seconds, "kill_grace_seconds": 5,
                                 "thread_limits": {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}},
            "selection_scope": {"registered_jobs_in_requested_adapters": len(registered_jobs),
                                "selected_jobs": len(jobs), "omitted_jobs_in_requested_adapters": len(registered_jobs)-len(jobs),
                                "families_without_selected_jobs": [case['id'] for case in catalog['cases']
                                    if case['id'] not in {job['case_id'] for job in jobs}],
                                "definition": "Execution selection only; the full original catalog is retained and omitted jobs are not validated."},
            "catalog": catalog, "jobs": jobs, "code_sha256": code_pins(ROOT, args.adapters)}
    if args.source_pairing:
        plan["execution_policy"]["source_pairings"] = args.source_pairing
        plan["selection_scope"]["historical_pairing_note"] = (
            "Supplemental historical model comparisons reuse existing archived targets. "
            "They neither replace current-file jobs nor add independent native target cells.")
    if args.comparison_scope:
        plan['execution_policy']['comparison_scopes'] = args.comparison_scope
        plan['selection_scope']['supplemental_scope_note'] = (
            'Explicit supplemental comparisons have separate conditional ledgers. '
            'Baseline targets, historical results and whole-family qualifications are retained; '
            'alternative settings do not add independent native reference cells.')
        if 'st1-mechanics' in args.comparison_scope:
            plan['selection_scope']['st1_scope_note'] = (
                'ST-1 mechanics selects 201 static plus 22 modal observables instead of the overlapping '
                '200-slot archive ledger. The legacy ledger remains available without this scope. '
                'Unloaded baselines and mesh repeats receive no extra reference votes.')
        if 'st2-mechanics' in args.comparison_scope:
            plan['selection_scope']['st2_scope_note'] = (
                'ST-2 mechanics selects 77 static ordinates plus 14 modal frequencies instead of the '
                'overlapping 490-slot archive. Static tip-pylon reconstruction remains explicit; '
                'modal files are literal. Every child solve is bounded and serial; unloaded states '
                'and mesh repeats receive no extra reference votes.')
        if 'st3-mechanics' in args.comparison_scope:
            plan['selection_scope']['st3_scope_note'] = (
                'ST-3 mechanics selects all 86 published static ordinates and nine modal cells, '
                'replacing overlapping historical ST-3 jobs. Two clipped static references stay '
                'unavailable. Signed script loads and torque-axis scaling remain explicit; '
                'both meshes are required and add no extra votes. Each child is bounded and serial.')
    if args.comparison_scope and {'st4-mechanics', 'st4-native'} & set(args.comparison_scope):
        plan['selection_scope']['st4_scope_note'] = ('ST4 paper72 and direct-native31 scopes overlap; select one. '
            'Original inputs, fixed vacuum with zero gravity, both meshes required; no native mode-identity or airflow claim. '
            'Children use one BLAS thread and512MiB/15CPU/25wall limits.')
    if args.comparison_scope and 'st5-mechanics' in args.comparison_scope:
        plan['selection_scope']['st5_scope_note'] = ('16 original static cases, 16,688 distinct structural values; '
            'native comparison at archived stations plus five physical states and final 0.1% convergence. '
            'The explicit allowance adds printed precision to the relative tolerance. '
            'Historical display/modal evidence remains separate; all children are bounded and serial.')
    path = directory / "plan.json"
    validate_resume_plan(path, plan, args.resume)
    if not path.exists():
        write_json(path, plan)
    write_json(directory / "catalog.json", catalog)
    for name in plan["code_sha256"]:
        destination = directory / "frozen-code" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes((ROOT / name).read_bytes())
    print(f"Evidence directory: {directory}", flush=True)
    print(f"{len(catalog['cases'])} families, {len(jobs)} planned archived-output jobs", flush=True)
    if args.plan_only:
        return
    results = {}
    if args.resume:
        for job in jobs:
            key = hashlib.sha256(job["id"].encode()).hexdigest()[:20]
            result_path = directory / "jobs" / key / "result.json"
            request_path = result_path.with_name("request.json")
            if result_path.exists() and request_path.exists():
                packet = json.loads(request_path.read_text())
                result = json.loads(result_path.read_text())
                if packet != {"job": job, "code_sha256": plan["code_sha256"]}:
                    raise ValueError("Saved job identity differs")
                complete = (result.get("execution_completed") is True and
                            (result.get("process_reaped") is True or
                             (result.get("execution_kind") == "inline_blocker_validation"
                              and result.get("subprocess_started") is False)))
                if result.get("job_id") != job["id"] or not complete:
                    raise ValueError("Saved result is incomplete or has a different identity")
                results[job["id"]] = checked_result(job, result)
    batch = None
    try:
        batch = asyncio.run(execute(plan, directory, args, results))
    finally:
        data = report(plan, results, ROOT, time.monotonic() - started)
        if batch is not None:
            data["execution_batch"] = batch
        write_json(directory / "report.json", data)
        (directory / "report.md").write_text(markdown(data))
    print(json.dumps({k: data[k] for k in ["status", "case_families", "jobs_planned", "jobs_finished", "job_status_counts", "case_status_counts", "seconds"]}), flush=True)
    # A useful red regression signal must not become a process success merely
    # because comparisons and unimplemented families were recorded correctly.
    raise SystemExit(0 if data["full_suite_validated"] and data["current_code_unchanged"] else 1)


if __name__ == "__main__":
    main()
