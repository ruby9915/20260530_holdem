#!/usr/bin/env bash
# 주말 자율 2단계 (구 foldvic_regret_chain.sh 대체 — 구 체인은 2026-08-07 21:2x 정지 확인):
#   TAG regret 배치(학습+평가) 종료 감지 (3회 연속 0, 10분 간격)
#   → foldvic_regret.sh 치유 재실행 (실패 런 ckpt 재개·누락 평가 보충)
#   → CFR 웨이브(MAXJOBS=10) + 저용량 팔·qtraj(MAXJOBS=3) 동시 발사 (계 13 = 관례 상한)
# 로그: results/_logs/weekend_stage2.log
set -u
cd "$(dirname "$0")"
LOGS="../../results/_logs"
log() { echo "[stage2 $(date '+%F %T')] $*" >> "$LOGS/weekend_stage2.log"; }

count_tag() {
  powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.CommandLine -match '(train|evaluate)\\.py' -and \$_.CommandLine -match 'regret_a30_|regret_a100_' }).Count" \
    2>/dev/null | tr -d '\r\n '
}

log "가동 — TAG regret 배치(학습+평가) 종료 대기"
streak=0
while (( streak < 3 )); do
  c=$(count_tag)
  [[ -z "$c" ]] && c=99
  if [[ "$c" == "0" ]]; then streak=$((streak+1)); else streak=0; fi
  log "TAG regret 프로세스 $c개 (streak $streak/3)"
  (( streak < 3 )) && sleep 600
done

log "TAG 웨이브 종료 감지 — 치유 재실행"
bash foldvic_regret.sh >> "$LOGS/weekend_stage2.log" 2>&1
log "치유 완료 — CFR 웨이브(10) + 저용량 팔(3) 발사"
MAXJOBS=10 bash foldvic_regret_cfr.sh >> "$LOGS/weekend_stage2.log" 2>&1 &
CFR_PID=$!
MAXJOBS=3 bash foldvic_lowdose.sh >> "$LOGS/weekend_stage2.log" 2>&1 &
LOW_PID=$!
wait "$CFR_PID" "$LOW_PID"
log "stage2 전체 완료"
