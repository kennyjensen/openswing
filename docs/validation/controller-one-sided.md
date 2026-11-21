# Recorded controller ambiguity at a clipping boundary

The failure below retains its original 58-module source and results. The later
[bounded original-residual diagnostic](controller-nonsmooth.md) rejects this
example and prevents retrying past a discovered ambiguity. General nonsmooth
uniqueness remains unresolved; the historical run is not relabeled as a pass.

A physical counterexample shows why checking a centered tangent is insufficient
for general nonsmooth controller authority. This is a recorded failure, not a
passing physical validation.

The fixture is the original OpenSwing guided rigid body: mass 1 kg, no
aerodynamic surface or volume, zero gravity, and a unit +x thrust actuator.
The implicit controller equation is:

```
E1 - clip(E1, 0, 1) = 0
```

At E1=0, the full cold and time-step equations have a one-sided solution family.
Increasing force and acceleration together by 0.3 in SI units preserves every
cold equation exactly. Applying the corresponding BDF1 velocity and position
increments preserves every step equation to 2.276e-16. A negative force change
violates the controller equation, with scaled residual 0.00244898.

The tested source is the isolated four-file controller rank correction, based on
the accepted-Newton/checkpoint-corrected main kernel. Both cold initialization
and the BDF step request the final rank check. Both centered tangents appear
regular, and the public solve accepts one step without rejection. This confirms
that extending the existing rank check to controllers does not resolve this
switching-boundary failure.

The solve uses panels=4, duration=dt=0.02 and the unmodified production retry
policy. An observer records actual Newton arguments and returned values, probes
the independent force family, then restores accepted-state residual/cache data.
It does not replace Newton's returned solution. The single attempted solve
completed with child exit zero and unchanged source/fixture/script pins. The
wrapper elapsed time was approximately 15.6 seconds.

The [evidence archive](controller-one-sided-evidence.zip) retains the exact 58
source modules, fixture, plan, observer, full output, terminal records and a
standard-library verifier. SHA-256:
`ded10450488d431a776086733848a943d282eaee5688a62110c1b482ac059596`.
The verifier checks retained bytes and the reproduction gates; it does not
rerun the numerical solve or establish a remedy. Historical absolute paths are
provenance.

Further work must distinguish true actuator ambiguity from a valid unique
saturation or anti-windup trajectory. Rejecting all nonsmooth expression syntax
or requiring equal left/right slopes would exclude valid dynamics. General
branch-aware certification remains unfinished, as do broader controller and
aircraft validation. No broad ASWING requirement is closed by this diagnostic.
