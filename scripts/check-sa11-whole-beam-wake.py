"""Check saved wake accounting and analytically separate offset root rays."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
norm = lambda v: math.sqrt(math.fsum(float(x)**2 for x in v))


def ray(point, origin, beta):
    """PG body-x semi-infinite vortex per unit circulation, zero core."""
    x = (point[0]-origin[0])/beta
    y, z = point[1]-origin[1], point[2]-origin[2]
    r2 = y*y+z*z
    assert r2 > 0
    factor = (1+x/math.sqrt(x*x+r2))/(4*math.pi*r2)
    return [0., -z*factor, y*factor]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    folder = parser.parse_args().input.resolve()
    output = folder/'verification.json'
    assert not output.exists()
    analysis = read(folder/'analysis.json')
    plan = read(folder/'plan.json')
    for name, pin in plan['pins'].items(): assert sha(ROOT/name) == pin, name
    for name, pin in analysis['artifact_sha256'].items(): assert sha(folder/name) == pin, name
    assert analysis['physical_solves'] == analysis['accepted_loads'] == analysis['primary_passes_added'] == 0
    errors = dict(force_accounting=0., percent=0., decomposition=0., ray_velocity=0., ray_decomposition=0.)
    roots = []
    for row in analysis['cases']:
        path = ROOT/row['source_report']
        assert sha(path) == row['source_report_sha256']
        report = read(path)
        for name, pin in report['artifact_sha256'].items(): assert sha(path.parent/name) == pin, name
        replays = row['replays']
        for key in ('CDi','efficiency'):
            error = 100*(replays['whole-new'][key]/row['target'][key]-1)
            errors['percent'] = max(errors['percent'], abs(error-row['errors_percent'][key]))
            a,b,c,d = [replays[k][key] for k in ('native-old','whole-old','native-new','whole-new')]
            s = row['symmetric_decomposition'][key]
            errors['decomposition'] = max(errors['decomposition'], abs(s['receiver']+s['circulation']-(d-a)))
        # The last term must be retained: CD-CDi does not isolate profile drag.
        reconstructed = replays['whole-new']['CDi']+row['near_vortex_minus_trefftz']+row['formal_profile_CD']
        errors['force_accounting'] = max(errors['force_accounting'], abs(reconstructed-row['formal_near_CD']))
        failure = read(path.parent/'openswing-rejected.json')['details']
        assert failure['kind'] == 'section_normal_mach' and failure['maximum']['beam'] == 2
        observed = failure['vortex_breakdown']
        sources = observed['wake_sources'][:2]
        assert [s['sources'][0]['beam'] for s in sources] == [1,2]
        assert [s['sources'][0]['endpoint'] for s in sources] == ['b','a']
        assert all(s['source_count'] == 1 and s['core_radius'] == 0 for s in sources)
        main, winglet = sources
        assert main['origin'][1:] == winglet['origin'][1:]
        gm, gu = main['net_circulation'], -winglet['net_circulation']
        assert gm > gu > 0
        beta = math.sqrt(1-(240./failure['sound_speed'])**2)
        point = observed['influence_receiver']
        km, ku = [ray(point, s['origin'], beta) for s in sources]
        for strength, kernel, saved in ((gm,km,main),(-gu,ku,winglet)):
            errors['ray_velocity'] = max(errors['ray_velocity'], *(abs(strength*k-v) for k,v in zip(kernel,saved['velocity'])))
        connector = [gm*(m-u) for m,u in zip(km,ku)]
        imbalance = [(gm-gu)*u for u in ku]
        pair = [math.fsum([a,b]) for a,b in zip(main['velocity'],winglet['velocity'])]
        errors['ray_decomposition'] = max(errors['ray_decomposition'], *(abs(a+b-c) for a,b,c in zip(connector,imbalance,pair)))
        with np.load(path.parent/'whole-new.npz') as f:
            invalid = np.flatnonzero(f['mach'] >= 1)
            assert len(invalid) == 2
            i = next(int(i) for i in invalid if f['beam'][i] == 2)
            span = f['span'][i].tolist()
        total = failure['maximum']['relative_velocity']
        altered = [v-d for v,d in zip(total,imbalance)]
        dot = math.fsum(a*b for a,b in zip(altered,span))
        altered_normal_mach = norm([v-dot*s for v,s in zip(altered,span)])/failure['sound_speed']
        roots.append(dict(alpha=row['alpha'], streamwise_origin_offset_m=winglet['origin'][0]-main['origin'][0],
            main_ray_distance_m=main['physical_ray_distance'], main_gamma=gm, winglet_gamma=gu,
            signed_jump_percent_of_main=100*(gm-gu)/gm,
            main_ray_speed=norm(main['velocity']), winglet_ray_speed=norm(winglet['velocity']),
            connector_velocity=connector, imbalance_velocity=imbalance,
            connector_speed=norm(connector), imbalance_speed=norm(imbalance), pair_speed=norm(pair),
            actual_local_mach=failure['maximum']['normal_mach'],
            algebraic_without_imbalance_mach=altered_normal_mach,
            scope='Exact root-ray decomposition only. Subtracting the imbalance term alone is not a consistent circulation solution or a proposed correction. All other bound/wake/incident terms are retained in the conditional scalar.'))
    assert len(roots) == 21
    assert errors['ray_velocity'] < 2e-8 and errors['ray_decomposition'] < 2e-8
    assert max(errors[k] for k in ('force_accounting','percent','decomposition')) < 2e-14
    record = dict(verified_utc=datetime.now(timezone.utc).isoformat(), errors=errors, cases=21,
        source_pins_verified=len(plan['pins']), analysis_sha256=sha(folder/'analysis.json'),
        script_sha256=sha(Path(__file__)), root_ray_attribution=roots,
        new_solves=0, accepted_loads=0, primary_passes_added=0,
        finding='Trefftz and near-field quantities retain separate definitions. The close-force whole-beam states retain the offset-root connector field; cancelling only the root-ray imbalance is not a consistent solution.')
    output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(errors=errors, roots=[r for r in roots if r['alpha'] in (0.,5.)])),flush=True)


if __name__ == '__main__': main()
