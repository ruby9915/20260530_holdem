"""
evaluate_pypokerengine.py
─────────────────────────────────────────────────────────────────────
19번 최종 Softmax 모델(eval_results.pkl)을 **외부 오픈소스 엔진
PyPokerEngine** 위에서 평가한다. (20번 실험 재현 스크립트)

본 스크립트는 학습 엔진(pokerkit)으로 학습한 Q-테이블을, 전혀 다른
규칙 엔진인 PyPokerEngine 환경에 어댑터로 붙여 RandomPlayer /
HonestPlayer 와 헤즈업 대결시키고 mbb/g · SE · 95% CI 를 산출한다.

────────────────────────────────────────────────────────────────────
재현 메모 (실험일지 17.3절과 동일한 두 가지 정합화 처리)
  (1) 포지션 스왑: pokerkit 은 player0=딜러(SB)지만 학습 시
      pk_to_position 이 player0 을 BB 로 뒤집어 저장했다. 따라서
      PyPokerEngine 에서 딜러(버튼=SB)일 때 Q-테이블의 BB 칸을,
      논딜러(BB)일 때 SB 칸을 조회한다(반대로 스왑).
  (2) 미방문 FOLD 함정 회피: 합법 액션들의 Q 값이 모두 동률(예: 초기
      0.0)일 때 Enum 순서상 FOLD(0)가 뽑히는 자폭을 막기 위해
      CHECK → CALL → RAISE → FOLD 선호 순으로 동률을 깬다.

주의: 원본 일회성 스크립트는 파일로 보존되지 않았다. 본 파일은
실험일지 17절의 설계·정합화 규약에 따라 동일 동작을 재구성한 것이다.
난수 시드(124/125/126)는 PyPokerEngine 덱 셔플 + 상대 봇 무작위성을
지배하므로, 같은 시드에서 결과가 결정론적으로 재현된다.

────────────────────────────────────────────────────────────────────
사용법:
  # 단일 평가 (vs honest 10k, 시드 124)
  python evaluate_pypokerengine.py <pkl> --opp honest --games 10000 --seeds 124

  # 100k × 3 교차검증 (vs honest, 시드 124/125/126)
  python evaluate_pypokerengine.py <pkl> --opp honest --games 100000 --seeds 124 125 126

  # vs random 100k × 3
  python evaluate_pypokerengine.py <pkl> --opp random --games 100000 --seeds 124 125 126
"""
import argparse
import math
import random
import statistics
import sys
from pathlib import Path

# 같은 폴더의 학습 모듈/추상화에서 상수와 enum, Chen/treys 로직 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
from abstraction import (
    Round, Position, State, PrevAction, Action,
    _RANK_VAL, _RANK_NUM, _chen_to_state, _evaluator,
)
from qlearning import QLearning

from treys import Card as TreysCard
from pypokerengine.players import BasePokerPlayer
from pypokerengine.api.game import setup_config, start_poker
from pypokerengine.utils.card_utils import gen_cards, estimate_hole_card_win_rate


# ── 학습과 동일한 게임 상수 ────────────────────────────
STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2
SCALE          = 1000.0 / BIG_BLIND     # mbb/g 스케일 = 500
NB_SIMULATION  = 100                     # HonestPlayer 몬테카를로 시뮬 횟수

# 라운드별 베팅 사이즈 비율 (abstraction.execute_action 과 동일)
_RAISE_PCT = {
    Action.RAISE_25:  0.25,
    Action.RAISE_50:  0.50,
    Action.RAISE_75:  0.75,
    Action.RAISE_100: 1.00,
}

# PyPokerEngine 카드 문자열: suit(C/D/H/S) + rank(2..9,T,J,Q,K,A)
_SUIT_PPE_TO_TREYS = {'C': 'c', 'D': 'd', 'H': 'h', 'S': 's'}
_STREET_TO_ROUND = {
    'preflop': Round.PREFLOP, 'flop': Round.FLOP,
    'turn': Round.TURN, 'river': Round.RIVER,
}


