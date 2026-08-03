# -*- coding: utf-8 -*-
"""α 지도 v2 — checktime 실효 지분 s(α) 실측 기반 재유도 (수리 가설 2).

배경 (수리 가설 1 기각 후): ε(칩) 지도는 정확한데 α(비율) 지도만 ~5배 과낙관.
원인 후보 = 정적 근사 s(α)=α/(1+α) 가 실제 산술과 다름 (game.py:120-124):
  실제 지분 s_i = α·p_i / (T_real + α·Σp_j)
    p_i = 그 체크 시점 팟, T_real = 에피소드 실투자 합, Σp_j = 모든 체크의 팟 합.
  → T_real ≫ α·Σp 면 지분 급감, 올체크 핸드(T_real=0)면 α 상쇄(지분이 α와 무관),
    α→∞ 에서도 지분 상한 E[p/Σp] — 도달 불가능한 요구 지분 k 가 존재할 수 있음.

방법 (학습 0회): 학습된 chec Q 로 greedy 대국을 시뮬레이션해 (p_i, T_real, Σp_j)
분포를 라운드별로 실측 → s_r(α) = E[α·p/(T+αΣp)] 곡선 구성 →
  ① 복원도 교정: μ̂_C = Q(CHECK)/s_r(α_학습)  (구판: Q·(1+α)/α)
  ② 요구 지분 k = ρ_B·μ̂_B/μ̂_C 에 대해 s_r(α_min) = k 를 이분법으로 풀어 α_min 재유도
     (해가 없으면 = checktime 으로 영구 미해결 셀 → α_min = inf 로 기록)
출력: samples_chec_v2_<플랫폼>.csv (fit_probit_repair 와 동일 형식) + 라운드 s(α) 요약.

usage: python derive_alpha_v2.py [--nsim 3000] [--platform legacy8-A8 k20-A12 ...]
한계(정직): 대국 분포 = greedy(학습 종반 근사) vs TAG — 학습 중반(고온 softmax)의
분포와 다를 수 있음. 필요 시 계측 훅 실측(설계 1단계 카드)으로 대체 예정.
"""
import argparse
import csv
import math
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
from analyze_threshold import PLATFORMS, RES, OUT, TOL, RHO, wmedian, wcdf
from cards import make_cards
from defs import PrevAction, pk_to_position, pk_to_round, pot_size
from game import make_game
from personas import PERSONA_POLICIES, step_opponent
from qtable import QTable


def sim_dose_and_visits(qt, cards, actions_version, n):
    """greedy vs TAG — 셀 방문수 + 체크 투여 표본 (라운드별 (p, T_real, Σp)) 수집."""
    random.seed(777)
    policy = PERSONA_POLICIES['tag']
    visits = Counter()
    dose = defaultdict(list)          # round -> [(p_i, T_real, sum_p)]
    pots = defaultdict(list)
    for i in range(n):
        pk = make_game()
        lid = i % 2
        pos = pk_to_position(lid)
        prev = {}
        checks = []                    # (round, p_i)
        t_real = 0.0
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
                    sb = pk.stacks[lid]
                    a = qt.best_action(r, pos, s, pa,
                                       legal_actions(pk, actions_version))
                    execute_action(pk, a)
                    inv = float(sb - pk.stacks[lid])
                    t_real += inv
                    if a == Action.CHECK and inv == 0:
                        checks.append((r, pot_size(pk)))
                else:
                    step_opponent(pk, 1 - lid, policy, prev)
            else:
                break
        sum_p = sum(p for _, p in checks)
        for r, p in checks:
            dose[r].append((p, t_real, sum_p))
    return visits, dose, pots


def s_of_alpha(samples, alpha):
    """라운드 투여 표본에서 실효 지분 s(α) = E[α·p/(T+α·Σp)]."""
    if not samples or alpha <= 0:
        return 0.0
    return st.mean(alpha * p / (t + alpha * sp) for p, t, sp in samples
                   if t + alpha * sp > 0)


def solve_alpha(samples, k, hi=50.0):
    """s(α)=k 이분법. 상한 s(hi) < k 면 미해결(inf)."""
    if s_of_alpha(samples, hi) < k:
        return float('inf')
    lo = 1e-4
    for _ in range(60):
        mid = (lo + hi) / 2
        if s_of_alpha(samples, mid) < k:
            lo = mid
        else:
            hi = mid
    return hi


