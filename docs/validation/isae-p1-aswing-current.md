# Current-source P-1 archived ASWING reproduction

All **110 archived thrust-coefficient values pass** the existing absolute `CT` tolerance of `2e-12`. The maximum difference is **2.220446049250313e-16**. This covers all six saved curves: 20 RPM coordinates each for two and three blades, and 15 for four blades, with viscous power both enabled and disabled.

The replay uses the original `scripts/verify-isae-p1.py` `evaluate()` function and the current production `engine_load`, without calling the historical runner's `main()`. Nominal diameter remains 9 inches, density 1.2256 kg/m³, and axial velocity zero. Original CP inputs and CdA values are unchanged: 1.6, 2.4 and 3.2 × 10⁻⁴ m² with viscous power enabled, and zero with it disabled. The original primary CP tables, extracted ASWING figure values and historical report agree exactly before execution. No parameter fitting, diameter sensitivity or density sweep is included.

Exactly **110 evaluate calls and 110 engine-load calls** were recorded. There were no aircraft solves, full aircraft residual evaluations or browser runs. The single bounded process completed successfully in **2.8011 seconds**, including imports; the component loop took 0.01770 seconds. Maximum independent momentum/power/direction/torque check error within the original helper was 1.6653345369377348e-16. The original reports remain unchanged.

All 111 current kernel modules and 13 helper/reference files were pinned and copied before the replay. Every input pin was verified before and after execution, and actual module import paths are recorded. The single process had a 90-second cap, exited 0 and was reaped; there were no retries.

This establishes reproduction of every stored P-1 CT-versus-RPM curve under its declared component inputs. It does not claim independent power prediction (CP is supplied), every possible propeller output, aircraft-level hover, or experimental agreement. Experimental agreement is outside this benchmark.

Evidence: [per-output report and source pins](isae-p1-aswing-current.json), [110-row CSV](isae-p1-aswing-current.csv), and [execution receipt](isae-p1-aswing-current-execution.json). The earlier [historical report](isae-p1.json) is retained separately.
