"""Required stations must not create accidental tiny panels in regular meshes."""
from pathlib import Path
import json
import numpy as np
from openswing.asw import parse_asw
from openswing.geometry import mesh_beam, model_meshes
from openswing.discretization import requirements
from test_arc_length import polynomial_beam, arc_parabola

ROOT=Path(__file__).resolve().parents[1]


def settings(n):
    return dict(default=n,beams={'1':dict(count=n,spacing='uniform-breaks')})


def test_curved_material_spans_are_uniform_and_keep_the_exact_required_parameters():
    beam=polynomial_beam(([0,0,1],[0,1],[0]))
    required=np.array([0,.31,.72,1.])
    mesh=mesh_beam(beam,settings(12),stations=required)
    nodes=np.r_[mesh.t0,mesh.t1[-1]]
    for t in required:assert t in nodes
    for left,right in zip(required[:-1],required[1:]):
        inside=nodes[(nodes>=left)&(nodes<=right)]
        lengths=np.diff(arc_parabola(inside))
        np.testing.assert_allclose(lengths,lengths.mean(),atol=3e-14,rtol=0)
    assert min(mesh.length)>.08


def test_parameter_scale_does_not_change_regular_spacing():
    a=polynomial_beam(([0],[0,2],[0]))
    b=polynomial_beam(([0],[0,1,0,1],[0]))
    aa=mesh_beam(a,settings(12),stations=[.5])
    # t+t^3=1 has one real root; these are the same physical attachment.
    root=float(np.roots([1,0,1,-1])[2].real)
    bb=mesh_beam(b,settings(12),stations=[root])
    np.testing.assert_allclose(aa.r0,bb.r0,atol=5e-14,rtol=0)
    np.testing.assert_allclose(aa.length,bb.length,atol=5e-14,rtol=0)


def test_daedalus_keeps_required_stations_and_removes_accidental_close_pairs():
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    request=json.loads((ROOT/'web/daedalus-mesh.json').read_text())
    meshes=model_meshes(model,request);required=requirements(model)
    for mesh in meshes:
        nodes=np.r_[mesh.t0,mesh.t1[-1]]
        assert {r['t'] for r in required[mesh.beam.index]}<=set(nodes)
        if mesh.beam.index in (1,2):
            np.testing.assert_allclose(nodes,-nodes[::-1],atol=1e-13,rtol=0)
        # Every interval between required nodes has constant material length.
        anchors=sorted({r['t'] for r in required[mesh.beam.index]})
        for left,right in zip(anchors[:-1],anchors[1:]):
            lengths=mesh.length[(mesh.t0>=left)&(mesh.t1<=right)]
            assert len(lengths)>0
            np.testing.assert_allclose(lengths,lengths.mean(),atol=4e-14,rtol=0)
    assert min(meshes[1].length)>.99
    assert min(meshes[2].length)>.79
    assert min(meshes[3].length)>1.24
    assert min(meshes[4].length)>.39
    assert min(meshes[0].length)==np.min(meshes[0].length[:1])
    assert [len(m.tm) for m in meshes]==[50,12,10,17,9]


def test_old_uniform_spacing_remains_unchanged_for_saved_cases():
    beam=polynomial_beam(([0],[0,2],[0]))
    request=dict(default=8,beams={'1':dict(count=8,spacing='uniform')})
    mesh=mesh_beam(beam,request,stations=[.31])
    expected=np.sort(np.r_[np.linspace(0,1,9),.31])
    np.testing.assert_allclose(np.r_[mesh.t0,mesh.t1[-1]],expected,atol=2e-15,rtol=0)
