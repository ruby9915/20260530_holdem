#!/usr/bin/env bash
# 주말 자율 슬럼봇 앵커 (저자 포괄 승인 2026-08-07, 기한 월 06:00 발사 마감):
#   백필 종료 감지(slumbot_eval 프로세스 0 × 3연속, 15분 간격 — 외부 서비스 예의 2동시 유지)
#   → 1웨이브: regret_a30_s1·regret_a100_s1 (TAG 대표런)
#   → 기한부 추가: regret_a10_s1·regret_cfr_a30_s1·regret_cfr_a100_s1 (준비된 것부터 2개씩)
# 로그: results/_logs/weekend_slumbot.log, 결과: slumbot_bf_<name>.log
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS=../results/_logs
OUT=../results/35_fold_vic
export PYTHONIOENCODING=utf-8
log() { echo "[slumbot-w $(date '+%F %T')] $*" >> "$LOGS/weekend_slumbot.log"; }
CUTOFF=$(date -d '2026-08-10 06:00:00' +%s)

count_slumbot() {
  powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.CommandLine -match 'slumbot_eval' }).Count" \
    2>/dev/null | tr -d '\r\n '
}
anchor() { local name=$1 dir=$2
  grep -q '==>' "$LOGS/slumbot_bf_$name.log" 2>/dev/null && { log "SKIP $name (완료)"; return 0; }
  [[ -f "$dir/qtable.pkl" ]] || { log "SKIP $name (qtable 없음)"; return 0; }
  log "앵커 시작 $name"
  $PY slumbot_eval.py "$dir" 4000 > "$LOGS/slumbot_bf_$name.log" 2>&1
  log "앵커 종료 $name"
}

log "가동 — 백필 종료 대기"
streak=0
while (( streak < 3 )); do
  c=$(count_slumbot)
  [[ -z "$c" ]] && c=99
  if [[ "$c" == "0" ]]; then streak=$((streak+1)); else streak=0; fi
  (( streak < 3 )) && sleep 900
done
log "백필 종료 감지"

while [[ ! -f "$OUT/regret_a30_s1/qtable.pkl" || ! -f "$OUT/regret_a100_s1/qtable.pkl" ]]; do
  (( $(date +%s) >= CUTOFF )) && { log "기한 도달 — 1웨이브 대기 중단"; break; }
  sleep 600
done
anchor regret_a30_s1 "$OUT/regret_a30_s1" &
anchor regret_a100_s1 "$OUT/regret_a100_s1" &
wait
log "1웨이브 종료"

pending=(regret_a10_s1 regret_cfr_a30_s1 regret_cfr_a100_s1)
while (( ${#pending[@]} )); do
  (( $(date +%s) >= CUTOFF )) && { log "기한 도달 — 잔여 생략: ${pending[*]}"; break; }
  batch=(); rest=()
  for n in "${pending[@]}"; do
    if [[ -f "$OUT/$n/qtable.pkl" && ${#batch[@]} -lt 2 ]]; then batch+=("$n"); else rest+=("$n"); fi
  done
  if (( ${#batch[@]} )); then
    for n in "${batch[@]}"; do anchor "$n" "$OUT/$n" & done
    wait
    pending=("${rest[@]:-}")
    [[ -z "${pending[0]:-}" ]] && pending=()
  else
    sleep 900
  fi
done
log "주말 앵커 전체 완료"
