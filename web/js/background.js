// The living background: drifting cells, DNA and RNA strands, a molecular
// network and a flow field over a slowly breathing blue gradient. One fixed
// canvas behind every page, so the whole site reads as one specimen.
//
// Ported from the original visual.html animation (docs/web/design.md). Loaded
// as <script type="module" src="js/background.js"></script>; it mounts itself.
// Under prefers-reduced-motion it draws a single still frame and stops.

const canvas = document.createElement('canvas');
canvas.className = 'site-bg';
canvas.setAttribute('aria-hidden', 'true');
document.body.prepend(canvas);
const ctx = canvas.getContext('2d');

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

class Particle {
  constructor(type) {
    this.type = type;
    this.reset();
    this.y = Math.random() * canvas.height;
  }

  reset() {
    this.x = Math.random() * canvas.width;
    this.y = canvas.height + Math.random() * 100;
    this.size = Math.random() * 3 + 1;
    this.speedY = -Math.random() * 0.42 - 0.17;
    this.speedX = (Math.random() - 0.5) * 0.25;
    this.opacity = Math.random() * 0.6 + 0.3;
    this.pulsePhase = Math.random() * Math.PI * 2;
    this.helixPhase = Math.random() * Math.PI * 2;
    this.helixLength = Math.random() * 30 + 20;
    this.helixAmplitude = Math.random() * 8 + 4;
  }

  update(time) {
    this.y += this.speedY;
    this.x += this.speedX + Math.sin(time * 0.42 + this.pulsePhase) * 0.17;
    if (this.y < -50) this.reset();
    if (this.x < -50) this.x = canvas.width + 50;
    if (this.x > canvas.width + 50) this.x = -50;
  }

  draw(time) {
    ctx.save();
    const size = this.size * (1 + Math.sin(time * 1.7 + this.pulsePhase) * 0.2);
    ctx.globalAlpha = this.opacity;
    if (this.type === 'cell') {
      const glow = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, size * 3);
      glow.addColorStop(0, 'rgba(0, 142, 204, 0.7)');
      glow.addColorStop(0.5, 'rgba(0, 142, 204, 0.4)');
      glow.addColorStop(1, 'rgba(0, 142, 204, 0)');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(this.x, this.y, size * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(0, 142, 204, 0.9)';
      ctx.beginPath();
      ctx.arc(this.x, this.y, size, 0, Math.PI * 2);
      ctx.fill();
    } else if (this.type === 'molecule') {
      ctx.fillStyle = 'rgba(92, 184, 92, 0.7)';
      ctx.beginPath();
      ctx.arc(this.x, this.y, size, 0, Math.PI * 2);
      ctx.fill();
    } else if (this.type === 'dna') {
      this.drawDna(time);
    } else {
      this.drawRna(time);
    }
    ctx.restore();
  }

  // Rotate about the particle so the strands are not all vertical.
  tiltAbout(angle) {
    ctx.translate(this.x, this.y);
    ctx.rotate(angle);
    ctx.translate(-this.x, -this.y);
  }

