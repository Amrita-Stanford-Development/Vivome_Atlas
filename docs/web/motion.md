# The Motion page and the film

`web/motion.html` is the storyboard for a film about VivOME: twelve scenes
over 120 seconds, each shown as a still rendered from the film itself,
beside its on-screen words, voice-over, motion notes and sound cue. The
film is made in its own project, `motion/`, with HyperFrames and other
motion tools; the page shows what it renders.

## The idea: a dive

The camera dives through the site's own living water and comes back up.

| Depth | Chapter | Scenes |
|---|---|---|
| At the surface | The problem: protein cells arrive unnamed and mostly unmeasured | 1 to 3 |
| Going down | The solution: RNA atlases already name their cells; VivOME carries the names across | 4 and 5 |
| The deep | What is new: built for missing values, honest answers, a second opinion | 6 to 8 |
| The floor | The results, with their caveats, and the limits | 9 and 10 |
| Rising, then the light | Use it: the Atlas page, then the end card | 11 and 12 |

The background never changes: every scene sits on the site's own white
field and gel, as the site's pages do, and every word is in the site's dark
ink. Depth shows in the objects instead. Going down, the view narrows so
the cells are larger, the camera drifts on through them faster, it sways so
the near ones move more than the far, the far ones are softly blurred, and
the particles grow; on the way up, all of that eases back. A time code and
a depth gauge in every frame carry the motif. The end breaks the surface:
"No cell placed without evidence."

## The page

| File | Role |
|---|---|
| `web/motion.html` | the page: the shared header and footer, a strip of every scene, then one block per scene, the script and the method |
| `web/js/reel-frames.js` | the storyboard, pure: every scene's timing, words, notes and number slots, and the page's markup builders |
| `web/js/reel.js` | loads the manifest, the manuscript data and the stills' sidecar, and fills the page |
| `web/css/reel.css` | the page's layout, for laptop and desktop screens |
| `web/motion/frames/NN-<scene>.webp` | the stills, 1920 by 1080, rendered by `motion/scripts/stills.mjs` |
| `web/motion/frames/index.json` | the sidecar: each still's time in the film and every number baked into it, with its record, file and field |
| `web/tests/reel.test.js` | the checks below |

The storyboard is one copy, read by the page and by the render pipeline,
so the notes beside a still always describe the frame that was rendered.

## Numbers

No number is typed into the storyboard, the compositions or the page. A
slot names its record: `{ms:key}` a record of `web/data/manuscript.json`,
`{fact:key}` a manifest fact (the model's name and the atlas version). The
page shows each through the site's guards (`msFact`, `factText`), so a
record that is not measured reads Pending; the sealed test on sorted cells
does, on purpose.

A number baked into a render would bypass that guard, so:

- `motion/scripts/prepare.mjs` reads every slot from the two data files at
  render time, through the same formatters, into `motion/build/facts.js`,
  and refuses files built for different releases;
- the compositions fill their slots from it (`motion/lib/slots.js`); a
  pending record shows Pending;
- `motion/scripts/stills.mjs` writes the sidecar with each still's numbers
  and their sources;
- `web/tests/reel.test.js` fails when a sidecar value no longer matches its
  record (render the stills again), and the page marks such a still too.

The test also checks that the scenes add up to 120 seconds, that every
slot names a record, that no percentage or decimal is typed, that the copy
keeps the site's rules (no em dashes, none of the words that wait for
evidence), that every caveat is one of the Manuscript page's, and that each
composition shows its scene's words and slots at its place in the film.

## The tools, and why each

