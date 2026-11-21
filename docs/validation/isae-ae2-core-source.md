# AE-2 sensor/core source review

**No different numeric core default or sensor self-core rule was found.** The available primary material supports W = 0.25 and a spacing **lower bound**, giving 0.035 m for the retained AE-2 fine meshes. It does not establish the core policy used by the historical ASWING executable for this tip-mounted sensor. No physics or production change follows.

The literal `[03_90].asw` sensor is attached to beam 1 at t = 0.558, with position `(0.07,0,0.558)`, Vspec along +x and Aspec along +z (lines 16–18). Beam 1 has no explicit physical index, so the documented default is physical index 1. The Xax multiplier is zero, making the jig reference axis the leading edge despite the unscaled table entries being 0.5. Chord is 0.14 m. The frozen tip bound-vortex endpoint is therefore `(0.035,0,0.558)` with a +x trailing leg: the jig sensor lies exactly on that filament. This remains an invalid location for a zero-core substitution.

The four original uncoupled scripts set the ground, mounted constraints, beta and IAS sweep, then export the sensor channels. None enters the K menu or reads settings explicitly. No `.set` file occurs in the archived AE-2 subtree. Startup nevertheless reads a same-basename settings file if present on the producing machine, and the option menu is saved there. Absence from the archive cannot establish the original K/W, K/F or K/K values. See `[0_90]_3s_A5.sh`, lines 2–68, and the [Drela user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt), local lines 1574–1581 and 2270.

## What the primary documents establish

- The user-guide K menu example has W = 0.2500; its K/W section recommends 0.25 and explicitly gives `core = max(W*chord, interval_width)` (local lines 2255, 2443–2454). Steady theory Eq161 gives the corresponding regularized Biot–Savart integral. It does not publish a distinct sensor core value. [Steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
- The physical-index rule assigns zero core to **mutual lattice influences** of beams representing the same physical surface. It does not explicitly say that a sensor inherits the anchor beam's lattice receiver identity (user-guide lines 1017–1054). The [version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt), v5.56, repeat this restricted scope. Sensor induced-flow capability was added separately in v5.55.
- Sensors sample local flow, including induced velocity from all surfaces and volumes. The [FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt), local lines 289–298, specifically describes trailing-vortex velocity at a near-tip sensor. Wholesale omission of the sensor's own lifting surface is therefore unsupported. Pylon attachment fixes motion and axes; it is not documented as an instruction to exclude that surface. [Unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf), §10.3–10.4, Eqs97–107.
- The user guide's broad statement that core size has no effect for a single surface occurs in the discussion of interacting lifting surfaces. Because the sensor treatment is unspecified and a sensor can lie in the wake, this sentence does not prove a zero-core rule for every sensor output. It is an ambiguity to resolve against implementation evidence, not grounds to suppress the existing finite core.

The [2025 extended manual](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf#page=24), printed p24, explicitly calls W = 0.25 the default. Its accompanying smaller-node-spacing wording conflicts with Drela's maximum rule and with the same manual's reproduced official appendix (local lines 4952–4976). Its p24 K/K description as an Earth/body inertial-data switch also conflicts with Drela's v5.77 notes. These summary inconsistencies should not define new physics. The local text and live parsed PDF agree; screenshot verification was unavailable and is not claimed.

## K/K does not explain the retained difference

Drela's v5.77 notes define K/K as full versus kinematic-only sensor V/alpha/beta, not an axis-basis change. Applying that documented alternative to the retained stationary states requires only the saved sensor triad and kinematic velocity:

| Nominal mesh | Kinematic-only V (m/s) | Kinematic-only beta (deg) |
|---:|---:|---:|
| 80 | 10.0000000000 | 5.58051076680 |
| 160 | 10.0000000000 | 5.58053453268 |
| Archived target | 10.0115 | 6.27943 |

At nominal 160 this increases the beta deficit to 0.69889547°, versus 0.13759837° with full flow. It cannot explain the archived result under the retained state and declared U = 10 m/s conditions. This arithmetic does not recover unknown historical atmosphere or state. The literal A axis is not leaned, so the separate v5.77 leaned-axis bug fix is also inapplicable to its specified jig axes.

## Bounded next discriminator

No source supports selecting a different numeric W and calling it the historical default. Do not fit W to the archived speed/beta or adopt the contradictory minimum rule.

If quantitative prioritization is needed, the defensible next field-only check is the **analytic derivative at the documented W = 0.25**, using the existing saved Gamma and jig receiver. Differentiate Eq161 with respect to core, retain bound/wake and physical/image contributions, and compare Gauss64/128 at nominal 80/160. This is four derivative products, no new equilibria, no alternative core values, and no inverse fit to the archive. It can show whether and how a core-policy difference changes the two observables, but cannot identify the original sensor routine or justify a default change. The unexecuted protocol is `candidate-test.json`.

A conclusive historical-policy check would need the producing sensor/induced-field routine or original executable output under explicitly logged K/W, K/K and K/F settings, using nonsingular sensor positions. Such evidence is unavailable in the reviewed archive. No request for an executable is required to retain this limitation honestly.

`review.json` pins 20 primary/current/saved files and records two saved-vector transforms. New field products, residual calls and equilibrium solves: **zero**. `record.py` completed directly with exit 0, terminal `77d531`; no persistent owner session exists.