  strand(time, speed, step, phase) {
    const points = 8;
    const spacing = this.helixLength / points;
    ctx.beginPath();
    for (let i = 0; i < points; i++) {
      const x = this.x + Math.sin(time * speed + this.helixPhase + i * step + phase) * this.helixAmplitude;
      const y = this.y + i * spacing - this.helixLength / 2;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  drawDna(time) {
    this.tiltAbout(this.helixPhase * 0.3 + Math.sin(time * 0.1 + this.helixPhase) * 0.4);
    ctx.strokeStyle = 'rgba(0, 142, 204, 0.75)';
    ctx.lineWidth = 1.5;
    this.strand(time, 0.3, 0.5, 0);
    this.strand(time, 0.3, 0.5, Math.PI);
    // Base pairs between the two strands.
    const spacing = this.helixLength / 8;
    ctx.strokeStyle = 'rgba(92, 184, 92, 0.6)';
    ctx.lineWidth = 0.8;
    for (let i = 0; i < 8; i += 2) {
      const a = time * 0.3 + this.helixPhase + i * 0.5;
      const y = this.y + i * spacing - this.helixLength / 2;
      ctx.beginPath();
      ctx.moveTo(this.x + Math.sin(a) * this.helixAmplitude, y);
      ctx.lineTo(this.x + Math.sin(a + Math.PI) * this.helixAmplitude, y);
      ctx.stroke();
    }
  }

  drawRna(time) {
    this.tiltAbout(this.helixPhase * 0.4 + Math.sin(time * 0.12 + this.helixPhase) * 0.5);
    ctx.strokeStyle = 'rgba(220, 53, 69, 0.75)';
    ctx.lineWidth = 2;
    this.strand(time, 0.25, 0.4, 0);
    // Nucleotides along the single strand.
    const spacing = this.helixLength / 8;
    ctx.fillStyle = 'rgba(255, 193, 7, 0.7)';
    for (let i = 0; i < 8; i += 2) {
      const x = this.x + Math.sin(time * 0.25 + this.helixPhase + i * 0.4) * this.helixAmplitude;
      const y = this.y + i * spacing - this.helixLength / 2;
      ctx.beginPath();
      ctx.arc(x, y, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

class NetworkNode {
  constructor() {
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.vx = (Math.random() - 0.5) * 0.42;
    this.vy = (Math.random() - 0.5) * 0.42;
    this.radius = Math.random() * 2 + 1;
    this.connections = [];
  }

  update() {
    this.x += this.vx;
    this.y += this.vy;
    if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
    if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
    this.x = Math.max(0, Math.min(canvas.width, this.x));
    this.y = Math.max(0, Math.min(canvas.height, this.y));
  }
}

const MAX_LINK = 140;

function linkNetwork(nodes) {
  nodes.forEach((node, i) => {
    node.connections = [];
    for (const other of nodes.slice(i + 1)) {
      const distance = Math.hypot(node.x - other.x, node.y - other.y);
      if (distance < MAX_LINK) node.connections.push({ node: other, distance });
    }
  });
}

function drawFlowField(time) {
  const step = 50;
  ctx.save();
  ctx.globalAlpha = 0.05;
  ctx.lineWidth = 1;
  for (let i = 0; i * step < canvas.width; i++) {
    for (let j = 0; j * step < canvas.height; j++) {
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

function drawBase(time) {
  const breathing = 0.5 + 0.3 * Math.sin(time * 0.8);
  const wave1 = 0.4 + 0.2 * Math.sin(time * 0.5);
  const wave2 = 0.3 + 0.15 * Math.sin(time * 0.7 + Math.PI / 3);
  const sat = 12 + breathing * 20 + wave1 * 8;
  const offset = wave2 * 5;

  const base = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  base.addColorStop(0, `hsl(210, ${Math.min(sat + offset, 50)}%, ${94 + breathing * 2}%)`);
  base.addColorStop(0.25, `hsl(212, ${Math.min(sat * 0.9 + offset, 45)}%, ${93 + breathing * 1.5}%)`);
  base.addColorStop(0.5, `hsl(215, ${Math.min(sat * 0.8 + wave1 * 8, 50)}%, ${92 + breathing}%)`);
  base.addColorStop(0.75, `hsl(213, ${Math.min(sat * 0.7 + offset, 45)}%, ${91 + breathing * 0.8}%)`);
  base.addColorStop(1, `hsl(218, ${Math.min(sat * 0.6 + wave2 * 10, 50)}%, ${90 + breathing * 0.5}%)`);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const sx = canvas.width * (0.3 + 0.2 * Math.sin(time * 0.3));
  const sy = canvas.height * (0.4 + 0.15 * Math.cos(time * 0.25));
  const shimmer = ctx.createRadialGradient(sx, sy, 0, sx, sy, canvas.width * 0.8);
  shimmer.addColorStop(0, `hsla(220, 35%, 96%, ${0.04 + wave1 * 0.03})`);
  shimmer.addColorStop(0.5, `hsla(215, 30%, 94%, ${0.02 + wave2 * 0.02})`);
  shimmer.addColorStop(1, 'hsla(210, 20%, 92%, 0)');
  ctx.fillStyle = shimmer;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawGridAndVignette() {
  ctx.save();
  ctx.globalAlpha = 0.03;
  ctx.strokeStyle = 'rgba(0, 142, 204, 0.5)';
  ctx.lineWidth = 0.5;
  for (let x = 0; x < canvas.width; x += 100) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += 100) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }
  ctx.restore();

  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  const vignette = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(canvas.width, canvas.height) * 0.7);
  vignette.addColorStop(0, 'rgba(245, 245, 243, 0)');
  vignette.addColorStop(1, 'rgba(0, 142, 204, 0.08)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

let particles = [];
let nodes = [];

function populate() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  particles = [
    ...Array.from({ length: 50 }, () => new Particle('dna')),
    ...Array.from({ length: 50 }, () => new Particle('rna')),
    ...Array.from({ length: 150 }, () => new Particle(Math.random() < 0.5 ? 'cell' : 'molecule')),
  ];
  nodes = Array.from({ length: 50 }, () => new NetworkNode());
  linkNetwork(nodes);
}

function frame(moving) {
  const time = Date.now() * 0.00085;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawBase(time);
  drawFlowField(time);

  if (moving) {
    nodes.forEach((node) => node.update());
    // Relinking every frame is O(n^2); a tenth of the frames looks the same.
    if (Math.random() < 0.1) linkNetwork(nodes);
  }
  ctx.save();
  ctx.globalAlpha = 0.1;
  ctx.lineWidth = 0.8;
  for (const node of nodes) {
    for (const link of node.connections) {
      ctx.strokeStyle = `rgba(0, 142, 204, ${(1 - link.distance / MAX_LINK) * 0.6})`;
      ctx.beginPath();
      ctx.moveTo(node.x, node.y);
      ctx.lineTo(link.node.x, link.node.y);
      ctx.stroke();
    }
  }
  ctx.fillStyle = 'rgba(0, 142, 204, 0.5)';
  for (const node of nodes) {
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  for (const particle of particles) {
    if (moving) particle.update(time);
    particle.draw(time);
  }
  drawGridAndVignette();
}

let running = false;

function loop() {
  if (!running) return;
  frame(true);
  requestAnimationFrame(loop);
}

function start() {
  if (reducedMotion.matches) {
    running = false;
    frame(false);
  } else if (!running) {
    running = true;
    requestAnimationFrame(loop);
  }
}

let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { populate(); if (!running) frame(false); }, 150);
});
reducedMotion.addEventListener('change', start);

populate();
start();
