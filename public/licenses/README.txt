# Attribution and third-party software

The original code and original example configurations in this repository are
MIT licensed. Mark Drela's ASWING publications are the scientific specification,
not source code copied into this project. ASWING has its own licensing terms;
this project's MIT license does not apply to ASWING or its publications/examples.
The three model files published on [Drela's ASWING page](https://web.mit.edu/drela/Public/web/aswing/)
are bundled unchanged at the user's request: `examples/dae.asw` (Daedalus),
`examples/usa.asw` (ultralight sailplane), and `examples/fw.asw` (swept flying wing).
They are upstream example data, not original OpenSwing configurations; their
inclusion does not place them under this project's MIT license. Source URLs,
retrieval date and byte-level checksums are in `examples/drela-sources.json`.
The original ISAE `FFWT_Flare10.asw` is also bundled unchanged as
`examples/isae-ffwt-flare10.asw` for reproducible reference comparisons. It is
upstream model data from
[ISAE_Aswing_Experimental_Validation](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation),
commit `f62943df20e9e4d7d9f50e070477b22426b5f865`, and is not relicensed as
original OpenSwing code. Its byte hash and exact case location are recorded
in `docs/validation/isae-ffwt-original.md` and the associated evidence.
The original SA-11 baseline `wing_alone.asw` from the same ISAE revision is
bundled unchanged as `examples/isae-sa11-wing-alone.asw` for inspection through
the example picker. Its exact upstream path and byte checksum are recorded in
`examples/isae-sa11-source.json`; it remains upstream model data, not original
MIT-licensed OpenSwing code.
The SA-11 upper and upper/lower winglet examples are adaptations of the same
ISAE revision. Only joint-station scaling and attribution comments are changed;
their original hashes, paths and exact corrections are recorded in
`examples/isae-sa11-winglet-sources.json`. They retain upstream attribution
and are not relicensed as original OpenSwing code.
Other downloaded reference documents remain in the ignored `.reference/`
directory and are excluded from distributable source and website assets.

The application uses:

| Package | Role | Upstream license |
|---|---|---|
| Python / CPython | Numerical language runtime | Python Software Foundation License |
| NumPy | Array algebra and linear algebra | BSD-3-Clause |
| SciPy | Interpolation and nonlinear/BVP solves | BSD-3-Clause (plus bundled dependency notices) |
| Pyodide | CPython and scientific packages in WebAssembly | MPL-2.0 and bundled package licenses |
| Three.js | WebGL aircraft view | MIT |
| Vite | Development and production bundling | MIT |
| Playwright | Browser integration tests | Apache-2.0 |
| pytest | Native numerical tests | MIT |
| pypdf | Optional local reference text extraction | BSD-3-Clause |
| DM Sans / IBM Plex Mono | Self-hosted interface fonts | SIL Open Font License 1.1 |

Exact JavaScript versions are locked in `package-lock.json`; WebAssembly package
versions/checksums are pinned by Pyodide's lock. Individual wheels carry their
own upstream licenses. Preserve those notices when redistributing runtime
assets. This list does not replace their detailed third-party notices.

The pinned [ARPACK-NG reference source](https://github.com/opencollab/arpack-ng)
is available in `third_party/arpack`, at upstream commit
`66faef9e09bb35f5acafe02960885050acc46fa0`. Its unchanged BSD license is in
`third_party/arpack/COPYING`; archive provenance and all 487 file hashes are in
`third_party/arpack-source.json`. This is a source reference for checking the
ASWING paper's Arnoldi algorithm. It has not been newly built or linked into
the application; numerical execution currently uses SciPy's ARPACK interface.
The reference tree retains its upstream license and is not original MIT-licensed
OpenSwing code.

Additional aerodynamic reference selections under `third_party` retain their
upstream licenses and revision/file hashes in their `SOURCE.json` manifests.
The OpenAeroStruct and PyTornado selections are Apache-2.0 licensed, with the
unmodified licenses in `third_party/openaerostruct/LICENSE.md` and
`third_party/pytornado/LICENSE.txt`. They are source-inspection references,
not application runtime dependencies or original OpenSwing code.

The PteraSoftware and pySailingVLM source selections are retained for force
and vortex-connectivity inspection. PteraSoftware's MIT license is in
`third_party/pterasoftware/LICENSE.md`; pySailingVLM's Apache-2.0 license is in
`third_party/pysailingvlm/LICENSE`. Each selection has a `SOURCE.json` recording
its upstream revision and unmodified file hashes. Neither is installed or
included as an application runtime dependency.

The numeric Durrant wing references in `docs/validation/durrant-reference.json`
and `docs/validation/durrant-low-speed-reference.json` are transcribed from
Matthew Durrant (2024), *Aeroelastic Instability of
Reduced-scale High-altitude Pseudo-satellite Wings*, author-deposited version
[10.6084/m9.figshare.26317378.v1](https://doi.org/10.6084/m9.figshare.26317378.v1),
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The transcription
and reconstructed inputs are identified in the accompanying study; they are
not asserted to be the author's exact computational models. The full thesis
is fetched separately and is excluded from the distributed archives.
