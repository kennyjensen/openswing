# AE-4: prescribed acceleration versus fixed frame

Six new equation checks pass. For a stationary, nonrotating operating point
with all six accelerations prescribed as zero, retaining the twelve global
kinematic states **does not change the wing's nonzero eigenvalues**. It adds
coordinate integrators. This explains a possible source of extra near-zero
roots without explaining the slow nonzero pole discrepancy at 103 m/s.

The physical and frame equations have a block-triangular descriptor pencil:

```text
A_aug = [ A_wing   C ]       M_aug = [ M_wing   0 ]
        [   0     A_f ]               [   0    M_f ]
```

In inertial Cartesian coordinates, the frame equations are `dv/dt = 0`,
`domega/dt = 0`, `dp/dt = v`, and `dtheta/dt = omega`. Their generator has
rank six and square zero, giving twelve zero eigenvalues in six integrator
chains. The determinant therefore contains a zero-root factor of degree
twelve, while the nonzero wing spectrum is retained. Unresolved or defective
zero roots can be sensitive numerically; this does not authenticate any
particular tiny root in an archived export.

The new [tests](../../tests/test_prescribed_frame_spectrum.py) use actual
production fixed/prescribed matrix assembly on a flexible, massive wing in
free air, at two Earth attitudes. They verify identical physical blocks,
vanishing lower-left coupling, nonzero upper-right aerodynamic/mechanical
coupling, agreement with an independent inertial-coordinate generator, and
the original full-pencil residuals of lifted finite wing modes. No synthetic
zero modes are appended to an aircraft result.

This conclusion applies to the stated prescribed-acceleration constraints.
It does not cover force-controlled free/mixed motion, rotating bases,
feedback, or unknown historical settings. The wall-contact frame derivative
extension remains unimplemented and was not bypassed. The mathematical
block argument is independent of the aerodynamic upper-right block, but
the tests themselves are free-air tests, not a completed wall-frame solve.

Drela's steady technical description Eq.178 and the user guide's unsteady
constraint equations motivate this distinction. `% D` in the AE-4 driver
still means exit the constraint editor, not select anchored defaults.
The 103 m/s nonzero discrepancy should therefore remain focused on spatial
discretization and other physical/setup differences; changing fixed to
prescribed acceleration alone cannot repair it under these assumptions.

The first test attempt used three intervals, below the public four-interval
minimum. Its six fixture errors are retained; the corrected four-interval
run passes all six tests. Production equations and ISAE pass counts are
unchanged.

- [Passing test log](../../artifacts/isae/ae4-constraints-20261105/tests-frame-final.log)
- [Initial fixture errors](../../artifacts/isae/ae4-constraints-20261105/tests-frame.log)
- [Previous full-spectrum investigation](isae-ae4-spectrum-20261105.md)
