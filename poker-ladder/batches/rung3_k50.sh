#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 사다리 3단: 카드축 K=20 → K=50 (A12·상대 TAG 고정 — 개정 v2).
# 기준선 = 2단 (K20·A12). 에피소드 18.75M = 7.5M × 2.5 (엔트리 7,680→19,200 비례).
# 판정: off 0/5 유지 ∧ chec_a30(또는 fixed5) 5/5 (동일 규약).
# 실행: bash batches/rung3_k50.sh  / 진행률: progress.py 창 ladder_rung3_*
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/32_ehs_k20/k50_a12
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
mkdir -p "$LOGS"

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        throttle
        $PY train.py --out "$OUT/$name" --card ehs50 --actions A12 \
            --episodes 18750000 --eval-every 75000 "$@" \
            > "$LOGS/ladder_rung3_$name.log" 2>&1 & }

for s in 1 2 3 4 5; do
  run "off_s$s"      --credit prop --vic off --seed $s
  run "fixed5_s$s"   --credit prop --vic fixed --vic-amount 5 --seed $s
  run "chec_a30_s$s" --credit prop --vic checktime --vic-amount 0.30 --seed $s
  run "pure_s$s"     --credit pure --seed $s
done
wait
echo "RUNG3 TRAIN DONE"

for d in "$OUT"/*/; do
  name=$(basename "$d")
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_rung3_eval_$name.log" 2>&1 &
done
wait
echo "RUNG3 BATCH DONE"
