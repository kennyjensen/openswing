"""JSON boundary shared by native validation and the browser worker."""
import json
from dataclasses import asdict
from .asw import parse_asw
from .geometry import geometry_summary, model_meshes, attachment_geometry
from .discretization import normalize as normalize_discretization, report as mesh_report
from .aero import AnalysisError, FlightCondition, solve_rigid
from .inertia import InertiaModel
from .operating import free_flight_constraints, steady_turn_constraints
from .reference_flow import reference_airflow_constraints
from .numerical_policy import request_policy, validate_saved_policy, validate_source_request, SOURCE_OPERATORS, SOURCE_SECTION, SOURCE_COUPLED, SOURCE_MODAL, SOURCE_AIRFLOW


def solve_static(*args, **kwargs):
    """Load the network solver on demand, after startup inspection."""
    from .network import solve_static as solve
    return solve(*args, **kwargs)


def dispatch(request, progress=None, *, _copy_frequency_result=True):
    wake_diagnostic = request.get('fourier_wake_diagnostic', False)
    if not isinstance(wake_diagnostic, bool):
        raise ValueError('fourier_wake_diagnostic must be boolean.')
    if wake_diagnostic and (request.get('action') not in ('solve', 'operating_points')
                            or request.get('mode', 'rigid') != 'rigid'):
        raise ValueError('The continuous Fourier wake diagnostic currently supports rigid steady solves and rigid operating-point stacks.')
    policy = request_policy(request)
    validate_saved_policy(request, policy)
    if request.get('action') == 'operating_points':
        from .operating_points import prepare_points, solve_points
        points = prepare_points(request, policy)
        model = parse_asw(request['source'], beam_interpolation=policy['beam_interpolation'])
        panels = normalize_discretization(request.get('panels', 40), model)
        return solve_points(model, request, points, panels, policy, _solve_steady, progress)
    source_policy = policy['structural_operator'] in SOURCE_OPERATORS
    if source_policy:
        validate_source_request(request)
    result = _dispatch(request, progress, policy, _copy_frequency_result=_copy_frequency_result)
    if source_policy:
        result['numerics'] = policy
        if policy['structural_operator'] in SOURCE_MODAL and request['action'] in ('modes','frequency','extend_frequency','time','launch_time','resume_time'):
            result['structural_operator'] = policy['structural_operator']
        if request['action'] == 'inspect':
            result['mass_properties_scope'] = dict(
                selected_operator_mass=False, dynamic_inertia_validated=False,
                description='Supplemental midpoint mass bookkeeping for inspection; not the selected source-discrete load integration.',
                selected_weight_rule='Source-discrete static solves use arithmetic endpoint mg/Dmg averages times unloaded interval length, with half the weight applied at each endpoint.')
            if policy['structural_operator'] in (SOURCE_SECTION, SOURCE_COUPLED):
                result['mass_properties_scope']['selected_weight_rule'] += ' The section policy also applies endpoint-CG gravity couples; dynamic inertia and spin are unavailable.'
    return result


