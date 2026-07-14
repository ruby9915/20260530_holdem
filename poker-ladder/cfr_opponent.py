# -*- coding: utf-8 -*-
"""CFR+ 동결 전략 상대 모듈 (사다리 5·6단 학습 상대 — 4단 부품 ⑤).

poker-cfrplus 의 베팅 트리 + 평균 전략(npz)을 로드해, pokerkit 대국에서
step-상대로 행동한다. 좌석 규약: pokerkit player0=BB / 트리 seat0=SB.

동작:
  reset(opp_id)   : 핸드 시작 — 트리 루트로, 좌석 매핑 고정
  step(pk, opp_id, prev): ① 학습자 행동·라운드 경계를 트리에서 소비(동기화)
                          ② 자기 버킷의 평균 전략으로 행동 표본 → pokerkit 실행
                          ③ 자기 행동을 학습자 관점 PrevAction 으로 분류(기존 규약)
번역: 학습자 벳이 트리에 없으면 pseudo-harmonic 확률 배분(Ganzfried 2013)으로
가장 가까운 두 가지에 매핑 — 발동 횟수를 계수(self.translations)해 실측 공개.
"""
import random
import sys
from pathlib import Path

import numpy as np

LADDER = Path(__file__).resolve().parent
CFRP = LADDER.parent / 'poker-cfrplus'
sys.path.insert(0, str(CFRP))
sys.path.insert(0, str(LADDER))

from hunl_tree import Chance, Decision, Terminal, build  # noqa: E402
from cards import make_cards, _canonical_label  # noqa: E402
from defs import classify_opp_action, pk_to_round, pot_size  # noqa: E402

K = 50

# 프리플랍 169 클래스 색인 — 솔버(combo_weights)·행렬(PRE_LABELS)과 동일 순서
_RANKS = 'AKQJT98765432'
PRE_IDX = {}
for _i, _r1 in enumerate(_RANKS):
    for _j, _r2 in enumerate(_RANKS):
        if _i == _j:
            PRE_IDX[_r1 + _r2] = len(PRE_IDX)
        elif _j > _i:
            PRE_IDX[_r1 + _r2 + 's'] = len(PRE_IDX)
            PRE_IDX[_r1 + _r2 + 'o'] = len(PRE_IDX)


