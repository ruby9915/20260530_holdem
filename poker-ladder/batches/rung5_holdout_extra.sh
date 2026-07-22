#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 5단 홀드아웃 보강: 기존 20런 qtable 에 lag/man/sta/nit 평가만 추가.
# (학습 없음 — 저장된 qtable.pkl 재사용, 100k×5, 12병렬)
# 실행: bash batches/rung5_holdout_extra.sh / 로그: ladder_rung5_ex_*
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/32_ehs_k20/k20_a12_cfr
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
export PYTHONIOENCODING=utf-8

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }

for d in "$OUT"/*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || { echo "SKIP $name (qtable.pkl 없음)"; continue; }
  [[ -f "$d/holdout_extra.csv" ]] && { echo "SKIP $name (완료)"; continue; }
  throttle
  OPPONENTS=lag,man,sta,nit OUT_CSV=holdout_extra.csv $PY evaluate.py "$d" \
      > "$LOGS/ladder_rung5_ex_$name.log" 2>&1 &
done
wait
echo "RUNG5 HOLDOUT-EXTRA DONE"
