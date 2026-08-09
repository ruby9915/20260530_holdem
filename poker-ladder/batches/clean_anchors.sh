#!/usr/bin/env bash
# 클린 재실행분 슬럼봇 앵커 4런 (2웨이브 × 2동시 — 외부 예의 유지)
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
LOGS="$(cd ../results/_logs && pwd)"
OUT=../results/35_fold_vic
export PYTHONIOENCODING=utf-8
a() { local n=$1
  grep -q '==>' "$LOGS/slumbot_bf_$n.log" 2>/dev/null && { echo "SKIP $n"; return 0; }
  $PY slumbot_eval.py "$OUT/$n" 4000 > "$LOGS/slumbot_bf_$n.log" 2>&1; }
a regret_a30_s1 &
a regret_a100_s1 &
wait
a regret_a10_s1 &
a regret_cfr_a30_s1 &
wait
echo "CLEAN ANCHORS DONE"
