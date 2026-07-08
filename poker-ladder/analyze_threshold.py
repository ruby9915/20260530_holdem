# -*- coding: utf-8 -*-
"""임계 분포 분석 (E9의 ladder 이식) — A8 vs A12 의 ε_min 이동 정량화.

원리 (레거시 analyze_threshold_cdf.py 동일):
  checktime α: Q(CHECK) = [α/(1+α)]·μ_C (팟-불변) → μ̂_C = Q·(1+α)/α
  팟-비례 레이즈 credit 지분 ρ = f/(f+1) (팟-불변 상수) → μ̂_B = Q(B)/ρ(B)
  갈등 셀의 복원 임계 ε_min(s) = k·c(s)/(1−k), k = ρ_B*·μ̂_B*/μ̂_C
  방문가중 CDF F(ε) = P(ε > ε_min(s)) 로 fixed-K 성패 예측.

용도: 2단에서 fixed5 가 A8 5/5 → A12 2/5 로 후퇴한 것이
      ε_min 분포의 우측 이동(오버벳 → 경쟁 지분·팟 확대)으로 설명되는지 검증.

usage: python analyze_threshold.py [n_sim=3000]
  대상: results/32_ehs_k20/k20/chec_a30_s{1-5} (A8) vs k20_a12/chec_a30_s{1-5} (A12)
한계(정직): μ̂=학습 Q 기반(잡음·greedy 방문 편향), 경쟁자=팟-비례 레이즈 한정
(CALL·ALLIN 지분 복원 불가), 쌍별 근사, c(s)=라운드 평균 팟.
"""
import random
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import Action, legal_actions, execute_action, _RAISE_PCT
from cards import make_cards
from defs import PrevAction, pk_to_position, pk_to_round, pot_size
from game import make_game
from personas import PERSONA_POLICIES, step_opponent
from qtable import QTable

N_SIM = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
ALPHA = 0.30
RES = Path(__file__).resolve().parent.parent / 'results' / '32_ehs_k20'
TOL = 1.0

# 팟-비례 레이즈 지분 ρ = f/(f+1) — A12 는 오버벳 4종 추가
RHO = {a: pct / (pct + 1.0) for a, pct in _RAISE_PCT.items()}


def sim_pot_and_visits(qt, cards, actions_version, n):
    """greedy vs 학습 TAG: 라운드별 평균 팟 + 셀 방문수 (레거시 E9 동일 설계)."""
    random.seed(777)
    policy = PERSONA_POLICIES['tag']
    pots = defaultdict(list)
    visits = Counter()
    for i in range(n):
        pk = make_game()
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
                    s = cards.state_of(pk, lid)
                    pa = prev.get(r, PrevAction.NONE)
                    pots[r].append(pot_size(pk))
                    visits[(r, pos, s, pa)] += 1
                    a = qt.best_action(r, pos, s, pa,
                                       legal_actions(pk, actions_version))
                    execute_action(pk, a)
                else:
                    step_opponent(pk, 1 - lid, policy, prev)
            else:
                break
    cbar = {r: st.mean(v) for r, v in pots.items()}
    return cbar, visits


def analyze(tag, run_glob, card_name, actions_version):
    scale = (1 + ALPHA) / ALPHA
    raises = [a for a in RHO
              if a.value < (12 if actions_version == 'A12' else 8)]
    all_eps, cover = [], Counter()
    for run in sorted(RES.glob(run_glob)):
        qt = QTable.load(run / 'qtable.pkl')
        cards = make_cards(card_name)
        cbar, visits = sim_pot_and_visits(qt, cards, actions_version, N_SIM)
        for (r, p, s, pa), w in visits.items():
            row = qt.q[r.value][p.value][s][pa.value]
            if max(abs(x) for x in row) <= TOL:
                cover['inactive'] += w; continue
            mu_c = row[Action.CHECK.value] * scale
            cands = [(a, row[a.value] / RHO[a]) for a in raises
                     if abs(row[a.value]) > 1e-9]
            if not cands:
                cover['no_priced_competitor'] += w; continue
            b_star, mu_b = max(cands, key=lambda t: t[1])
            if mu_c > mu_b and mu_b > 0:
                mode = 'masking'
            elif mu_c < mu_b and mu_b < 0:
                mode = 'absorption'
            else:
                cover['no_conflict'] += w; continue
            k = RHO[b_star] * mu_b / mu_c
            if not (0 < k < 1):
                cover['k_out_of_range'] += w; continue
            cover[mode] += w
            all_eps.append((k * cbar.get(r, 12.0) / (1 - k), w))

    tot = sum(cover.values())
    conf = cover['masking'] + cover['absorption']
    print(f"=== {tag} (chec_a30 seed1-5, n_sim={N_SIM}) ===")
    for kk, v in cover.most_common():
        print(f"  {kk:22} {v:8d} ({v/tot*100:5.1f}%)")
    print(f"  갈등 셀 방문 비중: {conf/tot*100:.2f}%")

    def F(x):
        w_ok = sum(w for e, w in all_eps if x > e)
        return w_ok / sum(w for _, w in all_eps) if all_eps else 0.0

    eps_sorted = sorted(all_eps)
    cum, half = 0, sum(w for _, w in all_eps) / 2
    med = float('nan')
    for e, w in eps_sorted:
        cum += w
        if cum >= half:
            med = e; break
    print(f"  ε_min 방문가중 중앙값 ≈ {med:.1f}칩 | F(1)={F(1):.2f} F(5)={F(5):.2f} "
          f"F(20)={F(20):.2f} F(60)={F(60):.2f}\n")
    return med, F(5)


def main():
    m8, f8 = analyze('A8  (k20)', 'k20/chec_a30_s*', 'ehs20', 'A8')
    m12, f12 = analyze('A12 (k20_a12)', 'k20_a12/chec_a30_s*', 'ehs20', 'A12')
    print("=== 예측 vs 관측 (fixed5) ===")
    print(f"  A8 : F(5)={f8:.2f}  ↔ 관측 5/5 양수")
    print(f"  A12: F(5)={f12:.2f}  ↔ 관측 2/5 양수")
    print(f"  ε_min 중앙값 이동: {m8:.1f}칩 → {m12:.1f}칩")


if __name__ == '__main__':
    main()
