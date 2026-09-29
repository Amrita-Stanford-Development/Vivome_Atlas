# web/

The public website: static HTML, CSS and ES modules, with no build step and
no dependencies. Serve this folder as-is:

```bash
cd web && python3 -m http.server 8000     # open http://localhost:8000/
```

Pages fetch `data/` over HTTP, so opening them from `file://` won't load
data.

| Path | Holds |
|---|---|
| `*.html` | one file per page; nav and back links point to `index.html` |
| `css/page.css` | shared styling |
| `js/manifest.js`, `js/panels.js` | pure modules (no DOM access) that load the manifest and build panel HTML |
| `data/` | `atlas_manifest.json` (generated; the only source of displayed numbers), cell metadata, embeddings; see [docs/web/data.md](../docs/web/data.md) |
| `plots/` | 30 standalone Plotly plots shown by `visual.html` |
| `tests/` | `node --test` suites for `js/`, run with `node --test` from the repo root |

The rule for every page: no number is displayed unless it was computed from
data in this repository. See [docs/web/manifest.md](../docs/web/manifest.md).
