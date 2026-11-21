"""Plot actual material-node locations before and after mesh redistribution."""
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-regular-mesh-20261114'


def plot(folder,args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    old=read(STUDY/'mesh/previous-nodes.json')['beams']
    new=read(STUDY/'mesh/regular-nodes.json')['beams']
    rows=read(STUDY/'mesh/result.json')['rows']
    fig,axes=plt.subplots(5,2,figsize=(10,7),layout='constrained')
    colors=['#c6302e','#af6200','#188442','#007f98','#285eb7']
    for i,color in enumerate(colors):
        for j,(name,beams) in enumerate([('previous',old),('regular',new)]):
            b=beams[i];ax=axes[i,j];positions=[n['fraction'] for n in b['nodes']]
            ax.vlines(positions,0,1,color=color,linewidth=1.2)
            ax.hlines([0,1],0,1,color=color,linewidth=.7)
            row=next(r for r in rows if r['mesh']==name and r['beam']==b['beam'])
            ax.set_title(f"{b['name']}: {b['panels']} intervals · gaps {row['minimum']:.3g}–{row['maximum']:.3g} ft",fontsize=9,loc='left')
            ax.set(xlim=(-.015,1.015),ylim=(-.05,1.05),xticks=[],yticks=[])
            for spine in ax.spines.values():spine.set_visible(False)
    fig.suptitle('Daedalus chord-line station spacing: previous (left), redistributed (right)\nEach component spans its own full material length; short required tip panels remain',fontsize=11)
    fig.savefig(folder/'spacing.svg');fig.savefig(folder/'spacing.png',dpi=150);plt.close(fig)
    return dict(source='Actual mesh node fractions; no smoothing or omitted stations',components=5)


if __name__=='__main__':
    inputs=[STUDY/'mesh'/name for name in ('previous-nodes.json','regular-nodes.json','result.json')]
    run(STUDY,'plot',inputs,plot,{},__file__)
