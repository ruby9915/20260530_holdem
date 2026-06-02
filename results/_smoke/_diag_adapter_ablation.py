"""
진단: pokerkit 25.7% vs PyPokerEngine 86.9% 격차의 원인 분리.
원본 어댑터(run_pypoker_eval_honest_100k.py)를 그대로 가져오되,
(A) 포지션 스왑 on/off, (B) FOLD 회피 on/off 를 토글해 기여도를 분해한다.
상대는 동일하게 PyPokerHonestPlayer(nb_simulation=30).
"""
import math, statistics, sys, random
from pathlib import Path
sys.path.insert(0, r"C:\code\minimizing\poker-pokerkit-prev")
from abstraction import Round, State, Position, Action, PrevAction, _RAISE_PCT
from qlearning import QLearning
from pypokerengine.players import BasePokerPlayer
from pypokerengine.api.game import setup_config, start_poker
from pypokerengine.utils.card_utils import estimate_hole_card_win_rate, gen_cards
from treys import Card as TreysCard, Evaluator


class DummyCard:
    def __init__(self, rank, suit): self.rank, self.suit = rank, suit

def c2t(c): return f"{c[1]}{c[0].lower()}"

def chen_state(hole):
    from abstraction import _chen_score, _chen_to_state
    cards = [DummyCard(hole[0][1], hole[0][0].lower()),
             DummyCard(hole[1][1], hole[1][0].lower())]
    return _chen_to_state(_chen_score(cards))

_ev = Evaluator()
def postflop_state(hole, comm):
    h = [TreysCard.new(c2t(c)) for c in hole]
    p = [TreysCard.new(c2t(c)) for c in comm]
    pct = _ev.evaluate(p, h) / 7462.0
    for thr, st in [(0.125,State.PREMIUM),(0.250,State.STRONG),(0.375,State.GOOD),
                    (0.500,State.DECENT),(0.625,State.MEDIOCRE),(0.750,State.WEAK),
                    (0.875,State.POOR)]:
        if pct < thr: return st
    return State.TRASH


class QLPlayer(BasePokerPlayer):
    def __init__(self, ql, swap=True, fold_avoid=True):
        self.ql, self.swap, self.fold_avoid, self.uuid = ql, swap, fold_avoid, None

    def declare_action(self, valid_actions, hole_card, round_state):
        street = round_state['street']
        r = {'preflop':Round.PREFLOP,'flop':Round.FLOP,'turn':Round.TURN,'river':Round.RIVER}[street]
        seats = round_state['seats']
        is_dealer = (seats[round_state['dealer_btn']]['uuid'] == self.uuid)
        # 포지션 스왑 토글
        if self.swap:
            pos = Position.BB if is_dealer else Position.SB
        else:
            pos = Position.SB if is_dealer else Position.BB
        if len(round_state['community_card']) == 0:
            s = chen_state(hole_card)
        else:
            s = postflop_state(hole_card, round_state['community_card'])
        opp_seat = next(x for x in seats if x['uuid'] != self.uuid)
        hist = round_state['action_histories'].get(street, [])
        opp_action = next((a for a in reversed(hist) if a['uuid']==opp_seat['uuid']), None)
        if opp_action is None:
            pa = PrevAction.NONE
        elif opp_action['action'] in ('CHECK','CALL'):
            pa = PrevAction.CHECK_CALL
        elif opp_action['action'] == 'RAISE':
            extra = opp_action.get('add_amount', opp_action.get('amount',0))
            pot_before = round_state['pot']['main']['amount'] - extra
            if opp_seat['stack']==0 or pot_before<=0: pa = PrevAction.BIG_RAISE
            else: pa = PrevAction.SMALL_RAISE if extra/pot_before<=0.5 else PrevAction.BIG_RAISE
        else:
            pa = PrevAction.NONE
        legal, amap = [], {}
        for va in valid_actions:
            n = va['action']
            if n=='fold': legal.append(Action.FOLD); amap[Action.FOLD]=va
            elif n=='call':
                a = Action.CHECK if va['amount']==0 else Action.CALL
                legal.append(a); amap[a]=va
            elif n=='raise':
                for a in (Action.RAISE_25,Action.RAISE_50,Action.RAISE_75,Action.RAISE_100,Action.RAISE_ALLIN):
                    legal.append(a); amap[a]=va
        max_q = max(self.ql.get_q(r,pos,s,pa,a) for a in legal)
        cands = [a for a in legal if self.ql.get_q(r,pos,s,pa,a)==max_q]
        if self.fold_avoid and len(cands)>1:
            pref = [Action.CHECK,Action.CALL,Action.RAISE_25,Action.RAISE_50,
                    Action.RAISE_75,Action.RAISE_100,Action.RAISE_ALLIN,Action.FOLD]
            best = next(a for a in pref if a in cands)
        else:
            # 원시 max: Enum 순서(FOLD=0 우선) — pokerkit greedy 와 동일
            best = min(cands, key=lambda a: a.value)
        va = amap[best]
        if best==Action.FOLD: return 'fold',0
        if best in (Action.CHECK,Action.CALL): return 'call',va['amount']
        if best==Action.RAISE_ALLIN: return 'raise',va['amount']['max']
        pct=_RAISE_PCT[best]; tp=round_state['pot']['main']['amount']
        rs=max(1,int(tp*pct)); ca=next(v['amount'] for v in valid_actions if v['action']=='call')
        t=ca+rs; return 'raise',max(va['amount']['min'],min(va['amount']['max'],t))

    def receive_game_start_message(self, gi):
        self.uuid = next(s['uuid'] for s in gi['seats'] if s['name']=='agent')
    def receive_round_start_message(self,*a): pass
    def receive_street_start_message(self,*a): pass
    def receive_game_update_message(self,*a): pass
    def receive_round_result_message(self,*a): pass


