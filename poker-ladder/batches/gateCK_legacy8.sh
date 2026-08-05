#!/usr/bin/env bash
# 게이트 C-K: K축 상한 탐침 fixed {60,120,240} × s1–5 (등록: 34번 README)
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/34_threshold_stage0/gateCK_legacy8
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-13}
export PYTHONIOENCODING=utf-8
declare -A PID2NAME=()
FAILED=()
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/ladder_gateCK_$name.log"
        $PY train.py --out "$OUT/$name" --card legacy8 --episodes 2000000 \
            --eval-every 8000 --ckpt-every 40000 "$@" \
            >> "$LOGS/ladder_gateCK_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }
for s in 1 2 3 4 5; do
  run "fixed60_s$s"  --credit prop --vic fixed --vic-amount 60 --seed $s
  run "fixed120_s$s" --credit prop --vic fixed --vic-amount 120 --seed $s
  run "fixed240_s$s" --credit prop --vic fixed --vic-amount 240 --seed $s
done
for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
(( ${#FAILED[@]} )) && echo "GATECK TRAIN FAILED: ${FAILED[*]}" || echo "GATECK TRAIN DONE"
for d in "$OUT"/*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || continue
  [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval $name"; continue; }
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_gateCK_eval_$name.log" 2>&1 &
done
wait
echo "GATECK BATCH DONE"
