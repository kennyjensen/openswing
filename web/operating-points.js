import {plotAxis} from './frequency-axes.js';
import {plotColors} from './plot-colors.js';

export const MAX_OPERATING_POINTS = 200;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const numberToken = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;
const coefficients = ['CL', 'CD', 'CDi', 'Cm', 'CDi_near', 'CDp', 'CLi', 'CYi', 'efficiency'];
const plots = [
  {key:'CL', title:'Lift coefficient'},
  {key:'CD', title:'Drag coefficient'},
  {key:'CDi', title:'Induced drag coefficient · Trefftz'},
  {key:'Cm', title:'Pitching moment coefficient'},
];

/** Explicit angles in degrees, in the entered order; no range expansion or sorting. */
export function parseOperatingPointAngles(text) {
  const input = String(text ?? '').trim();
  if (!input) throw new Error('Enter at least one angle of attack in degrees.');
  if (input.length > 20000) throw new Error('The angle list is too long. Enter at most 200 finite angles.');
  if (/^,|,$|,\s*,/.test(input)) throw new Error('An angle is missing between commas.');
  const tokens = input.split(/[,\s]+/);
  if (tokens.length > MAX_OPERATING_POINTS)
    throw new Error(`Enter at most ${MAX_OPERATING_POINTS} angles per run.`);
  return tokens.map((token, index) => {
    const value = Number(token);
    if (!numberToken.test(token) || !finite(value))
      throw new Error(`Angle ${index + 1} (${token}) must be a finite number in degrees.`);
    return value;
  });
}

function errorMessage(error) {
  if (typeof error === 'string') return error;
  if (error?.message) return String(error.message);
  if (error?.type) return String(error.type);
  return error ? JSON.stringify(error) : '';
}

/** Keep every requested row. A failed/absent solve never becomes a zero coefficient. */
export function operatingPointRows(sweep) {
  return (sweep?.points ?? []).map((point, position) => {
    const success = point.converged === true && !!point.result;
    const requestedAlpha = finite(point.condition?.alpha) ? point.condition.alpha : null;
    const actualAlpha = success && finite(point.actual_condition?.alpha) ? point.actual_condition.alpha : null;
    const values = Object.fromEntries(coefficients.map(key => {
      const value = point.result?.[key] ?? (['CLi', 'CYi'].includes(key) ? point.result?.trefftz?.[key] : null);
      return [key, success && finite(value) ? value : null];
    }));
    return {
      index:point.index ?? position, name:point.name ?? `Point ${position + 1}`,
      requestedAlpha, actualAlpha,
      // An absent actual condition is permitted by the older steady-result schema.
      plotAlpha:actualAlpha ?? requestedAlpha,
      success, error:success ? '' : errorMessage(point.error) || 'No converged result returned.',
      values, point,
    };
  });
}

/** Separate paths at failures and unavailable values; repeated/nonmonotone angles stay in order. */
export function operatingPointSegments(sweep, key) {
  const segments = [];
  let current = [];
  for (const row of operatingPointRows(sweep)) {
    if (row.success && finite(row.plotAlpha) && finite(row.values[key])) {
      current.push({alpha:row.plotAlpha, value:row.values[key], index:row.index});
    } else if (current.length) {
      segments.push(current); current = [];
    }
  }
  if (current.length) segments.push(current);
  return segments;
}

const csvLine = values => values.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',');
const jsonCell = value => value == null ? '' : JSON.stringify(value);

