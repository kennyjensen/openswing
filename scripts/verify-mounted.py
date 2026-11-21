"""Reproduce the mounted flexible-wing mesh study; not an ASWING benchmark."""
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

source = Path("examples/flexible.asw").read_bytes()
condition = FlightCondition(speed=30, alpha=5, beta=0, mach=0)
model = parse_asw(source.decode())
rows = []
for panels in (12, 24, 48):
    start = time.monotonic()
    result = solve_static(model, condition, panels=panels)
    row = {key: result[key] for key in ("panels", "structural_nodes", "CL", "CD", "Cm", "max_displacement",
                                       "max_rotation_deg", "residual", "force_balance", "moment_balance")}
    row["requested_panels_per_beam"] = panels
    rows.append(row)
    print(f"{panels} panels: CL={result['CL']:.9f}, displacement={result['max_displacement']:.9f}, {time.monotonic()-start:.1f}s", flush=True)

output = {
    "description": "Internal discretization study, not validation against ASWING or experimental data.",
    "source": "examples/flexible.asw", "source_sha256": hashlib.sha256(source).hexdigest(),
    "condition": {"speed": 30, "alpha": 5, "beta": 0, "mach": 0, "stall": True, "gravity": [0, 0, -model.constants[0]]},
    "units": "Consistent input units (m, s, N in this example).",
    "numpy": np.__version__, "scipy": scipy.__version__, "rows": rows,
}
destination = Path("docs/validation/mounted-flexible.json")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(output, indent=2, allow_nan=False)+"\n")
print(destination)
