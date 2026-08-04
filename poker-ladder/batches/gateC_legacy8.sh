#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 임계 조건 유도 — 게이트 C (상한 탐색, 사전 등록: results/34_threshold_stage0/README.md)
# 플랫폼 = legacy8-A8 (33번 규약 동일: 2M eps, eval 8k). chec α∈{1.0, 2.0} × s1–5.
# 실행: bash batches/gateC_legacy8.sh / 로그: ladder_gateC_*
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/34_threshold_stage0/gateC_legacy8
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-10}
export PYTHONIOENCODING=utf-8
mkdir -p "$LOGS"

declare -A PID2NAME=()
FAILED=()
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/ladder_gateC_$name.log"
        $PY train.py --out "$OUT/$name" --card legacy8 --episodes 2000000 \
            --eval-every 8000 --ckpt-every 40000 "$@" \
            >> "$LOGS/ladder_gateC_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }

for s in 1 2 3 4 5; do
  run "chec_a100_s$s" --credit prop --vic checktime --vic-amount 1.0 --seed $s
  run "chec_a200_s$s" --credit prop --vic checktime --vic-amount 2.0 --seed $s
done
for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
(( ${#FAILED[@]} )) && echo "GATEC TRAIN FAILED: ${FAILED[*]}" || echo "GATEC TRAIN DONE"

for d in "$OUT"/*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || continue
  [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval $name"; continue; }
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_gateC_eval_$name.log" 2>&1 &
done
wait
echo "GATEC BATCH DONE"
