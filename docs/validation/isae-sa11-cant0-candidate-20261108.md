# SA-11: the separate cant0 model does not resolve the archive

2026-11-08 UTC. Two predeclared native AVL/direct OpenSwing checks do **not**
support substituting the full-scale `wingtip_up_cant0.asw` for the unresolved
upper-winglet .75/.78 archives. Its reference area matches their dimensional
normalization, but its lift, induced drag and efficiency do not jointly match.
Both OpenSwing states also reject local Mach before stall. The primary result
remains **163/9,184 at 5%**, with no input, production-equation or scope changes.

## Why this source was checked

The [preceding fixed-PG study](isae-sa11-fixed-pg-candidate-20261108.md) found
useful baseline agreement with reference dimensions and slope independently
available in this separate input. That did not identify the geometry which
produced any archived polar. The present test uses the **entire original cant0
geometry and section data**, at its original full scale, rather than selecting
individual values or fitting a parameter.

The file's reference dimensions are 97.67 m², 3.7874 m and 24.852 m. The two
winglets are vertical in front view, unlike the paired upper-winglet model's
approximately 15° cant. Their physical x–z sweep is retained. The right/left
winglet twists are +4°/−4°, while both zero-lift offsets are +4.5°. Their local
section normals point in opposite spanwise directions, so these data should
not be silently interpreted as symmetric incidence. The main-wing slope is
6.34 and its twist is 2°.

The original joint records specify winglet stations +12.426 and −12.426, outside
their domains [1.5257, 3.5577] and [−3.5577, −1.5257]. The ordinary model-meshing
path still rejects this file. **No joint record was repaired or removed.**
For this explicitly rigid aerodynamic diagnostic, beams were meshed separately
and passed directly to the production aerodynamic evaluator; structural assembly
was not tested. This is not a successful literal-model import.

The authoritative [reference index](aswing-authoritative-references.md) and
checksummed catalog were consulted. Drela's guide allows arbitrary beam parameter
`t`; here the main beam uses y, while the vertical winglets use ±z. The earlier
special-purpose mapper assumed `t=y` and cannot be reused unchanged. The new
diagnostic inverts a verified affine transverse coordinate for each beam,
retaining the original geometry and orientation. No archived driver or polar is
paired with cant0 upstream, and this study does not create such a pairing.

## Two-angle comparison

Both cases use zero global PG, true speed 255 m/s, density 1.2256, a frozen
body-x wake, standard production stall/local-Mach checks, and 64 native
one-chord-row horseshoes. Zero PG follows the separately identified .75/.78
speed-invariance hypothesis; its historical value is still unverified. Native
AVL has no profile or section-moment model here, so no total-CD or Cm match is
claimed.

| Alpha | Native CL error | Native CDi error | Native efficiency error | OpenSwing maximum normal Mach |
|---|---:|---:|---:|---:|
| 0° | +6.946% | −19.339% | +39.587% | 1.84122, rejected |
| 1° | +4.873% | −12.754% | +24.154% | 2.22353, rejected |

Errors are against the original upper .75 coefficients. Those three archived
coefficients are identical at .78 for these rows, so the coefficient comparison
is the same. Production was evaluated only at 255 m/s; no 266 m/s solve is
claimed. Lift and drag independently reproduce the source area within
0.001 m² from the raw archived dimensional columns at both speeds. This
necessary normalization agreement does not establish the producing geometry.

Both production maxima occur at the right winglet root. All strips remain
inside their lift limits, with margins of at least 17.57 transition widths.
Circulation residuals are below 1.26e-15, and production/native circulation
differences are at most **0.147%**. Native side-force coefficients are −0.006897
and −0.006757, consistent with the retained asymmetric incidence data. There
is no archived side-force column to validate them against. The local Mach
peaks are invalid discrete-model states, not physical supersonic-flow predictions;
no accepted production force totals are reported from them.

## Verification and consequence

The independent native circulation reconstruction differs by at most 8.29e-9
relative. Native body-force coefficients reconstruct from the exported fields
within 5.56e-17. OpenSwing/native source endpoints and receivers match within
3.56e-15 m. Saved production velocities reconstruct within 1.33e-12 m/s;
native velocity reconstruction differs by at most 1.41e-7 at unit speed.
Original joint errors, reference dimensions, raw target mapping and every
pinned source/artifact hash are checked by the analyzer.

Both native processes and both production calls are terminal. Aerodynamic
evaluation totals 0.131 seconds, excluding startup and source verification;
this is not browser timing. All work ran serially in the foreground with one
BLAS thread. No background solver was started.

This closes the specific **unchanged cant0 + zero-PG** candidate at these
angles; it does not rule out every undocumented historical input. Do not
reassign the upper archive to cant0 or repair its joints in the primary suite
on the strength of the matching reference area. Return to the matched .70
upper-winglet configuration, where native integrated loading already agrees
closely, and investigate its local junction evaluation and native discretization.
The separate .75/.78 producing-model uncertainty remains explicit. SA-2 and
post-stall repairs remain deferred.

Evidence: [frozen plan and source audit](../../artifacts/isae/sa11-cant0-candidate-20261108/plan.json),
[verified results](../../artifacts/isae/sa11-cant0-candidate-20261108/analysis.json),
[serial driver](../../scripts/verify-sa11-cant0-candidate.py),
[analyzer](../../scripts/analyze-sa11-cant0-candidate.py).
