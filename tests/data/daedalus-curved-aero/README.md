# Actual loaded Daedalus geometric maps

The inputs come from the published corrected-mesh C16 cruise project and its
saved rudder response at 1 Hz and 1.15737773741517 Hz. All four lifting surfaces
(wing, stabilizer, rudder and fairing) are retained: 82 panels and 86 receiving
nodes. The file retains the real and imaginary parts of both complete saved
2044-coordinate harmonic directions.

`expected.npz` contains 110 arrays generated independently by
`scripts/daedalus_curved_aero_reference.py`: one base and four derivatives, each
with 22 complete geometry, vortex-velocity and nodal-transfer outputs. Expected
derivatives use 32-point filament quadrature and complex-step width `1e-24`.
The source study separately checked quadrature 16/32, complex steps
`1e-24`/`1e-20`, and two native fourth-order widths. `provenance.json` binds
each expected array's source file and the independent saved-data audit.

The regression restores the current public equilibrium, evaluates production
maps, and compares every component against these fixed expectations using
`atol=rtol=2e-8`. It performs no trim, linearization or harmonic solve.

The captured strip loads contain the actual base's volume flow, propulsive
jet, stall and other aerodynamic terms, but are held fixed when testing their
**geometric transfer**. Their physical laws and derivatives are not validated
by this fixture. Vortex-only fields are compared separately from those other
flow fields. Material interpolation, complete aircraft dynamics and historical
ASWING agreement remain outside this test.
