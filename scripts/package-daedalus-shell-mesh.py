#!/usr/bin/env python3
"""Package the checked, corrected-mesh Daedalus cruise state without a solve.

Usage: .venv/bin/python scripts/package-daedalus-shell-mesh.py --study DIR

DIR is the retained four-frequency shell-mesh study. Its frozen kernel predates
mesh-recipe metadata. This one-time migration first matches its complete raw
identity to the current default network with only the recipe key omitted. It
then decodes physical fields, checks the full residual, and captures a genuinely
current packet. It never interpolates, edits the raw packet, trims, or sweeps.
The project offers a 101-point UI grid; only the four study samples were run.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def pin(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


class SettingsHTML(HTMLParser):
    """Read actual rendered input types/options, without starting the app."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.elements = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        ancestors = [entry[1].get('id') for entry in self.stack]
        if tag in ('input', 'select', 'textarea') and any(x in ancestors for x in ('model-configuration', 'analysis-settings')):
            row = dict(id=attrs.get('id', ''), type=attrs.get('type', 'text'), tagName=tag.upper(),
                       project='project-settings' in ancestors,
                       dataset={key: attrs[attr] for key, attr in [('timeLoad', 'data-time-load'), ('timeTarget', 'data-time-target')] if attr in attrs}, options=[])
            self.elements.append(row)
            attrs['_field'] = row
        if tag == 'option':
            selects = [entry[1]['_field'] for entry in self.stack if entry[0] == 'select' and '_field' in entry[1]]
            if selects:
                if 'value' not in attrs:
                    raise ValueError('A rendered settings option needs an explicit value.')
                selects[-1]['options'].append(dict(value=attrs['value']))
        if tag not in self.VOID:
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


# Evaluate only the production settings markup, not main.js initialization.
# The resulting types/options come from the app, not from the saved project.
RENDER = r"""
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';
const root=process.argv[1];
const modules={projectSettings:'project-settings',timeSettings:'time-results',modeSettings:'mode-results',
 frequencySettings:'frequency-results',feedbackSettings:'feedback-results',equilibriumSettings:'equilibrium-state',
 gustSettings:'gust-settings',customSettings:'custom-constraints',allocationSettings:'control-allocation'};
const context={location:{hostname:'localhost'}};
for(const [name,file] of Object.entries(modules))context[name]=(await import(pathToFileURL(root+'/web/'+file+'.js')))[name];
let html;
context.document={querySelector(selector){if(selector!=='#app')throw new Error('Unexpected DOM operation');return {set innerHTML(value){html=value;}};}};
const source=readFileSync(root+'/web/main.js','utf8');
const start=source.indexOf('const icon =');
const end=source.indexOf('    <div id="analysis-actions">',start);
if(start<0||end<0)throw new Error('Production settings markup boundaries changed.');
vm.runInNewContext(source.slice(start,end)+'`;',context,{timeout:5000});
process.stdout.write(html);
"""