# ─────────────────────────────────────────────────────────
# 카드/핸드 → State 버킷  (학습과 동일한 Chen + treys 백분위)
# ─────────────────────────────────────────────────────────
def _chen_score_ppe(hole: list[str]) -> float:
    """PyPokerEngine 카드 문자열 2장으로 Chen score 계산 (abstraction 과 동일 규칙)."""
    r1, s1 = hole[0][1], hole[0][0]
    r2, s2 = hole[1][1], hole[1][0]
    n1, n2 = _RANK_NUM[r1], _RANK_NUM[r2]
    high   = r1 if n1 >= n2 else r2
    hi_n, lo_n = max(n1, n2), min(n1, n2)
    suited = (s1 == s2)
    pair   = (r1 == r2)

    score = _RANK_VAL[high]
    if pair:
        score = max(score * 2, 5)
    if suited:
        score += 2
    if not pair:
        gap = hi_n - lo_n - 1
        if   gap == 0: pass
        elif gap == 1: score -= 1
        elif gap == 2: score -= 2
        elif gap == 3: score -= 4
        else:          score -= 5
        if hi_n < 12 and gap <= 1:
            score += 1
    return score


def _ppe_to_treys(card: str) -> int:
    return TreysCard.new(card[1] + _SUIT_PPE_TO_TREYS[card[0]])


def _hand_state(hole: list[str], community: list[str]) -> State:
    if len(community) == 0:
        return _chen_to_state(_chen_score_ppe(hole))
    h = [_ppe_to_treys(c) for c in hole]
    p = [_ppe_to_treys(c) for c in community]
    percentile = _evaluator.evaluate(p, h) / 7462.0
    if percentile < 0.125: return State.PREMIUM
    if percentile < 0.250: return State.STRONG
    if percentile < 0.375: return State.GOOD
    if percentile < 0.500: return State.DECENT
    if percentile < 0.625: return State.MEDIOCRE
    if percentile < 0.750: return State.WEAK
    if percentile < 0.875: return State.POOR
    return State.TRASH


# ─────────────────────────────────────────────────────────
# round_state → PrevAction  (상대의 현재 스트리트 직전 액션 압축)
# ─────────────────────────────────────────────────────────
def _estimate_pot(round_state) -> float:
    pot = round_state['pot']['main']['amount']
    for sp in round_state['pot'].get('side', []):
        pot += sp['amount']
    return pot


def _prev_action(round_state, opp_uuid: str, opp_stack_now: float) -> PrevAction:
    """현재 스트리트에서 상대가 마지막으로 한 자발적 액션을 PrevAction 으로 분류.

    abstraction.classify_opp_action 의 규약을 PyPokerEngine 액션 히스토리에
    맞춰 재구성한 것이다 (블라인드 포스팅은 자발적 액션이 아니므로 제외).
    """
    street = round_state['street']
    hist   = round_state['action_histories']

    running_pot = 0.0          # 타깃 레이즈 직전 팟 추정용 (paid 누적)
    target = None              # (entry, pot_before)
    for st in ('preflop', 'flop', 'turn', 'river'):
        for e in hist.get(st, []):
            act  = e.get('action', '').upper()
            paid = e.get('paid', e.get('amount', 0)) or 0
            if (st == street and e.get('uuid') == opp_uuid
                    and act in ('CALL', 'RAISE')):
                target = (e, running_pot)
            running_pot += paid

    if target is None:
        return PrevAction.NONE

    e, pot_before = target
    if e['action'].upper() == 'CALL':
        return PrevAction.CHECK_CALL

    # RAISE: 콜 위에 더 얹은 칩(add_amount)으로 SMALL/BIG 구분
    extra     = e.get('add_amount', e.get('amount', 0)) or 0
    was_allin = (opp_stack_now == 0)
    if was_allin or pot_before <= 0:
        return PrevAction.BIG_RAISE
    return PrevAction.SMALL_RAISE if (extra / pot_before) <= 0.5 else PrevAction.BIG_RAISE


# ─────────────────────────────────────────────────────────
# valid_actions(PyPokerEngine) → Action enum 목록 / 응답 변환
# ─────────────────────────────────────────────────────────
def _legal_actions(valid_actions) -> list[Action]:
    legal: list[Action] = []
    fold_a, call_a, raise_a = valid_actions[0], valid_actions[1], valid_actions[2]
    if fold_a['action'] == 'fold':
        legal.append(Action.FOLD)
    if call_a['action'] == 'call':
        legal.append(Action.CHECK if call_a['amount'] == 0 else Action.CALL)
    rmax = raise_a['amount']['max']
    if raise_a['action'] == 'raise' and rmax != -1:
        legal.extend([Action.RAISE_25, Action.RAISE_50,
                      Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN])
    return legal


def _to_ppe(action: Action, valid_actions, round_state):
    fold_a, call_a, raise_a = valid_actions[0], valid_actions[1], valid_actions[2]
    if action == Action.FOLD:
        return 'fold', 0
    if action in (Action.CHECK, Action.CALL):
        return 'call', call_a['amount']
    rmin, rmax = raise_a['amount']['min'], raise_a['amount']['max']
    if action == Action.RAISE_ALLIN:
        return 'raise', rmax
    pot = _estimate_pot(round_state) + call_a['amount']
    target = rmin + int(pot * _RAISE_PCT[action])
    target = max(rmin, min(rmax, target))
    return 'raise', target


