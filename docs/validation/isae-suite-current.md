# Frozen broad ISAE archived-output baseline

This report retains the six-batch baseline before the source-rank and exact-station fixes. See the [new FFWT/ST-4 follow-up](isae-suite-followup-20261026.md) for current bounded reruns. Other families have not been rerun against that changed kernel; the counts below remain the original baseline.

41 families are accounted for; 23 still lack a current comparison adapter. The complete suite is not yet reproduced. Experimental agreement is not required.

Scalar outputs: **35193 required**, 35062 reported, 26251 finite, 26251 numerically valid and finite, **11521 matching**; 131 absent and 8811 reported but unavailable. 8724 required outputs belong to explicitly unsupported scopes; 212 belong to failed jobs.

Aggregate scalar pass fractions are not a validation or completion percentage. Counts include multiple meshes, repeated output recoveries and exact-zero channels. Family status and the declared model/reference scope are the primary coverage measures; jobs are execution units, not distinct cases. Original samples below exclude mesh repeats and include unsupported reference rows.

| Family | Computed/target models | Valid/original samples | Jobs finished/planned | Required | Reported | Finite | Valid finite | Passed | Absent | Unsupported | Current status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SA-1 | 1/1 | 11/11 | 22/22 | 154 | 154 | 154 | 154 | 19 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| SA-10 | 5/6 | 135/162 | 324/324 | 2268 | 2261 | 1883 | 1883 | 54 | 7 | 378 | NUMERICAL_OR_INPUT_FAILURES |
| SA-11 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-12 | 0/2 | 0/510 | 1020/1020 | 4080 | 4080 | 0 | 0 | 0 | 0 | 4080 | DECLARED_SCOPE_UNSUPPORTED |
| SA-13 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-14 | 3/3 | 180/180 | 360/360 | 360 | 325 | 325 | 325 | 2 | 35 | 0 | NUMERICAL_OR_INPUT_FAILURES |
| SA-15 | 0/1 | 0/13 | 26/26 | 182 | 182 | 0 | 0 | 0 | 0 | 182 | DECLARED_SCOPE_UNSUPPORTED |
| SA-2 | 1/1 | 5/5 | 10/10 | 70 | 70 | 70 | 70 | 0 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| SA-3 | 1/1 | 22/22 | 44/44 | 308 | 308 | 308 | 308 | 0 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| SA-4 | 1/1 | 42/42 | 84/84 | 588 | 539 | 539 | 539 | 0 | 49 | 0 | NUMERICAL_OR_INPUT_FAILURES |
| SA-5 | 1/1 | 12/12 | 24/24 | 168 | 168 | 164 | 164 | 20 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| SA-6 | 1/4 | 11/44 | 91/91 | 528 | 528 | 132 | 132 | 22 | 0 | 396 | PARTLY_UNSUPPORTED_SCOPE |
| SA-7 | 2/2 | 58/58 | 116/116 | 812 | 812 | 810 | 810 | 0 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| SA-8 | 2/2 | 36/36 | 72/72 | 504 | 504 | 504 | 504 | 0 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| UA-1 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| UA-2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AP-1 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AP-2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-1 | 0/0 | 110/110 | 6/6 | 110 | 110 | 110 | 110 | 110 | 0 | 0 | SELECTED_SCOPE_MATCHES |
| P-2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-3 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-4 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-5 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-1 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-3 | 1/1 | 45/45 | 1/1 | 1080 | 1080 | 1080 | 1080 | 930 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| ST-4 | 2/6 | 12/1777 | 42/42 | 3749 | 3749 | 36 | 36 | 0 | 0 | 3656 | NUMERICAL_OR_INPUT_FAILURES |
| ST-5 | 3/3 | 240/240 | 3/3 | 19440 | 19440 | 19440 | 19440 | 10364 | 0 | 0 | ARCHIVED_OUTPUT_DIFFERENCES |
| ST-6 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-1 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-2 | 1/1 | 87/91 | 182/182 | 728 | 728 | 696 | 696 | 0 | 0 | 32 | PARTLY_UNSUPPORTED_SCOPE |
| AE-3 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-4 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-5 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-6 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-7 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-1 | 0/1 | 0/8 | 16/16 | 64 | 24 | 0 | 0 | 0 | 40 | 0 | NUMERICAL_OR_INPUT_FAILURES |
| FFWT-2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-3 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-4 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-5 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |

