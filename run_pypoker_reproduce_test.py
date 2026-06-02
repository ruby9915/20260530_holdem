import math
import statistics
import sys
import random
from pathlib import Path

# poker-pokerkit-prev 폴더를 sys.path에 추가
sys.path.insert(0, r"C:\code\minimizing\poker-pokerkit-prev")
from abstraction import Round, State, Position, Action, PrevAction
from qlearning import QLearning

# PyPokerEngine 임포트
from pypokerengine.players import BasePokerPlayer
from pypokerengine.api.game import setup_config, start_poker
from pypokerengine.utils.card_utils import estimate_hole_card_win_rate, gen_cards
from treys import Card as TreysCard, Evaluator

# 첸 스코어를 위한 DummyCard
class DummyCard:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

def pypoker_card_to_treys(c: str) -> str:
    suit = c[0].lower()
    rank = c[1]
    return f"{rank}{suit}"

def get_chen_state(hole_card: list[str]) -> State:
    r1, s1 = hole_card[0][1], hole_card[0][0].lower()
    r2, s2 = hole_card[1][1], hole_card[1][0].lower()
    
    from abstraction import _chen_score, _chen_to_state
    cards = [DummyCard(r1, s1), DummyCard(r2, s2)]
    score = _chen_score(cards)
    return _chen_to_state(score)

_evaluator = Evaluator()
def get_postflop_state(hole_card: list[str], community_card: list[str]) -> State:
    h = [TreysCard.new(pypoker_card_to_treys(c)) for c in hole_card]
    p = [TreysCard.new(pypoker_card_to_treys(c)) for c in community_card]
    score = _evaluator.evaluate(p, h)
    percentile = score / 7462.0
    if percentile < 0.125: return State.PREMIUM
    if percentile < 0.250: return State.STRONG
    if percentile < 0.375: return State.GOOD
    if percentile < 0.500: return State.DECENT
    if percentile < 0.625: return State.MEDIOCRE
    if percentile < 0.750: return State.WEAK
    if percentile < 0.875: return State.POOR
    return State.TRASH

class QLearningPlayer(BasePokerPlayer):
    def __init__(self, ql: QLearning):
        self.ql = ql
        self.uuid = None

    def declare_action(self, valid_actions, hole_card, round_state):
        street = round_state['street']
        if street == 'preflop':
            r = Round.PREFLOP
        elif street == 'flop':
            r = Round.FLOP
        elif street == 'turn':
            r = Round.TURN
        else:
            r = Round.RIVER

        seats = round_state['seats']
        dealer_idx = round_state['dealer_btn']
        is_dealer = (seats[dealer_idx]['uuid'] == self.uuid)
        
        # 포지션 스왑 버그 보정
        pos = Position.BB if is_dealer else Position.SB

        if len(round_state['community_card']) == 0:
            s = get_chen_state(hole_card)
        else:
            s = get_postflop_state(hole_card, round_state['community_card'])

        opp_seat = next(seat for seat in seats if seat['uuid'] != self.uuid)
        opp_uuid = opp_seat['uuid']
        
        histories = round_state['action_histories'].get(street, [])
        opp_action = None
        for act in reversed(histories):
            if act['uuid'] == opp_uuid:
                opp_action = act
                break

        if opp_action is None:
            pa = PrevAction.NONE
        else:
            act_name = opp_action['action']
            if act_name in ('CHECK', 'CALL'):
                pa = PrevAction.CHECK_CALL
            elif act_name == 'RAISE':
                extra = opp_action.get('add_amount', opp_action.get('amount', 0))
                pot_before = round_state['pot']['main']['amount'] - extra
                current_opp_stack = opp_seat['stack']
                is_allin = (current_opp_stack == 0)
                
                if is_allin or pot_before <= 0:
                    pa = PrevAction.BIG_RAISE
                else:
                    pct = extra / pot_before
                    pa = PrevAction.SMALL_RAISE if pct <= 0.5 else PrevAction.BIG_RAISE
            else:
                pa = PrevAction.NONE

        legal = []
        action_map = {}
        for va in valid_actions:
            name = va['action']
            if name == 'fold':
                legal.append(Action.FOLD)
                action_map[Action.FOLD] = va
            elif name == 'call':
                if va['amount'] == 0:
                    legal.append(Action.CHECK)
                    action_map[Action.CHECK] = va
                else:
                    legal.append(Action.CALL)
                    action_map[Action.CALL] = va
            elif name == 'raise':
                legal.extend([Action.RAISE_25, Action.RAISE_50, Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN])
                for act in (Action.RAISE_25, Action.RAISE_50, Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN):
                    action_map[act] = va

        # 6. 베스트 액션 선택 (FOLD 자폭 회피 보정)
        max_q = max(self.ql.get_q(r, pos, s, pa, a) for a in legal)
        best_candidates = [a for a in legal if self.ql.get_q(r, pos, s, pa, a) == max_q]
        if len(best_candidates) > 1:
            preference = [Action.CHECK, Action.CALL, 
                          Action.RAISE_25, Action.RAISE_50, Action.RAISE_75, Action.RAISE_100,
                          Action.RAISE_ALLIN, Action.FOLD]
            best_a = next(a for a in preference if a in best_candidates)
        else:
            best_a = best_candidates[0]
        
        va = action_map[best_a]
        if best_a == Action.FOLD:
            return 'fold', 0
        elif best_a in (Action.CHECK, Action.CALL):
            return 'call', va['amount']
        elif best_a == Action.RAISE_ALLIN:
            return 'raise', va['amount']['max']
        else:
            from abstraction import _RAISE_PCT
            pct = _RAISE_PCT[best_a]
            total_pot = round_state['pot']['main']['amount']
            raise_size = max(1, int(total_pot * pct))
            call_amount = next(v['amount'] for v in valid_actions if v['action'] == 'call')
            target = call_amount + raise_size
            min_r = va['amount']['min']
            max_r = va['amount']['max']
            target = max(min_r, min(max_r, target))
            return 'raise', target

    def receive_game_start_message(self, game_info):
        seats = game_info['seats']
        self.uuid = next(s['uuid'] for s in seats if s['name'] == 'agent')

    def receive_round_start_message(self, round_count, hole_card, seats): pass
    def receive_street_start_message(self, street, round_state): pass
    def receive_game_update_message(self, action, round_state): pass
    def receive_round_result_message(self, winners, hand_info, round_state): pass

