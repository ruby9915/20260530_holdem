#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# 사다리 5단: 학습 상대 TAG → CFR+ 동결 전략 (개정 v2 — (K20, A12, CFR) 칸).
# 기준선 = 2단 (K20·A12·TAG). 바뀌는 변수 하나: --opponent cfrplus.
# 평가 = ID(vs cfrplus) + 홀드아웃(random·eval_tag) — 일반화 주장 없음.
# 사전 조건: 봇 동결(hunl_frozen_k50.npz) + 품질 게이트 통과.
# 실행: bash batches/rung5_cfropp.sh  / 진행률: ladder_rung5_*
#
# 재실행 = 이어하기. 이미 qtable.pkl 이 있는 런은 건너뛰고, 죽은 런만
# out/ckpt.pkl 에서 재개한다 (재개본의 최종 Q 는 무중단 런과 비트 동일).
# 로그는 덮어쓰지 않고 이어붙인다 — 앞 세션의 증거를 지우지 않기 위해.
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/32_ehs_k20/k20_a12_cfr
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
export PYTHONIOENCODING=utf-8     # 복구 안내(한국어)가 cp949 로 깨지는 것 방지
mkdir -p "$LOGS"

declare -A PID2NAME=()
FAILED=()

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        if [[ -f "$OUT/$name/qtable.pkl" ]]; then
          echo "SKIP $name (qtable.pkl 존재)"; return; fi
        throttle
        echo "=== session $(date '+%F %T') ===" >> "$LOGS/ladder_rung5_$name.log"
        $PY train.py --out "$OUT/$name" --card ehs20 --actions A12 \
            --opponent cfrplus --episodes 7500000 --eval-every 30000 \
            --ckpt-every 30000 "$@" \
            >> "$LOGS/ladder_rung5_$name.log" 2>&1 &
        PID2NAME[$!]=$name; }

for s in 1 2 3 4 5; do
  run "off_s$s"      --credit prop --vic off --seed $s
  run "fixed5_s$s"   --credit prop --vic fixed --vic-amount 5 --seed $s
  run "chec_a30_s$s" --credit prop --vic checktime --vic-amount 0.30 --seed $s
  run "pure_s$s"     --credit pure --seed $s
done

for pid in "${!PID2NAME[@]}"; do
  wait "$pid" || FAILED+=("${PID2NAME[$pid]}")
done
if (( ${#FAILED[@]} )); then
  echo "RUNG5 TRAIN FAILED: ${FAILED[*]}"
  echo "  -> 로그 확인 후 같은 명령으로 재실행하면 ckpt 에서 이어간다"
else
  echo "RUNG5 TRAIN DONE"
fi

for d in "$OUT"/*/; do
  name=$(basename "$d")
  [[ -f "$d/qtable.pkl" ]] || { echo "SKIP eval $name (qtable.pkl 없음)"; continue; }
  throttle
  OPPONENTS=cfrplus,random,eval_tag $PY evaluate.py "$d" \
      > "$LOGS/ladder_rung5_eval_$name.log" 2>&1 &
done
wait
echo "RUNG5 BATCH DONE"
