# AE-1: completion of saved evidence after the worker deadline

On 2026-11-10, `AE-1-a05-row024-m80-frozen` (5°, 23 m/s, nominal mesh 80) terminated with SIGALRM, return code −14. Its original terminal receipt is retained unchanged. The cold solve, independent restored residual and all 29 physical checks had already been written successfully. Both residuals are 2.437803977579608e−14. The missing output was the final adapter bookkeeping, not the physical solution.

The new saved-data finalizer verified the original canonical request, model and current kernel hashes; complete raw file set; convergence and residual evidence; independent strip wrenches and root clamp; both operating setups; sensor geometry; and cold/restored sensor parity. It then applied the existing adapter contract and unchanged 5% reference allowance. All six reference channels pass. This performed **zero additional solves or residual evaluations** and imported no production modules.

Incomplete evidence is not eligible. Seven focused tests pass: a complete-record control and rejection of changed sensor geometry, detached restored residual, missing physical check, altered request, changed strip force and missing fresh-residual call. No time, memory, equation or accuracy gate was relaxed.

The original plan, failed worker receipt and raw numerical results are immutable. An explicit finalization plan hashes them before the audit; a verification receipt binds the newly completed strict/policy metadata to those originals. Original numerical timing and RSS were not saved before termination, so the new receipt leaves them **unavailable**, rather than attributing metadata-audit time to a solve. The prior timeout remains a reported execution event.

An explicitly pinned continuation plan allows the supervisor to recognize this verified completion. It retains the original worker for new jobs, the same one-thread/512 MiB/15 CPU-second/25-second elapsed limits, and two-job serial batches. Unreviewed failures or partial records still stop the supervisor. Neither a missing observation nor a timer expiration triggers an automatic numerical retry.

The first continuation batch completes two fresh states and all twelve sensor comparisons, proving that the full original sweep can resume without rewriting its failed terminal record. Later batches retain their own receipts. The acceptance scope remains all 1,200 original comparisons; this bookkeeping change adds no independent native targets.

Evidence:

- [Original terminal](../../artifacts/isae/ae1-full-current-20261110/AE-1-a05-row024-m80-frozen/terminal.json)
- [Finalization plan](../../artifacts/isae/ae1-full-current-20261110/AE-1-a05-row024-m80-frozen/finalization/plan.json)
- [Verification and hashes](../../artifacts/isae/ae1-full-current-20261110/AE-1-a05-row024-m80-frozen/finalization/verification.json)
- [Seven regression checks](../../artifacts/isae/ae1-full-current-20261110/AE-1-a05-row024-m80-frozen/finalization/tests.xml)
- [Continuation plan](../../artifacts/isae/ae1-full-current-20261110/continuation-plan-0001.json)
- [First successful continuation batch](../../artifacts/isae/ae1-full-current-20261110/continuation-batches/0001.json)
