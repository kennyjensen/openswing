import {quiescentCondition,isQuiescentResult} from './quiescent-settings.js';
import {timeInitializationSummary} from './time-target-results.js';
import {mountedStatus, timeStatus, frequencyStatus} from './solve-progress.js';
import {beamColor, colorBeamPlot, plotColors} from './plot-colors.js';
import {timePhase} from './time-timeline.js';
import {shareTimeHistoryMetadata} from './time-history-metadata.js';
import {restoreWorkerTimeHistory} from './worker-time-history.js';
import {loadingQuantities,loadingValue} from './loading-data.js';
import {linearLoadingSamples,linearShoulderSamples,spanRange} from './linear-span.js';
import {totalForcesMarkup,renderFlightOutput,outputNumber} from './total-forces.js';
import {fourierWakeOptions,fourierWakeSummary} from './fourier-wake.js';
import {allocationSettings,createControlAllocation,allocationReport} from './control-allocation.js';
import {beamPlotControls,renderBeamDistribution} from './beam-distribution-plot.js';
import {customSettings,createCustomConstraints,customReport} from './custom-constraints.js';
import './style.css';
import './responsive-workbench.css';
import './asw-editor.css';
document.documentElement.style.setProperty('--plot-color', plotColors[0]);
import { createAswEditor } from './asw-editor.js';
import {createAircraftLoader} from './aircraft-loader.js';
import {takeSolverWorker} from './solver-worker.js';
import { createResponsiveWorkbench } from './responsive-workbench.js';
import { nodePane, createNodeEditor } from './node-editor.js';
import {daedalusDefaultMesh} from './daedalus-mesh.js';
import sailplaneMesh from './sailplane-mesh.json' with {type:'json'};
import daedalusPreview from './daedalus-preview.json' with {type:'json'};
import daedalusSource from '../examples/dae.asw?raw';
import { distributionPane, createDistributionEditor } from './distribution-editor.js';
import {massPane,createMassEditor} from './mass-editor.js';
import { createTimeCheckpoints } from './time-checkpoint.js';
import { equilibriumSettings, createEquilibriumSettings } from './equilibrium-state.js';
import { steadyProgressSettings, createSteadyProgress } from './steady-progress.js';
import { feedbackSettings, createFeedbackSettings } from './feedback-results.js';
import { gustSettings, createGustSettings } from './gust-settings.js';
import {captureSettings,validateSettings,applySettings,fieldValue,setFieldValue,bindNumberFormatting,defaultStrutMode,defaultBodyAddedMassFactor} from './case-settings.js';
import {steadyFlightSettings,createSteadyFlight,solvedFlightCondition} from './steady-flight.js';
import {sameConfiguration} from './project-data.js';
import {analysisStructuralSelection} from './analysis-numerics.js';
import {numericalSelection,selectedNumerics,numericalRequest,sameNumerics,assertVacuumInputs,vacuumModalRequest,assertStillAirInputs,stillAirModalRequest,assertMovingVacuumInputs,movingVacuumFrame,movingVacuumModalRequest,movingVacuumTimeRequest,sourceFrequencyRequest,assertAirflowInputs,airflowDynamicRequest} from './numerical-policy.js';
import {portableResult,verifySolution,kernelFingerprint} from './solution-data.js';
import {openTimeHistoryArchive} from './time-history-archive.js';
import {archiveTrajectory,archivedTimeHistory,copyTimeHistory,timeHistory} from './time-history-source.js';
import {joinTimeHistory} from './time-history-continuation.js';
import { structureOptions, structureUnits, structureDetails, createStructureResults } from './structure-results.js';
import { createViewer } from './viewer.js';
import { createAircraftDownload } from './aircraft-download.js';
import { createFlowFailure } from './flow-failure.js';
import { timeSettings, timeTransport, timePane, createTimeResults, trajectoryGeometry } from './time-results.js';
import { frequencySettings, frequencyTransport, frequencyPane, createFrequencyResults } from './frequency-results.js';
import { modeSettings, modeTransport, modePane, createModeResults } from './mode-results.js';

