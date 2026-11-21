#!/usr/bin/env python3
"""Read-only, stdlib-only arithmetic on retained SCN text, with no model import."""
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / '.reference/sa1-public-history-20261027/scn-study/SCN'


def pin(p):
    b = p.read_bytes()
    return {'path': str(p.relative_to(ROOT)), 'bytes': len(b), 'sha256': sha256(b).hexdigest()}


def interval(token):
    x = D(token)
    h = D(5).scaleb(x.as_tuple().exponent - 1)
    return (x-h, x+h)


def add(a, b):
    return (a[0]+b[0], a[1]+b[1])


def subtract(a, b):
    return (a[0]-b[1], a[1]-b[0])


def multiply(a, b):
    v = [x*y for x in a for y in b]
    return (min(v), max(v))


def intersection(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1])


def examine(path):
    lines = path.read_text().splitlines()
    rows = []
    for number, line in enumerate(lines, 1):
        tokens = line.split()
        if len(tokens) not in (9, 10):
            continue
        try:
            values = list(map(D, tokens))
        except Exception:
            continue
        rows.append({'line': number, 'tokens': tokens, 'values': values})
    header = next((i for i, line in enumerate(lines) if 'Fn/10' in line), None)
    out = {'source': pin(path), 'rows': len(rows),
           'first_cl': rows[0]['tokens'][7], 'terminal_cl': rows[-1]['tokens'][7],
           'columns': len(rows[0]['tokens']), 'Fn_scale': None,
           'Fn_balance': None, 'f_aero_times_delta_t_diagnostic': None}
    if header is None:
        out['qualification'] = 'Headerless: no force exponent or total-force header inferred from another file.'
        return out
    scale = D(10) ** int(lines[header-1].split()[-1])
    out['Fn_scale'] = scale
    center = next(i for i in range(len(rows)-1)
                  if rows[i]['values'][0] == rows[i+1]['values'][0])
    a, b = rows[center:center+2]
    root_jump = (b['values'][6] - a['values'][6]) * scale
    root_interval = multiply(subtract(interval(b['tokens'][6]), interval(a['tokens'][6])), (scale, scale))
    fz_token = re.search(r'sum Fz\s*:\s*([^ ]+)', '\n'.join(lines)).group(1)
    out['Fn_balance'] = {'root_lines': [a['line'], b['line']], 'root_jump': root_jump,
                         'root_jump_print_interval': root_interval, 'header_sum_Fz_token': fz_token,
                         'header_sum_Fz_print_interval': interval(fz_token),
                         'intervals_overlap': intersection(root_interval, interval(fz_token))}
    if len(rows[0]['tokens']) != 10:
        return out
    total, total_interval = D(0), (D(0), D(0))
    checks = []
    for a, b in zip(rows, rows[1:]):
        dt = b['values'][0] - a['values'][0]
        if dt == 0:
            continue  # duplicate-root interval carries a concentrated jump
        product = a['values'][8] * dt
        product_interval = multiply(interval(a['tokens'][8]), subtract(interval(b['tokens'][0]), interval(a['tokens'][0])))
        force = (a['values'][6] - b['values'][6]) * scale
        force_interval = multiply(subtract(interval(a['tokens'][6]), interval(b['tokens'][6])), (scale, scale))
        checks.append({'lines': [a['line'], b['line']], 'delta_t': dt,
                       'left_f_aero_times_delta_t': product, 'product_print_interval': product_interval,
                       'Fn_decrement': force, 'Fn_decrement_print_interval': force_interval,
                       'intervals_overlap': intersection(product_interval, force_interval)})
        total += product
        total_interval = add(total_interval, product_interval)
    out['f_aero_times_delta_t_diagnostic'] = {
        'assumptions_not_established': 'Treats printed delta-t as ds and printed f_aero as the complete applied normal load. Neither is established by this output alone.',
        'sum': total, 'sum_conservative_print_interval': total_interval,
        'sum_matches_root_jump_within_print_intervals': intersection(total_interval, root_interval),
        'interval_count': len(checks), 'intervals_with_overlapping_print_bounds': sum(c['intervals_overlap'] for c in checks),
        'local_checks': checks}
    return out


def main():
    data = {
        'format': 'openswing.isae.scn-retained-load-audit', 'version': 1,
        'scope': 'Saved text only; no solver, production import, model reconstruction, or fitted constant.',
        'pins': [pin(Path(__file__).resolve()), pin(ROOT/'.reference/aswing_doc.txt'),
                 pin(ROOT/'.reference/asw_theory.txt'), pin(SOURCE/'post_analysis.m')],
        'primary_evidence': [
            {'path': '.reference/aswing_doc.txt', 'lines': [2497, 2501], 'fact': 'D increment zero prints actual structural nodes; otherwise displayed values are interpolated.'},
            {'path': '.reference/aswing_doc.txt', 'lines': [2503, 2509], 'fact': 'f_aero is an aerodynamic lift-force/span diagnostic, with a simple-wing reduction rho V Gamma plus the circulation-rate term.'},
            {'path': '.reference/aswing_doc.txt', 'lines': [2546, 2599], 'fact': 'State variables are nodal. Derived cl/f_aero are midpoint values shifted upward half an output line. The last zeros are dummy.'},
            {'path': '.reference/asw_theory.txt', 'lines': [593, 598], 'pages': [12], 'fact': 'The structural subscript a denotes an arithmetic endpoint average.'},
            {'path': '.reference/asw_theory.txt', 'lines': [642, 655], 'pages': [13, 14], 'fact': 'Equations 55/56 conserve integrated distributed and concentrated loads.'},
            {'path': '.reference/asw_theory.txt', 'lines': [1587, 1619], 'pages': [32], 'fact': 'The aerodynamic section locally defines a as a theta midpoint and locates bound-vortex lift there.'}],
        'files': [examine(p) for p in sorted(SOURCE.glob('*.txt'))],
        'conclusions': [
            'The manual establishes following-interval association independently of any model pairing. A nonzero first cl and dummy-zero final cl do not demonstrate an asymmetric tip boundary condition.',
            'All seven headered outputs have central Fn jumps consistent with their reported sum Fz within original print rounding, using each file own force exponent.',
            'The raw scalar f_aero times delta-t hypothesis fails local printed-interval checks, including coarse cases. It cannot be used to establish exact force integration or endpoint recovery.',
            'Unknown complete geometry/local bases, span metric, velocity, profile force and display interpolation prevent a unique recovery of the internal transfer rule. The explicit midpoint printing convention is established; the structural transfer operator is not.',
            'No claim is made that Rectangular.asw generated the rectangular tables, or that matching CASEI headers prove execution. No new SA1 acceptance targets are registered.',
            'post_analysis.m plots derived values against node y without correcting the documented half-interval print shift, and estimates Gamma using fixed chord/speed; its plot is not an exact archived circulation field.']}
    assert len(data['files']) == 8
    balances = [r['Fn_balance'] for r in data['files'] if r['Fn_balance']]
    assert len(balances) == 7 and all(r['intervals_overlap'] for r in balances)
    (HERE/'report.json').write_text(json.dumps(data, indent=2, default=str)+'\n')
    print(json.dumps({'files': len(data['files']), 'headered_root_balances': len(balances),
                      'all_within_original_print_rounding': True, 'report': pin(HERE/'report.json')}))


if __name__ == '__main__':
    main()