| Tool | Used for | Why |
|---|---|---|
| HyperFrames (HeyGen, Apache 2.0) | the film: one root composition and a composition per scene; the stills | scenes are plain HTML and CSS, seeked frame by frame in headless Chrome, so the site's own stylesheet and code render as they are |
| GSAP | the words and diagrams inside each scene | HyperFrames' default runtime: paused timelines it can seek |
| three.js, with the site's water | the dive under every scene: `web/js/biocells.js` and `web/js/water.js`, unchanged | the film's water is the site's: the same cells and threads in the same gel, with its rain and wake ripples. The flow and ink effects are not used: their caustic lines and coloured ink would change the background's colour |
| The site's particle field | `web/js/background.js`'s cells, strands, network and flow field, drawn by `motion/lib/field.js` | background.js moves each particle a step per animation frame with an unseeded random start; the film needs a picture that is a function of time, so the drawing is the same and the positions are computed |
| Manim | scene 7, the answers: the map and each cell's set of plausible types | sets that grow and outline exactly the types they hold are geometry, which Manim draws precisely; it renders on a transparent background |
| FFmpeg | cutting Manim's QuickTime file into one frame per film frame; grading each still and writing it as WebP | Manim's own PNG sequence skips held frames, so its frame numbers would not be times |
| Canvas | the data pictures: the missing-value matrix, the reference map, the example file landing | drawn from `web/data/workflow.json` on each seek, as the Workflow page draws them |

Lottie is not used: it plays animations designed elsewhere, and the film
has none; everything here is data, 3D or exact geometry. Remotion is not
used because of its company licence.

## The project: `motion/`

`motion/` is the film's own project, with its own `package.json`, so `web/`
keeps no build step.

| Path | Role |
|---|---|
| `motion/index.html` | the root composition: 120 seconds, the water, the frost, the twelve scene hosts, the time code and the depth gauge |
| `motion/compositions/sNN-<scene>.html` | one scene each: its words, diagrams and GSAP timeline |
| `motion/lib/dive.js` | the water, drawn on every `hf-seek`: the cells stepped on a 60 a second grid from the film's start, each effect from its scene's start, so any frame renders the same on its own; depth as the objects coming forward (a narrower view, the drift, parallax, the far cells blurred); the waterline; the motif |
| `motion/lib/plan.js` | each scene's water: its effect, waterline, camera, particles, frost and cut |
| `motion/lib/field.js` | the site's particle field, as a function of time |
| `motion/lib/scenes.js` | the data pictures and the Manim frames, on the same seek |
| `motion/lib/slots.js` | fills number slots; counts them up with the landing's maths |
| `motion/lib/film.css` | the film's type and objects, from the site's tokens |
| `motion/manim/answers.py` | the Manim scene for scene 7 |
| `motion/scripts/hf.mjs` | runs the HyperFrames CLI with FFmpeg and Chrome found, and its telemetry, update checks and skill installs off |
| `motion/scripts/prepare.mjs` | copies the site's code into `motion/vendor/` and writes `motion/build/` |
| `motion/scripts/manim.mjs` | renders the Manim scene and cuts it into frames |
| `motion/scripts/stills.mjs` | snapshots each scene's still, grades it and writes the sidecar |

`motion/vendor/`, `motion/build/`, `motion/.hyperframes/` and
`motion/renders/` are written by the scripts and gitignored, as is
`motion/node_modules/`.

## Rendering

