#!/usr/bin/env bash
# Track D extension: run every remaining baseline run, one at a time.
#   benchmark/baselines_queue.sh TOOL [TOOL...]      e.g. maxfuse scglue
# Skips any run that already has its .json record, records each run's exit
# status in results/baselines_ext/logs/queue.txt, and continues past a failure
# (rerun the same command to retry). Run one queue at a time: the runs load the
# full 85,232-cell reference. PYTHON picks the interpreter (default python,
# the activated conda env's).
cd "$(dirname "$0")/.." || exit 1
PYTHON=${PYTHON:-python}
mkdir -p benchmark/results/baselines_ext/logs
for tool in "$@"; do
  for dataset in scope2 pbmc240 fulcher2026; do
    for seed in 0 1 2; do
      [ -f "benchmark/results/baselines_ext/$dataset/${tool}_seed${seed}.json" ] && continue
      echo "$(date +%H:%M:%S) start $tool $dataset $seed" | tee -a benchmark/results/baselines_ext/logs/queue.txt
      "$PYTHON" -m benchmark.baselines_run "$tool" "$dataset" "$seed" \
        > "benchmark/results/baselines_ext/logs/${tool}_${dataset}_${seed}.log" 2>&1
      status=$?
      echo "$(date +%H:%M:%S) end $tool $dataset $seed exit $status" | tee -a benchmark/results/baselines_ext/logs/queue.txt
    done
  done
done
