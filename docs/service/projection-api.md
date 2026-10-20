# Projection service

The projection service accepts an expression matrix and places its cells into
the shared latent space. It is the core of the resource claim: an atlas you
can *send data to*, not only look at.

> **Status: implemented and hosted.** The pipeline in `service/` runs
> end to end against the real reference (`service/model/README.md`), as v4.1
> by default with v4.2, v3.1, v4 and v3 selectable ([Pipeline versions](#pipeline-versions)),
> and is covered by `service/tests/`. It is hosted on Google Cloud Run at
> `https://vivome-atlas-577083340913.us-central1.run.app` (v4.1 only; `deploy/huggingface/PUBLISH.md`).
> The Atlas page's Your data tab (`web/atlas.html#your-data`) sends an upload
> there by default, or to a service the visitor runs locally
> (`python -m service.app`), shows each cell's answer and places the cells
> on the atlas map.
> Every value in the schemas below is a placeholder showing the response
> shape, not a measurement.

## Contract

```
POST /api/project
Content-Type: multipart/form-data

  modality                      : "rna" | "prot"
  matrix                        : CSV or TSV (auto-detected), features in rows, cells in columns
  restrict_to_supported_classes : "true" | "false"   (optional; default "false")
```

**`modality`** says what the matrix measures:
- **`"prot"`:** protein intensities, linear or log. A linear upload is
  found and log2-transformed (`value_scale` in the response).
- **`"rna"`:** expects log-normalised expression, as the reference's own RNA
  is (the atlas h5ad's `X`, log1p of normalised counts). In RNA a 0 is a
  measured value, so it votes on the scale. Raw counts are usually not
  transformed:
  - their median, zeros included, is under the linear-scale threshold of
    50, so they are read as log values;
  - every 0 counts as a measured value.

  Normalise and log1p counts before uploading.

**`restrict_to_supported_classes`** limits every label to the classes with
cross-modal protein evidence (`config.CROSS_MODAL_SUPPORTED_CLASSES`,
currently macrophage and monocyte). By default labels are assigned among
all 22 reference classes. A restricted upload can only be labelled
macrophage or monocyte, or abstain, so the restriction is wrong for
anything else: a PBMC upload restricted this way cannot get a lymphoid
label. The response's `label_space` field reports which candidate set was
used.

**Restricted mode was not evaluated under v3.1, and is not recommended
there.** NB2 never evaluated it. On SCoPE2, v3.1 restricted with its
service flags on commits every cell, but 97.9% of the answers are
"monocyte/macrophage". That group is exactly the two allowed classes, so it
says nothing the restriction didn't (`research/benchmark/results.md`,
"v3.1's two service flags").

The same file always returns the same response. v3.1, v4.1 and v4.2 draw
no calibration cells from the upload: their conformal thresholds and
out-of-distribution threshold are fixed. Under v3, the random calibration
subset (Stage 5) is seeded from a hash of the uploaded matrix.

The matrix has feature names in the first column and cell IDs in the header
row. A real DIA-NN report is also accepted directly: when a "Genes" column
is present, its values (which may be semicolon-separated protein groups)
become the gene identifiers, DIA-NN's other annotation columns
(`Protein.Group`, `Protein.Ids` from DIA-NN 1.8, `Protein.Names`,
`First.Protein.Description`, `N.Sequences`, `N.Proteotypic.Sequences`) are
excluded from the cell columns, and each remaining column's Windows
raw-file-path header is cleaned to its basename without `.raw`.

Four more protein tables are read as their software writes them
(`service/pipeline/alignment.py`):
- **Spectronaut's protein-group pivot report** (it has "PG.Genes" and
  "<run>.PG.Quantity" columns): "PG.Genes" gives the identifiers, and there
  is one cell per run, named by the run without its "[n]" prefix or file
  extension. "Filtered", "NaN" and 0 are missing.
- **MaxQuant's `proteinGroups.txt`** (it has "Majority protein IDs" and "Gene
  names"):
  - "Gene names" gives the identifiers;
  - rows marked "+" as reverse, contaminant or only identified by site are
    left out;
  - one cell per sample, from "LFQ intensity <sample>" when any value is
    above 0, else from "Intensity <sample>";
  - a SILAC search (Ratio columns) or a TMT search (Reporter intensity
    columns) is refused, because its intensities are labels or whole
    plexes, not cells.
- **FragPipe's LFQ `combined_protein.tsv`** (it has "Gene" and "Combined
  Total Peptides"):
  - "Gene" gives the identifiers;
  - rows whose "Protein" starts with `contam_` or `rev_` are left out;
  - one cell per sample, from "<sample> MaxLFQ Intensity" when any value is
    above 0, else from "<sample> Intensity". The unique, total and razor
    intensities are not cells.
- **A FragPipe TMT-Integrator protein table** (it has "Gene"): "Gene" gives
  the identifiers. Its annotation columns and reference channels are not
  cells.

In MaxQuant's and FragPipe's LFQ tables, 0 means "not quantified" and is
read as missing.

**In every layout:**
- The file may be UTF-8 (a byte order mark, as in Excel's "CSV UTF-8", is
  ignored), UTF-16 with its byte order mark (Excel's "Unicode Text"), or
  Windows-1252 (Excel's plain "CSV"). An Excel workbook (.xlsx) or another
  binary file is refused (400), saying what to send instead.
- Perseus's annotation rows (`#!{...}`) are skipped.
- A plain matrix written by R without the corner field over its row names
  is read with every cell under its own name.
- A versioned Ensembl ID (GENCODE's `ENSG00000121410.12`) matches its gene.

**Refused (400), with a message naming the problem:**
- a table with text where a number belongs (the message names the column
  and lists the layouts the service reads);
- a row too short for its header (the message names the line).

```json
200 Response
{
  "atlas_version"        : "<string>",
  "n_cells"              : "<int>",
  "n_features_matched"   : "<int>",
  "n_features_unmatched" : "<int>",
  "value_scale"          : {"detected": "linear" | "log" | "unknown", "transformed": "<bool>"},
  "label_space"          : {"restricted_to_supported_classes": "<bool>", "candidate_classes": ["<string>", "..."]},
  "gene_id_resolution"   : {"matched": "<int>", "unmapped": "<int>", "ambiguous": "<int>",
                            "unmapped_identifiers": ["<string>", "..."], "ambiguous_identifiers": ["<string>", "..."]},
  "cells": [
    {
      "cell_id"        : "<string>",
      "coordinates"    : ["<float>", "<float>", "<float>"],
      "observed_genes" : "<int>",
      "label"          : "<string>",
      "label_set"      : ["<string>", "..."],
      "confidence"     : "<float 0-1>",
      "abstained"      : false
    },
    {
      "cell_id"        : "<string>",
      "coordinates"    : ["<float>", "<float>", "<float>"],
      "observed_genes" : "<int>",
      "label"          : null,
      "label_set"      : [],
      "confidence"     : null,
      "abstained"      : true,
      "abstain_reason" : "coverage_too_low" | "outside_supported_region" | "no_confident_label" | "ambiguous_between_classes"
    }
  ]
}
```

`GET /api/status` answers `{"status": "ready", "atlas_version", "model_version", "pipeline_version", "limits"}`,
where `limits` is `{"max_cells", "max_upload_mb", "concurrent_projections"}`,
or `{"status": "unavailable", "reason"}`:
- **503** while an artifact is missing or not yet fetched;
- **500** for any other load error.

`POST /api/project` answers the same two codes with the same reason.
Nothing is remembered from a failed load: every request checks again, so
files fetched while the service runs are picked up without a restart.
The Atlas page's Your data tab calls `/api/status` before offering an upload.

`POST /api/project` also answers, each with `{"error", "reason"}`:
- **413** when the request is larger than `max_upload_mb`, or the matrix
  has more cells than `max_cells`;
- **503** with a `Retry-After` header (seconds) when every projection slot
  is taken by other uploads. This is checked before the matrix is read:
  reading a large table takes several times its size in memory, so it
  happens inside the slot. So a matrix the service would turn down (a 400,
  or a 413 for too many cells) can first be answered busy, and gets its
  refusal once a slot is free. The request's size, its form and a file that
  is not text are checked before the slot;
- **400** for a malformed request or matrix.

With `VIVOME_PROXY_SECRET` set, both endpoints answer **403** to any request
without that secret in the `X-VivOME-Proxy-Secret` header, before doing any
work. The hosted copy sets it: it answers only through its website, whose
`/api/...` (a Cloudflare Pages Function, `deploy/pages/api-proxy.js`)
forwards each request with the secret, behind the site's sign-in. Pages
call their own site's `/api` (`siteServiceUrl` in
`web/js/atlas/service-client.js`). The hosted copy's upload limit is 31 MiB:
Cloud Run takes at most 32 MiB in an HTTP/1 request (the site's host,
Cloudflare, takes 100 MB). `/api/status` reports it as `max_upload_mb`.

A browser may read the service's responses only from an allowed origin
(`config.ALLOWED_ORIGINS`, env `VIVOME_ALLOWED_ORIGINS`, comma separated).

The service reads these settings from the environment (`service/config.py`):

| Variable | Default | What it sets |
|---|---|---|
| `VIVOME_HOST`, `VIVOME_PORT` | `127.0.0.1`, `8001` | Where the server listens |
| `VIVOME_PIPELINE_VERSION` | `v4.1` | The model served (one per process) |
| `VIVOME_ALLOWED_ORIGINS` | the site served locally | Origins that may read the answers |
| `VIVOME_MAX_UPLOAD_CELLS` | `2000` | Cells per upload |
| `VIVOME_MAX_UPLOAD_MB` | `100` | Request size |
| `VIVOME_MAX_CONCURRENT_PROJECTIONS` | `1` | Projections running at once |
| `VIVOME_BUSY_RETRY_AFTER_SECONDS` | `30` | The `Retry-After` of a busy answer |
| `VIVOME_PROXY_SECRET` | unset | Only requests carrying it are answered |

The hosted copy's values are in `deploy/huggingface/Dockerfile`, except the
secret, which is set on the Cloud Run service itself and never in a file
(`deploy/huggingface/PUBLISH.md`).
The default allows the site served locally on port 8000. The service also
answers CORS preflights, including Chrome's Private Network Access check.

**`value_scale`** (additive, not yet in a strict reading of the contract
above — see `service/README.md`) reports whether the upload was detected as
linear-scale intensity data (e.g. a raw DIA-NN report, values in the
hundreds to tens of thousands) and log2-transformed before anything else
touched it. `"detected": "log"` means the upload already looked log-scale
and was left alone; `"unknown"` means the upload had no observed values at
all. The detection rule and its threshold are in
`service/model/canonical_preprocessing.json`.

**`gene_id_resolution`** reports how the upload's own feature identifiers
(gene symbols, Ensembl gene IDs, UniProt accessions, or a DIA-NN-style
semicolon-separated protein group of any of these) were resolved onto the
service's fixed 9,002-gene feature space, using the frozen, versioned
mapping table `service/model/runtime/gene_id_map_v1.tsv` (built once, offline, from
HGNC's public bulk dataset — never a live per-request lookup).
`unmapped_identifiers` lists identifiers that matched nothing;
`ambiguous_identifiers` lists identifiers (almost always a semicolon
protein group) whose members disagreed on which gene they meant, so none
was guessed. `matched`/`unmapped` here can differ from
`n_features_matched`/`n_features_unmatched` above — this reports whether
the *identifier itself* resolved to *any* known gene, not whether that gene
happens to be one of the 9,002 in this service's feature space.

**`observed_genes`**, per cell, is the absolute count of feature-space genes
that cell had a value for — what the coverage floor
(`config.MIN_OBSERVED_GENES`, 200, calibrated in T1 NB1b, see
`service/model/canonical_preprocessing.json`) checks against, replacing an
earlier fractional floor that refused the large majority of real
mass-spec-proteomics cells outright (a fixed gene count travels across
datasets with very different native panel sizes better than a fraction of
one fixed 9,002-gene denominator does).

## Pipeline versions

The service runs v4.1 unless `VIVOME_PIPELINE_VERSION` names another
version (`config.PIPELINE_VERSION`): `v3`, `v3.1`, `v4` and `v4.2` stay
selectable. The schema above is v3's. A v3.1 response keeps every v3 field
with the same meaning, and adds the fields below. A v4, v4.1 or v4.2
response is a v3.1 response with a different best guess and one more field
(see "v4.1").

### v3.1

v3.1 is T1 NB2's specification (`service/model/v3_1/nb2_spec_v31.json`),
implemented in `service/pipeline/ensemble.py`:

- **Ensemble.** Five V2 encoders (NB1b, seeds 0 to 4) each score
  softmax(cosine to their class centroids / T), with T fitted per member.
  The ensemble probability is the mean of the five.
- **No per-upload label space.** Every class is a candidate unless
  `restrict_to_supported_classes` is set.
- **Mondrian conformal sets.** Class c is in a cell's set when its
  probability is at least 1 − qhat[c], with one qhat per class.
- **Two service flags, on by default** (`ensemble.SERVICE_FLAGS`; NB2's
  spec has neither; NB3b measured both on RNA, `service/model/MODEL_CARD.md`,
  v3.1, Known limits 7):
  - `set_includes_best_guess`: every non-empty set also contains the cell's
    best guess. Sets only grow, so coverage is kept, and a one-class answer
    is always the best guess. An empty set stays empty: the cell abstains.
  - `restricted_renormalise`: a restricted request rescales each cell's
    probabilities over the allowed classes before its set is built.

  A later spec can set either under `service_flags`. The spec is read and
  checked once, when the service loads; a spec that fails a check is
  refused with the reason (500).
- **Out of distribution.** A cell is out of distribution when the mean over
  members of its max cosine to any reference cell is below the fixed
  `reference_abstain_threshold`.
- **Coordinates and property transfer** use member seed 4. The site's atlas
  coordinates come from the same member and the same PCA
  (`scripts/export_atlas_coordinates.py`), so a projected cell lands on the
  displayed atlas.

Every v3.1 file is checked against `service/model/v3_1/MANIFEST.json` when
the service loads. The five checkpoints live outside git
(`scripts/fetch_v31_members.py`). Until they are in place, the service
answers 503 and names the missing file.

```
{
  "pipeline_version"  : "v3.1",
  "supported_classes" : {"names": [<string>, ...], "method": "none" | "cross_modal_supported", "support": null,
                          "renormalised": <bool>},   probabilities rescaled over a restricted space
  "calibration" : {
    "method"                  : <string>,
    "target_coverage"         : 0.9,
    "applies_to"              : <string>,   what the coverage target is a guarantee about
    "n_calibration_cells"     : 0,          nothing is drawn from the upload
    "set_includes_best_guess" : <bool>
  },
  "reference_abstain_threshold" : <float>,  the out-of-distribution threshold itself
  "cells": [
    { ..., "label": "T cell", "label_level": "group",
      "label_set": ["cd4-positive, alpha-beta t cell", "regulatory t cell"],
      "confidence": <float>, "abstained": false,
      "reference_similarity": <float>,
      "best_guess": {"label": "cd4-positive, alpha-beta t cell", "probability": <float>} },
    { ..., "label": null, "label_level": null, "label_set": [], "confidence": null,
      "abstained": true, "abstain_reason": <reason>,
      "abstain_category": "no_reference_support" | "low_coverage" | "ambiguous",
      "reference_similarity": <float>,
      "best_guess": {...} }                 absent when abstain_reason is coverage_too_low
  ]
}
```

**The confident label** is stated at the level its conformal set supports.
`label_set` is the cell's set.
- **One class:** `label` is that class, and `label_level` is `"class"`.
- **Several classes in one group:** `label` is the group (for example
  `"T cell"`), and `label_level` is `"group"`.
- **Several groups in one lineage:** `label` is the lineage (for example
  `"lymphoid"`), and `label_level` is `"lineage"`.
- **Anything else:** the cell abstains with `ambiguous_between_classes`.

Groups and lineages are NB2's hierarchy (the spec's `hierarchy`, also
`research/notebook-outputs/nb2/tables/class_hierarchy.csv`). `confidence`
is the ensemble probability summed over `label_set`: the probability that
the cell is one of the classes it names. In a restricted request with
`renormalised`, it is that probability among the allowed classes; so is
the best guess's.

Cells are checked in order:
1. fewer than 200 observed genes: `coverage_too_low`;
2. out of distribution: `outside_supported_region`;
3. an empty set: `no_confident_label`;
4. the hierarchy above.

**`best_guess`** is the class with the highest ensemble probability among
the candidate classes, with that probability. Each member's temperature
was fitted in NB2 on labelled RNA, so the probability is calibrated there.
Every cell not refused for coverage has one, including cells that
abstained. It is not a confident answer: no coverage target covers it.
- Read `label` for an answer that holds at its stated level.
- Read `best_guess` and its probability to see where the model leans.

**`reference_similarity`** is the cell's out-of-distribution score. The
cell abstains with `outside_supported_region` when its score is below
`reference_abstain_threshold`, unless it was already refused for coverage.

`abstain_category` groups the reasons:

| `abstain_reason` | `abstain_category` |
|---|---|
| `outside_supported_region` | `no_reference_support` |
| `coverage_too_low` | `low_coverage` |
| `no_confident_label` | `ambiguous` |
| `ambiguous_between_classes` | `ambiguous` |

`calibration.applies_to` states what the coverage target covers:
- v3.1's qhats were fitted on labelled RNA simulated uploads, so on protein
  the coverage is approximate (`service/model/MODEL_CARD.md`, v3.1).
- v3's sets are calibrated on the upload's own top predictions, with no
  ground truth, so their target is nominal.

### v4.1

v4.1 keeps v3.1's answers and changes the best guess
(`service/pipeline/fusion.py`; spec `service/model/v4_1/spec_v41.json`,
built on v4's `service/model/v4/spec_v4.json`):

- **The answers are v3.1's:** the same members, conformal sets,
  out-of-distribution threshold, hierarchy, coordinates and properties.
- **The best guess is fused** from v3.1's members, with class-balanced
  centroids, and each cell's correlation with the reference's class means
  over the genes it measured.
- **The correlation term is used only where it carries signal:** when at
  least `agreement_threshold` of the upload's cells have the same top class
  under the correlation as under v3.1. Below it, the term is flat and the
  guess is the encoder's alone. An upload of one cell type usually falls
  below it.
- **The fused guess joins every non-empty set** beside v3.1's own guess
  (`set_includes_best_guess`), so v4.1's sets contain v3.1's.

The response is v3.1's, with `pipeline_version` `"v4.1"`, its own
`model_version`, and:

```
"best_guess_rule": {
  "rule"                : "fusion",
  "agreement"           : <float>,   the upload's agreement
  "agreement_threshold" : <float>,
  "correlation_term"    : "used" | "flat"
}
```

v4 is the same code with v4's spec: the encoder's weight is 0.7 wherever
the correlation term is used, against v4.1's 0.5.

### v4.2, selectable

v4.2, the default in release 0.5.0, is v4.1 with one change for protein
uploads (`modality` `"prot"`; spec `service/model/v4_2/spec_v42.json`, its
evaluation passed for release 0.5.0; release 0.6.0 serves v4.1 again after
v4.2 fell short of it on Khoury 2026): each cell's correlation is taken with protein class means from
sorted immune cells (Rieckmann et al. 2017, PRIDE PXD004352) for the
reference classes they cover, and with the reference's RNA class means for
the rest. An RNA upload is answered exactly as by v4.1
(`service/tests/test_v42.py`). Since each set holds the best guess, a
protein cell's answer can change with it. The response is v4.1's, with its
own `pipeline_version` and `model_version`.

### Components

`pipeline.components_for(version)` builds the three swappable stages:

| Stage | v3 | v3.1 |
|---|---|---|
| label space | `label_space.V3LabelSpace` | `label_space.V31LabelSpace` |
| conformal sets | `calibration.V3ConformalCalibrator` | `calibration.MondrianCalibrator` |
| abstention | `abstention.V3AbstentionScorer` | `abstention.V31AbstentionScorer` |

An abstention scorer can also ask for the encoder's 512-dimensional
pre-projection features (`encode_with_hidden`). In v3:
- Stage 4's nearest-centroid softmax takes a fitted temperature and
  per-class bias (`assignment.assign_labels`);
- Stage 7 chooses its confidence rule per label-space method
  (`config.FALLBACK_CONFIDENCE`).

## Two design commitments

**`label_set` is a conformal prediction set at the stated coverage level, not
a single argmax.** A cell whose identity is genuinely ambiguous between three
types returns all three. Collapsing that to one label discards the
uncertainty the atlas actually has.

**`abstained` is true when the query falls outside the region the atlas has
evidence for.** The service returns no label rather than guessing. This is the
same principle as the manifest's pending records, applied at query time: the
resource does not invent a value it cannot support.

`n_features_unmatched` is reported alongside `n_features_matched` for the same
reason — a projection computed from 12% of the submitted features is a
different claim than one computed from 90%, and the caller has to be able to
tell.

## Supported label space

A projection is only meaningful onto cell types the atlas supports.
The Atlas page's Your data tab renders the supported set from the manifest
via `buildSupportedLabelSpace()`, in its "Supported label space" section
(`web/atlas.html#labels`), so it tracks the atlas rather than being restated.
With the current build that is 22 cell types, only 2 of which have
cross-modal coverage. By default the service assigns among all 22; the
2 cross-modal ones are the candidate set only when a request sets
`restrict_to_supported_classes`.

## Client-side validation

The Atlas page's Your data tab validates before anything is sent
(`web/js/atlas/file-check.js`), and is built to handle real inputs:
expression matrices are routinely gigabytes.

- The header line is read in 64 KB slices, up to 16 MB (a DIA-NN report's
  header of raw-file paths passes 64 KB at about 900 cells).
- Rows are counted by streaming the file through a reader.
- The separator and annotation columns follow the service's own parser, so
  the cell count matches what the service will see; the count is checked
  against the service's limits.

Peak memory stays flat regardless of file size: the file is never read into
memory whole. The upload itself is streamed by the browser as `FormData`.