class CfrOpponent:
    def __init__(self, strategy_path=None, rng_seed=None):
        path = Path(strategy_path or CFRP / 'data' / f'hunl_frozen_k{K}.npz')
        self.root, _ = build()
        self._nodes = []

        def collect(n):
            if isinstance(n, Decision):
                n.acts = sorted(n.children)
                self._nodes.append(n)
                for c in n.children.values():
                    collect(c)
            elif isinstance(n, Chance):
                collect(n.child)
        sys.setrecursionlimit(300000)
        collect(self.root)

        d = np.load(path)
        for i, n in enumerate(self._nodes):
            ss = d[f's{i}']
            tot = ss.sum(axis=1, keepdims=True)
            kb = ss.shape[0]
            n.ssum = np.where(tot > 0, ss / np.where(tot > 0, tot, 1),
                              1.0 / ss.shape[1])
        self.cards = make_cards(f'ehs{K}')
        self.rng = random.Random(rng_seed)
        self.translations = 0            # 번역 발동 계수 (실측 공개용)
        self.decisions = 0
        self.desyncs = 0                 # 트리-실제 탈동기 (합법성 강등) 계수
        self.node = None

    # ── 핸드 시작 ──────────────────────────────────────────
    def reset(self, opp_id: int):
        self.node = self.root
        # pokerkit: player0=BB, player1=SB / 트리: seat0=SB, seat1=BB
        self.seat = 0 if opp_id == 1 else 1

    # ── 트리 동기화: 학습자 행동·찬스 소비 ─────────────────
    def _sync(self, pk, opp_id):
        pk_street = pk_to_round(pk).value
        learner_pk = 1 - opp_id
        # 학습자의 트리 좌석 = 1 − 내 좌석; 기여 = 시작스택 − 현재스택
        lr_seat = 1 - self.seat
        lr_contrib = 200 - pk.stacks[learner_pk]
        guard = 0
        while True:
            guard += 1
            if guard > 50:
                raise RuntimeError('cfr_opponent sync 발산')
            n = self.node
            if isinstance(n, Chance):
                if n.street < pk_street:
                    self.node = n.child
                    continue
                break
            if isinstance(n, Terminal):
                break
            if n.to_act == self.seat and n.street == pk_street:
                break                                  # 내 차례 — 동기화 완료
            # 학습자 결정 소비
            if lr_contrib > n.contrib[lr_seat]:
                if lr_contrib == n.contrib[1 - lr_seat] and 'c' in n.children:
                    self.node = n.children['c']        # 콜 (기여 동액화)
                elif f'b{lr_contrib}' in n.children:
                    self.node = n.children[f'b{lr_contrib}']
                else:
                    self.node = self._translate(n, lr_contrib, lr_seat)
            else:                                       # 칩 변화 없음 → 체크
                self.node = n.children.get('k', n.children.get('c'))

    def _translate(self, n, target, lr_seat):
        """트리 밖 벳 → pseudo-harmonic 확률 배분 (Ganzfried & Sandholm 2013)."""
        self.translations += 1
        bets = sorted((int(a[1:]), a) for a in n.acts if a.startswith('b'))
        if not bets:
            return n.children.get('c', next(iter(n.children.values())))
        below = [b for b in bets if b[0] <= target]
        above = [b for b in bets if b[0] >= target]
        if not below:
            return n.children[above[0][1]]
        if not above:
            return n.children[below[-1][1]]
        A, la = below[-1]
        B, lb = above[0]
        if A == B:
            return n.children[la]
        pot = n.contrib[0] + n.contrib[1]
        a, b, x = A / pot, B / pot, target / pot
        p_a = ((b - x) * (1 + a)) / ((b - a) * (1 + x))
        return n.children[la if self.rng.random() < p_a else lb]

    # ── 내 행동 ────────────────────────────────────────────
    def step(self, pk, opp_id: int, prev_action_by_round: dict):
        self._sync(pk, opp_id)
        n = self.node
        r_before = pk_to_round(pk)
        pot_before = pot_size(pk)
        cca_before = pk.checking_or_calling_amount
        stack_before = pk.stacks[opp_id]
        max_to = pk.max_completion_betting_or_raising_to_amount

        if not isinstance(n, Decision):
            # 동기화가 종단/찬스에 머묾(이상) — 안전 강등: 체크/콜
            self.desyncs += 1
            pk.check_or_call()
        else:
            self.decisions += 1
            bucket = self._bucket(pk, opp_id, n.street)
            sig = n.ssum[bucket]
            ai = self.rng.choices(range(len(n.acts)), weights=sig, k=1)[0]
            a = n.acts[ai]
            # 합법성 방어막: 트리-실제 탈동기 시 강등 (계수해 실측 공개)
            if a == 'f' and not pk.can_fold():
                self.desyncs += 1
                a = 'k' if 'k' in n.children else 'c'
            elif a.startswith('b') and not pk.can_complete_bet_or_raise_to():
                self.desyncs += 1
                a = 'c' if 'c' in n.children else 'k'
            self._execute(pk, opp_id, n, a)
            self.node = n.children[a]

        # 내 행동을 학습자 관점 PrevAction 으로 분류 (기존 규약 그대로)
        stack_after = pk.stacks[opp_id]
        invest = stack_before - stack_after
        was_allin = (stack_after == 0 and invest > cca_before + 1e-9) \
                    or (max_to == stack_before and invest > cca_before + 1e-9)
        pa = classify_opp_action(stack_before, stack_after, cca_before,
                                 pot_before, was_allin=was_allin)
        if pa is not None:
            prev_action_by_round[r_before] = pa

    def _bucket(self, pk, opp_id, street):
        if street == 0:                                # 프리플랍 169 무손실 색인
            hand = list(pk.hole_cards[opp_id])
            return PRE_IDX[_canonical_label(hand)]
        return self.cards.state_of(pk, opp_id)         # 포스트플랍 E[HS] K버킷

    def _execute(self, pk, opp_id, n, a):
        if a == 'f':
            pk.fold()
        elif a in ('k', 'c'):
            pk.check_or_call()
        else:
            target = int(a[1:])                        # 핸드 누적 기여 목표
            # 이번 라운드 bet-to = 목표 총기여 − 이전 라운드까지의 투입
            spent_prev = 200 - pk.stacks[opp_id] - (pk.bets[opp_id] if pk.bets else 0)
            bet_to = target - spent_prev
            lo = pk.min_completion_betting_or_raising_to_amount
            hi = pk.max_completion_betting_or_raising_to_amount
            if lo is None or hi is None:
                pk.check_or_call()
                return
            bet_to = max(lo, min(bet_to, hi))
            pk.complete_bet_or_raise_to(bet_to)