const icon = (name) => {
  const paths = { wing: '<path d="m3 17 6-6 12-5-8 8-10 3Z"/><path d="m9 11 4 3"/>', upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>', download: '<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>', play: '<path d="m8 4 12 8-12 8Z"/>', fit: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>', grid: '<path d="M3 3h18v18H3ZM9 3v18m6-18v18M3 9h18M3 15h18"/>', check: '<path d="m5 12 4 4 10-10"/>', source: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-5 2 2-16"/>' };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.wing}</svg>`;
};
let structuralSelection='aswing-airflow',previousAnalysisMode='mounted';
let workbenchView;
const quiescentSelected=()=>($('mode').value==='modes'&&$('modal-quiescent').checked)||($('mode').value==='frequency'&&sourceStillAirSelected());
const sourceVacuumSelected=()=>structuralSelection==='aswing-vacuum';
const sourceStillAirSelected=()=>structuralSelection==='aswing-still-air';
const sourceMovingVacuumSelected=()=>structuralSelection==='aswing-moving-vacuum';
const sourceAirflowSelected=()=>structuralSelection==='aswing-airflow';
function vacuumWorkbenchFields(){return {mode:$('mode').value,'modal-frame':$('modal-frame').value,
  'frequency-frame':$('frequency-frame').value,'frequency-inputs':$('frequency-inputs').value,
  ...Object.fromEntries(['F','M'].flatMap(kind=>['x','y','z'].flatMap(axis=>['load','target'].map(name=>{const key=`frequency-${name}-${kind}${axis}`;return [key,$(key).value];})))),
  'modal-ordinary-frame':$('modal-ordinary-frame').value,'modal-vacuum':$('modal-vacuum').checked,
  'modal-quiescent':$('modal-quiescent').checked,'modal-quiescent-density':$('modal-quiescent-density').value,'feedback-enabled':$('feedback-enabled').checked,
  'time-frame':$('time-frame').value,'time-actuators':$('time-actuators').value,
  ...Object.fromEntries([...document.querySelectorAll('[data-time-load],[data-time-target]')].map(input=>[input.dataset.timeLoad?'time-load:'+input.dataset.timeLoad:'time-target:'+input.dataset.timeTarget,input.value])),
  ...Object.fromEntries(['gravity-mode','gravity-magnitude',...['x','y','z'].map(axis=>`position-earth-${axis}`),...['bank','elevation','heading'].map(axis=>`attitude-${axis}`)].map(key=>[key,$(key).value])),
  ...Object.fromEntries(['moving-velocity','rates','acceleration','angular_acceleration'].flatMap(kind=>['x','y','z'].map(axis=>[`${kind}-${axis}`,$(`${kind}-${axis}`).value]))),
  ...Object.fromEntries(['F','M'].flatMap(kind=>['x','y','z'].flatMap(axis=>['load','target'].map(name=>{const key=`modal-${name}-${kind}${axis}`;return [key,$(key).value];}))))};}
const motionGroups=[['rates','Rotation rate','deg / T'],['acceleration','Absolute acceleration','L / T²'],['angular_acceleration','Angular acceleration','deg / T²']];
const poseGroups=[['position-earth','Body origin in Earth axes','input L',['x','y','z']],['attitude','Aircraft attitude','deg',['bank','elevation','heading']],['ground-normal','Ground normal in Earth axes','unit vector',['x','y','z']]];

const buildCommit = typeof __OPENSWING_BUILD_COMMIT__ === 'string' ? __OPENSWING_BUILD_COMMIT__ : '';
document.querySelector('#app').innerHTML = `
<header class="topbar">
  <div class="brand-lockup">
    <img class="brand-mark" src="/openswing-logo.svg" alt="" width="818" height="310">
    <a href="/" class="brand"><span>Open<span class="brand-accent">Swing</span></span><span class="version">0.1 / DEV</span></a>
    <span class="brand-subtitle">A coupled aerodynamic and structural solver inspired by <a href="https://web.mit.edu/drela/Public/web/aswing/" target="_blank" rel="noreferrer">ASWING</a>.</span>
  </div>
    <nav class="related-apps" aria-label="Related airfoil and flight tools">
      <a class="element-link" href="https://alula.vibefoil.com" target="_blank" rel="noopener noreferrer" aria-label="Alula (opens in a new tab)"><span class="element-symbol" aria-hidden="true">Al</span><span class="element-name">Alula</span></a>
      <a class="element-link" href="https://www.vibefoil.com" target="_blank" rel="noopener noreferrer" aria-label="Vibefoil (opens in a new tab)"><span class="element-symbol" aria-hidden="true">Vf</span><span class="element-name">Vibefoil</span></a>
      <a class="element-link" href="https://sim.vibefoil.com" target="_blank" rel="noopener noreferrer" aria-label="Vibesim (opens in a new tab)"><span class="element-symbol" aria-hidden="true">Vs</span><span class="element-name">Vibesim</span></a>
      <a class="element-link" href="https://avl.vibefoil.com" target="_blank" rel="noopener noreferrer" aria-label="Vibelattice (opens in a new tab)"><span class="element-symbol" aria-hidden="true">Vl</span><span class="element-name">Vibelattice</span></a>
    </nav>
  <div id="github-star" class="github-star">
    <a class="github-button" href="https://github.com/kennyjensen/openswing"
       data-color-scheme="no-preference: dark; light: dark; dark: dark;"
       data-icon="octicon-star" data-size="large" data-show-count="true"
       target="_blank" rel="noopener noreferrer" aria-label="Star OpenSwing on GitHub">Star</a>
  </div>
</header>
<nav id="workspace-tabs" class="workspace-tabs" role="tablist" aria-label="Workspace" hidden>
  ${[['editor','Editor'],['settings','Settings'],['plots','Plots'],['output','Output']].map(([key,label])=>`<button id="workspace-tab-${key}" type="button" role="tab" aria-controls="workspace-${key}" aria-selected="${key==='plots'}" tabindex="${key==='plots'?0:-1}" data-workspace="${key}">${label}</button>`).join('')}
</nav>
<main class="workbench" id="desktop-workbench">
  <aside class="setup-panel">
    <div id="analysis-settings">
      <details id="solution-type-panel" class="settings-panel" open>
        <summary>Solution Type</summary>
        <div class="settings-panel-content">
          <label class="field-label" for="mode">Analysis</label>
          <select id="mode"><option value="rigid">Rigid steady aerodynamics</option><option value="mounted" selected>Steady aeroelastic equilibrium</option><option value="structural">Structural static · no airflow</option><option value="time">Nonlinear time response</option><option value="modes">Coupled eigenmodes</option><option value="frequency">Frequency response · Bode</option></select>
              <p id="static-weight-note" class="small muted" hidden>This model contains signed Weight, mg or Dmg loads. Structural static analysis applies them at the rotating pylons or section centroids; negative entries cannot represent physical mass in dynamic analyses.</p>
          ${timeSettings}
          ${modeSettings}
          ${frequencySettings}
        </div>
      </details>
      <details id="flight-conditions-panel" class="settings-panel" open>
        <summary>Flight Conditions</summary>
        <div class="settings-panel-content">
          <div class="fields" id="flight-condition-fields">
            <label>Airspeed <span id="speed-unit">input L/T</span><input id="speed" type="number" value="21.981627296587927" min=".001" step="any" data-display-decimals="2"></label>
            <label>Angle of attack <span>deg</span><input id="alpha" type="number" value="3" min="-85" max="85" step="any"></label>
            <label>Sideslip <span>deg</span><input id="beta" type="number" value="0" min="-85" max="85" step="any"></label>
          </div>
          ${steadyFlightSettings}
          <div id="structural-settings" hidden>
            <label class="field-label" for="static-gravity-mode">Static gravity</label><select id="static-gravity-mode"><option value="file">File gravity along body −z</option><option value="custom">Specify body-axis vector</option></select>
            <div class="fields" id="static-gravity-fields" hidden>${['x','y','z'].map(a=>`<label>Gravity ${a} <span>input L/T²</span><input id="static-gravity-${a}" type="number" step="any" value="${a==='z'?-9.81:0}"></label>`).join('')}</div>
          </div>
          <!-- Internal trim and saved-case state; not a user-facing panel. -->
          <div id="operating-settings" hidden>
            <div class="constraint-actions"><button id="free-flight" type="button">Free-flight accelerations</button><button id="clear-constraints" type="button">Clear</button></div>
            <button id="reference-airflow" type="button">Set reference airflow targets</button>
            <details class="advanced" id="turn-preset"><summary>Straight flight & steady-turn presets</summary>
              <div class="fields"><label>Heading rate <span>deg / input T</span><input id="turn-rate" type="number" value="3" step="any"></label><label>Flight path <span>deg · climb positive</span><input id="turn-path" type="number" value="0" min="-89.9" max="89.9" step="any"></label></div>
              <button id="turn-kinematics" type="button">Set motion targets</button>
              <div class="fields">${[['roll','Roll flap'],['pitch','Pitch flap'],['yaw','Yaw flap'],['engine','Thrust control']].map(([key,label])=>`<label>${label}<select id="trim-${key}"></select></label>`).join('')}</div>
              <button id="turn-trim" type="button">Set full flight-trim targets</button>
              <p class="small muted" id="trim-note">Steady-turn trim needs three independent flap controls and an engine. Set sideslip to zero for coordinated flight. Control limits are not imposed.</p>
            </details>
            <div id="constraint-rows"></div><button id="add-constraint" type="button">+ Add constraint</button>${customSettings}${allocationSettings}
          </div>
        </div>
      </details>
      <details id="advanced-panel" class="settings-panel">
        <summary>Advanced</summary>
        <div class="settings-panel-content">
          <details class="advanced" id="control-input-settings"><summary>Control inputs</summary>
            <div id="controls" class="fields"></div>
            <div id="powers" class="fields"></div>
          </details>
          <details class="advanced" id="atmosphere-settings"><summary id="atmosphere-summary">Atmosphere, gravity & lift factor</summary>
            <p id="unit-note" class="small muted">Flight inputs use the .asw file’s consistent input units.</p>
            <div id="atmosphere-flow-settings">
              <div class="fields"><label>Atmospheric altitude<input id="altitude" type="number" value="0" min="-5" max="86" step="any"></label><label>Altitude units<select id="altitude-unit"><option value="1000">km</option><option value="304.8">thousand ft</option></select></label></div>
              <label class="field-label" for="density-mode">Ambient density</label><select id="density-mode"><option value="standard">From atmospheric altitude</option><option value="custom">Specify density</option></select>
              <div class="fields" id="density-field" hidden><label>Density <span>input M / L³</span><input id="density" type="number" value="1.225" min="1e-30" step="any"></label></div>
            </div>
            <label class="field-label" for="gravity-mode">Gravity magnitude</label><select id="gravity-mode"><option value="file">From .asw Constant</option><option value="custom">Specify magnitude</option></select>
            <div class="fields" id="gravity-field" hidden><label>Gravity <span>input L / T²</span><input id="gravity-magnitude" type="number" value="9.80665" min="0" step="any"></label></div>
            <div id="atmosphere-aero-settings">
              <label class="field-label" for="mach-mode">Prandtl–Glauert Mach</label><select id="mach-mode"><option value="auto">From true speed and atmosphere</option><option value="fixed">Specify PG Mach</option></select>
              <div class="fields" id="mach-field" hidden><label>PG Mach<input id="pg-mach" type="number" value="0" min="0" max="0.999" step="any"></label></div>
              <div class="fields"><label>Lift target multiplier <span>load factor N</span><input id="load-factor" type="number" value="1" step="any"></label></div>
            </div>
          </details>
          <details class="advanced" id="motion-settings"><summary>Body motion & acceleration</summary>
            <div id="moving-velocity-settings" hidden><p class="small muted">Body-origin velocity in body axes · input L / T</p><div class="fields motion-fields">${['x','y','z'].map(axis=>`<label>${axis}<input id="moving-velocity-${axis}" type="number" value="0" step="any"></label>`).join('')}</div><p class="small muted">Velocity is specified directly. Flight speed, angle of attack and sideslip are not used in vacuum.</p></div>
            ${motionGroups.map(([key,name,unit])=>`<p class="small muted">${name} · input ${unit}</p><div class="fields motion-fields">${['x','y','z'].map(axis=>`<label>${axis}<input id="${key}-${axis}" type="number" value="0" step="any"></label>`).join('')}</div>`).join('')}
          </details>
          <details class="advanced" id="ground-settings"><summary id="ground-summary">Earth pose & ground effect</summary>
            <label class="field-label" for="ground-effect">Image surface</label><select id="ground-effect"><option value="0">Off · free air</option><option value="1">Solid ground</option><option value="-1">Free surface · constant pressure</option></select>
            ${poseGroups.map(([key,name,unit,axes])=>`<div id="pose-${key}"><p class="small muted">${name} · ${unit}</p><div class="fields motion-fields">${axes.map(axis=>`<label>${axis}<input id="${key}-${axis}" type="number" value="${key==='ground-normal'&&axis==='z'?1:0}" step="any"></label>`).join('')}</div></div>`).join('')}
            <button id="level-attitude" type="button">Set level-flight attitude</button>
            <p id="ground-note" class="small muted">The plane passes through the Earth origin. Keep the aircraft above it. Gravity follows the aircraft attitude even with images off. The solved view shows the plane.</p>
          </details>
          ${gustSettings}
          <details class="advanced" id="sensor-settings" hidden><summary>Sensors</summary><label class="field-label" for="sensor-flow">Sensor airflow</label><select id="sensor-flow"><option value="full">Full · kinematics, induced flow and gust</option><option value="kinematic">Kinematic · still atmosphere only</option></select><p class="small muted">Changes the pitot/vane measurement only. Sensors are defined by Sensor records in the ASW file.</p></details>
          <details class="advanced" id="circulation-settings"><summary>Circulation representation</summary>
            <div id="circulation-modes" class="fields"></div>
            <div id="fourier-wake-settings">
              <label class="checkbox"><input id="fourier-wake-diagnostic" type="checkbox"><span>Check continuous Fourier wake</span></label>
            </div>
            <label class="checkbox"><input id="aero-lag" type="checkbox" checked><span>Aerodynamic lag</span></label>
            <label class="checkbox"><input id="freeze-influences" type="checkbox" checked><span>Freeze aerodynamic influences (K/F)</span></label>
            <label class="field-label" for="wake-core-ratio">Wake core radius / chord</label><input id="wake-core-ratio" type="number" min="0" step="any" value="0.25">
          </details>
          <details class="advanced" id="stall-settings"><summary>Section stall</summary>
            <label class="checkbox"><input type="checkbox" id="stall" checked><span>Section stall model</span></label>
            <label class="field-label" for="stall-factor">Stall leakage factor Kₛ</label><input id="stall-factor" type="number" min="0" step="any" value="40">
            <label class="field-label" for="stall-width">Transition width Δcₗ</label><input id="stall-width" type="number" min="0" step="any" value="0.05">
          </details>
          ${feedbackSettings}
          ${equilibriumSettings}
          ${steadyProgressSettings}
          <details class="advanced" id="derivative-settings" hidden><summary>Stability & control derivatives</summary>
            <label class="checkbox"><input id="derivatives-enable" type="checkbox"><span>Compute after equilibrium</span></label>
            <label class="field-label" for="derivative-response">Acceleration response</label><select id="derivative-response"><option value="fixed_acceleration">Hold accelerations fixed</option><option value="free_flight">Solve free-flight accelerations</option></select>
            <label class="field-label" for="derivative-basis">Input columns</label><select id="derivative-basis"><option value="standard">Speed, flow angles & stability rates</option><option value="body">Velocity-reference body components</option><option value="body_origin">Body-origin velocity & rotation rates</option></select>
            <label class="field-label" for="derivative-axes">Coefficient output axes</label><select id="derivative-axes"><option value="stability">Stability · x forward, z down</option><option value="body">Body · x aft, z up</option><option value="reverse_stability">Reverse stability · x aft, z up</option></select>
            <div id="derivative-parameters" class="derivative-choices"></div>
            <div class="fields"><label>Difference step<input id="derivative-step" type="number" value="0.00001" min="0.0000001" max="0.001" step="any"></label></div>
          </details>
        </div>
      </details>
    </div>
    <div id="analysis-actions">
    <button id="solve" class="primary" disabled>${icon('play')}<span>Run analysis</span><kbd>⌘ ↵</kbd></button>
    <button id="cancel" class="full-width" hidden>Cancel analysis</button>
    <div id="runtime-status" class="runtime-status" role="status"><span class="spinner"></span>Starting the numerical kernel…</div>
    <p id="runtime-detail" class="runtime-detail" hidden></p>
    </div>
  </aside>
  <section class="center-panel">
    <div class="viewport-header"><div><span class="panel-eyebrow">GEOMETRY</span><span id="shape-label" class="view-badge">JIG SHAPE</span></div><div class="view-actions"><button id="shape" hidden>Show jig</button><button id="top-view">Top</button><button id="front-view">Front</button><button id="fit" title="Fit aircraft to view">${icon('fit')}</button><button id="grid" title="Toggle grid and axes">${icon('grid')}</button><button id="download-aircraft" type="button" title="Download aircraft view" aria-label="Download aircraft view" disabled>${icon('download')}</button></div></div>
    <div class="viewport-container"><div id="viewport"></div><div class="viewport-label"><span class="status-dot"></span><span id="geometry-label">Loading geometry</span></div><span class="orbit-hint">DRAG TO ORBIT · SCROLL TO ZOOM</span><div class="axis-key"><span>+x aft</span><span>+y right</span><span>+z up</span></div></div>
    <div class="bottom-panel">
      ${timeTransport}
      ${modeTransport}
      ${frequencyTransport}
      <p id="solution-provenance" class="small muted" role="status" hidden></p>
      <div class="tabbar" role="tablist" aria-label="Analysis details"><button id="tab-loading" role="tab" aria-controls="pane-loading" aria-selected="true" data-tab="loading">2D Plot</button><button id="tab-editor" role="tab" aria-controls="pane-editor" aria-selected="false" data-tab="editor">Editor</button><button id="tab-report" role="tab" aria-controls="pane-report" aria-selected="false" data-tab="report">Solver report</button><button id="tab-time" role="tab" aria-controls="pane-time" aria-selected="false" data-tab="time">Time history</button><button id="tab-modes" role="tab" aria-controls="pane-modes" aria-selected="false" data-tab="modes">Eigenmodes</button><button id="tab-frequency" role="tab" aria-controls="pane-frequency" aria-selected="false" data-tab="frequency">Bode response</button></div>
      <div id="pane-loading" class="tab-pane beam-distribution-pane" role="tabpanel" aria-labelledby="tab-loading">
        ${beamPlotControls({prefix:'plot',quantityOptions:'<optgroup label="Aerodynamics">'+Object.entries(loadingQuantities).map(([value,q])=>`<option value="${value}">${q.label}</option>`).join('')+'<option value="shoulder.2">Shoulder force z</option><option value="shoulder.1">Shoulder force y</option><option value="shoulder.0">Shoulder force x</option></optgroup>'+structureOptions,
          extraControls:structureUnits})}
        <div id="plot" class="plot-empty"><p>Run an analysis to inspect span properties.</p></div>
        ${structureDetails}
      </div>
      ${timePane}
      ${modePane}
      ${frequencyPane}
      <div id="pane-editor" class="tab-pane editor-workspace" role="tabpanel" aria-labelledby="tab-editor" hidden>
        <details id="file-panel" class="editor-panel" open>
          <summary>File</summary>
          <div id="model-configuration" class="editor-panel-content">
            <div class="file-actions"><button id="open">${icon('upload')} Load</button><button id="save" title="Download the current ASW document">${icon('download')} Save</button></div>
            <input type="file" id="file" accept=".asw,text/plain" hidden>
            <label class="field-label" for="example">Example</label>
            <select id="example"><optgroup label="Drela’s ASWING examples"><option value="dae" selected>Daedalus human-powered aircraft</option><option value="usa">Ultralight sailplane</option><option value="fw">Swept flying wing UAV</option></optgroup><option value="" disabled>Custom .asw file</option></select>
            <h2 id="model-name">Aircraft workspace</h2>
            <div class="model-stats"><div><b id="beam-count">—</b><span>Beams</span></div><div><b id="panel-count">—</b><span>Panels</span></div></div>
            <dl class="reference-quantities" aria-label="Reference quantities">
              <div><dt>Area · Sref</dt><dd id="reference-area">—</dd></div>
              <div><dt>Chord · Cref</dt><dd id="reference-chord">—</dd></div>
              <div><dt>Span · Bref</dt><dd id="span">—</dd></div>
              <div><dt>Moment reference · x, y, z</dt><dd id="reference-moment">—</dd></div>
            </dl>
            <div id="beam-list" class="beam-list" aria-label="Surfaces and beams"></div>
            ${['localhost','127.0.0.1','[::1]'].includes(location.hostname)?'':`<a class="local-app-download" href="/openswing-local.zip" download>${icon('download')} Download local app</a>`}
          </div>
        </details>
        <details id="asw-panel" class="editor-panel" open>
          <summary>ASW Editor</summary>
          <div class="editor-toolbar"><span id="filename">dae.asw</span><button id="apply">Apply edits</button></div><div class="asw-editor"><pre id="editor-highlight" class="asw-highlight" aria-hidden="true"></pre><textarea id="editor" spellcheck="false" autocapitalize="off" autocorrect="off" wrap="off" aria-label="ASW configuration editor"></textarea></div>
        </details>
        <details id="mass-panel" class="editor-panel">
          <summary>Mass Properties</summary>
          ${massPane}
        </details>
        <details id="properties-panel" class="editor-panel">
          <summary>Beam Properties</summary>
          ${distributionPane}
        </details>
        <details id="nodes-panel" class="editor-panel">
          <summary>Beam Nodes</summary>
          ${nodePane}
        </details>
      </div>
      <div id="pane-report" class="tab-pane report" role="tabpanel" aria-labelledby="tab-report" hidden><p>No analysis yet. The solver will report convergence and applicable limitations here.</p></div>

    </div>
  </section>
  <aside class="results-panel"><div class="panel-eyebrow">Total Forces</div><div id="result-state" class="result-state">Awaiting analysis</div>
    ${totalForcesMarkup}
  </aside>
</main>
<footer class="desktop-feedback">
  <p id="github-note" class="github-note">Please submit bugs and feature requests <a href="https://github.com/kennyjensen/openswing/issues" target="_blank" rel="noopener noreferrer">here</a>.${buildCommit ? `
    <span class="build-revision"><a href="https://github.com/kennyjensen/openswing/commit/${buildCommit}" target="_blank" rel="noopener noreferrer" aria-label="View build commit ${buildCommit.slice(0,7)} on GitHub"><code>${buildCommit.slice(0,7)}</code></a></span>` : ''}</p>
</footer>
<div id="mobile-workbench" hidden>
  ${['editor','settings','plots','output'].map(key=>`<section id="workspace-${key}" class="workspace-panel" role="tabpanel" aria-labelledby="workspace-tab-${key}" tabindex="0" hidden></section>`).join('')}
  <div id="mobile-action-bar"></div>
  <footer id="mobile-feedback"></footer>
</div>
<div id="error" class="error-banner" role="alert" hidden><strong>Unable to continue</strong><p></p><button id="close-error" aria-label="Dismiss error">×</button></div>

`;

const $ = id => document.getElementById(id);
bindNumberFormatting($('speed'));
const sourceEditor = createAswEditor($('editor'), $('editor-highlight'));
const allocationView=createControlAllocation(resetResult);
const customView=createCustomConstraints(()=>state.model,resetResult);
const state = { source: '', model: null, result: null, trajectory: null, modal: null, frequency: null, deformed: false, busy: false, revision: 0, inspection: 0, dirty: false, filename: 'dae.asw' };
// Keep supplements from opened solutions even though their panels are retired.
const savedModalSupplements = new WeakMap();
let steadyProgressView;
let steadyFlightView;
let aircraftDownload;
const feedbackView = createFeedbackSettings(()=>{refreshConstraintVariables(true);refreshDerivativeParameters(true);resetResult();},download,showError);
const nodeView = createNodeEditor({context:()=>state,rpc,showError,commit:(source,model)=>inspect(source,state.filename,'',model,true)});
const distributionView = createDistributionEditor({context:()=>state,rpc,panels:()=>nodeView.settings(),commit:(source,model)=>inspect(source,state.filename,'',model,true)});
const massView = createMassEditor({context:()=>state,rpc,panels:()=>nodeView.settings(),commit:(source,model)=>inspect(source,state.filename,'',model,true)});
const structureView = createStructureResults(()=>state);
const timeView = createTimeResults(()=>state,(snapshot,fit)=>presentResult(snapshot,'time',state.trajectory.condition,fit),download,resetResult,()=>updateGeometry(true),showError,()=>equilibriumView.initial()?.launch?.condition?.time??0,
  ()=>({format:'openswing-workbench-history',version:1,configuration:captureCase()}),loadHistoryArchive);
const modeView = createModeResults(fit=>{updateGeometry(fit);renderPlot();},resetResult);
const checkpointView = createTimeCheckpoints(()=>state,()=>timeView.selectedIndex(),continueTime,download,showError);
const equilibriumView = createEquilibriumSettings(download,resetResult,showError);
steadyProgressView = createSteadyProgress({getState:()=>state,run:action=>run(action),loadCase,download,showError});
const frequencyView = createFrequencyResults(fit=>{updateGeometry(fit);renderPlot();},resetResult,download,()=>state.model,refineFrequency,()=>!state.busy&&!state.dirty,showError);
const gustView = createGustSettings(rpc,resetResult,download,showError,()=>state.busy,()=>state.revision);
let viewer;
let startupPreviewVisible=false;
viewer = createViewer($('viewport'));
aircraftDownload=createAircraftDownload({button:$('download-aircraft'),viewer,
  getPlayback:()=>state.frequency?frequencyView.playback():state.modal?modeView.playback():state.trajectory?timeView.playback():{playing:false},
  getContext:()=>state.frequency??state.modal??state.trajectory??state.model,
  available:()=>Boolean(state.model)&&!state.busy&&!state.dirty,
  filename:()=>state.filename,download,showError});
const failureElement=document.createElement('section');
failureElement.id='flow-failure';failureElement.hidden=true;
failureElement.setAttribute('aria-label','Rejected airflow diagnostics');
document.querySelector('.viewport-container').after(failureElement);
const flowFailureView=createFlowFailure(failureElement,()=>queueMicrotask(refreshPlotOverlays),download);
function refreshPlotOverlays() {
  viewer?.setOverlay(flowFailureView.overlays());
}

let worker;
let requestId = 0;
const pending = new Map();
function status(message, loading=false, detail='') {
  $('runtime-status').replaceChildren();
  const dot = document.createElement('span'); dot.className = loading ? 'spinner' : 'status-dot';
  $('runtime-status').append(dot, document.createTextNode(message));
  $('runtime-detail').textContent = detail;
  $('runtime-detail').hidden = !detail;
}
function startWorker() {
worker = takeSolverWorker();
worker.onmessage = ({data}) => {
  if (data.type === 'status') { status(data.message, true); return; }
  if (data.type === 'ready') { status('Numerical kernel ready'); return; }
  const item = pending.get(data.id);
  if (!item) return;
  if(data.type==='progress'){
    if(data.action==='operating_points'){
      const detail=mountedStatus(data);
      const label=`Steady point ${data.point}/${data.total_points}`;
      status(`${label}${data.stage==='operating_point_failed'?' · failed; continuing':data.stage==='operating_point_done'?' · complete':' · solving…'}`,true,
        detail?[detail.message,detail.detail].filter(Boolean).join(' · '):'Solving the steady equations with the selected settings.');return;
    }
    const mounted=frequencyStatus(data)||timeStatus(data)||mountedStatus(data);
    if(mounted){status(mounted.message,true,mounted.detail);return;}
    status(data.stage==='initializing'?`Completing initial physical state · ${data.time}/${data.steps} columns…`:data.action==='stability'?(data.stage==='point'?`Solving sweep point ${data.time}…`:`Linearizing sweep dynamics · ${data.time}/${data.steps}…`):data.action==='rom'?`${data.stage==='linearizing'?'Linearizing ROM base':'Comparing reduced and full response'} · ${data.time}/${data.steps}…`:['frequency','extend_frequency'].includes(data.action)?`${data.stage==='linearizing'?'Linearizing dynamics':'Solving frequency response'} · ${data.time}/${data.steps}…`:data.action==='modes'?`Linearizing dynamics · ${data.time}/${data.steps} columns…`:`Integrating · t = ${data.time.toPrecision(5)} T · ${data.steps} accepted steps…`,true);return;
  }
  pending.delete(data.id);
  if (data.error) item.reject(Object.assign(new Error(data.error),{details:data.details,request:item.request,software_provenance:data.software_provenance})); else item.resolve(data.result);
};
worker.onerror = event => {
  for (const item of pending.values()) item.reject(new Error(event.message || 'Numerical worker failed. Reload the page to restart.'));
  pending.clear(); status('Kernel unavailable');
};
}
const currentNumerics=()=>selectedNumerics(structuralSelection);
function rpc(request) {
  return new Promise((resolve,reject) => {
    request=numericalRequest(request,currentNumerics());
    if(!worker)startWorker();
    const id=++requestId;
    pending.set(id,{resolve,reject,request});
    worker.postMessage({id,request});
  });
}
function showError(error) { $('error').hidden=false; $('error').querySelector('p').textContent = error.message.split('\n').filter(Boolean).slice(-1)[0]; }
function download(name, text, type='text/plain') { const url=URL.createObjectURL(new Blob([text],{type})); const a=document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); }
function resetResult() {
  if(state.restoring)return;
  flowFailureView.clear();
  $('solution-provenance')?.setAttribute('hidden','');
  if(state.frequency?.frequency_session)rpc({action:'discard_frequency',session:state.frequency.frequency_session,numerics:state.frequency.request?.numerics,retain_model:true}).catch(()=>{});
  equilibriumView.setComputed(null);
  state.trajectory=null; timeView.setTrajectory(null);
  state.modal=null; modeView.setResult(null);
  state.frequency=null; frequencyView.setResult(null);
  if(state.model) viewer?.update(state.model.beams,state.model.attachments);
  state.deformed=false; $('shape').hidden=true; $('shape-label').textContent='JIG SHAPE';
  document.querySelector('.axis-key').hidden=false;
  $('geometry-label').textContent='BODY FRAME · JIG SHAPE';
  state.revision++; state.result=null;queueMicrotask(refreshPlotOverlays);checkpointView.refresh();distributionView.refresh();massView.refresh();nodeView.refresh();
  ['cl','cd','cdi','cdi-near','cdbody','cdp','cdam','cdeng','cy','roll','pitch','yaw','mach','efficiency','residual','stalled','deflection','mass'].forEach(id => $(id).textContent='—');
  renderFlightOutput(null,null,state.model);
  $('trefftz-note').hidden=true;$('trefftz-note').textContent='';
  $('circulation-note').hidden=true;$('circulation-note').textContent='';
  $('result-state').textContent='Awaiting analysis'; $('result-state').classList.remove('solved');
  
  $('pane-report').textContent='No current result. Run an analysis after changing the model or condition.';
  renderPlot();
  
  steadyProgressView?.invalidate();
  steadyFlightView?.clear();
  aircraftDownload?.refresh();
}
function toggleBusy(value) { state.busy=value; steadyProgressView?.refresh(); steadyFlightView?.refresh(); aircraftDownload?.refresh(); frequencyView.refresh(); distributionView.refresh();massView.refresh();nodeView.refresh(); $('cancel').hidden=!value; $('solve').disabled=value || !state.model || state.dirty; $('solve').querySelector('span').textContent = value ? 'Computing…' : 'Run analysis'; }

