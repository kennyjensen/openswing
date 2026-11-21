// Dark fills keep the brighter, hue-matched wireframe distinct in both viewers.
// The shared surface/plot palette retains its original colors and ordering.
export function surfaceFillColor(color) {
  return '#'+color.slice(1).match(/../g).map(channel=>
    Math.round(parseInt(channel,16)*.35).toString(16).padStart(2,'0')).join('');
}
