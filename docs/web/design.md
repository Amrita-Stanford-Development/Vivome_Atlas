# Design system

Every page in `web/` is built from one imagined world, so the landing page,
the dashboard and the tools read as one product. This page is the reference;
the tokens and component classes live in `web/css/page.css`. The concept this
follows (intro, landing, scroll story, dashboard, tools) is
[docs/webpage_concept.md](../webpage_concept.md).

## The world

A living specimen. The name carries it: **Viv** (living) + **OME** (omics).
The atlas covers two omes, RNA and protein, and the copy never claims more.

- **The field:** `web/js/background.js` draws one fixed canvas behind every
  page: cells, DNA and RNA strands, a molecular network and a flow field
  drifting over a slowly breathing blue gradient. It is the original landing
  and Visuals animation, kept as the site's signature. Under reduced motion it
  draws one still frame. Every page loads it with a one-line module script
  tag, and it mounts itself.
- **Cards:** the white card with the blue halo from the original landing
  (`.sheet`). The halo is the accent's glow, so shadows are blue-tinted, never
  plain black.
- **Thread:** two strands, RNA and protein, that start apart and braid into
  one shared space. Used in the landing story and, later, the logo.

## Objects: every UI role is one of four

| Class | Object | Use it for |
|---|---|---|
| `.glass` | frosted glass | chrome: the header, toolbars, sidebars |
| `.well` | pressed in | inputs, the active nav item, empty values |
| `.sheet` | the white card with the blue halo | anything you read: tables, cards, prose sections |
| `.bead` | a small cell | badges and status (`bead-rna`, `bead-prot`, `bead-both`, `bead-open`) |

`.breathe` makes a sheet's halo pulse slowly, as on the original landing.
Use it on one card per page at most.

A new element starts with the question "which object is this?" Reuse one of
the four, or add one class to `@layer components` in `page.css`. No one-off
styles. Page-specific layout (grids, spacing) may live in the page's own
`<style>`; it is unlayered, so it overrides the components when it must.

`.btn` is the one accent-filled button. `.cut` is the motif (below).

## Colour

| Token | Value | Meaning |
|---|---|---|
| `--field` | `#EAF0F6` | the field's resting colour, before the canvas draws |
| `--bench` | `#F5F5F3` | warm neutral for wells and fills |
| `--paper` | `#FFFFFF` | sheets |
| `--ink` / `--ink-soft` / `--ink-faint` | `#1D2B36` / `#4B4B4B` / `#666666` | headings / body / labels and Pending |
| `--line` | `#E4E3DE` | hairlines |
| `--accent` | `#0066A3` | the one accent: links, focus rings |
| `--accent-bright` | `#007AB8` | the cutout's fill only |
| `--rna` | `#C8641E` | reserved: RNA, and nothing else |
| `--prot` | `#2F8F6A` | reserved: protein, and nothing else |
| `--dot` | `#E4577A` | reserved: the logo's living dot |
| `--error` | `#B42318` | errors only |

A reserved colour is never decoration in the UI, so when it appears on a
mark it means something. The background field is the one decorative layer;
its red RNA strands and green molecules sit close to the reserved hues on
purpose, so the field and the marks tell the same story. A type present in both modalities gets both colours (the
`bead-both` split dot). RNA, protein and the accent pass the palette
validator as a set, both colour-blind simulations included.
Text contrast is AA or better on the bench.

Cell-type colours in the atlas viewer are a separate categorical palette, a
data encoding rather than UI.

## Type

Poppins throughout: 600 for headings, with tight tracking (`-0.03em` at
display sizes), 400/500 for body and UI. Body lines stay under about 72
characters. Labels are sentence case, never all caps.

## The motif

One key word set in a solid accent block: `Viv<span class="cut">OME</span>`,
"Two <span class="cut">omes.</span> One living space." Use it once per
heading at most, always on the word that carries the meaning.

## Copy

- Plain, sentence case, active voice. No hype words. No em dashes in visible
  text; use a colon, comma or full stop.
- The landing stays high level. Detail lives on the tool pages.
- **Honesty.** No page shows a number the manifest doesn't carry
  ([manifest.md](manifest.md)). These words stay off the site until the
  evidence exists:
  - "calibrated": conformal coverage is below its target until T1 NB3 passes;
  - "beats scANVI": true only for the shipped seed;
  - "99%": the modality probe is a diagnostic, not a score;
  - "state of the art": needs the sealed Khoury test;
  - "deployed" or "hosted": the projection service runs locally.

## Shared chrome

The header (wordmark, the tool links, Dashboard) and the footer are static
markup copied into each page, so they work without JS and don't shift the
layout. `web/tests/chrome.test.js` pins every copy byte-identical to
`web/home.html`'s, apart from the one `aria-current="page"` marker. Change
one, change all, and add a new page to the test's `PAGES` list.

## Where new results land

The pages read the runs' outputs from data files; the markup does not change
when a release does.

| Output | Lands in | Shown by |
|---|---|---|
| The deployed model and its facts | `manifest.model` (from `service/model/runtime/`) | dashboard release card, versions model card |
| The next release while it is in progress | `manifest.next_reference` | dashboard "Next release" card (hidden while null) |
| Re-exported atlas cells | `web/data/metadata_*_lat128.csv` | atlas viewer; regenerate the manifest |
| Benchmark rows | `manifest.benchmark` | benchmark page, dashboard status bead |
| Announcements | `web/data/whats_new.json` (text only, no metrics) | dashboard "What's new" |
