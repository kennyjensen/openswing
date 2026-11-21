// Drela's Daedalus GIF: wing, horizontal tail, fin, boom, fairing, propeller.
// Yellow and violet extend the six displayed hues for larger models.
export const surfaceColors = Object.freeze([
  '#ff0000', '#ffa500', '#00ff00', '#00ffff',
  '#0080ff', '#ff00ff', '#ffff00', '#8a2be2',
]);
export const plotColors = Object.freeze([
  '#ff4a3d', '#ff9f1a', '#6dd36f', '#22d3ee',
  '#2f7bff', '#f472b6', '#ffd166', '#9b5de5',
]);
export const engineColor = '#ff00ff';

// A white tint preserves each surface's hue while making its mesh readable.
export function wireframeColor(color) {
  return '#'+color.slice(1).match(/../g).map(channel=>
    Math.round(parseInt(channel,16)*.65+255*.35).toString(16).padStart(2,'0')).join('');
}

// All beams, including bodies, consume a color. Use model order, not beam IDs:
// IDs may be sparse and must retain their colors in deformed/modal geometry.
export function beamColor(beams, index) {
  const ordinal = beams.findIndex(beam => beam.index === index);
  return surfaceColors[Math.max(0, ordinal) % surfaceColors.length];
}

export function colorBeamPlot(element, beams, index) {
  element.style.setProperty('--plot-color', beamColor(beams, Number(index)));
}