class Honest(BasePokerPlayer):
    def declare_action(self, valid_actions, hole_card, round_state):
        nbp = len(round_state['seats'])
        wr = estimate_hole_card_win_rate(nb_simulation=30, nb_player=nbp,
            hole_card=gen_cards(hole_card), community_card=gen_cards(round_state['community_card']))
        if wr > 1.0/nbp:
            ca = next(va for va in valid_actions if va['action']=='call')
            return 'call', ca['amount']
        return 'fold',0
    def receive_game_start_message(self,*a): pass
    def receive_round_start_message(self,*a): pass
    def receive_street_start_message(self,*a): pass
    def receive_game_update_message(self,*a): pass
    def receive_round_result_message(self,*a): pass


def run(ql, swap, fold_avoid, n=2000, seed=124):
    random.seed(seed)
    payoffs=[]
    for _ in range(n):
        cfg=setup_config(max_round=1, initial_stack=200, small_blind_amount=1)
        cfg.register_player(name="agent", algorithm=QLPlayer(ql,swap,fold_avoid))
        cfg.register_player(name="opponent", algorithm=Honest())
        res=start_poker(cfg, verbose=0)
        payoffs.append(next(s['stack'] for s in res['players'] if s['name']=='agent')-200)
    n=len(payoffs); mean=sum(payoffs)/n
    win=sum(1 for p in payoffs if p>0)/n
    return win, mean*500


def main():
    ql=QLearning.load(r"C:\code\minimizing\results\19_mc_prop_softmax_prev_2000k\eval_results.pkl")
    print(f"{'mode':<28}{'win%':>9}{'mbb/g':>10}")
    print("-"*47)
    for label, swap, fa in [
        ("full(swap+foldavoid)", True, True),
        ("swap only(no foldavoid)", True, False),
        ("foldavoid only(no swap)", False, True),
        ("raw(no swap,no foldavoid)", False, False),
    ]:
        w,m=run(ql, swap, fa)
        print(f"{label:<28}{w*100:>8.2f}%{m:>+10.1f}")

if __name__=='__main__':
    main()
