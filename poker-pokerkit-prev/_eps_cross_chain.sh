#!/usr/bin/env bash
# 36번 ε-greedy 교차 자동 체인 (학습 10런 → 정밀평가 100k×5 → ZCA 지문 검사)
# 사전 등록: 실험일지 36절 (5) / results/README 36번 절 (커밋 fcae1f8)
set -u
cd "$(dirname "$0")"
PY=../.venv/Scripts/python.exe
OUT=../results/36_eps_cross
LOGS="$(cd ../results/_logs && pwd)"
MAXJOBS=${MAXJOBS:-10}
export PYTHONIOENCODING=utf-8
mkdir -p "$OUT"
FAILED=()

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }

train1() { local name=$1 mode=$2 alpha=$3 s=$4
  grep -q "pickle saved" "$LOGS/eps_t_${name}.log" 2>/dev/null && { echo "SKIP train $name"; return 0; }
  $PY _run_eps_seed.py "$mode" "$alpha" "$s" "$OUT/$name" > "$LOGS/eps_t_${name}.log" 2>&1; }

declare -A PIDNAME
for s in 1 2 3 4 5; do
  throttle; train1 "off_s$s" off 0 "$s" & PIDNAME[$!]=off_s$s
  throttle; train1 "fixed_k5_s$s" fixed 5 "$s" & PIDNAME[$!]=fixed_k5_s$s
done
for pid in "${!PIDNAME[@]}"; do wait "$pid" || FAILED+=("train:${PIDNAME[$pid]}"); done

# 정밀 평가 (100k×5, vs Random + vs TAG) — 동시 5
eval1() { local name=$1
  grep -q "==>" "$LOGS/eps_e_${name}.log" 2>/dev/null && { echo "SKIP eval $name"; return 0; }
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 $PY eval_persona_100k.py "36_eps_cross/$name" \
    > "$LOGS/eps_e_${name}.log" 2>&1; }
declare -A EPID
for s in 1 2 3 4 5; do
  for name in "off_s$s" "fixed_k5_s$s"; do
    while (( $(jobs -r | wc -l) >= 5 )); do sleep 5; done
    eval1 "$name" & EPID[$!]=$name
  done
done
for pid in "${!EPID[@]}"; do wait "$pid" || FAILED+=("eval:${EPID[$pid]}"); done

# ZCA 지문 (P1 판정 데이터)
ARGS=""
for s in 1 2 3 4 5; do
  ARGS="$ARGS off_s$s=$OUT/off_s$s/eval_results.pkl f5_s$s=$OUT/fixed_k5_s$s/eval_results.pkl"
done
$PY analyze_qcheck.py $ARGS > "$LOGS/eps_qcheck.log" 2>&1 || FAILED+=("qcheck")

if (( ${#FAILED[@]} )); then echo "EPS CROSS FAILED: ${FAILED[*]}"; else echo "EPS CROSS ALL DONE"; fi
