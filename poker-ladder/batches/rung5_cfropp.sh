#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 사다리 5단: 학습 상대 TAG → CFR+ 동결 전략 (개정 v2 — (K20, A12, CFR) 칸).
# 기준선 = 2단 (K20·A12·TAG). 바뀌는 변수 하나: --opponent cfrplus.
# 평가 = ID(vs cfrplus) + 홀드아웃(random·eval_tag) — 일반화 주장 없음.
# 사전 조건: 봇 동결(hunl_frozen_k50.npz) + 품질 게이트 통과.
# 실행: bash batches/rung5_cfropp.sh  / 진행률: ladder_rung5_*
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/32_ehs_k20/k20_a12_cfr
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
mkdir -p "$LOGS"

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        throttle
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --opponent cfrplus --episodes 7500000 --eval-every 30000 "$@" \
            > "$LOGS/ladder_rung5_$name.log" 2>&1 & }

for s in 1 2 3 4 5; do
  run "off_s$s"      --credit prop --vic off --seed $s
  run "fixed5_s$s"   --credit prop --vic fixed --vic-amount 5 --seed $s
  run "chec_a30_s$s" --credit prop --vic checktime --vic-amount 0.30 --seed $s
  run "pure_s$s"     --credit pure --seed $s
done
wait
echo "RUNG5 TRAIN DONE"

for d in "$OUT"/*/; do
  name=$(basename "$d")
  throttle
  OPPONENTS=cfrplus,random,eval_tag $PY evaluate.py "$d" \
      > "$LOGS/ladder_rung5_eval_$name.log" 2>&1 &
done
wait
echo "RUNG5 BATCH DONE"
