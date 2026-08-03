# -*- coding: utf-8 -*-
"""임계 분포 분석 v2 — 임계 조건 유도 0단계 (설계: zca_theory/vic_임계조건_유도_설계.md).

원리 (E9 동일):
  checktime α: Q(CHECK) = [α/(1+α)]·μ_C (팟-불변) → μ̂_C = Q·(1+α)/α
  팟-비례 레이즈 credit 지분 ρ = f/(f+1) → μ̂_B = Q(B)/ρ(B)
  갈등 셀 임계 ε_min(s) = k·c(r)/(1−k), k = ρ_B*·μ̂_B*/μ̂_C
  ★ 무차원 임계 α_min(s) = ε_min/c(r) = k/(1−k) — 팟 추정과 무관 (0단계 핵심 지표)

v2 변경 (설계 0단계 지시):
  ① masking(상한)·absorption(하한) 분포 분리 — 구판은 합산(오염) → 양쪽 별도 보고
  ② α_min 분포·F_α 산출 (무차원 자기일관성 검사 P1)
  ③ 플랫폼 확장: legacy8 / k20-A8 / k20-A12 / k50-A12 / k20-A12-CFR / k50-A12-CFR
  ④ 팟 분위수(p25/50/75) 보고 (평균 단독 → 분포)
  ⑤ 근거 Q 교차(basis): chec(정확 복원) / fixed5(근사 복원 — T̂=c̄/2 가정, 주의 표기)
     / off(복원 불가 — 0-지배 셀 구성비만)

usage: python analyze_threshold.py [--nsim 3000] [--basis chec] [--platform 이름 ...]
  결과: stdout + results/34_threshold_stage0/stage0_<basis>.csv
한계(정직): μ̂=학습 Q 기반(잡음·greedy 방문 편향), 경쟁자=팟-비례 레이즈 한정,
  쌍별 근사, c(r)=라운드 평균 팟(ε 칩 환산에만 사용 — α_min 은 무관),
  팟 시뮬 상대 = TAG 고정(플랫폼 간 비교 가능성 우선; CFR-학습 Q 도 TAG 대국 팟 사용).
"""
import argparse
import csv
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

RES = Path(__file__).resolve().parent.parent / 'results'
OUT = RES / '34_threshold_stage0'
TOL = 1.0

# 팟-비례 레이즈 지분 ρ = f/(f+1)
RHO = {a: pct / (pct + 1.0) for a, pct in _RAISE_PCT.items()}

# 플랫폼 = (런 루트, 카드, 행동, basis별 사용 조건·α)
#   basis 'chec' 조건명이 플랫폼마다 다름: legacy8 은 사다리 재현(33번)에 chec_a30 이 없어
#   chec_a20(α=0.20, 5/5 확인 대상)을 사용 — α 는 복원 공식에 반영되므로 정합.
PLATFORMS = {
    'legacy8-A8':  ('33_ladder_replicate_k8', 'legacy8', 'A8',
                    {'chec': ('chec_a20_s*', 0.20), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('rand_off_s*', None)}),
    'k20-A8':      ('32_ehs_k20/k20', 'ehs20', 'A8',
                    {'chec': ('chec_a30_s*', 0.30), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('off_s*', None)}),
    'k20-A12':     ('32_ehs_k20/k20_a12', 'ehs20', 'A12',
                    {'chec': ('chec_a30_s*', 0.30), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('off_s*', None)}),
    'k50-A12':     ('32_ehs_k20/k50_a12', 'ehs50', 'A12',
                    {'chec': ('chec_a30_s*', 0.30), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('off_s*', None)}),
    'k20-A12-CFR': ('32_ehs_k20/k20_a12_cfr', 'ehs20', 'A12',
                    {'chec': ('chec_a30_s*', 0.30), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('off_s*', None)}),
    'k50-A12-CFR': ('32_ehs_k20/k50_a12_cfr', 'ehs50', 'A12',
                    {'chec': ('chec_a30_s*', 0.30), 'fixed': ('fixed5_s*', 5.0),
                     'off': ('off_s*', None)}),
}