VALIDATE = r"""
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=process.argv[1],payload=JSON.parse(readFileSync(0,'utf8'));
const elements=payload.elements.map(e=>({...e,closest(s){assert.equal(s,'#project-settings');return e.project?{}:null;}}));
globalThis.document={querySelectorAll(selector){assert.equal(selector,'#model-configuration input,#model-configuration select,#model-configuration textarea,#analysis-settings input,#analysis-settings select,#analysis-settings textarea');return elements;}};
const {parseProject}=await import(pathToFileURL(root+'/web/project-data.js'));
const {validateSettings,settingFields}=await import(pathToFileURL(root+'/web/case-settings.js'));
const parsed=parseProject(JSON.stringify(payload.project));
assert.deepEqual(parsed,payload.project);
assert.equal(parsed.cases.length,1);assert.equal(parsed.solutions.length,0);
const config=parsed.cases[0].configuration;
assert.deepEqual(validateSettings(config,payload.model),config);
assert.equal(config.equilibrium.state.identity.mesh_recipe,'physical-breaks-v1');
assert.equal(config.fields['frequency-count'],'101');assert.equal(config.fields['frequency-spacing'],'log');
assert.match(config.equilibrium.label,/four frequencies checked/);
assert.match(config.equilibrium.label,/101-point grid not run/);
process.stdout.write(JSON.stringify({status:'PASS',production_project_parser:true,production_settings_validator:true,
 fields:settingFields().size,rendered_settings_from:'web/main.js and imported production settings templates',
 model_controls:payload.model.controls,model_powers:payload.model.engine_controls.map(e=>e.index),browser_run:false}));
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'examples/dae-cruise-physical-mesh-project.json')
    parser.add_argument('--receipts', type=Path)
    args = parser.parse_args()
    stage = args.study.resolve()
    receipts = (args.receipts or stage/'publication').resolve()
    receipts.mkdir(parents=True, exist_ok=True)
    report_path = receipts/'project-packaging.json'
    if report_path.exists() or args.output.exists():
        raise FileExistsError('Refusing to overwrite an existing project or packaging receipt.')
    source_paths = sorted((ROOT/'openswing').glob('*.py')) + sorted((ROOT/'web').glob('*.js'))
    input_paths = [Path(__file__), ROOT/'examples/dae-cruise-mesh-project.json', ROOT/'examples/dae.asw',
                   stage/'request.json', stage/'results/base.json', stage/'results/report.json', stage/'session-closeout.json']
    initial_pins = [pin(path) for path in input_paths + source_paths]
    checks = []
    operations = dict(network_constructors=0, full_residual_evaluations=0, aircraft_solves=0, linearizations=0, harmonic_solves=0, interpolations=0)

    def check(name, predicate, **details):
        checks.append(dict(name=name, passed=bool(predicate), **details))
        if not predicate:
            raise AssertionError(name)

    start = time.monotonic()
    write(receipts/'project-packaging-inputs.json', dict(pins=initial_pins, operations=operations,
          policy='Exact current identity check before physical decoding; two full residual evaluations; no solve or interpolation.'))
    try:
        sys.path.insert(0, str(ROOT))
        import numpy as np
        from openswing.asw import parse_asw
        from openswing.network import StaticNetwork
        from openswing.time_state import read_condition
        from openswing.discretization import CURRENT_MESH_RECIPE
        from openswing.equilibrium_state import identity, matching_identity, restore_physical_fields, capture, restore, warm_start_recipe

        study_report = json.loads((stage/'results/report.json').read_text())
        owner = json.loads((stage/'session-closeout.json').read_text())
        check('study has terminal successful owner', owner['exit_code'] == 0 and owner['reaped'] and not owner['timed_out'])
        check('terminal owner binds the final study report', owner['report_pin'] == pin(stage/'results/report.json'))
        check('study report has no failed checks', study_report['checks']['passed'] == study_report['checks']['total'])
        base = json.loads((stage/'results/base.json').read_text())
        raw = deepcopy(base['equilibrium_state'])
        raw_before = deepcopy(raw)
        launch = raw['launch']
        project = json.loads((ROOT/'examples/dae-cruise-mesh-project.json').read_text())
        config = deepcopy(next(c['configuration'] for c in project['cases'] if c['id'] == 'dae-cruise16'))
        request = json.loads((stage/'request.json').read_text())
        check('literal aircraft source unchanged', config['source'] == request['source'] == (ROOT/'examples/dae.asw').read_text())
        check('transitional packet is untagged and has no controller', 'mesh_recipe' not in raw['identity'] and raw['feedback'] is None and launch['controller'] is None)
        check('same seven trim constraints', len(launch['released_constraints']) == 7 and
              [{k:c[k] for k in ('variable','quantity','target')} for c in launch['released_constraints']] == config['constraints'])
        model = parse_asw(config['source'])
        operations['network_constructors'] += 1
        n = StaticNetwork(model, launch['panels'], read_condition(launch['condition']), launch['gravity'], launch['loads'],
                          operating_constraints=launch['released_constraints'], strut_mode=launch['strut_mode'])
        current = identity(n)
        check('current default physical recipe', CURRENT_MESH_RECIPE == n.mesh_recipe == current['mesh_recipe'] == 'physical-breaks-v1')
        stripped = deepcopy(current)
        del stripped['mesh_recipe']
        # No field is decoded before this full existing identity gate.
        check('complete identity matches with only recipe key omitted', matching_identity(raw['identity'], stripped))
        check('pointwise basis and expected corrected dimensions', not n.circulation_basis.modes and not n.hinges and
              (n.nn, n.ne, n.ng, n.nc, n.size) == (108, 103, 82, 30, 1385))
        x = restore_physical_fields(n, raw)
        zero = np.zeros_like(n.rj)
        options = dict(elastic_motion=(zero, zero, zero, zero), circulation_rate=np.zeros(n.circulation_basis.panels))
        operations['full_residual_evaluations'] += 1
        residual = n.residual(x, **options)
        np.savez(receipts/'project-full-residual.npz', x=x, residual=residual)
        maximum = float(np.max(np.abs(residual)))
        check('current full seven-constraint residual <= 1e-8', np.all(np.isfinite(residual)) and maximum <= 1e-8, maximum=maximum)
        saved = capture(n, x, residual=maximum, launch_frame=launch['frame'])
        check('captured identity is genuinely current', saved['identity'] == current)
        check('public warm start chooses corrected recipe', warm_start_recipe(model, launch['panels'], saved) == CURRENT_MESH_RECIPE)
        restored = restore(n, json.loads(json.dumps(saved, allow_nan=False)))
        check('current public restore roundtrip', np.allclose(restored, x, atol=2e-14, rtol=2e-14), maximum=float(np.max(abs(restored-x))))
        operations['full_residual_evaluations'] += 1
        restored_residual = n.residual(restored, **options)
        np.savez(receipts/'project-restored-residual.npz', x=restored, residual=restored_residual)
        restored_max = float(np.max(abs(restored_residual)))
        check('restored full residual <= 1e-8', np.all(np.isfinite(restored_residual)) and restored_max <= 1e-8, maximum=restored_max)
        check('raw packet untouched', raw == raw_before)
        config['mesh'] = launch['panels']
        condition = saved['launch']['condition']
        for key in ('speed', 'alpha', 'beta'):
            config['fields'][key] = str(condition[key])
        for key, value in zip(('bank', 'elevation', 'heading'), condition['attitude']):
            config['fields']['attitude-'+key] = str(value)
        config['controls'] = {key:str(value) for key,value in condition['controls'].items()}
        config['powers'] = {key:str(value) for key,value in condition['powers'].items()}
        config['equilibrium'] = dict(state=saved, enabled=True,
            label='Corrected physical mesh, 6.7 m/s level trim; four frequencies checked; 101-point grid not run.')
        check('101 logarithmic UI grid retained without computed solutions',
              config['fields']['frequency-count'] == '101' and config['fields']['frequency-spacing'] == 'log' and
              float(config['fields']['frequency-start']) == 2*np.pi*.1 and float(config['fields']['frequency-end']) == 2*np.pi*10)
        case = dict(id='dae-cruise-physical16', name='6.7 m/s cruise — corrected physical mesh, 16 intervals', configuration=config)
        project = dict(format='openswing-project', version=2, name='Daedalus cruise — corrected physical mesh',
                       selected=case['id'], cases=[case], solutions=[], selected_solution=None)
        write(receipts/'project-candidate.json', project)
        render = subprocess.run(['node', '--input-type=module', '-e', RENDER, str(ROOT)], check=True, text=True, capture_output=True, timeout=15)
        html = SettingsHTML()
        html.feed(render.stdout)
        model_data = dict(controls=model.controls, engine_controls=[dict(index=i) for i in model.engine_controls],
                          beams=[dict(index=b.index, lifting=b.lifting) for b in model.beams])
        payload = dict(project=project, elements=html.elements, model=model_data)
        validate = subprocess.run(['node', '--input-type=module', '-e', VALIDATE, str(ROOT)],
                                  input=json.dumps(payload, allow_nan=False), check=True, text=True, capture_output=True, timeout=15)
        js_report = json.loads(validate.stdout)
        write(receipts/'project-js-validation.json', js_report)
        check('production project parser and settings validator pass', js_report['status'] == 'PASS')
        for expected in initial_pins:
            check('input/source pin unchanged: '+expected['path'], pin(expected['path']) == expected)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            stream.write(json.dumps(project, indent=2, allow_nan=False)+'\n')
        report = dict(status='PASS', checks=dict(passed=len(checks), total=len(checks), items=checks), operations=operations,
                      elapsed_seconds=time.monotonic()-start, project=pin(args.output), generator=pin(__file__),
                      mesh_recipe=CURRENT_MESH_RECIPE, nodes=n.nn, elements=n.ne, circulation=n.ng,
                      full_residual=maximum, restored_full_residual=restored_max, ui_frequencies=101,
                      computed_study_frequencies_Hz=[.1, 1., 1.15737773741517, 10.], computed_project_solutions=0,
                      limitations=['The 101-point UI grid has not been computed for this mesh.',
                                   'The four-frequency comparison does not resolve the full-aircraft reference mismatch.',
                                   'Raw study packets remain unchanged; the public packet was recaptured only after exact identity and residual checks.'],
                      source_and_input_pins=initial_pins, javascript=js_report)
        write(report_path, report)
        print(json.dumps({k:report[k] for k in ('status','project','operations','full_residual','restored_full_residual','ui_frequencies')}))
    except BaseException as exc:
        write(receipts/'project-packaging-failure.json', dict(status='FAIL', error=repr(exc),
              checks=checks, operations=operations, elapsed_seconds=time.monotonic()-start))
        raise


if __name__ == '__main__':
    main()
