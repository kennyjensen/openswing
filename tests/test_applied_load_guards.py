import numpy as np
import pytest
from openswing.applied_load_outputs import AppliedLoadTangent,AppliedLoadUnavailable
from openswing.frequency_response import FrequencyAnalysis
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from pathlib import Path
from test_applied_load_outputs import build,freeze,snapshot_values
from test_support_outputs import system_for,snapshots_for


def test_wire_and_clipping_branches_preserve_physical_output_fallback():
 s=system_for('wire_taut');a,m=freeze(np.zeros((s.size,s.size)),np.zeros((s.size,s.size)))
 t=AppliedLoadTangent(s,a,m,1e-5);v=np.zeros(s.size);snaps=snapshots_for(s,v.astype(complex))
 snaps[0]['struts'][0]['slack']=not snaps[0]['struts'][0]['slack']
 with pytest.raises(AppliedLoadUnavailable,match='wire'):t.apply(v,v,None,None,snaps)
 s,a,m,t=build('powered','fixed',{'powers':{1:7}});v=np.zeros(s.size);_,snaps=snapshot_values(s,v,v,1e-5)
 snaps[0]['engines'][0]['power_clipped']=not snaps[0]['engines'][0]['power_clipped']
 with pytest.raises(AppliedLoadUnavailable,match='clipping'):t.apply(v,v,None,None,snaps)


def test_nested_fields_and_controller_context_keep_original_output_path():
 s,a,m,t=build();n=s.network
 n.iteration_fields=object()
 try:
  with pytest.raises(AppliedLoadUnavailable):AppliedLoadTangent(s,a,m,1e-5)
 finally:n.iteration_fields=None
 s.feedback=object()
 try:
  with pytest.raises(AppliedLoadUnavailable):AppliedLoadTangent(s,a,m,1e-5)
 finally:s.feedback=None
 assert t.matches(s,a,m,1e-5)


def test_frequency_model_reuse_retains_C_Q_and_rebinds_D():
 model=parse_asw(Path('examples/flexible.asw').read_text());condition=FlightCondition(speed=20,alpha=3,mach=.1)
 first=FrequencyAnalysis(model,condition,4,inputs=[dict(kind='gust',name='first',wave='uniform')])
 previous=first.solve([.3,1.7]);packet=first.applied_loads
 assert packet is not None and previous['diagnostics']['applied_load_linearization']['applications']==2
 second=FrequencyAnalysis(model,condition,4,inputs=[dict(kind='gust',name='second',wave='convected')],_base_analysis=first)
 assert second.applied_loads is packet
 current=second.solve([.7]);assert current['converged']
 assert current['diagnostics']['applied_load_linearization']['applications']==1
 assert packet.applications==3
 assert previous['diagnostics']['applied_load_linearization']['applications']==2
 fresh=FrequencyAnalysis(model,FlightCondition(speed=21,alpha=3,mach=.1),4,
  inputs=[dict(kind='gust',name='third')],_base_analysis=second)
 assert fresh.applied_loads is not packet
 assert not packet.matches(fresh.system,fresh.a,fresh.m,1e-5)
