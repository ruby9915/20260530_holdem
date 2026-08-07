#!/usr/bin/env bash
# 자동 체인 (저자 2일 부재 대응, 2026-08-07 지시): TAG regret 배치 종료 감지
#   → foldvic_regret.sh 치유 재실행 (실패 런 ckpt 재개·누락 평가 보충, 완료면 즉시 통과)
#   → foldvic_regret_cfr.sh 자동 발사 (CFR 이식 웨이브)
# 종료 감지 = regret_a30_/regret_a100_ 경로를 문 python 프로세스가 3회 연속(10분 간격) 0개.
# 로그: results/_logs/foldvic_chain.log
set -u
cd "$(dirname "$0")"
LOGS="../../results/_logs"
log() { echo "[chain $(date '+%F %T')] $*" >> "$LOGS/foldvic_chain.log"; }

count_regret() {
  powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.CommandLine -match 'regret_a30_|regret_a100_' }).Count" \
    2>/dev/null | tr -d '\r\n '
}

log "체인 가동 — TAG regret 배치 종료 대기"
streak=0
while (( streak < 3 )); do
  c=$(count_regret)
  [[ -z "$c" ]] && c=99                # powershell 실패 시 보수적으로 '진행 중' 취급
  if [[ "$c" == "0" ]]; then streak=$((streak+1)); else streak=0; fi
  log "regret 프로세스 $c개 (streak $streak/3)"
  (( streak < 3 )) && sleep 600
done

log "TAG 웨이브 종료 감지 — 치유 재실행 시작"
bash foldvic_regret.sh >> "$LOGS/foldvic_chain.log" 2>&1
log "치유 재실행 종료 — CFR 웨이브 발사"
bash foldvic_regret_cfr.sh >> "$LOGS/foldvic_chain.log" 2>&1
log "체인 완료"