class PyPokerHonestPlayer(BasePokerPlayer):
    def declare_action(self, valid_actions, hole_card, round_state):
        nb_player = len(round_state['seats'])
        win_rate = estimate_hole_card_win_rate(
            nb_simulation=30, 
            nb_player=nb_player, 
            hole_card=gen_cards(hole_card), 
            community_card=gen_cards(round_state['community_card'])
        )
        
        if win_rate > 1.0 / nb_player:
            call_act = next(va for va in valid_actions if va['action'] == 'call')
            return 'call', call_act['amount']
        else:
            return 'fold', 0

    def receive_game_start_message(self, game_info): pass
    def receive_round_start_message(self, round_count, hole_card, seats): pass
    def receive_street_start_message(self, street, round_state): pass
    def receive_game_update_message(self, action, round_state): pass
    def receive_round_result_message(self, winners, hand_info, round_state): pass

def run_simulation(ql, n_games=1_000, seed=124):
    random.seed(seed)
    payoffs = []
    
    for i in range(n_games):
        config = setup_config(max_round=1, initial_stack=200, small_blind_amount=1)
        config.register_player(name="agent", algorithm=QLearningPlayer(ql))
        config.register_player(name="opponent", algorithm=PyPokerHonestPlayer())
        
        game_result = start_poker(config, verbose=0)
        agent_stack = next(s['stack'] for s in game_result['players'] if s['name'] == 'agent')
        payoffs.append(agent_stack - 200)

    n = len(payoffs)
    mean = sum(payoffs) / n
    std = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / 2.0  # mbb/g 변환
    win = sum(1 for p in payoffs if p > 0) / n
    
    mbb = mean * scale
    se = (std / math.sqrt(n)) * scale
    return win, mbb, se

def main():
    pkl_path = r"C:\code\minimizing\results\19_mc_prop_softmax_prev_2000k\eval_results.pkl"
    ql = QLearning.load(pkl_path)
    
    print("=== 재현 가능성 (Reproducibility) 정밀 검증 스크립트 ===")
    print("조건: seed=124, n_games=1,000, 2회 연속 수행하여 일치 여부 비교")
    
    print("\n[Run 1] 시뮬레이션 가동...")
    w1, m1, se1 = run_simulation(ql, 1_000, seed=124)
    print(f"Run 1 결과 -> win%: {w1*100:.2f}% | mbb/g: {m1:+.2f} | SE: {se1:.2f}")
    
    print("\n[Run 2] 시뮬레이션 가동 (동일 조건)...")
    w2, m2, se2 = run_simulation(ql, 1_000, seed=124)
    print(f"Run 2 결과 -> win%: {w2*100:.2f}% | mbb/g: {m2:+.2f} | SE: {se2:.2f}")
    
    print("\n" + "="*50)
    if w1 == w2 and m1 == m2 and se1 == se2:
        print("★ 검증 성공: 두 실행 결과가 소수점 아래 끝자리까지 100% 일치합니다!")
        print("=> 난수 시드(Seed=124) 제어를 통해 완벽한 결정론적 재현성(Deterministic Reproducibility)이 입증되었습니다.")
    else:
        print("⚠️ 검증 실패: 결과가 일치하지 않습니다. 난수 설정에 누수가 있습니다.")
    print("="*50)

if __name__ == '__main__':
    main()
