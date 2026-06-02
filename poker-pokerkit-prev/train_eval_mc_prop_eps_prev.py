"""
train_eval_mc_prop_eps_prev.py  (鍮꾨? 諛곕텇 MC + 琯-greedy + PrevAction)
?????????????????????????????????????????????????????????????????????
11踰?train_eval_mc_prop_eps.py) ??吏곸젒 ?뺤옣:
  ??state ?ㅼ뿉 PrevAction(?곷????쇱슫????吏곸쟾 ?≪뀡 4醫???異붽?
  ???됰룞 ?좏깮 / ?몃젅?댁뒪 / Q 媛깆떊 紐⑤몢 PrevAction ?ы븿
  ??蹂댁긽 遺꾨같 諛⑹떇(invest 鍮꾨?)쨌琯 ?ㅼ?以꽷룻븯?댄띁?뚮씪誘명꽣??11踰덇낵 ?숈씪

異붽? ?먮즺援ъ“:
  ??prev_action_by_round : dict[Round, PrevAction]
        ?대떦 ?쇱슫?쒖뿉???곷?媛 留덉?留됱쑝濡????≪뀡??遺꾨쪟媛?
        ?쇱슫??泥?吏꾩엯 ?????놁쓬 ???숈뒿??議고쉶 ??NONE.
  ??trace ??ぉ : (Round, State, PrevAction, Action, invest)
"""
import csv
import math
import random
import statistics
from dataclasses import dataclass

from pokerkit import Automation, NoLimitTexasHoldem

from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
    classify_opp_action,
)
from qlearning import QLearning


# ?? 寃뚯엫 ?ㅼ젙 ??????????????????????????????????????????
STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2

# ?? ?숈뒿 ?섏씠?쇳뙆?쇰??????????????????????????????????
TOTAL_EPISODES  = 40_000
ALPHA           = 0.1
GAMMA           = 0.9
UCB_C           = 50.0   # 誘몄궗??
EPS_START       = 1.0
EPS_END         = 0.05
EPS_DECAY_END   = 0.8

# ?? ?됯? ?ㅼ젙 ?????????????????????????????????????????
EVAL_EVERY      = 200
EVAL_GAMES      = 200
CSV_PATH        = "eval_results_mc_prop_eps_prev.csv"

_AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
    Automation.CARD_BURNING,
)


def _make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS,
        True, 0,
        (SMALL_BLIND, BIG_BLIND),
        BIG_BLIND,
        (STARTING_STACK, STARTING_STACK),
        2,
    )


def epsilon_at(episode: int) -> float:
    progress = min(1.0, episode / (TOTAL_EPISODES * EPS_DECAY_END))
    return EPS_START + (EPS_END - EPS_START) * progress


# ?????????????????????????????????????????????????????
# ?곷? ?먯씠?꾪듃
# ?????????????????????????????????????????????????????
def _random_action(pk_state) -> None:
    choices = []
    if pk_state.can_fold():                      choices.append('fold')
    if pk_state.can_check_or_call():             choices.append('check_call')
    if pk_state.can_complete_bet_or_raise_to():  choices.append('raise')

    choice = random.choice(choices)
    if choice == 'fold':
        pk_state.fold()
    elif choice == 'check_call':
        pk_state.check_or_call()
    else:
        lo = pk_state.min_completion_betting_or_raising_to_amount
        hi = pk_state.max_completion_betting_or_raising_to_amount
        pk_state.complete_bet_or_raise_to(random.randint(lo, hi))


_RULE_POLICY = {
    (Round.PREFLOP, False): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_50,    State.DECENT: Action.RAISE_25,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.PREFLOP, True): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.CALL,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.FLOP, False): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_50,    State.DECENT: Action.RAISE_25,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.FLOP, True): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.TURN, False): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_25,    State.DECENT: Action.CHECK,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.TURN, True): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.RIVER, False): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.RAISE_25,    State.DECENT: Action.CHECK,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.RIVER, True): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
}


