"""Edited-file identity, full record round trips, spline sides and mechanics."""
from pathlib import Path
import hashlib
import numpy as np
import pytest
from openswing.asw import AswError, Distribution, parse_asw
from openswing.asw_edit import edit_distribution, distribution_report, model_data, unknown_blocks
from openswing.bridge import dispatch
from openswing.network import solve_static
from openswing.aero import FlightCondition

WING=Path('examples/rectangular.asw').read_text()
SPRING=Path('examples/instrumented-oscillator.asw').read_text()
EXAMPLES=sorted(Path('examples').glob('*.asw'))


@pytest.mark.parametrize('path',EXAMPLES,ids=lambda p:p.stem)
def test_all_fixtures_lossless_and_canonical_semantics(path):
    source=path.read_text().replace('\n','\r\n')
    m=parse_asw(source);assert m.dumps()==source
    canonical=m.dumps(canonical=True);out=parse_asw(canonical)
    assert model_data(out)==model_data(m)
    assert out.dumps(canonical=True)==canonical
    for a,b in zip(m.beams,out.beams):
        t=np.unique(np.r_[np.linspace(*a.domain,33),a.breaks])
        for name in a.distributions:
            for side in ('left','right'):
                for derivative in (0,1,2):
                    np.testing.assert_array_equal(a.value(name,t,side=side,derivative=derivative),b.value(name,t,side=side,derivative=derivative))


def test_scaling_optional_fields_physical_indices_and_unknown_content():
    unknown='Custom 4 5 ! preserved header\r\n odd data # note\r\nEnd ! unknown end\r\n'
    source=WING.replace('Beam 1','Beam 1 42').replace('0 0 0 0 1 .25\n6 0 6 0 1 .25',
        '* -1 1 2 1 3D0 1\n+ 0 0 1 0 .5 0\n0 0 0 0 1 .25\n6 0 6 0 1 .25')
    source+='Weight\n* 2 3 4 5 6\n+ 1 1 1 1 1\n1 2 3 4 5 6\nEnd\n'+unknown
    m=parse_asw(source);m.name='Edited aircraft';saved=m.dumps();out=parse_asw(saved)
    assert model_data(m)==model_data(out)
    assert out.beams[0].physical_index==42
    np.testing.assert_allclose(out.records['weight'][0][:6],[1,5,10,17,26,37])
    assert not out.records['weight'][0][6:].any()
    assert unknown in saved and unknown_blocks(out)==[unknown]
    assert '! preserved header' in saved and saved.count('# note')==1
    assert out.dumps(canonical=True)==saved
    assert saved.count('Comments retained from original source')==1


def test_all_mutable_model_fields_are_exported():
    m=parse_asw(SPRING)
    m.name='Renamed';m.constants[:]=[10,1.2,330];m.units.declarations={'L':(1,'m'),'T':(1,'s'),'M':(1,'kg')}
    m.reference[1:]=[[1,2,3],[4,5,6],[7,8,9]]
    m.records['weight'][0][5]=20;m.records['engine'][0][10]=3
    m.beams[0].physical_index=18;m.beams[0].name='New beam'
    m.beams[0].distributions['EA']=Distribution('EA',[0,.5,2],[1500,1600,2000],0)
    out=parse_asw(m.dumps());assert model_data(out)==model_data(m)
    assert out.dumps()!=SPRING


def test_stale_spline_array_mutation_cannot_be_exported_as_a_different_model():
    m=parse_asw(WING);d=m.beams[0].distributions['chord'];d.values*=2
    assert m.beams[0].value('chord',1)==1
    with pytest.raises(AswError,match='rebuilding'):m.dumps()
    d.__post_init__()
    assert parse_asw(m.dumps()).beams[0].value('chord',1)==2
    d.values/=2
    with pytest.raises(AswError,match='rebuilding'):m.dumps()


@pytest.mark.parametrize('edit',[
    dict(points=[[0,1]]),dict(points=[[0,1],[0,2],[1,3]]),
    dict(points=[[0,1],[2,2],[1,3]]),dict(points=[[0,1],[1,float('nan')]]),
    dict(points=[[0,1,2],[1,2,3]]),dict(multiplier=float('inf')),dict(multiplier='invalid'),
    dict(multiplier=1e308,adder=1e308),dict(remove=True,adder=1),
])
def test_bad_edit_leaves_original_model_untouched(edit):
    m=parse_asw(WING)
    with pytest.raises((AswError,ValueError)):edit_distribution(m,1,'chord',**edit)
    assert m.dumps()==WING and m.beams[0].value('chord',2)==1


