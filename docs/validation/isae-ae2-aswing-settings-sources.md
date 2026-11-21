Historical PG Mach, K/F and atmosphere cannot be uniquely recovered from the retained AE-2 files. The scripts explicitly set the solid wall, anchored constraints, beta and indicated-speed sweep; they contain no K/F, K/M or altitude commands. No matching .set/.pnt/.con files survive in the repository, but ASWING could have loaded them at historical startup.

The official menu shows frozen influences and fixed PG Mach zero as examples. It also documents updated influences and PG Mach V/a. These support the finite 2×2 comparison; they do not prove historical factory or runtime settings. The current implementation keeps local section-Mach correction separate from selected PG Mach.

The original model specifies sea-level rho1.23 and sound speed340.21. Sensor V includes induced flow and cannot be read as freestream TAS. A conditional planar diagnostic from the four lowest-speed rows is consistent with TAS≈IAS, within3.1e-6m/s, but lacks the full orientation/flow components needed to recover density or K/F. Keep rho1.23/altitude0 declared and do not tune atmosphere.

The ISAE report identifies AE-2 Figure3 as ASWING5.96. The local executable path and saved channel headers do not establish an exact binary, build or producing input hash. A newer5.98 manual is supporting documentation only.

The frozen source contract covers beta5/U10 on nominal80/160 meshes: updated/frozen influences × PG0/PG=10/340.21. Eight catalog states include two exact prior updated/U-over-a reuses and six new cold candidates. Compare all four archived channels—RY, Psi, V and beta—and both mesh metrics. Preserve the literal stiffness input unchanged. A closest combination is consistency evidence, not reconstructed historical metadata; report all combinations without fitting or changing defaults.

Source/command checks: 244/244 PASS. The87 positive uncoupled archive rows and four unresolved initial NaN rows are retained separately. No physics, production imports or repository changes were performed. The property-derived input remains frozen optional evidence and is excluded from execution.
