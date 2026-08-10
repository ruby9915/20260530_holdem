# -*- coding: utf-8 -*-
"""CFR판 regret 부호 반전 해부 0단계 (학습 0회 — Q-테이블 정책 비교).

저자 게이트 승인(2026-08-10) "vsTAG 부호 반전(−132→+299/+928) 해부" 착수분.
비교: 기준선 32_ehs_k20/k20_a12_cfr/chec_a30_s{1..5} ↔ 35_fold_vic/regret_cfr_{a30,a100}_s{1..5}
(시드 짝 s_i↔s_i, 학습 상대·카드·행동·체크 VIC 전부 동일 — 차이는 --vic-fold regret 하나).

측정 3종:
  A (보정 대조) 벳 직면 셀(n(FOLD)≥30) Q(FOLD) — 강도 3분위 방문가중 평균·음수 셀 비율.
    보강 39 보고치(강패 +1.22/+1.86, 음수 10%/8%) 재산출로 배관 검증.
  B (정책 이동) pa∈{SMALL_RAISE, BIG_RAISE} 공통 셀에서 greedy 비교 —
    FOLD→지속 / 지속→FOLD / 불변. 강도 3분위 분해, 기준선 방문가중.
  C (기전 검증) FOLD→지속으로 열린 셀에서 "지속 최선 Q"의 부호 —
    가설 "지속 가치가 양수로 학습된 셀만 열렸다"의 직접 확인.

greedy 근사: 후보 = FOLD + (그 런에서 n>0인 비-FOLD 행동) — fold_threshold_map.py 관례.
강도 3분위: EHS 버킷 s(0~19) → 약패 0–6 / 중간 7–13 / 강패 14–19.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import Action
from qtable import QTable

RES = Path(__file__).resolve().parent.parent / 'results'
BASE = RES / '32_ehs_k20' / 'k20_a12_cfr'
REG = RES / '35_fold_vic'
F = Action.FOLD.value
BETFACING_PA = (2, 3)          # SMALL_RAISE, BIG_RAISE — 전 라운드 무조건 벳 직면
TER = lambda s: 0 if s <= 6 else (1 if s <= 13 else 2)
TNAME = ('약패', '중간', '강패')


def cells(qt):
    for r in range(4):
        for p in range(2):
            for s in range(len(qt.q[r][p])):
                for pa in range(4):
                    yield r, p, s, pa


def greedy(qt, r, p, s, pa, fold_legal=True):
    """오프라인 greedy 근사. fold_legal: 벳 직면(pa 2·3)과 프리플랍 SB 첫 결정만 True —
    그 외(상대 체크 뒤 등)는 콜할 금액이 없어 실전에서 FOLD 불법."""
    row, nrow = qt.q[r][p][s][pa], qt.n[r][p][s][pa]
    cand = [i for i in range(len(row)) if i != F and nrow[i] > 0]
    if fold_legal or not cand:
        cand = [F] + cand
    return max(cand, key=lambda i: row[i])


def fingerprint(qt):
    """측정 A: 벳 직면(n(FOLD)≥30) 셀 Q(FOLD) 3분위 통계 (방문가중)."""
    wsum = [0.0] * 3
    wtot = [0.0] * 3
    neg = pos = zero = 0
    for r, p, s, pa in cells(qt):
        nf = qt.n[r][p][s][pa][F]
        if nf < 30:
            continue
        qf = qt.q[r][p][s][pa][F]
        t = TER(s)
        wsum[t] += qf * nf
        wtot[t] += nf
        if qf < -0.05:
            neg += 1
        elif qf > 0.05:
            pos += 1
        else:
            zero += 1
    means = [wsum[t] / wtot[t] if wtot[t] else float('nan') for t in range(3)]
    ncell = neg + pos + zero
    return means, (neg / ncell if ncell else float('nan')), ncell


def policy_diff(qb, qr):
    """측정 B·C: 공통 벳 직면 셀 greedy 이동 (기준선 방문가중)."""
    move = {}                   # (구분, 3분위) -> [셀수, 가중치]
    opened = []                 # FOLD→지속 셀의 지속 최선 Q (기준선 값)
    for r, p, s, pa in cells(qb):
        if pa not in BETFACING_PA:
            continue
        w = sum(qb.n[r][p][s][pa])
        if w < 30:
            continue            # 기준선이 실제로 겪은 셀만
        gb, gr = greedy(qb, r, p, s, pa), greedy(qr, r, p, s, pa)
        kind = ('FOLD→지속' if gb == F and gr != F else
                '지속→FOLD' if gb != F and gr == F else
                '불변(FOLD)' if gb == F else '불변(지속)')
        k = (kind, TER(s))
        c = move.setdefault(k, [0, 0.0])
        c[0] += 1
        c[1] += w
        if kind == 'FOLD→지속':
            row, nrow = qb.q[r][p][s][pa], qb.n[r][p][s][pa]
            others = [row[i] for i in range(len(row)) if i != F and nrow[i] > 0]
            if others:
                opened.append((max(others), w))
    return move, opened


AGG = {a.value for a in Action if a.name.startswith('RAISE')}


def initiative_diff(qb, qr):
    """측정 D: 자기 주도 셀(pa∈{NONE, CHECK_CALL}) greedy의 공격성 이동.

    분류: 수동(CHECK/CALL) vs 공격(RAISE_*). FOLD greedy는 별도 집계(프리플랍 SB 등).
    가중 = 기준선 방문. 반환 (이동표, 기준선 공격 비중, regret 공격 비중).
    """
    move = {}
    wagg_b = wagg_r = wtot = 0.0
    for r, p, s, pa in cells(qb):
        if pa in BETFACING_PA:
            continue
        w = sum(qb.n[r][p][s][pa])
        if w < 30:
            continue
        fl = (r == 0 and pa == 0 and p == 1)   # 프리플랍 SB 첫 결정만 FOLD 합법
        gb = greedy(qb, r, p, s, pa, fold_legal=fl)
        gr = greedy(qr, r, p, s, pa, fold_legal=fl)
        cb = 'F' if gb == F else ('공' if gb in AGG else '수')
        cr = 'F' if gr == F else ('공' if gr in AGG else '수')
        k = (f'{cb}→{cr}', TER(s))
        c = move.setdefault(k, [0, 0.0])
        c[0] += 1
        c[1] += w
        wtot += w
        wagg_b += w * (cb == '공')
        wagg_r += w * (cr == '공')
    return move, wagg_b / wtot, wagg_r / wtot


def main():
    for cond in ('regret_cfr_a30', 'regret_cfr_a100'):
        print(f"\n===== {cond} (5시드 합산) =====")
        fpm = [[], [], []]
        fpneg = []
        agg = {}
        opened_all = []
        for sd in range(1, 6):
            qb = QTable.load(BASE / f'chec_a30_s{sd}' / 'qtable.pkl')
            qr = QTable.load(REG / f'{cond}_s{sd}' / 'qtable.pkl')
            means, negfrac, _ = fingerprint(qr)
            for t in range(3):
                fpm[t].append(means[t])
            fpneg.append(negfrac)
            move, opened = policy_diff(qb, qr)
            for k, (c, w) in move.items():
                a = agg.setdefault(k, [0, 0.0])
                a[0] += c
                a[1] += w
            opened_all += opened
        print("[A 보정 대조] Q(FOLD) 방문가중 평균 (시드 평균): "
              + " / ".join(f"{TNAME[t]} {sum(fpm[t])/5:+.2f}" for t in range(3))
              + f" | 음수 셀 {sum(fpneg)/5*100:.0f}%")
        wtot = sum(w for _, w in agg.values()) or 1
        print("[B 정책 이동] (기준선 방문가중 비율 / 셀수)")
        for kind in ('불변(FOLD)', '불변(지속)', 'FOLD→지속', '지속→FOLD'):
            row = []
            for t in range(3):
                c, w = agg.get((kind, t), (0, 0.0))
                row.append(f"{TNAME[t]} {w/wtot*100:5.1f}%/{c:4d}")
            print(f"  {kind:10} " + "  ".join(row))
        if opened_all:
            wpos = sum(w for q, w in opened_all if q > 0)
            wneg = sum(w for q, w in opened_all if q <= 0)
            print(f"[C 기전] FOLD→지속 셀의 기준선 지속최선Q: 양수 가중 "
                  f"{wpos/(wpos+wneg)*100:.0f}% (셀 {len(opened_all)}개)")
        iagg = {}
        aggb = aggr = 0.0
        for sd in range(1, 6):
            qb = QTable.load(BASE / f'chec_a30_s{sd}' / 'qtable.pkl')
            qr = QTable.load(REG / f'{cond}_s{sd}' / 'qtable.pkl')
            move, ab, ar = initiative_diff(qb, qr)
            aggb += ab / 5
            aggr += ar / 5
            for k, (c, w) in move.items():
                a = iagg.setdefault(k, [0, 0.0])
                a[0] += c
                a[1] += w
        print(f"[D 자기 주도 셀] 공격 행동 방문가중 비중: 기준선 {aggb*100:.1f}% → "
              f"regret {aggr*100:.1f}%")
        iwtot = sum(w for _, w in iagg.values()) or 1
        changed = [(k, v) for k, v in iagg.items() if k[0][0] != k[0][2]]
        for (kind, t), (c, w) in sorted(changed, key=lambda kv: -kv[1][1])[:8]:
            print(f"    {kind} {TNAME[t]}: {w/iwtot*100:5.1f}% / {c}셀")
        out = REG / f'dissect_{cond}.csv'
        with open(out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['kind', 'tercile', 'cells', 'weight'])
            for (kind, t), (c, wt) in sorted(agg.items()):
                w.writerow([kind, TNAME[t], c, f'{wt:.0f}'])
        print(f"saved {out}")


if __name__ == '__main__':
    main()