function captureCase(){
  if(state.busy||!state.model||state.dirty)throw new Error('Finish the analysis and apply ASW text or mesh edits before saving or loading a case.');
  if(nodeView.hasDraft()||distributionView.hasDraft()||massView.hasDraft())throw new Error('Finish mass-property edits and apply or reload beam-property and node drafts before saving or loading a case.');
  return captureSettings({source:state.source,filename:state.filename,mesh:nodeView.settings(),constraints:readConstraints(),equilibrium:equilibriumView.capture(),numerics:currentNumerics()});
}

function acceptFlightTrim(result){
  // Keep the converged result visible while adopting its solved inputs. No
  // input events: those would discard the result we have just computed.
  for(const [variable,value] of Object.entries(result.operating_values??{})){
    const [kind,key]=variable.split('.');
    const input=kind==='control'?document.querySelector(`[data-control="${key}"]`)
      :kind==='power'?document.querySelector(`[data-power="${key}"]`)
      :$(key?`${kind==='position_earth'?'position-earth':kind}-${key}`:kind);
    if(input)setFieldValue(input,String(['rates','angular_acceleration'].includes(kind)?value*180/Math.PI:value));
  }
  // The solved commands become fixed base inputs for response analysis.
  // Releasing trim targets lets free-flight perturbations accelerate.
  $('constraint-rows').replaceChildren();
  allocationView.refresh(false);customView.refresh();
  equilibriumView.restore({state:result.equilibrium_state,enabled:true,label:'Steady flight trim'});
  $('result-state').textContent='Converged · steady flight';
  status('Steady flight trimmed · ready for response analysis');
  
}
async function loadCase(configuration,solution=null){
  const clean=validateSettings(configuration),backup=captureCase(),oldResult=hasComputedSolution()?captureComputedSolution():null,oldModel=state.model,revision=state.revision;let changed=false;
  async function apply(value,model){
    state.restoring=true;
    try{
      structuralSelection=numericalSelection(value.numerics);
      nodeView.restore(model.mesh_discretization.settings);
      await inspect(value.source,value.filename,'',model);
      if(state.model!==model||state.dirty)throw new Error('The saved model could not be applied.');
      applySettings(value,{refreshDerivatives:()=>refreshDerivativeParameters(),addConstraint,
        clearConstraints:()=>{$('constraint-rows').replaceChildren();allocationView.refresh(false);customView.refresh();},
        restoreEquilibrium:value=>equilibriumView.restore(value)});
      const restored=captureSettings({source:state.source,filename:state.filename,mesh:nodeView.settings(),constraints:readConstraints(),equilibrium:equilibriumView.capture(),numerics:currentNumerics()});
      if(!sameConfiguration(restored,value))throw new Error('Saved inputs could not be restored exactly. The previous workspace has been restored.');
      $('error').hidden=true;
    }finally{state.restoring=false;}
    resetResult();nodeView.plot();
  }
  toggleBusy(true);status('Checking saved case…',true);
  try{
    const model=await rpc({action:'inspect',source:clean.source,panels:clean.mesh,numerics:clean.numerics});validateSettings(clean,model);
    if(revision!==state.revision)throw new Error('Inputs changed while the case was being checked. Load it again when ready.');
    changed=true;await apply(clean,model);if(solution)await restoreComputedSolution(solution);status(solution?'Saved solution opened':'Case inputs restored');
  }catch(error){
    if(changed){await apply(backup,oldModel);if(oldResult)await restoreComputedSolution(oldResult);}
    status('Case load stopped');throw error;
  }finally{toggleBusy(false);if(changed&&state.model)distributionView.setModel(state.model,state.source);}
}

function hasComputedSolution(){return !!(state.frequency||state.modal||state.trajectory||state.result?.request);}
// Only result selectors are presentation state. Numerical setup is captured by
// captureCase; temporary import forms, files and unapplied model edits are not.
function resultViewFields(){
  return [...document.querySelectorAll('.tab-pane input,.tab-pane select,.tab-pane textarea,.time-transport input,.time-transport select')]
    .filter(e=>e.id&&e.type!=='file'&&!e.closest('#pane-nodes,#pane-distributions,#pane-editor')&&!e.id.startsWith('frequency-overlay-'));
}
function captureComputedSolution(){
  const configuration=captureCase(),data=state.frequency??state.modal??state.trajectory??state.result;
  if(!hasComputedSolution()||!data.software_provenance)throw new Error('Run an analysis before saving a computed solution.');
  const kind=state.frequency?'frequency':state.modal?'modes':state.trajectory?'time':data.request.mode;
  const view=Object.fromEntries(resultViewFields().map(e=>[e.id,e.multiple?[...e.selectedOptions].map(o=>o.value):e.type==='checkbox'?e.checked:e.value]));
  if(state.modal)view['modal-select']=String(modeView.selectedIndex());
  view.active_tab=document.querySelector('.tabbar [aria-selected="true"]')?.id??'tab-loading';
  if(workbenchView.current())view.workspace=workbenchView.current();
  return {kind,configuration,data:archivedTimeHistory(data)?copyTimeHistory(data):portableResult(data),provenance:structuredClone(data.software_provenance),view,
    auxiliary:{...portableResult(savedModalSupplements.get(data)??{}),comparison:frequencyView.captureComparison()}};
}
async function restoreComputedSolution(solution){
  const data=archivedTimeHistory(solution.data)?copyTimeHistory(solution.data):shareTimeHistoryMetadata(portableResult(solution.data));
  if(solution.kind==='frequency')presentFrequency(data);
  else if(solution.kind==='modes')presentModes(data);
  else if(solution.kind==='time'){state.trajectory=data;await timeView.setTrajectory(data);$('tab-time').click();}
  else presentResult(data,solution.kind,data.condition);
  const view={...solution.view};
  if(view.active_tab==='tab-structure'){
    view.active_tab='tab-loading';
    view['plot-beam']=view['structure-beam']??view['plot-beam'];
    view['plot-quantity']='structure:'+(view['structure-quantity']??'shell.axial_strain_bound');
  }
  if(['tab-flow','tab-operating-points'].includes(view.active_tab))view.active_tab='tab-loading';
  if(['tab-sensors','tab-feedback','tab-romfiles','tab-derivatives'].includes(view.active_tab))view.active_tab='tab-report';
  state.restoring=true;
  try{
    const restoreField=e=>{if(!Object.hasOwn(view,e.id))return;
      const value=view[e.id];
      if(e.multiple){if(!Array.isArray(value))return;for(const o of e.options)o.selected=value.includes(o.value);}
      else {if(e.tagName==='SELECT'&&![...e.options].some(o=>o.value===value))return;
        if(e.type==='checkbox')e.checked=value;else e.value=value;}
      e.dispatchEvent(new Event('input'));e.dispatchEvent(new Event('change'));
    };
    resultViewFields().forEach(restoreField);
    if(solution.kind==='modes'){
      savedModalSupplements.set(state.modal,portableResult({rom:solution.auxiliary.rom??null,stability:solution.auxiliary.stability??null}));
      if(Object.hasOwn(view,'modal-select'))modeView.select(Number(view['modal-select']));
    }
    if(solution.kind==='time'){await timeView.select(Number($('time-scrub').value));await timeView.ready();}
    if(solution.kind==='frequency')frequencyView.restoreComparison(solution.auxiliary.comparison);
  }finally{state.restoring=false;}
  const tab=$(view.active_tab);if(tab?.matches('.tabbar button'))tab.click();
  if(solution.view.workspace)workbenchView.show(solution.view.workspace);
  const same=solution.provenance.fingerprint===state.model.software_provenance?.fingerprint;
  const mixed=data.history_sources?.some(s=>s.software_provenance?.fingerprint!==solution.provenance.fingerprint);
  $('solution-provenance').hidden=false;$('solution-provenance').textContent=`Saved calculation · ${same?'same numerical version':'different numerical version'} for the latest calculation.${mixed?' Retained history includes a different or unrecorded numerical version.':''} Values are displayed without recomputation. New calculations use the currently loaded kernel.`;
  
}
async function loadComputedSolution(value){
  const revision=state.revision,solution=await verifySolution(value);
  if(revision!==state.revision)throw new Error('Inputs changed while the saved solution was being checked. Open it again when ready.');
  await loadCase(solution.configuration,solution);
}

async function loadHistoryArchive(file){
  const backup=captureCase(),oldResult=hasComputedSolution()?captureComputedSolution():null;
  const revision=state.revision;let changed=false,appliedRevision=null;
  toggleBusy(true);status('Opening complete time history…',true);
  try{
    const reader=await openTimeHistoryArchive(file),result=archiveTrajectory(reader),saved=result.openswing_workbench;
    if(saved?.format!=='openswing-workbench-history'||saved.version!==1)throw new Error('This archive has no saved workbench settings. Open a file made with Save complete history.');
    const configuration=validateSettings(saved.configuration);
    if(configuration.fields.mode!=='time'||result.request?.source!==configuration.source
      ||!sameNumerics(configuration.numerics,result.numerics)||!sameNumerics(configuration.numerics,result.request?.numerics))
      throw new Error('The history, ASW source and saved numerical settings do not match.');
    if(!result.software_provenance||await kernelFingerprint(result.software_provenance)!==result.software_provenance.fingerprint)
      throw new Error('The history numerical fingerprint is inconsistent.');
    // Check the first complete state before replacing any workbench data.
    const first=await timeHistory(result).read(0);timeHistory(result).pin(0,first);
    if(state.revision!==revision)throw new Error('Inputs changed while the history was being opened. Open it again when ready.');
    toggleBusy(false);await loadCase(configuration);changed=true;
    appliedRevision=state.revision;toggleBusy(true);state.trajectory=result;$('tab-time').click();await timeView.setTrajectory(result);
    if(state.revision!==appliedRevision||state.trajectory!==result)throw new Error('Inputs changed while the history was being opened.');
    $('solution-provenance').hidden=false;$('solution-provenance').textContent='Saved complete history · physical snapshots are read from the archive when selected. Values are displayed without recomputation.';
    status(`Complete history opened · ${reader.snapshotCount} snapshots`);
  }catch(error){
    if(changed&&state.revision===appliedRevision){toggleBusy(false);await loadCase(backup,oldResult);}
    status('History open stopped');throw error;
  }finally{toggleBusy(false);checkpointView.refresh();}
}

