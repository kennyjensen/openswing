# SA-8: no alternative input recovered from public history

2026-10-31. The SA-8 model, driver and native-output files are unchanged
throughout the inspected public history, including their earlier directory
paths. This investigation does not recover a different fore-wing model to
explain the total-drag discrepancy.

The GitHub API returns 14 reachable commits for `main` at the retained
[f62943df20e9 revision](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/f62943df20e9e4d7d9f50e070477b22426b5f865).
All 14 recursive trees were fetched and checked for truncation. Thirteen
contain the full-aircraft and fore-only `.asw`, `.sh` and `.txt` files;
the earliest tree predates their import. The six corresponding Git blob
identities are the same in all 13 populated trees and match the bytes used
in the current comparisons: **78 file-identity checks**.

The current-path histories of the fore-only model, driver and output each
point to [a58ec61bbafb](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/a58ec61bbafb22f9915ed4188b34bc35727e05bc).
Inspecting earlier trees is necessary: they contain the same bytes under
earlier paths. There is no alternate model hidden by that path change.

No ASWING `.set` or `.def` file is recovered. Two older case layouts contain
`xfoil.def`; its inspected contents specify XFOIL panel distribution,
plotting, Mach/Reynolds and transition settings. The named global defaults
files `aswing.def`, `aswing.set`, `asw.def` and `asw.set` are absent.
This cannot recover defaults from the authors'
working directory, uncommitted changes or inputs predating the import. It
does **not** prove that the stored native outputs were generated from the
stored deck.

The adjacent `NACA4309_POLARS.txt` is an XFOIL section polar, not an
alternative ASWING deck or aircraft result. Its blob is also unchanged
across the 13 populated trees. Neither retained model nor driver explicitly
references that file.

The [source-history report](../../artifacts/isae/sa8-source-history-20261031/report.md),
[verified tree/file comparison](../../artifacts/isae/sa8-source-history-20261031/analysis.json),
and [receipt](../../artifacts/isae/sa8-source-history-20261031/receipt.json)
retain API responses, URLs, hashes, paths and commit identities. No solver
call, input correction, target change or registered acceptance gain results
from this audit.

SA-8's isolated-wing diagnostic therefore remains **212/252** at strength 20.
Its failed fine-mesh total-drag errors remain median **11.29%**, maximum
**15.66%**; every other archived output passes under that separately qualified
setup. Resolving the native total-drag definition or producing setup remains
necessary.
