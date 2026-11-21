// Metadata from the pinned kernel time_history.py; see tests/fixtures/time-history-catalog.json.
// These labels describe inverse target ownership, not prescribed frame replacement.
export const historyTargets=Object.freeze([
  {
    "quantity": "reference.equivalent_airspeed",
    "label": "V",
    "table_unit": "input L/T",
    "target_unit": "input L/T",
    "factor": 1.0,
    "semantics": "Gust-relative airspeed at the body velocity reference times sqrt(rho/rho0); low-speed equivalent-airspeed convention, not proven executable IAS parity.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "reference.alpha",
    "label": "A",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "Gust-relative alpha at the body velocity reference; excludes induced and local elastic flow.",
    "derivative_order": 1,
    "periodic": true,
    "label_kind": "documented global label"
  },
  {
    "quantity": "reference.beta",
    "label": "B",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "Gust-relative beta at the body velocity reference; excludes induced and local elastic flow.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "flight_path",
    "label": "Ga",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "Climb angle of stationary-air Earth velocity at the velocity reference; original ASW reference-point parity is unresolved.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "rates.x",
    "label": "Wx",
    "table_unit": "deg/input T",
    "target_unit": "rad/input T",
    "factor": 0.017453292519943295,
    "semantics": "Body angular-velocity vector component; not an Euler-angle rate.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "position_earth.x",
    "label": "RX",
    "table_unit": "input L",
    "target_unit": "input L",
    "factor": 1.0,
    "semantics": "Body-origin Earth position; not the velocity-reference position.",
    "derivative_order": 2,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "rates.y",
    "label": "Wy",
    "table_unit": "deg/input T",
    "target_unit": "rad/input T",
    "factor": 0.017453292519943295,
    "semantics": "Body angular-velocity vector component; not an Euler-angle rate.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "position_earth.y",
    "label": "RY",
    "table_unit": "input L",
    "target_unit": "input L",
    "factor": 1.0,
    "semantics": "Body-origin Earth position; not the velocity-reference position.",
    "derivative_order": 2,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "rates.z",
    "label": "Wz",
    "table_unit": "deg/input T",
    "target_unit": "rad/input T",
    "factor": 0.017453292519943295,
    "semantics": "Body angular-velocity vector component; not an Euler-angle rate.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "position_earth.z",
    "label": "RZ",
    "table_unit": "input L",
    "target_unit": "input L",
    "factor": 1.0,
    "semantics": "Body-origin Earth position; not the velocity-reference position.",
    "derivative_order": 2,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "attitude.bank",
    "label": "Ex",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "ASW principal Euler chart R=Rz(-heading) Ry(elevation) Rx(-bank); nonsingular elevation required.",
    "derivative_order": 2,
    "periodic": true,
    "label_kind": "documented global label"
  },
  {
    "quantity": "attitude.elevation",
    "label": "Ey",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "ASW principal Euler chart R=Rz(-heading) Ry(elevation) Rx(-bank); nonsingular elevation required.",
    "derivative_order": 2,
    "periodic": false,
    "label_kind": "documented global label"
  },
  {
    "quantity": "attitude.heading",
    "label": "Ez",
    "table_unit": "deg",
    "target_unit": "deg",
    "factor": 1.0,
    "semantics": "ASW principal Euler chart R=Rz(-heading) Ry(elevation) Rx(-bank); nonsingular elevation required.",
    "derivative_order": 2,
    "periodic": true,
    "label_kind": "documented global label"
  },
  {
    "quantity": "velocity_earth.x",
    "label": "velocity_earth.x",
    "table_unit": "input L/T",
    "target_unit": "input L/T",
    "factor": 1.0,
    "semantics": "Stationary-air Earth velocity at the body velocity reference, R(U_origin + Omega cross r_v).",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "velocity_earth.y",
    "label": "velocity_earth.y",
    "table_unit": "input L/T",
    "target_unit": "input L/T",
    "factor": 1.0,
    "semantics": "Stationary-air Earth velocity at the body velocity reference, R(U_origin + Omega cross r_v).",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "velocity_earth.z",
    "label": "velocity_earth.z",
    "table_unit": "input L/T",
    "target_unit": "input L/T",
    "factor": 1.0,
    "semantics": "Stationary-air Earth velocity at the body velocity reference, R(U_origin + Omega cross r_v).",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "rates_earth.x",
    "label": "rates_earth.x",
    "table_unit": "rad/input T",
    "target_unit": "rad/input T",
    "factor": 1.0,
    "semantics": "Earth angular-velocity vector R Omega, in radians per input time.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "rates_earth.y",
    "label": "rates_earth.y",
    "table_unit": "rad/input T",
    "target_unit": "rad/input T",
    "factor": 1.0,
    "semantics": "Earth angular-velocity vector R Omega, in radians per input time.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "rates_earth.z",
    "label": "rates_earth.z",
    "table_unit": "rad/input T",
    "target_unit": "rad/input T",
    "factor": 1.0,
    "semantics": "Earth angular-velocity vector R Omega, in radians per input time.",
    "derivative_order": 1,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "acceleration_earth.x",
    "label": "acceleration_earth.x",
    "table_unit": "input L/T^2",
    "target_unit": "input L/T^2",
    "factor": 1.0,
    "semantics": "Absolute acceleration at the acceleration reference, resolved in Earth axes; not body-origin acceleration or a body-velocity derivative.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "acceleration_earth.y",
    "label": "acceleration_earth.y",
    "table_unit": "input L/T^2",
    "target_unit": "input L/T^2",
    "factor": 1.0,
    "semantics": "Absolute acceleration at the acceleration reference, resolved in Earth axes; not body-origin acceleration or a body-velocity derivative.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "acceleration_earth.z",
    "label": "acceleration_earth.z",
    "table_unit": "input L/T^2",
    "target_unit": "input L/T^2",
    "factor": 1.0,
    "semantics": "Absolute acceleration at the acceleration reference, resolved in Earth axes; not body-origin acceleration or a body-velocity derivative.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "angular_acceleration_earth.x",
    "label": "angular_acceleration_earth.x",
    "table_unit": "rad/input T^2",
    "target_unit": "rad/input T^2",
    "factor": 1.0,
    "semantics": "Absolute angular-acceleration vector in Earth axes, in radians per squared input time.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "angular_acceleration_earth.y",
    "label": "angular_acceleration_earth.y",
    "table_unit": "rad/input T^2",
    "target_unit": "rad/input T^2",
    "factor": 1.0,
    "semantics": "Absolute angular-acceleration vector in Earth axes, in radians per squared input time.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  },
  {
    "quantity": "angular_acceleration_earth.z",
    "label": "angular_acceleration_earth.z",
    "table_unit": "rad/input T^2",
    "target_unit": "rad/input T^2",
    "factor": 1.0,
    "semantics": "Absolute angular-acceleration vector in Earth axes, in radians per squared input time.",
    "derivative_order": 0,
    "periodic": false,
    "label_kind": "explicit canonical extension"
  }
].map(item=>Object.freeze(item)));
