# Projection service

The projection service accepts an expression matrix and places its cells into
the shared latent space. It is the core of the resource claim: an atlas you
can *send data to*, not only look at.

> **Status: implemented, not deployed.** The pipeline in `service/` runs
> end to end against the real v3 reference (`service/model/README.md`) and
> is covered by `service/tests/`. It is not wired up to this site —
> `project.html` today performs client-side validation only, has no
> fetch/XHR anywhere, and publishes the contract below. Every value in the
> schema is a placeholder showing the response shape — none of them is a
> measurement.

## Contract

```
POST /api/project
Content-Type: multipart/form-data

  modality : "rna" | "prot"
  matrix   : CSV, features in rows, cells in columns
```

The matrix has feature names in the first column and cell IDs in the header
row.

```json
200 Response
{
  "atlas_version"        : "<string>",
  "n_cells"              : "<int>",
  "n_features_matched"   : "<int>",
  "n_features_unmatched" : "<int>",
  "value_scale"          : {"detected": "linear" | "log" | "unknown", "transformed": "<bool>"},
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
      "abstain_reason" : "outside supported latent space"
    }
  ]
}
```

**`value_scale`** (additive, not yet in a strict reading of the contract
above — see `service/README.md`) reports whether the upload was detected as
linear-scale intensity data (e.g. a raw DIA-NN report, values in the
hundreds to tens of thousands) and log2-transformed before anything else
touched it. `"detected": "log"` means the upload already looked log-scale
and was left alone; `"unknown"` means the upload had no observed values at
all. The detection rule and its threshold are in
`service/model/canonical_preprocessing.json`.

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
cross-modal coverage — a query outside them should abstain.

## Client-side validation

`project.html` validates before anything is sent, and is built to handle real
inputs: expression matrices are routinely gigabytes.

- The header line is read from the first 64 KB slice only (`readHeaderLine`).
- Rows are counted by streaming the file through a reader (`countNonEmptyLines`).

Peak memory stays flat regardless of file size — the file is never read into
memory whole. Keep that property when wiring the real upload.