async function inspect(source, filename=state.filename, exampleKey='', prepared=null, preserveConditions=false, freshMesh=false) {
  if(freshMesh){
    nodeView.clear();
    // A newly opened aircraft or reset mesh cannot use the previous aircraft's
    // loaded state. Project loading restores its matching state separately.
    equilibriumView.restore({state:null,enabled:false,label:''});
    // Operating targets can name controls, sensors and custom equations that
    // belong to the previous aircraft. Mesh edits and saved-case restoration
    // use the non-fresh path and retain their own targets.
    $('constraint-rows').replaceChildren();
    allocationView.refresh(false);customView.refresh();
    // Match the approximate drawing density of Drela's gust animation.
    // The mesher retains required stations even if they raise the panel count.
    const mesh=exampleKey==='usa'?sailplaneMesh:daedalusDefaultMesh(source);
    if(mesh)nodeView.restore(mesh);
  }
  const sameSource=source===state.source;
  if(!sameSource)$('time-forcing').value='';
  if(sameSource && !exampleKey) exampleKey=$('example').value;
  resetResult(); $('error').hidden=true; const inspection=++state.inspection;
  state.model=null; state.source=source; state.filename=filename; state.dirty=true; distributionView.refresh();massView.refresh();nodeView.refresh();steadyProgressView?.refresh();
  $('editor').value=source; sourceEditor.refresh(); $('filename').textContent=filename; $('solve').disabled=true;
  status('Reading configuration…', true);
  try {
    const model=prepared ?? await rpc({action:'inspect',source,panels:nodeView.settings()});
    if (inspection!==state.inspection) return;
    if(!sameNumerics(currentNumerics(),model.numerics))throw new Error('The inspected model uses different numerical settings. Apply the model again.');
    const oldControls=(sameSource||preserveConditions)?Object.fromEntries([...$('controls').querySelectorAll('input')].map(input=>[input.dataset.control,input.value])):{};
    const oldPowers=(sameSource||preserveConditions)?Object.fromEntries([...$('powers').querySelectorAll('input')].map(input=>[input.dataset.power,input.value])):{};
    const oldCirculation=(sameSource||preserveConditions)?Object.fromEntries([...$('circulation-modes').querySelectorAll('input')].map(input=>[input.dataset.circulationBeam,input.value])):{};
    state.model=model; state.dirty=false;
    $('example').value=exampleKey;
    const displayName=model.name;
    $('model-name').textContent=displayName;
    $('beam-count').textContent=model.beams.length;
    $('panel-count').textContent=model.beams.reduce((sum,b)=>sum+b.panels,0);
    const lengthUnit=model.si && Math.abs(model.si.L-1)<1e-9 ? 'm' : model.si && Math.abs(model.si.L-.3048)<1e-9 ? 'ft' : 'L';
    const referenceValue=value=>Number(value.toPrecision(6)).toString();
    $('reference-area').textContent=`${referenceValue(model.reference[0][0])} ${lengthUnit}²`;
    $('reference-chord').textContent=`${referenceValue(model.reference[0][1])} ${lengthUnit}`;
    $('span').textContent=`${referenceValue(model.reference[0][2])} ${lengthUnit}`;
    $('reference-moment').textContent=`${model.reference[1].map(referenceValue).join(', ')} ${lengthUnit}`;
    $('geometry-label').textContent=displayName;
    $('beam-list').replaceChildren(); $('plot-beam').replaceChildren(); $('controls').replaceChildren();
    $('circulation-modes').replaceChildren();$('circulation-settings').hidden=!model.beams.some(b=>b.lifting);
    for (const beam of model.beams) {
      if(beam.lifting){
        const label=document.createElement('label');label.textContent=`${beam.name} · modes`;
        const input=document.createElement('input');input.type='number';input.min='0';input.max='512';input.step='1';
        input.dataset.circulationBeam=beam.index;input.value=oldCirculation[beam.index]??'0';
        input.addEventListener('input',()=>{resetResult();nodeView.plot();});label.append(input);$('circulation-modes').append(label);
      }
      const row=document.createElement('div'); row.className='beam-row';
      row.style.setProperty('--beam-color',beamColor(model.beams,beam.index));
      const name=document.createElement('span'); name.textContent=beam.name;
      const n=document.createElement('span'); n.textContent=beam.lifting?'SURFACE':'BODY';
      row.append(name,n); $('beam-list').append(row);
      { const option=document.createElement('option'); option.value=beam.index; option.textContent=beam.name; $('plot-beam').append(option); }
    }
    for (const control of model.controls) {
      const label=document.createElement('label'); label.textContent=`Flap ${control}`;
      // Trimmed control settings are continuous; retain their full precision.
      const input=document.createElement('input'); input.type='number'; input.step='any'; input.value=oldControls[control]??'0'; input.dataset.control=control; input.addEventListener('input',resetResult);
      label.append(input); $('controls').append(label);
    }
    $('powers').replaceChildren();
    for (const control of model.engine_controls) {
      const label=document.createElement('label'); label.textContent=`Engine ${control.index}`;
      const unit=document.createElement('span');unit.textContent=control.types.every(t=>t!==0)?'input F·L/T':control.types.every(t=>t===0)?'control setting':'mixed model setting';label.append(unit);
      const input=document.createElement('input');input.type='number';input.step='any';input.value=oldPowers[control.index]??'0';input.dataset.power=control.index;input.addEventListener('input',resetResult);
      label.append(input);$('powers').append(label);
    }
    $('sensor-settings').hidden=!model.sensors.length;
    if(!sameSource&&!preserveConditions) {
      $('density').value=model.constants[1]; $('modal-quiescent-density').value=model.constants[1]; $('gravity-magnitude').value=model.constants[0];
      $('static-gravity-z').value=-model.constants[0];
      if(model.signed_point_weights?.length||model.signed_distributed_weights?.length){
        $('mode').value='structural';$('static-gravity-mode').value='file';
        await changeAnalysisMode({modelImport:true});
        // A source-coupled selection resets to the default when signed static
        // loads choose structural mode. Its replacement inspection owns UI state.
        if(inspection!==state.inspection)return;
      }
    }
    refreshAnalysisVisibility();
    $('plot-quantity').querySelector('option[value="cl"]').disabled=!model.beams[0]?.lifting;
    $('plot-quantity').value=$('mode').value==='structural'?
      (model.signed_distributed_weights?.length?'structure:moment_axes.0':'structure:moment_axes.1'):
      model.beams[0]?.lifting?'cl':'fz';
    distributionView.setModel(model,source);
    massView.setModel(model,source);
    nodeView.setModel(model);
    refreshConstraintVariables(sameSource||preserveConditions);
    steadyFlightView?.setModel(model,source);
    frequencyView.refresh();
    refreshDerivativeParameters(sameSource||preserveConditions);
    const scales=model.si;
    $('speed-unit').textContent = scales && Math.abs(scales.L/scales.T-1)<1e-9 ? 'm/s' : scales && Math.abs(scales.L/scales.T-0.3048)<1e-9 ? 'ft/s' : 'input L/T';
    $('unit-note').textContent=scales ? `One input length unit = ${scales.L.toPrecision(5)} m. Airspeed uses input L/T; flap settings use the file’s derivative units.` : 'Custom unit labels. Calculations use consistent file input units.';
    const preservePreviewCamera=startupPreviewVisible&&exampleKey==='dae'&&freshMesh;
    startupPreviewVisible=false;
    viewer?.update(model.beams,model.attachments,null,{fit:!preservePreviewCamera});
    refreshPlotOverlays(); status(model.diagnostics.length ? 'Loaded with input warnings' : 'Configuration ready');
    if (model.diagnostics.length) showError(new Error(model.diagnostics.join(' ')));
    $('solve').disabled=state.busy;
  } catch (error) { if(inspection===state.inspection) { showError(error); status('Configuration needs attention'); } }
  finally{if(inspection===state.inspection){steadyProgressView?.refresh();steadyFlightView?.refresh();aircraftDownload?.refresh();}}
}

async function run(equilibriumJob=null) {
  const bounded=equilibriumJob!==null;
  await massView.ready();
  if(massView.hasDraft()){showError(new Error('Finish the mass-property edit before running analysis.'));return;}
  if(state.busy || state.dirty || !state.model) {
    return;
  }
  if(bounded&&(nodeView.hasDraft()||distributionView.hasDraft()||massView.hasDraft()))throw new Error('Apply or reload node and beam-property drafts before advancing equilibrium.');
  const jobConfiguration=bounded?captureCase():null;
  if(bounded)resetResult();
  flowFailureView.clear();
  $('error').hidden=true;
  $('solution-provenance').hidden=true;
  const revision=state.revision;
  const mode=$('mode').value,quiescent=quiescentSelected(),sourceVacuum=sourceVacuumSelected(),sourceStillAir=sourceStillAirSelected(),sourceMoving=sourceMovingVacuumSelected(),sourceAirflow=sourceAirflowSelected(),seed=quiescent?null:equilibriumView.initial(),savedLaunch=mode==='time'&&!!seed;
  if(sourceVacuum)try{assertVacuumInputs(vacuumWorkbenchFields(),readConstraints());}
  catch(error){showError(error);workbenchView.show('settings');return;}
  if(sourceStillAir)try{assertStillAirInputs(vacuumWorkbenchFields(),readConstraints());}
  catch(error){showError(error);workbenchView.show('settings');return;}
  if(sourceMoving)try{assertMovingVacuumInputs(vacuumWorkbenchFields(),readConstraints());}
  catch(error){showError(error);workbenchView.show('settings');return;}
  if(sourceAirflow)try{assertAirflowInputs(vacuumWorkbenchFields(),readConstraints(),{savedLaunch});}
  catch(error){showError(error);workbenchView.show('settings');return;}
  const controls=Object.fromEntries([...$('controls').querySelectorAll('input')].map(input=>[input.dataset.control,Number(input.value)]));
  let condition={speed:Number(fieldValue($('speed'))),alpha:Number($('alpha').value),beta:Number($('beta').value),stall:$('stall').checked,controls};
  for(const name of ['factor','width'])condition['stall_'+name]=$('stall-'+name).value.trim()===''?null:Number($('stall-'+name).value);
  condition.sensor_flow=$('sensor-flow').value;
  condition.aero_lag=$('aero-lag').checked;
  condition.freeze_influences=$('freeze-influences').checked;
  condition.wake_core_ratio=$('wake-core-ratio').value.trim()===''?null:Number($('wake-core-ratio').value);
  condition.circulation_modes=Object.fromEntries([...$('circulation-modes').querySelectorAll('input')].map(input=>[input.dataset.circulationBeam,Number(input.value)]));
  condition.body_added_mass_factor=defaultBodyAddedMassFactor;
  condition.altitude_m=Number($('altitude').value)*Number($('altitude-unit').value);
  condition.density=$('density-mode').value==='custom'?Number($('density').value):null;
  condition.gravity_magnitude=$('gravity-mode').value==='custom'?Number($('gravity-magnitude').value):null;
  condition.mach=$('mach-mode').value==='fixed'?Number($('pg-mach').value):null;
  condition.load_factor=Number($('load-factor').value);
  condition.ground_effect=Number($('ground-effect').value);
  condition.position_earth=['x','y','z'].map(a=>Number($(`position-earth-${a}`).value));
  condition.attitude=['bank','elevation','heading'].map(a=>Number($(`attitude-${a}`).value));
  condition.ground_normal=['x','y','z'].map(a=>Number($(`ground-normal-${a}`).value));
  condition.powers=Object.fromEntries([...$('powers').querySelectorAll('input')].map(input=>[input.dataset.power,Number(input.value)]));
  for(const [key] of motionGroups) condition[key]=['x','y','z'].map(axis=>Number($(`${key}-${axis}`).value)*(key==='acceleration'?1:Math.PI/180));
  if(quiescent) {
    try { condition=quiescentCondition({density:Number($('modal-quiescent-density').value),position_earth:condition.position_earth,attitude:condition.attitude,gravity_magnitude:condition.gravity_magnitude,
      ...(state.model.beams.some(b=>!b.lifting)?{body_added_mass_factor:condition.body_added_mass_factor}:{})}); }
    catch(error){showError(error);workbenchView.show('settings');return;}
  }
  if(!savedLaunch)for (const input of document.querySelectorAll('#analysis-settings .fields input,#operating-settings:not([hidden]) input')) {
    if(input.closest('[hidden]:not(.workspace-panel):not(#mobile-workbench):not(#desktop-workbench),#turn-preset,#gust-settings'))continue;
    if(!input.checkValidity() || !input.value) {
      workbenchView.show('settings');
      for(let disclosure=input.closest('details');disclosure;disclosure=disclosure.parentElement?.closest('details'))
        disclosure.setAttribute('open','');
      input.focus();input.reportValidity();
      const label=input.labels?.[0]?.textContent.trim()||input.getAttribute('aria-label')||input.id||'operating-condition field';
      const reason=input.value?input.validationMessage:'A value is required.';
      const error=new Error(`Check ${label}: ${reason||'Enter a valid value.'}`);
      showError(error);return;
    }
  }
  const operating_constraints=['mounted','frequency'].includes(mode)||(mode==='modes'&&!$('modal-vacuum').checked&&!quiescent)?readConstraints():[];
  const derivatives=mode==='mounted'&&$('derivatives-enable').checked ? {response:$('derivative-response').value,basis:$('derivative-basis').value,axes:$('derivative-axes').value,step:Number($('derivative-step').value),parameters:[...document.querySelectorAll('#derivative-parameters input:checked')].map(input=>input.value)}:undefined;
  timeView.pause();
  modeView.pause();
  frequencyView.pause();
  toggleBusy(true); status(mode==='frequency'?'Solving the response base and linearizing dynamics…':mode==='modes'?'Solving the modal base and linearizing dynamics…':mode==='time'?'Integrating elastic motion, circulation and flight state…':mode==='structural'?'Solving nonlinear beam equilibrium under static loads…':mode==='mounted' ? 'Solving beam equilibrium and circulation together…' : 'Solving circulation and section loads…',true);
  workbenchView.show('plots');
  try {
    if(!savedLaunch&&mode!=='structural'&&!quiescent&&!sourceVacuum&&!sourceMoving)Object.assign(condition,gustView.condition(mode));
    let request={action:['time','modes','frequency'].includes(mode)?mode:'solve',mode,source:state.source,condition,operating_constraints,derivatives,strut_mode:defaultStrutMode,panels:nodeView.settings(),...fourierWakeOptions(mode,$('fourier-wake-diagnostic').checked)};
    if(mode==='structural'){
      request.condition=null;
      request.gravity=$('static-gravity-mode').value==='custom'?['x','y','z'].map(a=>Number($(`static-gravity-${a}`).value)):null;
    }
    if(mode==='time'){
      request.time=timeView.options();
      if(request.time.disturbance&&!savedLaunch)throw new Error('Initial physical disturbance requires an enabled loaded saved equilibrium. Compute and use an equilibrium or import one first.');
    }
    if(mode==='modes')request.modes=modeView.options();
    if(mode==='frequency'){request.frequency=frequencyView.options();request.frequency_spacing=$('frequency-spacing').value;request.retain_frequency=true;}
    if(!savedLaunch&&!quiescent&&!sourceVacuum&&!sourceMoving&&['time','modes','frequency'].includes(mode)){request[mode==='time'?'time':mode==='modes'?'modes':'frequency'].controller=feedbackView.options();}
    if(mode==='mounted')request.controller=feedbackView.options();
    if(savedLaunch)request={action:'launch_time',source:state.source,equilibrium_state:seed,time:timeView.options()};
    if(seed){if(['mounted','structural'].includes(mode))request.initial_state=seed;else if(['modes','frequency'].includes(mode))request[mode].initial_state=seed;}
    if(mode==='frequency'&&$('frequency-inputs').value!=='initial'&&!sourceVacuum&&!sourceStillAir&&!sourceMoving)request.frequency.inputs.push(...feedbackView.inputs());
    if(mode==='frequency'&&(sourceVacuum||sourceStillAir||sourceMoving))request=sourceFrequencyRequest(request,currentNumerics(),condition,sourceMoving?movingVacuumFrame(vacuumWorkbenchFields()):undefined);
    if(sourceVacuum&&mode==='modes')request=vacuumModalRequest(request,condition);
    if(sourceStillAir&&mode==='modes')request=stillAirModalRequest(request,condition);
    if(sourceMoving&&mode!=='frequency')request=mode==='modes'?movingVacuumModalRequest(request,movingVacuumFrame(vacuumWorkbenchFields())):
      movingVacuumTimeRequest(request,savedLaunch?undefined:movingVacuumFrame(vacuumWorkbenchFields()));
    if(sourceAirflow&&mode!=='mounted')request=airflowDynamicRequest(request);
    request=numericalRequest(request,currentNumerics());
    if(request.numerics&&mode==='structural'){delete request.operating_constraints;delete request.derivatives;}
    if(bounded)request=steadyProgressView.request(request,equilibriumJob);
    const result=await rpc(request);
    if(revision!==state.revision) {
      status('Inputs changed; run again for current results');return;
    }
    if(bounded&&result.continuation_status==='pending'){
      steadyProgressView.pending(jobConfiguration,request,result);
      $('result-state').textContent='Unfinished equilibrium';
      $('pane-report').textContent=`UNFINISHED EQUILIBRIUM\nApplied load ${(100*result.load_fraction).toFixed(2)}%\nAccepted load steps ${result.accepted_load_steps}\nPhysical residual ${result.checkpoint.physical_residual.toExponential(5)}\n\nNo full-load result is available. Save or advance this solve in Settings → Resumable equilibrium.`;
      status(`Equilibrium paused at ${(100*result.load_fraction).toFixed(2)}% applied load`);
      workbenchView.show('settings');return;
    }
    if(bounded){
      if(result.continuation_status!=='complete'||!result.converged||!result.equilibrium_state)throw new Error('Equilibrium job returned neither checked progress nor a converged result.');
    }
    state.modal=null;modeView.setResult(null);
    state.frequency=null;frequencyView.setResult(null);
    if(mode==='frequency'){
      state.trajectory=null;timeView.setTrajectory(null);
      presentFrequency({...result,condition:sourceVacuum||sourceStillAir||sourceMoving?null:condition,model:state.model.name,request});
    } else if(mode==='modes') {
      state.trajectory=null;timeView.setTrajectory(null);
      presentModes({...result,condition:sourceVacuum||sourceStillAir||sourceMoving?null:condition,model:state.model.name,request,reference_span:state.model.reference[0][2]});
    } else if(mode==='time') {
      state.trajectory=restoreWorkerTimeHistory(shareTimeHistoryMetadata({...result,condition:result.restart_context.setup.condition,model:state.model.name,request}));
      await timeView.setTrajectory(state.trajectory);
      $('tab-time').click();
    } else {
      state.trajectory=null;timeView.setTrajectory(null);
      presentResult({...result,request,requested_operating_constraints:operating_constraints},mode,condition);
    }
    if(bounded)steadyProgressView.complete();
    status(mode==='time'?'Time integration converged':mode==='frequency'&&!result.converged?'Frequency response finished with gaps':'Analysis converged');
    return result;
  } catch(error) { if(revision===state.revision) {
    resetResult(); showError(error); status('Analysis stopped');
    flowFailureView.set(error.details,{span:Math.abs(state.model?.reference[0][2]??1),request:error.request,provenance:error.software_provenance,message:error.message});
  } }
  finally { toggleBusy(false); }
}