def test_removal_and_new_control_catalog_with_independent_station_grid():
    m=parse_asw(WING)
    out=edit_distribution(m,1,'dcldf12',points=[[-6,-.2],[0,0],[6,.2]])
    assert out.controls==[1,12] and m.controls==[1]
    out=edit_distribution(out,1,'dCMdF1',remove=True)
    assert out.controls==[1,12]
    out=edit_distribution(out,1,'dCLdF1',remove=True)
    assert out.controls==[12]
    assert out.beams[0].value('dCLdF1',3)==0
    assert len(out.beams[0].distributions['dCLdF12'].t)==3
    with pytest.raises(AswError,match='x, y, or z'):edit_distribution(parse_asw(SPRING),1,'y',remove=True)
    with pytest.raises(AswError,match='documented'):edit_distribution(m,1,'alien',points=[[0,1],[6,1]])


def test_plot_samples_actual_spline_mirrored_jump_y_center_and_overshoot():
    m=edit_distribution(parse_asw(WING),1,'alpha',points=[[0,0],[1,0],[1,4],[6,4]])
    r=distribution_report(m,1,'alpha')
    assert r['mirrored'] and len(r['segments'])==4
    assert [s['values'][0] for s in r['segments']]==[4,0,0,4]
    assert [s['values'][-1] for s in r['segments']]==[4,0,0,4]
    m=edit_distribution(m,1,'y',adder=5)
    r=distribution_report(m,1,'y')
    assert r['segments'][0]['values'][0]==-1
    assert r['segments'][-1]['values'][-1]==11
    m=edit_distribution(m,1,'Cm',points=[[0,0],[1,1],[2,1],[6,0]])
    r=distribution_report(m,1,'Cm');assert max(v for s in r['segments'] for v in s['values'])>1
    m=edit_distribution(m,1,'Cdf',points=[[1,0],[2,1]])
    assert any(s['extrapolated'] for s in distribution_report(m,1,'Cdf')['segments'])
    r=distribution_report(parse_asw(WING),1,'dCLdF1');assert not r['mirrored']
    assert len(r['segments'])==3


def test_unknown_distribution_and_comments_survive_other_edits():
    source=WING.replace('t Cdf','t alien\n0 3\n6 7\nt Cdf')
    m=edit_distribution(parse_asw(source),1,'chord',multiplier=1.5)
    assert m.diagnostics and m.beams[0].value('alien',3)==5
    assert '! Original OpenSwing verification example.' in m.dumps()


@pytest.mark.parametrize('change',[
    lambda m:setattr(m,'name','Broken\nEnd'),
    lambda m:m.constants.__setitem__(1,float('inf')),
    lambda m:m.reference.__setitem__((0,0),-1),
    lambda m:m.units.declarations.update(L=(-1,'m')),
    lambda m:setattr(m.beams[0],'index',1.5),
    lambda m:m.records['ground'][0].__setitem__(0,2),
])
def test_programmatic_edits_cannot_emit_invalid_asw(change):
    m=parse_asw(WING);change(m)
    with pytest.raises(AswError):m.dumps()


def test_bridge_preview_and_serialized_stiffness_match_analytic_solution_and_identity():
    m=parse_asw(SPRING)
    edited=edit_distribution(m,1,'EA',multiplier=2)
    out=dispatch(dict(action='edit_distribution',source=SPRING,beam=1,name='EA',edit=dict(multiplier=2)))
    assert out['source']==edited.dumps()
    assert out['distribution']['points']==[[0,2000],[2,2000]]
    results=[]
    for model in (m,edited,parse_asw(out['source'])):
        r=solve_static(model,FlightCondition(speed=10,alpha=0,mach=0),panels=4,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=[0,10,0])])
        expected=.02 if model is m else .01
        assert r['nodes'][-1]['position'][1]-2==pytest.approx(expected,abs=1e-10)
        np.testing.assert_allclose(r['support_force'],[0,-10,0],atol=1e-9)
        assert r['equilibrium_state']['identity']['model_sha256']==hashlib.sha256(model.dumps().encode()).hexdigest()
        results.append(r)
    assert results[0]['equilibrium_state']['identity']!=results[1]['equilibrium_state']['identity']
    assert results[1]['equilibrium_state']['identity']==results[2]['equilibrium_state']['identity']
    # Programmatic reference edits must invalidate saved identity too.
    m.reference[3,0]=.3
    r=solve_static(m,FlightCondition(speed=10,alpha=0,mach=0),panels=4,gravity=[0,0,0])
    assert r['equilibrium_state']['identity']!=results[0]['equilibrium_state']['identity']
