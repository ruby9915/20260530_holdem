#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 사다리 2단: 행동축 A8 → A12 (35절 개정 v2). 기준선 = 1단 (K=20, A8).
# 바뀌는 변수 하나: --actions A12 (레이즈 8종 + 오버벳). 카드 K=20·상대 TAG 고정.
# 에피소드 7.5M = 5M × 1.5 (Q-엔트리 5,120→7,680 비례 증량).
# 판정: off 0/5 유지 ∧ fixed5 또는 chec_a30 5/5 회복 (1단과 동일 규약).
# 실행: bash batches/rung2_a12.sh   / 진행률: progress.py 창 ladder_rung2_*
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/32_ehs_k20/k20_a12
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
mkdir -p "$LOGS"

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        throttle
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --episodes 7500000 --eval-every 30000 "$@" \
            > "$LOGS/ladder_rung2_$name.log" 2>&1 & }

for s in 1 2 3 4 5; do
  run "off_s$s"      --credit prop --vic off --seed $s
  run "fixed5_s$s"   --credit prop --vic fixed --vic-amount 5 --seed $s
  run "chec_a30_s$s" --credit prop --vic checktime --vic-amount 0.30 --seed $s
  run "pure_s$s"     --credit pure --seed $s
done
wait
echo "RUNG2 TRAIN DONE"

for d in "$OUT"/*/; do
  name=$(basename "$d")
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_rung2_eval_$name.log" 2>&1 &
done
wait
echo "RUNG2 BATCH DONE"
