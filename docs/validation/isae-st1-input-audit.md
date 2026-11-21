# ST-1 literal input audit

All **10 archived ST-1 models remain rejected**, with the same errors recorded in the inventory. This parse-only audit found no documented missing input feature that warrants accepting them unchanged. ST-1 remains pending; the coverage status and counts are unchanged.

| Observed literal parse error | Files | Source location |
|---|---:|---|
| `AswError: Line 60: engine is missing End.` | 9 | Empty trailing `Engine` header at line 60, without `End` |
| `ValueError: Sensor Vspec and Aspec must not be parallel.` | 1 | `Static_deflection/[45_0]_3a.asw`, sensor row at line 57 |

Every model supplies `Vspec = Aspec = (1,1,1)` at line 57. The nine EOF errors mask this additional undefined sensor frame. Four `[0_90]` files also supply 16 scaling values at line 38 for 15 named columns including t: mesh-convergence `[0_90]_3s`, modal `[0_90]_3s` and `[0_90]_s`, and static `[0_90]_3s`. These are **masked static findings**, established by inspecting the literal text and parser source. No repaired file was parsed to infer the next exception or choose the intended multiplier mapping.

Drela's [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt) defines global blocks as ending with `End` and defines the sensor frame through `B = Aspec × Vspec`, then `A = V × B`. The exact audited local anchors are `.reference/aswing_doc.txt`, lines **154–172** and **536–552**; its SHA-256 is `703bdcdee068d25991c37225f1942452e7366d16786f3db8cbc4b934db42269a`. The cross-product definition makes the supplied parallel frame undefined. The guide documents default axes for omitted vectors; it does not establish historical executable behavior for these supplied collinear vectors or an unfinished block.

The [ISAE archive](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865) is pinned to revision `f62943df20e9e4d7d9f50e070477b22426b5f865`. Sampled scripts point to historical local binaries and select sensor output channels 28–30. Retained output has rx/ry/rz position headers, but the historical channel mapping and connection to these exact input bytes are unverified. The pinned current guide, lines **3305–3316**, lists a different channel arrangement. The actual producing ASWING version, startup/settings and permissive input behavior remain unverified; no executable is available for comparison.

Exactly ten unmodified literal parses were made against 106 frozen current source modules. All source and input pins were checked before and after execution. No equilibrium, residual, physical matrix assembly, repaired-input parse or physics comparison was performed. Ordinary parser spline construction may use internal interpolation linear algebra. The authoritative archived `corrected-report.json` clarifies an overly broad call-count label in the preserved raw report; it does not change any result or rerun a parse.

Keep the original files and rejection evidence. Any subsequent physical study needs separately identified derived inputs with reviewed block termination, sensor directions and multiplier mapping, followed by primary beam, mass, fixture, load and measurement reconstruction. Selecting the documented default sensor axes would be a derived-input decision, not proof of literal-file compatibility. No silent repair, production change, runtime bundle update or deployment was made.

[Machine-readable audit](isae-st1-input-audit.json) · [Coverage ledger](isae-coverage.md) · [Evidence archive](isae-st1-input-audit-20261024-evidence.zip)
