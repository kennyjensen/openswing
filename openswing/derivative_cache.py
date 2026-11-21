"""Isolated exact cache ownership for unchanged centered derivative probes.

No residuals, stencils, physical supports or matrix entries are approximated.
This first revision deliberately leaves local-row geometry reuse disabled.
"""
from contextlib import contextmanager
from .tangent_influences import TangentInfluences


class DerivativeTangentCache(TangentInfluences):
    """Counters around existing numerical methods, with no new cache keys."""
    def __init__(self):
        super().__init__(local_geometry=False)
        self.counters=dict(steady_geometry_calls=0,steady_geometry_computes=0,
            material_calls=0,material_computes=0,factored_pair_calls=0,
            factored_pair_kernel_calls=0,vortex_calls=0,volume_pair_calls=0)
        self.maximum_tangent_bytes=0
        self.maximum_static_bytes=0

    def observe_storage(self):
        self.maximum_tangent_bytes=max(self.maximum_tangent_bytes,self.bytes)
        self.maximum_static_bytes=max(self.maximum_static_bytes,self.static_bytes)

    def steady_geometry(self,network,r,q,compute):
        self.counters['steady_geometry_calls']+=1
        def counted():
            self.counters['steady_geometry_computes']+=1
            return compute()
        try:return super().steady_geometry(network,r,q,counted)
        finally:self.observe_storage()

    def material_array(self,key,compute):
        self.counters['material_calls']+=1
        def counted():
            self.counters['material_computes']+=1
            return compute()
        try:return super().material_array(key,counted)
        finally:self.observe_storage()

    def factored_pairs(self,name,global_key,points,a,b,cores,excluded,compute):
        self.counters['factored_pair_calls']+=1
        def counted(*args,**kwargs):
            self.counters['factored_pair_kernel_calls']+=1
            return compute(*args,**kwargs)
        try:return super().factored_pairs(name,global_key,points,a,b,cores,excluded,counted)
        finally:self.observe_storage()

    def vortex(self,*args,**kwargs):
        self.counters['vortex_calls']+=1
        try:return super().vortex(*args,**kwargs)
        finally:self.observe_storage()

    def volume_pairs(self,*args,**kwargs):
        self.counters['volume_pair_calls']+=1
        try:return super().volume_pairs(*args,**kwargs)
        finally:self.observe_storage()

    def report(self):
        counters=dict(self.counters)
        counters['steady_geometry_hits']=counters['steady_geometry_calls']-counters['steady_geometry_computes']
        counters['material_hits']=counters['material_calls']-counters['material_computes']
        return dict(counters=counters,local_geometry=False,
            maximum_tangent_bytes=self.maximum_tangent_bytes,
            maximum_static_bytes=self.maximum_static_bytes,
            tangent_storage_budget_bytes=64*1024**2,
            static_storage_budget_bytes=self.static_limit,
            storage_budget_note='Existing array-payload accounting excludes material-key bytes and Python object/header overhead. Inherited NetworkMotion has a separate 16 MiB retained-map budget plus surface storage; these counters are not a whole-operation memory bound.',
            tangent_storage_within_budget=self.maximum_tangent_bytes<=64*1024**2,
            static_storage_within_budget=self.maximum_static_bytes<=self.static_limit,
            material_entries=len(self.material),pair_entries=len(self.entries),
            factored_pair_entries=len(self.factored_entries))


@contextmanager
def derivative_probe_cache(network,*,response,feedback,report):
    reasons=[]
    if response!='fixed_acceleration':reasons.append('response is not fixed_acceleration')
    if feedback is not None:reasons.append('feedback is active')
    if network.iteration_fields is not None:reasons.append('an IterationFields context already owns the network')
    if network.tangent_influences is not None:reasons.append('a tangent cache already owns the network')
    if network._tangent_loads is not None:reasons.append('a tangent-load cache already owns the network')
    report.update(eligible=not reasons,enabled=False,fallback_reasons=reasons,
        ownership='derivative-owned shallow network copy; no original-network attributes are assigned',
        scope='unchanged complete centered state and parameter probes; original dense SVD/LU',
        lagged_iteration_fields_introduced=False)
    if reasons:
        yield
        return
    previous=network.tangent_influences
    fields=network.iteration_fields
    loads=network._tangent_loads
    cache=DerivativeTangentCache()
    network.tangent_influences=cache
    network.aero_key=network.aero_cached=None
    report['enabled']=True
    try:
        yield
    finally:
        # Do not restore an aero value keyed to a prior condition/state.
        network.tangent_influences=previous
        network.aero_key=network.aero_cached=None
        report.update(cache.report(),owner_restored=network.tangent_influences is previous,
            iteration_fields_unchanged=network.iteration_fields is fields,
            tangent_load_owner_unchanged=network._tangent_loads is loads,
            aero_cache_invalidated=network.aero_key is None and network.aero_cached is None)
