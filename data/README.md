# data/

External datasets the project works from, kept separate from the site's
own data (`web/data/`) and the model's files (`service/model/`).

- `incoming/` — local staging for deliveries from the Colab notebooks
  (currently T1 NB1d: per-seed embeddings, tables, `nb1d.zip`). Gitignored:
  these are large, regenerable inputs. The small tables any reported number
  cites are copied into `research/notebook-outputs/` and committed there.

Track E (held-out mass-spectrometry data; see `research/roadmap.md`) will
add a dataset registry and download scripts here.
