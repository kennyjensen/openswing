"""Show the first torsional shape's documented root sign change."""
import verify_st1_modal_mechanics as modal

common=modal.common


def run():
    common.bounded()
    out=common.ROOT/'artifacts/isae/st1-thin-modal-reconstruction-20261109'
    data=common.read(out/'summary.json')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for row,style,color in zip(data['torsion_shapes'],('o-','-'),('#3076a9','#df7235'),strict=True):
        for ax in axes:
            ax.plot(row['span_from_clamp'],row['normalized_twist'],style,color=color,
                    markersize=3,linewidth=1.5,label=row['mesh'])
    for ax in axes:
        ax.axhline(0,color='.45',linewidth=.8)
        ax.grid(alpha=.2);ax.set_xlabel('Distance from clamp / span')
    axes[0].set_ylabel('Normalized local spanwise rotation')
    axes[0].set_title('First torsion-dominant mode, about 59.6 Hz')
    axes[1].set_title('Sign change near the clamp')
    axes[1].set_xlim(0,.3)
    root_values=[v for row in data['torsion_shapes'] for s,v in zip(row['span_from_clamp'],row['normalized_twist'],strict=True) if s<=.3]
    lo,hi=min(root_values),max(root_values);pad=.1*(hi-lo)
    axes[1].set_ylim(lo-pad,hi+pad)
    axes[0].legend();fig.suptitle('ST-1 thin blade: a first torsional mode need not have one twist sign')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(out/f'first-torsion-shape.{ext}',dpi=150)
    plt.close(fig)
    print('Wrote first-torsion-shape.png and .svg')


if __name__=='__main__':run()
