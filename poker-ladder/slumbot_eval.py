# -*- coding: utf-8 -*-
"""Slumbot API 평가 어댑터 — ladder 스키마 판 (레거시 slumbot_eval.py 이식).

프로토콜: POST slumbot.com/api/new_hand {token} → 핸드 상태 / POST /api/act {token, incr}.
  블라인드 50/100, 스택 20,000(=200bb, 매 핸드 리셋). client_pos 0=BB, 1=SB(버튼).
  액션 문자열: 스트리트 '/' 구분, k(체크)/c(콜)/f(폴드)/bN(스트리트 누적 N까지 벳).
  응답 winnings(칩)·baseline_winnings(분산감소). mbb/g = winnings×10.

ladder 판 차이: 상태 = 런의 카드축(qtable.pkl meta['card'] — legacy8/ehs20/ehs50)의
  bucket_raw, 행동 = meta['actions'](A8/A12)의 레이즈 메뉴. 나머지(재생·복구·로테이션) 동일.
정직한 한계: 스택 200bb(학습 100bb) 분포 이동, HTTP 왕복 지연.

usage: python slumbot_eval.py RUN_DIR N_HANDS [--verbose]
  RUN_DIR 예: ../results/32_ehs_k20/k20/chec_a30_s1
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
from actions import Action, _RAISE_PCT, _RAISES
from cards import make_cards
from defs import Position, PrevAction, Round
from qtable import QTable

HOST = "https://slumbot.com"
SB, BB, STACK = 50, 100, 20000
ROTATE_EVERY = 2000     # 세션당 핸드 한도(~3.5k 관측) 예방 토큰 교체


def api(path, payload, retries=5):
    for i in range(retries):
        try:
            req = urllib.request.Request(
                HOST + path, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


class HandState:
    """Slumbot 액션 문자열 재생 → (차례, 스트리트 기여, 팟, 상대 직전행동) 복원.
    좌석 0=SB, 1=BB. client_pos=0 → 클라이언트가 BB(좌석1)."""

    def __init__(self, client_pos):
        self.seat_client = 1 if client_pos == 0 else 0
        self.street = 0
        self.pot_prev = 0
        self.contrib = {0: SB, 1: BB}
        self.spent = {0: 0, 1: 0}
        self.to_act = 0                     # 프리플랍 첫 액터 = SB
        self.last_raise = BB
        self.prev_opp = PrevAction.NONE
        self.done = False

    def _advance_street(self):
        self.pot_prev += self.contrib[0] + self.contrib[1]
        self.spent[0] += self.contrib[0]; self.spent[1] += self.contrib[1]
        self.contrib = {0: 0, 1: 0}
        self.street += 1
        self.to_act = 1                     # 포스트플랍 첫 액터 = BB
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
            if actor != self.seat_client:   # 상대 행동 → PrevAction 분류 (동일 규칙)
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


def choose(qt, cards_ab, actions_version, hs, hole, board):
    rd = {0: Round.PREFLOP, 3: Round.FLOP, 4: Round.TURN, 5: Round.RIVER}[len(board)]
    pos = Position.BB if hs.seat_client == 1 else Position.SB
    s = cards_ab.bucket_raw(hole, board)
    me = hs.seat_client
    cmax = max(hs.contrib.values())
    facing = cmax - hs.contrib[me]
    cap = STACK - hs.spent[me]              # 이번 스트리트 bet-to 상한
    legal = []
    if facing > 0:
        legal += [Action.FOLD, Action.CALL]
    else:
        legal.append(Action.CHECK)
    if cmax < cap:
        legal += _RAISES[actions_version]
    a = qt.best_action(rd, pos, s, hs.prev_opp, legal)
    if a == Action.CHECK:
        return 'k', a
    if a == Action.CALL:
        return 'c', a
    if a == Action.FOLD:
        return 'f', a
    if a == Action.RAISE_ALLIN:
        return f'b{cap}', a
    target = cmax + max(int(hs.pot_total() * _RAISE_PCT[a]), BB)
    target = max(target, cmax + hs.last_raise)      # 최소 레이즈
    target = min(target, cap)
    if target <= cmax:                              # 레이즈 불가 → 콜/체크 강등
        return ('c' if facing > 0 else 'k'), a
    return f'b{target}', a


def main():
    run = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    verbose = '--verbose' in sys.argv
    qt = QTable.load(run / 'qtable.pkl')
    cards_ab = make_cards(qt.meta['card'])
    actions_version = qt.meta.get('actions', 'A8')
    label = f"{run.parent.name}/{run.name}"
    print(f"[slumbot] {label} card={qt.meta['card']} actions={actions_version} "
          f"n={n}", flush=True)

    token = None
    tot = tot_base = played = 0
    sq_w = sq_adj = 0.0
    t0 = time.time()
    while played < n:
        if token and played and played % ROTATE_EVERY == 0:
            token = None
        try:
            r = api("/api/new_hand", {"token": token} if token else {})
            if "client_pos" not in r:
                print(f"  [recover] new_hand 이상응답: {str(r)[:120]} — 토큰 재발급", flush=True)
                token = None
                r = api("/api/new_hand", {})
                if "client_pos" not in r:
                    time.sleep(10); continue
            token = r.get("token", token)
            while 'winnings' not in r:
                hs = HandState(r["client_pos"])
                hs.replay(r["action"])
                if hs.done:
                    break
                incr, a = choose(qt, cards_ab, actions_version, hs,
                                 r["hole_cards"], r.get("board", []))
                r2 = api("/api/act", {"token": token, "incr": incr})
                if "error_msg" in r2:
                    fb = 'c' if incr.startswith('b') else 'k'
                    r2 = api("/api/act", {"token": token, "incr": fb})
                    if "error_msg" in r2:
                        r2 = api("/api/act", {"token": token, "incr": 'f'})
                if "error_msg" in r2 or ('winnings' not in r2 and 'client_pos' not in r2):
                    print(f"  [recover] act 이상응답: {str(r2)[:120]} — 핸드 폐기·토큰 재발급", flush=True)
                    token = None
                    r = {'winnings': None}
                    break
                r = r2
        except Exception as e:
            print(f"  [recover] 예외 {type(e).__name__}: {e} — 토큰 재발급 후 계속", flush=True)
            token = None
            time.sleep(5)
            continue
        if r.get('winnings') is None:
            continue
        w = r['winnings']
        b = r.get('baseline_winnings', 0)
        tot += w; tot_base += b; played += 1
        sq_w += (w * 10) ** 2
        sq_adj += ((w - b) * 10) ** 2
        if verbose and played <= 5:
            print(f"  hand{played}: {r.get('action', '')} | win {w} base {b}", flush=True)
        if played % 100 == 0:
            el = time.time() - t0
            m = tot / played * 10
            ma = (tot - tot_base) / played * 10
            se = ((sq_w / played - m ** 2) / played) ** 0.5
            sea = ((sq_adj / played - ma ** 2) / played) ** 0.5
            print(f"[{label}] {played}/{n} | mbb/g {m:+.1f}±{se:.0f} | "
                  f"adj {ma:+.1f}±{sea:.0f} | {el:.0f}s ({el/played:.2f}s/hand)", flush=True)
    m = tot / played * 10
    ma = (tot - tot_base) / played * 10
    se = ((sq_w / played - m ** 2) / played) ** 0.5
    sea = ((sq_adj / played - ma ** 2) / played) ** 0.5
    print(f"==> {label} vsSlumbot n={played} mbb/g {m:+.1f}±{se:.1f} | "
          f"adj(w-b) {ma:+.1f}±{sea:.1f} | raw {tot} base {tot_base}", flush=True)


if __name__ == '__main__':
    main()
