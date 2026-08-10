#!/usr/bin/env bash
# K20 비교군 슬럼봇 앵커 증량 (평가만 — K50 판정의 병목이 K20 단일 시드로 이동)
# 근거: K50 3시드 완성(chec 평균 −1257·off −1533, 전부 옛 대역 밖) vs K20 단일 시드(±420)
#   → 1.5σ 정체. K20 chec_a30·off s2·s3 앵커로 비교군 표본 대칭화.
# 저자 자원 활용 승인 2026-08-10 범위 내(측정만). 동시 2런 예의 유지, stage3 앵커와 비중첩.
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
K20=../results/32_ehs_k20/k20_a12
LOGS="$(cd ../results/_logs && pwd)"
export PYTHONIOENCODING=utf-8
done_check() { grep -q "==>" "$LOGS/slumbot_k20_$1.log" 2>/dev/null; }
run1() { local name=$1 dir=$2
         done_check "$name" && { echo "SKIP $name"; return 0; }
         $PY slumbot_eval.py "$dir" 4000 > "$LOGS/slumbot_k20_$name.log" 2>&1; }

for wave in "chec_s2:$K20/chec_a30_s2 chec_s3:$K20/chec_a30_s3" \
            "off_s2:$K20/off_s2 off_s3:$K20/off_s3"; do
  pids=()
  for item in $wave; do
    run1 "${item%%:*}" "${item#*:}" &
    pids+=($!)
  done
  wait "${pids[@]}"
  echo "K20 WAVE DONE: $wave"
done
echo "K20 ANCHOR SEEDS DONE"
