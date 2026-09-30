# Projection service

The projection service accepts an expression matrix and places its cells into
the shared latent space. It is the core of the resource claim: an atlas you
can *send data to*, not only look at.

> **Status: implemented, not hosted.** The pipeline in `service/` runs
> end to end against the real v3 reference (`service/model/README.md`) and
> is covered by `service/tests/`. `web/project.html` sends an upload to a
> service the visitor runs locally (`python3 -m service.app`) and renders
> the response; there is no hosted service yet. Every value in the schema
> below is a placeholder showing the response shape, not a measurement.

## Contract

```
POST /api/project
Content-Type: multipart/form-data

  modality                      : "rna" | "prot"
  matrix                        : CSV or TSV (auto-detected), features in rows, cells in columns
  restrict_to_supported_classes : "true" | "false"   (optional; default "false")
```

**`restrict_to_supported_classes`** limits every label to the classes with
cross-modal protein evidence (`config.CROSS_MODAL_SUPPORTED_CLASSES`,
currently macrophage and monocyte). By default labels are assigned among
all 22 reference classes. The restriction is right for an upload known to
contain only those cell types, such as SCoPE2. It is wrong for anything
else: a PBMC upload restricted this way can only be labelled macrophage or
monocyte, or abstain. The response's `label_space` field reports which
candidate set was used.

The same file always returns the same response. The random calibration
subset (Stage 5) is seeded from a hash of the uploaded matrix.

The matrix has feature names in the first column and cell IDs in the header
row. A real DIA-NN report is also accepted directly: when a "Genes" column
is present, its values (which may be semicolon-separated protein groups)
become the gene identifiers, DIA-NN's other annotation columns
(`Protein.Group`, `Protein.Names`, `First.Protein.Description`,
`N.Sequences`, `N.Proteotypic.Sequences`) are excluded from the cell
columns, and each remaining column's Windows raw-file-path header is
cleaned to its basename without `.raw`.

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

`GET /api/status` answers `{"status": "ready", "atlas_version", "model_version"}`,
or 503 with `{"status": "unavailable", "reason"}` while an artifact is
missing. `project.html` calls it before offering an upload.

A browser may read the service's responses only from an allowed origin
(`config.ALLOWED_ORIGINS`, env `VIVOME_ALLOWED_ORIGINS`, comma separated).
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
(`config.MIN_OBSERVED_GENES`, currently a provisional default, see
`service/model/canonical_preprocessing.json`) checks against, replacing an
earlier fractional floor that refused the large majority of real
mass-spec-proteomics cells outright (a fixed gene count travels across
datasets with very different native panel sizes better than a fraction of
one fixed 9,002-gene denominator does).

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
`project.html` renders the supported set from the manifest via
`buildSupportedLabelSpace()`, so it tracks the atlas rather than being
restated. With the current build that is 22 cell types, only 2 of which have
cross-modal coverage. By default the service assigns among all 22; the
2 cross-modal ones are the candidate set only when a request sets
`restrict_to_supported_classes`.

## Client-side validation

`project.html` validates before anything is sent, and is built to handle real
inputs: expression matrices are routinely gigabytes.

- The header line is read from the first 64 KB slice only (`readHeaderLine`).
- Rows are counted by streaming the file through a reader (`countNonEmptyLines`).

Peak memory stays flat regardless of file size: the file is never read into
memory whole. The upload itself is streamed by the browser as `FormData`.