# ─────────────────────────────────────────────────────────
# 우리 에이전트 (Q-테이블 그리디 + 정합화 처리)
# ─────────────────────────────────────────────────────────
class QTablePlayer(BasePokerPlayer):
    # 동률 시 FOLD 자폭을 피하기 위한 선호 순서 (일지 17.3-(2))
    _PREF = [Action.CHECK, Action.CALL,
             Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
             Action.RAISE_100, Action.RAISE_ALLIN, Action.FOLD]

    def __init__(self, ql: QLearning):
        super().__init__()
        self.ql = ql

    def declare_action(self, valid_actions, hole_card, round_state):
        seats   = round_state['seats']
        my_idx  = next(i for i, s in enumerate(seats) if s['uuid'] == self.uuid)
        opp     = next(s for s in seats if s['uuid'] != self.uuid)

        # (1) 포지션 스왑: 딜러(버튼=SB)면 BB 칸, 논딜러면 SB 칸 조회
        is_dealer = (my_idx == round_state['dealer_btn'])
        pos = Position.BB if is_dealer else Position.SB

        r  = _STREET_TO_ROUND[round_state['street']]
        s  = _hand_state(hole_card, round_state['community_card'])
        pa = _prev_action(round_state, opp['uuid'], opp['stack'])

        legal = _legal_actions(valid_actions)
        if not legal:
            return 'fold', 0

        a = self._greedy(r, pos, s, pa, legal)
        return _to_ppe(a, valid_actions, round_state)

    def _greedy(self, r, pos, s, pa, legal) -> Action:
        qmax = max(self.ql.get_q(r, pos, s, pa, a) for a in legal)
        tied = [a for a in legal if self.ql.get_q(r, pos, s, pa, a) == qmax]
        if len(tied) == 1:
            return tied[0]
        for a in self._PREF:               # (2) 동률은 선호 순서로 해소
            if a in tied:
                return a
        return tied[0]

    # 알림 메시지 (no-op)
    def receive_game_start_message(self, game_info):       pass
    def receive_round_start_message(self, rc, hole, seats): pass
    def receive_street_start_message(self, street, rs):     pass
    def receive_game_update_message(self, action, rs):      pass
    def receive_round_result_message(self, w, hi, rs):      pass


# ─────────────────────────────────────────────────────────
# 외부 상대 봇 (PyPokerEngine 튜토리얼 표준 구현)
# ─────────────────────────────────────────────────────────
class RandomPlayer(BasePokerPlayer):
    """합법 액션 중 하나를 무작위로 선택. 레이즈면 [min,max] 균등 샘플."""
    def declare_action(self, valid_actions, hole_card, round_state):
        choices = [va for va in valid_actions
                   if not (va['action'] == 'raise' and va['amount']['max'] == -1)]
        choice = random.choice(choices)
        if choice['action'] == 'raise':
            lo, hi = choice['amount']['min'], choice['amount']['max']
            return 'raise', random.randint(lo, hi)
        return choice['action'], choice['amount']

    def receive_game_start_message(self, game_info):       pass
    def receive_round_start_message(self, rc, hole, seats): pass
    def receive_street_start_message(self, street, rs):     pass
    def receive_game_update_message(self, action, rs):      pass
    def receive_round_result_message(self, w, hi, rs):      pass


class HonestPlayer(BasePokerPlayer):
    """몬테카를로(100회)로 승률 추정 후, 승률 ≥ 1/N 이면 콜/체크, 아니면 폴드."""
    def __init__(self):
        super().__init__()
        self.nb_player = 2

    def declare_action(self, valid_actions, hole_card, round_state):
        win_rate = estimate_hole_card_win_rate(
            nb_simulation=NB_SIMULATION,
            nb_player=self.nb_player,
            hole_card=gen_cards(hole_card),
            community_card=gen_cards(round_state['community_card']),
        )
        if win_rate >= 1.0 / self.nb_player:
            call_a = valid_actions[1]      # call (amount 0 이면 check)
            return call_a['action'], call_a['amount']
        fold_a = valid_actions[0]
        return fold_a['action'], fold_a['amount']

    def receive_game_start_message(self, game_info):
        self.nb_player = game_info['player_num']
    def receive_round_start_message(self, rc, hole, seats): pass
    def receive_street_start_message(self, street, rs):     pass
    def receive_game_update_message(self, action, rs):      pass
    def receive_round_result_message(self, w, hi, rs):      pass


