#!/usr/bin/env bash
# 야간 검증 체인 (실험일지 32절 (4)) — E1→E2→E3→E4→V→E5→E6 순서 고정, 분기 없음.
# 각 단계: 병렬 launch → 완료 폴링(20s) → 다음. 단계별 최대 대기 후 강행(전체 사수).
cd "$(dirname "$0")"
PY=../.venv/Scripts/python.exe
L=../results/_logs
ts() { date +%H:%M:%S; }
say() { echo "[$(ts)] $*"; }

wait_files() { # $1=glob pattern(quoted) $2=grep pat $3=target count $4=max loops(20s)
  local n=0
  while true; do
    local c=$(grep -l "$2" $1 2>/dev/null | wc -l)
    [ "$c" -ge "$3" ] && { say "  wait ok: $c/$3"; return 0; }
    n=$((n+1)); [ "$n" -ge "$4" ] && { say "  WAIT TIMEOUT ($c/$3) — 강행"; return 1; }
    sleep 20
  done
}
wait_total() { # $1=glob $2=grep pat $3=total lines $4=max loops
  local n=0
  while true; do
    local c=$(cat $1 2>/dev/null | grep -c "$2")
    [ "$c" -ge "$3" ] && { say "  wait ok: $c/$3"; return 0; }
    n=$((n+1)); [ "$n" -ge "$4" ] && { say "  WAIT TIMEOUT ($c/$3) — 강행"; return 1; }
    sleep 20
  done
}

say "===== E1: 올체크-핸드 격리 (checktime a30 × {invested_only,allcheck_only} × s1-5) ====="
for s in 1 2 3 4 5; do for ap in invested_only allcheck_only; do
  nohup $PY _run_potfrac_seed.py checktime 30 $s ../results/30_vic_potfrac_seedsweep/chec_a30_${ap}_s${s} single $ap > $L/night_e1t_${ap}_s${s}.log 2>&1 &
done; done
wait_files "$L/night_e1t_*.log" "pickle saved" 10 90
say "E1 평가 launch"
for s in 1 2 3 4 5; do for ap in invested_only allcheck_only; do
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 nohup $PY eval_persona_100k.py 30_vic_potfrac_seedsweep/chec_a30_${ap}_s${s} > $L/night_e1e_${ap}_s${s}.log 2>&1 &
done; done
wait_total "$L/night_e1e_*.log" "==>" 10 60

say "===== E2: 홀드아웃 다중 OOD ({off,chec_a30,term_a30} × s1-5 × LAG/MAN/STA/NIT, α 사전고정) ====="
for s in 1 2 3 4 5; do for run in off chec_a30 term_a30; do
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 nohup $PY _eval_vs_persona.py 30_vic_potfrac_seedsweep/${run}_s${s} lag man sta nit > $L/night_e2_${run}_s${s}.log 2>&1 &
done; done
wait_total "$L/night_e2_*.log" "==>" 60 90

say "===== E3: fixed-K sweep (K{5,20,60}칩 × s1-5) ====="
for s in 1 2 3 4 5; do for k in 5 20 60; do
  nohup $PY _run_potfrac_seed.py fixed $k $s ../results/30_vic_potfrac_seedsweep/fixed_k${k}_s${s} single all > $L/night_e3t_k${k}_s${s}.log 2>&1 &
done; done
wait_files "$L/night_e3t_*.log" "pickle saved" 15 90
say "E3 평가 launch"
for s in 1 2 3 4 5; do for k in 5 20 60; do
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 nohup $PY eval_persona_100k.py 30_vic_potfrac_seedsweep/fixed_k${k}_s${s} > $L/night_e3e_k${k}_s${s}.log 2>&1 &
done; done
wait_total "$L/night_e3e_*.log" "==>" 15 60

say "===== E4: 메커니즘 진단 (argmax-flip 분류 + 행동 프로파일) ====="
for s in 1 2 3 4 5; do
  $PY analyze_potvic.py ../results/30_vic_potfrac_seedsweep/off_s${s}/eval_results.pkl ../results/30_vic_potfrac_seedsweep/chec_a30_s${s}/eval_results.pkl > $L/night_e4_flip_s${s}.log 2>&1
done
for run in off_s1 chec_a30_s1 term_a30_s1; do
  $PY _profile_behavior.py 30_vic_potfrac_seedsweep/${run} 20000 > $L/night_e4_prof_${run}.log 2>&1
done
say "E4 done"

say "===== V: 이론 toy (거울상 V1 + 확률적 ε V2) ====="
(cd ../zca_theory && $PY verify_toy_mirror.py > $L/night_v1_mirror.log 2>&1 && $PY verify_toy_stochastic_eps.py > $L/night_v2_stoch.log 2>&1)
say "V done"

say "===== E5: 저-α checktime ({4,8,15}% × s1-5) ====="
for s in 1 2 3 4 5; do for a in 4 8 15; do
  nohup $PY _run_potfrac_seed.py checktime $a $s ../results/30_vic_potfrac_seedsweep/chec_a${a}_s${s} single all > $L/night_e5t_a${a}_s${s}.log 2>&1 &
done; done
wait_files "$L/night_e5t_*.log" "pickle saved" 15 90
say "E5 평가 launch"
for s in 1 2 3 4 5; do for a in 4 8 15; do
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 nohup $PY eval_persona_100k.py 30_vic_potfrac_seedsweep/chec_a${a}_s${s} > $L/night_e5e_a${a}_s${s}.log 2>&1 &
done; done
wait_total "$L/night_e5e_*.log" "==>" 15 60

say "===== E6: 스킴 일반성 (chec_a30 × {cycle,mixed} × s1-5) ====="
for s in 1 2 3 4 5; do for sch in cycle mixed; do
  nohup $PY _run_potfrac_seed.py checktime 30 $s ../results/30_vic_potfrac_seedsweep/chec_a30_${sch}_s${s} $sch all > $L/night_e6t_${sch}_s${s}.log 2>&1 &
done; done
wait_files "$L/night_e6t_*.log" "pickle saved" 10 120
say "E6 평가 launch"
for s in 1 2 3 4 5; do for sch in cycle mixed; do
  N_REPEAT=5 N_GAMES=100000 BASE_SEED=1000 nohup $PY eval_persona_100k.py 30_vic_potfrac_seedsweep/chec_a30_${sch}_s${s} > $L/night_e6e_${sch}_s${s}.log 2>&1 &
done; done
wait_total "$L/night_e6e_*.log" "==>" 10 60

say "NIGHT-CHAIN-DONE"