function updateGeometry(fit=true) {
  queueMicrotask(refreshPlotOverlays);
  
  
  if(state.frequency){
    const geometry=frequencyView.geometry(),earth=$('frequency-view').value==='earth';
    if(geometry){viewer?.update(geometry.beams,geometry.attachments,geometry.ground,{fit});document.querySelector('.axis-key').hidden=earth;}
    else {viewer?.update(state.frequency.base.geometry,state.frequency.base.attachments,state.frequency.base.ground_plane,{fit});document.querySelector('.axis-key').hidden=false;}
    $('geometry-label').textContent=geometry?`${earth?'EARTH':'BODY'} FRAME · LINEAR HARMONIC RESPONSE`:frequencyView.initial()?'BODY FRAME · BASE · INITIAL-STATE SPECTRUM':'BODY FRAME · BASE · RESPONSE UNAVAILABLE';
    return;
  }
  if(state.modal){
    const {beams,attachments,ground}=modeView.geometry();
    viewer?.update(beams,attachments,ground,{fit});
    const earth=$('modal-view').value==='earth';document.querySelector('.axis-key').hidden=earth;
    $('geometry-label').textContent=`${earth?'EARTH':'BODY'} FRAME · SCALED LINEAR MODE`;
    return;
  }
  const result=state.result;
  let beams=state.deformed?result?.geometry:state.model?.beams;
  let attachments=state.deformed?result?.attachments:state.model?.attachments;
  if(!beams)return;
  let ground=result?.ground_plane;
  const earth=!!state.trajectory&&$('time-view').value==='earth';
  if(state.trajectory)({beams,attachments,ground}=trajectoryGeometry(beams,attachments,result,earth));
  viewer?.update(beams,attachments,ground,{fit});
  document.querySelector('.axis-key').hidden=earth;
  $('geometry-label').textContent=earth?'EARTH FRAME · TRUE SCALE':'BODY FRAME · TRUE SCALE';
}

function presentFrequency(result,preserve=false){
  if(!result.vacuum&&!isQuiescentResult(result))result={...result,condition:solvedFlightCondition(result.condition,result.base)};
  if(result.vacuum||isQuiescentResult(result)){
    presentStructuralStatic(result.base,!preserve);
    if(isQuiescentResult(result))equilibriumView.setComputed(null);
  }else presentResult(result.base,'mounted',result.condition,!preserve);
  state.frequency=result;state.deformed=true;
  $('shape').hidden=true;$('shape-label').textContent='LINEAR FREQUENCY RESPONSE';
  $('result-state').textContent='Frequency-response base';$('result-state').classList.add('solved');
  const pre=$('pane-report').querySelector('pre');
  pre.textContent=`FREQUENCY RESPONSE · ${result.frame_mode} FRAME\n\n${result.limitations.join('\n\n')}\n\nFREQUENCY DIAGNOSTICS\n${JSON.stringify(result.diagnostics,null,2)}\n\nBASE FRAME AND DRIFT\n${JSON.stringify(result.base.modal_base,null,2)}\n\n`+pre.textContent;
  frequencyView.setResult(result,preserve);refreshPlotAvailability();$('tab-frequency').click();
}

async function refineFrequency(frequencies){
  const previous=state.frequency;
  if(state.busy||state.dirty||!previous?.frequency_session)throw new Error('Load a current frequency analysis before adding samples.');
  const revision=state.revision;
  frequencyView.pause();$('error').hidden=true;toggleBusy(true);status('Adding samples to the loaded frequency response…',true);
  try{
    const result=await rpc({action:'extend_frequency',source:state.source,numerics:previous.request.numerics,session:previous.frequency_session,frequencies});
    if(revision!==state.revision||state.frequency!==previous)throw new Error('The aircraft inputs changed during frequency refinement.');
    const request=structuredClone(previous.request);request.frequency.frequencies=result.samples.map(s=>s.omega);
    presentFrequency({...result,condition:previous.condition,model:previous.model,request},true);
    status(result.converged?'Frequency refinement complete':'Frequency refinement finished with gaps');
  }catch(error){status('Frequency refinement stopped');throw error;}
  finally{toggleBusy(false);}
}

function presentModes(result){
  const quiescent=isQuiescentResult(result),sourceMoving=result.numerics?.structural_operator==='drela-moving-vacuum-v1';
  if(!result.vacuum&&!quiescent)result={...result,condition:solvedFlightCondition(result.condition,result.base)};
  if(!result.vacuum&&!quiescent)presentResult(result.base,'mounted',result.condition);
  else {
    state.result={...result.base,strips:[],condition:result.condition,model:state.model.name};
    renderFlightOutput(null,null,state.model);
    for(const id of ['cl','cd','cdi','cdi-near','cdbody','cdp','cdam','cdeng','cy','roll','pitch','yaw','mach','efficiency','stalled'])$(id).textContent='—';
    $('trefftz-note').hidden=true;$('trefftz-note').textContent='';
    $('circulation-note').hidden=true;$('circulation-note').textContent='';
    $('mass').textContent=result.base.mass_properties.mass.toPrecision(5);
    $('deflection').textContent=result.base.max_displacement.toPrecision(5);
    $('residual').textContent=result.diagnostics.base_residual.toExponential(1);
    renderPlot();
    const report=document.createElement('pre');report.textContent=`${quiescent?`STILL-AIR STRUCTURAL BASE EQUILIBRIUM\nDensity [M/L³] ${result.fluid.density}\nMean flow: exactly zero\n`:"VACUUM BASE EQUILIBRIUM\n"}Mass [M] ${result.base.mass_properties.mass}\nGravity in body axes [L/T²] ${result.base.gravity_body.join(', ')}\nSupport force [F] ${result.base.support_force.join(', ')}\nSupport moment [F·L] ${result.base.support_moment.join(', ')}\n`; $('pane-report').replaceChildren(report);
  }
  equilibriumView.setComputed(quiescent?null:result.base.equilibrium_state);
  state.modal=result;state.deformed=true;
  $('shape').hidden=true;$('shape-label').textContent='LINEAR MODE · SCALED';
  $('result-state').textContent='Modal base equilibrium';$('result-state').classList.add('solved');
  const pre=$('pane-report').querySelector('pre');
  pre.textContent=`${result.numerics?.structural_operator==='drela-fixed-still-air-v1'?'ASWING FIXED-FRAME STILL AIR':quiescent?'STILL-AIR':result.numerics?.structural_operator==='drela-fixed-vacuum-v1'?'ASWING FIXED-FRAME VACUUM':sourceMoving?'ASWING MOVING-FRAME VACUUM':'COUPLED'} EIGENMODES · ${result.frame_mode} FRAME\n\n${quiescent?'Structural modes with surface and fuselage fluid added mass. No circulation or aerodynamic coefficients. Workbench saved-equilibrium reuse, time launch, ROM and stability sweeps are unavailable.\n\n':''}${result.limitations.join('\n\n')}\n\nMODAL DIAGNOSTICS\n${JSON.stringify(result.diagnostics,null,2)}\n\nBASE FRAME AND DRIFT\n${JSON.stringify(result.base.modal_base,null,2)}\n\n`+pre.textContent;
  modeView.setResult(result);refreshPlotAvailability();$('tab-modes').click();
}

async function continueTime(saved,options,parent,index){
  if(state.busy||state.dirty||!state.model)throw new Error('Finish the current analysis and load the matching ASW source before continuing.');
  const revision=state.revision,request=numericalRequest({action:'resume_time',source:state.source,checkpoint:saved,time:options},currentNumerics());
  timeView.pause();modeView.pause();frequencyView.pause();$('error').hidden=true;toggleBusy(true);status('Continuing the saved trajectory…',true);
  try{
    const result=shareTimeHistoryMetadata(await rpc(request),parent===state.trajectory?parent:null);
    if(revision!==state.revision)throw new Error('The aircraft inputs changed during continuation.');
    $('solution-provenance').hidden=true;
    let output=restoreWorkerTimeHistory({...result,condition:result.restart_context.setup.condition,model:state.model.name,request});
    if(parent===state.trajectory&&Number.isInteger(index)){
      output=await joinTimeHistory(parent,index,output);
    }
    state.modal=null;modeView.setResult(null);
    state.frequency=null;frequencyView.setResult(null);state.trajectory=output;
    await timeView.setTrajectory(output);$('tab-time').click();status('Time continuation converged');
  }catch(error){status('Time continuation stopped');throw error;}
  finally{toggleBusy(false);checkpointView.refresh();}
}

function presentStructuralTime(result,fit){
  equilibriumView.setComputed(null);checkpointView.refresh();
  state.result={...result,strips:[],condition:null,model:state.model.name};
  renderFlightOutput(null,null,state.model);
  for(const id of ['cl','cd','cdi','cdi-near','cdbody','cdp','cdam','cdeng','cy','roll','pitch','yaw','mach','efficiency','stalled'])$(id).textContent='—';
  $('trefftz-note').hidden=true;$('trefftz-note').textContent='';
  $('circulation-note').hidden=true;$('circulation-note').textContent='';
  $('mass').textContent=result.mass_properties.mass.toPrecision(5);
  $('deflection').textContent=result.max_displacement.toPrecision(5);
  $('residual').textContent=result.residual.toExponential(1);
  $('result-state').textContent=`Structural time response · t = ${result.time.toPrecision(5)} T`;
  $('result-state').classList.add('solved');
  if(fit)state.deformed=true;$('shape').hidden=false;
  $('shape').textContent=state.deformed?'Show jig':'Show deformed';$('shape-label').textContent=state.deformed?'DEFORMED · 1×':'JIG SHAPE';
  updateGeometry(fit);
  const report=document.createElement('pre'),t=state.trajectory;
  report.textContent=`STRUCTURAL TIME RESPONSE · t = ${result.time} input T
${t.method}, ${t.frame_mode} frame; ${t.accepted_steps} accepted steps, ${t.rejected_steps} retries
Snapshot step ${result.step}, order ${result.order} · ${timePhase(result)}
Normalized residual ${result.residual.toExponential(5)}
Gravity in body axes [L/T²] ${result.gravity_body.join(', ')}
Support force [F] ${result.support_force.join(', ')}
Support moment [F·L] ${result.support_moment.join(', ')}
FRAME STATE
${JSON.stringify(result.frame,null,2)}
INITIALIZATION
${JSON.stringify(t.initialization??result.initial_phase??'time checkpoint',null,2)}
${t.limitations.join('\n')}
SECTION RECOVERY
${JSON.stringify(result.structure.summary,null,2)}
${result.structure.limitations.join('\n')}`;
  $('pane-report').replaceChildren(report);renderPlot();
}

function hingeReport(hinges){
  return hinges?.length?`\nSPRUNG HINGES\n${hinges.map(h=>`Joint ${h.joint}: beam ${h.beam} at t=${h.t} → beam ${h.other_beam} at t=${h.other_t}\n  hinge angle [deg] ${h.angle_deg.toPrecision(7)}\n  beam-1 structural moment [F·L] ${h.structural_moment.toPrecision(7)} (${h.moment_trace} trace)\n  compliance [deg / F·L] ${h.compliance_deg_per_moment.toPrecision(7)}\n  current axis ${h.axis.map(x=>x.toFixed(6)).join(', ')}${h.extrapolated?'\n  EXTRAPOLATED: moment exceeds the Jangle table range.':''}`).join('\n')}\n`:'';
}

function presentStructuralStatic(result,fit){
  equilibriumView.setComputed(result.equilibrium_state);checkpointView.refresh();
  state.result={...result,strips:[],condition:null,model:state.model.name};
  renderFlightOutput(null,null,state.model);
  for(const id of ['cl','cd','cdi','cdi-near','cdbody','cdp','cdam','cdeng','cy','roll','pitch','yaw','mach','efficiency','stalled'])$(id).textContent='—';
  for(const id of ['trefftz-note','circulation-note']){$(id).hidden=true;$(id).textContent='';}
  $('mass').textContent=result.mass_properties.physical===false?'—':result.mass_properties.mass.toPrecision(5);
  $('deflection').textContent=result.max_displacement.toPrecision(5);$('residual').textContent=result.residual.toExponential(1);
  $('result-state').textContent=result.numerics?'Converged · ASWING static · experimental':'Converged · structural static';$('result-state').classList.add('solved');
  
  if(fit)state.deformed=true;$('shape').hidden=false;
  $('shape').textContent=state.deformed?'Show jig':'Show deformed';$('shape-label').textContent=state.deformed?'DEFORMED · 1×':'JIG SHAPE';
  updateGeometry(fit);
  const report=document.createElement('pre');
  report.textContent=`STRUCTURAL STATIC · NO AIRFLOW\nNormalized residual ${result.residual.toExponential(5)}\nMaximum displacement [L] ${result.max_displacement.toPrecision(8)}\nGravity in body axes [L/T²] ${result.gravity_body.join(', ')}\nApplied force [F] ${result.applied_force.join(', ')}\nApplied moment [F·L] ${result.applied_moment.join(', ')}\nSupport force [F] ${result.support_force.join(', ')}\nSupport moment [F·L] ${result.support_moment.join(', ')}\nForce balance [F] ${result.force_balance.join(', ')}\nMoment balance [F·L] ${result.moment_balance.join(', ')}\n\n${result.mass_properties.physical===false?result.mass_properties.scope:'Mass [M] '+result.mass_properties.mass}\n\nEQUILIBRIUM INITIALIZATION\n${JSON.stringify(result.equilibrium_initialization,null,2)}\n\nSECTION RECOVERY\n${JSON.stringify(result.structure.summary,null,2)}\n${result.structure.limitations.join('\n')}\n\n${result.limitations.join('\n')}`;
  report.textContent+=hingeReport(result.hinges);
  $('pane-report').replaceChildren(report);renderPlot();
  $('tab-loading').click();
}

