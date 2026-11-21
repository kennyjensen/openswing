// ASW tokens use the same palette as VibeLattice; the textarea owns editing.
const blocks = new Set('name unit units constant reference ground beam weight sensor engine strut joint jangle end'.split(' '));
const fields = new Set(('t x y z chord twist EIcc EInn EIcn EIcs EIsn GJ EA GKc GKn '+
  'mgcc mgnn mg Ccg Ncg Dmgcc Dmgnn Dmg DCcg DNcg Cea Nea Cta Nta tdeps tdgam '+
  'Cshell Nshell Atshell radius Cdf Cdp alpha Cm Xax CLmax CLmin dCLda').toLowerCase().split(' '));
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const span = (kind, value) => `<span class="asw-token-${kind}">${escape(value)}</span>`;

export function highlightAsw(source) {
  let block = '', beamName = false;
  return source.split('\n').map(line => {
    // Names retain embedded #/%; whole-line comments still take precedence.
    const nameLine = block === 'name' || beamName;
    const offset = line.search(nameLine && !/^\s*[#%]/.test(line) ? /!/ : /[!#%]/);
    const code = offset < 0 ? line : line.slice(0, offset);
    const comment = offset < 0 ? '' : span('comment', line.slice(offset));
    const first = code.trim().split(/\s+/)[0]?.toLowerCase();
    if (!first) return escape(code)+comment;
    let text = false;
    if (first === 'end') { block = ''; beamName = false; }
    else if (!block) { block = first; beamName = first === 'beam'; }
    else if (block === 'name' || beamName) { text = true; beamName = false; }
    if (text) return span('string', code)+comment;
    const tokens = /"[^"\n]*"|'[^'\n]*'|[A-Za-z_][A-Za-z_0-9]*|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?|[=,:()+*/-]/g;
    let html = '', end = 0;
    for (const match of code.matchAll(tokens)) {
      const token = match[0], lower = token.toLowerCase();
      html += escape(code.slice(end, match.index));
      const kind = /^['"]/.test(token) ? 'string' : /^[-+\d.]/.test(token) && /\d/.test(token) ? 'number' :
        blocks.has(lower) || (block === 'beam' && fields.has(lower)) || /^dC[LMD]dF[1-9]\d*$/i.test(token) ||
        ((block === 'unit' || block === 'units') && /^[LTFM]$/.test(token)) ? 'keyword' : null;
      html += kind ? span(kind, token) : escape(token);
      end = match.index+token.length;
    }
    return html+escape(code.slice(end))+comment;
  }).join('\n');
}

export function createAswEditor(textarea, highlight) {
  const sync = () => {
    highlight.style.width = `${textarea.clientWidth}px`;
    highlight.style.height = `${textarea.clientHeight}px`;
    highlight.scrollTop = textarea.scrollTop;
    highlight.scrollLeft = textarea.scrollLeft;
  };
  const refresh = () => {
    // The final space retains the caret's otherwise-empty last line.
    highlight.innerHTML = highlightAsw(textarea.value)+' ';
    sync();
  };
  textarea.addEventListener('input', refresh);
  textarea.addEventListener('scroll', sync, {passive:true});
  const observer = new ResizeObserver(sync);
  observer.observe(textarea);
  refresh();
  return {refresh};
}
