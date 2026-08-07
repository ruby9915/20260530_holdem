#!/usr/bin/env bash
# FOLD 2단계: chec_a30 고정 + regret(부호 반전+유령 갱신) α_f ∈ {0.3, 1.0} × s1–5
# (사전 등록: results/35_fold_vic/README.md 2단계 절)
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/35_fold_vic
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-10}
export PYTHONIOENCODING=utf-8
declare -A PID2NAME=()
FAILED=()
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/foldvic_$name.log"
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --episodes 7500000 --eval-every 30000 --ckpt-every 30000 \
            --credit prop --vic checktime --vic-amount 0.30 "$@" \
            >> "$LOGS/foldvic_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }
for s in 1 2 3 4 5; do
  run "regret_a30_s$s"  --vic-fold regret --vic-fold-amount 0.3 --seed $s
  run "regret_a100_s$s" --vic-fold regret --vic-fold-amount 1.0 --seed $s
done
for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
(( ${#FAILED[@]} )) && echo "REGRET TRAIN FAILED: ${FAILED[*]}" || echo "REGRET TRAIN DONE"
for d in "$OUT"/regret_*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || continue
  [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval $name"; continue; }
  throttle
  OPPONENTS=random,eval_tag,lag,man,sta,nit $PY evaluate.py "$d" \
      > "$LOGS/foldvic_eval_$name.log" 2>&1 &
done
wait
echo "REGRET BATCH DONE"