function presentResult(result,mode,condition,fit=true) {
    if(mode==='structural'){presentStructuralStatic(result,fit);return;}
    if(mode==='time'&&!result.atmosphere){presentStructuralTime(result,fit);return;}
    if(mode==='mounted'||mode==='rigid')condition=solvedFlightCondition(condition,result);
    equilibriumView.setComputed(mode==='mounted'?result.equilibrium_state:null);
    checkpointView.refresh();
    state.result={...result,condition,model:state.model.name};
    renderFlightOutput(result,condition,state.model);
    const map={cl:'CL',cd:'CD',cdi:'CDi','cdi-near':'CDi_near',cdbody:'CDbody',cdp:'CDp',cdam:'CDam',cdeng:'CDeng',cy:'CY',roll:'Cl',pitch:'Cm',yaw:'Cn',mach:'mach',efficiency:'efficiency'};
    for(const [id,key] of Object.entries(map)) $(id).textContent=outputNumber(result[key],id==='mach'?3:4);
    const trefftz=result.trefftz;
    const coefficientText=(value,digits=8)=>value==null?'Unavailable':value.toPrecision(digits);
    const circulation=result.circulation_discretization;
    $('circulation-note').hidden=!circulation?.beams.some(b=>b.representation==='fourier');
    $('circulation-note').textContent=circulation?`${circulation.independent_unknowns} circulation unknowns · ${circulation.lifting_panels} intervals · max flow defect ${Math.max(0,...result.circulation_local_residual.map(Math.abs)).toExponential(2)} × airspeed`:'';
    $('trefftz-note').hidden=!trefftz;
    $('trefftz-note').textContent=result.coefficient_normalization?.available===false?result.coefficient_normalization.reason:!trefftz?'':!trefftz.available?`Trefftz drag and efficiency unavailable: ${trefftz.reason}`:
      `Far wake: CLi = ${trefftz.CLi.toFixed(5)} · CYi = ${trefftz.CYi.toFixed(5)}${mode==='time'?' · frozen straight wake':''}`;
    const wakeSummary=fourierWakeSummary(trefftz,result.request?.fourier_wake_diagnostic===true);
    if(wakeSummary){$('trefftz-note').hidden=false;$('trefftz-note').textContent+=' '+wakeSummary;}
    $('residual').textContent=result.residual.toExponential(1);
    $('stalled').textContent=`${result.strips.filter(x=>x.stalled).length} / ${result.lifting_panels}`;
    $('result-state').textContent=mode==='time'?`Time response · t = ${result.time.toPrecision(5)} T`:result.analysis==='constrained_static'?'Converged · constrained equilibrium':mode==='mounted'?'Converged · mounted equilibrium':'Converged · rigid geometry'; $('result-state').classList.add('solved');
    $('mass').textContent=result.mass_properties.mass.toPrecision(5);
    $('deflection').textContent=result.max_displacement == null ? '—' : result.max_displacement.toPrecision(5);
    if(result.geometry) {
      if(mode!=='time'||fit)state.deformed=true; $('shape').hidden=false;
      $('shape').textContent=state.deformed?'Show jig':'Show deformed'; $('shape-label').textContent=state.deformed?'DEFORMED · 1×':'JIG SHAPE';
    }
    updateGeometry(fit);
    
    const structure=result.geometry ? `\nStructural nodes      ${result.structural_nodes}\nLoad steps            ${result.continuation_steps}\nMax deflection [L]    ${result.max_displacement.toPrecision(7)}\nMax rotation [deg]    ${result.max_rotation_deg.toPrecision(7)}\n\nSupport force [F]     ${result.support_force.map(x=>x.toFixed(5)).join(', ')}\nSupport moment [F·L]  ${result.support_moment.map(x=>x.toFixed(5)).join(', ')}\nForce balance [F]     ${result.force_balance.map(x=>x.toExponential(2)).join(', ')}\nMoment balance [F·L]  ${result.moment_balance.map(x=>x.toExponential(2)).join(', ')}\n\nEarth gravity is rotated into body axes. Deformation is shown at true scale.\nExport results for node rotations, element loads, and individual reactions.\n` : '';
    const mass=result.mass_properties;
    const inertiaReport=`\nMass [input M]        ${mass.mass.toPrecision(7)}\nCG [input L]          ${mass.cg?mass.cg.map(x=>x.toFixed(6)).join(', '):'undefined (zero mass)'}\nInertia at CG [M·L²]\n${mass.inertia_cg?mass.inertia_cg.map(row=>row.map(x=>x.toPrecision(7)).join('  ')).join('\n'):'undefined (zero mass)'}\n\nApparent-mass force [F]    ${result.apparent_force.map(x=>x.toFixed(5)).join(', ')}\nApparent-mass moment [F·L] ${result.apparent_moment.map(x=>x.toFixed(5)).join(', ')}\n`;
    const constraintReport=(result.operating_constraints?.length)?`\nOPERATING TARGETS\n${result.operating_constraints.map(c=>`${c.quantity==='minimum_control'?'Least-squares control effort':`${c.quantity}: ${c.actual.toPrecision(8)} (target ${c.target})`}\n  solved ${c.variable} = ${result.operating_values[c.variable].toPrecision(8)}`).join('\n')}\nRates and angular accelerations in exports use radians per input T and T².\n`:'';
    const engineReport=result.engines.length?`\nENGINES\n${result.engines.map((e,i)=>`${i+1}: control ${e.index}, type ${e.type}\n  thrust [F] ${e.thrust.toPrecision(7)}, torque about thrust axis [F·L] ${e.torque.toPrecision(7)}\n  onset speed [L/T] ${e.axial_velocity.toPrecision(7)}, wake increment [L/T] ${e.delta_velocity.toPrecision(7)}\n  jet ${e.jet_enabled?'enabled':'disabled'}${e.power_clipped?' · windmilling power limited to physical branch':''}`).join('\n')}\nEngine drag coefficient ${coefficientText(result.CDeng,7)}\n`:'';
    const strutReport=result.struts?.length?`\nAXIAL BRACES · ${result.strut_mode==='wire'?'TENSION ONLY':'TENSION AND COMPRESSION'}\n${result.struts.map((s,i)=>`${i+1}: beam ${s.beam}, t=${s.t}\n  tension [F] ${s.tension.toPrecision(7)}, strain ${s.strain.toPrecision(7)}${s.slack?' · slack':''}`).join('\n')}\n`:'';
    const report=document.createElement('pre'); report.textContent=`${result.analysis==='constrained_static'?'CONSTRAINED AEROELASTIC EQUILIBRIUM':mode==='mounted'?'MOUNTED AEROELASTIC EQUILIBRIUM':'RIGID STEADY ANALYSIS'}\n\nNormalized residual    ${result.residual.toExponential(5)}\nResidual evaluations  ${result.evaluations}\nAerodynamic panels    ${result.panels}\nPG Mach               ${result.mach.toFixed(6)}\n\nAero force [input F]    ${result.force.map(x=>x.toFixed(5)).join(', ')}\nAero moment [input F·L] ${result.moment.map(x=>x.toFixed(5)).join(', ')}\n${structure}${inertiaReport}${constraintReport}\n${result.limitations.join('\n\n')}`;
    report.textContent+=engineReport+strutReport+allocationReport(result.control_allocation)+customReport(result);
    if(result.coefficient_normalization?.available===false)report.textContent+='\n'+result.coefficient_normalization.reason+'\n';
    if(result.moment_origin&&result.moment_definitions){
      const reference=result.moment_definitions.reference;
      report.textContent+=`\nMOMENT REFERENCES · BODY AXES\nFile moment reference [input L]: ${reference.map(x=>x.toPrecision(7)).join(', ')}\nCm about file reference: ${coefficientText(result.Cm)}\nMoment about body origin [input F·L]: ${result.moment_origin.map(x=>x.toPrecision(8)).join(', ')}\nCm about body origin: ${coefficientText(result.Cm_origin)}\n`;
    }
    if(condition)report.textContent+=`\nSECTION STALL · ${condition.stall?'ENABLED':'DISABLED'}\nLeakage factor K_s: ${condition.stall_factor??40}\nTransition width delta_cl: ${condition.stall_width??0.05}\nBoth parameters are dimensionless; CLmin and CLmax come from the section properties.\n`;
    const circulationSolver=result.circulation_solver;
    if(circulationSolver?.method==='continuation')report.textContent+=`\nCIRCULATION SOLVE\nArclength continuation: ${circulationSolver.steps} accepted steps\nFinal regularization: ${circulationSolver.final_regularization}\nPhysical residual: ${circulationSolver.physical_residual.toExponential(5)}\n${circulationSolver.scope}\n`;
    if(circulation)report.textContent+='\nCIRCULATION DISCRETIZATION\n'+JSON.stringify(circulation,null,2)+'\n';
    if(result.aerodynamic_lag)report.textContent+=`\nAERODYNAMIC LAG · ${result.aerodynamic_lag.enabled?'ENABLED':'DISABLED'}\nCirculation: ${result.aerodynamic_lag.circulation}. Circulation-rate lift: ${result.aerodynamic_lag.circulation_rate_lift?'enabled':'disabled'}.\n${result.aerodynamic_lag.apparent_mass}\n`;
    if(result.section_output_definitions)report.textContent+='\nSECTION OUTPUT DEFINITIONS\n'+Object.entries(result.section_output_definitions).map(([k,v])=>k+': '+v).join('\n')+'\n';
    if(result.lifting_airflow){const a=result.lifting_airflow,m=a.maximum;report.textContent+=`\nLIFTING FORCE-POINT AIRFLOW\n${m?`Maximum normal Mach ${m.normal_mach.toPrecision(7)} at beam ${m.beam}, t=${m.t.toPrecision(7)}.\nNormal relative speed ${m.normal_speed.toPrecision(7)}; sound speed ${a.sound_speed.toPrecision(7)} [input L/T].\nBody force point [input L]: ${m.position.map(v=>v.toPrecision(7)).join(', ')}.\n`:'No lifting force-point samples.\n'}${a.scope}\n${a.sampling}\n${a.validity}\n`;}
    if(result.aerodynamic_influences){const a=result.aerodynamic_influences;report.textContent+=`\nAERODYNAMIC INFLUENCES · ${a.frozen?'FROZEN (K/F)':'CURRENT'}\nGeometry: ${a.geometry}; wind angles: ${a.wind_angles.join(', ')} deg; PG Mach: ${a.pg_mach}.\n${a.scope}\n${a.ground}\nAttached receivers: ${a.attached_receivers}. External receivers: ${a.external_receivers}.\n`;}
    if(result.wake_core)report.textContent+=`\nWAKE CORE · r/c = ${result.wake_core.ratio}\n${result.wake_core.rule}\n${result.wake_core.minimum_radius===null?'No lifting panels.':`Source radius [input L]: ${result.wake_core.minimum_radius.toPrecision(6)} to ${result.wake_core.maximum_radius.toPrecision(6)}. Interval width sets ${result.wake_core.spacing_limited_panels} panels.`}\n${result.wake_core.scope}\n`;
    if(trefftz)report.textContent+='\nTREFFTZ PLANE\n'+JSON.stringify(Object.fromEntries(
      ['available','reason','CLi','CYi','CDi','efficiency','Cl','rolling_moment_wind','convention','scope'].map(key=>[key,trefftz[key]])),null,2)+
      '\nCOEFFICIENT DEFINITIONS\n'+JSON.stringify(result.coefficient_definitions,null,2)+'\n';
    if(wakeSummary)report.textContent+='\nCONTINUOUS FOURIER WAKE CHECK\n'+wakeSummary+'\n'+(trefftz?.continuous_fourier?JSON.stringify(trefftz.continuous_fourier,null,2)+'\n':'');
    if(result.equilibrium_initialization)report.textContent+='\nEQUILIBRIUM INITIALIZATION\n'+JSON.stringify(result.equilibrium_initialization,null,2)+'\n';
    if(result.steady_trim?.operating_constraints.length){
      const trim=result.steady_trim;
      report.textContent+='\nCLOSED-LOOP BASE TRIM\n'+trim.operating_constraints.map(c=>
        (c.quantity==='minimum_control'?'Least-squares control effort':c.quantity+': '+c.actual.toPrecision(8)+' (target '+c.target+')')+'\n  solved '+c.variable+' = '+trim.operating_values[c.variable].toPrecision(8)).join('\n')+
        '\nThese trim targets are released in the dynamic response; solved commands stay fixed.\n';
    }
    const air=result.atmosphere;
    const referenceFlow=result.reference_flow;
    if(referenceFlow) {
      const number=x=>x===null?'undefined':x.toPrecision(8);
      report.textContent+=`\nREFERENCE AIRFLOW · INCLUDES LOCAL GUST\nBody reference [L] ${referenceFlow.reference_body.map(number).join(', ')}\nEarth reference [L] ${referenceFlow.reference_earth.map(number).join(', ')}\nRelative velocity, body axes [L/T] ${referenceFlow.relative_velocity_body.map(number).join(', ')}\nTrue local airspeed [L/T] ${number(referenceFlow.speed)}\nLocal alpha [deg] ${number(referenceFlow.alpha)}; beta [deg] ${number(referenceFlow.beta)}\nLocal equivalent airspeed [L/T] ${number(referenceFlow.equivalent_airspeed)}\nLocal dynamic pressure [F/L²] ${number(referenceFlow.dynamic_pressure)}\nEquivalent airspeed uses sqrt(density / file sea-level density). Induced flow and local elastic velocity are excluded.\n`;
    }
    report.textContent+=`\nATMOSPHERE\nGeometric altitude [m] ${air.altitude_m.toFixed(3)}\nGeopotential altitude [m] ${air.geopotential_altitude_m.toFixed(3)}\nTemperature [K] ${air.temperature_K.toFixed(4)}\nDensity [input M/L³] ${air.density.toPrecision(8)} (${air.density_source==='override'?'specified':'standard atmosphere'})\nSound speed [input L/T] ${air.sound_speed.toPrecision(8)}\n${result.gust?.type&&result.gust.type!=='none'?'Still-atmosphere reference speed':'True airspeed'} [input L/T] ${(result.operating_values?.speed??condition.speed).toPrecision(8)}\nEquivalent airspeed [input L/T] ${air.equivalent_airspeed.toPrecision(8)}\nDynamic pressure [input F/L²] ${air.dynamic_pressure.toPrecision(8)}\nAmbient Mach ${air.ambient_mach.toFixed(6)}; PG Mach ${result.mach.toFixed(6)}\nGravity magnitude [input L/T²] ${air.gravity_magnitude.toPrecision(8)}\nLift target multiplier N ${air.load_factor}\n`;
    if(result.gust?.type!=='none')report.textContent+=`\nEARTH GUST · ${result.gust.type}\nField time [T] ${result.gust.time}\nVelocity at reference, Earth [L/T] ${result.gust.reference_velocity_earth.map(x=>x.toPrecision(7)).join(', ')}\nVelocity at reference, body [L/T] ${result.gust.reference_velocity_body.map(x=>x.toPrecision(7)).join(', ')}\n`;
    if(result.body_shoulders?.length)report.textContent+=`\nBODY SHOULDERS · CONCENTRATED POTENTIAL FORCES\n${result.body_shoulders.map(s=>`Beam ${s.beam}, t=${s.t}: radius ${s.radius_left} → ${s.radius_right} [L], area jump ${s.area_jump.toPrecision(7)} [L²]\n  Position [L] ${s.position.map(x=>x.toPrecision(7)).join(', ')}\n  Force [F] ${s.force.map(x=>x.toPrecision(7)).join(', ')}`).join('\n')}\nWeak limits of concentric smooth transitions; no added blunt-face or separation drag. Forces are separate from distributed strip loads.\n`;
    report.textContent+=hingeReport(result.hinges);
    const earth=result.earth_state,ground=result.ground_plane;
    report.textContent+=`\nEARTH POSE\nPosition [L] ${earth.position.map(x=>x.toFixed(6)).join(', ')}\nBank, elevation, heading [deg] ${earth.attitude.map(x=>x.toFixed(6)).join(', ')}\nVelocity in Earth axes [L/T] ${earth.velocity_earth.map(x=>x.toFixed(6)).join(', ')}\nFlight path [deg] ${earth.flight_path.toFixed(6)}\n`;
    report.textContent+=`\nFLIGHT KINEMATICS\nVelocity reference [L] ${earth.velocity_reference.join(', ')}\nAcceleration reference [L] ${earth.acceleration_reference.join(', ')}\nBody velocity derivative [L/T²] ${earth.velocity_derivative_body.map(x=>x.toExponential(5)).join(', ')}\nAcceleration at velocity reference, Earth axes [L/T²] ${earth.acceleration_velocity_reference_earth.map(x=>x.toFixed(6)).join(', ')}\nBank, elevation, heading rates [deg/T] ${earth.attitude_rates?earth.attitude_rates.map(x=>(x*180/Math.PI).toFixed(6)).join(', '):'undefined at Euler elevation pole'}\nSpeed rate [L/T²] ${earth.speed_rate.toExponential(5)}\nRadial residual AY − UX WZ [L/T²] ${earth.radial_acceleration.toExponential(5)}\n`;
    if(result.gravity_body)report.textContent+=`Gravity in body axes [L/T²] ${result.gravity_body.map(x=>x.toFixed(6)).join(', ')}\n`;
    if(ground.flag)report.textContent+=`\nGROUND IMAGES · ${ground.flag===1?'SOLID PLANE':'CONSTANT-PRESSURE FREE SURFACE'}\nNormal in body axes ${ground.normal_body.map(x=>x.toFixed(6)).join(', ')}\nMinimum sampled clearance [L] ${ground.minimum_clearance.toPrecision(7)}\n`;
    if(state.model.beams.some(b=>!b.lifting)) report.textContent+=`\nBODY LOADS\nBody force [F] ${result.body_force.map(x=>x.toFixed(6)).join(', ')}\nApparent-mass coefficient: ${result.body_added_mass_factor===1?'cylinder potential flow':'ASWING printed coefficient (×2)'}\n`;
    $('pane-report').replaceChildren(report);
    if(result.derivatives) {
      const d=result.derivatives;
      report.textContent+=`\nCOUPLED DERIVATIVES\nResponse: ${d.response}; coefficient axes: ${d.axes}\nController: ${d.controller?'closed-loop equilibrium; solved commands held except the selected input':'none'}\nSystem size ${d.system_size}; derivative residual evaluations ${d.residual_evaluations}\nColumn-scaled reciprocal condition ${d.column_scaled_reciprocal_condition.toExponential(5)}\nMaximum linear residual ${Math.max(...d.linear_residuals).toExponential(5)}\n${d.limitations.join('\n')}\n`;

    }
    if(result.structure)report.textContent+=`\nSECTION RECOVERY\n${JSON.stringify(result.structure.summary,null,2)}\n${result.structure.limitations.join('\n')}\n`;
    if(state.trajectory) {
      const t=state.trajectory;
      report.textContent=`UNSTEADY TIME RESPONSE · t = ${result.time} input T\n${t.method}, ${t.frame_mode} frame; ${t.accepted_steps} accepted steps, ${t.rejected_steps} retries\nSnapshot step ${result.step}, order ${result.order}, forcing side ${result.forcing_side} · ${timePhase(result)}\nPrescribed table values ${JSON.stringify(result.forcing_values)}\n${t.limitations.join('\n')}\n${t.forcing.limitations.join('\n')}\n${timeInitializationSummary(t)}\n\n`+report.textContent.replace(/^(CONSTRAINED AEROELASTIC EQUILIBRIUM|RIGID STEADY ANALYSIS)/,'INSTANTANEOUS UNSTEADY STATE').replace(/Load steps\s+undefined/,'Initial load steps    '+t.continuation_steps);
    }
    renderPlot(); 
}

