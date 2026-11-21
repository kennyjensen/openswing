# SA-11: independent input availability

2026-11-08 UTC. The additional sources checked here do **not** supply an
independently authored AVL representation of the ISAE SA-11 geometry or its
missing ASWING startup settings. This closes two specific leads; it is not a
claim that no such input exists elsewhere. SA-11 remains the priority, with
SA-2 stall-region work deferred.

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed catalog were consulted. The retained downloads and their retrieval
receipts are indexed in [the source supplement](sa11-independent-input-sources-20261108.json).

## Older repository from the validation author

The author's public repository listing identifies an older
[ASWING_Experimental_Validation repository](https://github.com/rom1isae/ASWING_Experimental_Validation/tree/1306162d0b814444d6d5799c869f1e05370af0e7).
Its complete recursive tree at revision
`1306162d0b814444d6d5799c869f1e05370af0e7` contains 538 entries and is explicitly
not truncated. Every file under `1 - Aerodynamics` is a `Readme.txt`; the
`Steady/CASE - 11 Transonic flight/Readme.txt` entry is a one-byte blob.
There are no aerodynamic models, driver scripts, startup settings or AVL inputs
in this pinned tree. Structural inputs elsewhere in that repository do not
establish the SA-11 setup. This finding does not cover uninspected revisions.

## Independent AVL thesis

Uram Kim's [Numerical Analysis and Optimization of Wing-tip Designs](https://www.sjsu.edu/ae/docs/project-thesis/Uram.Kim-S15.pdf)
(San Jose State University, 2015) includes an AVL input on PDF p. 72
(printed p. 67). It describes a **Boeing 747-100**, with reference span
59.64 m, area 615 m² and Mach 0.84. The listed baseline wing has two sections.
This is a different geometry from the ISAE wind-tunnel model. Its use of a
Whitcomb airfoil does not establish identical winglet geometry or ASW-to-AVL
conversion. It supplies no direct SA-11 acceptance target or native ASWING
force-sampling convention.

## Consequence for the investigation

Further searching of this older repository's present aerodynamic placeholders
will not recover the missing setup. Retain the actual-case
[twist-sign comparison](isae-sa11-winglet-polar-20261108.md),
[curved-geometry audit](isae-sa11-curved-extension-20261108.md) and
[receiver/moment evidence](isae-sa11-moment-speed-20261108.md) as the useful
constraints. The unresolved task is the actual winglet junction's local flow
and load recovery, alongside authentication of the archived producing setup.
Agreement with a different published winglet model would not resolve that task.

No solver was run for this source check. No production equations, original
inputs, comparison scopes or completion fractions changed. The primary SA-11
result remains **163/9,184 at 5%**; no progress observation is added for this
availability finding.
