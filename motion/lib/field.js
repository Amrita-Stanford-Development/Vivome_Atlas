// The site's field (web/js/background.js), drawn the same way but as a pure
// function of film time, so HyperFrames can seek to any frame: the breathing
// near-white base, the flow field, the molecular network, cells, molecules,
// DNA and RNA strands, and the faint grid and edge shade. background.js
// moves its particles a step per animation frame with Math.random(); here
// every position is worked out from seeded starting values and the time,
// which gives the same picture at the same moment on every render. The
// colours and shapes are background.js's own.
//
// createField(width, height) -> { canvas, draw(t, { climb, density, links, scale }) }
// paints the whole frame; web/js/biofield.js's water (lib/dive.js) lays it
// behind the cells, as the site does.

import { rng } from '../vendor/site/random.js';

const TAU = Math.PI * 2;
const wrap = (v, lo, span) => lo + ((((v - lo) % span) + span) % span);
// A bounce between 0 and span, as background.js's nodes do at the edges.
const bounce = (v, span) => { const m = wrap(v, 0, 2 * span); return m > span ? 2 * span - m : m; };

export function createField(width, height, seed = 17) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  const rand = rng(seed);

  // background.js's mix: 50 DNA, 50 RNA, 150 cells and molecules; and 50 nodes.
  const kinds = [
    ...Array.from({ length: 50 }, () => 'dna'),
    ...Array.from({ length: 50 }, () => 'rna'),
    ...Array.from({ length: 150 }, () => (rand() < 0.5 ? 'cell' : 'molecule')),
  ];
  // Shuffled, so a lower density keeps every kind.
  for (let i = kinds.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [kinds[i], kinds[j]] = [kinds[j], kinds[i]];
  }
  const particles = kinds.map((type) => ({
    type,
    x: rand() * width,
    y: rand() * (height + 100),
    size: rand() * 3 + 1,
    speedY: rand() * 0.42 + 0.17,
    speedX: (rand() - 0.5) * 0.25,
    opacity: rand() * 0.6 + 0.3,
    pulse: rand() * TAU,
    helix: rand() * TAU,
    helixLength: rand() * 30 + 20,
    helixAmplitude: rand() * 8 + 4,
  }));
  const nodes = Array.from({ length: 50 }, () => ({
    x: rand() * width, y: rand() * height, vx: (rand() - 0.5) * 0.42, vy: (rand() - 0.5) * 0.42, r: rand() * 2 + 1,
  }));

  function strand(p, x, y, time, speed, step, phase) {
    const points = 8;
    const spacing = p.helixLength / points;
    ctx.beginPath();
    for (let i = 0; i < points; i++) {
      const sx = x + Math.sin(time * speed + p.helix + i * step + phase) * p.helixAmplitude;
      const sy = y + i * spacing - p.helixLength / 2;
      if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
    }
    ctx.stroke();
  }

  function tilt(x, y, angle) {
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.translate(-x, -y);
  }

  function particle(p, x, y, time, glow) {
    const size = p.size * (1 + Math.sin(time * 1.7 + p.pulse) * 0.2);
    ctx.save();
    ctx.globalAlpha = Math.min(1, p.opacity * glow);
    if (p.type === 'cell') {
      const g = ctx.createRadialGradient(x, y, 0, x, y, size * 3);
      g.addColorStop(0, 'rgba(0, 142, 204, 0.7)');
      g.addColorStop(0.5, 'rgba(0, 142, 204, 0.4)');
      g.addColorStop(1, 'rgba(0, 142, 204, 0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, size * 3, 0, TAU);
      ctx.fill();
      ctx.fillStyle = 'rgba(0, 142, 204, 0.9)';
      ctx.beginPath();
      ctx.arc(x, y, size, 0, TAU);
      ctx.fill();
    } else if (p.type === 'molecule') {
      ctx.fillStyle = 'rgba(92, 184, 92, 0.7)';
      ctx.beginPath();
      ctx.arc(x, y, size, 0, TAU);
      ctx.fill();
    } else if (p.type === 'dna') {
      tilt(x, y, p.helix * 0.3 + Math.sin(time * 0.1 + p.helix) * 0.4);
      ctx.strokeStyle = 'rgba(0, 142, 204, 0.75)';
      ctx.lineWidth = 1.5;
      strand(p, x, y, time, 0.3, 0.5, 0);
      strand(p, x, y, time, 0.3, 0.5, Math.PI);
      const spacing = p.helixLength / 8;
      ctx.strokeStyle = 'rgba(92, 184, 92, 0.6)';
      ctx.lineWidth = 0.8;
      for (let i = 0; i < 8; i += 2) {
        const a = time * 0.3 + p.helix + i * 0.5;
        const sy = y + i * spacing - p.helixLength / 2;
        ctx.beginPath();
        ctx.moveTo(x + Math.sin(a) * p.helixAmplitude, sy);
        ctx.lineTo(x + Math.sin(a + Math.PI) * p.helixAmplitude, sy);
        ctx.stroke();
      }
    } else {
      tilt(x, y, p.helix * 0.4 + Math.sin(time * 0.12 + p.helix) * 0.5);
      ctx.strokeStyle = 'rgba(220, 53, 69, 0.75)';
      ctx.lineWidth = 2;
      strand(p, x, y, time, 0.25, 0.4, 0);
      const spacing = p.helixLength / 8;
      ctx.fillStyle = 'rgba(255, 193, 7, 0.7)';
      for (let i = 0; i < 8; i += 2) {
        const sx = x + Math.sin(time * 0.25 + p.helix + i * 0.4) * p.helixAmplitude;
        const sy = y + i * spacing - p.helixLength / 2;
        ctx.beginPath();
        ctx.arc(sx, sy, 1.2, 0, TAU);
        ctx.fill();
      }
    }
    ctx.restore();
  }

  // background.js's breathing base: the site's near-white field.
  function base(time) {
    const breathing = 0.5 + 0.3 * Math.sin(time * 0.8);
    const wave1 = 0.4 + 0.2 * Math.sin(time * 0.5);
    const wave2 = 0.3 + 0.15 * Math.sin(time * 0.7 + Math.PI / 3);
    const sat = 12 + breathing * 20 + wave1 * 8;
    const offset = wave2 * 5;
    const g = ctx.createLinearGradient(0, 0, width, height);
    g.addColorStop(0, `hsl(210, ${Math.min(sat + offset, 50)}%, ${94 + breathing * 2}%)`);
    g.addColorStop(0.25, `hsl(212, ${Math.min(sat * 0.9 + offset, 45)}%, ${93 + breathing * 1.5}%)`);
    g.addColorStop(0.5, `hsl(215, ${Math.min(sat * 0.8 + wave1 * 8, 50)}%, ${92 + breathing}%)`);
    g.addColorStop(0.75, `hsl(213, ${Math.min(sat * 0.7 + offset, 45)}%, ${91 + breathing * 0.8}%)`);
    g.addColorStop(1, `hsl(218, ${Math.min(sat * 0.6 + wave2 * 10, 50)}%, ${90 + breathing * 0.5}%)`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, width, height);
    const sx = width * (0.3 + 0.2 * Math.sin(time * 0.3));
    const sy = height * (0.4 + 0.15 * Math.cos(time * 0.25));
    const shimmer = ctx.createRadialGradient(sx, sy, 0, sx, sy, width * 0.8);
    shimmer.addColorStop(0, `hsla(220, 35%, 96%, ${0.04 + wave1 * 0.03})`);
    shimmer.addColorStop(0.5, `hsla(215, 30%, 94%, ${0.02 + wave2 * 0.02})`);
    shimmer.addColorStop(1, 'hsla(210, 20%, 92%, 0)');
    ctx.fillStyle = shimmer;
    ctx.fillRect(0, 0, width, height);
  }

  // background.js's faint grid and edge shade, drawn last.
  function gridAndVignette() {
    ctx.save();
    ctx.globalAlpha = 0.03;
    ctx.strokeStyle = 'rgba(0, 142, 204, 0.5)';
    ctx.lineWidth = 0.5;
    for (let x = 0; x < width; x += 100) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke(); }
    for (let y = 0; y < height; y += 100) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke(); }
    ctx.restore();
    const v = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, Math.max(width, height) * 0.7);
    v.addColorStop(0, 'rgba(245, 245, 243, 0)');
    v.addColorStop(1, 'rgba(0, 142, 204, 0.08)');
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, width, height);
  }

  function flowField(time, alpha) {
    const step = 50;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 1;
    for (let i = 0; i * step < width; i++) {
      for (let j = 0; j * step < height; j++) {
        const x = i * step;
        const y = j * step;
        const angle = (Math.sin(x * 0.01 + time * 0.17) + Math.cos(y * 0.01 + time * 0.127)) * Math.PI;
        ctx.strokeStyle = `hsla(${200 + Math.sin(time + i * 0.1) * 20}, 70%, 50%, 0.15)`;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + Math.cos(angle) * step * 0.8, y + Math.sin(angle) * step * 0.8);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // t: film seconds. climb: how far the water has risen past the camera by
  // now, in background.js's frames (60 a second at its own pace). density:
  // the share of particles shown. links: the network's strength. scale:
  // how large the particles are drawn (deeper, they come forward).
  // It paints the whole frame, as background.js does: the base first, the
  // grid and edge shade last.
  function draw(t, { climb = t * 60, density = 1, glow = 1, links = 1, scale = 1 } = {}) {
    // background.js's clock: Date.now() * 0.00085 ms, about 0.85 a second.
    const time = t * 0.85;
    base(time);
    flowField(time, 0.05 * glow);
    if (links > 0) {
      const at = nodes.map((n) => [bounce(n.x + n.vx * t * 60, width), bounce(n.y + n.vy * t * 60, height)]);
      ctx.save();
      ctx.globalAlpha = 0.1 * links * glow;
      ctx.lineWidth = 0.8;
      for (let i = 0; i < at.length; i++) {
        for (let j = i + 1; j < at.length; j++) {
          const d = Math.hypot(at[i][0] - at[j][0], at[i][1] - at[j][1]);
          if (d >= 140) continue;
          ctx.strokeStyle = `rgba(0, 142, 204, ${(1 - d / 140) * 0.6})`;
          ctx.beginPath();
          ctx.moveTo(at[i][0], at[i][1]);
          ctx.lineTo(at[j][0], at[j][1]);
          ctx.stroke();
        }
      }
      ctx.fillStyle = 'rgba(0, 142, 204, 0.5)';
      for (let i = 0; i < at.length; i++) {
        ctx.beginPath();
        ctx.arc(at[i][0], at[i][1], nodes[i].r, 0, TAU);
        ctx.fill();
      }
      ctx.restore();
    }
    const shown = Math.round(particles.length * Math.max(0, Math.min(1, density)));
    for (let i = 0; i < shown; i++) {
      const p = particles[i];
      const y = wrap(p.y - p.speedY * climb, -50, height + 100);
      const x = wrap(p.x + p.speedX * t * 60 + Math.sin(time * 0.42 + p.pulse) * 12, -50, width + 100);
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(scale, scale);
      ctx.translate(-x, -y);
      particle(p, x, y, time, glow);
      ctx.restore();
    }
    gridAndVignette();
  }

  return { canvas, draw };
}