function refreshPlotAvailability() {
  const loading=Boolean(state.result?.strips?.length||state.result?.elements?.length);
  $('plot-beam').disabled=$('plot-quantity').disabled=!loading;
  workbenchView?.setAvailable({loading,modes:Boolean(state.modal?.modes?.length),time:Boolean(state.trajectory&&timeView.hasData()),
    frequency:Boolean(state.frequency?.samples?.some(sample=>sample.responses?.some(response=>response.output)))});
}

function renderPlot() {
  refreshPlotAvailability();
  const linear=state.frequency?frequencyView.spanState():state.modal?modeView.spanState():null;
  const target=$('plot'),selector=$('plot-quantity');
  const beam=Number($('plot-beam').value);
  const rows=(state.result?.strips??[]).filter(s=>s.beam===beam);
  selector.disabled=!rows.length&&!(state.result?.elements??[]).some(e=>e.beam===beam);
  const shoulders=(state.result?.body_shoulders??[]).filter(s=>s.beam===beam);
  const isBody=rows.length?!rows[0].lifting:state.model?.beams.find(b=>b.index===beam)?.lifting===false;
  for(const [key,q] of Object.entries(loadingQuantities))selector.querySelector(`option[value="${key}"]`).disabled=isBody&&Boolean(q.surface);
  for(const option of selector.querySelectorAll('option[value^="shoulder."]'))option.disabled=!shoulders.length;
  selector.querySelector('option[value="structure:distributed_gravity.normal"]').disabled=!(state.result?.elements??[]).some(e=>e.beam===beam&&Number.isFinite(e.distributed_gravity?.normal));
  const structureOnly=state.result?.structure&&!(state.result.strips?.length);
  if(structureOnly&&!selector.value.startsWith('structure:'))selector.value='structure:moment_axes.0';
  const structural=selector.value.startsWith('structure:');
  $('structure-details').hidden=!structural;
  $('structure-stress-unit').closest('label').hidden=true;
  for(const id of ['plot-title','plot-unit'])$(id).textContent='';
  if(structural){structureView.render(linear);return;}
  if(!state.result) { target.className='plot-empty'; target.textContent='Run an analysis to inspect span properties.'; return; }
  colorBeamPlot(target,state.model.beams,beam);
  if(selector.value.startsWith('shoulder.')&&!shoulders.length)selector.value='fz';
  if(!rows.length) { target.textContent='No aerodynamic data on this beam. Choose a structural property.'; return; }
  if(isBody && loadingQuantities[$('plot-quantity').value]?.surface) $('plot-quantity').value='fz';
  const quantity=$('plot-quantity').value;
  if(quantity.startsWith('shoulder.')){
    const axis=Number(quantity.split('.')[1]);
    $('plot-title').textContent=`Concentrated shoulder force ${'xyz'[axis]}`;
    $('plot-unit').textContent='input F · t';
    renderShoulders(shoulders,rows,axis,linear);
    return;
  }
  const q=loadingQuantities[quantity],value=row=>loadingValue(row,quantity);
  $('plot-title').textContent=q.title;
  $('plot-unit').textContent=q.unit+' · t';
  if(!rows.some(row=>value(row)!==null)){target.className='plot-empty';target.textContent='This property is unavailable in the selected result.';return;}
  const samples=linear?linearLoadingSamples(rows,linear,quantity):rows.map(row=>({t:row.t,value:value(row),stalled:row.stalled}));
  renderBeamDistribution(target,samples,{label:q.title,unit:q.unit,range:linear?spanRange(samples):null,
    hoverKey:`${beam}:${quantity}`,emptyMessage:linear?'No animated values in this result. Run the analysis again.':undefined});

}

function renderShoulders(shoulders,strips,axis,linear=null){
  const samples=linear?linearShoulderSamples(shoulders,linear,axis):shoulders.map(row=>({t:row.t,value:row.force[axis]}));
  renderBeamDistribution($('plot'),samples,{
    kind:'impulses',label:`Concentrated shoulder force ${'xyz'[axis]}`,unit:'input F',
    range:linear?spanRange(samples):null,hoverKey:`${$('plot-beam').value}:shoulder.${axis}`,
    emptyMessage:linear?'No animated values in this result. Run the analysis again.':undefined,
    domain:[...strips.map(row=>row.t),...shoulders.map(row=>row.t)]
  });
}

function variableOptions() {
  const entries=[['alpha','Angle of attack'],['beta','Sideslip'],['speed','Airspeed']];
  for(const [key,label] of motionGroups) for(const axis of ['x','y','z']) entries.push([`${key}.${axis}`,`${label} ${axis}`]);
  for(const axis of ['x','y','z'])entries.push([`position_earth.${axis}`,`Earth position ${axis}`]);
  for(const axis of ['bank','elevation','heading'])entries.push([`attitude.${axis}`,`Attitude ${axis}`]);
  for(const control of state.model?.controls??[]) entries.push([`control.${control}`,`Flap ${control}`]);
  for(const control of state.model?.engine_controls??[]) entries.push([`power.${control.index}`,`Engine ${control.index}`]);
  entries.push(...feedbackView.commands());
  return entries;
}

function refreshDerivativeParameters(preserve=false) {
  const previous=new Set([...document.querySelectorAll('#derivative-parameters input:checked')].map(input=>input.value));
  const parameters=$('derivative-basis').value==='standard'?['u','alpha','beta','p','q','r']:$('derivative-basis').value==='body_origin'?['origin_velocity.x','origin_velocity.y','origin_velocity.z','origin_rates.x','origin_rates.y','origin_rates.z']:['velocity.x','velocity.y','velocity.z','rates.x','rates.y','rates.z'];
  parameters.push(...(state.model?.controls??[]).map(k=>`control.${k}`),...(state.model?.engine_controls??[]).map(e=>`power.${e.index}`));
  const commands=feedbackView.commands().map(([name])=>name);
  const commandFor=key=>key.replace(/^control\./,'command.F').replace(/^power\./,'command.E');
  const available=[...parameters.filter(key=>!commands.includes(commandFor(key))),...commands];
  $('derivative-parameters').replaceChildren();
  for(const key of available) {
    const paired=/^command\.F\d+$/.test(key)?key.replace('command.F','control.'):/^command\.E\d+$/.test(key)?key.replace('command.E','power.'):commandFor(key);
    const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=key;input.checked=!preserve||previous.has(key)||previous.has(paired);
    input.onchange=resetResult;label.append(input,document.createTextNode(key));$('derivative-parameters').append(label);
  }
}
function fillVariables(select,value) {
  select.replaceChildren();
  const entries=variableOptions();
  if(!entries.some(([key])=>key===value)) entries.push([value,`${value} (not in model)`]);
  for(const [key,label] of entries) { const option=document.createElement('option'); option.value=key; option.textContent=label; select.append(option); }
  select.value=value;
}
function refreshConstraintVariables(preservePresets=false) {
  for(const select of document.querySelectorAll('.constraint-variable')) fillVariables(select,select.value);
  const controls=state.model?.controls??[], engines=(state.model?.engine_controls??[]).map(e=>e.index);
  for(const [key,entries,index] of [['roll',controls,1],['pitch',controls,0],['yaw',controls,2],['engine',engines,0]]) {
    const select=$(`trim-${key}`), previous=select.value; select.replaceChildren();
    for(const id of entries) {const option=document.createElement('option');option.value=id;option.textContent=`${key==='engine'?'Engine':'Flap'} ${id}`;select.append(option);}
    select.value=preservePresets&&entries.includes(Number(previous))?previous:String(entries[index]??entries[0]??'');
  }
  $('turn-trim').disabled=controls.length<3 || engines.length<1;
  allocationView.refresh(preservePresets);
  customView.refresh();
}
function readConstraints() {
  return [...$('constraint-rows').children].map(row=>({variable:row.querySelector('.constraint-variable').value,quantity:row.querySelector('.constraint-quantity').value,target:Number(row.querySelector('input').value),...allocationView.read(row.querySelector('.constraint-variable').value),...customView.read(row)}));
}
function addConstraint(c={variable:'alpha',quantity:'lift',target:0}) {
  const row=document.createElement('div'); row.className='constraint-row';
  const variable=document.createElement('select'); variable.className='constraint-variable'; variable.setAttribute('aria-label','Variable to solve'); fillVariables(variable,c.variable);
  const quantity=document.createElement('select'); quantity.className='constraint-quantity'; quantity.setAttribute('aria-label','Target quantity');
  const targets=[...['force','moment'].flatMap(key=>['x','y','z'].map(axis=>[`${key}.${axis}`,`${key==='force'?'Net force':'Net moment'} ${axis} [${key==='force'?'F':'F·L'}]`])),['lift','Specified lift (×N) [F]'],['equivalent_airspeed','Equivalent airspeed [L/T]'],['dynamic_pressure','Dynamic pressure [F/L²]'],...['CL','CY','CD','Cl','Cm','Cn'].map(key=>[key,`${key} coefficient`])];
  targets.push(['flight_path','Flight path [deg]'],['minimum_control','Least-squares control effort'],['user','Custom equation / sensor target']);
  for(const [key,label,unit] of [['speed','true airspeed','L/T'],['alpha','alpha','deg'],['beta','beta','deg'],['equivalent_airspeed','equivalent airspeed','L/T'],['dynamic_pressure','dynamic pressure','F/L²']])targets.push([`reference.${key}`,`Reference ${label} · includes gust [${unit}]`]);
  for(const [key,label,unit] of [['velocity_earth','Earth velocity','L/T'],['rates_earth','Earth rotation rate','rad/T'],['acceleration_earth','Earth acceleration','L/T²'],['angular_acceleration_earth','Earth angular acceleration','rad/T²']])for(const axis of ['x','y','z'])targets.push([`${key}.${axis}`,`${label} ${axis} [${unit}]`]);
  for(const axis of ['x','y','z'])targets.push([`velocity_derivative_body.${axis}`,`Body velocity derivative ${axis} [L/T²]`]);
  targets.push(['radial_acceleration','Radial AY − UX WZ [L/T²]'],['speed_rate','Speed rate [L/T²]']);
  for(const [key,label] of variableOptions()) {
    const unit=key.startsWith('command.')?'file units':key==='speed'?'L/T':key.startsWith('rates.')?'rad/T':key.startsWith('angular_acceleration.')?'rad/T²':key.startsWith('acceleration.')?'L/T²':key.startsWith('position_earth.')?'L':key.startsWith('control.')||key.startsWith('power.')?'setting':'deg';
    targets.push([key,`${label} [${unit}]`]);
  }
  for(const [key,label] of targets) {const option=document.createElement('option');option.value=key;option.textContent=label;quantity.append(option);} quantity.value=c.quantity.startsWith('user.')?'user':c.quantity;
  const value=document.createElement('input'); value.type='number'; value.step='any'; value.value=c.target; value.setAttribute('aria-label','Target value');
  const remove=document.createElement('button'); remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove constraint');remove.onclick=()=>{row.remove();allocationView.refresh();customView.refresh();resetResult();};
  const refresh=()=>{value.disabled=quantity.value==='minimum_control';if(value.disabled)value.value='0';allocationView.refresh();customView.refresh();};
  for(const field of [variable,quantity])field.addEventListener('input',()=>{refresh();resetResult();});
  value.addEventListener('input',resetResult);
  row.append(variable,quantity,value,remove);$('constraint-rows').append(row);allocationView.remember(c);customView.remember(row,c);refresh();resetResult();
}

