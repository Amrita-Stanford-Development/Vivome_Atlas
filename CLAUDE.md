# CLAUDE.md

Working notes for this repository. Read before changing anything.

## What this is

A static web resource for the VivOME joint latent atlas. Plain HTML + CSS +
ES modules, in `web/`. **No build step, no bundler, no
framework, no dependencies.** Do not introduce one here. `package.json`
exists only to set `"type": "module"` and to run `node --test`.

`service/` is a separate concern: the Phase 5 projection service backend,
real Python with real dependencies (torch, an OT solver — see
`service/requirements.txt`). The "no dependencies" rule above is about the
static app; it does not extend to `service/`. See `service/README.md`
before touching it — its own working agreements are stricter in places
(several pipeline choices there look wrong until you've read the design
rationale each module docstring cites).

The app exists to deliver the *resource claim* of
`research/implementation-plan.md` — a versioned atlas with a projection
service, calibrated confidence, and explicit abstention. App work runs in
parallel with the modeling track and must not block on it.

## Where things live

[docs/project-structure.md](docs/project-structure.md) is the map: what each
folder is for, where a new file goes, naming rules. Every tracked file has
one line in [docs/file-index.md](docs/file-index.md).

- Adding, moving or deleting a tracked file means updating
  `docs/file-index.md` in the same commit.
- Moving a file means rewriting every citation of it (code, docstrings,
  docs, HTML, the manifest's notes).
- `scripts/check_paths.py` enforces both. It runs in the `scripts` test
  suite and fails on an unlisted file or a cited path that doesn't resolve.

## Roadmap work

Before starting a roadmap task, read `research/todo.md` and the relevant
track in `research/roadmap.md`. When you finish, tick the completed items in
`research/todo.md` with their commit hashes and add a changelog line.

## The rule that governs everything

**No page displays a number that was not computed from data in this
repository.**

`web/data/atlas_manifest.json` is the single source of truth. Every metric is a
record, either measured or pending:

```json
{ "value": 0.998634, "status": "measured", "basis": "3-PC projection" }
{ "value": null, "status": "pending", "phase": "Phase 2", "note": "..." }
```

`isMeasured()` in `web/js/manifest.js` is the single guard: a metric renders only
when `status === 'measured'`, `value !== null`, and the value is finite.
Everything else — pending, absent, malformed, truncated — renders as
`Pending`. Do not add a display path that bypasses it, and do not hardcode a
metric into HTML. See [docs/web/manifest.md](docs/web/manifest.md).

## Conventions

- `web/js/manifest.js` and `web/js/panels.js` are **pure** — no DOM access, no side
  effects. That is what lets the same code run under `node --test` and be
  assigned to `innerHTML` in the browser. Keep them pure.
- Panel builders return HTML strings. Every interpolated value from the
  manifest goes through `escapeHtml()` — cell-type names are data, and the
  test fixture deliberately includes a `<script>` payload to prove it.
- Pages mount panels with `<script type="module" async>` and always attach a
  `.catch()` that renders `errorPanel(err)`. A failed manifest load shows an
  error, never a blank panel or a stale number.
- `atlas.html` is a classic script and cannot import `web/js/manifest.js`, so the
  Git LFS magic string is duplicated there. `web/tests/lfs.test.js` pins the two
  copies byte-for-byte. If you touch either, the test must stay green.
- Nav and back links point to `index.html`.

## After changing data

Regenerate the manifest and commit it:

```bash
python3 scripts/build_manifest.py
```

Bump `ATLAS_VERSION` in `scripts/build_manifest.py` for a real release; the full
protocol is on `web/versions.html` and in [docs/web/manifest.md](docs/web/manifest.md).

## Tests

```bash
node --test                                          # from the repo root
python3 -m unittest discover -s scripts              # manifest builder + path/index check
python3 -m unittest discover -s service/tests -t .   # projection service, from the repo root
```

Run all three before committing. `web/tests/lfs.test.js` asserts the shipped RNA
parts are still unfetched LFS pointers — if you have run `git lfs pull`
locally it will fail, which is expected and is not a reason to change the
test.

## Working agreements

- **List what you intend to delete, and get approval, before deleting it.**
  This repo mixes generated bundles, precomputed plots, and hand-written
  pages; things that look dead are often deliberate (`miscellaneous.html` is
  intentionally blank).
- `README.md` and `docs/` describe the current state only. No "what was
  removed" sections — git history is the record of change.
- Pending is a feature. When a metric cannot be computed yet, add a pending
  record with the phase that will produce it. Never fill a gap with a
  plausible number.
