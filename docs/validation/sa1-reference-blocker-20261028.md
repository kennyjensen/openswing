# SA-1 reference-parity blocker

**SA-1 is incomplete: 19/154 registered checks pass, with no complete row passing.**
All 22 baseline jobs finish. The full OpenSwing objective remains incomplete.
The user subsequently paused SA-1 and redirected work to SA-2 and later cases;
the evidence and unresolved differences below remain retained.

The resumed investigation tested the remaining concrete leads: rigid versus
mounted equilibrium, prescribed-circulation load conservation, and the script's
speed/constraint/normalization mapping. Those checks did not resolve the native
output differences. The [comparison report](sa1-differences-20261027.md) retains
the numerical results and original acceptance accounting.

Three consecutive resumed turns have encountered the same evidence limit. The
first produced useful numerical exclusions; the next two revalidated the
sources and examined remaining actions. The pre-resume blocked turns are not
part of this count. A further independent review found no new source-supported
correction or meaningful unperformed diagnostic.

The unresolved discriminator is the historical mapping from generated nodes
and circulation representation to sampled velocities and integrated loads,
including the near-stall calculation. The papers specify sampling equations
given node locations, but do not recover the original NODE allocation routine.
The archived aggregate outputs do not uniquely identify the missing mapping.
Unrelated saved settings do not establish SA-1 defaults.

This is an evidence limit, **not proof that OpenSwing has no implementation
defect**. A justified next correction needs discriminating evidence such as an
authenticated discrete algorithm, or native nodes/circulation and settings
associated with the original case. No reference executable or additional run
settings are available from the user; no repeat request was made.

The final audit rechecked 192 existing pinned files without finding changes.
A separate broad recursive scan for newer files was deliberately interrupted;
it is not evidence of an exhaustive search for new files. No numerical solve,
production equation, model parameter, target or tolerance changed in this pass.