Missing adapters: SA-11, SA-13, UA-1, UA-2, AP-1, AP-2, P-2, P-3, P-4, P-5, ST-1, ST-2, ST-6, AE-1, AE-3, AE-4, AE-5, AE-6, AE-7, FFWT-2, FFWT-3, FFWT-4, FFWT-5.

Fine-grid polar errors use the larger predeclared nominal mesh. All rows remain in the denominator; metrics use valid finite pairs. Force units follow each literal model Unit F declaration; coefficients and efficiency are dimensionless.

| Table | Panels | Channel | Unit | Valid pairs/rows | Failed or unrun rows | Unavailable/absent | RMSE | Max absolute error |
|---|---:|---|---|---:|---:|---:|---:|---:|
| SA-1: SA_1_CL.txt | 400 | lift | N | 11/11 | 0 | 0/0 | 115.94997 | 238.90766 |
| SA-1: SA_1_CL.txt | 400 | drag | N | 11/11 | 0 | 0/0 | 3.9888837 | 8.1365584 |
| SA-1: SA_1_CL.txt | 400 | CL | 1 | 11/11 | 0 | 0/0 | 0.013976588 | 0.028795796 |
| SA-1: SA_1_CL.txt | 400 | CD | 1 | 11/11 | 0 | 0/0 | 0.0004808508 | 0.00098088272 |
| SA-1: SA_1_CL.txt | 400 | CDi | 1 | 11/11 | 0 | 0/0 | 0.0014611168 | 0.0031484179 |
| SA-1: SA_1_CL.txt | 400 | Cm | 1 | 11/11 | 0 | 0/0 | 0.0034465696 | 0.0070607614 |
| SA-1: SA_1_CL.txt | 400 | efficiency | 1 | 11/11 | 0 | 0/0 | 0.0027161788 | 0.0054709297 |
| SA-10: Louvered.txt | 200 | lift | N | 27/27 | 0 | 0/0 | 12.627882 | 23.198909 |
| SA-10: Louvered.txt | 200 | drag | N | 27/27 | 0 | 0/0 | 3.4685671 | 8.4153001 |
| SA-10: Louvered.txt | 200 | CL | 1 | 27/27 | 0 | 0/0 | 0.034232198 | 0.062890417 |
| SA-10: Louvered.txt | 200 | CD | 1 | 27/27 | 0 | 0/0 | 0.009402616 | 0.022812066 |
| SA-10: Louvered.txt | 200 | CDi | 1 | 27/27 | 0 | 0/0 | 0.0025414377 | 0.0048008946 |
| SA-10: Louvered.txt | 200 | Cm | 1 | 27/27 | 0 | 0/0 | 0.26110791 | 0.34836731 |
| SA-10: Louvered.txt | 200 | efficiency | 1 | 27/27 | 0 | 0/0 | 0.31004232 | 1.6099071 |
| SA-10: TS_60_40_80.txt | 128 | lift | N | 27/27 | 0 | 0/0 | 10.863132 | 22.249387 |
| SA-10: TS_60_40_80.txt | 128 | drag | N | 27/27 | 0 | 0/0 | 1.8003598 | 4.8806351 |
| SA-10: TS_60_40_80.txt | 128 | CL | 1 | 27/27 | 0 | 0/0 | 0.029448098 | 0.060315396 |
| SA-10: TS_60_40_80.txt | 128 | CD | 1 | 27/27 | 0 | 0/0 | 0.0048804137 | 0.01323059 |
| SA-10: TS_60_40_80.txt | 128 | CDi | 1 | 27/27 | 0 | 0/0 | 0.0020994369 | 0.0043674548 |
| SA-10: TS_60_40_80.txt | 128 | Cm | 1 | 27/27 | 0 | 0/0 | 0.28878989 | 0.39231621 |
| SA-10: TS_60_40_80.txt | 128 | efficiency | 1 | 27/27 | 0 | 0/0 | 0.34088191 | 1.0949065 |
| SA-10: TS_60_45_30.txt | 128 | lift | N | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | drag | N | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | CL | 1 | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | CD | 1 | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | CDi | 1 | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | Cm | 1 | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_60_45_30.txt | 128 | efficiency | 1 | 0/27 | 27 | 27/0 | unavailable | unavailable |
| SA-10: TS_80_60_40.txt | 128 | lift | N | 26/27 | 1 | 0/1 | 8.1951205 | 16.907947 |
| SA-10: TS_80_60_40.txt | 128 | drag | N | 26/27 | 1 | 0/1 | 0.71345259 | 2.3222666 |
| SA-10: TS_80_60_40.txt | 128 | CL | 1 | 26/27 | 1 | 0/1 | 0.022215481 | 0.045833651 |
| SA-10: TS_80_60_40.txt | 128 | CD | 1 | 26/27 | 1 | 0/1 | 0.0019340791 | 0.0062953098 |
| SA-10: TS_80_60_40.txt | 128 | CDi | 1 | 26/27 | 1 | 0/1 | 0.0022883304 | 0.0049105287 |
| SA-10: TS_80_60_40.txt | 128 | Cm | 1 | 26/27 | 1 | 0/1 | 0.28326198 | 0.39043055 |
| SA-10: TS_80_60_40.txt | 128 | efficiency | 1 | 26/27 | 1 | 0/1 | 0.17992344 | 0.88409197 |
| SA-10: wing_alone.txt | 200 | lift | N | 27/27 | 0 | 0/0 | 8.6740253 | 16.330724 |
| SA-10: wing_alone.txt | 200 | drag | N | 27/27 | 0 | 0/0 | 1.1534526 | 3.3890539 |
| SA-10: wing_alone.txt | 200 | CL | 1 | 27/27 | 0 | 0/0 | 0.02351407 | 0.044269385 |
| SA-10: wing_alone.txt | 200 | CD | 1 | 27/27 | 0 | 0/0 | 0.0031268139 | 0.0091872894 |
| SA-10: wing_alone.txt | 200 | CDi | 1 | 27/27 | 0 | 0/0 | 0.0024024825 | 0.0048445644 |
| SA-10: wing_alone.txt | 200 | Cm | 1 | 27/27 | 0 | 0/0 | 0.22260441 | 0.30253098 |
| SA-10: wing_alone.txt | 200 | efficiency | 1 | 27/27 | 0 | 0/0 | 0.18928978 | 0.98326818 |
| SA-10: wing_extension.txt | 200 | lift | N | 27/27 | 0 | 0/0 | 15.020805 | 25.532673 |
| SA-10: wing_extension.txt | 200 | drag | N | 27/27 | 0 | 0/0 | 2.9465573 | 7.5426244 |
| SA-10: wing_extension.txt | 200 | CL | 1 | 27/27 | 0 | 0/0 | 0.040719251 | 0.069214954 |
| SA-10: wing_extension.txt | 200 | CD | 1 | 27/27 | 0 | 0/0 | 0.007987539 | 0.020447707 |
| SA-10: wing_extension.txt | 200 | CDi | 1 | 27/27 | 0 | 0/0 | 0.0027290558 | 0.0050814176 |
| SA-10: wing_extension.txt | 200 | Cm | 1 | 27/27 | 0 | 0/0 | 0.27584718 | 0.36682375 |
| SA-10: wing_extension.txt | 200 | efficiency | 1 | 27/27 | 0 | 0/0 | 0.34708195 | 1.8021615 |
| SA-12: Rectangular_Wing_Flap_hc_05.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_05.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_05.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_05.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_2.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_2.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_2.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_2.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_inf.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_inf.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_inf.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_Flap_hc_inf.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_05.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_05.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_05.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_05.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_2.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_2.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_2.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_2.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_inf.txt | 200 | CL | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_inf.txt | 200 | CD | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_inf.txt | 200 | CDi | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-12: Rectangular_Wing_No_Flap_hc_inf.txt | 200 | Cm | 1 | 0/85 | 85 | 85/0 | unavailable | unavailable |
| SA-14: WB_polaire_totale.txt | 128 | CL | 1 | 48/60 | 12 | 0/12 | 0.042996694 | 0.093827441 |
| SA-14: WB_polaire_totale_infinite_fuselage.txt | 128 | CL | 1 | 48/60 | 12 | 0/12 | 0.040485104 | 0.083800762 |
| SA-14: W_only_polaire_totale.txt | 128 | CL | 1 | 49/60 | 11 | 0/11 | 0.017077686 | 0.028826367 |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | CD | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | CY | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | CL | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | Cl | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | Cm | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | Cn | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-15: JW1_FW_Only_Body_CL_alpha.txt | 128 | efficiency | 1 | 0/13 | 13 | 13/0 | unavailable | unavailable |
| SA-2: SA_2_CL.txt | 200 | lift | N | 5/5 | 0 | 0/0 | 4.6351036 | 10.348577 |
| SA-2: SA_2_CL.txt | 200 | drag | N | 5/5 | 0 | 0/0 | 3.6416165 | 6.703153 |
| SA-2: SA_2_CL.txt | 200 | CL | 1 | 5/5 | 0 | 0/0 | 0.0019601617 | 0.0043763983 |
| SA-2: SA_2_CL.txt | 200 | CD | 1 | 5/5 | 0 | 0/0 | 0.0015407213 | 0.0028360015 |
| SA-2: SA_2_CL.txt | 200 | CDi | 1 | 5/5 | 0 | 0/0 | 0.00016852143 | 0.00037678173 |
| SA-2: SA_2_CL.txt | 200 | Cm | 1 | 5/5 | 0 | 0/0 | 0.002164661 | 0.0048049116 |
| SA-2: SA_2_CL.txt | 200 | efficiency | 1 | 5/5 | 0 | 0/0 | 0.0012146614 | 0.0013692502 |
| SA-3: SA_3.txt | 200 | lift | N | 22/22 | 0 | 0/0 | 1.4675714 | 2.3470037 |
| SA-3: SA_3.txt | 200 | drag | N | 22/22 | 0 | 0/0 | 1.0331387 | 2.2465007 |
| SA-3: SA_3.txt | 200 | CL | 1 | 22/22 | 0 | 0/0 | 0.00050213186 | 0.00080486908 |
| SA-3: SA_3.txt | 200 | CD | 1 | 22/22 | 0 | 0/0 | 0.00035360393 | 0.00076899804 |
| SA-3: SA_3.txt | 200 | CDi | 1 | 22/22 | 0 | 0/0 | 1.1290275e-06 | 1.8601139e-06 |
| SA-3: SA_3.txt | 200 | Cm | 1 | 22/22 | 0 | 0/0 | 1.0015402e-05 | 1.6741337e-05 |
| SA-3: SA_3.txt | 200 | efficiency | 1 | 22/22 | 0 | 0/0 | 0.0026551143 | 0.0027408341 |
| SA-4: SA_4.txt | 160 | lift | N | 15/21 | 6 | 0/6 | 12.705066 | 47.34254 |
| SA-4: SA_4.txt | 160 | drag | N | 15/21 | 6 | 0/6 | 2.1907727 | 6.5651569 |
| SA-4: SA_4.txt | 160 | CL | 1 | 15/21 | 6 | 0/6 | 0.0043167358 | 0.016085526 |
| SA-4: SA_4.txt | 160 | CD | 1 | 15/21 | 6 | 0/6 | 0.00074432672 | 0.0022305824 |
| SA-4: SA_4.txt | 160 | CDi | 1 | 15/21 | 6 | 0/6 | 0.00026637654 | 0.0010187571 |
| SA-4: SA_4.txt | 160 | Cm | 1 | 15/21 | 6 | 0/6 | 0.0002817082 | 0.00073528194 |
| SA-4: SA_4.txt | 160 | efficiency | 1 | 15/21 | 6 | 0/6 | 0.016110545 | 0.062269917 |
| SA-4: SA_4_ASW_CD.txt | 40 | lift | N | 21/21 | 0 | 0/0 | 6.3964262 | 11.92958 |
| SA-4: SA_4_ASW_CD.txt | 40 | drag | N | 21/21 | 0 | 0/0 | 0.7500712 | 2.0636893 |
| SA-4: SA_4_ASW_CD.txt | 40 | CL | 1 | 21/21 | 0 | 0/0 | 0.0021731941 | 0.0040525277 |
| SA-4: SA_4_ASW_CD.txt | 40 | CD | 1 | 21/21 | 0 | 0/0 | 0.00025482248 | 0.00070104448 |
| SA-4: SA_4_ASW_CD.txt | 40 | CDi | 1 | 21/21 | 0 | 0/0 | 0.00024517834 | 0.00048490622 |
| SA-4: SA_4_ASW_CD.txt | 40 | Cm | 1 | 21/21 | 0 | 0/0 | 0.0077465268 | 0.013246109 |
| SA-4: SA_4_ASW_CD.txt | 40 | efficiency | 1 | 21/21 | 0 | 0/0 | 0.002543495 | 0.0045400963 |
| SA-5: SA_5.txt | 400 | lift | N | 12/12 | 0 | 0/0 | 33.51513 | 100.54469 |
| SA-5: SA_5.txt | 400 | drag | N | 12/12 | 0 | 0/0 | 6.5106001 | 17.619989 |
| SA-5: SA_5.txt | 400 | CL | 1 | 12/12 | 0 | 0/0 | 0.0039729256 | 0.011918743 |
| SA-5: SA_5.txt | 400 | CD | 1 | 12/12 | 0 | 0/0 | 0.00077175601 | 0.0020886395 |
| SA-5: SA_5.txt | 400 | CDi | 1 | 12/12 | 0 | 0/0 | 0.00053990422 | 0.0016521244 |
| SA-5: SA_5.txt | 400 | Cm | 1 | 12/12 | 0 | 0/0 | 0.0015244504 | 0.0033722773 |
| SA-5: SA_5.txt | 400 | efficiency | 1 | 10/12 | 0 | 2/0 | 0.0012513092 | 0.0018917334 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | lift | N | 29/29 | 0 | 0/0 | 29.404235 | 92.095988 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | drag | N | 29/29 | 0 | 0/0 | 1.3242989 | 4.1043192 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | CL | 1 | 29/29 | 0 | 0/0 | 0.017543501 | 0.054945492 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | CD | 1 | 29/29 | 0 | 0/0 | 0.0007901068 | 0.0024487099 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | CDi | 1 | 29/29 | 0 | 0/0 | 0.0051964431 | 0.013424043 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | Cm | 1 | 29/29 | 0 | 0/0 | 0.018339245 | 0.063109931 |
| SA-7: Tandem_GAW2_L163_G05.txt | 128 | efficiency | 1 | 29/29 | 0 | 0/0 | 0.0077990826 | 0.018946228 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | lift | N | 29/29 | 0 | 0/0 | 7660.0214 | 10715.664 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | drag | N | 29/29 | 0 | 0/0 | 765.44198 | 2134.662 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | CL | 1 | 29/29 | 0 | 0/0 | 4.6835585 | 6.5518683 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | CD | 1 | 29/29 | 0 | 0/0 | 0.46801339 | 1.3051946 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | CDi | 1 | 29/29 | 0 | 0/0 | 0.048249572 | 0.08007034 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | Cm | 1 | 29/29 | 0 | 0/0 | 1.1537837 | 1.5466945 |
| SA-7: Tandem_GAW2_L163_G05_Fore_Only.txt | 128 | efficiency | 1 | 28/29 | 0 | 1/0 | 20.073334 | 21.176456 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | lift | N | 18/18 | 0 | 0/0 | 2.9344162 | 6.8801041 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | drag | N | 18/18 | 0 | 0/0 | 0.14131936 | 0.52667949 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | CL | 1 | 18/18 | 0 | 0/0 | 0.0097674211 | 0.022902082 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | CD | 1 | 18/18 | 0 | 0/0 | 0.00047034385 | 0.0017529295 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | CDi | 1 | 18/18 | 0 | 0/0 | 0.00066081014 | 0.0017334027 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | Cm | 1 | 18/18 | 0 | 0/0 | 0.034914993 | 0.06742104 |
| SA-8: Tandem_Airframe_NACA4309.txt | 128 | efficiency | 1 | 18/18 | 0 | 0/0 | 0.22873863 | 0.96528144 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | lift | N | 18/18 | 0 | 0/0 | 2.7886528 | 5.8999264 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | drag | N | 18/18 | 0 | 0/0 | 0.3325505 | 0.57252592 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | CL | 1 | 18/18 | 0 | 0/0 | 0.0092814447 | 0.019636283 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | CD | 1 | 18/18 | 0 | 0/0 | 0.0011068509 | 0.001905562 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | CDi | 1 | 18/18 | 0 | 0/0 | 0.00033004185 | 0.00078807032 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | Cm | 1 | 18/18 | 0 | 0/0 | 0.0022540805 | 0.0047328917 |
| SA-8: Tandem_Airframe_NACA4309_Fore_Only.txt | 128 | efficiency | 1 | 18/18 | 0 | 0/0 | 0.0058560908 | 0.015278289 |

