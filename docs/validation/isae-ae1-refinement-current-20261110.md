# AE-1 final spacing checkpoint before switching to AE-2

Observed 2026-11-10 UTC. The three nominal-160 probes already underway
completed successfully. All 87 physical checks pass. These supplement the
[40/80 spacing diagnostic](isae-ae1-spacing-current-20261110.md); they add no
primary comparison votes and change no production settings or equations.

Signed tip-Z error at the original 5° / 17 m/s coordinate, in micrometres:

| Node mapping | Nominal 40 | Nominal 80 | Nominal 160 |
|---|---:|---:|---:|
| Current cosine | +34.802 | +31.683 | +30.900 |
| Drela 1989 mapping over the whole beam | −38.614 | −5.161 | +12.220 |
| Drela 1989 mirror-half mapping | +12.118 | +20.518 | +25.346 |

The current cosine mesh's last change is 0.783 µm, while its native discrepancy
remains 30.900 µm. The whole-beam mapping's unusually close nominal-80 result
does not persist at nominal 160. Choosing that grid for its agreement would
therefore be unjustified. The documented historical node arrays remain unknown.

The default-versus-explicit cosine preflight agrees to less than 8e−15 across
all ten checked mesh arrays. The subsequent assessment independently binds the
saved cold solve, restored residual, force/moment balance and sensor values;
it performs no new physical solve. All three worker processes exited zero and
were reaped, without retries.

AE-1 remains **1,170/1,200** at 5%, with its six crossover failures and 24
unavailable startup values retained. Further AE-1 work is deferred at the
user's request to focus on AE-2.

[Plan](../../artifacts/isae/ae1-spacing-refinement-20261110/plan.json) ·
[Cosine preflight](../../artifacts/isae/ae1-spacing-refinement-20261110/cosine-check.json) ·
[Saved-data assessment](../../artifacts/isae/ae1-spacing-refinement-20261110/assessment.json)
