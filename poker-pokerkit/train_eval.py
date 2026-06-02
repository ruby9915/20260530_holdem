"""
train_eval.py
?????????????????????????????????????????????????????????????????????
?숈뒿 吏꾪뻾???곕Ⅸ ?깅뒫 蹂?붾? 痢≪젙?섍린 ?꾪븳 ?ㅽ겕由쏀듃.

?숈뒿 ?먮쫫:
    [TRAIN N episodes] ??[EVAL vs Random 200寃뚯엫] ??[EVAL vs RuleBased 200寃뚯엫]
    ??諛섎났

?됯? ??琯=0 (?쒖닔 greedy) 怨좎젙 ???숈뒿???뺤콉留??ъ슜.
寃곌낵??肄섏넄 ?뚯씠釉?+ CSV ?뚯씪濡?異쒕젰.

?곷? 醫낅쪟:
    RandomAgent   : FOLD/CHECK_CALL/RAISE 洹좊벑 ?쒕뜡
    RuleBasedAgent: ?몃뱶 媛뺣룄(State)???곕씪 怨좎젙 ?뺤콉
        STRONG   ??RAISE_50
        GOOD     ??CALL
        MARGINAL ??CHECK
        WEAK     ??FOLD
        TRASH    ??FOLD
"""
import csv
import math
import random
import statistics
from dataclasses import dataclass, field

from pokerkit import Automation, NoLimitTexasHoldem