_OPP_FACTORY = {'random': RandomPlayer, 'honest': HonestPlayer}


# ─────────────────────────────────────────────────────────
# 평가 루프
# ─────────────────────────────────────────────────────────
def _play_one_hand(ql: QLearning, opp_name: str, agent_is_dealer: bool) -> float:
    """1핸드(=1게임)를 신선한 200스택으로 진행하고 에이전트 칩 손익을 반환."""
    config = setup_config(max_round=1, initial_stack=STARTING_STACK,
                          small_blind_amount=SMALL_BLIND)
    agent = QTablePlayer(ql)
    opp   = _OPP_FACTORY[opp_name]()
    # 좌석 순서를 번갈아 등록 → 에이전트가 두 포지션을 균등 경험
    if agent_is_dealer:
        config.register_player(name='agent', algorithm=agent)
        config.register_player(name='opp',   algorithm=opp)
    else:
        config.register_player(name='opp',   algorithm=opp)
        config.register_player(name='agent', algorithm=agent)

    result = start_poker(config, verbose=0)
    final = next(p['stack'] for p in result['players'] if p['name'] == 'agent')
    return final - STARTING_STACK


def evaluate(ql: QLearning, opp_name: str, n_games: int) -> tuple[float, float, float]:
    payoffs = [_play_one_hand(ql, opp_name, agent_is_dealer=(i % 2 == 0))
               for i in range(n_games)]
    n    = len(payoffs)
    mean = sum(payoffs) / n
    std  = statistics.stdev(payoffs) if n > 1 else 0.0
    win  = sum(1 for p in payoffs if p > 0) / n
    return win, mean * SCALE, (std / math.sqrt(n)) * SCALE


# ─────────────────────────────────────────────────────────
# 출력 (기존 evaluate_*.txt 와 동일한 표 형식)
# ─────────────────────────────────────────────────────────
def _print_header():
    print(f"{'opponent':>10} │ {'seed':>5} │ {'win%':>7} │ "
          f"{'mbb/g':>10} │ {'SE':>8} │ {'95% CI':>22}")
    print("─" * 78)


def _print_row(opp_name, seed, win, mbb, se):
    lo, hi = mbb - 1.96 * se, mbb + 1.96 * se
    seed_s = f"{seed}" if seed is not None else "-"
    print(f"{opp_name:>10} │ {seed_s:>5} │ {win*100:>6.2f}% │ "
          f"{mbb:>+10.1f} │ {se:>8.1f} │ [{lo:>+8.0f}, {hi:>+8.0f}]")


def run(pkl_path: str, opp_name: str, n_games: int, seeds: list[int]):
    ql = QLearning.load(pkl_path)
    print(f"=== PyPokerEngine vs {opp_name} {n_games:,}게임 교차 검증 "
          f"({len(seeds)}회) ===")
    print(f"평가 대상 모델: {pkl_path}")
    print(f"평가 게임 수: {n_games:,} (vs {opp_name} 각각)\n")

    _print_header()
    wins, mbbs, ses = [], [], []
    for seed in seeds:
        random.seed(seed)              # 덱 셔플 + 상대 봇 무작위성 고정
        win, mbb, se = evaluate(ql, opp_name, n_games)
        wins.append(win); mbbs.append(mbb); ses.append(se)
        _print_row(opp_name, seed, win, mbb, se)

    if len(seeds) > 1:
        print("─" * 78)
        win_c = sum(wins) / len(wins)
        mbb_c = sum(mbbs) / len(mbbs)
        # 독립 시드 결합 표준오차: sqrt(Σ se_i²) / k
        se_c  = math.sqrt(sum(s * s for s in ses)) / len(ses)
        _print_row('종합 평균', None, win_c, mbb_c, se_c)


def main():
    ap = argparse.ArgumentParser(description="19번 모델 PyPokerEngine 교차검증 (20번 재현)")
    ap.add_argument('pkl', help='평가할 Q-테이블 pickle 경로 (예: 19번 eval_results.pkl)')
    ap.add_argument('--opp', choices=['random', 'honest'], default='honest')
    ap.add_argument('--games', type=int, default=10000)
    ap.add_argument('--seeds', type=int, nargs='+', default=[124, 125, 126])
    args = ap.parse_args()
    run(args.pkl, args.opp, args.games, args.seeds)


if __name__ == '__main__':
    main()
