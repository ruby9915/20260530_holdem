# -*- coding: utf-8 -*-
"""Slumbot API 평가 어댑터 — 학습된 Q-table을 외부 근사-GTO 상대로 평가 (VI장 한계 ③ 대응).

프로토콜: POST slumbot.com/api/new_hand {token} → 핸드 상태 / POST /api/act {token, incr}.
  블라인드 50/100, 스택 20,000(=200bb, 매 핸드 리셋). client_pos 0=BB, 1=SB(버튼).
  액션 문자열: 스트리트를 '/'로 구분, 토큰 k(체크)/c(콜)/f(폴드)/bN(그 스트리트 누적 N까지 벳).
  응답에 winnings(칩)·baseline_winnings(분산감소 기준값) 제공. mbb/g = winnings×10.

상태 매핑: Round=보드 장수, Position=client_pos, State=첸점수(프리플랍)/treys 백분위(포스트플랍),
  PrevAction=상대의 현 스트리트 마지막 행동을 pot 대비 크기로 분류(우리 classify와 동일 규칙).
행동 매핑: CHECK→k, CALL→c, FOLD→f, RAISE_f→b(현 최대 + int(pot×f)) [최소레이즈·스택 클램프],
  RAISE_ALLIN→b(스트리트 상한).
정직한 한계: 스택 깊이 200bb(학습 100bb)의 분포 이동, HTTP 왕복 지연.

usage: python slumbot_eval.py RUN_DIR N_HANDS [--verbose]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from abstraction import Round, Position, State, PrevAction, Action, _chen_to_state
from qlearning import QLearning
from treys import Card as TreysCard, Evaluator

RES = Path(__file__).resolve().parent.parent / "results"
HOST = "https://slumbot.com"
SB, BB, STACK = 50, 100, 20000
_ev = Evaluator()
_RANK_NUM = {r: i for i, r in enumerate("23456789TJQKA", start=2)}
_RANK_VAL = {"A": 10, "K": 8, "Q": 7, "J": 6, "T": 5, "9": 4.5, "8": 4, "7": 3.5,
             "6": 3, "5": 2.5, "4": 2, "3": 1.5, "2": 1}


def api(path, payload, retries=5):
    for i in range(retries):
        try:
            req = urllib.request.Request(
                HOST + path, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def chen_state(cards):  # 카드 문자열("Ks") 버전 첸 점수
    r1, s1 = cards[0][0], cards[0][1]
    r2, s2 = cards[1][0], cards[1][1]
    n1, n2 = _RANK_NUM[r1], _RANK_NUM[r2]
    high = r1 if n1 >= n2 else r2
    hi, lo = max(n1, n2), min(n1, n2)
    score = _RANK_VAL[high]
    if r1 == r2:
        score = max(score * 2, 5)
    if s1 == s2:
        score += 2
    if r1 != r2:
        gap = hi - lo - 1
        score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
        if hi < 12 and gap <= 1:
            score += 1
    return _chen_to_state(score)


def board_state(hole, board):
    h = [TreysCard.new(c) for c in hole]
    b = [TreysCard.new(c) for c in board]
    pct = _ev.evaluate(b, h) / 7462.0
    for th, st_ in [(.125, State.PREMIUM), (.25, State.STRONG), (.375, State.GOOD),
                    (.5, State.DECENT), (.625, State.MEDIOCRE), (.75, State.WEAK),
                    (.875, State.POOR)]:
        if pct < th:
            return st_
    return State.TRASH


class HandState:
    """Slumbot 액션 문자열을 재생해 (누구 차례, 스트리트 기여, 팟, 상대 직전행동)을 복원."""

    def __init__(self, client_pos):
        self.client = client_pos            # 0=BB, 1=SB
        self.street = 0
        self.pot_prev = 0                   # 이전 스트리트까지의 팟
        self.contrib = {0: 0, 1: 0}         # 현 스트리트 기여 (pos 0=SB? → 아래 주석)
        # 좌석 인덱스: 0=SB, 1=BB 로 통일. client 좌석 = 1-client_pos? Slumbot 규약:
        # client_pos=0 → 클라이언트가 BB(좌석1), client_pos=1 → 클라이언트가 SB(좌석0).
        self.seat_client = 1 if client_pos == 0 else 0
        self.contrib = {0: SB, 1: BB}       # 프리플랍 블라인드
        self.spent = {0: 0, 1: 0}           # 이전 스트리트 누적(스택 상한용)
        self.to_act = 0                     # 프리플랍 첫 액터 = SB(좌석0)
        self.last_raise = BB
        self.prev_opp = PrevAction.NONE     # 상대의 현 스트리트 마지막 행동 분류
        self.done = False

    def _advance_street(self):
        self.pot_prev += self.contrib[0] + self.contrib[1]
        self.spent[0] += self.contrib[0]; self.spent[1] += self.contrib[1]
        self.contrib = {0: 0, 1: 0}
        self.street += 1
        self.to_act = 1                     # 포스트플랍 첫 액터 = BB(좌석1)
        self.last_raise = BB
        self.prev_opp = PrevAction.NONE

    def pot_total(self):
        return self.pot_prev + self.contrib[0] + self.contrib[1]

    def replay(self, action_str):
        i, seg = 0, action_str
        while i < len(seg):
            ch = seg[i]
            if ch == '/':
                self._advance_street(); i += 1; continue
            actor = self.to_act
            pot_before = self.pot_total()
            cmax = max(self.contrib.values())
            if ch == 'k':
                inv, i = 0, i + 1
                new = self.contrib[actor]
            elif ch == 'c':
                new = cmax; inv = new - self.contrib[actor]; i += 1
            elif ch == 'f':
                self.done = True; i += 1
                return
            elif ch == 'b':
                j = i + 1
                while j < len(seg) and seg[j].isdigit():
                    j += 1
                new = int(seg[i + 1:j]); i = j
                inv = new - self.contrib[actor]
                self.last_raise = max(new - cmax, BB)
            else:
                raise ValueError(f"bad token {ch!r} in {action_str!r}")
            # 상대 행동이면 PrevAction 분류 (우리 classify_opp_action과 동일 규칙)
            if actor != self.seat_client:
                cca = cmax - (new - inv)
                if ch in ('k', 'c') or inv <= cca + 1e-9:
                    self.prev_opp = PrevAction.CHECK_CALL
                else:
                    extra = inv - cca
                    allin = (self.spent[actor] + new) >= STACK
                    self.prev_opp = (PrevAction.BIG_RAISE
                                     if (extra > pot_before * 0.5 or allin)
                                     else PrevAction.SMALL_RAISE)
            self.contrib[actor] = new
            self.to_act = 1 - actor


ROUNDS = [Round.PREFLOP, Round.FLOP, Round.TURN, Round.RIVER]


def choose(ql, hs, hole, board, verbose=False):
    rd = {0: Round.PREFLOP, 3: Round.FLOP, 4: Round.TURN, 5: Round.RIVER}[len(board)]
    # 우리 학습 규약: player_idx 0=BB, 1=SB (pk_to_position). Slumbot 좌석 0=SB,1=BB
    pos = Position.BB if hs.seat_client == 1 else Position.SB
    st = chen_state(hole) if not board else board_state(hole, board)
    me, opp = hs.seat_client, 1 - hs.seat_client
    cmax = max(hs.contrib.values())
    facing = cmax - hs.contrib[me]
    cap = STACK - hs.spent[me]              # 이번 스트리트 bet-to 상한
    legal = []
    if facing > 0:
        legal.append(Action.FOLD)
        legal.append(Action.CALL)
    else:
        legal.append(Action.CHECK)
    if cmax < cap:
        legal += [Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
                  Action.RAISE_100, Action.RAISE_ALLIN]
    a = ql.best_action(rd, pos, st, hs.prev_opp, legal)
    if a == Action.CHECK:
        return 'k', a
    if a == Action.CALL:
        return 'c', a
    if a == Action.FOLD:
        return 'f', a
    if a == Action.RAISE_ALLIN:
        return f'b{cap}', a
    frac = {Action.RAISE_25: .25, Action.RAISE_50: .50,
            Action.RAISE_75: .75, Action.RAISE_100: 1.0}[a]
    target = cmax + max(int(hs.pot_total() * frac), BB)
    target = max(target, cmax + hs.last_raise)      # 최소 레이즈
    target = min(target, cap)
    if target <= cmax:                              # 레이즈 불가면 콜/체크로 강등
        return ('c' if facing > 0 else 'k'), a
    return f'b{target}', a


def main():
    run = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    verbose = '--verbose' in sys.argv
    ql = QLearning.load(str(RES / run / "eval_results.pkl"))
    token = None
    tot, tot_base, played = 0, 0, 0
    t0 = time.time()
    for h in range(n):
        r = api("/api/new_hand", {"token": token} if token else {})
        token = r.get("token", token)
        while 'winnings' not in r:
            hs = HandState(r["client_pos"])
            hs.replay(r["action"])
            if hs.done:
                break
            incr, a = choose(ql, hs, r["hole_cards"], r.get("board", []), verbose)
            r2 = api("/api/act", {"token": token, "incr": incr})
            if "error_msg" in r2:
                # 비합법 증분(드묾): 콜/체크로 폴백
                fb = 'c' if incr.startswith('b') else 'k'
                r2 = api("/api/act", {"token": token, "incr": fb})
                if "error_msg" in r2:
                    r2 = api("/api/act", {"token": token, "incr": 'f'})
            r = r2
        w = r.get('winnings', 0)
        b = r.get('baseline_winnings', 0)
        tot += w; tot_base += b; played += 1
        if verbose and h < 5:
            print(f"  hand{h}: {r.get('action','')} | win {w} base {b}", flush=True)
        if (h + 1) % 100 == 0:
            el = time.time() - t0
            print(f"[{run}] {h+1}/{n} | mbb/g {tot/played*10:+.1f} | "
                  f"baseline-adj {(tot-tot_base)/played*10:+.1f} | {el:.0f}s "
                  f"({el/(h+1):.2f}s/hand)", flush=True)
    print(f"==> {run} vsSlumbot n={played} mbb/g {tot/played*10:+.1f} | "
          f"adj(w-b) {(tot-tot_base)/played*10:+.1f} | raw {tot} base {tot_base}", flush=True)


if __name__ == '__main__':
    main()
