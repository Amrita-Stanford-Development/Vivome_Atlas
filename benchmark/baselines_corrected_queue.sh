#!/usr/bin/env bash
# Corrected baselines (baselines_corrected.py): every tool and seed on one
# development dataset, one run at a time.
#   benchmark/baselines_corrected_queue.sh DATASET [LABELS]   e.g. fulcher2026 v52
# LABELS is the reference label set (original, the default; clean, v51 or v52):
# a candidate's own labels, so it is compared with baselines that used them.
# Deterministic tools (correlation, pca, seurat) run once, as seed 0. Skips any
# run that already has its .json record (a failed run's record is retried by
# the runner itself), records each run's exit status in the label set's
# logs/queue.txt, and continues past a failure.
# The runs load the full 85,232-cell reference: run one queue at a time.
# PYTHON picks the interpreter (default python, the activated conda env's).
cd "$(dirname "$0")/.." || exit 1
PYTHON=${PYTHON:-python}
dataset=${1:?usage: benchmark/baselines_corrected_queue.sh DATASET [LABELS]}
labels=${2:-original}
if [ "$labels" = original ]; then root=benchmark/results/baselines_corrected
else root=benchmark/results/baselines_corrected_labels_$labels; fi
logs=$root/logs
mkdir -p "$logs"
for tool in correlation pca harmony seurat maxfuse scglue scanvi; do
  for seed in 0 1 2; do
    case "$tool" in correlation|pca|seurat) [ "$seed" != 0 ] && continue ;; esac
    record="$root/$dataset/${tool}_seed${seed}.json"
    [ -f "$record" ] && grep -q '"status": "\(completed\|diverged\)"' "$record" && continue
    echo "$(date +%H:%M:%S) start $tool $dataset $seed $labels" | tee -a "$logs/queue.txt"
    "$PYTHON" -m benchmark.baselines_corrected "$tool" "$dataset" "$seed" --labels "$labels" \
      > "$logs/${tool}_${dataset}_${seed}.log" 2>&1
    status=$?
    echo "$(date +%H:%M:%S) end $tool $dataset $seed $labels exit $status" | tee -a "$logs/queue.txt"
  done
done
