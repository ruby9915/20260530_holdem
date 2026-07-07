#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# K=8 레거시 시리즈 재현 배치 (신규 코드 poker-ladder, 전 조건 clean)
# 대상: 하중 있는 26~31번 라인. 제외: 19이전·21c(셀프플레이)·24(8M)·25(온도스윕).
# off_s{1-5}, chec_a30_s{1-5} 는 results/32_ehs_k20/rung0/ 재사용 (중복 생략).
# 실행: bash batches/replicate_k8.sh   (사다리 1단 완료 후 — 코어 경합 방지)
# 진행률: progress.py 감시 창에 ladder_rep_* 로 표시
# ─────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
OUT=../results/33_ladder_replicate_k8
LOGS=../results/_logs
MAXJOBS=${MAXJOBS:-12}
mkdir -p "$LOGS"

throttle() { while (( $(jobs -r | wc -l) >= MAXJOBS )); do sleep 5; done; }
run() { local name=$1; shift
        throttle
        $PY train.py --out "$OUT/$name" --card legacy8 --eval-every 8000 --episodes 2000000 "$@" \
            > "$LOGS/ladder_rep_$name.log" 2>&1 & }

SEEDS="1 2 3 4 5"

# ── 30번: fixed-K 용량-반응 (fixed1 = 28번 single/VIC-on 겸용) ──
for s in $SEEDS; do for k in 1 5 20 60; do
  run "fixed${k}_s$s" --credit prop --vic fixed --vic-amount $k --seed $s
done; done

# ── 30번: checktime α 스윕 (a30 은 rung0 재사용으로 생략) ──
for s in $SEEDS; do for a in 0.04 0.08 0.10 0.15 0.20 0.50; do
  run "chec_a${a#0.}_s$s" --credit prop --vic checktime --vic-amount $a --seed $s
done; done

# ── 30번: terminal 표본점 ──
for s in $SEEDS; do for a in 0.10 0.30; do
  run "term_a${a#0.}_s$s" --credit prop --vic terminal --vic-amount $a --seed $s
done; done

# ── E1 격리 (chec_a30) ──
for s in $SEEDS; do
  run "chec_a30_inv_s$s" --credit prop --vic checktime --vic-amount 0.30 --pot-apply invested_only --seed $s
  run "chec_a30_alc_s$s" --credit prop --vic checktime --vic-amount 0.30 --pot-apply allcheck_only --seed $s
done

# ── 28clean 2×3 나머지: cycle/mixed × {on=fixed1, off} ──
for s in $SEEDS; do for sc in cycle mixed; do
  run "${sc}_on_s$s"  --credit prop --scheme $sc --vic fixed --vic-amount 1 --seed $s
  run "${sc}_off_s$s" --credit prop --scheme $sc --vic off --seed $s
done; done

# ── 29 PURE: single-TAG + mixed ──
for s in $SEEDS; do
  run "pure_single_s$s" --credit pure --seed $s
  run "pure_mixed_s$s"  --credit pure --scheme mixed --seed $s
done

# ── 31 E8 경쟁 처방 (vic off 위에 처방만) ──
for s in $SEEDS; do
  run "opt50_s$s"  --credit prop --vic off --q-init 50 --seed $s
  run "slowT2_s$s" --credit prop --vic off --temp-floor 2.0 --seed $s
  run "unif5_s$s"  --credit prop --vic off --uniform-penalty 5 --seed $s
done

# ── 28b/28c: random 상대 학습 ±VIC ──
for s in $SEEDS; do
  run "rand_off_s$s"    --credit prop --vic off --opponent random --seed $s
  run "rand_fixed1_s$s" --credit prop --vic fixed --vic-amount 1 --opponent random --seed $s
done

# ── 26: 페르소나 단독 (레거시 = CHECK 1칩 시대 → fixed1) ──
for s in $SEEDS; do for p in lag man sta nit; do
  run "persona_${p}_s$s" --credit prop --vic fixed --vic-amount 1 --opponent $p --seed $s
done; done

wait
echo "REPLICATE-K8 TRAIN DONE"

# ── 정밀 평가 (100k×5, vsRand/vsTAG) ──
for d in "$OUT"/*/; do
  name=$(basename "$d")
  throttle
  $PY evaluate.py "$d" > "$LOGS/ladder_rep_eval_$name.log" 2>&1 &
done
wait
echo "REPLICATE-K8 BATCH DONE"
