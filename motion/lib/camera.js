// The film's camera: it travels through the water from one scene's place to
// the next (a journey), then stands exactly still while that scene's card is
// on screen. Pure: no DOM, so node --test checks the path
// (web/tests/reel.test.js).
//
// The world is flat: places are [x, y] in water units, y pointing down, at
// a fixed distance from the water's objects and with a fixed field of view,
// so nothing grows or shrinks as the camera moves; the near objects pass
// faster than the far (lib/shoal.js), the site's particles slower still
// (lib/field.js). Each scene's journey (lib/plan.js, `go`) is eased at both
// ends (a smootherstep), so the camera sets off and arrives at rest.

export const FOV = 46;                                  // degrees, top to bottom, never changed
export const TAN = Math.tan((FOV / 2) * (Math.PI / 180));
export const ASPECT = 16 / 9;
export const WATERLINE_DEPTH = 12;                      // how far off the surface is seen
export const FIELD_DEPTH = 40;                          // how far off the particle field is
export const FIELD_PX = 540 / (FIELD_DEPTH * TAN);      // particle shift, in frame pixels per unit
export const GAUGE_FLOOR = 36.9;                        // the depth the gauge calls the floor

export function smootherstep(x) {
  const t = Math.min(1, Math.max(0, x));
  return t * t * t * (t * (t * 6 - 15) + 10);
}
export const ease = smootherstep;

// Where each scene's card is seen from: the first scene's place, then each
// scene's journey (`go`) added to the place before.
export function stations(frames, plan) {
  const out = [];
  frames.forEach((f, i) => {
    const p = plan[f.id];
    out.push(i === 0 ? [...p.at] : [out[i - 1][0] + p.go[0], out[i - 1][1] + p.go[1]]);
  });
  return out;
}

// The camera's legs: the opening descent to the first scene's place, then
// one journey before each later scene. spans: [{ id, start, seconds,
// journey }] in film seconds.
export function cameraPath(spans, plan) {
  const places = stations(spans, plan);
  const first = plan[spans[0].id];
  const legs = spans.map((s, i) => ({
    from: i === 0 ? [places[0][0] + first.opening[0], places[0][1] + first.opening[1]] : places[i - 1],
    to: places[i],
    t0: s.start,
    t1: s.start + s.journey,
  }));
  return { legs, places, total: spans.at(-1).start + spans.at(-1).seconds };
}

// The leg the camera is on, or last finished, at time t, and how far along.
function legAt(path, t) {
  let k = 0;
  while (k < path.legs.length - 1 && t >= path.legs[k + 1].t0) k++;
  const leg = path.legs[k];
  return { k, leg, u: Math.min(1, Math.max(0, (t - leg.t0) / (leg.t1 - leg.t0))) };
}

// Where the camera is at time t: exactly its scene's place while the card
// is on screen.
export function poseAt(path, t) {
  const { leg, u } = legAt(path, t);
  const e = ease(u);
  return { x: leg.from[0] + (leg.to[0] - leg.from[0]) * e, y: leg.from[1] + (leg.to[1] - leg.from[1]) * e };
}

// How settled the camera is: 1 while it stands still, falling to 0 halfway
// through a journey. The water's focus follows it.
export function settled(path, t) {
  const { u } = legAt(path, t);
  return u <= 0 || u >= 1 ? 1 : 1 - Math.sin(Math.PI * u);
}

// The water's surface over a place (lib/plan.js, SURFACES).
export const surfaceOver = (x, surfaces) => surfaces.find((s) => x >= s.x[0] && x < s.x[1]);

// Where the surface crosses the frame, from 0 at the bottom to 1 at the
// top: above 1 the camera is too deep to see it, below 0 it is above it.
export function waterlineAt(pose, surfaces) {
  const s = surfaceOver(pose.x, surfaces);
  return s ? 0.5 + (pose.y - s.y) / (2 * WATERLINE_DEPTH * TAN) : Infinity;
}

// The depth gauge, 0 at the surface and 1 on the floor: each place's depth
// below its own surface, eased along each journey and still in between.
export function gaugeAt(path, t, surfaces) {
  const depth = ([x, y]) => Math.min(1, Math.max(0, (y - surfaceOver(x, surfaces).y) / GAUGE_FLOOR));
  const { leg, u } = legAt(path, t);
  return depth(leg.from) + (depth(leg.to) - depth(leg.from)) * ease(u);
}

// A journey's direction in words; within 20 degrees of an axis it is
// straight.
export function directionOf([dx, dy]) {
  const angle = (Math.atan2(-dy, dx) * 180) / Math.PI;   // 0 right, 90 up
  const near = (a) => Math.abs(((angle - a + 540) % 360) - 180) <= 20;
  if (near(0)) return 'right';
  if (near(90)) return 'up';
  if (near(180)) return 'left';
  if (near(-90)) return 'down';
  return `${dy > 0 ? 'down' : 'up'}-${dx > 0 ? 'right' : 'left'}`;
}
