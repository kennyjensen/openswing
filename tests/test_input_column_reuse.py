"""Reuse complete physical input columns only for an identical loaded operator."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.frequency_response import FrequencyAnalysis,input_partials,constant_input_key
from test_frequency_reuse import mixed_aircraft,mixed_inputs


def analysis(inputs=None,previous=None,panels=4):
    return FrequencyAnalysis(mixed_aircraft(),FlightCondition(speed=20,alpha=0,mach=.1,powers={1:2}),
        panels,inputs=mixed_inputs() if inputs is None else inputs,gravity=[0,0,0],_base_analysis=previous)


@pytest.mark.parametrize('gust',[False,True])
def test_reordered_input_columns_are_exact_and_skip_full_probes(gust,monkeypatch):
    original=analysis();original.solve([.3])
    specs=['power.1','control.1']+([mixed_inputs()[-1]] if gust else [])
    reused=analysis(specs,original)
    assert reused.system is original.system and reused.a is original.a and reused.m is original.m
    assert reused.template['diagnostics']['loaded_input_columns_reused']==2
    for i,j in [(0,1),(1,0)]:
        assert reused.constant_inputs[i][0] is original.constant_inputs[j][0]
        assert not reused.constant_inputs[i][0].flags.writeable
        assert reused.constant_inputs[i][1] is not original.constant_inputs[j][1]
    n=reused.system.network;before=n.nfev
    from openswing.frequency_response import HarmonicInput
    requested=[];at_frequency=HarmonicInput.at_frequency
    def traced(channel,omega):
        requested.append(channel.kind)
        return at_frequency(channel,omega)
    monkeypatch.setattr(HarmonicInput,'at_frequency',traced)
    actual,forcing,profiles=input_partials(reused.system,reused.channels,3.7,reused.step,
        constant_inputs=reused.constant_inputs,influence_cache=reused.input_influences)
    saved=n.nfev-before;before=n.nfev
    assert set(requested)==({'gust'} if gust else set())
    assert (saved>0) if gust else (saved==0)
    requested.clear()
    expected,reference,p=input_partials(reused.system,reused.channels,3.7,reused.step,
        influence_cache=reused.input_influences)
    # Direct power/gust derivatives reduce fresh residual evaluations too.
    # Check that reuse avoids rebuilding constant forcing, saves work, and
    # preserves complete columns, without assuming the older stencil cost.
    assert set(requested)==({'power','control','gust'} if gust else {'power','control'})
    assert n.nfev-before>saved
    np.testing.assert_array_equal(actual,expected);assert profiles==p
    zero=np.zeros(reused.system.size)
    for a,b in zip(forcing,reference):
        for part in (0,1):
            np.testing.assert_array_equal(reused.system.residual(zero,zero,forcing=a(part,.01)),
                reused.system.residual(zero,zero,forcing=b(part,.01)))


def test_new_inputs_are_built_and_gusts_never_transfer():
    original=analysis(['control.1',mixed_inputs()[-1]]);original.solve([.3])
    reused=analysis(previous=original)
    assert set(reused.constant_inputs)=={0}
    assert reused.template['diagnostics']['loaded_input_columns_reused']==1
    assert constant_input_key(reused.channels[-1]) is None
    out=reused.solve([3.7]);reused.constant_inputs={}
    assert reused.solve([3.7])==out


def test_mutated_previous_channel_is_rejected_and_new_forcing_is_independent():
    original=analysis();original.solve([.3])
    original.channels[0].scale*=2
    reused=analysis(previous=original)
    assert set(reused.constant_inputs)=={1}
    zero=np.zeros(reused.system.size);forcing=reused.constant_inputs[1][1]
    expected=reused.system.residual(zero,zero,forcing=forcing(0,.01))
    original.channels[1].index=999
    np.testing.assert_array_equal(reused.system.residual(zero,zero,forcing=forcing(0,.01)),expected)


def test_missing_or_failed_sweep_has_no_columns_to_transfer(monkeypatch):
    original=analysis()
    assert analysis(previous=original).constant_inputs=={}
    import openswing.frequency_response as module
    def fail(*args,**kwargs):raise ValueError('deliberate output failure')
    monkeypatch.setattr(module,'output_perturbation',fail)
    try:original.solve([.3])
    except ValueError as exc:assert str(exc)=='deliberate output failure'
    else:raise AssertionError('Expected output failure')
    assert not original.constant_inputs
    assert analysis(previous=original).constant_inputs=={}


def test_sparse_input_field_columns_and_complete_outputs_transfer_exactly():
    original=analysis(panels=16);original.solve([.3])
    assert original.output_fields is not None
    reused=analysis(list(reversed(mixed_inputs())),original,panels=16)
    assert reused.output_fields is original.output_fields
    for i,j in [(1,1),(2,0)]:
        assert reused.constant_inputs[i][1]._output_fields is original.constant_inputs[j][1]._output_fields
    actual=reused.solve([3.7]);reused.constant_inputs={}
    assert reused.solve([3.7])==actual


@pytest.mark.parametrize('frame,inputs',[('prescribed',['acceleration.x','angular_acceleration.y']),
    ('free',['target.force.x','target.moment.y'])])
def test_canonical_frame_input_columns_transfer_with_original_units(frame,inputs):
    settings=dict(frame=frame,inputs=inputs,gravity=[0,0,0])
    from pathlib import Path
    from openswing.asw import parse_asw
    model=parse_asw(Path('examples/flexible.asw').read_text()) if frame=='free' else mixed_aircraft()
    condition=FlightCondition(speed=20,mach=.1)
    original=FrequencyAnalysis(model,condition,4,**settings)
    # Populate only physical B columns; the free-flight zero-frequency pencil
    # need not be solved to test an input matrix.
    input_partials(original.system,original.channels,1.,original.step,constant_inputs=original.constant_inputs)
    reused=FrequencyAnalysis(model,condition,4,_base_analysis=original,**settings)
    assert reused.template['diagnostics']['loaded_input_columns_reused']==2
    actual,_,_=input_partials(reused.system,reused.channels,9.,reused.step,constant_inputs=reused.constant_inputs)
    expected,_,_=input_partials(reused.system,reused.channels,9.,reused.step)
    np.testing.assert_array_equal(actual,expected)