def _dispatch(request, progress, policy, *, _copy_frequency_result=True):
    if request['action'] == 'gust_import':
        from .gust_file import import_gust
        return import_gust(request.get('text'))
    if request['action'] == 'gust_export':
        from .gust_file import export_legacy_gust
        return export_legacy_gust(request.get('gust'))
    if request['action']=='discard_frequency':
        from .frequency_sweep import discard
        return discard(request.get('session'),retain_model=request.get('retain_model',False))
    if request['action'] == 'rom_import':
        from .rom_file import parse_rom, rom_response
        return rom_response(parse_rom(request['text']),request.get('frequencies',[0.,1.,10.,100.]))
    if request['action'] in ('gust_sample', 'gust_validate'):
        from .gust import gust_field
        field = gust_field(request.get('gust'))
        if request['action'] == 'gust_validate':
            return dict(type=field.kind)
        return dict(velocity=field.velocity(request['positions'], request.get('time', 0)).tolist())
    model = parse_asw(request["source"], beam_interpolation=policy['beam_interpolation'])
    if request['action']=='extend_frequency':
        from .frequency_sweep import extend
        if set(request)-{'action','source','session','frequencies','numerics'}:
            raise ValueError('Frequency refinement keeps its loaded model and settings; only new frequencies may be specified.')
        return extend(model,request.get('session'),request.get('frequencies'),progress,
                      _copy_result=_copy_frequency_result)
    panels = normalize_discretization(request.get("panels", 40), model)
    if request['action'] == 'vortex_preview':
        from .vortex_display import preview
        return preview(model_meshes(model, panels), **request.get('view', {}))
    if 'continuation' in request:
        from .steady_continuation import solve_job
        return solve_job(model,request,panels,policy,progress)
    if request['action']=='flow_survey':
        from .flow_survey import survey
        return survey(model,panels=panels,**request.get('survey',{}))
    if request['action']=='canonical_asw':
        return dict(source=model.dumps(canonical=True))
    if request['action']=='distribution':
        from .asw_edit import distribution_report
        return distribution_report(model,request['beam'],request['name'])
    if request['action']=='edit_distribution':
        from .asw_edit import edit_distribution,distribution_report
        edited=edit_distribution(model,request['beam'],request['name'],**request.get('edit',{}))
        return dict(source=edited.dumps(),distribution=None if request.get('edit',{}).get('remove') else distribution_report(edited,request['beam'],request['name']))
    if request['action'] == 'reference_airflow_constraints':
        return [asdict(c) for c in reference_airflow_constraints(**request.get('preset', {}))]
    if request["action"] == "steady_turn_constraints":
        constraints = steady_turn_constraints(**request.get("preset", {}))
        for c in constraints:
            if c.variable.startswith("control.") and int(c.variable.split('.')[1]) not in model.controls:
                raise ValueError("Selected trim flap is not present in this model.")
            if c.variable.startswith("power.") and int(c.variable.split('.')[1]) not in model.engine_controls:
                raise ValueError("Selected trim engine is not present in this model.")
        return [asdict(c) for c in constraints]
    if request["action"] == "inspect":
        from .point_objects import rigid_weight_attachments
        from .asw import DEFAULTS,RIGID
        from .sensors import sensor_metadata, validate_sensors
        try:
            si = model.units.si_scales()
        except ValueError:
            si = None
        meshes = model_meshes(model, panels, request.get('loads', ()))
        # Inspection may describe signed static loading devices; ordinary
        # aerodynamic/dynamic solves retain physical mass validation.
        inertia = InertiaModel(model, meshes, allow_signed_point_weights=True, allow_signed_distributed_weights=True)
        rigid_attachments = rigid_weight_attachments(model)
        return dict(name=model.name, beams=geometry_summary(model, meshes=meshes), controls=model.controls,
                    mesh_discretization=mesh_report(model, meshes, panels, request.get('loads', ())),
                    distributions=[dict(beam=b.index,name=b.name,physical_index=b.physical_index,properties=list(b.distributions),domain=list(b.domain),lifting=b.lifting) for b in model.beams],
                    distribution_defaults={k:0. if k in RIGID else v for k,v in sorted(DEFAULTS.items())},
                    sensors=[dict(index=int(r[0]),beam=int(r[1]),t=float(r[2]),**sensor_metadata(r)) for r in model.records.get('sensor', [])],
                    engine_controls=[dict(index=k, types=sorted({int(r[1]) for r in model.records["engine"] if int(r[0]) == k})) for k in model.engine_controls],
                    strut_count=len(model.records.get("strut", [])),
                    hinge_count=len(model.records.get("jangle", [])),
                    attachments=attachment_geometry(model),
                    mass_properties=inertia.summary(inertia.elements(meshes)),
                    signed_point_weights=inertia.signed_point_weights,
                    signed_distributed_weights=inertia.signed_distributed_weights,
                    diagnostics=model.diagnostics+validate_sensors(model),
                    rigid_weight_attachments=rigid_attachments,
                    compatibility_notes=model.compatibility_notes+[
                        dict(code=a['policy'], message=f"Weight {a['record']}, beam {a['beam']}: anchor t={a['original_t']:g} → {a['effective_t']:g}. "+a['reason'])
                        for a in rigid_attachments], reference=model.reference.tolist(),
                    constants=model.constants.tolist(), units=model.units.declarations, si=si,
                    elastic=any(any(k in b.distributions for k in ("EIcc", "EInn", "GJ", "EA")) for b in model.beams))
    if request["action"] in ("solve", "time", "modes", "frequency", "rom", "stability", "resume_time", "launch_time"):
        source_condition = None
        if policy['structural_operator'] == SOURCE_AIRFLOW and request['action'] in ('frequency','modes','time'):
            value = dict(request['condition'])
            for key in ('controls','powers'):
                value[key] = {int(k):float(v) for k,v in value.get(key,{}).items()}
            source_condition = FlightCondition(**value)
        if request['action'] == 'frequency' and policy['structural_operator'] in SOURCE_MODAL:
            from .frequency_response import solve_frequency_response
            if request.get('retain_frequency', False):
                from .frequency_sweep import start as solve_frequency_response
            options = dict(request.get('frequency', {}))
            if request.get('retain_frequency', False):
                options['_copy_result'] = _copy_frequency_result
            options.pop('vacuum', None)  # The explicit operator owns the medium.
            if options.get('motion') is not None:
                from .inertia import Motion
                options['motion'] = Motion(**options['motion'])
            return solve_frequency_response(model, source_condition, panels, gravity=request.get('gravity'),
                loads=request.get('loads', ()), progress=progress,
                strut_mode=request.get('strut_mode', 'bilateral'),
                structural_operator=policy['structural_operator'], **options)
        if request['action'] == 'time' and policy['structural_operator'] in ('drela-moving-vacuum-v1', SOURCE_AIRFLOW):
            from .time_integration import solve_time
            options = dict(request.get('time', {}))
            if options.get('motion') is not None:
                from .inertia import Motion
                options['motion'] = Motion(**options['motion'])
            return solve_time(model, source_condition, panels, gravity=request.get('gravity'),
                loads=request.get('loads', ()), initial_loads=request.get('initial_loads'),
                strut_mode=request.get('strut_mode', 'bilateral'), progress=progress,
                structural_operator=policy['structural_operator'], **options)
        if request['action'] == 'modes' and policy['structural_operator'] in SOURCE_MODAL:
            from .linear_dynamics import solve_modes
            options = dict(request.get('modes', {}))
            if options.get('motion') is not None:
                from .inertia import Motion
                options['motion'] = Motion(**options['motion'])
            return solve_modes(model, source_condition, panels, gravity=request.get('gravity'),
                loads=request.get('loads', ()), progress=progress,
                strut_mode=request.get('strut_mode', 'bilateral'),
                structural_operator=policy['structural_operator'], **options)
        if request['action'] == 'solve' and request.get('mode') == 'structural':
            if request.get('condition') not in (None, {}):
                raise ValueError('Structural static analysis has no FlightCondition; specify body-axis gravity and applied loads directly.')
            if policy['structural_operator'] in SOURCE_OPERATORS:
                from .source_discrete import solve_source_discrete
                options = {key: request[key] for key in ('tolerance', 'continuation_steps') if key in request}
                result = solve_source_discrete(model, panels, gravity=request.get('gravity'), loads=request.get('loads', ()),
                    initial_state=request.get('initial_state'), progress=progress,
                    structural_operator=policy['structural_operator'], strut_mode=request.get('strut_mode', 'bilateral'),
                    allow_signed_point_weights=True, allow_signed_distributed_weights=True, **options)
            else:
                result = solve_static(model, None, panels, gravity=request.get('gravity'), loads=request.get('loads', ()),
                                      operating_constraints=request.get('operating_constraints', ()),
                                      strut_mode=request.get('strut_mode', 'bilateral'),
                                      derivatives=request.get('derivatives'), controller=request.get('controller'),
                                      initial_state=request.get('initial_state'), progress=progress,
                                      allow_signed_point_weights=True, allow_signed_distributed_weights=True)
            result.update(analysis='structural_static', structural_only=True, strips=[])
            return result
        if request['action']=='launch_time':
            from .time_initialization import launch_time
            return launch_time(model,request.get('equilibrium_state'),progress=progress,**request.get('time',{}))
        if request['action']=='resume_time':
            from .time_state import resume_time
            return resume_time(model,request.get('checkpoint'),progress=progress,**request.get('time',{}))
        condition = dict(request.get("condition", {}))
        condition["controls"] = {int(k): float(v) for k, v in condition.get("controls", {}).items()}
        condition["powers"] = {int(k): float(v) for k, v in condition.get("powers", {}).items()}
        if request['action'] == 'stability':
            from .stability import solve_stability
            return solve_stability(model,FlightCondition(**condition),panels,
                gravity=request.get('gravity'),loads=request.get('loads',()),
                operating_constraints=request.get('operating_constraints',()),
                strut_mode=request.get('strut_mode','bilateral'),progress=progress,
                modes=request.get('modes',{}),**request.get('stability',{}))
        if request['action'] == 'rom':
            from .reduced_model import solve_reduced_model, rom_text
            from .rom_file import export_rom
            result = solve_reduced_model(model, FlightCondition(**condition), panels,
                gravity=request.get('gravity'), loads=request.get('loads', ()),
                operating_constraints=request.get('operating_constraints', ()),
                strut_mode=request.get('strut_mode', 'bilateral'), progress=progress,
                **request.get('rom', {}))
            result['text_export'] = rom_text(result)
            try:
                result['legacy_export'] = export_rom(result,model.units,model.name)
            except ValueError as exc:
                result['legacy_export_error'] = str(exc)
            return result
        if request['action'] == 'frequency':
            from .frequency_response import solve_frequency_response
            options = dict(request.get('frequency', {}))
            if request.get('retain_frequency',False):
                from .frequency_sweep import start as solve_frequency_response
                options['_copy_result'] = _copy_frequency_result
            return solve_frequency_response(model, FlightCondition(**condition), panels,
                gravity=request.get('gravity'), loads=request.get('loads', ()),
                operating_constraints=request.get('operating_constraints', ()),
                strut_mode=request.get('strut_mode', 'bilateral'), progress=progress,
                **options)
        if request['action'] == 'modes':
            from .linear_dynamics import solve_modes
            return solve_modes(model, FlightCondition(**condition), panels,
                               gravity=request.get('gravity'), loads=request.get('loads', ()),
                               operating_constraints=request.get('operating_constraints', ()),
                               strut_mode=request.get('strut_mode', 'bilateral'), progress=progress,
                               **request.get('modes', {}))
        if request["action"] == "time":
            from .time_integration import solve_time
            return solve_time(model, FlightCondition(**condition), panels,
                              gravity=request.get("gravity"), loads=request.get("loads", ()),
                              initial_loads=request.get("initial_loads"),
                              strut_mode=request.get("strut_mode", "bilateral"), progress=progress, **request.get("time", {}))
        return _solve_steady(model, request, FlightCondition(**condition), panels, policy, progress)
    raise ValueError(f"Unknown action: {request['action']}")


