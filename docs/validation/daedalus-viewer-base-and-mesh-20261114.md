# Daedalus viewer: starting flight condition and chord-line spacing

The Bode viewer now reports the saved base's motion status, reference airspeed,
weight and flight-path angle above the response selectors. These values come
from the computed base, not the current settings or selected forcing amplitude.
A fixed aircraft is not labeled as trimmed just because its motion is zero.
The existing `kinematically_steady` flag is used without a new threshold; its
true value does not by itself establish straight, level flight. Weight is
physical mass times actual gravity, not the lift-target multiplier. Missing
quantities remain absent rather than inferred.

## Saved comparison rechecked

A small bounded job restores the accepted source-equation/SEGSPL state on its
preserved mesh and evaluates the current residual and output recovery. No trim,
linearization or harmonic solve runs. It confirms zero flight path and attitude
rates, a kinematically steady base and a full residual below 1e-9. The summary is:

> Base motion: steady in the recorded flight frame. Reference airspeed 21.982
> ft/s · Weight 233.3 lb · Flight path 0°.

The wing tips remain **8.04855 and 8.05318 ft** above the loaded root. This
establishes the declared comparison's starting state, not the user's browser
state or the GIF's operating point. Selecting the aircraft and Free flight in
the app does not reproduce this trim automatically. The existing untrimmed
Daedalus fixture correctly displays an accelerating base.

[Current base extraction](../../artifacts/daedalus-base-condition-20261114/level-base/result.json),
[display fixture](../../artifacts/daedalus-base-condition-20261114/level-base/display-fixture.json),
[driver](../../scripts/check_daedalus_base_condition.py).
The [weight audit](daedalus-paper-properties-20261114.md) and
[paper shape comparison](daedalus-wing-paper-20261113.md) retain the differences
between the public input, historical paper and measured aircraft.

## Why chord lines are uneven

The counts in this audit describe the prior fresh-import default. The user's
subsequent request is implemented in the
[new Daedalus default mesh](daedalus-default-mesh-20261114.md).

Both renderers draw panel boundaries from the analysis geometry, with no
independent uniform resampling of chord lines. The default mesh uses cosine
spacing in material arc length, then inserts exact required stations. Thus
the requested interval count need not equal the displayed count.

A mesh-only check of the current public file gives:

| Wing setting | Actual intervals | Smallest interval [ft] | Largest interval [ft] |
| --- | ---: | ---: | ---: |
| 16 cosine intervals | 28 | 0.49602 | 8.48605 |
| 48 cosine intervals, current default count | 58 | 0.10091 | 3.66258 |
| 48 uniform intervals | 50 | 0.58000 | 2.33333 |

The uniform option still retains required stations, including the ±55.42 ft
chord break near the tips. It is available under **Beam nodes → Distribution →
Uniform in arc length** (under **Editor** on mobile). Applying it changes the
computational mesh and invalidates prior results; it is not a cosmetic setting.

The authoritative index and source catalog were consulted. The original
ASWING manual's **Considerations for Data Discontinuities** lists the default
`KBREAK` properties and explicitly discusses irregular node spacing.
OpenSwing preserves additional physical breaks. On this wing, **±7 and ±49 ft**
are inserted for `GJ` alone, beyond the documented native default list and
without another attachment at those stations. Other breaks coincide with
documented geometry/incidence breaks or brace attachments. This is a concrete
discretization difference, not a recovered native GIF mesh.

The GIF's node count, placement and exact local adjustment algorithm remain
unknown. Its projected chord spacing cannot establish uniform material
spacing. No rendering resampling, physics, default or mesh policy was changed
to make its appearance match. The documented native break handling and node
relocation deserve a separate comparison before a policy change.

[Mesh summary](../../artifacts/daedalus-mesh-spacing-20261114/current-mesh/result.json),
[complete stations and reasons](../../artifacts/daedalus-mesh-spacing-20261114/current-mesh/cases.json),
[mesh-only driver](../../scripts/check_daedalus_mesh_spacing.py).

## Cabin and tail follow-up

The application default is **48 intervals per beam**, not 48 for the whole
aircraft and not a span-dependent allocation. A fresh import without per-beam
overrides therefore puts almost as many chord lines on the 5.6 ft-tall fairing
as on the 112 ft wing. These are analysis stations, not physical aircraft ribs.
The current public input models the fairing as a lifting plate with `chord`
and `dCLda` tables, so it follows the same display rule as the tails.

| Component | Requested intervals | Actual intervals | Unique stations |
| --- | ---: | ---: | ---: |
| Wing | 48 | 58 | 59 |
| Horizontal tail | 48 | 50 | 51 |
| Vertical tail | 48 | 50 | 51 |
| Tail boom | 48 | 53 | 54 |
| Cabin fairing | 48 | 50 | 51 |

For lifting surfaces, each unique station supplies a chord boundary (adjacent
panel edges overlap). The boom instead has a 12-sided circular display section
at each station, so its visible edges also include tube rings and longitudinal
lines. The GIF visibly uses coarser cabin and tail strip drawings, but no exact
native counts or per-beam meshing settings have been recovered. The `.asw`
geometry alone does not prescribe these mesh counts. Saved OpenSwing projects
can also differ from the fresh-import defaults above.

Each component already has independent count and spacing controls under
**Beam nodes → Beam → Distribution → Intervals**. Applying them changes the
analysis mesh and requires a new solution; an aesthetic count match would not
by itself establish dynamic accuracy. No defaults or drawing density were
changed. The small serial mesh-only job used 2.322 CPU seconds, 7.071 wall
seconds and 80,008 KiB peak RSS; it exited successfully, was reaped and kept
all pinned inputs unchanged.

[Component results](../../artifacts/daedalus-component-mesh-20261114/current-defaults/result.json),
[station tables](../../artifacts/daedalus-component-mesh-20261114/current-defaults/cases.json),
[execution receipt](../../artifacts/daedalus-component-mesh-20261114/current-defaults/terminal.json),
[driver](../../scripts/check_daedalus_component_mesh.py).

## Checks and limits

Both small serial jobs succeeded and were reaped, with all inputs unchanged.
Peak RSS was below 90 MiB and maximum CPU time was 3.336 s, under the existing
512 MiB / 15 CPU s / 25 wall s caps. The actual JavaScript helper and eight
focused tests pass **47 assertions** in a V8 isolate, including the fresh
trimmed fixture, saved fixed/free cases, zero gravity, gravity override,
missing mass and the distinction between weight and lift-target multiplier.
The Bode module parses and the existing server serves the updated modules.
The first standalone syntax-check attempt failed to strip an existing module
re-export; correcting that checker required no application change.

[Verification](../../artifacts/daedalus-base-condition-20261114/verification.json),
[JavaScript checks](../../artifacts/daedalus-base-condition-20261114/javascript-checks.json).
Browser integration expectations were updated but remain unexecuted under the
browser/build hold. No browser job or watcher was started. ISAE fractions,
scope and progress history are unchanged. The Daedalus Bode mismatch remains
open; this work adds no native comparison passes.
