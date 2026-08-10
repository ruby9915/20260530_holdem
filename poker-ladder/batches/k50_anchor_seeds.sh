#!/usr/bin/env bash
# K50 보류 판정용 슬럼봇 앵커 증량 (평가만 — 학습 0회, 기존 3단 s2·s3 모델 사용)
# 근거: 보강 37 K50-TAG chec −1090이 "천장 전 셀 ~−1900" 문언 밖 첫 관측(1.6σ·s1 단일)
#   → 시드 운인지 판별. 저자 자원 활용 승인 2026-08-10 ("남는 자원 최대로").
# 외부 서비스 예의: 동시 2런 유지 (stage3 대표 앵커와 시간대 비중첩 — 그쪽은 ~12h 후).
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
K50=../results/32_ehs_k20/k50_a12
LOGS="$(cd ../results/_logs && pwd)"
export PYTHONIOENCODING=utf-8
done_check() { grep -q "==>" "$LOGS/slumbot_k50_$1.log" 2>/dev/null; }
run1() { local name=$1 dir=$2
         done_check "$name" && { echo "SKIP $name"; return 0; }
         $PY slumbot_eval.py "$dir" 4000 > "$LOGS/slumbot_k50_$name.log" 2>&1; }

for wave in "chec_s2:$K50/chec_a30_s2 chec_s3:$K50/chec_a30_s3" \
            "off_s2:$K50/off_s2 off_s3:$K50/off_s3"; do
  pids=()
  for item in $wave; do
    run1 "${item%%:*}" "${item#*:}" &
    pids+=($!)
  done
  wait "${pids[@]}"
  echo "K50 WAVE DONE: $wave"
done
echo "K50 ANCHOR SEEDS DONE"