export function operatingPointsCSV(sweep) {
  const header = ['index', 'name', 'requested_alpha_deg', 'actual_alpha_deg', 'plot_alpha_deg',
    'mode', 'status', 'error_type', 'error', ...coefficients, 'residual',
    'condition_json', 'actual_condition_json', 'operating_constraints_json', 'initialization_json', 'request_json'];
  const rows = operatingPointRows(sweep).map(row => csvLine([
    row.index, row.name, row.requestedAlpha, row.actualAlpha, row.plotAlpha,
    sweep?.mode, row.success ? 'converged' : 'failed', row.point.error?.type, row.error,
    ...coefficients.map(key => row.values[key]),
    row.success && finite(row.point.result?.residual) ? row.point.result.residual : null,
    jsonCell(row.point.condition), jsonCell(row.point.actual_condition),
    jsonCell(row.point.operating_constraints), jsonCell(row.point.initialization), jsonCell(sweep?.request),
  ]));
  return [csvLine(header), ...rows].join('\r\n') + '\r\n';
}

export function operatingPointsJSON(sweep) {
  return JSON.stringify(sweep, null, 2) + '\n';
}

const fmt = value => finite(value) ? Number(value.toPrecision(7)).toString() : '—';

export function operatingPointStart(point) {
  const start = point.initialization;
  if (!start || start.kind === 'cold') return 'Independent';
  return `Point ${start.source_index + 1}${start.cold_fallback ? ' → independent retry' : ''}`;
}

