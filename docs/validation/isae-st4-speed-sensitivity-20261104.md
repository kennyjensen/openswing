# ST-4 local speed sensitivity

The small difference in computed static divergence speeds accounts, to first
order, for **99.85%** of the near-zero pole difference between OpenSwing N160
and the fine independent reference. It accounts for **99.86%** of that pole's
N128→N160 change. It predicts the wrong sign for the other unresolved damping
component. The two failed comparisons therefore have different explanations.
No corrected pole replaces a computed result, and all existing comparison
scores and gates remain unchanged.

At 139.5 m/s the saved full descriptor pairs are checked against their original
A/M before probing fresh nonlinear equations. For `A v = lambda M v`,

```text
d(lambda)/dU = w^H (A_U - lambda M_U) v / (w^H M v)
```

Centered physical-state/rate probes form the complete A/M actions. Speed
half-widths are 0.03, 0.01 and 0.003 m/s; the final speed pair also repeats with
state width 3e-6 instead of 1e-5. Each complex direction is probed through real
states. Both componentwise derivative-convergence checks pass the predeclared
`1e-7 + 1e-4*abs(derivative)` allowance. All seven restored physical bases pass;
the anchor residual is 4.59e-16. The coordinate scales can depend on speed:
their derivative terms cancel in this left/right projection at an exact pair.
The unchanged anchor chart is verified against saved matrix actions.

| Native archive ordinal | OpenSwing pole at 139.5 m/s | Local derivative with speed |
|---|---|---|
| 3 | +0.0343997064 /s | +0.6225491204 /m |
| 6 | -1.3070942788 + 182.8723020905 i /s | +0.1521114138 - 0.2803008457 i /m |

The previously verified critical speeds are 139.4457094284 m/s (N128),
139.4447794796 m/s (N160), and 139.4432301014 m/s (fine reference).
The table tests the local hypothesis
`delta(lambda) = -lambda_U * delta(U_critical)`, relative to N160.
This is a sensitivity diagnostic, not an independently solved corrected mode.

| Comparison target | Ordinal | Actual real-pole difference (/s) | Critical-shift prediction (/s) | Unexplained remainder (/s) |
|---|---:|---:|---:|---:|
| n128 | 3 | -0.0005797659 | -0.0005789388 | -0.0000008271 |
| n128 | 6 | +0.0011841833 | -0.0001414558 | +0.0013256391 |
| a768_s512 | 3 | +0.0009659987 | +0.0009645640 | +0.0000014347 |
| a768_s512 | 6 | -0.0020953731 | +0.0002356781 | -0.0023310512 |

For the slow pole, a 0.00155 m/s critical-speed difference produces nearly the
entire 0.000966 /s modal difference. Its apparently large 2.731% relative error
is amplified by being very close to zero. This observation does not waive the
0.1% modal-component gate. For ordinal 6, the predicted damping change has the
opposite sign: a critical-speed shift cannot explain that discrepancy.
Further spatial refinement remains necessary, and the native ASWING mismatch
is unresolved.

The one serial job uses 151 fresh residual evaluations, 58.48 recorded seconds
and 151.5 MiB peak RSS. It performs no equilibrium solve, Jacobian assembly or
eigensolve. The limits remain one BLAS thread, 90 seconds and 512 MiB address
space. Production kernels and the verified browser build are unchanged.

[Portable evidence](isae-st4-speed-sensitivity-20261104.json) retains derivatives,
widths, gates and source hashes. Full action vectors are in
`artifacts/isae/st4-speed-sensitivity-20261104/physical/actions.npz`.
The runner is `scripts/verify-isae-st4-speed-sensitivity.py`.
