#!/usr/bin/env bash
# 3모델×7상대 행렬의 슬럼봇 열 (저자 지시 2026-08-25 "일단 슬럼봇은 바로 돌려봐")
# 대상: 32번 k20_a12_cfr 계열 pure/off/chec_a30 × s1~s5 = 15런(행렬 본체) 우선,
#       fixed5 × s1~s5 = 5런(대표 교체 대비 예비)은 후순위.
# 프로토콜: 시드당 10,000핸드 통일(시드 6→5 축소 결정과 세트 — 행렬_3x7_cfr학습.md).
# 외부 서비스 예의: 동시 2런 유지(기존 캠페인과 동일). 예상 ~42시간.
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
BASE=../results/32_ehs_k20/k20_a12_cfr
LOGS="$(cd ../results/_logs && pwd)"
N=10000
export PYTHONIOENCODING=utf-8
done_check() { grep -q "==>" "$LOGS/slumbot_mx_$1.log" 2>/dev/null; }
run1() { local name=$1 dir=$2
         done_check "$name" && { echo "SKIP $name"; return 0; }
         $PY slumbot_eval.py "$dir" $N > "$LOGS/slumbot_mx_$name.log" 2>&1; }

for cond in pure off chec_a30 fixed5; do
  for wave in "s1 s2" "s3 s4" "s5"; do
    pids=()
    for s in $wave; do
      run1 "${cond}_${s}" "$BASE/${cond}_${s}" &
      pids+=($!)
    done
    wait "${pids[@]}"
  done
  echo "MX COND DONE: $cond"
done
echo "MATRIX SLUMBOT DONE"
