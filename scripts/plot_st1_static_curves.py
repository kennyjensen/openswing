"""Plot saved ST-1 ASWING static-curve comparisons; no new solves."""
import csv
from decimal import Decimal
from pathlib import Path

import verify_sa14_defaults as common


def main():
    common.bounded()
    out=common.ROOT/'artifacts/isae/st1-static-curves-20261109'
    current=common.read(out/'summary.json')
    earlier=common.read(common.ROOT/'artifacts/isae/st1-coupled-orientations-20261109/summary.json')
    first=common.read(common.ROOT/'artifacts/isae/st1-coupled-curve-20261109/summary.json')
    rows=current['rows']+[dict(r,case='coupled-'+r['case']) for r in earlier['rows']]+[dict(r,case='coupled-m45') for r in first['rows']]
    assert len(rows)==current['combined_required']==201
    assert sum(r['passed'] for r in rows)==current['combined_passed']
    plan=common.read(out/'plan-v2.json')
    # Independent Decimal replay of all newly extracted y coordinates/decisions.
    for r in current['rows']:
        axis=plan['cases'][r['case']]['axes']['y']
        expected=(Decimal(str(r['point_scale']))*Decimal(r['original_y_token'])-Decimal(str(axis['offset'])))/Decimal(str(axis['scale']))
        assert abs(expected-Decimal(str(r['expected'])))<Decimal('2e-16')
        error=abs(Decimal(str(r['predicted']))-expected)
        allowance=max(Decimal(str(r['original_absolute_tolerance'])),Decimal('.05')*abs(expected))
        assert bool(error<=allowance)==r['passed']
    fields=['case','mass','axis','expected','predicted','error_m','error_percent','original_absolute_tolerance','passed']
    with (out/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({k:r.get(k) for k in fields} for r in rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=[('cross-0','[0/90]3s · 0°'),('cross-45','[0/90]3s · 45°'),
           ('angle-0','[20/−70/−70/20]2a · 0°'),('angle-45','[20/−70/−70/20]2a · 45°'),
           ('coupled-m45','[45/0]3s · −45°'),('coupled-0','[45/0]3s · 0°'),
           ('coupled-45','[45/0]3s · 45°'),('twisted-0','[45/0]3a · 0°'),('twisted-45','[45/0]3a · 45°')]
    fig,axes=plt.subplots(3,3,figsize=(11,10))
    for ax,(name,title) in zip(axes.flat,cases,strict=True):
        for axis,color in zip('xyz',('#265dcc','#c83232','#202020'),strict=True):
            selected=sorted((r for r in rows if r['case']==name and r['axis']==axis),key=lambda r:r['mass'])
            assert selected
            ax.plot([r['mass'] for r in selected],[r['expected'] for r in selected],color=color,lw=1.6,label='ASWING '+axis)
            ax.plot([r['mass'] for r in selected],[r['predicted'] for r in selected],linestyle='none',marker='o',markersize=4,
                    markerfacecolor='none',color=color,label='OpenSwing '+axis)
        ax.set_title(title,fontsize=10);ax.set_xlabel('Tip mass (kg)');ax.set_ylabel('|Loaded − unloaded| (m)')
        ax.grid(alpha=.22)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.956),ncol=3,frameon=False)
    fig.suptitle('ST-1 static mechanics · four layouts, nine root conditions',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.90))
    for ext in ('png','svg'):fig.savefig(out/f'comparison.{ext}',dpi=150)
    print('Plotted 201 archived ASWING coordinate comparisons; independently replayed all 138 new decisions.')


if __name__=='__main__':main()
