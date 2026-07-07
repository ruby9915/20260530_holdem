# -*- coding: utf-8 -*-
"""임계 분포 검증 (②-3) — "임계는 점이 아니라 분포"의 정량 예측 vs 관측 대조.

원리:
  checktime α 모드에서 Q(CHECK) = [α/(α+1)]·μ_C (팟-불변)  →  μ̂_C = Q(CHECK)·(1+α)/α
  팟-비례 레이즈의 credit 지분은 팟-불변 상수: ρ(R25)=0.20, ρ(R50)=1/3, ρ(R75)=3/7, ρ(R100)=0.5
    →  μ̂_B = Q(B)/ρ(B)
  셀 s의 갈등 여부/방향은 μ̂ 순위 vs ρ-스케일 순위 비교로 판정,
  복원 임계는 ε_min(s) = k·c(s)/(1−k),  k = ρ_B*·μ̂_B*/μ̂_C  (흡수·은폐 동형).
  α-공간은 c 소거: α_min(s) = k/(1−k).
  → 방문가중 CDF  F(ε) = P( ε > ε_min(s) )  를 예측하고 관측 용량-반응과 겹쳐본다.

c(s)·방문가중: 학습 상대(TAG) 대상 greedy 시뮬레이션에서 라운드별 평균 팟과 셀 방문수를 측정.
한계(정직): μ̂는 학습된 Q 기반(잡음·greedy 방문 편향), 경쟁자는 팟-비례 레이즈로 한정
(CALL·ALLIN은 지분 복원 불가 — 해당 셀은 커버리지에서 보고), CHECK-vs-최강경쟁자 쌍별 근사.

usage: python analyze_threshold_cdf.py  [alpha=0.30]  [n_sim=5000]
"""
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import train_eval_mc_prop_softmax_2000k as base
from abstraction import (Round, Position, State, PrevAction, Action,
                         pk_to_round, pk_to_state, pk_to_position,
                         legal_our_actions, execute_action)
from qlearning import QLearning

ALPHA = float(sys.argv[1]) if len(sys.argv) > 1 else 0.30
N_SIM = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
RES = Path(__file__).resolve().parent.parent / "results" / "30_vic_potfrac_seedsweep"

# 팟-비례 레이즈의 팟-불변 credit 지분 ρ = f/(f+1) (f = 팟 대비 레이즈 비율)
RHO = {Action.RAISE_25: 0.25 / 1.25, Action.RAISE_50: 0.50 / 1.50,
       Action.RAISE_75: 0.75 / 1.75, Action.RAISE_100: 1.00 / 2.00}
TOL = 1.0


def sim_pot_and_visits(ql, n):
    """greedy vs TAG(학습 상대): 라운드별 평균 팟 + 셀 방문수."""
    import rulebased_personas as personas
    import random
    random.seed(777)
    policy = personas.PERSONA_POLICIES['tag']
    pots = defaultdict(list)
    visits = Counter()
    for i in range(n):
        pk = base._make_game()
        lid = i % 2
        pos = pk_to_position(lid)
        prev = {}
        while pk.status:
            if pk.can_deal_hole():
                pk.deal_hole()
            elif pk.can_deal_board():
                pk.deal_board()
            elif pk.actor_index is not None:
                if pk.actor_index == lid:
                    r = pk_to_round(pk)
                    s = pk_to_state(pk, lid)
                    pa = prev.get(r, PrevAction.NONE)
                    pot = sum(p.amount for p in pk.pots) + sum(pk.bets)
                    pots[r].append(pot)
                    visits[(r, pos, s, pa)] += 1
                    a = ql.best_action(r, pos, s, pa, legal_our_actions(pk))
                    execute_action(pk, a)
                else:
                    personas.step_persona_opponent(pk, 1 - lid, policy, prev)
            else:
                break
    cbar = {r: st.mean(v) for r, v in pots.items()}
    return cbar, visits


