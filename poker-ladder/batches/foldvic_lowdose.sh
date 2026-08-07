#!/usr/bin/env bash
# 주말 자율 확장 (저자 포괄 승인 2026-08-07 "알아서 돌려놔", 기한 월 10:00):
#   ① regret 저용량 팔 α_f=0.1 × s1–3 (3시드 예비 — 격자 하단 괄호화)
#   ② qtraj 계측 재상영: regret_a30_s1 동일 설정 + --q-snap (순수 관측 훅)
# 사전 등록 부록: results/35_fold_vic/README.md
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/35_fold_vic
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-3}
export PYTHONIOENCODING=utf-8
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/foldvic_$name.log"
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --episodes 7500000 --eval-every 30000 --ckpt-every 30000 \
            --credit prop --vic checktime --vic-amount 0.30 "$@" \
            >> "$LOGS/foldvic_$name.log" 2>&1 &
}
for s in 1 2 3; do
  run "regret_a10_s$s" --vic-fold regret --vic-fold-amount 0.1 --seed $s
done
wait
echo "LOWDOSE TRAIN DONE"

# qtraj 계측 재상영 (q_snap 은 LOCKED_KEYS 제외 — 원본과 비트 동일 재상영 + 스냅샷)
QT="$OUT/qtraj_regret_a30_s1"
if [[ ! -f "$QT/qtable.pkl" ]]; then
  mkdir -p "$QT"
  throttle
  $PY train.py --out "$QT" --card ehs20 --actions A12 \
      --episodes 7500000 --eval-every 30000 --ckpt-every 30000 \
      --credit prop --vic checktime --vic-amount 0.30 \
      --vic-fold regret --vic-fold-amount 0.3 --seed 1 \
      --q-snap "$QT/qsnap.pkl" \
      >> "$LOGS/foldvic_qtraj_regret_a30_s1.log" 2>&1 &
fi
for s in 1 2 3; do
  d="$OUT/regret_a10_s$s"
  [[ -f "$d/qtable.pkl" ]] || continue
  [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval regret_a10_s$s"; continue; }
  throttle
  OPPONENTS=random,eval_tag,lag,man,sta,nit $PY evaluate.py "$d" \
      > "$LOGS/foldvic_eval_regret_a10_s$s.log" 2>&1 &
done
wait
echo "LOWDOSE BATCH DONE"
