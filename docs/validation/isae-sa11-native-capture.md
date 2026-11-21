# SA-11: minimal native ASWING reference capture

The active investigation is **SA-11 before stall**. SA-2 stall-region work
remains deferred. This package prepares a reference run; it contains **no new
native results** and changes no comparison fractions or production equations.

The [latest saved-field audit](isae-sa11-whole-beam-wake-20261108.md) finds
close CL/CD/CDi/efficiency on the disclosed report-minus4 alternative, but all
21 complete states reject local Mach at the winglet roots. The next useful
native evidence is the actual node/receiver placement, settings and section
quantities at 0° and 1°, rather than another integrated polar alone.

Generate the portable package from the repository root:

```sh
python3 scripts/prepare-sa11-native-capture.py --out /tmp/sa11-native-capture
```

The destination must not exist. The script performs no solver runs or network
requests. It verifies the archived sources against the retained upstream
manifest, includes their hashes and exact differences, and creates a ZIP next
to the directory. The generated `README.md` is the standalone capture protocol.

Prepared 2026-11-08: [portable ZIP](../../artifacts/isae/sa11-native-capture-20261108.zip),
[capture instructions](../../artifacts/isae/sa11-native-capture-20261108/README.md),
[verification](../../artifacts/isae/sa11-native-capture-20261108-verification.json).
All 12 packaged files match their hashes and ZIP copies; 66 parsed beam
distributions match the bundled Joint correction and intended twist alternative.
The original input is byte-identical. These checks validate package preparation,
not native command execution or aerodynamic predictions. No native run occurred.

## Inputs kept separate

| Directory | Input | Question |
|---|---|---|
| `original` | Byte-identical archived `wingtip_up.asw`, including its Joint multiplier row and +4° twist | Does native ASWING accept it, and what joint locations does it actually read? |
| `joint-only` | Same model, with only the Joint multiplier row corrected to `0.1 0.1` | Does the explicit station scaling change native interpretation? |
| `report-minus4` | Joint correction plus the four upper-winglet twist values changed from +4° to −4° | Does the report-derived sign explain the archived loading? |

The original driver and output table remain unmodified in `source/`. The
two-angle proposed command deck retains the driver's setup and `kk`/`mm`
tokens, whose exact effects must be recorded from native menus. It omits the
other 39 requested angles and uses a separate output filename. It is **not a
verified native automation script** and must be stepped through while checking
prompts. Each model requires a separate clean process and directory.

## Reference basis and limits

Consult the [authoritative index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json). Jan Part I Appendix D,
pp. 65–68, Fig. 40 supplies the −4° alternative; it does not prove which input
generated the archived table. Drela's user documentation describes automatic
loading of `.set`, `.pnt`, `.con` at startup, `SSAV`/`PSAV`, and displayed
variables `V`/`D`. An interpolation increment of zero requests actual structural
nodes. Derived section quantities occupy interval midpoints but are printed
half an interval earlier, beside node values: do not equate their positions.

The [MIT distribution page](https://web.mit.edu/drela/Public/web/aswing/)
provides public references/examples and licensing information. Its linked
[installation repository](https://github.com/LeonardoAVONI/91_ASWING_Public)
does not include the proprietary ASWING code. No working native ASWING is
available in this workspace. The
[official FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt)
explains that `.set`/`.pnt` are version/build-dependent memory dumps. Preserve
native sidecars and executable identity together; do not synthesize them.

A new run with fresh defaults cannot establish the historical startup state.
Keep original ASWING, the executable used at ISAE, and any later modified code
identified separately. A failed import or solve is useful evidence and must
remain in the capture. No Mach clipping, altered core, discarded root strip
or fitted section input is part of this protocol.
