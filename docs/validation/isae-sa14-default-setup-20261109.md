# SA-14: startup-setting audit, follow-up deferred

The user selected SA-13 on 2026-11-09 while a small SA-14 follow-up was in
progress. One of six planned jobs had completed; **the other five were not
started**. No SA-14 sweep remains running. Its primary result stays the
historical **115/360 at 3%**, pending a complete current rerun.

The three original SA-14 polar drivers contain no `F` command and one `K/M`
toggle, with no paired `.set` files. Drela's original user manual shows frozen
influences enabled in the operating menu, and explains that `M` toggles fixed
PG Mach to flight-speed Mach (local `reference/aswing_doc.txt`, lines 2243–2255,
2293–2312 and 2409–2429). Steady theory §4.6, Eqs.176–177, describes freezing
both vortex and volume influence coefficients at zero angles.

The SA-14 adapter now reconstructs that documented startup as frozen influences
with automatic Mach. Its earlier hard-coded current influences/fixed Mach zero
were not established by those drivers. This is a documented-startup
interpretation; the exact historical ISAE executable startup remains unknown.
The parser requires the reviewed menu paths and rejects added/missing toggles.
Thirteen focused adapter checks passed; no production equation changed.

Only the 64-interval wing/body state at 5° was run: CL **0.3262858293** versus
archived **0.328182**, an error of **−0.57778%**. It is numerically valid and
passes the 5% gate. It cannot establish a family pass or update the historical
total. All 360 required slots, including 128 slots for unconverged native rows,
remain in the adapter plan.

The [six-point plan](../../artifacts/isae/sa14-default-setup-20261109/plan.json),
[single completed result](../../artifacts/isae/sa14-default-setup-20261109/job-00/accepted-result.json)
and [deferral record](../../artifacts/isae/sa14-default-setup-20261109/deferred.json)
preserve the partial work. The result took 0.160 s after imports and used
205,500 KiB peak RSS under the serial 512 MiB / 15 CPU-second / 25 wall-second
caps. Browser and build testing remain under the existing hold.
