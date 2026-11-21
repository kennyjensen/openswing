# Actual Daedalus complete aerodynamic directional regression

`expected.npz` retains 23 independent map arrays for the stationary base and each of four real/imaginary saved responses at 1 Hz and 1.15737773741517 Hz. Expected values come from independent vortex quadrature, body source/doublet integration, propeller jet integration, section loads, stall leakage, and absolute local/frame kinematics. No production evaluator generated the expected loads.

`inputs.npz` retains exact saved descriptor directions, their harmonic rate directions, the unit native control.3 input in real directions only, and physical restoration guards. The portable test restores the public corrected-mesh project, then performs one baseline and sixteen prescribed-state residual evaluations. It does not retrim or solve a new response.

The comparison checks the implemented discrete aerodynamic equations at selected directions. It excludes material interpolation, the physical input chart, complete equilibrium/free-frame balance, mesh convergence, and historical ASWING parity. The selected body apparent-mass factor is 1; printed ASWING equations use 2, an already documented unresolved convention. No end closure is inferred at finite-radius body ends.

`provenance.json` pins the retained evidence and fixed componentwise gate. The first reference attempt failed on a padded Engine-record adapter before producing a complete expected value; the evidence archive preserves that failure and source correction. No gate or aircraft parameter changed.
