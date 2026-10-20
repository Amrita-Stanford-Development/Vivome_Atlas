# The Atlas page

`web/atlas.html` draws the reference: every RNA cell of the Tabula Sapiens
blood reference and every SCoPE2 protein cell, as dots in the 3D space the
served model's coordinate member defines. Its Your data tab sends a
visitor's file to the online service, and the file's cells land on the same
map where the model places them. It is an app view on PC screens: the
header, a sidebar with two tabs, the viewer, and a drawer that slides over
the viewer's right side. Design rules: [design.md](design.md), "The Atlas
page".

The page is markup. Its code is the ES modules in `web/js/atlas/`, loaded
by one module script tag for `web/js/atlas/main.js`; three.js r128 is a
classic `<script>` tag, the same build the living water loads
(`web/tests/chrome.test.js` pins the URL).

## Modules

Pure modules have no DOM and are covered by `node --test`
(`web/tests/atlas-*.test.js`).

| Module | Role |
|---|---|
| `organs.js` (pure) | The organ maps: the organ the address names (`?organ=lung`), plain names for organ types, the families (the hierarchy's groups) and a colour per type, a family one hue |
| `reference-data.js` (pure) | Reads the metadata CSVs and the organ maps into typed arrays; the class order (sorted, as the colours follow); the scene frame (`atlasFrame`: the box round every RNA and protein cell, 80 units across), kept so uploaded cells land through the same transform |
| `spatial.js` (pure) | The orbit pose, nearest reference cells on a grid, screen-space picking, the file's cloud (an irregular, seeded shape of a few lobes, sized by the cell count), label placement |
| `answers.js` (pure) | A service response or the recorded example as one cell shape; how each answer is drawn; which pipelines share this map (v3.1, v4, v4.1, v4.2); the receipt's numbers |
| `choreography.js` (pure) | The landing's timing: the flight schedule, the guided timeline, the waiting loop, framing a pose, reduced-motion timing |
| `director.js` (pure) | The page's state machine (below) |
| `file-check.js` (pure) | Checks a file in the browser (header, cells, rows) against the service's limits; it counts cells the way the service reads each layout (a plain matrix, DIA-NN, MaxQuant, FragPipe LFQ or TMT) |
| `service-client.js` | The service's address, its status and project calls (upload progress, Retry-After, timeouts), plain-words failures |
| `atlas-panels.js` (pure) | The cell card, the receipt, the answer key, the outcome chips, the example's summary |
| `cell-browser.js` (pure) | The projected cells grouped by the answer each was given (one group per type, family, branch, reason for no answer, and not placed), their order (sorted by confidence, file order or likeness; searched by name), and the drawer's browser |
| `stage.js` | Renderer, camera and orbit rig (drag to turn, right-drag to move, wheel to zoom, glide, slow turn until touched), one render loop that draws only when something changed, and the visitor's dot size (every layer sizes and picks its dots by `pixelScale`) |
| `reference-layer.js` | All reference cells as one `THREE.Points`, shaded as small spheres; filters, dimming and highlighting a set of types (a selected cell's possible types) are uniform writes |
| `upload-layer.js` | Uploaded cells: their flights, answer looks, landing flash and ripple, and the neighbour glow, all moved by the GPU on one clock; a per-cell mask hides the cells of a type the visitor hid |
| `illustration.js` | The waiting illustration of the service's six steps |
| `landing.js` | Runs the state machine on the stage's clock: the file's cloud, the illustration, the receipt, the flights, the camera, the results, and Play from the first cell once the cells have landed |
| `data-tab.js` | The Your data tab. With an answer on the map it is the file's card (answer filters, Replay, Download, Clear, Send another file); otherwise the setup: the service line, the example, the file controls, and, folded, what it can label and an own copy's address |
| `gene-profile.js` | A clicked reference cell's gene profile, streamed from the large CSVs; says so when this copy of the site does not have them |
| `explore-tab.js` | Counts, the RNA and protein switches, the cell-type list (also the colour key) |
| `view-controls.js` | In Explore: the visitor's cells while an answer is on the map (a switch, the answer filters, the types given with Only, and the highlight of a selected cell's types), names on the map, dimming the reference, the dot size |
| `type-labels.js` | Names on the map: each shown type's name at its centre, placed so no two overlap, following the camera |
| `overlay.js` | Loading screen, error panel, tooltip |
| `main.js` | Loads the reference, wires everything, keeps `window.vivomeAtlas` as a console handle |

## Other organs

The Organ list at the top of Explore offers blood and the maps in
`web/data/organs/index.json`: the large intestine, the lung and the lymph
node. Choosing one loads `atlas.html?organ=<id>`. An organ's map is its
reference's RNA cells in its own bundle's coordinate space, so an upload
would land on it, but no file is labelled against it: each organ's
reference missed its development gates (`research/organ-references.md`).
So the organ page hides Your data and the protein cells, and says why.
Every way into Your data is closed there: its tab, the arrow keys, the
address (`#your-data`) and a file dropped on the map, which is refused.

- **Colours** (`organPalette`): one hue per family, its types in shades of
  it, so families read as blocks on the map. Blood keeps `CLASS_COLOURS`.
- **The type list** is one block per family; a family's name shows or
  hides the whole block.
- **A cell** shows its type, family and branch; gene profiles are kept for
  blood only.

## The landing

`director.js` holds the states; `landing.js` moves between them.

| State | What the visitor sees |
|---|---|
| idle | The atlas, turning slowly until touched |
| checking, chosen | The file is checked in the browser; the camera eases aside and the file appears beside the atlas as an irregular cloud of dots, one per cell, that breathes (it swells and settles, each dot drifting on its own small loop). Nothing is sent yet |
| sending | Real upload progress, with Cancel |
| working | The service sends no progress: an **illustration** of its six steps loops (`SERVICE_STEPS` in `web/js/workflow-data.js`), with a clock and, after a few seconds, the note that the service may be waking up |
| busy | Another file is being labelled: a countdown, then another try, three tries in all |
| finishing | The illustration plays its remaining steps quickly |
| receipt | The response's own numbers: cells, genes matched, whether the second opinion was used, the model. A folding card, open until the visitor has the camera |
| flying | Cells arc from their breathing places in the cloud onto their coordinates by answer level (one type, family, branch, no answer), highest confidence first; each lands with a flash and a ripple, and nearby reference cells of its type glow briefly. The camera glides to frame them |
| settling | The cloud stops breathing; each landed cell is a bead, larger than any reference dot, in a halo of its own colour that pulses slowly. The reference dims, the results open in the drawer (Download and Clear, then About this answer, Answers and Cells as folding sections), the camera settles on the landed cells |
| interactive | The camera flies to the first cell and Play walks on from it (not when the visitor took the camera during the landing, nor under reduced motion); then the visitor's camera. Click a cell or a row of the drawer's cell browser for its card; step through the shown cells with the step bar (Previous, Next, Play), the card's own Previous and Next, or the arrow keys; filter by answer level and by the type given; Replay, Download, Clear. A new file or the example replaces the answer shown |
| failed | The reason in plain words, with Try again |

The guided part, from the receipt to the settled view, lasts about 8 to 9
seconds for any number of cells; Skip (or Esc) jumps to the end, and a drag
or the wheel hands the camera back at once: the landing goes on, but the
camera stays where the visitor put it. Replay and Clear wait for the end.
The sidebar folds away when a file is sent or the example starts and comes
back at idle, chosen or failed (`sidebarFor` in `director.js`).
Under reduced motion every duration is zero.

**The example.** "Watch the example" replays the PBMC240 file traced through
the served model (`web/data/workflow.json`, `trace.cells`): no file is sent.
"Send the example file" sends `web/data/examples/pbmc240_proteins_raw.tsv`
(a byte-exact copy of `service/examples/`) to the service like any upload.

## The service

- **Status** is asked only when the Your data tab first opens, on Check, and
  when the address changes, so a visit to the map never wakes the service.
- **Placing cells** needs a pipeline that shares this map
  (`COMPATIBLE_PIPELINES`). Otherwise the cells are listed, not placed.
- **Limits** come from the service's status when it gives them, else from the
  Workflow data's service records.
- **Address:** the online service by default (`DEFAULT_SERVICE_URL`, which
  `web/data/workflow.json` records); an address the visitor types for their
  own copy is remembered in their browser.

## Drawing

- **One draw call** for 86,723 reference cells. The vertex shader reads the
  palette (`CLASS_COLOURS`), the per-type and per-modality switches and the
  dimming; the fragment shader shades each dot as a sphere lit from the
  upper left, its centre the swatch's colour. Colours go out as given (no
  tone mapping), so dots match the list.
- **Uploaded cells** move in the vertex shader on one clock (start, end,
  delay, duration per cell), so the CPU does nothing per frame while they
  fly; `positionsAt` repeats the same path on the CPU for picking.
- **Picking** projects every point to the screen once per camera move and
  takes the nearest visible one; uploaded cells first. No raycasting.
- **Sizes** are scene units: radius 0.5 for RNA cells, 0.9 for protein cells.

## Data

`web/data/metadata_RNA_lat128.csv` and `metadata_PROT_lat128.csv`
([data.md](data.md)); the organ maps in `web/data/organs/`; `web/data/workflow.json` for the example and the
service's limits. Gene profiles come from the large files, fetched only on a
click; the public site leaves them out.