def main():
    scale = (1 + ALPHA) / ALPHA
    all_eps, all_alpha = [], []          # (ε_min, weight), (α_min, weight)
    cover = Counter()
    for seed in [1, 2, 3, 4, 5]:
        ql = QLearning.load(str(RES / f"chec_a30_s{seed}" / "eval_results.pkl"))
        cbar, visits = sim_pot_and_visits(ql, N_SIM)
        for (r, p, s, pa), w in visits.items():
            q = [ql.get_q(r, p, s, pa, a) for a in Action]
            if max(abs(x) for x in q) <= TOL:
                cover['inactive'] += w; continue
            mu_c = q[Action.CHECK.value] * scale
            cands = [(a, q[a.value] / RHO[a]) for a in RHO if abs(q[a.value]) > 1e-9]
            if not cands:
                cover['no_priced_competitor'] += w; continue
            # μ̂ 기준 최강 경쟁자
            b_star, mu_b = max(cands, key=lambda t: t[1])
            rho_b = RHO[b_star]
            # 갈등 판정: ρ-스케일 greedy(현행)와 μ̂ greedy(참) 사이 CHECK 관련 오순위?
            #  - 은폐: μ_C > μ_B (CHECK 참-최선) 인데 ρ_C(0)·μ_C = 0 < ρ_B·μ_B  → μ_B>0이면 갈등
            #  - 흡수: μ_C < μ_B 인데 0 > ρ_B·μ_B  → μ_B<0이면 갈등
            if mu_c > mu_b and mu_b > 0:
                mode = 'masking'
            elif mu_c < mu_b and mu_b < 0:
                mode = 'absorption'
            else:
                cover['no_conflict'] += w; continue
            k = rho_b * mu_b / mu_c
            if not (0 < k < 1):
                cover['k_out_of_range'] += w; continue
            cover[mode] += w
            c = cbar.get(r, 12.0)
            all_eps.append((k * c / (1 - k), w))
            all_alpha.append((k / (1 - k), w))

    tot_w = sum(cover.values())
    conf_w = cover['masking'] + cover['absorption']
    print(f"=== 커버리지 (방문가중, seed1-5 합산, α={ALPHA}) ===")
    for kk, v in cover.most_common():
        print(f"  {kk:22} {v:8d} ({v/tot_w*100:5.1f}%)")
    print(f"  갈등 셀 방문 비중: {conf_w/tot_w*100:.1f}%\n")

    def F(pairs, x):
        w_ok = sum(w for e, w in pairs if x > e)
        return w_ok / sum(w for _, w in pairs)

    print("=== 예측 회복분율 F vs 관측 (fixed-K, ε칩) ===")
    print(f"{'ε':>6} {'예측F(ε)':>10}   관측(양수 seed 비율)")
    obs_k = {0: '0/6', 1: '2/6', 5: '5/5', 20: '5/5', 60: '5/5'}
    for e in [0, 1, 5, 20, 60]:
        print(f"{e:>6} {F(all_eps, e) if e else 0.0:>10.2f}   {obs_k.get(e,'—')}")
    print()
    print("=== 예측 회복분율 F vs 관측 (checktime α) ===")
    print(f"{'α':>6} {'예측F(α)':>10}   관측")
    obs_a = {0.04: '0/5', 0.08: '3/5', 0.10: '1/6', 0.15: '1/5', 0.20: '5/6', 0.30: '6/6'}
    for a in [0.04, 0.08, 0.10, 0.15, 0.20, 0.30]:
        print(f"{a:>6.2f} {F(all_alpha, a):>10.2f}   {obs_a[a]}")
    print()
    # 분위수
    eps_sorted = sorted(all_eps)
    cum, half = 0, sum(w for _, w in all_eps) / 2
    for e, w in eps_sorted:
        cum += w
        if cum >= half:
            print(f"ε_min 방문가중 중앙값 ≈ {e:.1f}칩")
            break
    al_sorted = sorted(all_alpha)
    cum = 0
    for a, w in al_sorted:
        cum += w
        if cum >= half:
            print(f"α_min 방문가중 중앙값 ≈ {a*100:.1f}%")
            break


if __name__ == '__main__':
    main()
