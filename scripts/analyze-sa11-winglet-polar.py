"""Verify and plot the retained SA-11 polar comparison without new solves."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-winglet-polar-20261108'
SPEC = importlib.util.spec_from_file_location('polar', ROOT/'scripts/verify-sa11-winglet-polar.py')
POLAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLAR)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def main():
    plan = read(BASE/'plan.json')
    POLAR.check(plan)
    assert sha(BASE/'driver-used.py') == plan['driver_sha256']
    table = np.loadtxt(POLAR.TABLE)
    first_fields = tangent = None
    rows, pins = [], {}
    geometry_errors, force_errors, new_native_seconds, new_production_seconds = [], [], [], []
    for case in plan['cases']:
        path = ROOT/case['reused_report'] if 'reused_report' in case else BASE/case['id']/'report.json'
        if 'reused_report' in case:
            assert sha(path) == case['reused_sha256']
        pins[str(path.relative_to(ROOT))] = sha(path)
        report = read(path)
        for name, pin in report['artifact_sha256'].items():
            assert sha(path.parent/name) == pin, name
        assert read(path.parent/'process.json')['returncode'] == 0
        with np.load(path.parent/'native-fields.npz') as archive:
            f = {name:archive[name].copy() for name in archive.files}
        if first_fields is None:
            first_fields = f
            model = POLAR.INC.model_at(case['twist'])
            _, segments = POLAR.INC.CONVERT.conversion(model, 1)
            meshes, _, _, _ = POLAR.INC.CONVERT.mapped_meshes(model, f, segments)
            tangent = np.concatenate([mesh.frames[...,1] for mesh in meshes])
        geom_error = max(float(np.max(abs(f[key]-first_fields[key]))) for key in ('RV1','RV2','RV','RC'))
        assert geom_error < 1e-14
        geometry_errors.append(geom_error)
        angle = np.deg2rad(case['alpha'])
        freestream = np.array([np.cos(angle),0.,np.sin(angle)])
        assert np.max(abs(f['VINF']-freestream)) < 1e-14
        force = np.sum(2*f['GAM']*np.cross(f['VINF']+f['VV'],f['RV2']-f['RV1']),axis=0)/.9329
        force_error = max(abs(float(force@[-np.sin(angle),0.,np.cos(angle)])-report['native']['CL']),
                          abs(float(force@freestream)-report['native']['CD_near']))
        assert force_error < 1e-12
        force_errors.append(force_error)
        native_v = 240*(f['VINF']+f['VV'])
        normal = native_v-np.sum(native_v*tangent,axis=1)[:,None]*tangent
        native_mach = float(np.linalg.norm(normal,axis=1).max()/340.21)
        state = report['production']
        assert state['status'] == 'rejected' and state['details']['kind'] == 'section_normal_mach'
        assert state['residual'] < 1e-8
        assert not (path.parent/'openswing.json').exists()
        with np.load(path.parent/'diagnostic-state.npz') as diagnostic:
            gamma, velocity, margin = [diagnostic[key] for key in ('gamma','velocity','stall_margin')]
            relative_gamma_error = float(np.max(abs(gamma/240-f['GAM'].ravel()))/np.max(abs(f['GAM'])))
            vp = velocity-np.sum(velocity*tangent,axis=1)[:,None]*tangent
            mach = float(np.linalg.norm(vp,axis=1).max()/340.21)
            min_margin = float(margin.min()/.05)
            assert np.sum(margin<0) == report['stalled_strips'] == 0
            assert abs(relative_gamma_error-report['native_production_gamma_relative_linf']) < 1e-14
            assert abs(min_margin-report['minimum_stall_margin_widths']) < 1e-12
            assert abs(mach-state['maximum_section_normal_mach']) < 1e-12
        reference = dict(CL=float(table[case['row'],77]), CD=float(table[case['row'],78]), CDi=float(table[case['row'],79]))
        assert reference == report['reference']
        for key in ('CL','CDi'):
            assert abs(100*(report['native'][key]/reference[key]-1)-report['native_error_percent'][key]) < 1e-12
        labels = POLAR.INC.CONVERT.MATCHED.NATIVE.labeled(path.parent/'total.txt')
        assert abs(labels["Mach, rb/2V, r'b/2V"][0]-240/340.21) < 1e-14
        assert labels['Trefftz Plane: CLff, CDff, CYff, e'][1] == report['native']['CDi']
        rows.append(dict(case=case, native=report['native'], reference=reference,
            error_percent=report['native_error_percent'], maximum_production_mach=mach,
            maximum_native_mach_using_asw_axis=native_mach, circulation_residual=state['residual'],
            circulation_relative_linf_error_percent=100*relative_gamma_error,
            minimum_stall_margin_widths=min_margin, production_status=state['status']))
        if 'reused_report' not in case:
            new_native_seconds.append(read(path.parent/'process.json')['seconds'])
            new_production_seconds.append(report['openswing_seconds'])
    assert len(rows) == 42 and len(new_native_seconds) == 40
    summary = {}
    for twist in (4., -4.):
        selected = [r for r in rows if r['case']['twist'] == twist]
        assert [r['case']['alpha'] for r in selected] == list(np.arange(21)*.25)
        summary[str(twist)] = dict(angles=21,
            errors_percent={key:dict(minimum=min(r['error_percent'][key] for r in selected),
                                    maximum=max(r['error_percent'][key] for r in selected)) for key in ('CL','CDi')},
            maximum_circulation_relative_linf_error_percent=max(r['circulation_relative_linf_error_percent'] for r in selected),
            minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in selected),
            maximum_production_mach_range=[min(r['maximum_production_mach'] for r in selected),max(r['maximum_production_mach'] for r in selected)],
            maximum_native_mach_range=[min(r['maximum_native_mach_using_asw_axis'] for r in selected),max(r['maximum_native_mach_using_asw_axis'] for r in selected)])
    for name in ('verify-sa11-winglet-polar.py','analyze-sa11-winglet-polar.py'):
        ast.parse((ROOT/'scripts'/name).read_text())
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows, summary=summary,
        report_sha256=pins, unchanged_pins=plan['unchanged_pins'], new_native_calls=40, new_production_calls=40,
        reused_pairs=1, maximum_geometry_change=max(geometry_errors), maximum_force_reconstruction_error=max(force_errors),
        maximum_circulation_residual=max(r['circulation_residual'] for r in rows),
        new_native_seconds=sum(new_native_seconds), new_production_seconds=sum(new_production_seconds),
        primary_status='SA-11 remains163/4592; no registered fraction or scope changes. All42 production states are local-Mach rejections.',
        limitation='Native vortex CL excludes profile-force lift. The report-minus4 comparison stays well below section lift limits; the literal-plus4 cases approach the soft stall transition. No archived producing input is authenticated and no production result is accepted.')
    output = BASE/'analysis.json'
    assert not output.exists()
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    plot(rows)
    print(json.dumps({key:result[key] for key in ('summary','maximum_geometry_change','maximum_force_reconstruction_error','maximum_circulation_residual','new_native_seconds','new_production_seconds')}))


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    palette = ROOT/'web/plot-colors.js'
    colors = re.findall(r"'(#\w+)'",palette.read_text().split('export const plotColors')[1].split(']);')[0])
    fig, axes = plt.subplots(2,2,figsize=(11.3,7.6),sharex=True)
    for column, (key, label) in enumerate([('CL','Lift coefficient CL'),('CDi','Trefftz induced drag CDi')]):
        for index, (twist, name) in enumerate([(4.,'Original +4°'),(-4.,'Report −4°')]):
            selected = [r for r in rows if r['case']['twist'] == twist]
            x = [r['case']['alpha'] for r in selected]
            axes[0,column].plot(x,[r['native'][key] for r in selected],color=colors[index],label=f'Native AVL: {name}',lw=1.8)
            axes[1,column].plot(x,[r['error_percent'][key] for r in selected],color=colors[index],label=name,lw=1.8)
        axes[0,column].scatter(x,[r['reference'][key] for r in selected],color='#222222',s=19,marker='x',label='Archived ASWING',zorder=4)
        axes[0,column].set_ylabel(label)
        axes[1,column].set_ylabel('Signed error versus archive (%)')
        axes[1,column].set_xlabel('Aircraft angle of attack (degrees)')
        axes[1,column].axhline(0,color='#555555',ls=':',lw=1)
        axes[1,column].text(.97,.95, f"Report −4°: max |error| {max(abs(r['error_percent'][key]) for r in selected):.3f}%",
                            transform=axes[1,column].transAxes,ha='right',va='top',fontsize=9,
                            bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
    for ax in axes.ravel():
        ax.grid(alpha=.25); ax.set_xlim(0,5)
    fig.suptitle('SA-11 upper winglets: report/file twist-sign comparison\n240 m/s; 64 matched vortices; original archived rows at 0.25° intervals',fontsize=12)
    axes[0,0].legend(fontsize=8,loc='upper left')
    fig.text(.5,.025,'Native AVL comparisons only. All 42 OpenSwing states still fail the local Mach check; no new ISAE passes.',
             ha='center',fontsize=9)
    fig.subplots_adjust(top=.88,bottom=.12,left=.08,right=.97,hspace=.23,wspace=.28)
    artifacts = {}
    for suffix in ('png','svg'):
        file = BASE/f'winglet-polar.{suffix}'; assert not file.exists()
        fig.savefig(file,dpi=160); artifacts[str(file.relative_to(ROOT))] = sha(file)
    plt.close(fig)
    (BASE/'plot-verification.json').write_text(json.dumps(dict(analysis_sha256=sha(BASE/'analysis.json'),
        script_sha256=sha(Path(__file__)),palette_sha256=sha(palette),artifacts=artifacts),indent=2)+'\n')


if __name__ == '__main__':
    main()
