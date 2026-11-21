# ST-3 archived-table coverage correction

The validation summarizer previously skipped the beam-root row of the archived
negative-coupling static result. A fixed zero-based slice started at line 35,
although the first data row is physical line 34. It retained 44 of 45 rows.

The reader now finds the table by its exact nine-column header, verifies its
printed moment/force exponents and separator, and parses every finite data row.
It retains the root, tip and both rows at printed t = 0.335. Malformed rows,
nonfinite numbers, unexpected layouts and descending stations are rejected.
The raw printed scales remain unchanged: Mc′ is multiplied by 10⁻²; Ms′ and Fn
are unscaled. The original model, solver and historical reports are unchanged.

**14 parser regression tests pass.** A separate 172-check source audit verifies
all 45 literal rows, exact agreement with the old 44-row table after removing
only the root, source scaling/signs, and continuity of 111 kernel modules and
six historical artifacts. The omitted root includes Mc′ = −0.0207 N m and
Ms′ = 0.694 N m; dropping it excluded a loaded boundary from the comparison.
The tests require no source download, solver import or physical calculation.

This is a reference-reader correction, not a new physical reproduction claim.
The old full-output report remains a historical 44-row comparison. Its
selected y/z/twist results do not establish the other archived outputs.

## Next complete reference comparison

Use the unchanged final `[m15_0].asw`, `temp_analysis3.sh` and `temp.txt` under
ISAE's `3 - Structure/CASE - ST3 Low aspect ratio/Static_Deflection_analysis`.
The archive has 45 rows, 44 distinct printed stations, one input-station column
and eight predicted outputs: y, z−z0, tw−tw0, Mc′, Ms′, Fn, cl and flap angle.
Do not discard the repeated station or silently interpolate across a breakpoint.

The literal signed Weight values are ±0.5451 kg, scaled by 9.81 to ±5.347431 N.
Their undeformed resultant moment is 0.74864034 N m; the loaded moment rotates
with the actual pylon positions. The archive reports zero speed and zero body
position/attitude. Preserve these loads rather than rescaling to an experimental
label. The exact producing mesh remains unavailable; printed station and output
rounding must be accounted for separately from numerical mesh convergence.

[Parser audit](isae-st3-reference-parser.json) ·
[All archived targets and source pins](isae-st3-reference-target.json) ·
[Raw evidence](isae-sa3-velocity-20261025-evidence.zip)
