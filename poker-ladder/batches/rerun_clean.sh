#!/usr/bin/env bash
# 유령 분모 버그(레거시 회계 누수) 수정 후 전량 클린 재실행 (2026-08-08)
#   0) 자가 게이트: cfrplus + regret α_f=1.0 250k 스모크 — 구코드 크래시 구간(≈180k) 통과 확인
#   1) 웨이브 1: TAG 10런(MAXJOBS 10) + 저용량 3런·qtraj(MAXJOBS 3) 병행 (계 13)
#   2) 웨이브 2: CFR 10런(MAXJOBS 10)
# 구코드 산출물은 oldghost_* 로 보존됨. 로그: results/_logs/rerun_clean.log
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS=../results/_logs
export PYTHONIOENCODING=utf-8
log() { echo "[rerun $(date '+%F %T')] $*" >> "$LOGS/rerun_clean.log"; }

log "자가 게이트 스모크 시작 (cfrplus, regret α_f=1.0, 250k)"
if $PY train.py --out ../results/_smoke/regret_fix_gate --card ehs20 --actions A12 \
      --opponent cfrplus --episodes 250000 --eval-every 250000 --ckpt-every 250000 \
      --credit prop --vic checktime --vic-amount 0.30 \
      --vic-fold regret --vic-fold-amount 1.0 --seed 1 \
      > "$LOGS/rerun_gate_smoke.log" 2>&1 \
   && [[ -f ../results/_smoke/regret_fix_gate/qtable.pkl ]]; then
  log "게이트 통과 — 웨이브 1 발사 (TAG 10 + 저용량 3 + qtraj)"
else
  log "게이트 실패 — 중단 (rerun_gate_smoke.log 확인)"
  exit 1
fi

cd batches
MAXJOBS=10 bash foldvic_regret.sh >> "$LOGS/rerun_clean.log" 2>&1 &
A=$!
MAXJOBS=3 bash foldvic_lowdose.sh >> "$LOGS/rerun_clean.log" 2>&1 &
B=$!
wait "$A" "$B"
log "웨이브 1 완료 — CFR 웨이브(10) 발사"
MAXJOBS=10 bash foldvic_regret_cfr.sh >> "$LOGS/rerun_clean.log" 2>&1
log "전량 클린 재실행 완료"
