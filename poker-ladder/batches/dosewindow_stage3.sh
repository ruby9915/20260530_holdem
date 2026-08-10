#!/usr/bin/env bash
# 3단계 용량 창 지도: regret_cfr α_f ∈ {0.1, 0.5} × s1–5 = 10런
# (사전 등록: results/35_fold_vic/README.md 3단계 절 — 저자 승인 2026-08-10 "ㄱㄱ")
# 설정 = 2단계 CFR 웨이브와 비트 동일(7.5M eps·chec_a30 베이스), 변수 = --vic-fold-amount 만.
# 체인: 학습 10(MAXJOBS 10) → 정밀평가 7상대×100k×5 → 슬럼봇 대표 2런(a10_s1·a50_s1)
# 재실행 = 이어하기 (qtable.pkl 존재 시 SKIP, 죽은 런은 ckpt 재개).
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/35_fold_vic
LOGS="$(cd ../results/_logs && pwd)"
MAXJOBS=${MAXJOBS:-10}
export PYTHONIOENCODING=utf-8
log() { echo "[stage3 $(date '+%F %T')] $*" >> "$LOGS/dosewindow_stage3.log"; }
declare -A PID2NAME=()
FAILED=()
throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then echo "SKIP $name"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/foldvic_$name.log"
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --opponent cfrplus --episodes 7500000 --eval-every 30000 \
            --ckpt-every 30000 \
            --credit prop --vic checktime --vic-amount 0.30 "$@" \
            >> "$LOGS/foldvic_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }

log "학습 웨이브 발사 (a10·a50 × s1-5)"
for s in 1 2 3 4 5; do
  run "regret_cfr_a10_s$s" --vic-fold regret --vic-fold-amount 0.1 --seed $s
  run "regret_cfr_a50_s$s" --vic-fold regret --vic-fold-amount 0.5 --seed $s
done
for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
(( ${#FAILED[@]} )) && log "TRAIN FAILED: ${FAILED[*]}" || log "학습 10런 완료 — 정밀평가 발사"

for cond in a10 a50; do
  for s in 1 2 3 4 5; do
    d="$OUT/regret_cfr_${cond}_s$s"
    [[ -f "$d/qtable.pkl" ]] || continue
    [[ -f "$d/precision_eval.csv" ]] && { echo "SKIP eval ${cond}_s$s"; continue; }
    throttle
    OPPONENTS=cfrplus,random,eval_tag,lag,man,sta,nit $PY evaluate.py "$d" \
        > "$LOGS/foldvic_eval_regret_cfr_${cond}_s$s.log" 2>&1 &
  done
done
wait
log "정밀평가 완료 — 슬럼봇 대표 앵커 2런 (동시 2 예의 준수)"
$PY slumbot_eval.py "$OUT/regret_cfr_a10_s1" 4000 > "$LOGS/slumbot_bf_regret_cfr_a10_s1.log" 2>&1 &
$PY slumbot_eval.py "$OUT/regret_cfr_a50_s1" 4000 > "$LOGS/slumbot_bf_regret_cfr_a50_s1.log" 2>&1 &
wait
log "STAGE3 DONE"
echo "STAGE3 DONE"