$('open').onclick=()=>$('file').click();
const loadAircraft=createAircraftLoader({inspect,showError});
const loadAircraftFile=file=>loadAircraft(async()=>({source:await file.text(),filename:file.name}));
$('file').onchange=async e=>{
  const file=e.target.files[0];e.target.value='';
  if(file)await loadAircraftFile(file);
};
$('save').onclick=async()=>{await massView.ready();if(massView.hasDraft()){showError(new Error('Finish the mass-property edit before saving.'));return;}download(state.filename,state.dirty ? $('editor').value : state.source);};
$('example').onchange=()=>{
  const key=$('example').value;
  return loadAircraft(async()=>{
    const response=await fetch(`/examples/${key}.asw`);
    if(!response.ok)throw new Error('Example unavailable');
    return {source:await response.text(),filename:`${key}.asw`,example:key};
  });
};
$('solve').onclick=()=>run();
$('cancel').onclick=()=>{
  state.inspection++;resetResult();
  worker.terminate();
  for(const item of pending.values())item.reject(new Error('Analysis cancelled.'));
  pending.clear();toggleBusy(false);startWorker();
  inspect($('editor').value);
};
function refreshAnalysisVisibility(){
  const structural=$('mode').value==='structural',quiescent=quiescentSelected(),sourceVacuum=sourceVacuumSelected(),sourceStillAir=sourceStillAirSelected(),sourceMoving=sourceMovingVacuumSelected(),sourceAirflow=sourceAirflowSelected(),noFlow=quiescent||sourceVacuum||sourceStillAir||sourceMoving,model=state.model;
  $('structural-settings').hidden=!structural;
  $('static-weight-note').hidden=!structural||!(model?.signed_point_weights?.length||model?.signed_distributed_weights?.length);
  for(const id of ['speed','alpha','beta'])$(id).closest('label').hidden=structural||noFlow;
  for(const id of ['control-input-settings','controls','powers','gust-settings','stall-settings'])$(id).hidden=structural||noFlow;
  $('motion-settings').hidden=structural||(noFlow&&!sourceMoving);
  $('moving-velocity-settings').hidden=!sourceMoving;
  $('time-actuator-settings').hidden=(sourceMoving||sourceAirflow)&&!$('time-actuators').value.trim();
  $('forcing-pulse').hidden=sourceMoving;
  for(const id of ['atmosphere-settings','ground-settings'])$(id).hidden=structural;
  for(const id of ['atmosphere-flow-settings','atmosphere-aero-settings','pose-ground-normal','level-attitude'])$(id).hidden=noFlow;
  $('ground-effect').hidden=noFlow;document.querySelector('label[for="ground-effect"]').hidden=noFlow;
  $('atmosphere-summary').textContent=noFlow?'Gravity':'Atmosphere, gravity & lift factor';
  $('ground-summary').textContent=noFlow?'Earth pose':'Earth pose & ground effect';
  $('ground-note').textContent=noFlow?'Earth position and attitude are retained. Gravity follows aircraft attitude. Aerodynamic ground images are unavailable for this analysis.':'The plane passes through the Earth origin. Keep the aircraft above it. Gravity follows the aircraft attitude even with images off. The solved view shows the plane.';
  $('modal-quiescent-density-field').hidden=!quiescent;
  ($('mode').value==='frequency'&&sourceStillAir?$('frequency-fluid-slot'):$('modal-fluid-slot')).append($('quiescent-fluid-settings'));
  $('frequency-frame').disabled=sourceVacuum||sourceStillAir;
  for(const option of $('frequency-inputs').options)option.disabled=(sourceVacuum||sourceStillAir||sourceMoving)&&!(option.value==='initial'||(sourceMoving&&$('frequency-frame').value!=='fixed'&&option.value==='frame'));
  $('frequency-gust-settings').hidden=!['all','gust'].includes($('frequency-inputs').value)||noFlow;
  $('modal-frame').disabled=quiescent||sourceStillAir;
  $('modal-vacuum').disabled=$('modal-quiescent').disabled=state.busy;
  // Preserve the ordinary frame even while another analysis tab is active.
  // Saved settings assign both fields before events, so never capture the
  // temporary fixed display as the previous frame during a case restore.
  $('modal-frame').value=noFlow&&!sourceMoving?'fixed':$('modal-ordinary-frame').value;
  $('modal-load-settings').hidden=$('modal-quiescent').checked||$('modal-frame').value!=='mixed';
  $('feedback-settings').hidden=!['mounted','time','modes','frequency'].includes($('mode').value)||noFlow;
  $('stall').closest('label').hidden=structural||noFlow;
  $('circulation-settings').hidden=structural||noFlow||!model?.beams.some(b=>b.lifting);
  $('fourier-wake-settings').hidden=$('mode').value!=='rigid';
  $('sensor-settings').hidden=structural||noFlow||!model?.sensors.length;
  $('static-gravity-fields').hidden=$('static-gravity-mode').value!=='custom';
}
function selectedAnalysisDefaults(){
  return analysisStructuralSelection($('mode').value,{
    vacuum:$('modal-vacuum').checked,stillAir:$('modal-quiescent').checked,
    frame:$('modal-ordinary-frame').value
  });
}
async function changeAnalysisMode({modelImport=false}={}){
  let next=structuralSelection;
  if(!state.restoring){
    try{next=selectedAnalysisDefaults();}
    catch(error){$('mode').value=previousAnalysisMode;refreshAnalysisVisibility();showError(error);return;}
  }
  const resetPolicy=next!==structuralSelection;
  // A newly imported model replaces the previous model's drafts.
  if(resetPolicy&&(state.busy||(!modelImport&&(state.dirty||nodeView.hasDraft()||distributionView.hasDraft()||massView.hasDraft())))){
    $('mode').value=previousAnalysisMode;
    $('modal-vacuum').checked=sourceVacuumSelected()||sourceMovingVacuumSelected();
    $('modal-quiescent').checked=sourceStillAirSelected();
    equilibriumView.refresh();refreshAnalysisVisibility();
    showError(new Error('Finish the analysis and apply model edits before changing analysis type.'));return;
  }
  if(resetPolicy){structuralSelection=next;equilibriumView.restore({state:null,enabled:false,label:''});}
  previousAnalysisMode=$('mode').value;
  configureSourceFrequencyInputs();resetResult();
  refreshAnalysisVisibility();
  $('derivative-settings').hidden=$('mode').value!=='mounted';
  $('time-settings').hidden=$('mode').value!=='time';
  $('mode-settings').hidden=$('mode').value!=='modes';
  $('frequency-settings').hidden=$('mode').value!=='frequency';
  if(resetPolicy&&state.source){await inspect(state.source,state.filename,'',null,true);if(!state.dirty)status('Analysis ready');}
}
$('mode').onchange=()=>changeAnalysisMode();
function configureSourceFrequencyInputs(){
  if(state.restoring||$('mode').value!=='frequency'||!(sourceVacuumSelected()||sourceStillAirSelected()||sourceMovingVacuumSelected()))return;
  if(!sourceMovingVacuumSelected())$('frequency-frame').value='fixed';
  const allowed=['initial',...(sourceMovingVacuumSelected()&&$('frequency-frame').value!=='fixed'?['frame']:[])];
  if(!allowed.includes($('frequency-inputs').value))$('frequency-inputs').value=allowed.at(-1);
}
$('frequency-frame').addEventListener('change',()=>{configureSourceFrequencyInputs();refreshAnalysisVisibility();});
$('static-gravity-mode').onchange=()=>{refreshAnalysisVisibility();resetResult();};
for(const a of ['x','y','z'])$(`static-gravity-${a}`).addEventListener('input',resetResult);
$('sensor-flow').addEventListener('input',resetResult);
$('aero-lag').addEventListener('input',resetResult);
$('freeze-influences').addEventListener('input',resetResult);
$('fourier-wake-diagnostic').addEventListener('input',resetResult);
$('wake-core-ratio').addEventListener('input',resetResult);
for(const id of ['stall-factor','stall-width'])$(id).addEventListener('input',resetResult);
$('modal-frame').addEventListener('input',()=>{
  if(!$('modal-quiescent').checked)$('modal-ordinary-frame').value=$('modal-frame').value;
  if(!state.restoring&&$('mode').value==='modes')void changeAnalysisMode();
});
for(const id of ['modal-vacuum','modal-quiescent'])$(id).addEventListener('change',()=>{
  if($(id).checked)$(id==='modal-vacuum'?'modal-quiescent':'modal-vacuum').checked=false;
  void changeAnalysisMode();equilibriumView.refresh();
});
$('add-constraint').onclick=()=>addConstraint();
$('reference-airflow').onclick=async()=>{
  if(state.busy || !state.model || state.dirty)return;
  for(const id of ['speed','alpha','beta'])if(!$(id).value || !$(id).checkValidity()){$(id).reportValidity();return;}
  const revision=state.revision;
  const preset=Object.fromEntries(['speed','alpha','beta'].map(id=>[id,Number(fieldValue($(id)))]));
  toggleBusy(true);$('error').hidden=true;
  try {
    const constraints=await rpc({action:'reference_airflow_constraints',source:state.source,preset});
    if(revision!==state.revision)return;
    $('constraint-rows').replaceChildren();for(const constraint of constraints)addConstraint(constraint);
  }catch(error){if(revision===state.revision)showError(error);}finally{toggleBusy(false);}
};
$('clear-constraints').onclick=()=>{$('constraint-rows').replaceChildren();allocationView.refresh();customView.refresh();resetResult();};
$('free-flight').onclick=()=>{
  $('constraint-rows').replaceChildren();
  for(const [variable,quantity] of [['acceleration','force'],['angular_acceleration','moment']])
    for(const axis of ['x','y','z']) addConstraint({variable:`${variable}.${axis}`,quantity:`${quantity}.${axis}`,target:0});
};
async function applyTurnPreset(fullTrim) {
  if(state.busy || !state.model || state.dirty)return;
  for(const id of ['turn-rate','turn-path']) if(!$(id).value || !$(id).checkValidity()) {$(id).reportValidity();return;}
  const revision=state.revision;
  const preset={heading_rate:Number($('turn-rate').value)*Math.PI/180,flight_path:Number($('turn-path').value)};
  if(fullTrim)Object.assign(preset,{trim_controls:['roll','pitch','yaw'].map(key=>Number($(`trim-${key}`).value)),engine_control:Number($('trim-engine').value)});
  toggleBusy(true); $('error').hidden=true;
  try {
    const constraints=await rpc({action:'steady_turn_constraints',source:state.source,preset});
    if(revision!==state.revision)return;
    $('constraint-rows').replaceChildren(); for(const constraint of constraints)addConstraint(constraint);
  } catch(error) {if(revision===state.revision)showError(error);} finally {toggleBusy(false);}
}
$('turn-kinematics').onclick=()=>applyTurnPreset(false);
$('turn-trim').onclick=()=>applyTurnPreset(true);
for(const id of ['derivatives-enable','derivative-response','derivative-axes','derivative-step'])$(id).addEventListener('input',resetResult);
$('derivative-basis').onchange=()=>{refreshDerivativeParameters();resetResult();};
for(const [key] of motionGroups) for(const axis of ['x','y','z']) $(`${key}-${axis}`).addEventListener('input',resetResult);
for(const axis of ['x','y','z'])$(`moving-velocity-${axis}`).addEventListener('input',resetResult);
let altitudeUnit=1000;
$('altitude-unit').onchange=()=>{
  const next=Number($('altitude-unit').value);
  $('altitude').value=Number($('altitude').value)*altitudeUnit/next;
  $('altitude').min=-5000/next; $('altitude').max=86000/next; altitudeUnit=next;
};
for(const [selector,field,choice] of [['density-mode','density-field','custom'],['gravity-mode','gravity-field','custom'],['mach-mode','mach-field','fixed']]) $(selector).onchange=()=>{$(field).hidden=$(selector).value!==choice;resetResult();};
for(const id of ['altitude','density','gravity-magnitude','pg-mach','load-factor'])$(id).addEventListener('input',resetResult);
for(const [key,,,axes] of poseGroups)for(const axis of axes)$(`${key}-${axis}`).addEventListener('input',resetResult);
$('ground-effect').addEventListener('change',resetResult);
$('level-attitude').onclick=()=>{$('attitude-bank').value='0';$('attitude-elevation').value=$('alpha').value;resetResult();};
$('shape').onclick=()=>{
  if(!state.result?.geometry)return;
  state.deformed=!state.deformed;
  updateGeometry(false);
  $('shape').textContent=state.deformed?'Show jig':'Show deformed';
  $('shape-label').textContent=state.deformed?'DEFORMED · 1×':'JIG SHAPE';
};
for(const id of ['speed','alpha','beta','stall']) $(id).addEventListener('input',resetResult);
$('editor').addEventListener('input',()=>{resetResult();state.inspection++;state.dirty=true;distributionView.refresh();massView.refresh();nodeView.refresh();steadyProgressView?.refresh();$('solve').disabled=true;status('Editor changed · apply edits to update geometry');});
$('apply').onclick=()=>inspect($('editor').value);
$('plot-beam').onchange=renderPlot;
$('plot-quantity').onchange=renderPlot;
$('structure-stress-unit').onchange=renderPlot;
let loadingPlotWidth=0;
new ResizeObserver(entries=>{
  const width=entries[0].contentRect.width;
  if(width!==loadingPlotWidth){loadingPlotWidth=width;if(width>0)renderPlot();}
}).observe($('plot'));
$('fit').onclick=()=>viewer?.fit(); $('top-view').onclick=()=>viewer?.fit('top'); $('front-view').onclick=()=>viewer?.fit('front'); $('grid').onclick=()=>viewer?.toggleGrid();
workbenchView=createResponsiveWorkbench({onLeavePlots:()=>{timeView.pause();modeView.pause();frequencyView.pause();}});
refreshPlotAvailability();
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();run();}});
$('close-error').onclick=()=>$('error').hidden=true;
document.addEventListener('dragover',e=>e.preventDefault());
document.addEventListener('drop',async e=>{e.preventDefault();const file=e.dataTransfer.files[0];if(file)await loadAircraftFile(file);});
steadyFlightView=createSteadyFlight({getState:()=>state,capture:captureCase,load:loadCase,run,accept:acceptFlightTrim,showError});
// Draw the preview and inspect the bundled input without a separate fetch.
// The preview is display-only; normal inspection still owns the model and mesh.
if($('example').value==='dae'){
  const beams=daedalusPreview.beams.map(beam=>({
    ...beam,quads:beam.streamwise_quads??beam.quads,
  }));
  viewer.update(beams,daedalusPreview.attachments);
  startupPreviewVisible=true;
  $('geometry-label').textContent=daedalusPreview.name;
  loadAircraft(()=>({source:daedalusSource,filename:'dae.asw',example:'dae'}));
} else {
  $('example').onchange();
}

// Load the same widget as VibeFoil after the workbench is ready. The repository
// link remains usable if the widget cannot be downloaded.
if(navigator.onLine){
  const loadStarButton=()=>{
    const script=document.createElement('script');
    script.src='https://buttons.github.io/buttons.js';
    script.async=true;
    document.head.append(script);
  };
  if(document.readyState==='complete')setTimeout(loadStarButton,0);
  else window.addEventListener('load',loadStarButton,{once:true});
}
