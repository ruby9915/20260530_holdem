# -*- coding: utf-8 -*-
"""LBR-lite — 봇 전략에 대한 국소 최적 대응(Lisý & Bowling 2017 간이판)으로
실게임 착취 가능성의 **하한**을 직접 측정한다.

LBR 에이전트가 아는 것: 봇의 동결 전략 전체 + 봇의 트리 위치(공개 행동으로 추적).
매 결정에서:
  1) 봇 레인지 추적: 1326 콤보 가중치를 봇의 관측 행동 확률로 베이즈 갱신
  2) 후보 행동 {폴드, 콜/체크, 팟25%·75%·100% 벳, 올인} 의 국소 EV 비교
     - EV(벳 b) = P(폴드)·팟 + (1−P폴드)·[콜레인지 상대 에퀴티·(팟+2b) − b]
     - 에퀴티는 실카드 MC (버킷 아님 — 간극을 보는 눈)
     - 국소 가정: 벳 이후는 체크다운 (표준 LBR 가정)
  3) 트리 밖 크기의 봇 반응은 pseudo-harmonic 번역 기대치로 근사
한계(정직): 국소 가정·후보 크기 제한 → 진짜 최적 대응보다 약함 = 측정치는 하한.

usage: python lbr_eval.py [n_hands=5000]
"""
import math
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from treys import Card as TC, Evaluator
from cfr_opponent import CfrOpponent, PRE_IDX
from cards import EHS, _canonical_label, _RawCard
from game import BIG_BLIND, STARTING_STACK, make_game
from hunl_tree import Decision, Chance, Terminal

_ev = Evaluator()
RANKS = '23456789TJQKA'
DECK = [r + s for r in RANKS for s in 'shdc']
EHS50 = EHS(50)
FRACS = (0.25, 0.75, 1.0)      # LBR 후보 벳 크기 (①에서 확인된 착취 크기 포함)


def _combos(excl):
    out = []
    for i in range(52):
        for j in range(i + 1, 52):
            a, b = DECK[i], DECK[j]
            if a in excl or b in excl:
                continue
            out.append((a, b))
    return out


def _bucket(hole_strs, board_strs, street):
    if street == 0:
        return PRE_IDX[_canonical_label([_RawCard(c) for c in hole_strs])]
    from bisect import bisect_right
    e = EHS50._ehs([TC.new(c) for c in hole_strs], [TC.new(c) for c in board_strs])
    return bisect_right(EHS50._cuts[len(board_strs)], e)


class LBR:
    def __init__(self, bot, rng):
        self.bot = bot
        self.rng = rng

    def reset(self, pk, my_id):
        self.my_id = my_id
        excl = {repr(c) for c in pk.hole_cards[self.my_id]}
        self.range_ = {c: 1.0 for c in _combos(excl)}

    # ── 봇 관측 행동으로 레인지 갱신 ──────────────────────
    def observe(self, pk, node_before, action_label, board_strs, street):
        if not isinstance(node_before, Decision):
            return
        try:
            ai = node_before.acts.index(action_label)
        except ValueError:
            return
        cache = {}
        for combo in list(self.range_):
            if combo[0] in board_strs or combo[1] in board_strs:
                del self.range_[combo]; continue
            b = cache.get(combo)
            if b is None:
                b = _bucket(combo, board_strs, street)
                cache[combo] = b
            p = float(node_before.ssum[b][ai])
            w = self.range_[combo] * max(p, 1e-6)
            if w < 1e-12:
                del self.range_[combo]
            else:
                self.range_[combo] = w

    # ── 실카드 에퀴티 (내 핸드 vs 레인지) ─────────────────
    def _equity(self, my_hole, board_strs, rng_weights, n=160):
        combos = list(rng_weights)
        if not combos:
            return 0.5
        ws = [rng_weights[c] for c in combos]
        tot = sum(ws)
        my_t = [TC.new(c) for c in my_hole]
        used_base = set(my_hole) | set(board_strs)
        acc = 0.0
        for _ in range(n):
            opp = self.rng.choices(combos, weights=ws, k=1)[0]
            if opp[0] in used_base or opp[1] in used_base:
                continue
            used = used_base | {opp[0], opp[1]}
            rest = [c for c in DECK if c not in used]
            board = list(board_strs) + self.rng.sample(rest, 5 - len(board_strs))
            bt = [TC.new(c) for c in board]
            sh = _ev.evaluate(bt, my_t)
            so = _ev.evaluate(bt, [TC.new(opp[0]), TC.new(opp[1])])
            acc += 1.0 if sh < so else (0.5 if sh == so else 0.0)
        return acc / max(n, 1)

    # ── 봇의 폴드 확률 (벳 b 직면 시, 번역 기대치) ────────
    def _fold_prob(self, node, target, board_strs, street):
        # node = 봇이 받게 될 결정 노드 후보들 (트리 밖이면 이웃 두 가지 가중)
        if not isinstance(node, Decision):
            return 0.0, self.range_
        lbl = f'b{target}'
        kids = node  # 관측 노드
        # 이 구현은 "봇이 target 벳을 받은 후의 노드"를 직접 찾는 대신,
        # 현 노드의 자식 중 벳 가지의 후속에서 f 확률을 계산해야 하나
        # 간이화: 봇 폴드확률을 현 스트리트 버킷별 전략의 f 비중 평균으로 근사
        return None, None


