# -*- coding: utf-8 -*-
"""Q-궤적 경주 분석 — 수렴 경쟁(race) 채널의 직접 검증 (계측 재상영 qsnap 기반).

입력: results/34_threshold_stage0/qtraj_a{15,30}_s1/qsnap.pkl
  (30k 에피소드마다 (ep, q 전체) — 결정론 재상영의 순수 관측)

정의:
  흡수(absorbed) 셀 @t: argmax 행이 CHECK ∧ CHECK 외 최대 Q < 0
  델타 셀: a30 최종 비흡수 ∧ a15 최종 흡수  (30%는 풀고 15%는 못 푼 셀)
판별 (사전 고정):
  델타 셀의 a15 갭 g(t) = Q(CHECK) − max_{a≠CHECK} Q(a) 궤적을 분류 —
    '이동중' = 후반 1/4 기울기 < −잡음 (경주에서 지는 중 = race 채널 지지)
    '정체'   = 후반 기울기 ≥ −잡음 (고정점 자체가 위 = 정적 임계가 참으로 더 높음)
  다수가 '이동중'이면 race 확정, 다수가 '정체'면 race 기각·정적 지도 자체 오추정.
  a30 델타 셀의 교차 시점(에피소드·온도) 분포도 산출.

usage: python analyze_qrace.py
"""
import pickle
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import Action
from qtable import QTable
from train import temperature_at

OUT = Path(__file__).resolve().parent.parent / 'results' / '34_threshold_stage0'
CHECK = Action.CHECK.value
TOTAL_EP = 7_500_000


def load_snaps(run):
    snaps = []
    with open(OUT / run / 'qsnap.pkl', 'rb') as f:
        while True:
            try:
                snaps.append(pickle.load(f))
            except EOFError:
                break
    return snaps


def cells_of(q):
    for r in range(len(q)):
        for p in range(len(q[r])):
            for s in range(len(q[r][p])):
                for pa in range(len(q[r][p][s])):
                    yield (r, p, s, pa)


def row_of(q, c):
    r, p, s, pa = c
    return q[r][p][s][pa]


def absorbed(row):
    others = [x for i, x in enumerate(row) if i != CHECK]
    return (row[CHECK] >= max(others)) and (max(others) < 0) \
        and any(abs(x) > 1e-9 for x in others)


def gap(row):
    return row[CHECK] - max(x for i, x in enumerate(row) if i != CHECK)


def main():
    s15 = load_snaps('qtraj_a15_s1')
    s30 = load_snaps('qtraj_a30_s1')
    print(f"스냅샷: a15 {len(s15)}개, a30 {len(s30)}개 (30k 간격)")
    qt15 = QTable.load(OUT / 'qtraj_a15_s1' / 'qtable.pkl')

    f15, f30 = s15[-1][1], s30[-1][1]
    # 방문 가중치: a15 학습 n(CHECK) — 실제로 쓰인 셀만 의미
    delta, a15_abs, a30_abs = [], 0, 0
    for c in cells_of(f15):
        r, p, s, pa = c
        n_c = qt15.n[r][p][s][pa][CHECK]
        if n_c < 30:                      # 사실상 미사용 셀 제외
            continue
        ab15, ab30 = absorbed(row_of(f15, c)), absorbed(row_of(f30, c))
        a15_abs += ab15
        a30_abs += ab30
        if ab15 and not ab30:
            delta.append((c, n_c))
    print(f"최종 흡수 셀(방문 n≥30): a15 {a15_abs} vs a30 {a30_abs} | "
          f"델타 셀(30% 해소·15% 미해소): {len(delta)}")

    if not delta:
        print("델타 셀 없음 — 성능 차이가 흡수 채널 밖에 있음 (재검토 필요)")
        return

    # 델타 셀의 a15 갭 궤적 분류
    n_snap = len(s15)
    q3 = 3 * n_snap // 4
    moving, plateau, details = 0, 0, []
    for c, n_c in delta:
        g = [gap(row_of(q, c)) for _, q in s15]
        tail = g[q3:]
        xs = list(range(len(tail)))
        mx = st.mean(xs)
        my = st.mean(tail)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, tail))
        var = sum((x - mx) ** 2 for x in xs) or 1
        slope = cov / var                          # 스냅샷당 칩 변화
        noise = st.stdev(tail) if len(tail) > 2 else 0.0
        if slope < -max(noise / max(len(tail), 1), 1e-3):
            moving += 1
        else:
            plateau += 1
        details.append((n_c, g[-1], slope))

    print(f"\n[a15 델타 셀 궤적 판별] 이동중(지는 경주) {moving} vs 정체(고정점 위) {plateau}")
    top = sorted(details, reverse=True)[:8]
    print("  방문수 상위 델타 셀 (n, 최종 갭, 후반 기울기/스냅샷):")
    for n_c, gf, sl in top:
        print(f"    n={n_c:6d} 갭 {gf:+7.2f}칩 기울기 {sl:+.4f}")

    # a30 쪽: 델타 셀들이 언제(온도 몇에서) 교차했나
    cross = []
    for c, n_c in delta:
        for ep, q in s30:
            if not absorbed(row_of(q, c)) and gap(row_of(q, c)) < 0:
                cross.append((ep, temperature_at(ep, TOTAL_EP), n_c))
                break
    if cross:
        eps_ = [e for e, t, _ in cross]
        ts = [t for _, t, _ in cross]
        print(f"\n[a30 교차 시점] 중앙값 ep {st.median(eps_):,.0f} "
              f"(T={st.median(ts):.1f}) | p25 T={sorted(ts)[len(ts)//4]:.1f} "
              f"p75 T={sorted(ts)[3*len(ts)//4]:.1f}")
        late = sum(1 for t in ts if t < 3)
        print(f"  저온(T<3) 교차 비중 {late/len(ts)*100:.0f}% — 높으면 race 여지 큼")


if __name__ == '__main__':
    main()