The tools are set up once ([setup-windows.md](../setup-windows.md), "Motion
tools"). From `motion/`:

```bash
npm install          # HyperFrames, GSAP and three.js r128, pinned
npm run stills       # prepare, Manim, then the twelve stills and their sidecar
npm run preview      # HyperFrames Studio, to watch the film play
npm run lint         # HyperFrames' checks of the compositions
```

`npm run stills` takes under a minute. To render only some scenes, run
`npm run data`, then `motion/scripts/stills.mjs` with `--only <scene id>`
(comma-separated); the other stills and their sidecar entries stay. Commit
the stills and `web/motion/frames/index.json` together.

The whole film renders silent, since there is no recorded voice-over or
music yet, in about two and a half minutes on this PC: run `npm run manim`
from `motion/`, then `motion/scripts/hf.mjs` with
`render --output renders/<name>.mp4 --fps 30 --quality draft`. HyperFrames
renders at the composition's 1920 by 1080; FFmpeg then scales a draft to
1280 by 720 and makes a smaller copy for sending. Renders stay in the
gitignored `motion/renders/` and are not on the site.

To change the film: edit the scene in `web/js/reel-frames.js` (words,
timing, notes), then its composition, and its host in `motion/index.html`
if its timing changed; the test checks they agree. Render the stills again.

## The script

Number slots are written as they are in the storyboard; the page and the
render show each record's value, or Pending. The voice-over runs at about
two words a second.

### 1. The surface (0:00 to 0:08, 8 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (rain).

- **On screen:** eyebrow "Single-cell proteomics"; headline "Proteins, measured one cell at a time."
- **Voice-over:** "Mass spectrometry can now measure the proteins inside single cells, one cell at a time."
- **Camera:** Just under the surface, looking up and ahead; a slow push in.
- **Transition:** Opens from white light. Flows on into scene 2 as the camera tips down.
- **Water:** Rain on the surface: each drop sends rings across the white gel, and a fine white waterline runs along the top.
- **Particles:** Sparse. Cells and molecules drift up towards the light.
- **Sound:** Rain on water, close. A low pad fades in; one soft piano note as the title lands.

### 2. Without names (0:08 to 0:18, 10 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "But they arrive without names."; line "Few protein datasets come labelled, and every lab detects a different set of proteins."; tag "Unnamed".
- **Voice-over:** "But those cells arrive without names. Labelled protein references are few, and every lab detects a different set of proteins."
- **Camera:** Tips down and sinks; the waterline slides up and out of the frame.
- **Transition:** One continuous move from scene 1. Leaves through a cloud of silt.
- **Water:** The same white gel, still now; the waterline slides up out of sight.
- **Particles:** Protein cells in green drift past, each with an empty name tag.
- **Sound:** The rain muffles as we go under. A slow low swell; a hollow tick as each empty tag appears.

### 3. Mostly missing (0:18 to 0:28, 10 s)

Chapter: the problem. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "And each one is only partly seen."; number "{ms:wf_missing_share}"; label "of the values in one public file are missing"; caption "PBMC240, the example file on the Workflow page"; number "{ms:ds_fulcher2026_proteins_per_cell}"; label "proteins measured per cell in Fulcher 2026, the median"; caption "VivOME reads {ms:gs_size} genes."
- **Voice-over:** "And each cell is only partly seen. Much of a protein matrix is empty."
- **Camera:** A slow sideways track along a matrix of cells and proteins.
- **Transition:** The missing tiles fall away as specks that become the RNA cells of scene 4.
- **Water:** The white gel thickens a little: the frost rises and the far cells soften.
- **Particles:** The molecular network loses links as values drop out.
- **Sound:** Dry ticks as tiles drop out. The pad thins to one held note.
- **Drawn from data:** The matrix: the PBMC240 example file's own values, as the Workflow page shows them (web/data/workflow.json); striped tiles were not measured.

### 4. RNA has names (0:28 to 0:38, 10 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "RNA atlases already name their cells."; number "{ms:ref_cells}"; label "RNA cells, each one labelled"; caption "in {ms:ref_classes} blood and immune cell types, from Tabula Sapiens".
- **Voice-over:** "Single-cell RNA is different. Its atlases are large, and every cell in them has a name."
- **Camera:** Descends through a shoal of cells, then pulls back to see the whole map.
- **Transition:** The map holds and slides aside to become one side of scene 5.
- **Water:** The same white gel. The camera drifts on through the cells, which come closer and larger as it goes down.
- **Particles:** RNA strands in red and gold thread through the shoal.
- **Sound:** A warm chord: the first hint of the theme.
- **Drawn from data:** The map: a sample of the reference's own cells in the atlas's projection, coloured by type, as the Atlas page draws them (web/data/workflow.json).

### 5. VivOME (0:38 to 0:50, 12 s)

Chapter: the solution. Made with HyperFrames, GSAP, three.js water (wake).

- **On screen:** wordmark "VivOME"; headline "Trained on RNA. Read on protein."; line "No protein labels, no paired cells, no retraining on your data."; label "Labelled RNA"; label "Your protein cells"; label "{ms:gs_size} genes link the two"; caption "It carries the names across. It never mixes the two kinds of data."
- **Voice-over:** "VivOME learns blood cell types from labelled RNA alone, then reads each protein cell against that reference. No protein labels, no paired cells, and no retraining on your data."
- **Camera:** Holds on the wordmark, then a slow crane down to the bridge between the two sides.
- **Transition:** The wordmark rises out of the particles. Leaves on a push into the protein side.
- **Water:** A slow wake ripples through the white gel as the wordmark rises.
- **Particles:** The network links up across the frame as the bridge forms.
- **Sound:** The theme enters in full: a rising arpeggio, and a soft whoosh as the wordmark locks.

### 6. Built for gaps (0:50 to 1:00, 10 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (still), canvas.

- **On screen:** headline "Built for missing values."; point "It knows which proteins were never measured."; point "It scales each protein within your file."; point "It borrows from similar cells in the same file."; point "{ms:wf_members} encoders answer together."
- **Voice-over:** "It is built for gaps: it knows which proteins were never measured, scales each one within your file, and asks {ms:wf_members} encoders to answer together."
- **Camera:** Tracks along the matrix from scene 3, now lit: a mask marks each gap.
- **Transition:** Match cut from scene 3's matrix. Leaves as the beams meet in one point that drops into scene 7.
- **Water:** The white gel, clearer than in scene 3; nearer cells drift larger past the camera, the far ones softly out of focus.
- **Particles:** Streams of particles converge on one point.
- **Sound:** Soft tones, one per encoder, resolving into one chord.
- **Drawn from data:** The matrix: the same cells and proteins as scene 3, scaled within the file and then smoothed over similar cells, as the Workflow page shows them (web/data/workflow.json).

### 7. Honest answers (1:00 to 1:12, 12 s)

Chapter: what is new. Made with Manim, HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "When unsure, it says so."; label "Cell type"; label "Group"; label "Lineage"; label "No answer, and the reason"; caption "Cells of the PBMC240 example file, and the answers VivOME gave them."
- **Voice-over:** "Every cell gets the most precise answer the evidence allows: a cell type, its group, its lineage, or no answer, and the reason why."
- **Camera:** Locked off on the reference map, seen flat from one side.
- **Transition:** Each answer steps down the ladder in turn. Leaves as the last cell's outline dissolves into the gel.
- **Water:** Still gel, so the diagram reads cleanly.
- **Particles:** Few and slow, kept to the edges.
- **Sound:** Descending notes, one per rung, and a soft stop on no answer.
- **Drawn from data:** Manim draws the reference map and each cell's set of plausible types: four real cells of the example file, with the sets and answers the served model gave them (web/data/workflow.json).

### 8. A second opinion (1:12 to 1:20, 8 s)

Chapter: what is new. Made with HyperFrames, GSAP, three.js water (wake).

- **On screen:** headline "One best guess, with a second opinion."; label "The encoder"; label "Correlation to each RNA type's average"; label "Used only when your file agrees with the encoder"; label "Best guess"; chip "New in {fact:model_name}".
- **Voice-over:** "Its best guess adds a second opinion, used only when your file agrees with the encoder."
- **Camera:** Follows two currents as they braid into one.
- **Transition:** Comes in as scene 7's outline dissolves. Leaves as the braided current dives on down.
- **Water:** A wake follows the two currents through the white gel.
- **Particles:** Two streams of particles that merge after a gate.
- **Sound:** Two lines of melody braid into one.

### 9. On real protein data (1:20 to 1:32, 12 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "Checked against real data."; label "Fulcher 2026"; number "{ms:committed_fulcher}"; label "of cells given an answer"; number "{ms:correct_fulcher}"; label "of those answers right, at the level stated"; label "Khoury 2026"; number "{ms:khoury_lymphoid}"; label "of lymphoid cells put in the lymphoid lineage"; number "{ms:khoury_myeloid}"; label "of myeloid cells put in the myeloid lineage"; caption "Development: these data were used while VivOME was built. Post-hoc: their labels had been read before."
- **Caveats shown:** development, post-hoc.
- **Voice-over:** "On real blood protein data, here is how often it answers, and how often those answers are right."
- **Camera:** Settles at the deepest point of the dive; the cards rise among the nearest cells.
- **Transition:** Leaves on a slow pan along the floor into scene 10.
- **Water:** The same white gel; at the deepest point the cells are closest and largest, and the far ones most softly blurred.
- **Particles:** Dense and close: cells and strands drift large around the cards.
- **Sound:** The music drops to a deep pulse; each number lands with a soft sonar ping.

### 10. Against established methods (1:32 to 1:44, 12 s)

Chapter: the results. Made with HyperFrames, GSAP, three.js water (still).

- **On screen:** headline "Measured against established methods."; line "On real protein data, VivOME is level with the best of them and ahead of the rest."; number "{ms:bm_khoury_baseline_favour} of {ms:bm_khoury_baseline_runs}"; label "baseline runs favour VivOME on Khoury 2026"; number "{ms:bm_fulcher_favour} of {ms:bm_fulcher_pairings}"; label "paired comparisons favour VivOME on Fulcher 2026"; caption "Still weak: CD8 T cells and dendritic cells, for every method tested."; caption "A sealed test on sorted cells: {ms:open_sorted_test}".
- **Caveats shown:** post-hoc, in-sample, pending.
- **Voice-over:** "Against established methods, on real protein data, it is level with the best and ahead of the rest. Where it is still weak, it says so."
- **Camera:** A slow pan along the floor past the methods, each a bubble with its name.
- **Transition:** Leaves as the camera turns up towards the light.
- **Water:** The same white gel; the cells begin to recede as the camera turns to rise.
- **Particles:** The methods rise past the camera as bubbles, each with its name: scANVI, MaxFuse, scGLUE, Harmony, Seurat, PCA and correlation.
- **Sound:** The pulse continues under a lighter counter-melody: the rise begins.

### 11. In your browser (1:44 to 1:54, 10 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js water (wake), canvas.

- **On screen:** headline "Label your own data."; line "Send a DIA-NN, FragPipe or CSV file from the Atlas page. Your cells land on the reference, each with its answer or the reason for none."; chip "The PBMC240 example file"; caption "Answered by {fact:model_name}, atlas {fact:atlas_version}".
- **Voice-over:** "It runs online. Send your file from the Atlas page, and your cells land on the map, each with its answer."
- **Camera:** Rises through the water towards a browser window floating near the surface.
- **Transition:** Leaves as the camera keeps rising and breaks the surface.
- **Water:** A wake: the file leaves a trail of ripples as it drops into the atlas.
- **Particles:** The file's cells fly in as beads and land in their places.
- **Sound:** Bright plucks as each cell lands; the theme returns in full.
- **Drawn from data:** The map is the reference sample, and the beads are the PBMC240 example file's cells with the answers the served model gave them, in the Atlas page's legend (web/data/workflow.json).

### 12. Into the light (1:54 to 2:00, 6 s)

Chapter: use it. Made with HyperFrames, GSAP, three.js water (rain).

- **On screen:** wordmark "VivOME"; headline "No cell placed without evidence."; chip "Explore the atlas"; chip "Label your data"; caption "vivome-atlas.pages.dev".
- **Voice-over:** "Bring your protein cells up into the light. VivOME: no cell placed without evidence."
- **Camera:** Rushes up and breaks the surface, then settles.
- **Transition:** The splash clears to white and the end card holds.
- **Water:** The waterline sweeps down the frame as we surface and settles low; rain rings the water under the end card.
- **Particles:** Bubbles rise and burst at the surface, then the frame clears.
- **Sound:** A swell, a splash as we break the surface, and a bright final chord. Silence on the end card.
