# SA-11 archived normalization conflict

The Mach 0.75/0.78 archives do not use the force/coefficient normalization of the supplied comparison files. Their lift and drag columns independently imply a reference area near **97.67 m²**, assuming the supplied density 1.2256 kg/m³. The Mach 0.70/0.80 archives imply **0.9329 m²**, matching the four comparison inputs.

The inference uses `rho*S = 2*force/(V²*coefficient)`. It does not independently determine density or area. The separate cant0 input also specifies 97.67 m² and tenfold geometry, but that coincidence does not establish which geometry generated any archive. Unknown force units, runtime reference changes, density or older input revisions remain possible. No model or coefficient has been rescaled.

| Configuration | Nominal Mach | Recorded V | Implied area range from lift, at supplied density | Supplied comparison area |
| --- | ---: | ---: | ---: | ---: |
| wingtip_up | 0.7 | 240 | 0.932897–0.932905 | 0.9329 |
| wingtip_up | 0.75 | 255 | 97.669630–97.670273 | 0.9329 |
| wingtip_up | 0.78 | 266 | 97.669710–97.670402 | 0.9329 |
| wingtip_up | 0.8 | 272 | 0.932897–0.932905 | 0.9329 |
| wingtip_up_and_down | 0.7 | 240 | 0.932895–0.932904 | 0.9329 |
| wingtip_up_and_down | 0.75 | 255 | 97.669619–97.670488 | 0.9329 |
| wingtip_up_and_down | 0.78 | 266 | 97.669487–97.670328 | 0.9329 |
| wingtip_up_and_down | 0.8 | 272 | 0.932895–0.932904 | 0.9329 |
| wing_alone | 0.7 | 240 | 0.932897–0.932905 | 0.9329 |
| wing_alone | 0.75 | 255 | 97.669629–97.670455 | 0.9329 |
| wing_alone | 0.78 | 266 | 97.669789–97.670399 | 0.9329 |
| wing_alone | 0.8 | 272 | 0.932897–0.932905 | 0.9329 |
| wing_extension | 0.7 | 240 | 0.932898–0.932904 | 0.9329 |
| wing_extension | 0.75 | 255 | 97.669786–97.670340 | 0.9329 |
| wing_extension | 0.78 | 266 | 97.669679–97.670308 | 0.9329 |
| wing_extension | 0.8 | 272 | 0.932897–0.932903 | 0.9329 |

All 16 tables contain 41 converged rows. Using their implied area, printed force and coefficient differences are within 2×10⁻⁵ relative. All 65 upstream files pass their pinned SHA-256, Git blob SHA-1 and byte-count checks.

The Mach 0.75/0.78 baseline, extension and upper-only lift/drag curves are almost identical at archive precision. The combined upper/lower winglets change between those speeds. PG settings and exact model revisions remain unverified.

Numerical comparisons at these two Mach labels must therefore be interpreted as comparisons against unmatched source configurations. See [machine-readable audit](isae-sa11-archive.json) and [source geometry audit](isae-sa11-sources.md).