SA-6 six static stability-axis coefficients at the predeclared128 mesh. Each model retains11 original fmat operating points; three model/driver pairings remain unsupported. Derivative and inertia tensors are excluded.

| Original model | Channel | Valid pairs/11 | RMSE | Max absolute error |
|---|---|---:|---:|---:|
| Straight_Wing_20b_15c.asw | CX | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_15c.asw | CY | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_15c.asw | CL | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_15c.asw | Cl | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_15c.asw | Cm | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_15c.asw | Cn | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | CX | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | CY | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | CL | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | Cl | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | Cm | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_20c.asw | Cn | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | CX | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | CY | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | CL | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | Cl | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | Cm | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_30c.asw | Cn | 0/11 | unavailable | unavailable |
| Straight_Wing_20b_35c.asw | CX | 11/11 | 0.046957328 | 0.08706092 |
| Straight_Wing_20b_35c.asw | CY | 11/11 | 0 | 0 |
| Straight_Wing_20b_35c.asw | CL | 11/11 | 0.026074463 | 0.038966489 |
| Straight_Wing_20b_35c.asw | Cl | 11/11 | 0.0021181045 | 0.0032566287 |
| Straight_Wing_20b_35c.asw | Cm | 11/11 | 0.0073160465 | 0.01136448 |
| Straight_Wing_20b_35c.asw | Cn | 11/11 | 0.01499771 | 0.029021578 |

