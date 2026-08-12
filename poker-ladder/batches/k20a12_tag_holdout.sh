#!/usr/bin/env bash
# K20-A12 TAG-학습 런 페르소나 홀드아웃 — CFR-학습(5단)과 같은 판 교차 대조용
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
export PYTHONIOENCODING=utf-8
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
for d in ../results/32_ehs_k20/k20_a12/off_s{1..5} \
         ../results/32_ehs_k20/k20_a12/fixed5_s{1..5} \
         ../results/32_ehs_k20/k20_a12/chec_a30_s{1..5} \
         ../results/34_threshold_stage0/gateAB_k20_a12/fixed8_s{1..5}; do
  name=$(basename "$(dirname "$d")")_$(basename "$d")
  [[ -f "$d/holdout_extra.csv" ]] && { echo "SKIP $name"; continue; }
  throttle
  OPPONENTS=lag,man,sta,nit OUT_CSV=holdout_extra.csv $PY evaluate.py "$d" \
      > "$LOGS/k20tag_ex_$name.log" 2>&1 &
done
wait
echo "K20TAG HOLDOUT DONE"
