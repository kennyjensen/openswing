# SA-12 examples in the workbench

The **ISAE aerodynamics** example group now contains both original SA-12 inputs:

- **SA-12 ground effect · plain wing** — [ASW file](../../examples/isae-sa12-plain-wing.asw)
- **SA-12 ground effect · equivalent slotted flap** — [ASW file](../../examples/isae-sa12-slotted-flap.asw)

The files are byte-for-byte copies of the ISAE repository inputs. The second
model represents the fixed 40° slotted flap through section incidence, lift
slope, maximum lift and drag; it remains a single rectangular lifting surface.
No hinged or separately meshed flap has been added.

Selecting an example loads its geometry through the existing example loader.
Selection alone does **not** apply a reference run preset: airspeed, angle of attack,
influence freezing and ground settings retain their current values. The input's
`Ground` record is a structural support, not the aerodynamic image switch.

To reproduce the reviewed closest-ground setup, select either SA-12 example
and click **Apply SA-12 baseline** below the example note. Review Settings,
then click **Run analysis**. The button applies the appropriate column below,
including the mesh and solid-ground switch. It clears previous operating
constraints, loaded-equilibrium input, control deflections and rotation/
acceleration inputs; it disables gusts and influence freezing. It does not
change the ASW text or run a solve. The resulting case can be saved using the
ordinary project controls. Apply or reload pending editor/mesh/property drafts
before using the button.

## Reproduce the reviewed baseline setup

These settings reproduce the declared reconstruction used in the
[six-state pilot](isae-sa12-current-pilot-20261109.md), not a recovered historical
ASWING setup. Use **Rigid steady aerodynamics**, natural-v1 interpolation,
100 cosine intervals and pointwise circulation (zero Fourier modes). Disable
**Freeze aerodynamic influences (K/F)**. Keep stall enabled with strength 40
and transition width 0.05, and the usual wake-core ratio 0.25.

| Setting | Plain wing sample | Equivalent slotted-flap sample |
|---|---:|---:|
| Airspeed | 35.76 m/s | 35.76 m/s |
| Alpha | 8° | 0° |
| Beta | 0° | 0° |
| Specified density | 1.2256 kg/m³ | 1.2256 kg/m³ |
| Specified PG Mach | 0 | 0 |
| Image surface | Solid ground | Solid ground |
| Earth ground normal | (0, 0, 1) | (0, 0, 1) |
| Body origin in Earth axes | (0, 0, 0.127) m | (0, 0, 0.127) m |
| Attitude: bank, elevation, heading | (0, 8, 0)° | (0, 0, 0)° |

Use zero body rotation rates and accelerations, no gust, zero controls, and no
loaded equilibrium or operating constraints. Height 0.127 m corresponds to
h/c=0.5 at the quarter chord. The other reviewed heights are 0.508 m (h/c=2)
and 1000 m (the archive's nominal infinity, with images still enabled).
Keep pitch equal to alpha for this wind-parallel reconstruction.

After solving, enable **Horseshoes** in the aircraft plot. Real bound lines
and wakes are cyan/violet; reflected image lines and wakes are amber/rose.
The ground grid and image geometry make the chosen orientation inspectable.
The image overlay is drawing-only and does not change forces or circulation.

The original scripts do not record numerical Euler attitude or the initial
K/F state. The [image-wake investigation](isae-sa12-flap-image-wake-20261109.md)
retains that ambiguity. The plain-wing close-ground sample still has a
33.72% raw-CD error against the archive; availability in the example menu
does not imply that SA-12 is validated.

## Provenance and checks

Source revision: `f62943df20e9e4d7d9f50e070477b22426b5f865`, case
`SA - 12 - A-B - Ground Effect on a Wing with Plain and Slotted Flaps - Lift and Drag`,
under `Aswing_Simulations` in the [ISAE validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865).
The [authoritative reference index](aswing-authoritative-references.md),
checksummed catalog and [SA-12 source audit](isae-sa12-sources.md) govern the setup.
Jan Part I p.38 and Figure 23 p.40 describe the equivalent section model.

| Original filename | Bytes | SHA-256 |
|---|---:|---|
| `Rectangular_Wing_No_flap.asw` | 4,353 | `ea09c3c5ad7e3595caaf11a863dbddc9bb909d0cbd4c45fcd46bd3865a92fe94` |
| `Rectangular_Wing_flap.asw` | 4,340 | `b41e9d0e926313ebd41e591ccec1bee2f02a06347178d9125444629875a5a55a` |

The `examples/` and `public/examples/` copies are checked against the pinned
original sources. The existing packaging script copies these ordinary examples
for future builds.

The [preset implementation](../../web/sa12-baseline.js) is checked against the
two closest-ground jobs in the immutable six-state pilot plan. **10 JavaScript
checks pass**, covering both presets, exact model copies, prior-workspace
immutability, removal of interfering inputs, valid project round trips and the
existing project checks. The button uses the common case loader, with its
validation and rollback path. New buttons add no serialized settings fields.
All **141 production solver source hashes** still match that pilot.

The [verification receipt](../../artifacts/isae/sa12-baseline-button-20261109/receipt.json)
records these checks and the two JavaScript syntax checks. Browser loading,
button execution and the packaged build have not been rerun under the current
resource hold. No new solve, reference pass, denominator or progress observation
is implied by the preset feature.
