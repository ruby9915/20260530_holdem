# -*- coding: utf-8 -*-
"""FOLD 임계 지도 선행 유도 (이중 VIC 로드맵 0.5단계 — 학습 0회).

CHECK 임계 분석의 대칭 적용: k20-A12 chec_a30 학습 Q(5시드)의 **벳 직면 셀**에서
  흡수 판정: max(비-FOLD 행동 Q) < 0  (FOLD의 0이 argmax 지배)
  FOLD 참값 근사: μ̂_F = −c̄(r)/2   (폴드 시 평균 payoff = −기투자; 기투자 ≈ 라운드 평균 팟 절반)
  요구 지분: k_f = Q(B*)/μ̂_F   (B* = 최선 비-FOLD 행동)
  폴드 지분 근사: s_f(α_f) ≈ α_f/(0.5+α_f)  (팟 p≈c̄, 실투자 T≈c̄/2 가정)
  → α_f_min = 0.5·k_f/(1−k_f)
가중치 = 훈련 n(FOLD) (그 맥락 방문 빈도의 대용).

정직 명시(등록문에 병기할 근사 3건): ① μ̂_F 의 기투자 절반 근사 ② s_f 의 정적 근사
(CHECK판 게이트 B가 정적 근사의 한계를 보였음 — 같은 위험) ③ 커버리지→성적 링크는
vsRand 로 보정된 것을 vsMAN 에 이식하는 미검증 가정.

usage: python fold_threshold_map.py
"""
import csv
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import Action
from analyze_threshold import sim_pot_and_visits, wmedian, wcdf
from cards import make_cards
from qtable import QTable

RES = Path(__file__).resolve().parent.parent / 'results'
OUT = RES / '35_fold_vic'
F = Action.FOLD.value
DOSES = (0.05, 0.15, 0.30, 1.0)


def main():
    OUT.mkdir(exist_ok=True)
    samples = []                    # (alpha_f_min, weight)
    cover = Counter()
    for s in range(1, 6):
        run = RES / '32_ehs_k20' / 'k20_a12' / f'chec_a30_s{s}'
        qt = QTable.load(run / 'qtable.pkl')
        cards = make_cards('ehs20')
        pots, _ = sim_pot_and_visits(qt, cards, 'A12', 2000)
        cbar = {r.value: st.mean(v) for r, v in pots.items()}
        for r in range(4):
            for p in range(2):
                for s_ in range(len(qt.q[r][p])):
                    for pa in range(4):
                        nrow = qt.n[r][p][s_][pa]
                        if nrow[F] < 30:
                            continue            # 벳 직면 맥락만 (FOLD 가 실제 사용된 셀)
                        row = qt.q[r][p][s_][pa]
                        others = [row[i] for i in range(len(row))
                                  if i != F and abs(row[i]) > 1e-9]
                        if not others:
                            cover['no_competitor'] += nrow[F]
                            continue
                        b = max(others)
                        if b >= 0:
                            cover['not_absorbed'] += nrow[F]
                            continue            # 양수 대안 존재 → 0-지배 아님
                        cover['absorbed'] += nrow[F]
                        mu_f = -cbar.get(r, 12.0) / 2
                        k_f = b / mu_f          # 음/음 → 양수
                        if not (0 < k_f < 1):
                            cover['k_out_of_range'] += nrow[F]
                            continue
                        a_min = 0.5 * k_f / (1 - k_f)
                        samples.append((a_min, nrow[F]))

    tot = sum(cover.values()) or 1
    print("=== FOLD 임계 지도 (k20-A12 chec_a30 ×5시드, 벳 직면 셀) ===")
    for kk, v in cover.most_common():
        print(f"  {kk:16} {v:8d} ({v/tot*100:5.1f}%)")
    print(f"  α_f_min 방문가중 중앙값 = {wmedian(samples):.3f}")
    line = " ".join(f"F({d:g})={wcdf(samples, d):.2f}" for d in DOSES)
    print(f"  커버리지: {line}")
    with open(OUT / 'fold_threshold_map.csv', 'w', newline='',
              encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['alpha_f_min', 'weight'])
        for a, wt in samples:
            w.writerow([f'{a:.6f}', wt])
    print(f"saved {OUT / 'fold_threshold_map.csv'}")


if __name__ == '__main__':
    main()