def analyze_v2(pname, n_sim):
    root, card_name, actions_version, bases = PLATFORMS[pname]
    cond_glob, a_train = bases['chec']
    raises = [a for a in RHO
              if a.value < (12 if actions_version == 'A12' else 8)]
    out_rows, cover = [], Counter()
    dose_all = defaultdict(list)

    for run in sorted((RES / root).glob(cond_glob)):
        qt = QTable.load(run / 'qtable.pkl')
        cards = make_cards(card_name)
        visits, dose, pots = sim_dose_and_visits(qt, cards, actions_version, n_sim)
        cbar = {r: st.mean(v) for r, v in pots.items()}
        for r, v in dose.items():
            dose_all[r].extend(v)
        for (r, p, s, pa), w in visits.items():
            row = qt.q[r.value][p.value][s][pa.value]
            if max(abs(x) for x in row) <= TOL:
                cover['inactive'] += w
                continue
            ds = dose[r] if dose[r] else None
            if not ds:
                cover['no_dose_sample'] += w
                continue
            s_train = s_of_alpha(ds, a_train)
            if s_train <= 0:
                cover['s_train_zero'] += w
                continue
            mu_c = row[Action.CHECK.value] / s_train        # ★ 교정 복원
            cands = [(a, row[a.value] / RHO[a]) for a in raises
                     if abs(row[a.value]) > 1e-9]
            if not cands:
                cover['no_priced_competitor'] += w
                continue
            b_star, mu_b = max(cands, key=lambda t: t[1])
            if not (mu_c < mu_b < 0):
                cover['no_conflict'] += w
                continue
            k = RHO[b_star] * mu_b / mu_c
            if not (0 < k < 1):
                cover['k_out_of_range'] += w
                continue
            cover['absorption'] += w
            a_min = solve_alpha(ds, k)                       # ★ 실효 지분으로 재유도
            e_min = (a_min * cbar.get(r, 12.0)) if math.isfinite(a_min) else float('inf')
            out_rows.append((a_min, e_min, w))

    tot = sum(cover.values()) or 1
    fin = [(a, w) for a, e, w in out_rows if math.isfinite(a)]
    inf_w = sum(w for a, e, w in out_rows if not math.isfinite(a))
    conf_w = cover['absorption']
    print(f"=== {pname} v2 (실효 지분 모형, n_sim={n_sim}) ===")
    print("  s(α) 라운드 곡선 (α=0.10/0.15/0.30/1.0):")
    for r in sorted(dose_all, key=lambda x: x.value):
        d = dose_all[r]
        print(f"    {r.name:8s} n={len(d):6d} | " + " ".join(
            f"s({a:g})={s_of_alpha(d, a):.3f}" for a in (0.10, 0.15, 0.30, 1.0))
            + f" | s(∞)≈{st.mean(p/sp for p, _, sp in d if sp > 0):.3f}")
    print(f"  흡수 셀 방문 비중 {conf_w/tot*100:.2f}% | "
          f"미해결(α_min=∞) 질량 {inf_w/max(conf_w,1)*100:.1f}%")
    if fin:
        print(f"  α_min(유한) 중앙값 {wmedian(fin):.3f} | "
              f"F_α(0.10)={wcdf(fin,0.10)*(1-inf_w/max(conf_w,1)):.2f} "
              f"F_α(0.15)={wcdf(fin,0.15)*(1-inf_w/max(conf_w,1)):.2f} "
              f"F_α(0.30)={wcdf(fin,0.30)*(1-inf_w/max(conf_w,1)):.2f} "
              f"(전체 흡수 질량 기준)")
    with open(OUT / f'samples_chec_v2_{pname}.csv', 'w', newline='',
              encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['mode', 'eps_min', 'alpha_min', 'weight'])
        for a, e, wt in out_rows:
            w.writerow(['absorption', f'{e:.4f}' if math.isfinite(e) else 'inf',
                        f'{a:.6f}' if math.isfinite(a) else 'inf', wt])
    print(f"  saved samples_chec_v2_{pname}.csv\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nsim', type=int, default=3000)
    ap.add_argument('--platform', nargs='*',
                    default=['legacy8-A8', 'k20-A8', 'k20-A12', 'k50-A12'])
    args = ap.parse_args()
    for pname in args.platform:
        analyze_v2(pname, args.nsim)


if __name__ == '__main__':
    main()
