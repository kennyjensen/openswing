# ST-4: published node spacing and point-load audit

The newly recovered spacing prescription in Drela's 1989 paper does **not**
resolve the two sensitive 7a airflow discrepancies. Two fresh serial states
pass the discrete equation checks, but miss the archived frequency by **20.15%**
and slow-pole magnitude by **99.01%**. Production defaults and the accepted
ST-4 mechanics result remain unchanged.

## What the primary sources establish

Drela's [1989 paper](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf),
printed p. 326, Eqs. 37–38, prescribes, for `u = j/J`,

```
theta = (pi/2) * (1 - u*(1 + abs(u))/2)
s = (b/2) * cos(theta)
```

Page 327 explains the structural/aerodynamic spacing compromise and adjusts
nodes to point loads, with coincident nodes admitting a force jump. The
algorithm for those local adjustments is not supplied. The
[official manual](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
identifies this paper with **ASWING 3.x**. It does not establish a 5.x default.
The formula was visually read from PDF page 5, rather than inferred from its
incomplete extracted equation text. The
[source supplement](isae-st4-node-placement-sources-20261109.json) records the
download, checksums and version distinction.

This formula differs from pure cosine and the existing SA-2-coordinate-based
modified-cosine option. That option remains a separate source hypothesis.
No coefficient in either rule was fitted to the ST-4 eigenvalues.

The 2015 steady description, pp. 13–15, Eqs. 55–56 and Fig. 7, requires exact
concentrated-load jumps. OpenSwing uses a shared physical node and separate
adjacent-element force/moment traces, preserving the same jump without an
explicit duplicate kinematic node. The current point-pylon regression passes
independent force, moment and sided-jump checks. Thus a missing zero-length
load-jump mechanism is not supported by this audit.

The distinction also matters for counts: **40 unique physical nodes in
OpenSwing are not automatically 40 native nodes when coincident nodes are
counted separately**. The previous “40-node” comparison is a disclosed numerical
hypothesis, not an authenticated replay of the report's native mesh.

## Explicit-node comparison

The [new probe](../../scripts/verify_st4_airflow_formula.py) evaluates Eqs. 37–38
at 39 base nodes and maps them affinely into the literal straight-beam material
domain. The existing exact point-weight insertion adds one unique node. The
identity with `sin(pi*u*(1+abs(u))/4)`, symmetry, endpoints and monotonicity are
checked before the plan is frozen. The unspecified historical node-adjustment
algorithm is not invented. The source formula alone changes from the
[preceding 40-node study](isae-st4-airflow-current-20261109.md).

All original geometry, weights, stiffnesses and declared flow settings are
retained, including zero PG Mach, moving influences, pointwise circulation,
gravity, lag and the full 16-root search. Neither state is a reduced modal model.

| Grid hypothesis | Frequency at 120.5 m/s, rad/s | Error from 3.3632329 | Slow Re(λ) at 139.5 m/s, 1/s | Error from −0.088874035 |
|---|---:|---:|---:|---:|
| Cosine, preceding study | 1.71731729 | 48.9385% | +0.021353711 | 124.0269% |
| Modified cosine, preceding study | 3.41295484 | 1.4784% | −0.110757882 | 24.6234% |
| Drela 1989 Eqs. 37–38, new | 4.04098101 | 20.1517% | −0.176865780 | 99.0073% |

Other identified nonzero components in the new runs differ by at most 1.156%.
The raw component comparison is 24/30 at 5%, with four unidentified native
components retained as unavailable. This is a diagnostic alternative, not an
additional acceptance scope or a converged result. The saved-matrix assessor
now groups the explicitly named alternatives generically; the earlier assessor
version and its reports remain preserved.

Both jobs complete in 10.94–11.01 seconds under the existing one-thread,
512 MiB, 15 CPU-second and 25 wall-second child limits, peaking at 126,496 KiB
resident memory. All **96** independently recomputed left/right equation and
mass-pairing checks pass; maximum relative-action error is 2.542e−12. The
separate current point-jump regression passes in 5.41 seconds. No production
equation or default has changed.

The archived Xplot11 files inspected here are eigenvalue diagrams with partial
operating-point legends, not structural node-coordinate plots. The
[7a legend preview](../../artifacts/isae/st4-node-placement-20261109/native-7a-legend.png)
does not provide the missing node coordinates or enough labeled settings to
authenticate the startup. The original PostScript is retained; previews read
its straight stroke commands without executing the file.

The conclusion is limited: the historical 3.x formula is another demonstrably
different mesh, and switching to it would not close this comparison. Exact
native node placement remains unavailable. Further changes to physical
coefficients or default meshing are not justified by these three alternatives.
The structural paper's six source discrepancies remain separately required;
this airflow diagnostic adds no accepted passes.

[Frozen plan](../../artifacts/isae/st4-node-placement-20261109/formula1989/plan.json),
[complete comparison and matrix audit](../../artifacts/isae/st4-node-placement-20261109/formula1989/assessment.json),
[point-jump regression receipt](../../artifacts/isae/st4-node-placement-20261109/point-jump-check.xml).
