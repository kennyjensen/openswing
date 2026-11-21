# OpenSwing

OpenSwing is a browser-based solver for the coupled aerodynamics and structural
response of flexible aircraft. It independently implements methods published by
Mark Drela for ASWING. The numerical solver runs locally in the browser through
WebAssembly. [Open the workbench](https://openswing.vibefoil.com/).

## Main features

- **Aircraft modeling.** Open and save ASWING `.asw` files. Edit beam properties,
  mesh nodes, and mass properties in the workbench.
- **Steady aerodynamics and flight trim.** Compute rigid aerodynamic loads or
  solve for elastic equilibrium with aerodynamic loads and structural deflection
  coupled together. Trim the aircraft for steady flight.
- **Dynamics and stability.** Run nonlinear time responses to control inputs or
  gusts. Compute coupled eigenmodes, track stability with airspeed, and plot
  linear frequency responses around a solved operating point.
- **Visualization.** Inspect the aircraft and its deformed shape in 3D, plot
  aerodynamic and structural quantities along a beam, and review total forces
  and moments. Export still views as PDFs and animations as GIFs.

ASWING compatibility and validation are ongoing. See the
[ISAE comparison status](docs/validation/ISAE_STATUS.md) for coverage and
remaining differences.

## Run locally

From the repository root, use Node.js 22.12 or newer (24 recommended) and
Python 3.12 or newer.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install matplotlib
npm ci
npm start
```

Open **http://127.0.0.1:8000**. The build uses Matplotlib to render the
validation progress charts. The first build downloads the browser's
numerical runtime. For development, run `npm run dev` after the initial build
and open the URL it prints.

To use the prebuilt version, download the [local app ZIP](https://openswing.vibefoil.com/openswing-local.zip),
extract the ZIP, and run this command from the extracted folder:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open the same address. The prebuilt bundle works offline and only needs Python
to serve the files.

## ASWING references and credits

Mark Drela at MIT developed [ASWING](https://web.mit.edu/drela/Public/web/aswing/)
and published the methods on which OpenSwing is based. The primary references are:

- Mark Drela, *ASWING 5.99 Technical Description* (2015).
  [Steady Formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
  and [Unsteady Extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
- Mark Drela, *Integrated Simulation Model for Preliminary Aerodynamic,
  Structural, and Control-Law Design of Aircraft*, AIAA 99-1394 (1999).
  [Paper](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf).
- Mark Drela, *Method for Simultaneous Wing Aerodynamic and Structural Load
  Prediction*, AIAA 89-2200 (1989).
  [Paper](https://hpaextend.web.fc2.com/HPA_Extend/ji_shu_ji_shi_files/AIAA-1989-2200-903.pdf).
- Mark Drela, *Analysis of Exact and ROM Bode Responses for Alternative State
  Vector Definitions* (2008).
  [Technical note](https://web.mit.edu/drela/Public/web/aswing/rom_bode_test.pdf).
- Mark Drela, [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
  and [CG and inertia calculation note](https://web.mit.edu/drela/Public/web/aswing/CG_Calc.pdf).

Thanks to Romain Jan for publishing the ISAE validation cases and reports, and
to Leonardo Avoni for the extended ASWING manual. The
[reference index](docs/validation/aswing-authoritative-references.md) lists
these resources and related studies.

[Project guide](docs/PROJECT_GUIDE.md) · [GitHub Pages setup](docs/GITHUB_PAGES.md) ·
[MIT license for OpenSwing code](LICENSE) · [Third-party attribution](THIRD_PARTY.md)
