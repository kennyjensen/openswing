"""Compare all original SA-11 speed pairs using printed uncertainty intervals.

This source-only audit infers no exact PG Mach and changes no test setup.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/sa11-complete-scope-20261108'
OUT = ROOT / 'artifacts/isae/sa11-speed-signature-20261108'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
FIELDS = dict(CL=77, CD=78, CDi=79, Cm=80, efficiency=81)


def interval(token):
    value = Decimal(token)
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    return value, value-half, value+half


def main():
    assert not OUT.exists(), OUT
    plan = read(BASE / 'plan.json')
    assert sha(BASE / 'plan.json') == read(BASE / 'analysis.json')['plan_sha256']
    groups, pins = [], {}
    for variant in ('wing_alone', 'wing_extension', 'wingtip_up', 'wingtip_up_and_down'):
        for labels in (('0_75', '0_78'), ('0_70', '0_80')):
            pairs, commands = [], []
            for label in labels:
                jobs = sorted((j for j in plan['jobs'] if j['variant'] == variant
                               and j['mach_label'] == label and j['settings']['panels'] == 64),
                              key=lambda j: j['row_index'])
                assert len(jobs) == 41
                job = jobs[0]
                for source in job['sources']:
                    assert sha(ROOT / source['path']) == source['sha256'], source['path']
                    pins[source['path']] = source['sha256']
                # Re-read original tokens; do not depend on a computed prediction.
                lines = (ROOT / job['table_path']).read_text().splitlines()
                rows = [s.split() for s in lines if len(s.split()) == 82 and s.split()[0].isdigit()]
                assert rows == [j['reference_row']['tokens'] for j in jobs]
                pairs.append(rows)
                commands.append(dict(label=label, speed=job['settings']['speed'],
                                     commands=job['driver_declarations']['settings_commands'],
                                     path=job['driver_path']))
            comparisons = []
            for row_a, row_b in zip(*pairs):
                assert Decimal(row_a[71]) == Decimal(row_b[71])
                assert Decimal(row_a[69]) == Decimal(str(commands[0]['speed']))
                assert Decimal(row_b[69]) == Decimal(str(commands[1]['speed']))
                fields = {}
                for name, col in FIELDS.items():
                    a, alo, ahi = interval(row_a[col])
                    b, blo, bhi = interval(row_b[col])
                    fields[name] = dict(tokens=[row_a[col], row_b[col]],
                                        intervals_overlap=max(alo, blo) <= min(ahi, bhi),
                                        signed_change_percent=float(100*(b-a)/abs(a)))
                comparisons.append(dict(alpha=float(row_a[71]), fields=fields))
            groups.append(dict(variant=variant, labels=labels, commands=commands,
                               rows=comparisons, summary={name: dict(
                                   rows=41, overlapping_printed_intervals=sum(r['fields'][name]['intervals_overlap'] for r in comparisons),
                                   maximum_absolute_change_percent=max(abs(r['fields'][name]['signed_change_percent']) for r in comparisons))
                                   for name in FIELDS}))
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), groups=groups,
                  source_sha256=pins, plan_sha256=sha(BASE / 'plan.json'),
                  script_sha256=sha(Path(__file__)), new_solver_calls=0,
                  inference='For three configurations, all41 CL/CD/CDi/efficiency intervals overlap between255 and266m/s while no Cm intervals overlap. Their matching drivers omit KK/MM; the upper/lower drivers include them and all five channels change. This supports a fixed globalPG versus speed-dependent globalPG distinction. FixedPG need not be zero, and unknown original geometry/startup prevents an authenticated setting claim.',
                  source_equations='Steady equations64-73,150-161; user guide local sectionCm PG is always computed independently of selected globalPG. Fixed-geometry nondimensional loads can be speed-invariant at fixedPG while sectionCm varies with true speed.',
                  normalization_conflicts_resolved=False, primary_scope_changed=False,
                  production_changed=False, recovered_native_pg_value=None)
    OUT.mkdir(parents=True)
    (OUT / 'analysis.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    (OUT / 'audit-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps([dict(variant=g['variant'], labels=g['labels'], summary=g['summary']) for g in groups]))


if __name__ == '__main__':
    main()
