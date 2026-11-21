# FFWT-1 circulation refinement and endpoint behavior

Refining the panel mesh does not repair the low-mode Fourier results in the
[preceding diagnostic](isae-ffwt1-circulation-modes.md). Local velocities grow
near the internal beam junctions until the subsonic-validity guard rejects
the calculation. An independent decomposition identifies the adjacent tip
beam as the dominant source of that growth in the saved states.

Full-basis controls closely reproduce the pointwise loads, but strict
convergence and independent-replay failures remain recorded separately.
This is not an experimental validation pass. Production source, defaults and
the app release are unchanged. ISAE coverage remains **17 partial / 24
pending / 0 fully validated**, with FFWT-1 pending.

## Declared controls and outcomes

Fifteen new native circulation solve attempts use the same three previously
computed poses at 8.779176°, 11.923603° and 30.263890°. The rigid reconstructed
model, level body, 22 m/s flow, section properties and frozen influences are
unchanged. There are no outer hinge solves and no new hinge equilibria.

| Block | Requested intervals, main/tips | Circulation representation | Cases |
| --- | --- | --- | ---: |
| Coarse full | 100/40/40 | Actual full 102/41/41 modes | 3 |
| Fine pointwise | 200/80/80 | One value per actual panel | 3 |
| Fine full | 200/80/80 | Actual full 202/81/81 modes | 3 |
| Fine fixed modes | 200/80/80 | 8/4/4 modes | 3 |
| Finer fixed modes | 400/160/160 | 8/4/4 modes | 3 |

Full-basis and pointwise cases must satisfy both projected and local
normalized residuals at **1e−12**. Truncated cases retain the same projected
requirement; their local defects are reported separately. The native solver's
ordinary 1e−8 reported-convergence threshold is not the study's acceptance
threshold. All fifteen slots were declared before execution.

The native run returns eleven circulation states: nine meet their declared
gates and two fail strict requirements. Four attempts raise the existing
local Mach guard and return no circulation arrays. Eleven additional
supplied-state sensor evaluations are counted separately. The timed native
loop is 23.089 seconds, including geometry exports, sensor postprocessing and
recording but excluding imports and provenance checks; this is not a browser
or coupled-equilibrium timing.

## Refinement of the fixed 8/4/4 space

The table gives maximum section-normal Mach. Coarse values are reused from
the preceding diagnostic, not new solve attempts.

| Incidence | 100/40/40 | 200/80/80 | 400/160/160 |
| --- | ---: | ---: | ---: |
| 8.779176° | 0.412412 | 0.854883 | 1.741614 — rejected |
| 11.923603° | 0.473534 | 0.984668 | 2.008124 — rejected |
| 30.263890° | 0.489814 | 1.005343 — rejected | 2.038791 — rejected |

At 11.923603°, the local normalized residual grows from 14.2091 to 30.0864
between the coarse and fine meshes, while the fine projected residual is
3.90e−16. Lift changes from 29.245508 N to 33.495394 N. A small projected
residual does not establish a converged local flow or load distribution.

The fine 8.779176° state additionally misses its strict projected requirement
(1.09436e−12). Its recorded fields remain available for diagnostics, with
that failure retained. Nothing is inferred about unavailable circulation
arrays in the four Mach-rejected attempts.

## Full-coordinate controls

The full sine basis spans every sampled circulation value when its sampling
matrix is invertible. This is a coordinate-equivalence control, not a test
of spectral convergence or proof that a nonlinear root is unique.

Five of six native pointwise/full-basis comparisons meet the declared native
residual gates and agreement bounds. The coarse 8.779176° full-basis case
fails: its projected residual is 1.22266e−12 and its local residual is
2.13057e−11. Its close force agreement does not make it an accepted control.

At fixed poses, the fine pointwise lift values are 14.415277 N, 17.714532 N
and 19.901928 N. Each changes by less than 0.000158 N from the corresponding
coarse pointwise value. These two meshes do not establish a continuum limit
or explain the archived ASWING lift discrepancy.