def _rulebased_action(pk_state, player_idx: int) -> None:
    r          = pk_to_round(pk_state)
    s          = pk_to_state(pk_state, player_idx)
    facing_bet = pk_state.checking_or_calling_amount > 0
    action     = _RULE_POLICY[(r, facing_bet)][s]
    legal      = legal_our_actions(pk_state)

    if action not in legal:
        fallback_order = [Action.CHECK, Action.CALL, Action.FOLD,
                          Action.RAISE_25, Action.RAISE_50,
                          Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN]
        action = next((a for a in fallback_order if a in legal), legal[0])

    execute_action(pk_state, action)


# ?????????????????????????????????????????????????????
# ?ы띁: ?곷?媛 ???≪뀡??泥섎━????PrevAction ?뚯씠釉?媛깆떊
# ?????????????????????????????????????????????????????
def _step_opponent(pk_state, opp_id: int, opponent: str,
                   prev_action_by_round: dict) -> None:
    """
    ?곷? 1?섎? ?먭퀬, 洹?寃곌낵瑜?PrevAction ?쇰줈 遺꾨쪟??
    ?대떦 ?쇱슫????ぉ??湲곕줉?쒕떎.
    """
    r_before        = pk_to_round(pk_state)
    pot_before      = (sum(pot.amount for pot in pk_state.pots)
                       + sum(pk_state.bets))
    cca_before      = pk_state.checking_or_calling_amount
    stack_before    = pk_state.stacks[opp_id]
    max_to_amount   = pk_state.max_completion_betting_or_raising_to_amount

    if opponent == 'random':
        _random_action(pk_state)
    else:
        _rulebased_action(pk_state, opp_id)

    stack_after = pk_state.stacks[opp_id]
    invest      = stack_before - stack_after
    # ?ъ씤 ?먯젙: ?곷?媛 媛???ㅽ깮??(?ъ떎?? 紐⑤몢 諛?덈떎硫?BIG_RAISE 濡?泥섎━
    was_allin   = (stack_after == 0 and invest > cca_before + 1e-9) \
                  or (max_to_amount == stack_before
                      and invest > cca_before + 1e-9
                      and stack_before == max_to_amount)

    pa = classify_opp_action(stack_before, stack_after, cca_before,
                             pot_before, was_allin=was_allin)
    if pa is not None:
        prev_action_by_round[r_before] = pa


