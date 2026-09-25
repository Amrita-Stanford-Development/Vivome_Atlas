# Documentation

| Document | Covers |
|---|---|
| [manifest.md](manifest.md) | The manifest pipeline — schema, the measured/pending contract, regeneration, release protocol |
| [data.md](data.md) | Data layout, Git LFS, what ships and what does not |
| [projection-service.md](projection-service.md) | The `POST /api/project` contract, conformal label sets, abstention |
| [plans/](plans/) | Implementation plans |

The contract above is implemented at [`../service/`](../service/) — see
[`service/README.md`](../service/README.md) for the pipeline stage-by-stage
design rationale, what's real versus pending, and known sharp edges, and
[`service/model/README.md`](../service/model/README.md) for the reference
artifacts themselves.

Start at the repository [README](../README.md) for setup and layout, and
[CLAUDE.md](../CLAUDE.md) for the conventions any change has to respect.

The scientific plan this work serves is
[VivOME_NatComms_Implementation_Plan.md](../VivOME_NatComms_Implementation_Plan.md).
Its phase numbers (Phase 0 through Phase 6) are referenced throughout these
documents and in the manifest's pending records.
