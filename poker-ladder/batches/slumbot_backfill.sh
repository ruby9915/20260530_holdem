#!/usr/bin/env bash
# 슬럼봇 절대 앵커 공백 전수 채우기 (저자 지시 2026-08-07: "자원이 허락하는 한 전부")
# 외부 서비스 예의: 동시 2런, 우선순위 웨이브. 각 4k핸드 ~1.5-2h.
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS=../results/_logs
export PYTHONIOENCODING=utf-8

done_check() { grep -q "==>" "$LOGS/slumbot_bf_$1.log" 2>/dev/null; }
run1() { local name=$1 dir=$2
         done_check "$name" && { echo "SKIP $name"; return 0; }
         $PY slumbot_eval.py "$dir" 4000 > "$LOGS/slumbot_bf_$name.log" 2>&1; }

# 웨이브 정의: 이름:경로 (우선순위순, 2개씩)
WAVES=(
 "k50_off_s1:../results/32_ehs_k20/k50_a12/off_s1 k50_chec_s1:../results/32_ehs_k20/k50_a12/chec_a30_s1"
 "k50cfr_off_s1:../results/32_ehs_k20/k50_a12_cfr/off_s1 k50cfr_chec_s1:../results/32_ehs_k20/k50_a12_cfr/chec_a30_s1"
 "fixed8_s1:../results/34_threshold_stage0/gateAB_k20_a12/fixed8_s1 chec_a800_s1:../results/34_threshold_stage0/gateC_legacy8/chec_a800_s1"
 "rung0_off_s1:../results/32_ehs_k20/rung0/off_s1 rung0_chec_s1:../results/32_ehs_k20/rung0/chec_a30_s1"
 "fold_a30_s1:../results/35_fold_vic/fold_a30_s1 fixed240_s1:../results/34_threshold_stage0/gateCK_legacy8/fixed240_s1"
 "rep33_fixed5_s1:../results/33_ladder_replicate_k8/fixed5_s1"
)
for wave in "${WAVES[@]}"; do
  pids=()
  for item in $wave; do
    name="${item%%:*}"; dir="${item#*:}"
    run1 "$name" "$dir" &
    pids+=($!)
  done
  wait "${pids[@]}"
  echo "WAVE DONE: $wave"
done
echo "SLUMBOT BACKFILL DONE"