/** Mount the steady polar UI. run(points) returns the full sweep (including request provenance). */
export function createOperatingPointsView({run, inspect, download}) {
  const pane = document.getElementById('pane-operating-points');
  if (!pane) throw new Error('Missing #pane-operating-points container.');
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const button = (id, text) => {
    const node = element('button', text); node.id = id; node.type = 'button'; return node;
  };
  const intro = element('p', 'Run steady operating points using the current Settings. Inspect a successful point to view its aircraft loads and output.', 'small muted');
  const controls = element('div', null, 'operating-points-controls');
  const label = element('label', 'Angles of attack [deg]');
  const input = element('input'); input.id = 'operating-points-values'; input.type = 'text';
  input.value = '-2, 0, 2, 4, 6, 8'; input.autocomplete = 'off'; input.spellcheck = false;
  input.setAttribute('aria-describedby', 'operating-points-hint');
  label.htmlFor = input.id; label.append(input);
  const hint = element('p', 'Separate angles with commas or spaces; up to 200 finite values. Repeated angles and the entered order are preserved.', 'small muted');
  hint.id = 'operating-points-hint';
  const startLabel = element('label', 'Starting solution');
  const start = element('select'); start.id = 'operating-points-initialization';
  for (const [value, text] of [['cold', 'Independent starts'], ['previous', 'Continue from previous point']]) {
    const option = element('option', text); option.value = value; start.append(option);
  }
  startLabel.htmlFor = start.id; startLabel.append(start);
  const startHint = element('p', 'Continuation starts from the preceding converged point and solves again at the new settings. The first point and points after a failure start independently. Near stall or a fold, the two choices may reach different solutions.', 'small muted');
  startHint.id = 'operating-points-initialization-hint'; start.setAttribute('aria-describedby', startHint.id);
  const toolbar = element('div', null, 'time-toolbar');
  const runButton = button('operating-points-run', 'Run steady polar'); runButton.className = 'primary';
  const csvButton = button('operating-points-csv', 'Polar CSV');
  const jsonButton = button('operating-points-json', 'Polar JSON');
  toolbar.append(runButton, csvButton, jsonButton); controls.append(label, hint, startLabel, startHint, toolbar);
  const status = element('p', null, 'small muted'); status.id = 'operating-points-status'; status.setAttribute('aria-live', 'polite');
  const error = element('p'); error.id = 'operating-points-error'; error.setAttribute('role', 'alert'); error.hidden = true;
  const results = element('div'); results.id = 'operating-points-results'; results.hidden = true;
  const plotNote = element('p', 'Plots use solved angles when available, otherwise the requested angles. Lines follow the entered order and stop at failed points or unavailable coefficients.', 'small muted');
  const plotGrid = element('div', null, 'operating-points-plots'); plotGrid.id = 'operating-points-plots';
  const canvases = plots.map(({key, title}) => {
    const figure = element('figure', null, 'operating-points-chart');
    figure.append(element('figcaption', `${key} · ${title}`));
    const canvas = element('canvas'); canvas.id = `operating-points-plot-${key}`;
    canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `${title} versus angle of attack. Numerical values are in the operating points table.`);
    canvas.style.width = '100%'; canvas.style.height = '230px';
    figure.append(canvas); plotGrid.append(figure); return canvas;
  });
  const wrap = element('div', null, 'derivative-table-wrap');
  const table = element('table'); table.id = 'operating-points-table';
  table.append(element('caption', 'Steady operating points · coefficients are dimensionless'));
  const head = element('thead'), headings = element('tr');
  for (const text of ['Point', 'Requested α [deg]', 'Solved α [deg]', 'CL', 'CD', 'CDi', 'Cm', 'Starting solution', 'Status', 'Inspect']) {
    const cell = element('th', text); cell.scope = 'col'; headings.append(cell);
  }
  head.append(headings); const body = element('tbody'); table.append(head, body); wrap.append(table);
  results.append(plotNote, plotGrid, wrap); pane.replaceChildren(intro, controls, status, error, results);
  let result = null, externalBusy = false, pending = false, revision = 0;
  const busy = () => externalBusy || pending;
  function buttons() {
    runButton.disabled = busy(); input.disabled = busy(); start.disabled = busy();
    csvButton.disabled = busy() || !result; jsonButton.disabled = busy() || !result;
    for (const node of body.querySelectorAll('button')) node.disabled = busy();
    pane.setAttribute('aria-busy', String(busy()));
  }
  function showError(value) { error.textContent = errorMessage(value); error.hidden = !error.textContent; }
  function summary() {
    if (busy()) { status.textContent = 'Solving steady operating points…'; return; }
    if (!result) { status.textContent = 'Enter angles, then run a steady polar.'; return; }
    const rows = operatingPointRows(result), successful = rows.filter(row => row.success).length;
    status.textContent = `${successful}/${rows.length} points converged; ${rows.length - successful} failed. Failed points remain in the table and exports.`;
  }
  function draw(canvas, key, color) {
    const width = canvas.getBoundingClientRect().width;
    if (!width) return; // Hidden tab; ResizeObserver or resize() draws it when shown.
    const height = 230, ratio = Math.min(3, window.devicePixelRatio || 1);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext('2d'); if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, width, height);
    const segments = operatingPointSegments(result, key);
    const xAxis = plotAxis(operatingPointRows(result).map(row => row.plotAlpha));
    const yAxis = plotAxis(segments.flatMap(segment => segment.map(point => point.value)));
    const left = 70, right = Math.max(left + 1, width - 18), top = 15, bottom = height - 42;
    const x = value => left + (right - left) * xAxis.position(value);
    const y = value => bottom - (bottom - top) * yAxis.position(value);
    ctx.font = '10px "IBM Plex Mono", monospace'; ctx.lineWidth = 1;
    ctx.textBaseline = 'middle'; ctx.fillStyle = '#829796';
    for (const tick of yAxis.ticks) {
      ctx.strokeStyle = tick.value === 0 ? '#54795f' : '#253930';
      ctx.beginPath(); ctx.moveTo(left, y(tick.value)); ctx.lineTo(right, y(tick.value)); ctx.stroke();
      ctx.textAlign = 'right'; ctx.fillText(Number(tick.value.toPrecision(4)).toString(), left - 8, y(tick.value), left - 12);
    }
    const stride = Math.max(1, Math.ceil(xAxis.ticks.length / Math.max(2, Math.floor((right - left) / 65))));
    xAxis.ticks.forEach((tick, index) => {
      ctx.strokeStyle = tick.value === 0 ? '#54795f' : '#253930';
      ctx.beginPath(); ctx.moveTo(x(tick.value), top); ctx.lineTo(x(tick.value), bottom); ctx.stroke();
      if (index % stride === 0) { ctx.textAlign = 'center'; ctx.fillText(Number(tick.value.toPrecision(4)).toString(), x(tick.value), bottom + 15, 65); }
    });
    ctx.textAlign = 'center'; ctx.fillText('Angle of attack [deg]', (left + right) / 2, height - 8);
    if (!segments.length) { ctx.fillText('No successful values', (left + right) / 2, (top + bottom) / 2); return; }
    ctx.save(); ctx.beginPath(); ctx.rect(left, top, right - left, bottom - top); ctx.clip();
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
    for (const segment of segments) {
      ctx.beginPath();
      segment.forEach((point, index) => index ? ctx.lineTo(x(point.alpha), y(point.value)) : ctx.moveTo(x(point.alpha), y(point.value)));
      ctx.stroke();
      for (const point of segment) { ctx.beginPath(); ctx.arc(x(point.alpha), y(point.value), 3, 0, 2 * Math.PI); ctx.fill(); }
    }
    ctx.restore();
  }
  function resize() { if (result) canvases.forEach((canvas, index) => draw(canvas, plots[index].key, plotColors[index])); }
  function setResult(value) {
    if (!value || value.analysis !== 'operating_points' || !Array.isArray(value.points))
      throw new Error('Expected an operating-points result.');
    result = value; results.hidden = false; body.replaceChildren(); showError(null);
    const sweep = value;
    for (const row of operatingPointRows(value)) {
      const tr = element('tr'); tr.dataset.pointIndex = row.index;
      for (const text of [row.name, fmt(row.requestedAlpha), fmt(row.actualAlpha),
        ...plots.map(({key}) => fmt(row.values[key]))])
        tr.append(element('td', text));
      const startCell = element('td', operatingPointStart(row.point));
      startCell.title = row.point.initialization?.reason ?? 'Independent point requested.';
      tr.append(startCell, element('td', row.success ? 'Converged' : `Failed: ${row.error}`));
      const cell = element('td');
      if (row.success) {
        const control = button('', 'Inspect'); control.setAttribute('aria-label', `Inspect ${row.name}`);
        control.onclick = async () => { try { await inspect(sweep, row.index); } catch (problem) { showError(problem); } };
        cell.append(control);
      } else cell.textContent = '—';
      tr.append(cell); body.append(tr);
    }
    summary(); buttons(); resize();
  }
  function clear() {
    revision++; result = null; results.hidden = true; body.replaceChildren();
    showError(null); summary(); buttons();
  }
  function setBusy(value) { externalBusy = !!value; buttons(); summary(); }
  runButton.onclick = async () => {
    if (busy()) return;
    let angles;
    try { angles = parseOperatingPointAngles(input.value); } catch (problem) { showError(problem); input.focus(); return; }
    const current = ++revision;
    pending = true; result = null; results.hidden = true; body.replaceChildren(); showError(null); buttons(); summary();
    try {
      const points = angles.map(alpha => ({name:`α = ${alpha}°`, condition:{alpha}}));
      const value = await run(points, start.value);
      if (revision === current && value) setResult(value);
    } catch (problem) { if (revision === current) showError(problem); }
    finally { pending = false; buttons(); summary(); }
  };
  input.addEventListener('input', clear);
  start.addEventListener('change', clear);
  input.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); runButton.click(); } });
  csvButton.onclick = () => { if (result) download('openswing-operating-points.csv', operatingPointsCSV(result), 'text/csv;charset=utf-8'); };
  jsonButton.onclick = () => { if (result) download('openswing-operating-points.json', operatingPointsJSON(result), 'application/json'); };
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
  observer?.observe(plotGrid); clear();
  return {setResult, clear, setBusy, resize, capture:() => result ? structuredClone(result) : null,
    destroy:() => { revision++; observer?.disconnect(); }};
}
