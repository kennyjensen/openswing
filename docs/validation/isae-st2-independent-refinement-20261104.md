# ST-2 upright modal refinement

**14/14 independent mode comparisons pass**: the first seven positive modes in vacuum and in still air, with unchanged 0.1% frequency/mesh gates and mode-shape assurance above 0.999. **Native ASWING agreement remains unverified; the registered ST-2 score stays 0/490.**

The original upright Pazy modal file is unchanged, including its two zero-valued Weight records at .558. It uses fixed-frame gravity [0,0,-9.81], the source endpoint-average operator, cosine meshes of nominal 160/320 intervals plus the mandatory .52 property break, and separate vacuum/still-air density 1.23 branches. These are declared conditional settings, not recovered historical settings. Each full descriptor solve retains 20 roots at shift [-.01,0], with both left and right vectors. The first seven positive roots are selected by computed frequency, with unique negative conjugates; archived target frequencies do not choose modes.

| Mode | Vacuum, N320 Hz | Reference error | Still air, N320 Hz | Reference error | Largest N160→N320 change |
|---|---:|---:|---:|---:|---:|
| OOP1 | 4.63052817 | 0.000221% | 4.59797199 | 0.000226% | 0.000574% |
| OOP2 | 29.29246575 | 0.004403% | 29.08841433 | 0.004427% | 0.013223% |
| T1 | 43.54088868 | 0.000117% | 43.44281170 | 0.000117% | 0.000566% |
| OOP3 | 81.53182901 | 0.012066% | 80.97221686 | 0.012127% | 0.036330% |
| IP1 | 128.13334402 | 0.000190% | 128.13334401 | 0.000190% | 0.000530% |
| T2 | 135.74824909 | 0.001427% | 135.38817226 | 0.001430% | 0.006116% |
| OOP4 | 158.14562575 | 0.023649% | 157.08297058 | 0.023766% | 0.071264% |

Maximum fine reference error is **0.023766%**, maximum production mesh change **0.071264%**, and maximum reference N192→N384 change **0.001917%**. The smallest shape assurance across coarse/reference, fine/reference and coarse/fine comparisons is **0.999999635**. Shape matching uses a positive mass-weighted metric and one-to-one assignment; all seven shape assignments agree with the frequency ordinals.

The independent reference imports no OpenSwing code. It integrates cubic Hermite bending in two planes and linear torsion about the common elastic/CG axis, including upright gravitational compression. Still-air kinetic energy uses μ=ρπc²/4, the 0.005 m midchord offset and J=ρπc⁴/128, following the Technical Description equations 84–85 and 248/256. The reference neglects finite axial shortening. Seven focused tests check integrated rigid-motion inertia, the zero-density limit and invalid densities.

The original uniform-grid boundary insertion produced a very short N384 cell and contaminated the first reference frequency by about 0.0133%. A mesh with two uniform material intervals removes that artifact without changing coefficients or fitting the native outputs. An earlier dense-eigensolver precision failure is also retained; symmetric shift-invert passes the same small-density continuity gate.

All four production cases pass their equilibrium, mass, gravity, clamp, global balance and all 40 original-pencil left/right residual checks. For each staged N320 calculation, the fresh mass matrix is exactly identical and all 16 full nonlinear directional checks pass. The N320 A matrix is also exactly unchanged between vacuum and still air; the fluid contribution enters M.

The fine results still pass **0/14 original printed complex-component intervals in each medium**. Vacuum frequency error against the archived file has median 0.2144% and maximum 0.6998%; still-air median is 0.1032% and maximum 0.9387%. The tiny real components retain their original absolute intervals, including widths down to 5e-22; they are neither rounded to zero nor removed. Historical medium, gravity, base, mesh and physical branch identities remain unknown. Independent continuum agreement does not establish native parity.

The initial N320 vacuum run hit its 180-second limit after saving both matrices. A resumed run completed the solve but failed while creating one large JSON string; incremental JSON export resolved that memory failure. The N320 still-air calculation deliberately saves an assembly checkpoint and finishes modes separately. These staged results are not cold end-to-end runtime benchmarks. Every numerical job ran serially with one BLAS thread and a 512 MiB address-space cap.

Remaining ST-2 scope includes the other original modal configuration, invalid active static attachment anchors, historical pairing/setup, and native complex-spectrum agreement. Production kernels and the browser bundle are unchanged by this validation increment.

Raw scripts, matrices, full modal outputs, original failed receipts and source hashes are in `artifacts/isae/st2-independent-refinement-20261104/`. The [portable evidence](isae-st2-independent-refinement-20261104.json) records every comparison.
