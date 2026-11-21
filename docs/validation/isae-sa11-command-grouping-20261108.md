# SA-11: surface grouping and archived command audit

2026-11-08 UTC. This source audit finds no documented basis for merging
connected logical beams into one Fourier domain. It also finds inconsistent
compressibility command sequences among the archived drivers. Neither finding
supplies a solver repair or an authenticated native startup state. **SA-11
remains 163/4,592 at 5%.** SA-2 stall-region work remains deferred.

## Three different meanings of grouping

| Mechanism | Primary evidence | Consequence for SA-11 |
|---|---|---|
| Structural beam group | Drela steady description §3.8, p. 29: joints couple independently factored beam matrices through global variables. | Structural connectivity does not establish a single aerodynamic basis or coincident vortex endpoints. |
| Shared physical index | User Guide, “Physical index”; version 5.56 revision note. | Turns off the finite core in mutual vortex influences. Both sources explicitly use wing/winglet and T-tail examples. This agrees with the current zero mutual core for the supplied SA-11 indices. |
| Common loading-plot coordinate | Version 5.75 revision note. | Adjacent endpoints with a common physical index are displayed together. This is stated as a plotting change; it is not evidence of a merged circulation domain. |

Sources: [Drela steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf#page=29),
[User Guide](../../reference/aswing_doc.txt:1009),
[retained revision notes](../../reference/version_notes.txt:390), and
[official revision notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt).

The User Guide explicitly warns that zero mutual core can cause numerical
noise when one beam's trailing legs approach another beam's control points.
The [retained field checks](isae-sa11-winglet-current-wind-20261108.md) identify
such close interactions in SA-11. The warning supports investigating the
junction geometry and evaluation points; it does not prescribe an additional
core, a merged basis, or a local-Mach limiter.

ISAE Part I §3.5, equations 18 and 23, pp. 18–20 assigns coefficients and a
mode count to each lifting surface. The extended manual §1.3.5, Figure 1.13,
p. 21 displays modes for an individual named beam. Neither source explicitly
maps a branched set of logical beams sharing a physical index to a single
Fourier coordinate. Thus the exact native domain remains unverified. The
existing per-logical-beam implementation is not proven wrong by this audit,
and the [pointwise failures](isae-sa11-practical-resolution-20261108.md) remain
independent of that Fourier-domain question.

## Archived driver differences

All 17 shell files in the pinned SA-11 directory were read as data, never
executed. The 16 configuration-specific drivers have these commands after
the angle sequence and before `xx`:

| Configuration | Label 0.70, 240 m/s | Label 0.75, 255 m/s | Label 0.78, 266 m/s | Label 0.80, 272 m/s |
|---|---|---|---|---|
| Wing alone | `kk`, `mm` | absent | absent | `kk`, `mm` |
| Wing extension | `kk`, `mm` | absent | absent | `kk`, `mm` |
| Upper winglet | `kk`, `mm` | absent | absent | `kk`, `mm` |
| Upper and lower winglets | `kk`, `mm` | `kk`, `mm` | `kk`, `mm` | `kk`, `mm` |

The additional `Wing_tip_up/wing_alone_polar_Ma_0_80.sh` also omits both
commands. In total, ten scripts contain the pair and seven omit it. This is
a source inventory, not a new comparison scope. None of the 17 scripts
explicitly selects `F`, `NODE`, or `SGET`; no `.set`, `.pnt`, or `.con`
sidecar is present in the case directory.

The [User Guide](../../reference/aswing_doc.txt:2238) documents `K` as the
options submenu and, within it, `M` as the toggle between specified PG Mach
and `V/a`. Its example shows specified PG Mach zero and frozen influences
enabled. The [extended manual](../../reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf#page=24)
also documents that Mach choice. These descriptions do not authenticate
the doubled `kk`/`mm` interpretation or the original process startup state.
In particular, omission does **not** prove PG was off: settings can be loaded
at startup. The report's explicit statement that PG was enabled remains
separate evidence, recorded in the [source audit](isae-sa11-sources.md).

The retained 16 output tables contain speed and flow angles but no PG-Mach,
freeze-state, mesh, or mode-count column. Consequently, they do not resolve
these omissions directly. The differences strengthen the need to recover
the producing setup; they do not justify silently changing the registered
conditions or assigning an exact native mode count.

## Result and next focus

This audit narrows the connected-surface hypothesis: a combined loading
plot and a structural joint are insufficient reasons to merge circulation
domains. It also prevents treating all SA-11 scripts as the same startup
protocol. No new physical solves were warranted by these findings.

The next useful work remains the upper-winglet junction's local velocity
and force/moment treatment at the documented low-angle condition. Keep the
[report-versus-file twist conflict](isae-sa11-winglet-polar-20261108.md)
explicit: the report-derived sign gives native AVL lift/CDi errors below
0.561%/0.332% across 21 angles, while OpenSwing still rejects the local Mach.
This is useful agreement in loading, not completed validation.

[Audit evidence](../../artifacts/isae/sa11-command-grouping-20261108/audit.json)
records source hashes, script line numbers, full command text, sidecar search,
output-column inventories and the unchanged status fractions. Production
equations, original models, retained numerical evidence and tracked scopes
are unchanged. No completion observation is added because no fraction or
tracked scope changes.