# ?????????????????????????????????????????????????????
# ?숈뒿 ?먰뵾?뚮뱶 (鍮꾨? 諛곕텇 MC + PrevAction)
# ?????????????????????????????????????????????????????
def play_train_episode(ql: QLearning, epsilon: float,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list[tuple[Round, State, PrevAction, Action, float]] = []
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id

    prev_action_by_round: dict = {}

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index
            if pid == learner_id:
                r     = pk_to_round(pk_state)
                s     = pk_to_state(pk_state, learner_id)
                pa    = prev_action_by_round.get(r, PrevAction.NONE)
                legal = legal_our_actions(pk_state)
                a     = ql.epsilon_greedy(r, pos, s, pa, legal, epsilon)

                stack_before = pk_state.stacks[learner_id]
                execute_action(pk_state, a)
                stack_after  = pk_state.stacks[learner_id]
                invest = float(stack_before - stack_after)

                trace.append((r, s, pa, a, invest))
            else:
                _step_opponent(pk_state, opp_id, 'random',
                               prev_action_by_round)
        else:
            break

    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    total_invest = sum(inv for (_, _, _, _, inv) in trace)

    if total_invest > 0:
        for (r, s, pa, a, inv) in trace:
            R = (inv / total_invest) * payoff
            ql.update_mc(r, pos, s, pa, a, R)
    else:
        n = len(trace)
        if n > 0:
            R = payoff / n
            for (r, s, pa, a, _inv) in trace:
                ql.update_mc(r, pos, s, pa, a, R)

    return payoff


# ?????????????????????????????????????????????????????
# ?됯? ?먰뵾?뚮뱶 (greedy, Q 誘멸갚??
# ?????????????????????????????????????????????????????
def _play_eval_episode(ql: QLearning, opponent: str,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index
            if pid == learner_id:
                r     = pk_to_round(pk_state)
                s     = pk_to_state(pk_state, learner_id)
                pa    = prev_action_by_round.get(r, PrevAction.NONE)
                legal = legal_our_actions(pk_state)
                a     = ql.best_action(r, pos, s, pa, legal)
                execute_action(pk_state, a)
            else:
                _step_opponent(pk_state, opp_id, opponent,
                               prev_action_by_round)
        else:
            break

    return float(pk_state.stacks[learner_id] - STARTING_STACK)


@dataclass
class EvalResult:
    episode:       int
    win_vs_random: float
    mbb_vs_random: float
    se_vs_random:  float
    win_vs_rule:   float
    mbb_vs_rule:   float
    se_vs_rule:    float


def _mbb_and_se(payoffs: list[float]) -> tuple[float, float]:
    n    = len(payoffs)
    mean = sum(payoffs) / n
    std  = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / BIG_BLIND
    return mean * scale, (std / math.sqrt(n)) * scale


def evaluate(ql: QLearning, n_games: int = EVAL_GAMES):
    payoffs_r:  list[float] = []
    payoffs_rb: list[float] = []

    for i in range(n_games):
        payoffs_r.append(_play_eval_episode(ql, 'random', learner_id=i % 2))
    for i in range(n_games):
        payoffs_rb.append(_play_eval_episode(ql, 'rulebased', learner_id=i % 2))

    win_r  = sum(1 for p in payoffs_r  if p > 0) / n_games
    win_rb = sum(1 for p in payoffs_rb if p > 0) / n_games
    mbb_r,  se_r  = _mbb_and_se(payoffs_r)
    mbb_rb, se_rb = _mbb_and_se(payoffs_rb)
    return win_r, mbb_r, se_r, win_rb, mbb_rb, se_rb


def main():
    ql      = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=UCB_C)
    results: list[EvalResult] = []

    hdr = (f"{'episode':>8} ??{'win%_rand':>9} {'mbb/g_rand':>14} ??
           f" {'win%_rule':>9} {'mbb/g_rule':>14}")
    sep = "?" * len(hdr)
    print(sep)
    print(hdr)
    print(sep)

    wr, mr, sr, wrb, mrb, srb = evaluate(ql)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>8} ??{wr*100:>8.1f}% {mr:>+8.0f}짹{sr:>4.0f} ??{wrb*100:>8.1f}% {mrb:>+8.0f}짹{srb:>4.0f}")

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            eps = epsilon_at(i)
            play_train_episode(ql, eps, learner_id=i % 2)
        ep = next_eval

        wr, mr, sr, wrb, mrb, srb = evaluate(ql)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))
        print(f"{ep:>8} ??{wr*100:>8.1f}% {mr:>+8.0f}짹{sr:>4.0f} ??{wrb*100:>8.1f}% {mrb:>+8.0f}짹{srb:>4.0f}")

    print(sep)

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['episode',
                         'win%_vs_random', 'mbb/g_vs_random', 'se_vs_random',
                         'win%_vs_rulebased', 'mbb/g_vs_rulebased', 'se_vs_rulebased'])
        for r in results:
            writer.writerow([r.episode,
                             f"{r.win_vs_random:.4f}", f"{r.mbb_vs_random:.2f}", f"{r.se_vs_random:.2f}",
                             f"{r.win_vs_rule:.4f}",   f"{r.mbb_vs_rule:.2f}",   f"{r.se_vs_rule:.2f}"])
    print(f"\nCSV ????꾨즺: {CSV_PATH}")

    print("\n=== ?숈뒿 ?꾨즺 Q-?뚯씠釉?(鍮꾨? 諛곕텇 MC + 琯-greedy + PrevAction) ===")
    ql.print_q_table()

    qmd_path = CSV_PATH.replace('.csv', '.qtable.md')
    saved_qmd = ql.save_qtable_markdown(qmd_path)
    print('Q-table markdown Save Complete:', saved_qmd)

    pkl_path = CSV_PATH.rsplit('.', 1)[0] + '.pkl' if CSV_PATH.endswith('.csv') else CSV_PATH + '.pkl'
    saved = ql.save(pkl_path)
    print(f"Q-table pickle ????꾨즺: {saved}")


if __name__ == '__main__':
    random.seed(42)
    main()

