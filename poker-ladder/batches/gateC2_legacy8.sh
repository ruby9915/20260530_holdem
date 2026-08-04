#!/usr/bin/env bash
# 게이트 C 연장: α∈{4.0, 8.0} × s1–5 학습 + 상대 6종 전체 100k×5 평가
# (사전 등록: results/34_threshold_stage0/README.md — 게이트 C 연장 절)
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/34_threshold_stage0/gateC_legacy8
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-10}
export PYTHONIOENCODING=utf-8

declare -A PID2NAME=()
FAILED=()
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/ladder_gateC2_$name.log"
        $PY train.py --out "$OUT/$name" --card legacy8 --episodes 2000000 \
            --eval-every 8000 --ckpt-every 40000 "$@" \
            >> "$LOGS/ladder_gateC2_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }

for s in 1 2 3 4 5; do
  run "chec_a400_s$s" --credit prop --vic checktime --vic-amount 4.0 --seed $s
  run "chec_a800_s$s" --credit prop --vic checktime --vic-amount 8.0 --seed $s
done
for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
(( ${#FAILED[@]} )) && echo "GATEC2 TRAIN FAILED: ${FAILED[*]}" || echo "GATEC2 TRAIN DONE"

for s in 1 2 3 4 5; do
  for cond in chec_a400 chec_a800; do
    d="$OUT/${cond}_s$s"
    [[ -f "$d/qtable.pkl" ]] || continue
    [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval ${cond}_s$s"; continue; }
    throttle
    OPPONENTS=random,eval_tag,lag,man,sta,nit $PY evaluate.py "$d" \
        > "$LOGS/ladder_gateC2_eval_${cond}_s$s.log" 2>&1 &
  done
done
wait
echo "GATEC2 BATCH DONE"
