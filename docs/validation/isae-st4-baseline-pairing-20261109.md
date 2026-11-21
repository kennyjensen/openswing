# ST-4 unloaded-input pairing note

The retained `W0M.asw` does **not** provide a different distributed inertia from
`Weight7a/WING.asw`. A read-only comparison verifies the original archive hashes
and all 20 parsed beam distributions, including the identical 0.0078 kg m
`mgcc/g` value. Their reference data and non-Weight records also match.

The original `W0M.asw` lacks its final Beam `End`. The comparison appends that
terminator to an explicitly derived string in memory; the original file is
unchanged. Both files have two physically null Weight objects: one zeros the
weight scale, the other zeros the individual masses. Their different attachment
coordinates therefore add no loads or inertia under the documented point-mass
equations. No physical system was constructed and no solver ran.

`Simulation_files/Flutter_analysis.sh` directly names `W0M`, while the root
`vaccum.sh` names the unavailable `W0.asw`. This confirms a driver/input pairing
for `W0M`; it does not establish which input generated the report's unloaded
Table 6 row. Changing to the retained `W0M` would not test a lower-inertia
baseline hypothesis. A different source-backed input would be needed for that.

The stopped ST-4 numerical study, its partial results, original inputs and all
accepted comparison fractions remain unchanged. This note is preparation for
later work, not a new ST-4 validation result.

[Checksummed source comparison](../../artifacts/isae/st4-baseline-pairing-20261109/report.json)
· [audit script](../../artifacts/isae/st4-baseline-pairing-20261109/audit.py).
