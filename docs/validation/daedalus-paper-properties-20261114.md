# Daedalus: published wing properties and measured construction weights

The public `dae.asw` does not represent the same mass distribution as either
Figure 7 of Drela's 1989 wing-load paper or the measured aircraft in Juan
Cruz's construction weight log. The parser faithfully reads the public file.
This is evidence of differing inputs, not a demonstrated solver defect or an
identification of the later rudder Bode setup.

![Property and weight-distribution comparisons](../../artifacts/daedalus-paper-properties-20261114/compare/properties.png)

## Literal input audit

The [authoritative index](aswing-authoritative-references.md) and checksummed
source catalog were consulted. The [1989 paper](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf)
and its [source record](isae-st4-node-placement-sources-20261109.json) supply
Figure 7 on PDF p. 8, printed p. 329.

An independent reader checks all **20 wing-property tables and 269 entries**,
including each `*` multiplier, source station and repeated-station break,
against the production parser. All arrays agree exactly. Current SEGSPL
interpolation is plotted between those unchanged samples. No parameter was
inferred from the response curves or changed to make the overlay agree.

At the root, the file gives EIcc = 50,300, EInn = 1,650,000 and GJ = 40,800
in lb ft², with weight density 0.610 lb/ft. In this wing's section axes, EIcc
is out-of-plane bending stiffness and EInn is in-plane stiffness.

Figure 7 uses Lref = **230 lb**, distinct from the **240 lb flight case** in
section 5.2. With b = 112 ft, its displayed normalizations give:

| Quantity at root | Current normalized value |
| --- | ---: |
| 5 EInn / (Lref b²) | 2.85950 |
| 100 EIcc / (Lref b²) | 1.74343 |
| GJ / (Lref b²), literal scanned label | 0.01414 |
| 100 GJ / (Lref b²), conditional display | 1.41415 |
| mg / (Lref/b) | 0.29704 |

The main bending-stiffness scales and trends agree visually, but local steps
and interpolation differ. The GJ curve resembles a **100-times display** of
the current values; the scanned legend does not show that factor. The overlay
therefore shows both interpretations explicitly. This may be a label omission,
but that is an inference, not evidence to multiply physical GJ by 100. No
strict matched-input stiffness validation is claimed. Chord widths are also
compared, under an explicitly assumed equal-scale planform drawing.

## Weight distribution in Figure 7

The visible mg curve contains peaks near positive-semispan stations 14 and
42 ft, mirrored on the other wing. The modern file has no corresponding peaks
in `mg`, no `Dmg` contribution and no point weights attached to the wing.
The source curve is traced without using model or Bode values to place it.
98.58% of traced columns find a dark pixel within the fixed manual corridor;
the rest use the disclosed visual anchor interpolation.

| Peak | Approximate peak density, lb/ft | Modern density there, lb/ft | Excess weight above local baseline, per peak |
| --- | ---: | ---: | ---: |
| Near 14 ft | 1.733 | 0.430 | 1.739 ± 0.282 lb |
| Near 42 ft | 0.882 | 0.217 | 0.632 ± 0.221 lb |

Across both wings, the peaks contain approximately **4.74 ± 1.01 lb** above
their local baselines. These are raster estimates; the bounds cover two-pixel
vertical uncertainty in the trace and baseline endpoints only, not horizontal
window selection, unknown plotting errors or historical-model errors.
Positions and local densities assume 112 ft span. Integrated weight
does not require that span assumption: for the symmetric wing,
`W = Lref * integral_0^1 [mg/(Lref/b)] d(2s/b)`.

The entire trace integrates to **49.62 lb**, with a two-pixel ordinate bound of
**±4.76 lb**. The literal SEGSPL density integrates to **37.7023 lb**; independent
three- and four-point interval quadrature agree. The earlier solved mesh uses
endpoint quadrature and gives **38.5382 lb**. These three quantities are kept
distinct. The raster estimate should not replace either a measured weight or
the literal model input. [Trace CSV, image and calibration](../../artifacts/daedalus-paper-properties-20261114/compare/)
and [integral results](../../artifacts/daedalus-paper-properties-20261114/integrate/result.json)
are retained.

## Independent measured weights

Juan R. Cruz, MIT, *Weight Analysis of the Daedalus Human Powered Aircraft*,
**Technical Soaring 14(1), 1990**, presented at the 1989 OSTIV Congress,
provides the measured construction log. The PDF was downloaded from the
[journal](https://ts.ostiv.org/index.php/ts/article/view/760) into the visible
[reference directory](../../reference/daedalus-weight-20261114/). Its
[checksummed supplement](daedalus-weight-sources-20261114.json) records provenance.
Table 1, PDF p. 3 / printed p. 4, was visually checked against the following
values. This is a primary measured-aircraft source, distinct from an ASWING
reference solution.

| Component | Cruz measured, lb | Public model as solved, lb | Model difference |
| --- | ---: | ---: | ---: |
| Wing | 41.85 | 38.538 | -7.91% |
| Elevator | 1.19 | 1.1325 | -4.83% |
| Rudder | 1.37 | 1.1363 | -17.06% |
| Fuselage and remaining equipment | 24.09 | 15.495 | -35.68% |
| Empty aircraft | 68.50 | 56.302 | -17.81% |

The modern empty weight subtracts its 165 lb pilot and 12 lb water from the
233.3019 lb total. The fuselage/equipment row includes both nonlifting/body
assemblies and the 8 lb of propulsion/gearbox point weights. Printed rounded
component totals differ from the rounded overall total by 0.01 lb.

The measured wing total is substantially below the 1989 diagram's raster
integral. Thus even the historical publications cannot be combined into one
authenticated model without further reconciliation. The measurements also
show that most of the modern empty-weight difference lies outside the wing.
The table cannot uniquely identify an omitted component's position, centroid
or inertia. For example, the separately reported rudder tab is relevant to
the rudder mass difference, but is not proof that the public model excludes
all of its aerodynamic or mass effects.

## Consequence and evidence

These results prioritize an explicit mass-distribution sensitivity over more
unsupported changes to aerodynamic derivatives. Any conditional reconstruction
must disclose its component locations and distinguish the measured table,
raster curve and public file. None establishes the mass model used by the 2008
Bode drawing. No aircraft, production equation, ISAE count or tolerance changed.

The [driver](../../scripts/check_daedalus_paper_properties.py) ran four small
serial jobs with one BLAS thread; all succeeded and were reaped. The largest
observed CPU time was 3.253 s, wall time 8.504 s and RSS 201.21 MiB, below the
unchanged 15 CPU s / 25 wall s / 512 MiB caps. The reference download is
separately recorded. The [verification receipt](../../artifacts/daedalus-paper-properties-20261114/verification.json)
checks inputs, outputs and unchanged production. Browser/build jobs remain
on hold, and the full ASWING-equivalence goal remains incomplete.