def _solve_steady(model, request, condition, panels, policy, progress=None):
    """The unchanged single-point route, shared by explicit operating stacks."""
    mode = request.get('mode', 'rigid')
    if policy['structural_operator'] in (SOURCE_COUPLED, SOURCE_AIRFLOW):
        from .source_coupled import solve_source_coupled
        from .source_airflow import solve_source_airflow_steady
        solve = solve_source_airflow_steady if policy['structural_operator'] == SOURCE_AIRFLOW else solve_source_coupled
        options = {key: request[key] for key in ('tolerance', 'continuation_steps') if key in request}
        if policy['structural_operator'] == SOURCE_AIRFLOW:
            options.update({key:request[key] for key in ('controller','derivatives') if request.get(key) is not None})
        return solve(model, condition, panels,
            gravity=request.get('gravity'), loads=request.get('loads', ()),
            operating_constraints=request.get('operating_constraints', ()),
            initial_state=request.get('initial_state'), progress=progress,
            strut_mode=request.get('strut_mode', 'bilateral'), **options)
    if mode in ('mounted', 'free'):
        constraints = free_flight_constraints() if mode == 'free' else request.get('operating_constraints', [])
        return solve_static(model, condition, panels, gravity=request.get('gravity'),
            loads=request.get('loads', ()), operating_constraints=constraints,
            strut_mode=request.get('strut_mode', 'bilateral'), derivatives=request.get('derivatives'),
            controller=request.get('controller'), initial_state=request.get('initial_state'), progress=progress)
    if mode == 'rigid':
        if request.get('controller') is not None:
            raise ValueError('Feedback equilibrium requires mounted or free-flight equilibrium; Ground constraints define the body frame.')
        if request.get('derivatives') is not None:
            raise ValueError('Coupled derivatives require mounted equilibrium; rigid .asw beams give its rigid limit.')
        return solve_rigid(model, condition, panels, circulation_method=request.get('circulation_method', 'auto'),
                           initial_circulation=request.get('initial_circulation'),
                           fourier_wake_diagnostic=request.get('fourier_wake_diagnostic', False))
    raise ValueError(f'Unknown analysis mode: {mode}')


