# Sparse derivative RHS refinement

The R3 candidate reproduces the independently refined 320-interval state and p-wrench results while retaining the three failures against the older dense outputs. This is an intentional arithmetic accuracy change. The exact physical Jacobian, input partials and checked/analytic circulation columns remain unchanged. The full 640 comparison remains unavailable because an existing input limit rejected its node list before any physical evaluation.

The implementation applies exactly two compensated original-J residual corrections using the same certified sparse factor. It retains every centered probe, the default full API step 1e-5, original branch checks, full equation gate 1e-8 and rank threshold 1e-10. Unsupported arithmetic or an inconclusive certificate uses the original dense fallback. Guarded FMA/fsum is not a universal correctly rounded residual certificate.

| Completed scope | Result |
| --- | --- |
| New native arithmetic/API controls | 31/31 pass |
| Existing derivative/feedback/cache regressions | 48/48 pass |
| Portable staged tests | 50/50 pass; simulated missing-FMA fallback included |
| Actual Pyodide | 22 helper tests and 4 derivative cases pass; 1,336 physical matrix values compared |
| Actual browser | 1 test covering 2 current/frozen mounted cases passes; exact 109-module worker |

These scopes overlap and are not a unique-test total. The portable suite ran on a runtime with FMA; it does not establish an end-to-end Python 3.12 result. Actual Pyodide compared both sparse cases under the original 2e-8 absolute/relative gate and reproduced both dense-fallback matrices exactly. The browser evidence covers a small isolated offline app, exports, rank-bound display and section plots.

The matched 320 call passed its 39/39 execution guards. The saved audit passed 246/246 declared accuracy checks while retaining one failed aggregate old-output comparison, so its total remains 246/247. All 8,344 state-response entries agree with the fixed second correction accumulated independently at 113-bit precision, under 1e-13 absolute plus 1e-12 relative; the maximum difference is 1.5643085e-32. All 18 p-wrench entries are bit-identical to the separately completed refined output replay. Neither reference was selected by matching the old outputs.

All 81,703 old physical values were still compared at 2e-8 absolute plus 2e-8 relative. The three p/body-z force entries remain **FAIL**, with maximum tolerance fraction 1.096695605. The new values are about 5.7–5.9e-12; the old values are about 2.194e-8. Near-zero symmetry is descriptive, not an acceptance oracle. Every other old physical comparison passes. The control coefficient changes by only 1.3580283e-14 per file flap setting, below its unchanged 3.3513017e-09 gate.

The matched call used 4,172 unknowns and retained 123,455 Jacobian nonzeros as explicit CSC arrays. Its fresh pre/post physical residuals are zero in saved floating-point results. The ordinary full linear residual decreased from 2.0968782e-12 to 2.3847591e-13; both are below the unchanged 1e-8 gate. The reported rank value is a conservative lower bound, 1.4013596e-09, with exact rcond null. Exactly two corrections and 8,355 derivative residual evaluations were retained. The derivative took 110.81s; observed process peak was 192,212 KiB. These single measurements, taken with other work running, are not a speedup benchmark.

The attempted 640 run **failed before physics evaluation**: the existing explicit-node parser accepts at most 513 stations and rejected the prepared 641-node list. One constructor was attempted; no network was returned, no residual or derivative was evaluated, and no 640 coefficient exists. The child exited 1 and was reaped after 8.3986s. The full-mesh comparison is unavailable, not a numerical PASS or FAIL. The original fine-denominator 1% criterion remains unchanged. A separately proposed R4 correction to that input limit is outside this completed R3 evidence.

The prepared full refinement splits every 320 interval at its saved actual Glauert sample, preserving all old nodes, root, endpoints and control boundaries. It specifies 641 nodes, 640 intervals and an expected 8,332 unknowns. The planned conditions are the same fresh literal zero state, gravity convention, fixed-acceleration standard/stability derivatives and control.1,p parameters. This large stage completed one 320 derivative and no equilibrium or finite-control solves. Its completed saved audit used only one signed and one absolute sparse matrix product, with two RHS, and no factorization, solve or physics evaluation.

The five earlier 1% mesh failures remain 2.0773%, 7.1435%, 3.4688%, 4.1729% and 6.3620%. No convergence order, pure aerodynamic/structural error attribution or experimental agreement follows. The historical nonlinear-control checks apply to 320, and 640 needs its own consistency checks. ISAE coverage remains **17 partial, 24 pending, 0 fully validated**; AE-3 remains pending. No original ASWING executable is available.

ROOT source and the public kernel remain the prior 108-module version at this completed R3 study snapshot. The isolated 109-module candidate is not installed or deployed; any promotion must have a separate receipt. The preparation-only inherited nested-plan pin failure is preserved and corrected transparently; the old physical/parity failures are untouched.

See the [earlier sparse investigation](derivative-sparse-investigation.md), [machine-readable report](derivative-sparse-refinement.json), and [verified evidence archive](derivative-sparse-refinement-20261024-evidence.zip).