Independent replay of all eleven returned states passes 587 predeclared
arithmetic comparisons, but only seven states meet the independent strict
residual gates. It preserves the two native failures and adds failures for
the fine 11.923603° pointwise and full-basis states. Their independent local
residuals are 1.15604e−12 and 1.35132e−12, respectively. The corresponding
native full-basis comparison therefore remains qualified by these independent
failures. Arithmetic agreement within its separate comparison tolerance
does not waive the 1e−12 equation requirement.

An 80-decimal-digit audit evaluates four selected panels from these two
states, preserving their saved circulation and using both stored geometry
paths. At the two disputed panels, normalized residuals are 7.92032e−13 and
9.82272e−13. The difference between the rounded geometry paths contributes
only about 1.85e−19 there; evaluation arithmetic explains these sampled gate
crossings. All eight sampled paths meet the unchanged local requirement.
This does not certify the unsampled residual vector or projected residuals,
so the original full-state outcomes remain unchanged. The initial missing
library startup failure is retained; the completed audit uses the previously
pinned mpmath wheel without changing production dependencies.

A separate saved-data review passes 570 checks of the fifteen attempts,
thirty event records, eleven sensor replays, representation sizes, comparison
bounds and failure accounting. No review changes a circulation vector.

## Source of the endpoint velocity growth

For a fixed sine series, a nonzero leading endpoint slope produces
circulation proportional to the square root of distance from that endpoint.
That fact alone does not prove divergent own-beam velocity: cancellation
between trailing-vortex contributions must be retained.

An independent split-wing toy passes 111 checks, including zero-leading-slope
and continuous-wing controls. It shows that an adjacent beam's square-root
onset can produce velocity proportional to the cosine mesh count at the
neighboring endpoint sample. The own-beam contribution stays bounded in the
matched control. Both special bounded controls are retained rather than
generalizing from the divergent example.

The follow-up decomposition checks five actual saved low-mode states using
the exact scalar reduction for their straight, common-plane frozen vortex
geometry. At the first main-beam panel and 8.779176°:

| Vertical induced velocity contribution | Coarse, m/s | Fine, m/s |
| --- | ---: | ---: |
| Adjacent port tip | +144.480274 | +295.682714 |
| Main beam | −9.230862 | −9.019113 |
| Distant starboard tip | +0.004702 | +0.004658 |
| Total | +135.254114 | +286.668259 |

At 11.923603°, the adjacent-tip contribution similarly rises from
165.523742 to 339.967895 m/s. The scalar decomposition reproduces the saved
velocity components within 5.69e−14 m/s. The unfitted endpoint asymptotic
prediction differs by about 9% on the coarse grid and 4.4% on the fine grid.
This quantitatively supports adjacent-endpoint interaction as the source of
the observed growth. A solved continuum limit still depends on how the
circulation coefficients behave under further refinement; it is not proved
by two returned meshes.

## Remaining work

The tested low-mode representation is unsuitable for this split-beam case
under the demonstrated refinement. A physically justified treatment of
circulation across connected beam pieces must be checked against pointwise
and independent references, with mode count and quadrature varied separately.
Original ASWING's Fourier coordinate grouping remains unproven, so a new
continuous-surface representation would be an explicit model choice until
its correspondence is established. The existing validity guard remains active.

The archived producing setup, physical flexible fixture and flow,
updated-influence limitations, dynamics and the other pending ISAE families
also remain unresolved. No original ASWING executable is available.

The [recorded-result index](isae-ffwt1-circulation-refinement.json),
[selected evidence archive](isae-ffwt1-circulation-refinement-evidence.zip)
and [verification receipt](isae-ffwt1-circulation-refinement-evidence.json)
retain the outcomes, independent checks and failed cases. Index reproduction
and archive byte checks do not claim a historical scientific rerun or an app
build.