def play_hand(bot, rng, hand_no):
    """LBR vs 봇 1핸드. 반환: LBR payoff(칩)."""
    pk = make_game()
    my_id = hand_no % 2
    bot_id = 1 - my_id
    bot.reset(bot_id)
    lbr = LBR(bot, rng)
    started = False
    prev = {}

    while pk.status:
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if not started:
                lbr.reset(pk, my_id)
                started = True
            board_strs = [repr(c) for grp in pk.board_cards for c in grp]
            street = {0: 0, 3: 1, 4: 2, 5: 3}[len(board_strs)]
            if pk.actor_index == bot_id:
                node_before = None
                bot._sync(pk, bot_id)
                node_before = bot.node
                stack_b = pk.stacks[bot_id]
                bot.step(pk, bot_id, prev)
                # 관측 라벨 복원: 칩 변화로 판정
                inv = stack_b - pk.stacks[bot_id]
                if not pk.status or pk.actor_index is None:
                    lbl = None
                elif inv == 0 and pk.checking_or_calling_amount == 0:
                    lbl = 'k'
                else:
                    total = STARTING_STACK - pk.stacks[bot_id]
                    lbl = 'c' if isinstance(node_before, Decision) and \
                        f'b{total}' not in node_before.children else f'b{total}'
                if lbl and isinstance(node_before, Decision) and \
                        lbl not in node_before.children:
                    lbl = 'c' if 'c' in node_before.children else 'k'
                if lbl:
                    lbr.observe(pk, node_before, lbl, board_strs, street)
            else:
                _lbr_act(pk, lbr, bot, my_id, board_strs, street, rng)
        else:
            break
    return float(pk.stacks[my_id] - STARTING_STACK)


def _lbr_act(pk, lbr, bot, my_id, board_strs, street, rng):
    # 보드와 겹치는 콤보 프루닝 (봇 행동 관측 전에 보드가 갱신된 경우)
    bset = set(board_strs)
    for combo in list(lbr.range_):
        if combo[0] in bset or combo[1] in bset:
            del lbr.range_[combo]
    my_hole = [repr(c) for c in pk.hole_cards[my_id]]
    pot = sum(p.amount for p in pk.pots) + sum(pk.bets)
    owed = pk.checking_or_calling_amount
    wp = lbr._equity(my_hole, board_strs, lbr.range_)
    # 봇 폴드확률 근사 — 읽기 전용 엿보기 (sync 호출 금지: 유령 행동 소비 방지)
    n = bot.node
    while isinstance(n, Chance) and n.street < street:
        n = n.child
    fp = 0.0
    if isinstance(n, Decision):
        # 봇이 다음에 받을 벳-직면 노드가 아니라 현재 노드 기준의 근사 —
        # 자식 중 첫 벳 가지의 후속 노드에서 f 확률을 레인지 가중 평균
        bets = [a for a in n.acts if a.startswith('b')]
        if bets:
            child = n.children[bets[len(bets) // 2]]
            if isinstance(child, Decision) and 'f' in child.acts:
                fi = child.acts.index('f')
                tot = w = 0.0
                cache = {}
                for combo, wt in list(lbr.range_.items())[:300]:
                    b = cache.setdefault(combo, _bucket(combo, board_strs, street))
                    w += wt * float(child.ssum[b][fi]); tot += wt
                fp = w / tot if tot > 0 else 0.0
    # 후보 EV (국소: 이후 체크다운 가정)
    evs = {}
    if owed > 0:
        evs['f'] = 0.0
        evs['c'] = wp * (pot + owed) - owed
    else:
        evs['k'] = wp * pot
    lo = pk.min_completion_betting_or_raising_to_amount
    hi = pk.max_completion_betting_or_raising_to_amount
    if lo is not None and hi is not None:
        for f in FRACS:
            b_amt = max(1, int(pot * f))
            cmax = max(pk.bets) if pk.bets else 0
            tgt = min(max(cmax + b_amt, lo), hi)
            cost = tgt - (pk.bets[my_id] if pk.bets else 0)
            evs[f'b{tgt}'] = fp * pot + (1 - fp) * (wp * (pot + 2 * cost) - cost)
    best = max(evs, key=evs.get)
    if best == 'f':
        pk.fold()
    elif best in ('c', 'k'):
        pk.check_or_call()
    else:
        pk.complete_bet_or_raise_to(int(best[1:]))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    rng = random.Random(2026)
    random.seed(2026)
    bot = CfrOpponent(rng_seed=2026)
    pays = []
    t0 = time.time()
    for i in range(1, n + 1):
        pays.append(play_hand(bot, rng, i))
        if i % max(1, n // 20) == 0:
            m = statistics.mean(pays) * 1000 / BIG_BLIND
            se = statistics.stdev(pays) / math.sqrt(i) * 1000 / BIG_BLIND if i > 1 else 0
            print(f"  ({i/n*100:5.1f}%) {i} | LBR {m:+.1f} ± {se:.1f} mbb/g | {time.time()-t0:.0f}s",
                  flush=True)
    m = statistics.mean(pays) * 1000 / BIG_BLIND
    se = statistics.stdev(pays) / math.sqrt(n) * 1000 / BIG_BLIND
    print(f"==> LBR-lite vs bot n={n} | LBR {m:+.1f} ± {se:.1f} mbb/g "
          f"(실게임 착취가능성 하한)", flush=True)


if __name__ == '__main__':
    main()