P-1 CT: 110/110 valid pairs (full original selected scope: 110); maximum absolute difference 2.220446e-16.

P-1 is an isolated component comparison and does not name a whole-aircraft model. No mesh or reference gate was widened. Source import counts and test counts are not included in output agreement.

Original models without a paired reference remain inventory records with zero scalar targets:

| Family | Model | Record status | Reason |
|---|---|---|---|
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b30.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b46.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b48.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b8.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/WING.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7b/7b_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7b/7b_b21.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7c/7c_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7c/7c_b28.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b21.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b27.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b33.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b39.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b44.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7d/7d_b49.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7e/7e_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7e/7e_b21.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7e/7e_b29.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7e/7e_b35.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7e/7e_b40.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7f/7f_b11.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7f/7f_b16.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7f/7f_b24.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7f/7f_b32.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| ST-4 | /home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7f/7f_b40.asw | unsupported | No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred. |
| SA-6 | .reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 6 - Straight Wing - Rolling and Yawing Moments induced by various Ailerons/Simulation/spanwize/Straight_Wing_10b_25c.asw | unsupported | Original spanwise model has no paired archived numerical fmat output; experimental tables are excluded. |
| SA-6 | .reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 6 - Straight Wing - Rolling and Yawing Moments induced by various Ailerons/Simulation/spanwize/Straight_Wing_15b_25c.asw | unsupported | Original spanwise model has no paired archived numerical fmat output; experimental tables are excluded. |
| SA-6 | .reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 6 - Straight Wing - Rolling and Yawing Moments induced by various Ailerons/Simulation/spanwize/Straight_Wing_20b_25c.asw | unsupported | Original spanwise model has no paired archived numerical fmat output; experimental tables are excluded. |

Executable modal comparisons retain only the declared positive imaginary components within selected roots, not a complete spectrum or a globally lowest-mode claim.
Blocked modal aggregate cells are ASWING-labelled reference candidates; their stored-cell precision is not recovered ASWING printed precision.
Unpaired original models remain visible inventory jobs with no invented scalar targets; job completion is checked even when their scalar count is zero.
Aeroelastic comparisons retain all four declared original channels; missing NaN rows remain unsupported, with no interpolation or zero replacement.
