"""Reproduce the braced twin-prop mesh study; not an ASWING benchmark."""
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static

source = Path("examples/powered.asw").read_bytes()
model = parse_asw(source.decode())
condition = FlightCondition(speed=30, alpha=5, mach=0, powers={1:3000})
rows = []
for panels in (8, 16, 32):
    start = time.monotonic()
    result = solve_static(model, condition, panels=panels, strut_mode="wire")
    row = {key: result[key] for key in ("panels", "structural_nodes", "CL", "CD", "Cm", "max_displacement",
                                       "residual", "force_balance", "moment_balance", "engine_force")}
    row["requested_panels_per_beam"] = panels
    row["strut_tension"] = [s["tension"] for s in result["struts"]]
    row["engine_thrust"] = [e["thrust"] for e in result["engines"]]
    rows.append(row)
    print(f"{panels} panels: CL={result['CL']:.9f}, displacement={result['max_displacement']:.9f}, {time.monotonic()-start:.1f}s", flush=True)
output = dict(description="Internal discretization study, not validation against ASWING or experimental data.",
              source="examples/powered.asw", source_sha256=hashlib.sha256(source).hexdigest(),
              condition=dict(speed=30, alpha=5, beta=0, mach=0, stall=True, powers={1:3000},
                             gravity=[0,0,-model.constants[0]], strut_mode="wire"),
              units="Consistent input units (m, s, N in this example); shaft power is 3000 W per propeller.",
              numpy=np.__version__, scipy=scipy.__version__, rows=rows)
destination = Path("docs/validation/powered-braced.json")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(output, indent=2, allow_nan=False)+"\n")
print(destination)
