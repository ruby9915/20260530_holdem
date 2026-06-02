"""
FOLD 동률(greedy max==0.000, FOLD가 argmax) 컨텍스트가 실제 게임에서
어떤 legal set에 도달하는지 실측한다.

핵심 질문: 17.5 (3-1) 표의 "FOLD=0, CHECK=0" 행이 실재하는가?
 - pokerkit verify_folding: bets[player] >= max(bets)(=체크 가능)면 FOLD 비합법.
 - 따라서 FOLD가 legal한 모든 스팟은 베팅 직면 → CHECK 아닌 CALL과 동반.
 - 즉 모든 FOLD 동률은 "FOLD=CALL=0"이며, "FOLD=CHECK=0"은 발생 불가능.

방법: 19번 학습 때와 동일한 train 루프(상대=random, seed)를 재생하되,
learner 결정 스팟마다 (round,pos,state,prevaction)와 legal set을 기록하고
그 컨텍스트가 Q테이블에서 greedy 0.000 동률(FOLD argmax)인지 매칭한다.
"""
import os, sys, pickle, random
from collections import Counter

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "poker-pokerkit-prev")))

import train_eval_mc_prop_softmax_2000k as b
from abstraction import (legal_our_actions, Action,
                         pk_to_round, pk_to_state)

# play_train_episode와 동일한 포지션 매핑
pk_to_position = b.pk_to_position

EPS = 1e-12
d = pickle.load(open(os.path.join(os.path.dirname(__file__), "..",
                     "19_mc_prop_softmax_prev_2000k", "eval_results.pkl"), "rb"))
q = d["q"]


def is_fold_tie(r, pos, s, pa):
    """그 컨텍스트의 greedy가 0.000 동률이고 FOLD가 argmax(=raw가 FOLD)인가."""
    row = q[r][pos][s][pa]
    mx = max(row)
    if abs(mx) >= EPS:
        return False
    # 0.000 동률 → python max는 iteration 첫 번째(FOLD, index 0)를 고름
    n_tie = sum(1 for v in row if abs(v - mx) < EPS)
    return n_tie > 1  # 동률(여러 액션이 0)


# ── 카운터 ────────────────────────────────────────────────
spots_total = 0
tie_spots = 0
tie_with_fold_legal = 0
tie_fold_and_check = 0      # FOLD와 CHECK 둘 다 legal (표 첫 행 케이스)
tie_fold_and_call = 0       # FOLD와 CALL 둘 다 legal (표 둘째 행)
tie_check_only = 0          # FOLD 불법, CHECK 가능 (동률이지만 FOLD 선택 불가)
legalset_kinds = Counter()

random.seed(42)
N_GAMES = 30000

for g in range(N_GAMES):
    learner_id = g % 2  # 학습 코드처럼 번갈아
    pk_state = b._make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round = {}

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index
            if pid == learner_id:
                r = pk_to_round(pk_state)
                s = pk_to_state(pk_state, learner_id)
                pa = prev_action_by_round.get(r, b.PrevAction.NONE)
                legal = legal_our_actions(pk_state)
                spots_total += 1

                ri = int(getattr(r, 'value', r))
                si = int(getattr(s, 'value', s))
                posi = int(getattr(pos, 'value', pos))
                pai = int(getattr(pa, 'value', pa))

                has_fold = Action.FOLD in legal
                has_check = Action.CHECK in legal
                has_call = Action.CALL in legal

                if is_fold_tie(ri, posi, si, pai):
                    tie_spots += 1
                    kind = (("FOLD," if has_fold else "")
                            + ("CHECK," if has_check else "")
                            + ("CALL," if has_call else "")).rstrip(",")
                    legalset_kinds[kind] += 1
                    if has_fold:
                        tie_with_fold_legal += 1
                        if has_check:
                            tie_fold_and_check += 1
                        if has_call:
                            tie_fold_and_call += 1
                    elif has_check:
                        tie_check_only += 1

                # 학습과 동일: 낮은 온도 greedy 비슷하게 그냥 best/legal 진행
                a = legal[0]
                from abstraction import execute_action
                execute_action(pk_state, a)
            else:
                b._step_opponent(pk_state, opp_id, 'random',
                                 prev_action_by_round)
        else:
            break

print("=" * 66)
print(f"게임 {N_GAMES} | learner 결정 스팟 {spots_total}")
print(f"FOLD 동률 컨텍스트 도달 스팟: {tie_spots}")
print(f"  ├ FOLD가 legal(=베팅 직면): {tie_with_fold_legal}")
print(f"  │   ├ FOLD & CHECK 동시 legal (표 1행 'FOLD=CHECK=0'): {tie_fold_and_check}")
print(f"  │   └ FOLD & CALL  동시 legal (표 2행 'FOLD=CALL=0'):  {tie_fold_and_call}")
print(f"  └ FOLD 불법·CHECK 가능(동률이나 FOLD 선택 불가): {tie_check_only}")
print("-" * 66)
print("legal set 종류별 분포 (FOLD 동률 스팟):")
for k, v in legalset_kinds.most_common():
    print(f"  {k:24s} {v}")
print("=" * 66)
