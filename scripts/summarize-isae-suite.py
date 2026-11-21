"""Independently summarize frozen ISAE comparisons; never run a solver.

Multiple runs are additive only: duplicate job IDs, changed numerical helpers,
runtime or original-source provenance are rejected, never resolved by choosing
the closer result. Existing reports are read without modification.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from decimal import Decimal
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CHANNELS = ('lift', 'drag', 'CL', 'CD', 'CDi', 'Cm', 'efficiency')
COUNTS = ('required', 'reported', 'finite', 'numerically_valid_finite', 'passed',
          'absent', 'reported_unavailable', 'unrun_required', 'failed_job_required', 'unsupported_required')
EXTRA_CHANNELS = {'SA-10': CHANNELS, 'SA-12': ('CL', 'CD', 'CDi', 'Cm'),
                  'SA-14': ('CL',), 'SA-15': ('CD', 'CY', 'CL', 'Cl', 'Cm', 'Cn', 'efficiency')}
POLAR_ADAPTERS = ('polars', 'extra_polars', 'sa11', 'sa12')
ST3_CHANNELS = ('y_m', 'z_m', 'twist_deg', 'Mc_prime_Nm', 'Ms_prime_Nm', 'Fn_N', 'cl', 'a_flap')
AE_CHANNELS = {'AE-2': ('RY_m', 'Psi_deg', 'sensor_V_m_s', 'sensor_beta_deg'),
               'FFWT-1': ('lift', 'root_Mc', 'left_tip_bank', 'left_tip_alpha')}
SA6_CHANNELS = ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')
FAMILIES = {f'SA-{n}' for n in range(1, 16) if n != 9}
for _prefix, _last in [('UA', 2), ('AP', 2), ('P', 5), ('ST', 6), ('AE', 7), ('FFWT', 5)]:
    FAMILIES.update(f'{_prefix}-{n}' for n in range(1, _last + 1))


def pin(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def precision_pass(check, *, exact_decimal=False):
    x, y, tolerance = (check.get(key) for key in ('predicted', 'expected', 'tolerance'))
    if not all(finite(value) for value in (x, y, tolerance)) or tolerance < 0:
        return False
    operation = check.get('comparison', '<=')
    require(operation in ('<', '<='), 'Unknown reference comparison operator.')
    if exact_decimal:
        require(operation == '<=', 'Native exact decimal interval requires <=.')
        expected = Decimal(check['exact_decimal_expected'])
        half = Decimal(check['exact_decimal_tolerance'])
        require(expected.is_finite() and half.is_finite() and half >= 0, 'Invalid exact decimal interval.')
        return abs(Decimal(str(x)) - expected) <= half
    return abs(x - y) < tolerance if operation == '<' else abs(x - y) <= tolerance


def numerically_valid(result):
    if not result or result.get('status') != 'computed':
        return False
    valid = result.get('numerical_pass', result.get('numerical_passed', False)) is True
    if result.get('numerical_checks'):
        valid = valid and all(check.get('passed') is True for check in result['numerical_checks'])
    return valid


def st2_mechanics(job):
    return job.get('adapter') == 'st2' and job.get('comparison_scope') == 'st2-mechanics'


def st3_mechanics(job):
    return job.get('adapter') == 'st3' and job.get('comparison_scope') == 'st3-mechanics'


def st4_mechanics(job):
    return job.get('adapter') == 'st4' and job.get('comparison_scope') in ('st4-mechanics', 'st4-native')


def st5_mechanics(job):
    return job.get('adapter') == 'st5' and job.get('comparison_scope') == 'st5-mechanics'


def st5_contract(job):
    from scripts.isae_suite_st5_mechanics import reference_contract
    return reference_contract(job)


def st4_contract(job):
    from scripts.isae_suite_st4_mechanics import reference_contract
    return reference_contract(job)


def st3_contract(job):
    from scripts.isae_suite_st3_mechanics import reference_contract
    return reference_contract(job)


def historical_polar(job):
    pairing = job.get('source_pairing')
    return (job.get('target_kind') == 'historical_source_polar' or
            job.get('execution_route') == 'historical_seven_fields' or
            job.get('comparison_scope') == 'supplemental_historical_source_pairing' or
            isinstance(pairing, dict) and pairing.get('id') == 'sa7-fore-f745fb40' or
            ':historical-f745fb40:' in job.get('id', '') or
            job.get('adapter') == 'extra_polars' and
            (job.get('case_id') == 'SA-7' or 'source_pairing' in job))


def sa6_postprocessor(job):
    binding = job.get('source_binding')
    return (isinstance(binding, dict) and
            (binding.get('kind') == 'original_matlab_control_binding' or
             'postprocessor_path' in binding))


def sa6_controls(job):
    from scripts.isae_suite_sa6_controls import identifies
    return identifies(job)


def sa6_states(job):
    from scripts.isae_suite_sa6_states import identifies
    return identifies(job)


def sa6_mass(job):
    from scripts.isae_suite_sa6_mass import identifies
    return identifies(job)


def sa6_derivatives(job):
    # Retain this shared supplemental-contract dispatch name for historical callers.
    if sa6_mass(job):
        from scripts import isae_suite_sa6_mass
        return isae_suite_sa6_mass
    if sa6_states(job):
        from scripts import isae_suite_sa6_states
        return isae_suite_sa6_states
    if sa6_controls(job):
        from scripts import isae_suite_sa6_controls
        return isae_suite_sa6_controls
    return None


def require_sa6_postprocessor(job):
    binding = job.get('source_binding', {})
    require(job.get('adapter') == 'sa6' and job.get('case_id') == 'SA-6' and
            job.get('execution_route') in ('rigid_static_coefficients', 'rigid_control_derivatives', 'rigid_state_derivatives', 'rigid_mass_properties') and
            binding.get('kind') == 'original_matlab_control_binding' and
            binding.get('missing_original_driver') is True and
            binding.get('producer_execution_authenticated') is False and
            job.get('driver_path') is None and job.get('driver_declarations') is None,
            'Unreviewed SA6 postprocessor source binding.')
    if sa6_derivatives(job):
        sa6_derivatives(job).validate_record_contract(job)


def require_sa6_identity(job):
    if job.get('case_id') == 'SA-6' or job.get('id', '').startswith('SA-6:') or sa6_derivatives(job):
        require(job.get('case_id') == 'SA-6' and job.get('adapter') == 'sa6',
                'SA6 source binding requires its original family and adapter.')
        if sa6_derivatives(job):
            sa6_derivatives(job).validate_record_contract(job)
        if job.get('expected_outputs', 0) and job.get('execution_route') != 'unsupported' and not job.get('driver_path'):
            require_sa6_postprocessor(job)


def polar_channels(job):
    adapter = job.get('adapter')
    if historical_polar(job):
        require(adapter == 'extra_polars' and job.get('case_id') == 'SA-7' and
                job.get('target_kind') == 'historical_source_polar' and
                job.get('execution_route') == 'historical_seven_fields' and
                job.get('comparison_scope') == 'supplemental_historical_source_pairing' and
                isinstance(job.get('source_pairing'), dict) and
                job['source_pairing'].get('id') == 'sa7-fore-f745fb40',
                'Unreviewed historical polar pairing.')
        return CHANNELS
    if adapter == 'polars':
        return CHANNELS
    if adapter == 'extra_polars':
        from scripts import isae_suite_sa15 as sa15
        if sa15.identifies(job):
            sa15.reference_contract(job)
        channels = EXTRA_CHANNELS.get(job['case_id'])
        require(channels is not None, 'Unreviewed extra polar family.')
        return channels
    require(adapter in ('sa11', 'sa12') and job['case_id'] == {'sa11': 'SA-11', 'sa12': 'SA-12'}[adapter],
            'Unreviewed dedicated polar family.')
    return CHANNELS if adapter == 'sa11' else EXTRA_CHANNELS['SA-12']


def reference_policy(value):
    """Validate the full declared policy, not only its percentage label."""
    if value is None:
        return None
    from scripts.isae_acceptance import reference_acceptance_policy
    require(isinstance(value, dict) and 'relative_tolerance' in value and 'tiny_reference' in value,
            'Incomplete reference acceptance policy.')
    canonical = reference_acceptance_policy(relative_tolerance=value['relative_tolerance'],
                                             tiny_reference=value['tiny_reference'])
    require(value == canonical, 'Unknown or changed reference acceptance policy.')
    return canonical


def strict_policy_job(job):
    """Reconstruct and verify the original strict evidence behind a report view.

    Adapter contracts below still see original strict checks.  Reapplying the
    declared policy must reproduce every saved policy field and pass flag;
    a report cannot merely label arbitrary passing checks as a 3% policy.
    """
    result = job.get('result')
    if not result or 'reference_acceptance_policy' not in result:
        return job
    from scripts.isae_acceptance import apply_reference_acceptance
    policy = reference_policy(result['reference_acceptance_policy'])
    require(policy is not None and isinstance(result.get('strict_reference_match'), bool)
            and isinstance(result.get('strict_output_accounting'), dict),
            'Policy view lacks original strict result evidence.')
    strict = deepcopy(result)
    strict.pop('reference_acceptance_policy')
    strict['reference_match'] = strict.pop('strict_reference_match')
    strict['output_accounting'] = strict.pop('strict_output_accounting')
    for check in strict.get('reference_checks', []):
        require(isinstance(check.get('strict_passed'), bool) and
                'original_tolerance' in check and check['original_tolerance'] == check.get('tolerance'),
                'Policy view changed or omitted the original strict comparison.')
        check['passed'] = check.pop('strict_passed')
        for key in ('original_tolerance', 'effective_tolerance', 'acceptance_comparison',
                    'acceptance_basis', 'relative_error', 'exact_decimal_effective_tolerance'):
            check.pop(key, None)
    rebuilt = apply_reference_acceptance(strict, relative_tolerance=policy['relative_tolerance'],
                                          tiny_reference=policy['tiny_reference'])
    require(rebuilt == result, 'Saved reference acceptance view differs from the recomputed policy.')
    return dict(job, result=strict)


def scalar_counts(job):
    strict_job = strict_policy_job(job)
    counts = strict_scalar_counts(strict_job)
    if strict_job is not job:
        strict_accounting = dict(required=counts['required'], reported=counts['reported'],
            finite=counts['finite'], unavailable=counts['reported_unavailable'],
            numerically_valid=counts['numerically_valid_finite'], passed=counts['passed'], missing=counts['absent'])
        require(strict_job['result'].get('output_accounting') == strict_accounting,
                'Saved strict output accounting differs from independently verified checks.')
        if numerically_valid(job.get('result')):
            counts['passed'] = sum(check.get('passed') is True for check in job['result']['reference_checks'])
    return counts


def strict_scalar_counts(job):
    require_sa6_identity(job)
    if sa6_postprocessor(job):
        require_sa6_postprocessor(job)
    required = job['expected_outputs']
    require(all(c.get('relative_allowance_rule') is None or
                st5_mechanics(job) and c['relative_allowance_rule'] == 'add_printed_precision'
                for c in (job.get('result') or {}).get('reference_checks', [])),
            'Additive printed precision requires the declared ST5 mechanics scope.')
    check_pass = lambda check: precision_pass(check, exact_decimal=job.get('adapter') in ('st1', 'st3_modal', 'ae4', 'ae6', 'st4') or
        job.get('adapter') == 'st2' and job.get('target_kind') == 'native_modal' or
                st3_mechanics(job) and job.get('target_kind') == 'modal' or sa6_derivatives(job))
    inventory_shape = ((job.get('adapter') == 'modes' and job.get('required_components') == [] and
                        job.get('expected_operations', {}).get('cold_bridge_calls') == 0) or
                       (job.get('adapter') == 'sa6' and job.get('case_id') == 'SA-6' and
                        job.get('required_outputs') == [] and job.get('expected_operations', {}).get('cold_rigid_calls') == 0))
    inventory_only = (inventory_shape and job.get('blocker_code') == 'NO_PAIRED_EXPORT' and
                      job.get('execution_route') == 'unsupported' and isinstance(job.get('model_path'), str) and
                      job.get('table_path') is None and job.get('reference_rows') == [])
    if job.get('adapter') == 'st2':
        inventory_only = (job.get('case_id') == 'ST-2' and job.get('target_kind') == 'model_inventory' and
            job.get('blocker_code') in ('LITERAL_ATTACHMENT_OUTSIDE_DOMAIN', 'MODAL_SCOPE_REGISTERED_SEPARATELY') and
            job.get('execution_route') == 'unsupported' and isinstance(job.get('model_path'), str) and
            job.get('table_path') is None and job.get('reference_rows') == [] and job.get('observations') == [] and
            job.get('required_components') == [] and job.get('expected_operations', {}).get('cold_bridge_calls') == 0)
    if job.get('adapter') == 'ae3':
        inventory_only = (job.get('case_id') == 'AE-3' and job.get('target_kind') == 'model_inventory' and
            job.get('blocker_code') == 'NO_PAIRED_EXPORT' and
            job.get('execution_route') == 'unsupported' and isinstance(job.get('model_path'), str) and
            job.get('table_path') is None and job.get('reference_rows') == [] and job.get('observations') == [] and
            job.get('required_components') == [] and job.get('expected_operations', {}).get('cold_bridge_calls') == 0)
    if job.get('adapter') == 'st1':
        inventory_only = (job.get('case_id') == 'ST-1' and job.get('target_kind') == 'model_inventory' and
            job.get('blocker_code') == 'LITERAL_MODEL_UNSUPPORTED' and job.get('execution_route') == 'unsupported' and
            isinstance(job.get('model_path'), str) and job.get('table_path') is None and
            job.get('reference_rows') == [] and job.get('observations') == [] and job.get('required_components') == [] and
            job.get('expected_operations') == dict(cold_solves=0, fresh_residuals=0, retries=0))
    require(isinstance(required, int) and not isinstance(required, bool) and
            (required > 0 or required == 0 and inventory_only),
            'Zero scalar counts require an explicit unsupported model without a paired reference.')
    result = job.get('result')
    if sa6_derivatives(job) and result:
        require(sa6_derivatives(job).validate_result_contract(job, result), 'Invalid conditional SA6 derivative evidence.')
    if sa6_postprocessor(job) and result and result.get('status') == 'computed':
        require(result.get('source_binding') == job['source_binding'],
                'SA6 result lost its postprocessor source-binding qualification.')
    checks = result.get('reference_checks', []) if result else []
    names = [check.get('name') for check in checks]
    require(len(checks) <= required and len(set(names)) == len(names) and
            all(isinstance(name, str) and name for name in names),
            'Output checks must have unique nonempty names and not exceed required outputs.')
    valid = numerically_valid(result)
    contract = job.get('_summary_reference_contract')
    if job.get('adapter') in ('ae4', 'ae6'):
        module = importlib.import_module('scripts.isae_suite_' + job['adapter'])
        module.validate_record_contract(job)
        contract = module.reference_contract(job)
        if result and result.get('status') in ('computed', 'unsupported'):
            require(module.validate_result_contract(job, result), 'Invalid modal evidence.')
    if job.get('adapter') == 'st3_modal':
        from scripts.isae_suite_st3_modal import reference_contract, validate_result_contract
        contract = reference_contract(job)
        if result and result.get('status') == 'computed':
            require(validate_result_contract(job, result), 'Invalid conditional ST3 modal evidence.')
    if st3_mechanics(job):
        from scripts.isae_suite_st3_mechanics import validate_result_contract
        contract = st3_contract(job)
        if result:
            require(validate_result_contract(job, result), 'Invalid ST3 mechanics evidence.')
    if st5_mechanics(job):
        from scripts.isae_suite_st5_mechanics import validate_result_contract
        contract = st5_contract(job)
        if result:
            require(validate_result_contract(job, result), 'Invalid ST5 mechanics evidence.')
    if st4_mechanics(job):
        from scripts.isae_suite_st4_mechanics import validate_result_contract
        contract = st4_contract(job)
        if result:
            require(validate_result_contract(job, result), 'Invalid ST4 mechanics evidence.')
    if contract is None and job.get('adapter') == 'modes':
        contract = modes_contract(job)
    if contract is None and job.get('adapter') == 'aeroelastic':
        contract = aeroelastic_contract(job)
    if contract is None and job.get('adapter') == 'sa6':
        contract = sa6_contract(job)
    if job.get('adapter') == 'sa13':
        contract = sa13_contract(job)
        if result:
            require(result.get('status') != 'computed' and not valid and
                    result.get('reference_match') is not True and result.get('numerical_pass') is not True and
                    result.get('numerical_passed') is not True and
                    all(c.get('predicted') is None and c.get('passed') is False for c in checks) and
                    all(result.get(k, 0) == 0 for k in ('physical_calls', 'physical_solver_calls', 'production_imports')),
                    'SA13 missing-input scope cannot claim computed predictions or physical calls.')
            if result.get('status') == 'unsupported':
                from scripts.isae_suite_sa13 import validate_result_contract
                require(validate_result_contract(job, result), 'Invalid SA13 blocked reference evidence.')
    if job.get('adapter') == 'st2':
        # A conditional local modal survey cannot promote static/workbook or
        # inventory records into comparisons, or claim historical root identity.
        contract = st2_contract(job)
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls',
                        'equilibrium_solves', 'modal_solves', 'production_imports')),
                    'ST2 blocked registration cannot claim numerical execution, predictions or a reference match.')
            if result.get('status') == 'unsupported':
                require(len(checks) == required and result.get('source_pins_unchanged') is True,
                        'ST2 blocked result requires complete unavailable slots and unchanged source pins.')
        if result:
            from scripts.isae_suite_st2 import validate_result_contract
            require(validate_result_contract(job, result) is not False,
                    'ST2 saved result violates its physical or reference contract.')
        if result and result.get('status') == 'computed' and not st2_mechanics(job):
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'native_modal' and
                    result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_bridge_calls=1, equilibrium_solves=1,
                        modal_solves=1, fresh_residuals=1, retries=0) and result.get('physical_calls') == 2,
                    'ST2 computed modes lack the declared loaded fixed-frame route, fresh residual or unchanged pins.')
    if job.get('adapter') == 'ap1':
        contract = ap1_contract(job)
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls')) and
                    (result.get('operations') is None or result['operations'] ==
                     dict(cold_solves=0, fresh_residuals=0, retries=0)),
                    'AP1 blocked route cannot claim numerical execution, predictions or a reference match.')
            if result.get('status') == 'unsupported':
                require(len(checks) == required and result.get('source_pins_unchanged') is True and
                        result.get('operations') == dict(cold_solves=0, fresh_residuals=0, retries=0),
                        'AP1 blocked result requires complete unavailable slots and unchanged source pins.')
        if result and result.get('status') == 'computed':
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'paired_header',
                    'AP1 numerical comparison is limited to the declared paired header route.')
            ap1_physical_contract(job, result)
            require(result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                    result.get('physical_calls') == 2,
                    'AP1 computed header lacks complete physical checks, fresh residual or unchanged source/kernel pins.')
    if job.get('adapter') == 'ap2':
        contract = ap2_contract(job)
        if result:
            from scripts.isae_suite_ap2 import validate_result_contract
            require(validate_result_contract(job, result) is not False,
                    'AP2 saved result violates its physical or reference contract.')
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls')),
                    'AP2 blocked route cannot claim numerical execution, predictions or a reference match.')
            if result.get('status') == 'unsupported':
                require(len(checks) == required and result.get('source_pins_unchanged') is True and
                        result.get('operations') == dict(cold_solves=0, fresh_residuals=0, retries=0),
                        'AP2 blocked result requires complete unavailable slots and unchanged source pins.')
        if result and result.get('status') == 'computed':
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'grid_state' and
                    result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                    result.get('physical_calls') == 2,
                    'AP2 computed grid state lacks the declared route, fresh residual or unchanged source/kernel pins.')
    if job.get('adapter') == 'ae1':
        contract = ae1_contract(job)
        if result:
            from scripts.isae_suite_ae1 import validate_result_contract
            require(validate_result_contract(job, result) is not False,
                    'AE1 saved result violates its physical or reference contract.')
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls', 'production_imports')),
                    'AE1 unknown initial operating state cannot claim numerical execution or a reference match.')
        if result and result.get('status') == 'computed':
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'paired_sensor' and
                    result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                    result.get('physical_calls') == 2,
                    'AE1 computed sensor row lacks its declared route, fresh residual or unchanged source/kernel pins.')
    if job.get('adapter') == 'ae3':
        contract = ae3_contract(job)
        if result:
            from scripts.isae_suite_ae3 import validate_result_contract
            require(validate_result_contract(job, result) is not False,
                    'AE3 saved result violates its physical or reference contract.')
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls', 'production_imports')),
                    'AE3 unsupported targets cannot claim numerical execution or a reference match.')
        if result and result.get('status') == 'computed':
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'native_coefficients' and
                    result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                    result.get('physical_calls') == 2,
                    'AE3 computed native state lacks its declared route, fresh residual or unchanged source/kernel pins.')
    if job.get('adapter') == 'st1':
        contract = st1_contract(job)
        if result:
            from scripts.isae_suite_st1 import validate_result_contract
            require(validate_result_contract(job, result) is not False,
                    'ST1 saved result violates its physical or reference contract.')
        if result and job.get('execution_route') == 'unsupported':
            require(result.get('status') != 'computed' and result.get('reference_match') is not True and
                    result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                    all(check.get('predicted') is None and check.get('passed') is False for check in checks) and
                    all(result.get(key, 0) == 0 for key in ('physical_calls', 'physical_solver_calls', 'production_imports')),
                    'ST1 unresolved native outputs and model inventories cannot claim numerical execution or a match.')
        if result and result.get('status') == 'computed':
            require(job.get('execution_route') == 'worker' and job.get('target_kind') == 'native_position' and
                    result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                    result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                    result.get('physical_calls') == 2,
                    'ST1 computed position lacks its structural route, fresh residual or unchanged source/kernel pins.')
    if job.get('adapter') in POLAR_ADAPTERS:
        channels = polar_channels(job)
        if job.get('adapter') == 'extra_polars':
            from scripts.isae_suite_extra_polars import validate_result_contract
            if result:
                require(validate_result_contract(job, result), 'Invalid extra-polar scope evidence.')
        if historical_polar(job) and result and result.get('status') == 'computed':
            require(all(result.get(key) == job.get(key) for key in
                        ('source_pairing', 'target_kind', 'comparison_scope')),
                    'Historical polar result lost its source-pairing qualification.')
        require(required == len(channels), 'Polar required output scope changed.')
        if job['adapter'] != 'polars':
            require(job.get('required_outputs') == list(channels), 'Polar required output scope changed.')
        for check in checks:
            require(check['name'] in channels, 'Unknown polar output name.')
            ref = job['reference_row']['fields'][check['name']]
            require(check.get('expected') == ref['value'] and check.get('tolerance') == ref['tolerance'] and
                    check.get('comparison', '<=') == '<=', 'Polar printed-center precision gate changed.')
    elif job.get('adapter') == 'ae5':
        from scripts.isae_suite_ae5 import validate_result_contract
        if result:
            require(validate_result_contract(job, result), 'Invalid AE5 blocked source contract')
    elif job.get('adapter') == 'ffwt3':
        from scripts.isae_suite_ffwt3 import validate_result_contract
        if result:
            require(validate_result_contract(job, result), 'Invalid FFWT3 blocked source contract')
    elif job.get('adapter') == 'p2':
        from scripts.isae_suite_p2 import validate_result_contract
        if result and result.get('status') == 'computed':
            require(validate_result_contract(job, result), 'Invalid P-2 source-input/physical contract')
    elif job.get('case_id') == 'P-1' and job.get('adapter') == 'components':
        expected = {f"CT:row{row['index']:02d}": row['archived_CT'] for row in job['observations']}
        for check in checks:
            require(check['name'] in expected and check.get('expected') == expected[check['name']] and
                    check.get('tolerance') == job['numerical_gate']['value'] and check.get('comparison') == '<',
                    'P-1 original CT precision gate changed.')
    elif job.get('adapter') in ('structure', 'modes', 'aeroelastic', 'sa6', 'st2', 'ap1', 'ap2', 'ae1', 'ae3', 'ae4', 'ae6', 'st1', 'sa13', 'st3_modal', 'st3') and contract is not None:
        require(len(contract) == required, 'Declared required output scope changed.')
        for check in checks:
            require(check['name'] in contract, 'Unknown declared output name.')
            require(all(check.get(key) == value for key, value in contract[check['name']].items()) and
                    check.get('comparison', '<=') == '<=',
                    'Original target, precision gate or coordinate/trace changed.')
    if result and result.get('status') == 'computed':
        require(not inventory_only, 'Unpaired model inventory cannot claim a computed comparison.')
        require(valid and len(checks) == required, 'Computed job lacks complete numerically valid output checks.')
        require(all(check.get('passed') is check_pass(check) for check in checks),
                'Saved reference boolean differs from its unchanged precision gate.')
        require(result.get('reference_match') is all(check_pass(check) for check in checks),
                'Saved whole-job reference flag is inconsistent.')
    elif result:
        require(result.get('reference_match') is not True, 'Failed job claims a reference match.')
    available = sum(finite(check.get('predicted')) for check in checks)
    return dict(required=required, reported=len(checks), finite=available,
                numerically_valid_finite=available if valid else 0,
                passed=sum(check_pass(check) for check in checks) if valid else 0,
                absent=required - len(checks), reported_unavailable=len(checks) - available,
                unrun_required=required if result is None else 0,
                failed_job_required=required if result is not None and not valid and result.get('status') != 'unsupported' else 0,
                unsupported_required=required if result is not None and result.get('status') == 'unsupported' else 0)


def structure_contract(job, target):
    """Decode pinned printed targets independently; never import a verifier."""
    st3 = job['case_id'] == 'ST-3'
    forward = tuple('st5-forward-'+s for s in ('cosine_20lb', 'cosine_30lb', 'elliptical_20lb', 'elliptical_30lb'))
    roller = tuple('st5-roller-'+s for s in ('20lb_80_20', '20lb_90_10', '30lb_80_20', '30lb_90_10'))
    elliptical = tuple('st5-elliptical-'+s for s in ('20lb_80_20', '20lb_90_10', '30lb_80_20', '30lb_90_10'))
    snapshots = ('st3-m15_0',) if st3 else ('st5-20lb_80_20', 'st5-20lb_90_10', 'st5-30lb_90_10', 'st5-30lb_80_20')+roller+forward+elliptical
    require(job.get('snapshot') in snapshots, 'Unknown structural snapshot scope.')
    names = ST3_CHANNELS if st3 else tuple(column['name'] for column in target['columns'][1:])
    require(len(names) == (8 if st3 else 27), 'Structural target column count changed.')
    levels = [grid['level'] for grid in job['grids']]
    require(levels == [0, 1, 2], 'Structural three-grid scope changed.')
    rows = []
    if st3:
        require(len(target['printed_exponents']) == 9, 'ST3 exponent count changed.')
        duplicates = [i for i, row in enumerate(target['rows']) if row['physical_values'][0] == .335]
        require(len(duplicates) == 2, 'ST3 original duplicate station changed.')
        for i, row in enumerate(target['rows']):
            values = row['physical_values'][1:]
            tolerances = row['printed_half_ulp_physical'][1:]
            # Recheck the original decoder's physical scaling. Retain the exact
            # published half-place floats as the acceptance gate.
            for token, exponent, value, tolerance in zip(row['tokens'][1:], target['printed_exponents'][1:], values, tolerances, strict=True):
                scale = 10.**exponent
                raw = Decimal(token.replace('D', 'E').replace('d', 'e'))
                half = float(Decimal(10)**raw.as_tuple().exponent / 2) * scale
                require(math.isclose(float(raw)*scale, value, rel_tol=2e-15, abs_tol=0.) and
                        math.isclose(half, tolerance, rel_tol=2e-15, abs_tol=0.), 'ST3 target scaling differs from printed tokens.')
            rows.append((row, values, tolerances, row['physical_values'][0],
                         .6*.558 if i in duplicates else row['physical_values'][0],
                         'right' if i == 0 or i == duplicates[1] else 'left'))
    else:
        for beam in target['beams']:
            previous = None
            require(len(beam['physical_multipliers']) == 28, 'ST5 multiplier count changed.')
            for i, row in enumerate(beam['rows']):
                t = row['printed_t'] if row['exact_anchor_t'] is None else row['exact_anchor_t']
                tolerances = []
                require(len(row['raw_tokens']) == len(row['physical']) == 28, 'ST5 original column count changed.')
                for token, scale, value in zip(row['raw_tokens'], beam['physical_multipliers'], row['physical'], strict=True):
                    raw = Decimal(token.replace('D', 'E').replace('d', 'e'))
                    require(finite(scale) and scale > 0 and math.isclose(float(raw)*scale, value, rel_tol=2e-15, abs_tol=0.),
                            'ST5 target scaling differs from printed tokens.')
                    tolerances.append(float(Decimal(10)**raw.as_tuple().exponent)/2*scale)
                rows.append((row, row['physical'][1:], tolerances[1:], row['printed_t'], t,
                             'right' if i == 0 or t == previous else 'left'))
                previous = t
    require(len(rows) == job['rows_per_grid'] == (45 if st3 else 58 if job['snapshot'] in forward else 80) and
            job['outputs_per_row'] == len(names) and job['expected_outputs'] == 3*len(rows)*len(names),
            'Structural declared row/column count changed.')
    return {f'grid{level}:row{i:03d}:{name}': dict(expected=value, tolerance=tolerance,
                source_line=row['source_line'], t_printed=printed, t_evaluated=t, trace=side)
            for level in levels for i, (row, values, tolerances, printed, t, side) in enumerate(rows)
            for name, value, tolerance in zip(names, values, tolerances, strict=True)}


def load_structure_contract(job, root):
    origin = job['target_origin']
    path = Path(origin.get('path', origin.get('archive', '')))
    path = path if path.is_absolute() else root / path
    if 'archive' in origin:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(origin['member'])
    else:
        raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == origin['sha256'] and
            ('bytes' not in origin or len(raw) == origin['bytes']), 'Pinned structural target changed.')
    if 'decoder' in origin:
        from scripts.isae_suite_structure import decode_st5_original, decode_st5_variant, ROLLER_CASES, FORWARD_CASES, ELLIPTICAL_CASES
        require('archive' not in origin, 'Unreviewed original structural text decoder.')
        if origin['decoder'] == 'st5-original-text-v1' and job.get('snapshot') == 'st5-30lb_80_20':
            target = decode_st5_original(root)
        elif origin['decoder'] == 'st5-variant-text-v1' and job.get('snapshot') in ROLLER_CASES + FORWARD_CASES + ELLIPTICAL_CASES:
            target, _ = decode_st5_variant(root, job['snapshot'])
        else:
            raise ValueError('Unreviewed original structural text decoder.')
        encoded = json.dumps(target, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        require(hashlib.sha256(encoded).hexdigest() == origin['decoded_sha256'], 'Decoded original structural target changed.')
        exports = [item for item in target['source_pins'] if Path(item['path']).suffix == '.txt']
        require(len(exports) == 1 and path.resolve() == Path(exports[0]['path']).resolve() and
                all(origin.get(key) == exports[0][key] for key in ('bytes', 'sha256')),
                'Structural decoder source differs from declared original .txt export.')
        return structure_contract(job, target)
    return structure_contract(job, json.loads(raw))


def printed_token(token, unavailable=False):
    """Original lexical precision, without a relative-error acceptance rule."""
    try:
        value = Decimal(token.strip().replace(',', '.').replace('D', 'E').replace('d', 'e'))
        require(value.is_finite(), 'Nonfinite reference token.')
    except (ValueError, ArithmeticError):
        require(unavailable, 'Unavailable reference token outside its declared scope.')
        return None, None
    return float(value), float(Decimal(5).scaleb(value.as_tuple().exponent - 1))


def modes_contract(job):
    require(job['case_id'] == 'ST-4', 'Unreviewed modal family.')
    contract = {}
    if 'aggregate_targets' in job:
        require(job.get('execution_route') == 'unsupported' and not job['reference_rows'] and
                not job['required_components'], 'Aggregate candidates must remain unsupported.')
        for target in job['aggregate_targets']:
            label = target['name'].split(':')[-1]
            require(label in ('Vf_Asw', 'fb1_Asw', 'fb2_Asw', 'ft_Asw', 'ff_Asw') and
                    target['precision_scope'] == 'Stored cell token only; spreadsheet storage precision is not a recovered ASWING print format.',
                    'Aggregate target is not an explicitly qualified ASWING cell.')
            value, tolerance = printed_token(target['raw_token'], unavailable=True)
            require(target['expected'] == value and target['tolerance'] == tolerance and
                    target['units'] == ('m/s' if label == 'Vf_Asw' else 'Hz'),
                    'Aggregate stored value, precision or unit changed.')
            require(target['name'] not in contract, 'Duplicate aggregate target.')
            contract[target['name']] = {key: val for key, val in target.items() if key != 'name'}
    else:
        rows, components = job['reference_rows'], job['required_components']
        counts = job.get('grid_counts') or [None]
        if job.get('execution_route') == 'local_vacuum':
            require(counts == [16, 32, 64] and components == ['imaginary'], 'Selected modal frequency/grid scope changed.')
        elif rows:
            require(job.get('execution_route') == 'unsupported' and components in (['imaginary'], ['real', 'imaginary']),
                    'Unreviewed modal component scope.')
        else:
            require(job.get('blocker_code') == 'NO_PAIRED_EXPORT' and not components, 'Empty modal target is not model inventory.')
        for count in counts:
            for ordinal, row in enumerate(rows, 1):
                require(len(row['raw_tokens']) == 3 and int(row['raw_tokens'][0]) == row['operating_point'],
                        'Original modal operating point changed.')
                decoded = [printed_token(token) for token in row['raw_tokens'][1:]]
                require(row['eigenvalue'] == [pair[0] for pair in decoded] and
                        row['half_printed_units'] == [pair[1] for pair in decoded], 'Original modal target precision changed.')
                for component in components:
                    index = 0 if component == 'real' else 1
                    value, tolerance = decoded[index]
                    contract[f'n{count}:row{ordinal:04d}:{component}'] = dict(expected=value, tolerance=tolerance,
                        expected_token=row['raw_tokens'][index+1], source_line=row['line'],
                        operating_point=row['operating_point'], units='1/s')
    require(len(contract) == job['expected_outputs'], 'Modal required output count changed.')
    return contract


def st2_contract(job):
    """Source-only ST2 contract; no constructor or physics worker is imported."""
    from scripts.isae_suite_st2 import reference_contract
    return reference_contract(job)


def ap1_contract(job):
    """Keep AP1 header comparisons separate from blocked span recovery."""
    from scripts.isae_suite_ap1 import reference_contract
    return reference_contract(job)


def ap2_contract(job):
    """Keep binary MAT identity and original decimal witnesses distinct."""
    from scripts.isae_suite_ap2 import reference_contract
    return reference_contract(job)


def ae1_contract(job):
    """Retain all six absolute native sensor channels and original precision."""
    from scripts.isae_suite_ae1 import reference_contract
    return reference_contract(job)


def ae3_contract(job):
    """Keep finite coefficients, derivatives and qualified embedded targets separate."""
    from scripts.isae_suite_ae3 import reference_contract
    return reference_contract(job)


def st1_contract(job):
    """Keep all native complex roots and raw body-position targets intact."""
    from scripts.isae_suite_st1 import reference_contract
    return reference_contract(job)


def ap1_physical_contract(job, result):
    """Require every declared physical check and recompute saved metric gates."""
    from scripts.isae_suite_ap1 import GATES, PHYSICAL_CHECK_SPECS, REQUIRED_PHYSICAL_CHECKS, validate_physical_checks
    require(job.get('numerical_gates') == GATES, 'AP1 immutable numerical gates changed.')
    physical = result.get('physical_checks')
    require(isinstance(physical, list) and all(isinstance(item, dict) for item in physical),
            'AP1 physical checks must be a complete list.')
    names = [item.get('name') for item in physical]
    require(len(names) == len(REQUIRED_PHYSICAL_CHECKS) and len(set(names)) == len(names) and
            set(names) == set(REQUIRED_PHYSICAL_CHECKS) == set(PHYSICAL_CHECK_SPECS),
            'AP1 physical checks must contain every required name exactly once.')
    require(validate_physical_checks(job, physical), 'AP1 computed header has a failed physical check.')
    outputs = {item['name']: item.get('predicted') for item in result.get('reference_checks', [])}
    for check in physical:
        spec = PHYSICAL_CHECK_SPECS[check['name']]
        metric_name, gate_name = spec['metric'], spec['gate']
        if metric_name is not None:
            metric = check.get(metric_name)
            gate = job['numerical_gates'][gate_name]
            require(finite(metric) and metric >= 0 and check.get('gate') == gate,
                    'AP1 recorded physical metric or immutable gate changed.')
            if check['name'].startswith('independent_') and not check['name'].startswith('independent_header_'):
                a, b = check.get('reported'), check.get('reconstructed')
                require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3 and
                        all(finite(value) for value in a+b), 'AP1 independent wrench metric lacks finite vectors.')
                reconstructed_metric = max(abs(x-y) for x, y in zip(a, b))/(1+max(max(map(abs, a)), max(map(abs, b))))
                require(metric == reconstructed_metric, 'AP1 independent wrench metric differs from saved vectors.')
            elif check['name'].startswith('independent_header_'):
                output = check['name'].removeprefix('independent_header_')
                a, b = outputs.get(output), check.get('reconstructed')
                require(finite(a) and finite(b) and check.get('reported') == a,
                        'AP1 independent header metric lacks matching finite outputs.')
                reconstructed_metric = abs(a-b)/(1+max(abs(a), abs(b)))
                require(metric == reconstructed_metric, 'AP1 independent header metric differs from saved outputs.')
            elif check['name'] == 'restored_header_parity':
                require(check.get('reported') == outputs, 'AP1 restored header evidence differs from reference predictions.')
            require(check.get('passed') is (metric <= gate), 'AP1 physical pass boolean differs from its recorded metric.')
        require(check.get('passed') is True, 'AP1 computed header has a failed physical check.')
    return True


def ap1_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'ap1']
    if not selected:
        return []
    from scripts.isae_suite_ap1 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def ap2_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'ap2']
    if not selected:
        return []
    from scripts.isae_suite_ap2 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def ae1_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'ae1']
    if not selected:
        return []
    from scripts.isae_suite_ae1 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def ae3_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'ae3']
    if not selected:
        return []
    from scripts.isae_suite_ae3 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def st1_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'st1']
    if not selected:
        return []
    from scripts.isae_suite_st1 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def st2_mesh_diagnostics(jobs):
    selected = [job for job in jobs if job['adapter'] == 'st2']
    if not selected:
        return []
    from scripts.isae_suite_st2 import mesh_diagnostics
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def st3_mechanics_mesh_diagnostics(jobs):
    from scripts.isae_suite_st3_mechanics import mesh_diagnostics
    selected = [job for job in jobs if st3_mechanics(job)]
    return mesh_diagnostics(selected, {job['id']: job['result'] for job in selected if job.get('result') is not None})


def aeroelastic_contract(job):
    channels = AE_CHANNELS.get(job['case_id'])
    require(channels is not None and job['expected_outputs'] == 4 and
            [row['name'] for row in job['observations']] == list(channels), 'Aeroelastic required output scope changed.')
    contract = {}
    for index, row in enumerate(job['observations'], 2):
        require(row['token'] == job['reference_row']['raw_tokens'][index] and
                row['source_column_1based'] == index+1, 'Aeroelastic original output column changed.')
        missing = row['token'].lower() == 'nan'
        require(row['missing'] is missing and (not missing or job['case_id'] == 'AE-2'),
                'Undeclared missing aeroelastic target.')
        value, tolerance = printed_token(row['token'], unavailable=missing)
        require(row['expected'] == value and row['tolerance'] == tolerance, 'Aeroelastic printed precision changed.')
        contract[row['name']] = {key: val for key, val in row.items() if key != 'name'}
    return contract


def sa6_contract(job):
    require(job['case_id'] == 'SA-6', 'Unreviewed fmat family.')
    if sa6_derivatives(job):
        return sa6_derivatives(job).reference_contract(job)
    if sa6_postprocessor(job):
        require_sa6_postprocessor(job)
    if job['expected_outputs'] == 0:
        require(job.get('blocker_code') == 'NO_PAIRED_EXPORT' and job.get('required_outputs') == [] and
                job.get('reference_rows') == [] and job.get('table_path') is None,
                'Unpaired SA6 model cannot invent reference outputs.')
        return {}
    require(job['expected_outputs'] == 6 and job['required_outputs'] == list(SA6_CHANNELS),
            'SA6 six-static-coefficient scope changed.')
    fields = job['reference_row']['fields']
    require(set(fields) == set(SA6_CHANNELS), 'SA6 reference coefficient set changed.')
    contract = {}
    for name in SA6_CHANNELS:
        ref = fields[name]
        expected, tolerance = printed_token(ref['token'], unavailable=True)
        require(ref['value'] == expected and ref['tolerance'] == tolerance, 'SA6 original printed precision changed.')
        contract[name] = dict(expected=expected, tolerance=tolerance, expected_token=ref['token'], units='dimensionless')
    return contract


def sa13_contract(job):
    from scripts.isae_suite_sa13 import reference_contract
    return reference_contract(job)


def ae4_contract(job):
    from scripts.isae_suite_ae4 import reference_contract
    return reference_contract(job)


def ae6_contract(job):
    from scripts.isae_suite_ae6 import reference_contract
    return reference_contract(job)


def verify_reference_lines(job, root):
    """Bind direct export rows to original files after their hashes are checked."""
    if job['adapter'] in ('p2', 'ae5', 'ffwt3'):
        module = importlib.import_module('scripts.isae_suite_' + job['adapter'])
        module.verify_reference_sources(root, job)
        return
    if job['adapter'] in ('ae4', 'ae6'):
        module = importlib.import_module('scripts.isae_suite_' + job['adapter'])
        module.validate_record_contract(job, root)
    elif job['adapter'] == 'st3_modal':
        from scripts.isae_suite_st3_modal import validate_record_contract
        validate_record_contract(job, root)
    elif job['adapter'] == 'st5':
        from scripts.isae_suite_st5_mechanics import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'st4':
        from scripts.isae_suite_st4_mechanics import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'st3':
        from scripts.isae_suite_st3_mechanics import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'st2':
        from scripts.isae_suite_st2 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'ap1':
        from scripts.isae_suite_ap1 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'ap2':
        from scripts.isae_suite_ap2 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'ae1':
        from scripts.isae_suite_ae1 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'ae3':
        from scripts.isae_suite_ae3 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'st1':
        from scripts.isae_suite_st1 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] == 'sa13':
        from scripts.isae_suite_sa13 import verify_reference_sources
        verify_reference_sources(root, job)
    elif job['adapter'] in ('sa11', 'sa12'):
        path = Path(job['table_path'])
        lines = (path if path.is_absolute() else root/path).read_text().splitlines()
        row = job['reference_row']
        line = row['line_number']
        require(isinstance(line, int) and 1 <= line <= len(lines) and lines[line-1].split() == row['tokens'],
                'Polar reference row differs from the pinned original table.')
        width, start = (82, 75) if job['adapter'] == 'sa11' else (9, 5)
        require(len(row['tokens']) == width and row['row_index'] == job['row_index'] and
                printed_token(row['tokens'][0])[0] == job['row_index']+1,
                'Polar original row/column scope changed.')
        for column, name in enumerate(polar_channels(job), start):
            ref = row['fields'][name]
            token = row['tokens'][column]
            value, tolerance = printed_token(token, unavailable=True)
            require(ref['token'] == token and ref['value'] == value and ref['tolerance'] == tolerance,
                    'Polar target or precision differs from its original printed token.')
    elif job['adapter'] == 'modes' and 'aggregate_targets' in job:
        path = Path(job['table_path'])
        path = path if path.is_absolute() else root/path
        if path.suffix == '.csv':
            cells = {line: dict(enumerate(row)) for line, row in enumerate(csv.reader(path.read_text().splitlines(), delimiter=';'), 1)}
        else:
            require(path.suffix == '.xlsx', 'Unknown aggregate reference storage.')
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            with zipfile.ZipFile(path) as archive:
                strings = [''.join(node.itertext()) for node in ElementTree.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
                sheet = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            cells = {}
            for row in sheet.findall('.//s:sheetData/s:row', ns):
                values = {}
                for cell in row.findall('s:c', ns):
                    letters = re.match(r'[A-Z]+', cell.attrib['r'])[0]
                    column = 0
                    for char in letters:
                        column = column*26 + ord(char)-ord('A')+1
                    value = cell.find('s:v', ns)
                    token = '' if value is None else value.text or ''
                    values[column-1] = strings[int(token)] if cell.attrib.get('t') == 's' and token else token
                cells[int(row.attrib['r'])] = values
        columns = {column: value.strip() for column, value in cells[1].items() if value.strip().lower().endswith('_asw')}
        require(set(columns.values()) == {'Vf_Asw', 'fb1_Asw', 'fb2_Asw', 'ft_Asw', 'ff_Asw'}, 'Aggregate ASWING column scope changed.')
        expected = {}
        for line, row in cells.items():
            weight = row.get(0, '').strip().upper()
            if weight in ('0', '7A', '7B', '7C', '7D', '7E', '7F'):
                for column, label in columns.items():
                    expected[f'row{line}:{label}'] = dict(source_line=line, column_1based=column+1,
                        weight_label=weight, position_token=row.get(1, ''), raw_token=row.get(column, ''))
        require(len(expected) == len(job['aggregate_targets']) and
                {item['name'] for item in job['aggregate_targets']} == set(expected), 'Aggregate original ASWING cell coverage changed.')
        require(all(all(item.get(key) == value for key, value in expected[item['name']].items())
                    for item in job['aggregate_targets']), 'Aggregate target differs from its original stored cell.')
    elif job['adapter'] == 'modes' and job.get('reference_rows'):
        path = Path(job['table_path'])
        lines = (path if path.is_absolute() else root/path).read_text().splitlines()
        require(all(lines[row['line']-1].split() == row['raw_tokens'] for row in job['reference_rows']),
                'Modal reference row differs from the pinned original table.')
    elif job['adapter'] == 'aeroelastic':
        path = Path(job['source_output']['path'])
        lines = (path if path.is_absolute() else root/path).read_text().splitlines()
        row = job['reference_row']
        line = row['output_file_line_1based'] if job['case_id'] == 'AE-2' else row['file_line']
        require(lines[line-1] == row['raw_line'] and lines[line-1].split() == row['raw_tokens'] and
                all(item['source_line'] == line for item in job['observations']),
                'Aeroelastic reference row differs from the pinned original table.')
    elif sa6_mass(job):
        from scripts.isae_suite_sa6 import verify_mass_sources
        require(verify_mass_sources(root, job), 'Conditional SA6 tensor source verification failed.')
    elif sa6_states(job):
        from scripts.isae_suite_sa6 import verify_state_sources
        require(verify_state_sources(root, job), 'Conditional SA6 state source verification failed.')
    elif sa6_controls(job):
        from scripts.isae_suite_sa6 import verify_control_sources
        require(verify_control_sources(root, job), 'Conditional SA6 source verification failed.')
    elif job['adapter'] == 'sa6' and job.get('table_path'):
        text = (root/job['table_path']).read_text()
        header = 'Normalized forces in: Stability axes, x fwd, z down'
        require(text.count(header) == 1, 'SA6 original force-axis declaration changed.')
        block = text.split(header, 1)[1].split('Derivatives in:', 1)[0]
        for name in SA6_CHANNELS:
            tokens = re.findall(r'\b'+name+r'\s*=\s*(\S+)', block)
            require(tokens == [job['reference_row']['fields'][name]['token']], 'SA6 coefficient differs from original fmat token.')
        indices = re.findall(r'For deformed shape, operating point\s+(\d+)\s+\.\.\.', text)
        require(indices == [str(job['row_index']+1)] and job['reference_row']['operating_point'] == job['row_index']+1,
                'SA6 original operating-point index changed.')
        if job.get('driver_path'):
            driver = (root/job['driver_path']).read_text()
            invocations = re.findall(r'^aswing\s+(\S+)\s+<<EOF\s*$', driver, re.M)
            controls = re.findall(r'^!F1\s+(\S+)\s*$', driver, re.M)
            require(invocations == [Path(job['model_path']).stem] and
                    controls == [str(v) for v in range(4, 45, 4)] and
                    job['settings']['controls'] == {'1': float(controls[job['row_index']])},
                    'SA6 original driver/model/control pairing changed.')
        elif sa6_postprocessor(job):
            require_sa6_postprocessor(job)
            from scripts.isae_suite_sa6 import verify_postprocessor_sources
            verify_postprocessor_sources(root, job)
        else:
            require(job.get('execution_route') == 'unsupported' and job.get('blocker_code') == 'NO_MATCHING_DRIVER',
                    'SA6 unmatched driver scope must remain unsupported.')


def totals(jobs):
    values = [scalar_counts(job) for job in jobs]
    return {key: sum(row[key] for row in values) for key in COUNTS}


def source_signature(catalog):
    return {'repository': catalog['repository'], 'revision': catalog['revision'],
            'sources': sorted(catalog['sources'], key=lambda row: row['path']),
            'families': sorted((row['id'], row['path']) for row in catalog['cases']),
            'models': sorted((row['path'], row['bytes'], row['sha256']) for row in catalog['models'])}


def merge_runs(packets):
    """Pure accounting merge; current-file verification belongs to load_runs."""
    require(bool(packets), 'At least one frozen run is required.')
    st2_scopes = {job.get('comparison_scope', 'archive') for packet in packets
                  for job in packet['report']['jobs'] if job.get('adapter') == 'st2'}
    require(not ('st2-mechanics' in st2_scopes and len(st2_scopes) > 1),
            'ST2 mechanics and the overlapping archive must be summarized separately.')
    st3_scopes = {job.get('comparison_scope', 'archive') for packet in packets
                  for job in packet['report']['jobs'] if job.get('case_id') == 'ST-3'}
    require(not ('st3-mechanics' in st3_scopes and len(st3_scopes) > 1),
            'ST3 mechanics and overlapping historical scopes must be summarized separately.')
    st4_scopes = {job.get('comparison_scope', 'archive') for packet in packets
                  for job in packet['report']['jobs'] if job.get('case_id') == 'ST-4'}
    require(not (st4_scopes & {'st4-mechanics', 'st4-native'} and len(st4_scopes) > 1),
            'ST4 paper, native and overlapping archive scopes must be summarized separately.')
    st5_scopes = {job.get('comparison_scope', 'archive') for packet in packets
                  for job in packet['report']['jobs'] if job.get('case_id') == 'ST-5'}
    require(not ('st5-mechanics' in st5_scopes and len(st5_scopes) > 1),
            'ST5 mechanics and overlapping historical scopes must be summarized separately.')
    first = packets[0]
    runtime = first['report']['runtime']
    policy = reference_policy(first['report'].get('reference_acceptance'))
    source = source_signature(first['catalog'])
    kernel = {k: v for k, v in first['report']['code_sha256'].items() if k.startswith('openswing/')}
    require(bool(kernel), 'Missing numerical kernel provenance.')
    jobs, seen, helpers = [], set(), {}
    for packet in packets:
        report, catalog = packet['report'], packet['catalog']
        require(len(catalog['cases']) == 41 and {row['id'] for row in catalog['cases']} == FAMILIES,
                'The complete original 41-family catalog is required.')
        require(report.get('current_code_unchanged') is True, 'Run does not retain unchanged numerical code.')
        require(report['runtime'] == runtime, 'Runtime provenance differs across runs.')
        require(reference_policy(report.get('reference_acceptance')) == policy,
                'Reference acceptance policy differs across runs; summarize policies separately.')
        if policy is not None:
            require('scripts/isae_acceptance.py' in report['code_sha256'],
                    'Reference acceptance helper is not pinned.')
        require(source_signature(catalog) == source, 'Original-source/catalog provenance differs across runs.')
        require(report.get('repository') == catalog['repository'] and report.get('revision') == catalog['revision'],
                'Run and original catalog provenance differ.')
        require({k: v for k, v in report['code_sha256'].items() if k.startswith('openswing/')} == kernel,
                'Numerical kernel provenance differs across runs.')
        # The orchestration runner may gain new adapters. All pinned numerical
        # adapters/helpers and the source catalog interpreter must remain exact.
        for path, sha in report['code_sha256'].items():
            if path.startswith('openswing/') or path == 'scripts/run-isae-suite.py':
                continue
            require(path not in helpers or helpers[path] == sha, 'Adapter/helper provenance differs: ' + path)
            helpers[path] = sha
        for job in report['jobs']:
            require(job['id'] not in seen, 'Duplicate job ID; no best-result or last-result selection: ' + job['id'])
            require(job['case_id'] in {row['id'] for row in catalog['cases']}, 'Job family absent from catalog.')
            expected = 'scripts/isae_suite_' + ('st5_mechanics' if st5_mechanics(job) else 'st4_mechanics' if st4_mechanics(job) else 'st3_mechanics' if st3_mechanics(job) else job['adapter']) + '.py'
            require(expected in report['code_sha256'], 'Used adapter is not pinned: ' + expected)
            if job.get('result') is not None:
                require(job['result'].get('reference_acceptance_policy') == policy,
                        'Job reference acceptance policy differs from its run.')
            scalar_counts(job)
            seen.add(job['id'])
            jobs.append(job)
    return {'catalog': first['catalog'], 'jobs': jobs, 'runtime': runtime,
            'kernel_pins': kernel, 'helper_pins': helpers, 'source_provenance': source,
            'reference_acceptance': policy}


def load_runs(paths, root=ROOT):
    root = Path(root).resolve()
    packets, input_pins, upstream, verified = [], [], {}, {}

    def remember(item):
        item = dict(item, path=str(Path(item['path']).resolve()))
        require(item['path'] not in verified or verified[item['path']] == item,
                'Conflicting verified file pins: ' + item['path'])
        verified[item['path']] = item
        return item

    def current(path):
        path = str(Path(path).resolve())
        return verified[path] if path in verified else remember(pin(path))

    remember(pin(__file__))
    for value in paths:
        path = Path(value).resolve()
        path = path / 'report.json' if path.is_dir() else path
        catalog_path = path.with_name('catalog.json')
        plan_path = path.with_name('plan.json')
        require(path.is_file() and catalog_path.is_file() and plan_path.is_file(),
                'Each report needs its adjacent frozen catalog.json and plan.json.')
        documents = []
        for source in (path, catalog_path, plan_path):
            raw = source.read_bytes()
            item = remember(dict(path=str(source), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            input_pins.append(item)
            documents.append(json.loads(raw))
        report, catalog, plan = documents
        require(plan['catalog'] == catalog, 'Frozen plan and source catalog differ.')
        require([{k: v for k, v in job.items() if k != 'result'} for job in report['jobs']] == plan['jobs'],
                'Reported job coordinates/settings/gates differ from frozen plan.')
        require(plan['code_sha256'] == report['code_sha256'] and plan['runtime'] == report['runtime'],
                'Run and frozen plan numerical provenance differ.')
        for field in ('execution_policy', 'selection_scope', 'reference_acceptance'):
            # Historical schemas omit selection metadata from both files. Once
            # present, it must be retained identically on both sides.
            if field in plan or field in report:
                require(field in plan and field in report and plan[field] == report[field],
                        'Reported ' + field + ' differs from frozen plan.')
        scopes = plan.get('execution_policy', {}).get('comparison_scopes', [])
        require(isinstance(scopes, list) and len(scopes) == len(set(scopes)) and
                set(scopes).issubset({'sa6-f1-rigid', 'sa6-state-rigid', 'sa6-mass-rigid', 'ae1-frozen-influences', 'sa15-declared-setup', 'ae4-undeformed-alpha0', 'ae6-declared-airflow', 'st2-mechanics', 'st3-mechanics', 'st4-mechanics', 'st4-native', 'st5-mechanics'}), 'Invalid frozen comparison scopes.')
        if any(st2_mechanics(job) for job in plan['jobs']):
            from scripts.isae_suite_st2_mechanics import EXECUTION_HELPERS
            require('st2-mechanics' in scopes and all('scripts/'+name in plan['code_sha256'] for name in
                (*EXECUTION_HELPERS, 'isae_suite_st2.py', 'isae_suite_st2_modal.py',
                 'isae_st2_archive.py', 'isae_suite_st2_mechanics.py')),
                'ST2 mechanics requires explicit opt-in and complete helper pins.')
        if any(st5_mechanics(job) for job in plan['jobs']):
            require('st5-mechanics' in scopes and all('scripts/'+name in plan['code_sha256'] for name in
                ('isae_suite_st5_mechanics.py', 'isae_st5_recurring_worker.py', 'summarize-isae-suite.py')),
                'ST5 requires explicit scope and complete helper pins.')
        if any(st4_mechanics(job) for job in plan['jobs']):
            from scripts.isae_suite_st4_mechanics import EXECUTION_HELPERS
            require(len(set(scopes) & {'st4-mechanics', 'st4-native'}) == 1 and
                all(j['comparison_scope'] in scopes for j in plan['jobs'] if st4_mechanics(j)) and
                all('scripts/'+name in plan['code_sha256'] for name in
                    (*EXECUTION_HELPERS, 'isae_suite_st4_mechanics.py', 'summarize-isae-suite.py')),
                'ST4 requires one explicit scope and complete helper pins.')
        if any(st3_mechanics(job) for job in plan['jobs']):
            from scripts.isae_suite_st3_mechanics import EXECUTION_HELPERS
            require('st3-mechanics' in scopes and all('scripts/'+name in plan['code_sha256'] for name in
                (*EXECUTION_HELPERS, 'isae_suite_st3_mechanics.py', 'summarize-isae-suite.py')),
                'ST3 mechanics requires explicit opt-in and complete helper pins.')
        if any(job.get('comparison_scope') == 'ae4-undeformed-alpha0' for job in plan['jobs']):
            require('ae4-undeformed-alpha0' in scopes and all('scripts/'+name in plan['code_sha256'] for name in
                ('isae_suite_ae4.py','verify-isae-ae4-wall-modes.py','isae_modal_classification.py','isae_pencil_actions.py')),
                'Declared AE4 scope requires explicit opt-in and complete helper pins.')
        if any(job.get('comparison_scope') == 'ae6-declared-airflow' for job in plan['jobs']):
            require('ae6-declared-airflow' in scopes and all('scripts/'+name in plan['code_sha256'] for name in
                ('isae_suite_ae6.py', 'verify-isae-ae6-anchor.py')),
                'Declared AE6 scope requires explicit opt-in and complete helper pins.')
        from scripts import isae_suite_sa15 as sa15
        if any(sa15.identifies(job) for job in plan['jobs']):
            require(sa15.SCOPE in scopes and 'scripts/isae_suite_sa15.py' in plan['code_sha256'],
                    'Declared SA15 scope needs explicit opt-in and a pinned helper.')
        if any(job.get('comparison_scope') == 'ae1-frozen-influences' for job in plan['jobs']):
            require('ae1-frozen-influences' in scopes and 'scripts/isae_suite_ae1.py' in plan['code_sha256'],
                    'Conditional AE1 scope requires explicit frozen opt-in and adapter pin.')
        for identifies, scope, helper in ((sa6_controls, 'sa6-f1-rigid', 'isae_suite_sa6_controls.py'),
                                           (sa6_states, 'sa6-state-rigid', 'isae_suite_sa6_states.py'),
                                           (sa6_mass, 'sa6-mass-rigid', 'isae_suite_sa6_mass.py')):
            if any(identifies(job) for job in plan['jobs']):
                require(scope in scopes and 'scripts/'+helper in plan['code_sha256'] and
                        'scripts/isae_suite_sa6_controls.py' in plan['code_sha256'],
                        'Conditional SA6 scope requires explicit frozen opt-in and helper pin.')
                if scope == 'sa6-mass-rigid':
                    require('scripts/isae_suite_sa6_mass_math.py' in plan['code_sha256'],
                            'Tensor scope requires its independent evidence helper pin.')
        packets.append({'report': report, 'catalog': catalog})
    merged = merge_runs(packets)
    actual_kernel = {p.relative_to(root).as_posix(): current(p)['sha256'] for p in (root / 'openswing').glob('*.py')}
    require(actual_kernel == merged['kernel_pins'], 'Current kernel differs from the frozen runs.')
    for relative, sha in merged['helper_pins'].items():
        require(current(root / relative)['sha256'] == sha, 'Current adapter/helper differs: ' + relative)
    sources = list(merged['source_provenance']['sources'])
    for job in merged['jobs']:
        sources += job.get('sources', job.get('source_pins', []))
    for item in sources:
        path = Path(item['path'])
        path = path if path.is_absolute() else root / path
        identity = {key: item[key] for key in ('bytes', 'sha256')}
        require(str(path) not in upstream or upstream[str(path)] == identity, 'Conflicting source pins: ' + str(path))
        if str(path) in upstream:
            continue
        actual = current(path)
        require(all(actual[key] == value for key, value in identity.items()), 'Current source differs: ' + str(path))
        upstream[str(path)] = identity
    # These adapters rebuild the same full immutable source context for every
    # row. Rebuild it once for this call, then compare every canonical field.
    # The transaction-local file ledger is rehashed before returning/publishing;
    # there is no persistent, mtime-based or cross-run verification cache.
    canonical = {}
    canonical_adapters = {'ap2', 'ae1', 'ae3', 'ae4', 'ae6', 'st1', 'st2', 'st3', 'st4', 'st5', 'sa13'}
    for job in merged['jobs']:
        require_sa6_identity(job)
        if sa6_postprocessor(job):
            require_sa6_postprocessor(job)
            canonical_adapters.add('sa6')
        if sa6_derivatives(job):
            canonical_adapters.add('sa6')
    for adapter in sorted({job['adapter'] for job in merged['jobs']} & canonical_adapters):
        module = importlib.import_module('scripts.isae_suite_' + ('st5_mechanics' if adapter == 'st5' else 'st4_mechanics' if adapter == 'st4' else 'st3_mechanics' if adapter == 'st3' else adapter))
        selected_scopes = tuple(scope for identify, scope in ((sa6_controls,'sa6-f1-rigid'),(sa6_states,'sa6-state-rigid'),(sa6_mass,'sa6-mass-rigid'))
                                if any(identify(j) for j in merged['jobs']))
        if adapter == 'ae1':
            selected_scopes = ('ae1-frozen-influences',) if any(
                j.get('comparison_scope') == 'ae1-frozen-influences' for j in merged['jobs']) else ()
        if adapter == 'ae4':
            selected_scopes = ('ae4-undeformed-alpha0',) if any(
                j.get('comparison_scope') == 'ae4-undeformed-alpha0' for j in merged['jobs']) else ()
        if adapter == 'ae6':
            selected_scopes = ('ae6-declared-airflow',) if any(
                j.get('comparison_scope') == 'ae6-declared-airflow' for j in merged['jobs']) else ()
        if adapter == 'st2':
            selected_scopes = ('st2-mechanics',) if any(st2_mechanics(j) for j in merged['jobs']) else ()
        if adapter == 'st4':
            selected_scopes = tuple(sorted({j['comparison_scope'] for j in merged['jobs'] if j['adapter'] == 'st4'}))
        if adapter == 'st5':
            selected_scopes = ('st5-mechanics',)
        if adapter == 'st3':
            selected_scopes = ('st3-mechanics',)
        rows = (module.plan(root, comparison_scopes=selected_scopes)
                if adapter in ('sa6', 'ae1', 'ae4', 'ae6', 'st2', 'st3', 'st4', 'st5') and selected_scopes else module.plan(root))
        canonical[adapter] = {job['id']: job for job in rows}
        require(len(canonical[adapter]) == len(rows), 'Duplicate canonical source job.')
        canonical_pins = {}
        for row in rows:
            for item in row.get('source_pins', []) + row.get('kernel_pins', []) + row.get('sources', []):
                require(item['path'] not in canonical_pins or canonical_pins[item['path']] == item,
                        'Conflicting canonical source pins: ' + item['path'])
                canonical_pins[item['path']] = item
        for item in canonical_pins.values():
            remember(dict(item, path=str(root / item['path'])))
    historical = {}
    from scripts import isae_suite_sa15 as sa15
    declared_sa15 = ({j['id']: j for j in sa15.plan(root)}
                    if any(sa15.identifies(j) for j in merged['jobs']) else {})
    for job in merged['jobs']:
        if sa15.identifies(job):
            original = declared_sa15.get(job['id'])
            require(original is not None and all(job.get(k) == v for k, v in original.items()),
                    'SA15 job differs from original source, declared setup or numerical code.')
            for item in original['sources'] + original['kernel_pins']:
                current(root / item['path'])
            scalar_counts(job)
        if historical_polar(job):
            polar_channels(job)
            pairing = job['source_pairing']['id']
            if pairing not in historical:
                from scripts.isae_suite_extra_polars import plan_source_pairing
                rows = plan_source_pairing(root, pairing)
                historical[pairing] = {row['id']: row for row in rows}
                require(len(historical[pairing]) == len(rows), 'Duplicate historical source job.')
            original = historical[pairing].get(job['id'])
            require(original is not None and all(job.get(key) == value for key, value in original.items()),
                    'Historical polar job differs from its reviewed source pairing, setup or targets.')
            for item in original.get('sources', []):
                current(root / item['path'])
            scalar_counts(job)
        if job['adapter'] in ('p2', 'ae5', 'ffwt3'):
            verify_reference_lines(job, root)
            scalar_counts(job)
        elif job['adapter'] == 'structure':
            job['_summary_reference_contract'] = load_structure_contract(job, root)
            scalar_counts(job)
        elif job['adapter'] in ('sa11', 'sa12'):
            verify_reference_lines(job, root)
            scalar_counts(job)
        elif job['adapter'] in ('modes', 'aeroelastic', 'sa6', 'st2', 'st3', 'st4', 'st5', 'ap1', 'ap2', 'ae1', 'ae3', 'ae4', 'ae6', 'st1', 'sa13'):
            if job['adapter'] in canonical:
                original = canonical[job['adapter']].get(job['id'])
                require(original is not None and all(job.get(key) == value for key, value in original.items()),
                        'Job differs from original sources, declared setup or current numerical code.')
            else:
                verify_reference_lines(job, root)
            if st2_mechanics(job) and job.get('result'):
                from scripts.isae_suite_st2_mechanics import verify_artifacts
                for artifact in verify_artifacts(root, job, strict_policy_job(job)['result']):
                    remember(artifact)
            if st5_mechanics(job) and job.get('result'):
                from scripts.isae_suite_st5_mechanics import verify_artifacts
                for artifact in verify_artifacts(root, job, strict_policy_job(job)['result']):
                    remember(artifact)
            if st4_mechanics(job) and job.get('result'):
                from scripts.isae_suite_st4_mechanics import verify_artifacts
                for artifact in verify_artifacts(root, job, strict_policy_job(job)['result']):
                    remember(artifact)
            if st3_mechanics(job) and job.get('result'):
                from scripts.isae_suite_st3_mechanics import verify_artifacts
                for artifact in verify_artifacts(root, job, strict_policy_job(job)['result']):
                    remember(artifact)
            if job['adapter'] in ('ae4', 'ae6'):
                module = importlib.import_module('scripts.isae_suite_' + job['adapter'])
                if job.get('result'):
                    module.verify_artifacts(root, strict_policy_job(job)['result'])
                    for artifact in job['result'].get('artifacts', []):
                        remember(artifact)
            builder = {'modes': modes_contract, 'aeroelastic': aeroelastic_contract,
                       'sa6': sa6_contract, 'st2': st2_contract, 'st3': st3_contract, 'st4': st4_contract, 'st5': st5_contract, 'ap1': ap1_contract,
                       'ap2': ap2_contract, 'ae1': ae1_contract, 'ae3': ae3_contract, 'st1': st1_contract,
                       'sa13': sa13_contract, 'ae4': ae4_contract, 'ae6': ae6_contract}[job['adapter']]
            job['_summary_reference_contract'] = builder(job)
            scalar_counts(job)
    force_units = {}
    for job in merged['jobs']:
        if job['adapter'] not in POLAR_ADAPTERS or job['model_path'] in force_units:
            continue
        text = (root / job['model_path']).read_text()
        block = re.search(r'^\s*Unit\s*$\n(.*?)^\s*End\s*$', text, re.M | re.S | re.I)
        declaration = re.search(r'^\s*F\s+(\S+)\s+(\S+)', block[1], re.M) if block else None
        label = 'input F (declaration not recovered)'
        if declaration:
            scale = float(declaration[1].replace('D', 'E').replace('d', 'e'))
            label = 'N' if scale == 1 and declaration[2] == 'N' else f'input F ({declaration[1]} {declaration[2]})'
        force_units[job['model_path']] = label
    merged.update(inputs=input_pins, source_files_verified=len(upstream), force_units=force_units,
                  _verified_file_pins=list(verified.values()), _verified_root=str(root),
                  runner_versions=[packet['report']['code_sha256'].get('scripts/run-isae-suite.py') for packet in packets])
    verify_summary_sources(merged)
    return merged


def verify_summary_sources(merged):
    """Rehash the bounded verified context; any change aborts publication."""
    root = Path(merged['_verified_root'])
    require({p.relative_to(root).as_posix() for p in (root/'openswing').glob('*.py')} == set(merged['kernel_pins']),
            'Numerical kernel file inventory changed during summary.')
    for item in merged['_verified_file_pins']:
        require(pin(item['path']) == item, 'Verified file changed during summary: ' + item['path'])


def error_stats(jobs, channel):
    errors, absent, unavailable, failed = [], 0, 0, 0
    finite_predictions = passed = accepted = 0
    for job in jobs:
        result = job.get('result')
        if result and 'reference_acceptance_policy' in result:
            scalar_counts(job)  # Verify policy and the underlying strict contract.
        valid = numerically_valid(result)
        failed += not valid
        check = next((item for item in (result or {}).get('reference_checks', []) if item['name'] == channel), None)
        if check is None:
            absent += 1
            continue
        finite_predictions += finite(check.get('predicted'))
        if not finite(check.get('predicted')):
            unavailable += 1
        if valid and finite(check.get('predicted')) and finite(check.get('expected')):
            error = abs(check['predicted'] - check['expected'])
            require(math.isfinite(error), 'Nonfinite difference in a numerically valid comparison.')
            errors.append(error)
            strict_pass = precision_pass(check, exact_decimal=job.get('adapter') in ('st1', 'st4') or
                job.get('adapter') == 'st2' and job.get('target_kind') == 'native_modal' or
                st3_mechanics(job) and job.get('target_kind') == 'modal' or sa6_derivatives(job))
            passed += strict_pass
            accepted += check.get('passed') is True if result.get('reference_acceptance_policy') else strict_pass
    norm = 0.
    for error in errors:
        norm = math.hypot(norm, error)
    return {'required_rows': len(jobs), 'reported_rows': len(jobs) - absent,
            'finite_predictions': finite_predictions, 'valid_comparison_pairs': len(errors),
            'precision_passed': passed, 'acceptance_passed': accepted, 'absent_rows': absent,
            'unavailable_predictions': unavailable, 'failed_or_unrun_rows': failed,
            'rmse': norm / math.sqrt(len(errors)) if errors else None,
            'maximum_absolute_error': max(errors) if errors else None}


def polar_tables(jobs, force_units=None):
    by_row = defaultdict(list)
    for job in jobs:
        if job['adapter'] in POLAR_ADAPTERS:
            pairing = job.get('source_pairing', {}).get('id', '')
            scope = job.get('comparison_scope', '')
            by_row[(job['case_id'], job['table_path'], job['row_index'], pairing, scope)].append(job)
    tables = defaultdict(list)
    for (case, table, index, pairing, scope), rows in by_row.items():
        require(len(rows) == 2 and len({j['settings']['panels'] for j in rows}) == 2,
                'Every polar row requires its two declared meshes; extra refinements need an explicit new summary policy.')
        rows.sort(key=lambda j: j['settings']['panels'])
        keys = set(rows[0]['settings']) | set(rows[1]['settings'])
        require(all(rows[0]['settings'].get(k) == rows[1]['settings'].get(k)
                    for k in keys - {'panels', 'mesh_level'}), 'Paired mesh physical settings differ.')
        require(rows[0]['reference_row'] == rows[1]['reference_row'] and rows[0]['sources'] == rows[1]['sources'],
                'Paired mesh reference/source provenance differs.')
        require(rows[0]['adapter'] == rows[1]['adapter'] and rows[0].get('required_outputs') == rows[1].get('required_outputs'),
                'Paired mesh required-output scope differs.')
        tables[(case, table, pairing, scope)].append(rows[1])  # Predeclared finer count, even if it fails.
    result = []
    for (case, table, pairing, scope), fine in sorted(tables.items()):
        fine.sort(key=lambda j: j['row_index'])
        require([j['row_index'] for j in fine] == list(range(len(fine))), 'Polar table row coverage is incomplete.')
        channels = polar_channels(fine[0])
        require(all((tuple(j.get('required_outputs', CHANNELS)) == tuple(channels)) for j in fine),
                'Polar table mixes required-output scopes.')
        result.append({'case_id': case, 'table_path': table, 'model_path': fine[0]['model_path'],
                       'selection': 'Larger predeclared nominal panel count; no selection by agreement or successful outcome.',
                       'fine_panels': sorted({j['settings']['panels'] for j in fine}),
                       'rows': len(fine), 'scalar_counts': totals(fine),
                       'channels': {key: dict(error_stats(fine, key), unit=(force_units or {}).get(fine[0]['model_path'], 'input F') if key in ('lift', 'drag') else '1')
                                    for key in channels}})
        if pairing:
            result[-1].update(source_pairing_id=pairing,
                             comparison_scope='supplemental_historical_source_pairing',
                             existing_native_targets_reused=True)
        elif scope:
            result[-1].update(comparison_scope=scope, existing_native_targets_reused=True)
    return result


def sa6_tables(jobs, *, controls=False, states=False, mass=False):
    require(sum((controls, states, mass)) <= 1, 'Choose a single SA6 table scope.')
    scope = 'sa6-mass-rigid' if mass else 'sa6-state-rigid' if states else 'sa6-f1-rigid' if controls else 'static'
    grouped = defaultdict(list)
    for job in jobs:
        if job['adapter'] == 'sa6' and job['expected_outputs'] and job.get('comparison_scope', 'static') == scope:
            grouped[job['model_path']].append(job)
    tables = []
    for model, rows in sorted(grouped.items()):
        by_index = defaultdict(list)
        for row in rows:
            by_index[row['row_index']].append(row)
        require(all(type(index) is int and 0 <= index < 11 for index in by_index), 'SA6 original operating index changed.')
        fine = []
        for index, pair in sorted(by_index.items()):
            pair.sort(key=lambda j: j['settings']['panels'])
            meshes = [j['settings']['panels'] for j in pair]
            require(len(set(meshes)) == len(meshes) and set(meshes).issubset({64, 128}), 'SA6 declared mesh pair changed.')
            if len(pair) == 2:
                keys = set(pair[0]['settings']) | set(pair[1]['settings'])
                require(all(pair[0]['settings'].get(k) == pair[1]['settings'].get(k) for k in keys-{'panels', 'mesh_level'}) and
                        pair[0]['reference_row'] == pair[1]['reference_row'] and pair[0]['sources'] == pair[1]['sources'],
                        'SA6 paired mesh inputs or references differ.')
            fine.extend(j for j in pair if j['settings']['panels'] == 128)
        if not fine:
            continue  # Selected coarse jobs remain in the full scalar/scope ledgers.
        channels = (tuple(fine[0]['required_outputs']) if mass else tuple(name+suffix for name in SA6_CHANNELS for suffix in ('u','a','b','p','q','r')) if states
                    else tuple(name+'dF1' for name in SA6_CHANNELS) if controls else SA6_CHANNELS)
        tables.append(dict(case_id='SA-6', model_path=model, table_paths=[j['table_path'] for j in fine],
            fine_panels=[128], rows=len(fine), scalar_counts=totals(fine),
            control_source=('Original MATLAB postprocessor; original shell driver absent'
                            if all(sa6_postprocessor(j) for j in fine) else
                            'Original shell driver' if all(j.get('driver_path') for j in fine) else
                            'Unresolved original control settings'),
            selection='Only supplied jobs at predeclared128 count; no coarse substitution, selection by outcome or mesh-convergence claim.',
            comparison_scope=scope,
            channels={name: dict(error_stats(fine, name), unit=(('kg m^2' if 'inertia' in name else 'kg') if mass else 'per '+fine[0]['parameter_units'][i%6] if states
                else 'per file control unit' if controls else '1')) for i,name in enumerate(channels)}))
    return tables


def sa6_mesh_diagnostics(jobs):
    selected = [j for j in jobs if j.get('adapter') == 'sa6']
    if not selected:
        return []
    from scripts.isae_suite_sa6 import mesh_diagnostics
    return mesh_diagnostics(selected, {j['id']:j['result'] for j in selected if j.get('result') is not None})


def st3_modal_mesh_diagnostics(jobs):
    selected = [j for j in jobs if j.get('adapter') == 'st3_modal']
    if not selected:
        return []
    from scripts.isae_suite_st3_modal import mesh_diagnostics
    return mesh_diagnostics(selected, {j['id']: j['result'] for j in selected if j.get('result') is not None})


def ae4_mesh_diagnostics(jobs):
    selected = [j for j in jobs if j.get('adapter') == 'ae4']
    if not selected:
        return []
    from scripts.isae_suite_ae4 import mesh_diagnostics
    return mesh_diagnostics(selected, {j['id']:j['result'] for j in selected if j.get('result') is not None})


def ae6_mesh_diagnostics(jobs):
    from scripts.isae_suite_ae6 import mesh_diagnostics
    selected = [j for j in jobs if j.get('adapter') == 'ae6']
    return mesh_diagnostics(selected, {j['id']:j['result'] for j in selected if j.get('result') is not None})


def declared_scope(jobs):
    """Distinct models and archived samples, without multiplying by meshes."""
    models, samples = set(), set()
    for job in jobs:
        if not job['expected_outputs']:
            continue
        model = job.get('model_path', job.get('source'))
        if isinstance(model, str):
            models.add(model)
        adapter = job['adapter']
        if adapter in (*POLAR_ADAPTERS, 'sa6'):
            samples.add((job['table_path'], job['row_index']))
        elif adapter == 'structure':
            origin = json.dumps(job['target_origin'], sort_keys=True)
            samples.update((origin, i) for i in range(job['rows_per_grid']))
        elif adapter in ('modes', 'ae4', 'ae6'):
            samples.update((job['table_path'], row['line']) for row in job.get('reference_rows', []))
            samples.update((job['table_path'], row['source_line']) for row in job.get('aggregate_targets', []))
        elif st2_mechanics(job) or st3_mechanics(job) or st4_mechanics(job) or st5_mechanics(job):
            samples.update((row['source'], row['name']) for row in job['observations'])
        elif adapter == 'st2':
            samples.update((job['table_path'], row['line_number']) for row in job['reference_rows'])
            if job['target_kind'] == 'workbook_summary':
                samples.update((job['table_path'], row['source_line']) for row in job['observations'])
        elif adapter in ('ap1', 'ae1'):
            samples.update((job['table_path'], row['row_number']) for row in job['reference_rows'])
        elif adapter == 'st3_modal':
            samples.update((job['table_path'], row['cell']) for row in job['observations'])
        elif adapter in ('ae3', 'st1'):
            # AE3 native tables share line numbers across separate tensors.
            # Its source-qualified observation names identify the stored cells.
            samples.update((job['table_path'], row['name']) for row in job['observations'])
        elif adapter == 'sa13':
            samples.update((job['table_path'], job['variant'], row['source_row_1based'])
                           for row in job['observations'])
        elif adapter == 'ap2':
            if job['target_kind'] == 'grid_state':
                samples.update((job['table_path'], job['coordinate_id'], row['grid_row'], row['grid_column'])
                               for row in job['reference_rows'])
            else:
                samples.update((job['table_path'], row['row_number']) for row in job['reference_rows'])
        elif adapter == 'aeroelastic':
            row = job['reference_row']
            index = row['output_file_line_1based'] if job['case_id'] == 'AE-2' else row['file_line']
            samples.add((job['source_output']['path'], index))
        elif adapter == 'components':
            samples.update((job['reference']['original_figure']+row['source_series_label'], row['index'])
                           for row in job['observations'])
    scope = dict(models_with_target_scopes=sorted(models), unique_model_count=len(models),
                original_reference_samples=len(samples),
                definition='Distinct original table rows, modal rows, structural stations, AP2 MAT grid cells, AE3/ST1 stored numeric cells or archived curve samples; mesh repeats excluded. Other aggregate tables count rows, not individual cells.')
    st3_modal = [job for job in jobs if job['adapter'] == 'st3_modal']
    ae4 = [job for job in jobs if job['adapter'] == 'ae4']
    if ae4:
        finite_rows = set()
        for job in ae4:
            result = job.get('result')
            if not numerically_valid(result):
                continue
            values = {c['name']:c.get('predicted') for c in result['reference_checks']}
            for row in job['reference_rows']:
                if all(finite(values.get(f"line{row['line']}:{component}")) for component in ('real','imaginary')):
                    finite_rows.add((job['table_path'],row['line']))
        scope.update(ae4_modal_tables=len({j['table_path'] for j in ae4}),
            ae4_stored_modal_rows=len({(j['table_path'],r['line']) for j in ae4 for r in j['reference_rows']}),
            ae4_distinct_file_content_modal_rows=len({(j['table_sha256'],r['line']) for j in ae4 for r in j['reference_rows']}),
            ae4_declared_scalar_slots=sum(j['expected_outputs'] for j in ae4 if j['comparison_scope']=='ae4-undeformed-alpha0'),
            ae4_historical_scalar_slots=sum(j['expected_outputs'] for j in ae4 if j['comparison_scope']=='historical-modal-exports'),
            ae4_rows_with_finite_predictions=len(finite_rows),
            ae4_other_sensor_time_scopes_covered=False)
    ae6 = [job for job in jobs if job['adapter'] == 'ae6']
    if ae6:
        finite_rows = set()
        for job in ae6:
            result = job.get('result')
            if not numerically_valid(result):
                continue
            values = {c['name']:c.get('predicted') for c in result['reference_checks']}
            for row in job['reference_rows']:
                if all(finite(values.get(f"line{row['line']}:{component}")) for component in ('real','imaginary')):
                    finite_rows.add((job['table_path'],row['line']))
        scope.update(ae6_modal_tables=len({j['table_path'] for j in ae6}),
            ae6_stored_modal_rows=len({(j['table_path'],r['line']) for j in ae6 for r in j['reference_rows']}),
            ae6_distinct_file_content_modal_rows=len({(j['table_sha256'],r['line']) for j in ae6 for r in j['reference_rows']}),
            ae6_declared_scalar_slots=sum(j['expected_outputs'] for j in ae6 if j['comparison_scope']=='ae6-declared-airflow'),
            ae6_historical_scalar_slots=sum(j['expected_outputs'] for j in ae6 if j['comparison_scope']=='historical-modal-exports'),
            ae6_rows_with_finite_predictions=len(finite_rows),
            ae6_all_modal_tables_duplicate_st4=all(len(j['ST4_overlaps'])==3 and all(p['identical'] for p in j['ST4_overlaps']) for j in ae6),
            ae6_other_sensor_time_scopes_covered=False)
    if st3_modal:
        # Rank names repeat across layups; original cell addresses do not.
        cells = {(job['table_path'], row['cell']) for job in st3_modal for row in job['observations']}
        scope.update(qualified_st3_workbook_cells=len(cells),
            conditional_st3_modal_scalar_slots=sum(j['expected_outputs'] for j in st3_modal),
            conditional_st3_modal_jobs=len(st3_modal), historical_modal_identity_verified=False)
    mechanics = [job for job in jobs if st2_mechanics(job) or st3_mechanics(job) or st4_mechanics(job) or st5_mechanics(job)]
    if mechanics:
        distinct = lambda rows: len({(r['source'],r['name']) for j in rows for r in j['observations']})
        scope.update(mechanics_scalar_targets=distinct(mechanics),
                     mechanics_static_targets=distinct([j for j in mechanics if j['target_kind']=='static']),
                     mechanics_modal_targets=distinct([j for j in mechanics if j['target_kind']=='modal']),
                     mechanics_jobs=len(mechanics),
                     mechanics_scalar_slots=sum(j['expected_outputs'] for j in mechanics),
                     mechanics_setup='Explicit static tip-pylon reconstruction; literal modal files with declared still-air settings. Mesh repeats and unloaded states add no votes.')
        if any(st3_mechanics(j) for j in mechanics):
            scope['unavailable_reference_targets'] = sum(not r.get('source_available', True) for j in mechanics for r in j['observations'])
            scope['mechanics_setup'] = ('Reviewed ST2/ST3 physical scopes; ' if any(st2_mechanics(j) for j in mechanics) else '') + 'Original ST3 static signed-load scripts and modal files; two clipped static ordinates stay unavailable. Both meshes are required and add no votes.'
    if any(st4_mechanics(j) for j in mechanics):
        scope['st4_frequency_targets'] = distinct([j for j in mechanics if st4_mechanics(j)])
        scope['st4_setup'] = 'Original models, fixed-frame vacuum, zero gravity; both meshes required. Paper72 and native31 overlap and stay separate. Native mode identity and airflow remain open.'
        if all(st4_mechanics(j) for j in mechanics):
            scope['mechanics_setup'] = scope['st4_setup']
    if any(st5_mechanics(j) for j in mechanics):
        scope['st5_structural_targets'] = distinct([j for j in mechanics if st5_mechanics(j)])
        scope['st5_setup'] = 'Native static observations at archived stations; five cold physical states and independent final 0.1% field convergence. No repeated-mesh votes. Legacy and unresolved evidence remain separate.'
        if all(st5_mechanics(j) for j in mechanics):
            scope['mechanics_setup'] = scope['st5_setup']
    st2 = [job for job in jobs if job['adapter'] == 'st2' and not st2_mechanics(job)]
    if st2:
        native = [job for job in st2 if job['target_kind'].startswith('native_')]
        workbooks = [job for job in st2 if job['target_kind'] == 'workbook_summary']
        modal = [job for job in native if job['target_kind'] == 'native_modal']
        scope.update(native_reference_samples=len({(job['table_path'], row['line_number'])
                                                  for job in native for row in job['reference_rows']}),
                     native_scalar_targets=len({(job['table_path'], row['name'])
                                                for job in native for row in job['observations']}),
                     native_scalar_slots=sum(job['expected_outputs'] for job in native),
                     modal_reference_roots=len({(job['table_path'], row['line_number'])
                                               for job in modal for row in job['reference_rows']}),
                     modal_distinct_scalar_targets=len({(job['table_path'], row['name'])
                                                        for job in modal for row in job['observations']}),
                     conditional_modal_jobs=sum(job['execution_route'] == 'worker' for job in modal),
                     conditional_modal_scalar_slots=sum(job['expected_outputs'] for job in modal
                                                        if job['execution_route'] == 'worker'),
                     blocked_scalar_slots=sum(job['expected_outputs'] for job in st2
                                              if job['execution_route'] == 'unsupported'),
                     qualified_workbook_cells=sum(len(job['observations']) for job in workbooks),
                     qualified_workbook_scalar_targets=sum(job['expected_outputs'] for job in workbooks),
                     literal_model_inventory_records=sum(job['target_kind'] == 'model_inventory' for job in st2))
    ap1 = [job for job in jobs if job['adapter'] == 'ap1']
    if ap1:
        def rows_for(kinds):
            return {(job['table_path'], row['row_number']) for job in ap1 if job['target_kind'] in kinds
                    for row in job['reference_rows']}
        scope.update(span_reference_samples=len(rows_for(('paired_span', 'unpaired_span_and_header'))),
                     operating_reference_samples=len(rows_for(('unpaired_operating',))),
                     header_reference_states=len({job['table_path'] for job in ap1
                         if job['target_kind'] in ('paired_header', 'unpaired_span_and_header')}),
                     paired_header_scalar_targets=sum(job['expected_outputs'] for job in ap1
                         if job['target_kind'] == 'paired_header'))
    ap2 = [job for job in jobs if job['adapter'] == 'ap2']
    if ap2:
        grid = [job for job in ap2 if job['target_kind'] == 'grid_state']
        unpaired = [job for job in ap2 if job['target_kind'] == 'unpaired_operating']
        scope.update(mat_grid_cells=len({(job['table_path'], job['coordinate_id'], row['grid_row'], row['grid_column'])
                                         for job in grid for row in job['reference_rows']}),
                     unpaired_operating_rows=len({(job['table_path'], row['row_number'])
                                                  for job in unpaired for row in job['reference_rows']}),
                     final_csv_witness_states=len({job['coordinate_id'] for job in grid
                                                   if {'CL', 'CD'} <= set(ap2_contract(job))}),
                     mat_binary_identity_scalar_targets=sum('CL_CD_ratio' in ap2_contract(job) for job in grid),
                     final_csv_printed_scalar_targets=sum(len(set(ap2_contract(job)) & {'CL', 'CD'}) for job in grid),
                     unpaired_txt_scalar_targets=sum(job['expected_outputs'] for job in unpaired))
    ae1 = [job for job in jobs if job['adapter'] == 'ae1']
    if ae1:
        paired = [job for job in ae1 if job['target_kind'] == 'paired_sensor']
        initial = [job for job in ae1 if job['target_kind'] == 'initial_operating_unknown']
        scope.update(sensor_reference_rows=len({(job['table_path'], row['row_number'])
                                                for job in ae1 for row in job['reference_rows']}),
                     conditional_operating_rows=len({(job['table_path'], row['row_number'])
                                                      for job in paired for row in job['reference_rows']}),
                     unknown_initial_rows=len({(job['table_path'], row['row_number'])
                                               for job in initial for row in job['reference_rows']}),
                     conditional_sensor_scalar_targets=sum(job['expected_outputs'] for job in paired),
                     blocked_initial_scalar_targets=sum(job['expected_outputs'] for job in initial))
    ae3 = [job for job in jobs if job['adapter'] == 'ae3']
    if ae3:
        native = [job for job in ae3 if re.search(r'\.fmat_\d+$', job.get('table_path') or '')]
        embedded = [job for job in ae3 if job['target_kind'] == 'embedded_source_array']
        coefficients = [job for job in native if job['target_kind'] == 'native_coefficients']
        scope.update(native_reference_states=len({job['table_path'] for job in native}),
                     native_distinct_scalar_targets=len({(job['table_path'], row['name'])
                                                         for job in native for row in job['observations']}),
                     native_scalar_slots=sum(job['expected_outputs'] for job in native),
                     coefficient_reference_states=len({job['table_path'] for job in coefficients}),
                     coefficient_scalar_slots=sum(job['expected_outputs'] for job in coefficients),
                     embedded_distinct_scalar_targets=len({(job['table_path'], row['name'])
                                                           for job in embedded for row in job['observations']}),
                     embedded_scalar_slots=sum(job['expected_outputs'] for job in embedded),
                     embedded_slots_by_scope={kind: sum(job['expected_outputs'] for job in embedded
                         if job['embedded_kind'] == kind) for kind in sorted({job['embedded_kind'] for job in embedded})},
                     literal_model_inventory_records=sum(job['target_kind'] == 'model_inventory' for job in ae3))
    st1 = [job for job in jobs if job['adapter'] == 'st1']
    if st1:
        native = [job for job in st1 if job.get('table_path') is not None]
        positions = [job for job in native if job['target_kind'] in ('native_position', 'blocked_native_position')]
        eigenvalues = [job for job in native if job['target_kind'] == 'blocked_native_eigenvalues']
        conditional = [job for job in positions if job['target_kind'] == 'native_position']
        candidates = {item['source']['path']: item for job in st1 for item in job.get('output_candidates', [])}
        distinct = lambda rows: len({(job['table_path'], obs['name']) for job in rows for obs in job['observations']})
        row_count = lambda rows: len({(job['table_path'], row['row_number']) for job in rows for row in job['reference_rows']})
        scope.update(native_reference_files=len({job['table_path'] for job in native}),
                     native_reference_rows=row_count(native), native_distinct_scalar_targets=distinct(native),
                     native_scalar_slots=sum(job['expected_outputs'] for job in native),
                     position_reference_rows=row_count(positions), position_distinct_scalar_targets=distinct(positions),
                     position_scalar_slots=sum(job['expected_outputs'] for job in positions),
                     eigenvalue_reference_roots=row_count(eigenvalues), eigenvalue_distinct_scalar_targets=distinct(eigenvalues),
                     real_only_reference_roots=len({(job['table_path'], row['row_number']) for job in eigenvalues
                                                   for row in job['reference_rows'] if row['real_only_root']}),
                     conditional_position_reference_rows=row_count(conditional),
                     conditional_position_scalar_slots=sum(job['expected_outputs'] for job in conditional),
                     blocked_native_scalar_slots=sum(job['expected_outputs'] for job in native if job['execution_route'] == 'unsupported'),
                     literal_models_covered=len({job['model_path'] for job in st1 if job.get('model_path')}),
                     literal_model_inventory_records=sum(job['target_kind'] == 'model_inventory' for job in st1),
                     inventoried_output_candidates=len(candidates),
                     candidate_files_by_classification=dict(Counter(item['classification'] for item in candidates.values())),
                     additional_arrays_and_plots_outside_native_denominator=True,
                     supplemental_duplicate_tree_adds_independent_targets=False)
    historical = [job for job in jobs if historical_polar(job)]
    if historical:
        scope.update(historical_source_pairings=sorted({job['source_pairing']['id'] for job in historical}),
                     supplemental_historical_jobs=len(historical),
                     supplemental_historical_scalar_slots=sum(job['expected_outputs'] for job in historical),
                     historical_pairings_reuse_existing_native_targets=True,
                     historical_producer_execution_authenticated=False)
    sa6 = [job for job in jobs if job['adapter'] == 'sa6']
    if sa6:
        scopes = {name:[j for j in sa6 if j.get('comparison_scope', 'static') == name]
                  for name in ('static', 'sa6-f1-rigid', 'sa6-state-rigid', 'sa6-mass-rigid')}
        scope['sa6_comparison_scopes'] = {name: dict(
            jobs=len(rows), scalar_slots=sum(j['expected_outputs'] for j in rows),
            native_states=len({j['table_path'] for j in rows if j.get('table_path')}),
            distinct_native_cells=len({(j['table_path'], channel) for j in rows for channel in j.get('required_outputs', [])}),
            conditional=name != 'static') for name, rows in scopes.items() if rows}
    sa13 = [job for job in jobs if job['adapter'] == 'sa13']
    if sa13:
        scope.update(aswing_figure_series=len(sa13),
            figure_ordinate_slots=sum(j['expected_outputs'] for j in sa13),
            finite_figure_ordinates=sum(j['finite_reference_outputs'] for j in sa13),
            unavailable_figure_ordinates=sum(j['unavailable_reference_outputs'] for j in sa13),
            original_discretization_finite_ordinates=sum(j['finite_reference_outputs'] for j in sa13 if j['variant']=='discrete'),
            modified_aswing_finite_ordinates=sum(j['finite_reference_outputs'] for j in sa13 if j['variant']=='continuous'),
            original_model_and_setup_available=False, figure_precision_contract_established=False)
    return scope


def summarize(merged):
    catalog, jobs = merged['catalog'], merged['jobs']
    families = []
    for case in catalog['cases']:
        selected = [job for job in jobs if job['case_id'] == case['id']]
        counts = totals(selected)
        unsupported = [j for j in selected if (j.get('result') or {}).get('status') == 'unsupported']
        failed = [j for j in selected if j.get('result') is not None and
                  not numerically_valid(j['result']) and j['result'].get('status') != 'unsupported']
        status = ('NO_COMPARISON_JOBS_IN_SUPPLIED_RUNS' if not selected else
                  'INCOMPLETE_RUN' if any(j.get('result') is None for j in selected) else
                  'NUMERICAL_OR_INPUT_FAILURES' if failed else
                  'DECLARED_SCOPE_UNSUPPORTED' if len(unsupported) == len(selected) else
                  'PARTLY_UNSUPPORTED_SCOPE' if unsupported else
                  'AVAILABLE_REFERENCES_MATCH' if all(st3_mechanics(j) for j in selected)
                    and counts['reported_unavailable'] > 0
                    and counts['reported_unavailable'] == sum(not r['source_available'] for j in selected for r in j['observations'])
                    and counts['passed'] == counts['required']-counts['reported_unavailable'] else
                  'SELECTED_SCOPE_MATCHES' if counts['passed'] == counts['required'] else 'ARCHIVED_OUTPUT_DIFFERENCES')
        scope = declared_scope(selected)
        computed_scope = declared_scope([j for j in selected if numerically_valid(j.get('result'))])
        scope.update(models_with_numerical_results=computed_scope['unique_model_count'],
                     numerically_valid_reference_samples=computed_scope['original_reference_samples'])
        if any(st2_mechanics(job) or st3_mechanics(job) or st4_mechanics(job) or st5_mechanics(job) for job in selected):
            scope['numerically_valid_mechanics_targets'] = computed_scope.get('mechanics_scalar_targets', 0) - computed_scope.get('unavailable_reference_targets', 0)
            scope['numerically_valid_reference_samples'] -= computed_scope.get('unavailable_reference_targets', 0)
        elif any(job['adapter'] == 'st2' for job in selected):
            scope.update(numerically_valid_modal_reference_roots=computed_scope.get('modal_reference_roots', 0),
                         numerically_valid_native_distinct_scalars=computed_scope.get('native_scalar_targets', 0))
        if any(job['adapter'] == 'ap1' for job in selected):
            scope.update(numerically_valid_header_reference_states=computed_scope.get('header_reference_states', 0),
                         numerically_valid_span_reference_samples=computed_scope.get('span_reference_samples', 0),
                         numerically_valid_operating_reference_samples=computed_scope.get('operating_reference_samples', 0))
        if any(job['adapter'] == 'ap2' for job in selected):
            scope.update(numerically_valid_mat_grid_cells=computed_scope.get('mat_grid_cells', 0),
                         numerically_valid_final_csv_witness_states=computed_scope.get('final_csv_witness_states', 0),
                         numerically_valid_unpaired_operating_rows=computed_scope.get('unpaired_operating_rows', 0))
        if any(job['adapter'] == 'ae1' for job in selected):
            scope.update(numerically_valid_conditional_operating_rows=computed_scope.get('conditional_operating_rows', 0),
                         numerically_valid_initial_rows=computed_scope.get('unknown_initial_rows', 0))
        if any(job['adapter'] == 'ae3' for job in selected):
            scope.update(numerically_valid_coefficient_states=computed_scope.get('coefficient_reference_states', 0),
                         numerically_valid_native_distinct_scalars=computed_scope.get('native_distinct_scalar_targets', 0),
                         numerically_valid_embedded_scalars=computed_scope.get('embedded_distinct_scalar_targets', 0))
        if any(job['adapter'] == 'ae4' for job in selected):
            scope['numerically_valid_reference_samples'] = computed_scope.get('ae4_rows_with_finite_predictions', 0)
        if any(job['adapter'] == 'ae6' for job in selected):
            scope['numerically_valid_reference_samples'] = computed_scope.get('ae6_rows_with_finite_predictions', 0)
        if any(job['adapter'] == 'st1' for job in selected):
            scope.update(numerically_valid_position_reference_rows=computed_scope.get('conditional_position_reference_rows', 0),
                         numerically_valid_native_distinct_scalars=computed_scope.get('native_distinct_scalar_targets', 0),
                         numerically_valid_eigenvalue_roots=computed_scope.get('eigenvalue_reference_roots', 0))
        families.append({'id': case['id'], 'path': case['path'], 'status': status,
                         'jobs_planned': len(selected), 'jobs_finished': sum(job.get('result') is not None for job in selected),
                         'job_status_counts': dict(Counter((j.get('result') or {}).get('status', 'unrun') for j in selected)),
                         'unsupported_jobs': len(unsupported), 'failed_jobs': len(failed),
                         'model_inventory_jobs_without_targets': sum(j['expected_outputs'] == 0 for j in selected),
                         'scalar_counts': counts, 'original_models': len(case['models']),
                         'reference_candidates': len(case['reference_candidates']),
                         'declared_scope': scope,
                         'complete_family_reproduction': False})
        if case['id'] in ('SA-6', 'AE-1', 'SA-15', 'AE-4', 'AE-6') or any(st2_mechanics(j) or st3_mechanics(j) or st4_mechanics(j) or st5_mechanics(j) for j in selected):
            families[-1]['comparison_scopes'] = {name: totals([j for j in selected
                if j.get('comparison_scope', 'static') == name])
                for name in sorted({j.get('comparison_scope', 'static') for j in selected})}
    p1 = [job for job in jobs if job['case_id'] == 'P-1' and job['adapter'] == 'components']
    errors = [abs(check['predicted'] - check['expected']) for job in p1 if numerically_valid(job.get('result'))
              for check in job['result']['reference_checks'] if finite(check.get('predicted')) and finite(check.get('expected'))]
    return {'status': 'RECORDED_WITH_OPEN_COMPARISONS', 'full_suite_validated': False,
            'acceptance_target': 'Original archived ASWING outputs; experimental agreement is not required.',
            'reference_acceptance': merged.get('reference_acceptance'),
            'strict_scalar_counts': totals([strict_policy_job(job) for job in jobs]),
            'family_count': len(families), 'jobs': len(jobs), 'scalar_counts': totals(jobs),
            'families': families,
            'missing_adapters': [row['id'] for row in families if not row['jobs_planned']],
            'fine_grid_polar_tables': polar_tables(jobs, merged.get('force_units')),
            'fine_grid_sa6_coefficients': sa6_tables(jobs),
            'fine_grid_sa6_control_derivatives': sa6_tables(jobs, controls=True),
            'fine_grid_sa6_state_derivatives': sa6_tables(jobs, states=True),
            'fine_grid_sa6_mass_tensors': sa6_tables(jobs, mass=True),
            'sa6_mesh_diagnostics': sa6_mesh_diagnostics(jobs),
            'ap1_mesh_diagnostics': ap1_mesh_diagnostics(jobs),
            'ap2_mesh_diagnostics': ap2_mesh_diagnostics(jobs),
            'ae1_mesh_diagnostics': ae1_mesh_diagnostics(jobs),
            'ae3_mesh_diagnostics': ae3_mesh_diagnostics(jobs),
            'st1_mesh_diagnostics': st1_mesh_diagnostics(jobs),
            'st2_mesh_diagnostics': st2_mesh_diagnostics(jobs),
            'st5_mechanics_mesh_diagnostics': [dict(job_id=j['id'], checks=(j.get('result') or {}).get('mesh_checks', [])) for j in jobs if st5_mechanics(j)],
            'st4_mechanics_mesh_diagnostics': [dict(job_id=j['id'], checks=(j.get('result') or {}).get('mesh_checks', [])) for j in jobs if st4_mechanics(j)],
            'st3_mechanics_mesh_diagnostics': st3_mechanics_mesh_diagnostics(jobs),
            'st3_modal_mesh_diagnostics': st3_modal_mesh_diagnostics(jobs),
            'ae4_mesh_diagnostics': ae4_mesh_diagnostics(jobs),
            'ae6_mesh_diagnostics': ae6_mesh_diagnostics(jobs),
            'model_inventory_without_targets': [dict(id=j['id'], case_id=j['case_id'], model_path=j['model_path'],
                status=(j.get('result') or {}).get('status', 'unrun'), reason=j['unsupported_reason'])
                for j in jobs if j['expected_outputs'] == 0],
            'additional_scope_notes': [
                'Executable modal comparisons retain only the declared positive imaginary components within selected roots, not a complete spectrum or a globally lowest-mode claim.',
                'Blocked modal aggregate cells are ASWING-labelled reference candidates; their stored-cell precision is not recovered ASWING printed precision.',
                'Unpaired original models remain visible inventory jobs with no invented scalar targets; job completion is checked even when their scalar count is zero.',
                ('ST2 mechanics compares the declared published static ordinates and modal frequencies with fresh baselines, mesh and shape checks. Its explicit static tip-pylon reconstruction and literal modal inputs remain qualified; the overlapping legacy archive is not added to these counts.'
                 if any(st2_mechanics(j) for j in jobs) else
                 'ST2 retains all fourteen native complex roots, all static rows, separate workbook cells and six literal models. Its predeclared fixed-frame loaded vacuum/still-air surveys compare both root components by local ascending-imaginary ordinal under exact decimal printed intervals using Decimal(str(predicted)). Historical branch identity, medium and node arrays remain unrecovered; no globally lowest spectrum or whole-family claim follows. Static, workbook and inventory routes remain blocked.'),
                'AP1 executable comparisons cover declared positive-slope header/state channels only. Span recovery, zero-slope models and unpaired targets remain explicitly blocked; header comparisons cannot establish span validation.',
                'AP2 reconstructs declared parameter-grid states under explicit current setup assumptions. MAT ratios use zero-tolerance stored binary-cell identity diagnostics, not recovered ASWING print precision; paired final CSV witnesses retain decimal half-last-place gates. Unpaired TXT records remain blocked.',
                'AE1 retains all six native absolute Earth sensor outputs under a conditional mounted reconstruction of the unchanged literal model. Both initial states remain blocked. Source NODE I40 does not recover historical arrays; current nominal intervals40/80 were declared before comparisons. Mesh changes are descriptive and historical startup settings remain unknown.',
                'AE3 compares all six native finite-control coefficient states on predeclared80/160 interval meshes. All native derivatives, mass/inertia/centroid and rate output cells remain distinct blocked scopes; embedded original/modified-ASWING arrays retain separate provenance. Their source identities and precision are not interchangeable. No experimental target or old selected study counts as native agreement.',
                'ST1 retains all 197 native scalars from 27 files, including both components of all 76 complex roots and 25 real-only roots. The unchanged static [45_0]_3a anchor-position snapshot has two prospective 100/200 interval structural comparisons; other grammar, modal and pairing scopes remain blocked. Additional arrays/plots stay outside this native denominator. Exact decimal printed intervals use Decimal(str(predicted)); no baseline subtraction, absolute-value transform or fabricated sensor triad is permitted.',
                'Aeroelastic comparisons retain all four declared original channels; missing NaN rows remain unsupported, with no interpolation or zero replacement.'],
            'P1_CT': {'unit': '1', 'jobs': len(p1), 'scalar_counts': totals(p1),
                      'original_scope_outputs': 110, 'valid_comparison_pairs': len(errors),
                      'maximum_absolute_error': max(errors) if errors else None},
            'source_inventory_separate_from_output_counts': catalog['counts'],
            'test_counts_included': False, 'runtime': merged['runtime'],
            'kernel_pins': merged['kernel_pins'], 'helper_pins': merged['helper_pins'],
            'source_provenance': merged['source_provenance'],
            'inputs': merged.get('inputs', []), 'runner_versions': merged.get('runner_versions', []),
            'definitions': {
                'missing_adapters': 'Legacy key: families without comparison jobs in the supplied runs; this is not the global adapter-registry count.',
                'required': 'All declared scalar outputs, including failed and unrun jobs.',
                'reported': 'Unique named reference-check slots returned, including null/nonfinite predictions.',
                'finite': 'Reported finite numeric predictions, even from a failed numerical job.',
                'numerically_valid_finite': 'Finite predictions from jobs whose numerical checks passed.',
                'passed': 'Numerically valid finite predictions satisfying the declared reference acceptance policy; original strict outcomes remain separately recorded.',
                'absent': 'Required scalar slots with no returned reference check.',
                'reported_unavailable': 'Reported slots with no finite prediction; never substituted with zero.',
                'unsupported_required': 'Required slots in explicitly unsupported adapter scopes; distinct from numerical/input failures.',
                'failed_job_required': 'Required slots in completed numerical/input/process failures; excludes explicitly unsupported and unrun jobs.',
                'metrics': 'RMSE/max absolute error use numerically valid finite predicted/reference pairs only; exclusions retain explicit counts.',
                'force_units': 'Polar lift/drag use the literal model Unit F declaration, reported per table. No unit normalization is fitted.',
                'coefficient_units': 'CL, CD, CDi, Cm, span efficiency and CT are dimensionless (1).'},
            'limitations': ['Selected scope matches do not establish complete family reproduction or recovered historical settings.',
                'Aggregate scalar pass fractions are not a validation or completion percentage: counts include multiple meshes, repeated output recoveries and exact-zero channels.',
                'Fine-grid means the larger of the two predeclared counts, not demonstrated mesh convergence.',
                'Original strict reference gates are retained; a declared provisional relative policy may accept additional continuous outputs. Mesh and numerical validity gates remain unchanged.',
                'Original source import results and test evidence are separate from scalar output agreement.']}


def markdown(data):
    c = data['scalar_counts']
    lines = ['# Current ISAE archived-output comparisons', '',
             f"{data['family_count']} families are accounted for; {len(data['missing_adapters'])} have no comparison jobs in the supplied runs. "
             'The complete suite is not yet reproduced. Experimental agreement is not required.', '',
             f"Scalar outputs: **{c['required']} required**, {c['reported']} reported, {c['finite']} finite, "
             f"{c['numerically_valid_finite']} numerically valid and finite, **{c['passed']} matching**; "
             f"{c['absent']} absent and {c['reported_unavailable']} reported but unavailable. "
             f"{c['unsupported_required']} required outputs belong to explicitly unsupported scopes; "
             f"{c['failed_job_required']} belong to failed jobs.", '',
             'Aggregate scalar pass fractions are not a validation or completion percentage. Historical scopes can include multiple meshes, repeated output recoveries and exact-zero channels. Family status and the declared model/reference scope are the primary coverage measures; jobs are execution units, not distinct cases. Original samples below exclude mesh repeats and include unsupported reference rows.', '',
             '| Family | Computed/target models | Valid/original samples | Jobs finished/planned | Required | Reported | Finite | Valid finite | Passed | Absent | Unsupported | Current status |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    policy = data.get('reference_acceptance')
    if policy is not None:
        lines[2:2] = [f"Reference acceptance: **{100 * policy['relative_tolerance']:g}%** relative error "
            "or the original absolute tolerance, whichever is larger. "
            f"References with magnitude ≤ {policy['tiny_reference']:g} keep their original strict comparison. "
            f"Original strict matches: **{data['strict_scalar_counts']['passed']}/{data['strict_scalar_counts']['required']}**. "
            "Numerical validity gates are unchanged.", '']
    if any(row['declared_scope'].get('st5_structural_targets') for row in data['families']):
        lines += ['', 'ST-5 mechanics explicitly adds original printed precision to the relative allowance, including tiny values. At zero relative tolerance it uses the original strict interval. Five physical states and the final 0.1% mesh gates qualify each distinct native observation; mesh repeats and input/display echoes add no votes.', '']
    for row in data['families']:
        c = row['scalar_counts']
        scope = row['declared_scope']
        lines.append(f"| {row['id']} | {scope['models_with_numerical_results']}/{scope['unique_model_count']} | {scope['numerically_valid_reference_samples']}/{scope['original_reference_samples']} | {row['jobs_finished']}/{row['jobs_planned']} | {c['required']} | {c['reported']} | {c['finite']} | "
                     f"{c['numerically_valid_finite']} | {c['passed']} | {c['absent']} | {c['unsupported_required']} | {row['status']} |")
    for row in data['families']:
        scope = row['declared_scope']
        if scope.get('historical_source_pairings'):
            lines += ['', f"{row['id']} supplemental pairing(s): " + ', '.join(scope['historical_source_pairings']) + '. '
                'Historical model comparisons reuse existing native target cells; they do not replace current-file comparisons. '
                'The source association is verified, but the historical producing execution and startup state remain unverified.']
        if row['id'] == 'ST-2' and scope.get('mechanics_jobs'):
            lines += ['', f"ST-2 mechanics registers {scope['mechanics_static_targets']} static ordinates and "
                f"{scope['mechanics_modal_targets']} modal frequencies in {scope['mechanics_jobs']} jobs. "
                'Static inputs retain the explicit tip-pylon reconstruction; modal files are literal with declared still-air settings. '
                'Unloaded baselines and mesh repeats add no targets. The overlapping 490-slot archive is summarized separately; '
                'literal attachment compatibility, historical settings and full-family validation remain unresolved.']
        elif row['id'] == 'ST-2' and row['jobs_planned']:
            lines += ['', f"ST-2 registers {scope['native_reference_samples']} native rows / {scope['native_scalar_targets']} native scalar targets, "
                f"plus {scope['qualified_workbook_cells']} separately qualified workbook cells and "
                f"{scope['literal_model_inventory_records']} literal model inventory records. "
                f"The conditional modal scope has {scope['conditional_modal_jobs']} jobs / "
                f"{scope['conditional_modal_scalar_slots']} scalar slots, with mesh and medium repeats excluded from native target counts. "
                'Static, workbook and inventory routes remain blocked. Local ordinal root comparisons do not establish historical branch identity or complete family reproduction.']
        if row['id'] == 'ST-3' and scope.get('mechanics_jobs'):
            lines += ['', f"ST-3 mechanics registers {scope['mechanics_static_targets']} static ordinates and "
                f"{scope['mechanics_modal_targets']} modal frequencies in {scope['mechanics_jobs']} jobs. "
                'The two clipped static references remain unavailable in the denominator. Signed loads and the script torque-axis factor remain explicit; '
                'both meshes are required and receive no extra votes. The overlapping historical scopes are kept separate. '
                'Historical startup, native modal labels and full-family compatibility remain unresolved.']
        if row['id'] == 'AP-1' and row['jobs_planned']:
            lines += ['', f"AP-1 retains {scope['span_reference_samples']} distinct span rows and "
                f"{scope['operating_reference_samples']} operating rows, plus {scope['header_reference_states']} separate header/state records. "
                f"{scope['numerically_valid_header_reference_states']} header/state records and "
                f"{scope['numerically_valid_span_reference_samples']} span rows have numerical results. "
                'Mesh repetitions are excluded from these sample counts; header agreement does not validate blocked span recovery.']
        if row['id'] == 'AP-2' and row['jobs_planned']:
            lines += ['', f"AP-2 retains {scope['mat_grid_cells']} distinct MAT grid cells and "
                f"{scope['unpaired_operating_rows']} unpaired operating rows. "
                f"{scope['final_csv_witness_states']} final-state CSV witnesses supplement the grid cells without adding duplicate states. "
                f"The declared slots comprise {scope['mat_binary_identity_scalar_targets']} stored binary-cell identity diagnostics, "
                f"{scope['final_csv_printed_scalar_targets']} CSV decimal targets and {scope['unpaired_txt_scalar_targets']} blocked TXT targets. "
                'MAT zero-tolerance identity is not original print precision. Reconstructed grid settings and mesh comparisons do not establish full historical reproduction.']
        if row['id'] == 'AE-1' and row['jobs_planned']:
            lines += ['', f"AE-1 retains {scope['sensor_reference_rows']} distinct original sensor rows: "
                f"{scope['conditional_operating_rows']} positive operating rows and {scope['unknown_initial_rows']} unknown initial rows. "
                f"All six absolute Earth sensor channels are retained, giving {scope['conditional_sensor_scalar_targets']} conditional "
                f"and {scope['blocked_initial_scalar_targets']} blocked scalar slots across the declared meshes. "
                'The literal model is unchanged. Mounted setup is conditional; source NODE I40 and current nominal intervals40/80 do not establish the historical node arrays or startup settings.']
            if 'ae1-frozen-influences' in row.get('comparison_scopes', {}):
                counts = row['comparison_scopes']['ae1-frozen-influences']
                lines += ['', f"The explicitly selected ae1-frozen-influences alternative has {counts['passed']}/{counts['required']} matching scalar slots. "
                    'Frozen and updated influence settings have separate comparison ledgers and mesh pairs. '
                    'They reuse the same original sensor rows; alternative settings add no independent native targets. '
                    'The historical OPER K/F setting remains unknown, and the default baseline is unchanged.']
        if row['id'] == 'SA-15' and 'sa15-declared-setup' in row.get('comparison_scopes', {}):
            counts = row['comparison_scopes']['sa15-declared-setup']
            lines += ['', f"The explicitly selected sa15-declared-setup reconstruction has {counts['passed']}/{counts['required']} matching scalar slots. "
                'All seven original columns remain required. The original .set is undecoded; historical startup, nodes and OPER output identity remain unverified. '
                'The historical blocked scope is retained separately, and alternative settings add no independent native targets. '
                'These conditional matches do not establish whole-family reproduction.']
        if row['id'] == 'AE-4' and row['jobs_planned']:
            lines += ['', f"AE-4 retains {scope['ae4_modal_tables']} original modal tables and "
                f"{scope['ae4_stored_modal_rows']} stored modal rows; identical file content reduces this to "
                f"{scope['ae4_distinct_file_content_modal_rows']} content/line identities. "
                'The historical ledger remains blocked. The optional undeformed alpha-zero scope reuses its native cells '
                'on two declared meshes and retains all unmatched real/complex roots. Historical startup, index mapping '
                'and native modal identity remain qualified. Sensor and LCO time histories are outside this modal adapter; '
                'no whole-family validation follows.']
            if 'ae4-undeformed-alpha0' in row.get('comparison_scopes', {}):
                counts = row['comparison_scopes']['ae4-undeformed-alpha0']
                lines += ['', f"The explicitly selected ae4-undeformed-alpha0 scope has {counts['passed']}/{counts['required']} "
                    'matching components. Initial point1 remains blocked; the terminal modal point has no archived values. '
                    'The separate 0.1% mesh diagnostics are not waived by the 5% reference allowance.']
        if row['id'] == 'AE-6' and row['jobs_planned']:
            lines += ['', f"AE-6 retains {scope['ae6_modal_tables']} modal tables and "
                f"{scope['ae6_stored_modal_rows']} complex rows. All six model/driver/table triples duplicate ST4. "
                'Historical setup remains blocked. The declared airflow scope uses literal driver speeds and two meshes; '
                'Weight0 remains blocked by its unterminated original model. Complex-distance matching does not authenticate '
                'native eigenvector identity, and the separate 0.1% mesh gate is unchanged. Other nacelle positions, '
                'aggregate output, exact flutter onset and whole-family validation remain open.']
            if 'ae6-declared-airflow' in row.get('comparison_scopes', {}):
                counts = row['comparison_scopes']['ae6-declared-airflow']
                lines += ['', f"Selected declared AE-6 comparisons: {counts['passed']}/{counts['required']} components match."]
        if row['id'] == 'SA-13' and row['jobs_planned']:
            lines += ['', f"SA-13 retains {scope['aswing_figure_series']} figure series and "
                f"{scope['figure_ordinate_slots']} ordinate slots: {scope['finite_figure_ordinates']} finite and "
                f"{scope['unavailable_figure_ordinates']} unavailable NaN/padding entries. "
                f"The finite values comprise {scope['original_discretization_finite_ordinates']} original-discretization "
                f"and {scope['modified_aswing_finite_ordinates']} modified-ASWING observations. "
                'Original inputs/settings and a reference precision contract are missing; all comparisons remain blocked. '
                'Experimental curves and geometric outlines are retained as context, not comparison targets.']
    lines += ['', 'Families not covered by these supplied runs: ' + ', '.join(data['missing_adapters']) + '.', '',
              'Fine-grid polar errors use the larger predeclared nominal mesh. All rows remain in the denominator; '
              'metrics use valid finite pairs. Force units follow each literal model Unit F declaration; coefficients and efficiency are dimensionless.', '',
              '| Table | Panels | Channel | Unit | Valid pairs/rows | Failed or unrun rows | Unavailable/absent | RMSE | Max absolute error |',
              '|---|---:|---|---|---:|---:|---:|---:|---:|']
    def number(value):
        return 'unavailable' if value is None else f'{value:.8g}'
    for table in data['fine_grid_polar_tables']:
        label = f"{table['case_id']}: {Path(table['table_path']).name}"
        if table.get('source_pairing_id'):
            label += f" [pairing {table['source_pairing_id']}; {Path(table['model_path']).name}]"
        elif table.get('comparison_scope'):
            label += f" [scope {table['comparison_scope']}]"
        for channel, stat in table['channels'].items():
            lines.append(f"| {label} | {','.join(map(str,table['fine_panels']))} | {channel} | {stat['unit']} | "
                         f"{stat['valid_comparison_pairs']}/{stat['required_rows']} | {stat['failed_or_unrun_rows']} | "
                         f"{stat['unavailable_predictions']}/{stat['absent_rows']} | {number(stat['rmse'])} | {number(stat['maximum_absolute_error'])} |")
    p1 = data['P1_CT']
    if data.get('fine_grid_sa6_coefficients'):
        lines += ['', 'SA-6 six static stability-axis coefficients at the predeclared 128 mesh. Tables include only supplied fine-grid operating points; coarse jobs remain in the overall ledger. Control-source evidence is listed per model; postprocessor bindings do not recover the missing shell drivers or authenticate historical startup. Derivative and inertia tensors are excluded.', '',
                  '| Original model | Control source | Channel | Valid pairs/selected | RMSE | Max absolute error |',
                  '|---|---|---|---:|---:|---:|']
        for table in data['fine_grid_sa6_coefficients']:
            for channel, stat in table['channels'].items():
                lines.append(f"| {Path(table['model_path']).name} | {table['control_source']} | {channel} | {stat['valid_comparison_pairs']}/{table['rows']} | {number(stat['rmse'])} | {number(stat['maximum_absolute_error'])} |")
    if data.get('fine_grid_sa6_control_derivatives'):
        lines += ['', 'SA-6 supplemental conditional F1 derivatives at nominal 128 intervals. '
            'These original cells have a separate ledger from static coefficients; historical producer and response/startup settings remain unauthenticated. '
            'Literal infinite stiffness removes elastic shape response at the same fixed base/frame/mesh, while aerodynamic K/F and global-frame settings remain qualified.', '',
            '| Original model | Control source | Derivative | Valid pairs/selected | RMSE | Max absolute error |',
            '|---|---|---|---:|---:|---:|']
        for table in data['fine_grid_sa6_control_derivatives']:
            for channel, stat in table['channels'].items():
                lines.append(f"| {Path(table['model_path']).name} | {table['control_source']} | {channel} | {stat['valid_comparison_pairs']}/{table['rows']} | {number(stat['rmse'])} | {number(stat['maximum_absolute_error'])} |")
    if data.get('fine_grid_sa6_state_derivatives'):
        lines += ['', 'SA-6 supplemental conditional state derivatives at nominal128 intervals. All36 native channels retain a separate ledger from static/F1 targets. '
            'The complete current steady operator is differentiated at fixed base stability axes, dynamic pressure and reference lengths. '
            'Historical producer/startup, response and influence-lagging conventions remain unverified; literal infinite stiffness does not authenticate them.', '',
            '| Original model | Control source | Derivative | Valid pairs/selected | RMSE | Max absolute error |',
            '|---|---|---|---:|---:|---:|']
        for table in data['fine_grid_sa6_state_derivatives']:
            for channel, stat in table['channels'].items():
                lines.append(f"| {Path(table['model_path']).name} | {table['control_source']} | {channel} | {stat['valid_comparison_pairs']}/{table['rows']} | {number(stat['rmse'])} | {number(stat['maximum_absolute_error'])} |")
    if data.get('fine_grid_sa6_mass_tensors'):
        lines += ['', 'SA-6 supplemental dimensional body-axis mass tensors at nominal 128 intervals. '
            'All 33 printed cells remain separate from static and derivative targets. Physical real CG is undefined for zero mass; '
            'centroid-labelled inertia uses the archived numeric zero reporting coordinate. No aerodynamic solve is performed. '
            'Historical mesh, producer and reported deformed-shape identity remain unverified.', '',
            '| Original model | Tensor component | Unit | Valid pairs/selected | RMSE | Max absolute error |',
            '|---|---|---|---:|---:|---:|']
        for table in data['fine_grid_sa6_mass_tensors']:
            for channel, stat in table['channels'].items():
                lines.append(f"| {Path(table['model_path']).name} | {channel} | {stat['unit']} | {stat['valid_comparison_pairs']}/{table['rows']} | {number(stat['rmse'])} | {number(stat['maximum_absolute_error'])} |")
    lines += ['', f"P-1 CT: {p1['valid_comparison_pairs']}/{p1['scalar_counts']['required']} valid pairs "
              f"(full original selected scope: 110); maximum absolute difference {number(p1['maximum_absolute_error'])}.", '',
              'P-1 is an isolated component comparison and does not name a whole-aircraft model. No mesh or reference gate was widened. Source import counts and test counts are not included in output agreement.']
    if data.get('model_inventory_without_targets'):
        lines += ['', 'Original models without a paired reference remain inventory records with zero scalar targets:', '',
                  '| Family | Model | Record status | Reason |', '|---|---|---|---|']
        for row in data['model_inventory_without_targets']:
            lines.append(f"| {row['case_id']} | {row['model_path']} | {row['status']} | {row['reason']} |")
    lines += ['', *data.get('additional_scope_notes', [])]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    require(not (args.output_dir / 'summary.json').exists() and not (args.output_dir / 'summary.md').exists(),
            'Existing summary retained; choose a new output directory.')
    merged = load_runs(args.run)
    data = summarize(merged)
    data.update(summarizer=pin(__file__), physics_calls=0, production_imports=0, test_runs=0)
    encoded = json.dumps(data, indent=2, allow_nan=False) + '\n'
    rendered = markdown(data)
    verify_summary_sources(merged)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'summary.json').write_text(encoded)
    (args.output_dir / 'summary.md').write_text(rendered)
    print(json.dumps({'status': data['status'], 'families': data['family_count'], 'jobs': data['jobs'],
                      'scalar_counts': data['scalar_counts'], 'missing_adapters': data['missing_adapters']}, indent=2))


if __name__ == '__main__':
    main()
