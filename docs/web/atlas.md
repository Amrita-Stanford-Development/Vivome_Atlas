# The Atlas page

`web/atlas.html` draws the reference: every RNA cell of the Tabula Sapiens
blood reference and every SCoPE2 protein cell, as dots in the 3D space the
served model's coordinate member defines. It is an app view on PC screens:
the header, a sidebar, the viewer, and a drawer that slides over the
viewer's right side.

The page is markup. Its code is the ES modules in `web/js/atlas/`, loaded
by one module script tag for `web/js/atlas/main.js`; three.js r128 is a
classic `<script>` tag, the same build the living water loads
(`web/tests/chrome.test.js` pins the URL).

## Modules

| Module | Role |
|---|---|
| `reference-data.js` (pure) | Reads the metadata CSVs into typed arrays; the class order (sorted, as the colours follow); the scene frame (`atlasFrame`: the box round every RNA and protein cell, 80 units across), kept so uploaded cells land through the same transform |
| `spatial.js` (pure) | The orbit pose, nearest reference cells on a grid, screen-space picking, the file's sheet, label placement |
| `answers.js` (pure) | A service response or the recorded example as one cell shape; how each answer is drawn; which pipelines share this map |
| `stage.js` | Renderer, camera and orbit rig (drag to turn, right-drag to move, wheel to zoom, slow turn until touched), and one render loop that draws only when something changed |
| `reference-layer.js` | All reference cells as one `THREE.Points`, shaded as small spheres; filters, dimming and focusing a type are uniform writes |
| `gene-profile.js` | A clicked cell's gene profile, streamed from the large CSVs; says so when this copy of the site does not have them |
| `explore-tab.js` | Counts, the RNA and protein switches, the cell-type list (also the colour key), the cross-modal support panels |
| `overlay.js` | Loading screen, error panel, tooltip |
| `main.js` | Loads the reference, wires everything, keeps `window.vivomeAtlas` as a console handle |

## Drawing

- **One draw call** for 86,723 cells. The vertex shader reads the palette
  (`CLASS_COLOURS`, `web/js/workflow-data.js`), the per-type and
  per-modality switches and the dimming; the fragment shader shades each dot
  as a sphere lit from the upper left, its centre the swatch's colour.
  Colours go out as given (no tone mapping), so dots match the list.
- **Picking** projects every point to the screen once per camera move and
  takes the nearest visible one within 8 px; no raycasting.
- **Sizes** are scene units, as the spheres were: radius 0.5 for RNA cells,
  0.9 for protein cells.
- **Motion:** under reduced motion the view never turns by itself.

## Data

`web/data/metadata_RNA_lat128.csv` and `metadata_PROT_lat128.csv`
([data.md](data.md)). Gene profiles come from the large files, fetched only on
a click; the public site leaves them out.
