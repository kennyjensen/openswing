# SA-1 coefficient and load consistency across the complete polar

All 11 native rows are internally compatible with the documented moment, induced-drag and span-efficiency identities once their printed intervals are propagated. The unchanged model normalization `qS=8295.48524320` also lies within every lift/CL and drag/CD pair's printed intervals. [The saved analysis](report.json) retains all original tokens, bounds, 22 current predictions and six detailed states; [the script](analysis.py) uses only retained data and the standard library.

For this straight planar wing with zero section Cm and the moment reference on its beam axis,
`CLi=(-4 Cm-CDi sin(alpha))/cos(alpha)` independently agrees with `sqrt(pi AR e CDi)` within native precision. The profile components then follow from `CLprofile=CL-CLi` and `CDprofile=CD-CDi`. These are inferred diagnostic quantities, not additional archived acceptance targets.

The table uses the 400-interval baseline. Component errors are current minus archived printed-center inference; the profile-lift compatibility column uses the full propagated native intervals.

| Alpha (deg) | CLi error (%) | CDi error (%) | Profile CL error | Profile CD error | Profile CL compatible with rounding? |
|---:|---:|---:|---:|---:|:---:|
| 0.029369 | +0.057725 | +0.000189 | +2.7388497e-09 | -1.4147756e-09 | yes |
| 1.9971 | +0.057802 | +0.000293 | +2.8212174e-07 | +4.7529307e-08 | yes |
| 4.1116 | +0.057752 | -0.000073 | -5.7855149e-07 | -3.5740398e-08 | yes |
| 6.1087 | +0.057227 | -0.000248 | +1.9632695e-06 | -1.7694805e-08 | yes |
| 8.1351 | +0.054937 | -0.005339 | -3.4446297e-07 | +6.4017629e-08 | yes |
| 10.103 | -0.008570 | -0.119744 | +1.0754651e-06 | +2.4789493e-07 | yes |
| 12.1 | -0.741731 | -1.426915 | +1.7527131e-07 | +6.4475519e-05 | yes |
| 14.097 | -1.742840 | -3.155304 | -1.6464856e-05 | +0.000689614 | no |
| 15.095 | -2.052338 | -3.678316 | -3.3120038e-05 | +0.0012475961 | no |
| 16.006 | -2.271620 | -4.046341 | -6.0455493e-05 | +0.0018669614 | no |
| 18.091 | -2.654474 | -4.682317 | -0.00011244416 | +0.0036169711 | no |

The low-incidence lift bias and the stalled discrepancy have different shapes. CLi changes from about 0.0577% high to 2.6545% low. Profile lift remains compatible with native precision through 12.1 degrees, where CLi is already 0.7417% low. At 18.091 degrees, the total CL error of -0.028795796 consists of -0.028683352 circulation lift and -0.000112444 profile lift. The latter accounts for only 0.3905% of the total error. A profile-force projection adjustment cannot account for the dominant lift discrepancy.

Drag has substantial cancellation. At 18.091 degrees, the induced-drag error is -0.0031484179 and the profile-drag error is +0.0036169711, leaving a total-CD error of +0.00046855318. Total drag agreement alone would conceal this component mismatch. Current span-efficiency error changes from +0.1154% at low incidence to -0.5840% at 18.091 degrees. A uniform Gamma multiplier leaves efficiency invariant and cannot reconcile these values.

The six detailed saved states provide a direct additional check. With `r=V_hv dot lift_axis/U` and `t=V_cp dot normal/U`, Eq70 gives basic profile CD as `sum((Cdf+Cdp)*sqrt(1+r*r)*ds/S)` and separation CD as `sum(4*t*t/sqrt(1+r*r)*ds/S)`. Multiplying each summand by `r` gives its profile CL. The scalar horseshoe oracle supplies the control-point velocity independently. These sums and the moment/efficiency identities reproduce retained raw forces and coefficients within 1.8e-15. At 1.9971 degrees the separation contribution is negligible. At 18.091 degrees/400 intervals, basic profile CD is 0.0112697139 and separation CD is 0.0213188572. The archive does not retain a corresponding split.

This isolates the circulation-lift integral as the main high-incidence lift discrepancy, but does not recover historical Gamma. A historical circulation-distribution difference and a force-integration/transfer difference cannot be distinguished from these aggregate columns. The evidence neither identifies a historical stall parameter nor proves a production-law defect. No parameter was fitted, no frozen artifact was changed, and no new physical solve was performed. The six diagnostic reference-check packets were not used; their Lift/Drag naming issue does not affect this analysis.