def sim_pot_and_visits(qt, cards, actions_version, n):
    """greedy vs 학습 TAG: 라운드별 팟 표본 + 셀 방문수 (E9 설계 유지)."""
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
    return pots, visits


def wmedian(pairs):
    """가중 중앙값. pairs = [(값, 가중치)]."""
    if not pairs:
        return float('nan')
    pairs = sorted(pairs)
    half = sum(w for _, w in pairs) / 2
    cum = 0
    for v, w in pairs:
        cum += w
        if cum >= half:
            return v
    return pairs[-1][0]


def wcdf(pairs, x):
    """방문가중 CDF F(x) = P(임계 < x)."""
    tot = sum(w for _, w in pairs)
    return sum(w for v, w in pairs if v < x) / tot if tot else float('nan')


def analyze(pname, basis, n_sim, nmin=0, tag=''):
    """nmin: 학습 방문수 필터 — CHECK·경쟁자 모두 훈련 중 n(s,a) ≥ nmin 인 셀만 신뢰.
    (게이트 B 기각의 수리 가설: 저방문 행동의 Q 잡음이 작은-임계 질량을 부풀림)"""
    root, card_name, actions_version, bases = PLATFORMS[pname]
    cond_glob, bval = bases[basis]
    raises = [a for a in RHO
              if a.value < (12 if actions_version == 'A12' else 8)]
    runs = sorted((RES / root).glob(cond_glob))
    if not runs:
        print(f"[{pname}/{basis}] 런 없음 ({root}/{cond_glob}) — 건너뜀")
        return None

    eps = {'absorption': [], 'masking': []}     # (ε_min, w)
    alp = {'absorption': [], 'masking': []}     # (α_min, w) — 무차원
    cover = Counter()
    pot_all = defaultdict(list)
    zero_dom = 0                                 # off: 0-지배 셀 방문 (Q_CHECK≈0 ∧ 경쟁 전부 음수)

    for run in runs:
        qt = QTable.load(run / 'qtable.pkl')
        cards = make_cards(card_name)
        pots, visits = sim_pot_and_visits(qt, cards, actions_version, n_sim)
        cbar = {r: st.mean(v) for r, v in pots.items()}
        for r, v in pots.items():
            pot_all[r].extend(v)
        for (r, p, s, pa), w in visits.items():
            row = qt.q[r.value][p.value][s][pa.value]
            if max(abs(x) for x in row) <= TOL:
                cover['inactive'] += w
                continue
            q_c = row[Action.CHECK.value]
            nrow = qt.n[r.value][p.value][s][pa.value]
            if nmin and nrow[Action.CHECK.value] < nmin:
                cover['low_visit'] += w
                continue
            cands = [(a, row[a.value] / RHO[a]) for a in raises
                     if abs(row[a.value]) > 1e-9
                     and (not nmin or nrow[a.value] >= nmin)]
            if basis == 'off':
                # 복원 불가 — 0-지배 구조(ZCA 지문)만 계수
                if abs(q_c) <= TOL and cands and all(m < 0 for _, m in cands):
                    zero_dom += w
                else:
                    cover['non_zero_dom'] += w
                cover['visited'] += w
                continue
            if basis == 'chec':
                mu_c = q_c * (1 + bval) / bval
            else:                               # fixed: 근사 복원 (T̂ = c̄/2 가정)
                t_hat = cbar.get(r, 12.0) / 2
                mu_c = q_c * (bval + t_hat) / bval
            if not cands:
                cover['no_priced_competitor'] += w
                continue
            b_star, mu_b = max(cands, key=lambda t: t[1])
            if mu_c > mu_b and mu_b > 0:
                mode = 'masking'
            elif mu_c < mu_b and mu_b < 0:
                mode = 'absorption'
            else:
                cover['no_conflict'] += w
                continue
            k = RHO[b_star] * mu_b / mu_c
            if not (0 < k < 1):
                cover['k_out_of_range'] += w
                continue
            cover[mode] += w
            a_min = k / (1 - k)                  # 무차원 (팟 추정 무관)
            eps[mode].append((a_min * cbar.get(r, 12.0), w))
            alp[mode].append((a_min, w))

    tot = sum(cover.values()) or 1
    print(f"=== {pname} / basis={basis}({cond_glob.split('_s')[0]}) "
          f"seed×{len(runs)}, n_sim={n_sim} ===")
    if basis == 'off':
        print(f"  0-지배 셀(ZCA 지문) 방문 비중: {zero_dom/tot*100:.2f}% "
              f"(inactive {cover['inactive']/tot*100:.1f}%)\n")
        return {'platform': pname, 'basis': basis, 'zero_dom_pct': zero_dom / tot * 100}

    for kk, v in cover.most_common():
        print(f"  {kk:22} {v:8d} ({v/tot*100:5.1f}%)")
    q_pot = {r: (st.quantiles(v, n=4) if len(v) >= 4 else [0, 0, 0])
             for r, v in pot_all.items()}
    print("  팟 분위수 p25/p50/p75: " + " | ".join(
        f"{r.name} {q[0]:.0f}/{q[1]:.0f}/{q[2]:.0f}" for r, q in sorted(
            q_pot.items(), key=lambda t: t[0].value)))

    out = {'platform': pname, 'basis': basis}
    for mode in ('absorption', 'masking'):
        e, a = eps[mode], alp[mode]
        me, ma = wmedian(e), wmedian(a)
        out[f'{mode}_eps_med'] = me
        out[f'{mode}_alpha_med'] = ma
        for x in (1, 5, 20, 60):
            out[f'{mode}_F{x}'] = wcdf(e, x)
        for x in (0.05, 0.10, 0.15, 0.30):
            out[f'{mode}_Fa{int(x*100)}'] = wcdf(a, x)
        print(f"  [{mode:10}] ε중앙값 {me:6.1f}칩 | α중앙값 {ma:.3f} | "
              f"F(1/5/20/60)={wcdf(e,1):.2f}/{wcdf(e,5):.2f}/{wcdf(e,20):.2f}/{wcdf(e,60):.2f} | "
              f"F_α(5/10/15/30%)={wcdf(a,.05):.2f}/{wcdf(a,.10):.2f}/{wcdf(a,.15):.2f}/{wcdf(a,.30):.2f}")
    both = eps['absorption'] + eps['masking']
    print(f"  [합산(구판 호환)] ε중앙값 {wmedian(both):6.1f}칩 — "
          f"흡수 순수치와 차이 = 구판 오염도\n")
    out['combined_eps_med'] = wmedian(both)

    # 원시 분포 저장 — probit 적합에서 임의 지점의 F(v)·F_α(x) 평가용
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f'samples_{basis}{tag}_{pname}.csv', 'w', newline='',
              encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['mode', 'eps_min', 'alpha_min', 'weight'])
        for mode in ('absorption', 'masking'):
            for (e, wt), (a, _) in zip(eps[mode], alp[mode]):
                w.writerow([mode, f'{e:.4f}', f'{a:.6f}', wt])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nsim', type=int, default=3000)
    ap.add_argument('--basis', default='chec', choices=['chec', 'fixed', 'off'])
    ap.add_argument('--platform', nargs='*', default=list(PLATFORMS))
    ap.add_argument('--nmin', type=int, default=0)
    args = ap.parse_args()

    rows = []
    for pname in args.platform:
        tag = f'_n{args.nmin}' if args.nmin else ''
        r = analyze(pname, args.basis, args.nsim, nmin=args.nmin, tag=tag)
        if r:
            rows.append(r)
    if rows:
        OUT.mkdir(parents=True, exist_ok=True)
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k != 'platform', k))
        sfx = f'_n{args.nmin}' if args.nmin else ''
        with open(OUT / f'stage0_{args.basis}{sfx}.csv', 'w', newline='',
                  encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"saved {OUT / f'stage0_{args.basis}.csv'}")


if __name__ == '__main__':
    main()
