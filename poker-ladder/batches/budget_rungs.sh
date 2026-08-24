#!/usr/bin/env bash
# 37번 — 학습 예산 눈금 실험 (사전 등록: 실험일지 36절 (6), results/README 37번 절, 커밋 fcae1f8)
# pure/off/chec_a30 × 예산 {15M, 5M, 2.5M, 1M} × s1~s5 = 60런 + 각 런 정밀평가 자동 체인.
# 온도 스케줄은 train.py가 예산 비례(진행률 기반)라 --episodes만 바꾸면 신축 충족.
# 체크포인트 밀도 관례 유지: eval-every = ckpt-every = episodes/250.
# 발사 순서: 15M 우선(최장 ~21h가 벽시계를 지배) → 5M → 2.5M → 1M.
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/37_budget_rungs
LOGS="$(cd ../results/_logs && pwd)"
MAXJOBS=${MAXJOBS:-12}
export PYTHONIOENCODING=utf-8
mkdir -p "$OUT"
declare -A PIDNAME
FAILED=()

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }

run1() { # name, episodes, every, arm-args...
  local name=$1 eps=$2 every=$3; shift 3
  local d="$OUT/$name"
  if [ ! -f "$d/qtable.pkl" ]; then
    $PY train.py --out "$d" --card ehs20 --actions A12 --opponent cfrplus \
        --episodes "$eps" --eval-every "$every" --ckpt-every "$every" "$@" \
        >> "$LOGS/budget_${name}.log" 2>&1 || { echo "TRAIN FAIL $name"; return 1; }
  fi
  if [ ! -f "$d/precision_eval.csv" ]; then
    OPPONENTS=cfrplus,random,eval_tag N_GAMES=100000 N_REPEAT=5 \
      $PY evaluate.py "$d" >> "$LOGS/budget_eval_${name}.log" 2>&1 \
      || { echo "EVAL FAIL $name"; return 1; }
  fi
}

arm_args() { case $1 in
  pure) echo "--credit pure";;
  off) echo "--credit prop --vic off";;
  chec_a30) echo "--credit prop --vic checktime --vic-amount 0.30";;
esac; }

for tier in "15000000 b15m 60000" "5000000 b5m 20000" "2500000 b2p5m 10000" "1000000 b1m 4000"; do
  set -- $tier; eps=$1 tag=$2 every=$3
  for arm in pure off chec_a30; do
    for s in 1 2 3 4 5; do
      name="${arm}_${tag}_s${s}"
      throttle
      run1 "$name" "$eps" "$every" $(arm_args $arm) --seed "$s" &
      PIDNAME[$!]=$name
    done
  done
done

for pid in "${!PIDNAME[@]}"; do
  wait "$pid" || FAILED+=("${PIDNAME[$pid]}")
done
if (( ${#FAILED[@]} )); then echo "BUDGET RUNGS FAILED: ${FAILED[*]}"; else echo "BUDGET RUNGS ALL DONE"; fi