def _run_result(request_json, progress=None, *, compact_time=False, _copy_frequency_result=True):
    request = json.loads(request_json)
    if not _copy_frequency_result and request.get('action') in ('frequency', 'extend_frequency'):
        result = dispatch(request, progress, _copy_frequency_result=False)
    else:
        result = dispatch(request, progress)
    if compact_time and isinstance(result, dict) and result.get('analysis') == 'time_response':
        from .time_result_storage import pack_time_result
        if progress is not None:
            progress('time_reporting', result['end_time'], len(result['snapshots']))
        from .time_snapshot_storage import SnapshotHistory
        if not isinstance(result['snapshots'], SnapshotHistory):
            result = pack_time_result(result)
    return result


def run_json(request_json, progress=None, *, compact_time=False):
    result = _run_result(request_json, progress, compact_time=compact_time)
    compact = compact_time and isinstance(result, dict) and result.get('format') == 'openswing-time-result'
    return json.dumps(result, allow_nan=False, **(dict(separators=(',', ':')) if compact else {}))


def run_worker_json(request_json, progress=None):
    """Keep structured rejection evidence across Pyodide's exception boundary.

    The native API still raises; this envelope is only for the browser worker.
    Unexpected exceptions retain their traceback through the worker's catch.
    """
    try:
        result = run_json(request_json, progress, compact_time=True)
    except AnalysisError as error:
        return json.dumps(dict(error=str(error), details=error.details), allow_nan=False)
    return '{"result":' + result + '}'


def run_worker_parts(request_json, progress=None):
    """Compute once, then expose small records without a full-grid JSON copy."""
    from .worker_transport import WorkerReply
    from .time_snapshot_storage import browser_time_storage
    try:
        with browser_time_storage():
            reply = dict(result=_run_result(request_json, progress, compact_time=True, _copy_frequency_result=False))
    except AnalysisError as error:
        reply = dict(error=str(error), details=error.details)
    return WorkerReply(reply)