from abstraction import (
    Round, State, Action,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
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
EPS_START       = 1.0
EPS_END         = 0.05
EPS_DECAY_END   = 0.8

# ?? ?됯? ?ㅼ젙 ?????????????????????????????????????????
EVAL_EVERY      = 200      # N ?먰뵾?뚮뱶留덈떎 ?됯?
EVAL_GAMES      = 200      # ?됯? 寃뚯엫 ??
CSV_PATH        = "eval_results.csv"

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


# ?????????????????????????????????????????????????????
# 寃뚯엫 ?앹꽦 / ?좏떥
# ?????????????????????????????????????????????????????
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
    """洹좊벑 ?쒕뜡 ?먯씠?꾪듃"""
    choices = []
    if pk_state.can_fold():        choices.append('fold')
    if pk_state.can_check_or_call(): choices.append('check_call')
    if pk_state.can_complete_bet_or_raise_to(): choices.append('raise')

    choice = random.choice(choices)
    if choice == 'fold':
        pk_state.fold()
    elif choice == 'check_call':
        pk_state.check_or_call()
    else:
        lo = pk_state.min_completion_betting_or_raising_to_amount
        hi = pk_state.max_completion_betting_or_raising_to_amount
        pk_state.complete_bet_or_raise_to(random.randint(lo, hi))


# 猷?湲곕컲 ?먯씠?꾪듃 ?뺤콉: (Round, facing_bet) ??State ??Action. ?몃뱶 媛뺣룄 8?④퀎.
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
    """?쇱슫??횞 facing-bet 횞 ?몃뱶 媛뺣룄 湲곕컲 怨좎젙 ?뺤콉 ?먯씠?꾪듃"""
    r          = pk_to_round(pk_state)
    s          = pk_to_state(pk_state, player_idx)
    facing_bet = pk_state.checking_or_calling_amount > 0
    action     = _RULE_POLICY[(r, facing_bet)][s]
    legal      = legal_our_actions(pk_state)

    # ?좏깮???≪뀡??遺덈쾿?대㈃ legal 以?媛??媛源뚯슫 寃껋쑝濡??泥?
    if action not in legal:
        # ?곗꽑?쒖쐞: FOLD > CHECK > CALL > RAISE_50 > ... (蹂댁닔??諛⑺뼢)
        fallback_order = [Action.CHECK, Action.CALL, Action.FOLD,
                          Action.RAISE_25, Action.RAISE_50,
                          Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN]
        action = next((a for a in fallback_order if a in legal), legal[0])

    execute_action(pk_state, action)


# ?????????????????????????????????????????????????????
# ?먰뵾?뚮뱶 ?ㅽ뻾 (?숈뒿??
# ?????????????????????????????????????????????????????
def play_train_episode(ql: QLearning, epsilon: float,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list[tuple[Round, State, Action]] = []
    pos = pk_to_position(learner_id)

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
                legal = legal_our_actions(pk_state)
                a     = ql.epsilon_greedy(r, pos, s, legal, epsilon)
                if trace:
                    pr, ps, pa = trace[-1]
                    ql.update_q(pr, pos, ps, pa, reward=0.0,
                                next_r=r, next_s=s, terminal=False)
                trace.append((r, s, a))
                execute_action(pk_state, a)
            else:
                _random_action(pk_state)
        else:
            break

    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    if trace:
        lr, ls, la = trace[-1]
        ql.update_q(lr, pos, ls, la, reward=payoff, terminal=True)
    return payoff


# ?????????????????????????????????????????????????????
# ?됯? (琯=0, Q ?낅뜲?댄듃 ?놁쓬)
# ?????????????????????????????????????????????????????
def _play_eval_episode(ql: QLearning, opponent: str,
                       learner_id: int = 0) -> float:
    """
    opponent: 'random' | 'rulebased'
    琯=0 greedy 濡쒕쭔 ?뚮젅?? Q-?뚯씠釉??낅뜲?댄듃 ?놁쓬.
    """
    pk_state = _make_game()
    pos = pk_to_position(learner_id)

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
                legal = legal_our_actions(pk_state)
                a     = ql.best_action(r, pos, s, legal)   # 琯=0
                execute_action(pk_state, a)
            else:
                if opponent == 'random':
                    _random_action(pk_state)
                else:
                    opp_id = 1 - learner_id
                    _rulebased_action(pk_state, opp_id)
        else:
            break

    return float(pk_state.stacks[learner_id] - STARTING_STACK)


@dataclass
class EvalResult:
    episode:       int
    win_vs_random: float   # ?밸쪧 (0~1)
    mbb_vs_random: float   # milli big blinds / game
    se_vs_random:  float   # ?쒖??ㅼ감 (mbb ?ㅼ???
    win_vs_rule:   float
    mbb_vs_rule:   float
    se_vs_rule:    float


def _mbb_and_se(payoffs: list[float]) -> tuple[float, float]:
    # mbb/g = (?됯퇏 payoff / BB) * 1000,  SE???숈씪 ?ㅼ???
    n = len(payoffs)
    mean = sum(payoffs) / n
    std  = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / BIG_BLIND
    return mean * scale, (std / math.sqrt(n)) * scale


def evaluate(ql: QLearning, n_games: int = EVAL_GAMES):
    """n_games?????곷?? ??? (win_r, mbb_r, se_r, win_rb, mbb_rb, se_rb) 諛섑솚
    mbb/g ?⑥쐞???ъ빱 ?숆퀎 ?쒖? (milli big blinds per game).
    ?ъ???援먮?: ?덈컲? BB(0), ?덈컲? SB(1)
    """
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


# ?????????????????????????????????????????????????????
# 硫붿씤
# ?????????????????????????????????????????????????????
def main():
    ql      = QLearning(alpha=ALPHA, gamma=GAMMA)
    results: list[EvalResult] = []

    # ?ㅻ뜑 異쒕젰
    hdr = (f"{'episode':>8} ??{'win%_rand':>9} {'mbb/g_rand':>14} ??
           f" {'win%_rule':>9} {'mbb/g_rule':>14}")
    sep = "?" * len(hdr)
    print(sep)
    print(hdr)
    print(sep)

    # ep=0 ?먯꽌 ?ъ쟾 ?됯? (?숈뒿 ??湲곗???
    wr, mr, sr, wrb, mrb, srb = evaluate(ql)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>8} ??{wr*100:>8.1f}% {mr:>+8.0f}짹{sr:>4.0f} ??{wrb*100:>8.1f}% {mrb:>+8.0f}짹{srb:>4.0f}")

    ep = 0
    while ep < TOTAL_EPISODES:
        # ?? ?숈뒿 援ш컙 ??????????????????????????????
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            eps = epsilon_at(i)
            # 留??먰뵾?뚮뱶 ?ъ???援먮? (BB / SB)
            play_train_episode(ql, eps, learner_id=i % 2)
        ep = next_eval

        # ?? ?됯? 援ш컙 ??????????????????????????????
        wr, mr, sr, wrb, mrb, srb = evaluate(ql)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))
        print(f"{ep:>8} ??{wr*100:>8.1f}% {mr:>+8.0f}짹{sr:>4.0f} ??{wrb*100:>8.1f}% {mrb:>+8.0f}짹{srb:>4.0f}")

    print(sep)

    # ?? CSV ??????????????????????????????????????
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

    # ?? 理쒖쥌 Q-?뚯씠釉???????????????????????????????
    print("\n=== ?숈뒿 ?꾨즺 Q-?뚯씠釉?===")
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

