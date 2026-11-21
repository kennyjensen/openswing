# SA-11: finite surface forces when section moments are undefined

2026-11-08 UTC. The browser's local-Mach rejection panel now displays the
already calculated lifting-surface forces. This follows the user's question
about removing the [blanket analysis stop](isae-sa11-local-mach-limit-20261108.md).
It makes partial lift/drag information inspectable without inventing a section
moment or accepting an incomplete equilibrium.

**These are rejected-state diagnostics, not validated aircraft coefficients.**
The SA-11 primary comparison stays **163/9,184 at 5%**. No physical equation,
vortex, Mach threshold, source model, comparison denominator or tolerance changes.
Native ASWING's limiting/failure behavior remains unknown.

## Scope and presentation

Drela's steady Eqs. 67 and 70 supply the existing circulatory lift and profile
force arrays. The code also retains its already evaluated circulation-rate force.
Their evaluation precedes the singular section-moment correction in Eq. 73.
The [authoritative reference index](aswing-authoritative-references.md) and
catalog remain the governing source basis.

The new observer sums those existing arrays and projects them onto the flight
lift/drag/side axes. It performs no new flow calculation, influence assembly or
physical solve. It exports body-force vectors, wind axes, dynamic pressure and
reference area. Circulatory, circulation-rate and profile contributions remain
separate, including the profile force's lift projection.

Per-beam sums and a subtotal of the Mach-invalid strips remain included in the
overall sum; they are not extra forces. **Apparent mass, body loads, point-object
drag, engine loads and all section moments are excluded.** This is not a
Trefftz-CDi calculation. Coefficients use `q*Sref`, with flight dynamic pressure;
zero normalization preserves dimensional forces and shows coefficients as
unavailable. Nonfinite/overflowing diagnostic sums are withheld.

The panel is under the aircraft in Plots, with the force disclosure open by
default. **Download diagnostic JSON** includes the force budget, rejected
sections, exact request and kernel provenance. Normal aircraft result fields
and exports remain unavailable. The error envelope contains no `result` or
`equilibrium_state`, and a coupled residual cannot consume it as valid loads.
The exception text now identifies the undefined *section pitching-moment
correction* more precisely. No Mach clamp or replacement moment is introduced.

## Actual bundled example

Use the existing Joint-corrected **+4° upper-winglet example**, 240 m/s, alpha
1°, beta 0°, frozen influences, global PG `240/340.21`, density 1.2256,
reference area 0.9329, and 12 requested intervals per beam. Required breaks
produce 18 main-wing strips and 12 on each winglet. This is distinct from the
report-minus4/native-endpoint studies and the archived original input.

| Surface contribution | Diagnostic CL | Diagnostic near-field CD |
|---|---:|---:|
| Circulatory | 0.3511817234 | 0.0017640513 |
| Circulation rate | 0 | 0 |
| Profile | −0.0002966767 | 0.0072201138 |
| Sum | **0.3508850467** | **0.0089841651** |
| Two Mach-invalid strips, already included | 0.0009085974 | −0.0009368269 |

Both root samples still reach **M_perp = 1.1009181721**. The Python diagnostic
run has circulation residual **4.933e-16**, but that does not supply the missing
moment. The invalid strips are retained in the force sums; none is removed to
make a coefficient agree.

## Verification

**26 Python checks, 4 JavaScript checks and 1 actual-worker browser workflow
pass**, all run serially with one BLAS thread. The browser check completes in
53.35 seconds including startup. Desktop and mobile screenshots were inspected.

Python checks cover signed projections, per-beam/rejected-strip accounting,
coordinate rotations, consistent force-unit changes, unavailable normalization,
nonfinite handling and immutable inputs. A separate equation control changes
only sound speed while retaining fixed global PG, prescribed circulation,
geometry, rates and gust. The rejected force sums equal the valid control's
forces minus apparent mass for both frozen/current influences and both ordinary
and coupled-load evaluation paths. This deliberate control is not a proposed
physical repair of SA-11.

A complete accepted 30 m/s SA-11 result was retained **before** the edit and
recomputed afterward with the same request. The entire result is exactly equal.
Browser/Python rejected force budgets agree within **4.37e-18 in coefficient**
and **1.82e-12 in body-force components**. The 141 browser kernel module hashes
match the current files. The UI test checks visible force values, partial-result
labels, JSON scope, disabled normal exports and equilibrium use, mobile overflow,
clearing on edits, and recovery to an accepted low-speed solve.

Evidence: [verification receipt](../../artifacts/isae/sa11-partial-forces-20261108/verification.json),
[Python log](../../artifacts/isae/sa11-partial-forces-20261108/tests.log),
[browser report](../../artifacts/isae/sa11-partial-forces-20261108/browser.json),
[Python rejected-state record](../../artifacts/isae/sa11-partial-forces-20261108/rejected-native.json).
The same directory retains before/after accepted results, the JavaScript log,
desktop/mobile screenshots and browser diagnostic JSON. These are development
server checks, not a new packaged-release audit.

The observer changes the kernel fingerprint, so unfinished equilibrium
checkpoints from the preceding kernel retain the existing intentional
version/context rejection on resume. This does not alter archived results or
rewrite previous evidence.
