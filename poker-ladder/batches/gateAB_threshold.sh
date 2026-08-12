#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 임계 조건 유도 — 게이트 A/B (사전 등록: results/34_threshold_stage0/README.md)
# 플랫폼 = k20_a12 (2단과 동일 규약: ehs20·A12·single-TAG·7.5M eps).
# 게이트 A: fixed K∈{8,10,20} × s1–5 (K=8 = M2 결정 시험)
# 게이트 B: chec α∈{0.10,0.15} × s1–5
# 실행: bash batches/gateAB_threshold.sh / 로그: ladder_gateAB_*
# 재실행 = 이어하기 (qtable 있으면 SKIP, 죽은 런은 ckpt 재개).
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/34_threshold_stage0/gateAB_k20_a12
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-13}
export PYTHONIOENCODING=utf-8
mkdir -p "$LOGS"

declare -A PID2NAME=()
FAILED=()

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then
          echo "SKIP $name (qtable.pkl 존재)"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/ladder_gateAB_$name.log"
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --episodes 7500000 --eval-every 30000 --ckpt-every 30000 "$@" \
            >> "$LOGS/ladder_gateAB_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }

for s in 1 2 3 4 5; do
  run "fixed8_s$s"   --credit prop --vic fixed --vic-amount 8 --seed $s
  run "fixed10_s$s"  --credit prop --vic fixed --vic-amount 10 --seed $s
  run "fixed20_s$s"  --credit prop --vic fixed --vic-amount 20 --seed $s
  run "chec_a10_s$s" --credit prop --vic checktime --vic-amount 0.10 --seed $s
  run "chec_a15_s$s" --credit prop --vic checktime --vic-amount 0.15 --seed $s
done

for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
if (( ${#FAILED[@]} )); then
  echo "GATEAB TRAIN FAILED: ${FAILED[*]}"
else
  echo "GATEAB TRAIN DONE"
fi

for d in "$OUT"/*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || { echo "SKIP eval $name"; continue; }
  [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval $name (완료)"; continue; }
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_gateAB_eval_$name.log" 2>&1 &
done
wait
echo "GATEAB BATCH DONE"
