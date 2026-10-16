---
title: VivOME Atlas projection service
sdk: docker
app_port: 7860
pinned: false
short_description: Labels single-cell proteomics cells against a blood atlas
---

# VivOME Atlas projection service

The labelling service behind the VivOME Atlas site
(https://vivome-atlas.pages.dev/project.html). Send a matrix of proteins
(or genes) by cells, and every cell comes back with a label or an
abstention with its reason, a best guess, and coordinates in the atlas's
shared space.

- **Model:** {model_version}, atlas release {atlas_version}.
- **Reference:** a human blood single-cell RNA atlas (Tabula Sapiens, 22
  cell classes).
- **Limits:** at most {max_cells} cells and {max_upload_mb} MB per upload,
  one upload projected at a time. A busy service answers 503 with a
  Retry-After; split a larger dataset at random into mixed uploads.
- **Send mixed cells,** such as PBMCs, in one file. Each protein is scaled
  within the upload, so a single sorted population gets confident but often
  wrong answers.

## Endpoints

- `GET /api/status`: whether the service can project, with the model and the
  limits above.
- `POST /api/project` (multipart form): `modality` (`prot` or `rna`),
  `matrix` (CSV or TSV, features in rows and cells in columns, or a DIA-NN
  report), optional `restrict_to_supported_classes` (`true` or `false`).

The contract, the model and its known limits are documented on the site
(versions page) and in the project repository. Research use only; not for
diagnosis.

Files: `space_manifest.json` lists every file in this Space with its sha256
and the repository commit it was built from.
