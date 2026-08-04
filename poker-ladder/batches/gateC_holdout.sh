#!/usr/bin/env bash
# 게이트 C 홀드아웃 보강: gateC(a100/a200) + 기준(a20/a50) × lag/man/sta/nit 100k×5
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
export PYTHONIOENCODING=utf-8
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
for d in ../results/34_threshold_stage0/gateC_legacy8/chec_a100_s{1..5} \
         ../results/34_threshold_stage0/gateC_legacy8/chec_a200_s{1..5} \
         ../results/33_ladder_replicate_k8/chec_a20_s{1..5} \
         ../results/33_ladder_replicate_k8/chec_a50_s{1..5}; do
  name=$(basename "$d")
  [[ -f "$d/holdout_extra.csv" ]] && { echo "SKIP $name"; continue; }
  throttle
  OPPONENTS=lag,man,sta,nit OUT_CSV=holdout_extra.csv $PY evaluate.py "$d" \
      > "$LOGS/gateC_ex_$name.log" 2>&1 &
done
wait
echo "GATEC HOLDOUT DONE"
