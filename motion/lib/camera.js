// The film's camera: one continuous, eased path through a world where each
// scene's cards are a plane (lib/plan.js gives each its place, `at`, and
// its move while it is on, `move`). Pure: no DOM, so node --test checks the
// path is continuous (web/tests/reel.test.js).
//
// World units are the scenes' own pixels: a plane seen from REST away fills
// the 1920 by 1080 frame exactly as its composition is laid out. The camera
// holds on a scene while it plays, moving as its `move` says (a push-in, a
// pan, an orbit); between scenes it travels from one plane to the next, so
// the outgoing cards leave and the incoming arrive with the camera, not by
// fading. Every stretch is a cubic Hermite curve whose speed carries on
// through each key, so the camera never stops dead and never jumps.

export const REST = 1200;   // how far the camera stands from a plane it frames
export const OUT = 0.3;     // seconds before a scene ends that the camera sets off
export const IN = 1.9;      // seconds into the next scene by which it arrives

const POSE = ['x', 'y', 'z', 'yaw', 'pitch', 'roll'];
const add = (at, off = []) => POSE.map((_, k) => (k < 3 ? at[k] : 0) + (off[k] ?? 0));

// The camera's keys: for each scene, where it stands when it has arrived
// and when it sets off, from the scene's place and move.
export function cameraKeys(frames, plan, total) {
  const keys = [];
  frames.forEach((f, i) => {
    const p = plan[f.id];
    const from = i === 0 ? 0 : f.start + IN;
    const until = p.move?.until !== undefined ? f.start + p.move.until : (i === frames.length - 1 ? total : f.start + f.seconds - OUT);
    keys.push({ t: from, pose: add(p.at, p.move?.from) });
    keys.push({ t: until, pose: add(p.at, p.move?.to) });
    if (i === frames.length - 1 && until < total) keys.push({ t: total, pose: add(p.at, p.move?.to) });
  });
  return keys;
}

// The pose at time t: a Hermite curve through the keys. Each key's
// velocity is a damped mean of the stretches either side (zero at the film's
// ends), so a move eases in and out and flows on into the next.
export function poseAt(keys, t) {
  const n = keys.length;
  const x = Math.min(keys[n - 1].t, Math.max(keys[0].t, t));
  let k = 0;
  while (k < n - 2 && x >= keys[k + 1].t) k++;
  const a = keys[k];
  const b = keys[k + 1];
  const h = b.t - a.t;
  const u = h > 0 ? (x - a.t) / h : 0;
  const u2 = u * u;
  const u3 = u2 * u;
  const velocity = (j, c) => {
    if (j === 0 || j === n - 1) return 0;
    const before = (keys[j].pose[c] - keys[j - 1].pose[c]) / (keys[j].t - keys[j - 1].t);
    const after = (keys[j + 1].pose[c] - keys[j].pose[c]) / (keys[j + 1].t - keys[j].t);
    // Where the two stretches move opposite ways the camera turns at rest;
    // otherwise it keeps a share of the slower one's speed.
    if (before * after <= 0) return 0;
    return 0.6 * Math.sign(before) * Math.min(Math.abs(before), Math.abs(after));
  };
  return Object.fromEntries(POSE.map((name, c) => [name,
    (2 * u3 - 3 * u2 + 1) * a.pose[c] + (u3 - 2 * u2 + u) * h * velocity(k, c)
    + (-2 * u3 + 3 * u2) * b.pose[c] + (u3 - u2) * h * velocity(k + 1, c)]));
}

// How a scene's plane, placed at `at`, looks from the camera: its scale,
// its offset from the frame's centre (in frame pixels) and its turn
// (degrees), which a CSS transform applies to the scene.
export function planeView(pose, at) {
  const depth = Math.max(80, at[2] - (pose.z - REST));
  const scale = REST / depth;
  return {
    scale,
    dx: (at[0] - pose.x) * scale,
    dy: (at[1] - pose.y) * scale,
    turnY: -pose.yaw * 0.8,
    turnX: pose.pitch * 0.8,
    roll: pose.roll,
  };
}

// The CSS transform that puts a scene's plane where the camera sees it
// (lib/dive.js sets it on the scene's host, about the frame's centre).
export const PERSPECTIVE = 2400;
export function cssTransform(v) {
  const f = (x, d) => x.toFixed(d);
  return `translate(${f(v.dx, 2)}px, ${f(v.dy, 2)}px) perspective(${PERSPECTIVE}px) `
    + `rotateY(${f(v.turnY, 3)}deg) rotateX(${f(v.turnX, 3)}deg) rotateZ(${f(v.roll, 3)}deg) scale(${f(v.scale, 4)})`;
}

// Where a point of a plane's layout (lx, ly, 1920 by 1080) lands in the
// frame under that transform: [x, y, scale]. CSS applies the list from the
// right, so the point is scaled, rolled, turned, seen in perspective and
// then moved; this does the same, so a picture drawn here (lib/bridges.js)
// meets the scene's own exactly.
export function viewPoint(v, lx, ly) {
  const r = Math.PI / 180;
  let x = (lx - 960) * v.scale;
  let y = (ly - 540) * v.scale;
  let z = 0;
  const [cz, sz] = [Math.cos(v.roll * r), Math.sin(v.roll * r)];
  [x, y] = [x * cz - y * sz, x * sz + y * cz];
  const [cx, sx] = [Math.cos(v.turnX * r), Math.sin(v.turnX * r)];
  [y, z] = [y * cx - z * sx, y * sx + z * cx];
  const [cy, sy] = [Math.cos(v.turnY * r), Math.sin(v.turnY * r)];
  [x, z] = [x * cy + z * sy, -x * sy + z * cy];
  const w = 1 - z / PERSPECTIVE;
  return [960 + v.dx + x / w, 540 + v.dy + y / w, v.scale / w];
}

// Where a point of the layout of the plane at `at` lands in the frame.
export function project(pose, at, lx, ly) {
  return viewPoint(planeView(pose, at), lx, ly);
}

// How settled the camera is on scene i at time t: 1 while it plays, falling
// to 0 at the middle of a journey to or from it. The rack focus follows it.
export function settled(frames, i, t) {
  const f = frames[i];
  const arrive = i === 0 ? 0 : f.start + IN;
  const leave = i === frames.length - 1 ? Infinity : f.start + f.seconds - OUT;
  const mid = (a, b) => (a + b) / 2;
  if (t >= arrive && t <= leave) return 1;
  if (t < arrive) {
    const start = frames[i - 1].start + frames[i - 1].seconds - OUT;
    const m = mid(start, arrive);
    return t <= m ? 0 : smootherstep((t - m) / (arrive - m));
  }
  const end = frames[i + 1].start + IN;
  const m = mid(leave, end);
  return t >= m ? 0 : 1 - smootherstep((t - leave) / (m - leave));
}

// Where the water's surface crosses the frame, from 0 at the bottom to 1 at
// the top (lib/dive.js draws the waterline there): the surface over the
// camera (lib/plan.js, SURFACES), seen level from it.
export function waterline(pose, surfaces) {
  const s = surfaces.find((w) => pose.x >= w.x[0] && pose.x < w.x[1]);
  return s ? 1 - (540 + (s.y - pose.y)) / 1080 : Infinity;
}

export function smootherstep(x) {
  const t = Math.min(1, Math.max(0, x));
  return t * t * t * (t * (t * 6 - 15) + 10);
}
