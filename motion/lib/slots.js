// Number slots in the compositions: <span data-slot="ms:committed_fulcher">
// shows that record's text from build/facts.js (scripts/prepare.mjs read it
// from web/data/ through the site's formatters). A pending record shows
// Pending, set apart as the site sets it. A classic script, so each scene's
// own script can fill its slots while it builds its timeline.
//
// A slot with data-count-at="1.2" (and data-count-for, seconds, default
// 1.4) counts up from zero to its text from that time in its scene, with
// the landing's maths (web/js/motion.js, as build/count.js). lib/dive.js
// calls tick() on every seek, so the count is a function of the time.
//
//   VivomeSlots.fill(sceneRoot)          fill every slot inside it
//   VivomeSlots.tick(sceneRoot, seconds) set each counting slot for that time

(function () {
  const facts = (window.VIVOME && window.VIVOME.facts) || {};

  function fill(root) {
    for (const el of root.querySelectorAll('[data-slot]')) {
      const fact = facts[el.dataset.slot];
      el.textContent = fact ? fact.text : 'Pending';
      el.classList.toggle('pending', !(fact && fact.measured));
      el.dataset.final = el.textContent;
    }
  }

  function tick(root, seconds) {
    const count = window.VivomeCount && window.VivomeCount.countText;
    if (!root || !count) return;
    for (const el of root.querySelectorAll('[data-slot][data-count-at]')) {
      const at = Number(el.dataset.countAt) || 0;
      const span = Number(el.dataset.countFor) || 1.4;
      const t = Math.min(1, Math.max(0, (seconds - at) / span));
      el.textContent = count(el.dataset.final || el.textContent, t);
    }
  }

  window.VivomeSlots = { fill, tick };
})();
