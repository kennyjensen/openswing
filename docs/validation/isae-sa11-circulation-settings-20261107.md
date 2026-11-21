# SA-11: explicit Fourier diagnostic settings

2026-11-07. Fixed a reproducibility bug in
[`verify-isae-sa11-circulation.py`](../../scripts/verify-isae-sa11-circulation.py).
Its requests declared `frozen=False`, but the script omitted that argument
when creating `FlightCondition`. With the current ASWING-style frozen
default, a rerun would therefore solve a different setup from the one recorded.
The script also ignored its `pg` request field.

The script now explicitly forwards both settings, rejects unknown settings,
and records the complete applied condition on computed and rejected rows.
Computed results also retain the solver's actual influence metadata and
circulation discretization. The script hash participates in its cache identity,
so the corrected script creates a distinct cache instead of reusing old rows.

The [solver-boundary reproduction](../../artifacts/isae/sa11-circulation-settings-20261107/reproduction.json)
executes the retained pre-fix script under current production defaults, stopping
before any physical solve. It observes `freeze_influences=True` for requests
declaring false and `mach=None` for a request declaring PG zero. The corrected
script forwards false and zero, respectively. This establishes a current rerun
bug; it does not determine which defaults were active when the older archived
Fourier study was generated. That archive is preserved without relabeling.

## Verification

Seven [focused checks](../../tests/test_isae_sa11_circulation_settings.py) pass
in two small serial jobs with one BLAS thread:

- Four actual SA-11 Fourier solves cover frozen/current influences and
  speed-derived/zero PG. Returned wind angles, Mach, three circulation modes,
  residuals and JSON-persisted settings are checked.
- One N100, 19-mode, 5° request is rejected by the local-Mach guard. Its retained
  velocity breakdown confirms the requested current geometry and wind direction;
  circulation converges before the physical validity rejection.
- Two malformed-setting requests fail before a solve.

This adds **no native ASWING comparison passes**. The primary SA-11 adapter
already supplied its influence setting explicitly and is unchanged. The
48-request historical Fourier report and its raw cache are not regenerated.
All 141 production Python modules and `ISAE_STATUS.md` retain their prior
hashes; the primary count remains **163/4,592**.

## Why the local-Mach guard remains

The [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
printed page 16, equation 67, evaluates the circulatory force using velocity
at the bound vortex. Page 17, equation 73, uses the local perpendicular Mach
number in the section-moment factor `1/sqrt(1-M_perp²)`. The retained SA-11
inputs have nonzero section moment coefficients. A converged circulation
residual therefore cannot make a state with `M_perp >= 1` admissible under
these real-valued equations. The guard is unchanged. This does not resolve
why the swept discrete velocity grows under refinement or establish parity
with native ASWING's force-point treatment.

[Before/after provenance](../../artifacts/isae/sa11-circulation-settings-20261107/before.json),
[computed-path test results](../../artifacts/isae/sa11-circulation-settings-20261107/settings.xml),
[rejected-path test results](../../artifacts/isae/sa11-circulation-settings-20261107/rejection.xml).
