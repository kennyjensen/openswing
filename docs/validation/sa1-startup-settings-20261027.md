# SA1 startup settings: primary-source clarification

**No numerical setting change is justified by this audit.** The retained `mach=0`, `freeze_influences=False`, stall factor 40 and transition width .05 remain qualified reconstruction choices. No solve, parameter fit or implementation edit was performed. [JSON evidence and source pins](sa1-startup-settings-20261027.json).

The frozen [source-readiness report](isae-sa1-source-readiness-20261027/report.md), line 53, says the guide displays `fast = T` “as a default.” **This attribution is superseded: the guide displays a menu example, and no F startup default is authenticated.** The [guide](../../.reference/aswing_doc.txt), lines 2236–2270, shows `fast = T`; lines 2293–2306 define F as a toggle. In contrast, lines 2335–2338 explicitly guarantee that the separate L flag starts True and is not saved in `.set`. The original SA1 driver, lines 9–14, performs one K/F toggle. The example therefore cannot prove its resulting F state.

The guide identifies itself as **5.97** at line 2. The [steady theory](../../.reference/asw_theory.txt), lines 3–5, identifies **5.99**, dated 10 March 2015. Its lines 2085–2102 recommend approximately `Ks = 40` and `Δcl = .05`. The [revision notes](../../.reference/version_notes.txt), lines 1008–1061, list no stall-constant change from 5.96 through 5.99 and its addendum. This is evidence against claiming a documented version-specific stall change; it does not authenticate the compiled constants in the archived 5.96 run. No alternative constants are established.

| Setting | Exact primary evidence | Consequence |
|---|---|---|
| PG Mach versus actual Mach | Guide 2413–2429 distinguishes fixed `M_PGspec` from `V/a` and permits fixed zero below approximately Mach .3. Version notes 604 separately name actual Mach and Mach_PG. | A nonzero airspeed does not contradict the current PG setting of zero. The native table records neither Mach. |
| Local section moment PG | Guide 2431–2434 makes local-normal-Mach scaling independent of AIC PG; literal model 79–82 has section `Cm = 0`. | This distinction does not establish a missing SA1 section-moment correction. |
| NODE request/defaults | Version notes 448–475 report a circulation-default fix without numeric defaults; 591–598 define the NODE/I node request. Driver 3–5 explicitly requests 200. | The completed metadata correction stands. No new evidence selects 199 intervals, a numeric K, or a spacing law. |

The originals were rechecked against the pinned archive manifest. Their hashes match. The audit neither alters frozen reports nor attributes the archived result to an unrecorded graphics mode, startup state or executable build.
