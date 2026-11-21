# SA-11 source and geometry audit

**Source audit complete; aerodynamic comparisons remain in progress. No experimental validation pass.**

The pinned ISAE case contains 65 files, five aircraft inputs, 16 archived polars and five airfoil coordinate sets. The [source record](isae-sa11-sources.json) retains their hashes, original content, CSV row mappings and commands. Upstream shell and MATLAB scripts were read, never executed.

The primary source is Jacobs, Flechner and Montoya, [NASA-TN-D-8473 (1977)](https://ntrs.nasa.gov/citations/19780012121), a semispan KC-135A experiment. The ISAE heading says KC-130, but the apparatus and primary citation identify KC-135A. The NASA report was recovered and its geometry drawings and measurement description were reviewed.

## Literal inputs and explicit reconstructions

| Input | Literal result | Separate reconstruction |
|---|---|---|
| wingtip_up | Line 32: Too many scaling values (integer columns are not scaled). | [station_scaling](isae-sa11-wingtip_up-station_scaling.asw) |
| wingtip_up_and_down | Attachment station is outside beam 1's parameter range. | [station_scaling](isae-sa11-wingtip_up_and_down-station_scaling.asw) |
| wingtip_up_cant0 | Attachment station is outside beam 2's parameter range. | [joint_station](isae-sa11-wingtip_up_cant0-joint_station.asw) |
| wing_alone | Constructs at all three checked meshes | — |
| wing_extension | Constructs at all three checked meshes | — |

All reconstructions preserve the geometry, section properties and reference quantities. Two correct joint station scaling; the cant0 reconstruction corrects only the winglet-side joint parameters. They are distinct inputs and do not count as successful literal imports.

## Geometry and reference differences

- The upper-winglet axes have about 15.001° front-view cant from vertical, consistent with the stated 15°. The lower-winglet axes instead have 56.041°, versus the primary 36°. This mismatch is preserved.
- The main-wing input twist is 2° about the swept beam axis; its evaluated surface plane intersects a constant-body-y vertical plane at about 1.607° incidence. The primary describes 2° root incidence. The separate airfoil zero-lift offsets are retained and are not fitted to hide the difference.
- Primary coefficients use exposed semispan area 0.4648 m². Half the main input reference area is 0.46645 m². The inputs also use different moment-reference locations. Reference conventions require reconciliation before claiming matched predictions.
- The cant0 variant uses geometry ten times larger, a different reference area and opposite signed left/right winglet twist. No measured or archived curve is assigned to it.
- Primary geometry includes winglet fillets, flow-through nacelles, a fuselage and representative cruise flexibility. The literal rigid lifting-surface calculation is not established as an equivalent apparatus.

The [geometry diagnostic](isae-sa11-source-geometry.json) records physical frames, section-surface areas, endpoint cant and reflection differences. Raw normal-section chord dimensions must not be mistaken for streamwise chord.

## Measurement and postprocessing audit

- CSV headers assign the third pair to upper/lower winglets and the fourth to the extension. MATLAB lift plotting interchanges those two labels; this study follows the headers and retains that provenance uncertainty.
- The lift CSVs have two header lines. MATLAB skips three and repeatedly uses baseline columns for the experimental slope calculations. The study retains all numeric rows and compares each labeled configuration separately.
- MATLAB adds constant CD offsets of 0.0064 at Mach 0.7 and 0.0075 at Mach 0.8. These are documented postprocessing transformations, not raw solver output.
- The archived tables and scripts use speeds 240, 255, 266 and 272 m/s. Their Mach labels are approximate with the input sound speed of 340.21 m/s. Experimental lift comparisons will also evaluate the exact nominal Mach values.
- The ISAE report explicitly states that PG is enabled. PG-off states are numerical diagnostics. Exact archived PG values, initial K/F state and solution-branch history remain unresolved.
- The NASA report warns that the wing/fuselage gap affects absolute axial force and thus lift and drag. Cruise repeat differences of about 0.0002 in CD, less than 0.2% in CL and less than 0.4% in rolling coefficient indicate repeatability, not complete uncertainty bounds.

Transonic shocks and wave drag are outside this ASWING model. Large local velocities at the winglet junctions are also reproduced by [independent line quadrature](isae-sa11-velocity.json); they are not converted into accepted physical solutions.
