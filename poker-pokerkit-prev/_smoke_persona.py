"""
_smoke_persona.py  (26번 스모크 — 성향 동작/공격성 검증)
─────────────────────────────────────────────────────────────────────
각 성향(persona)으로 짧은 학습을 돌려서
  (1) 파이프라인이 에러 없이 도는지
  (2) 상대가 실제로 의도한 만큼 공격적/소극적인지
를 상대의 PrevAction(우리가 관측한 상대 행동) 분포로 검증한다.

기대: man > lag > tag 순으로 RAISE 비율↑, sta 는 RAISE 0,
      nit 은 대부분 FOLD/NONE(거의 안 들어옴), 우리가 FACING 도달↑.
"""
import random
import collections

import train_eval_mc_prop_softmax_2000k as base
from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
)
from qlearning import QLearning
import rulebased_personas as personas

N_EPISODES = 3000
TEMP       = 5.0   # 학습 초반 비슷한 탐색 온도


def run_persona(persona: str):
    policy = personas.PERSONA_POLICIES[persona]
    ql = QLearning(alpha=base.ALPHA, gamma=base.GAMMA, ucb_c=50.0)

    opp_pa_counter   = collections.Counter()   # 상대가 만든 PrevAction 분포
    our_facing_count = 0                        # 우리가 베팅 직면 도달 횟수
    our_decision     = 0

    for ep in range(N_EPISODES):
        learner_id = ep % 2
        pk_state = base._make_game()
        opp_id   = 1 - learner_id
        pos      = pk_to_position(learner_id)
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
                    if pk_state.checking_or_calling_amount > 0:
                        our_facing_count += 1
                    our_decision += 1
                    a = ql.softmax_action(r, pos, s, pa, legal, TEMP)
                    execute_action(pk_state, a)
                else:
                    r_before = pk_to_round(pk_state)
                    personas.step_persona_opponent(
                        pk_state, opp_id, policy, prev_action_by_round)
                    pa_now = prev_action_by_round.get(r_before)
                    if pa_now is not None:
                        opp_pa_counter[pa_now.name] += 1
            else:
                break

    total_pa = sum(opp_pa_counter.values()) or 1
    raise_share = (opp_pa_counter.get('SMALL_RAISE', 0)
                   + opp_pa_counter.get('BIG_RAISE', 0)) / total_pa
    facing_rate = our_facing_count / max(1, our_decision)
    dist = {k: f"{v/total_pa*100:4.1f}%"
            for k, v in sorted(opp_pa_counter.items(),
                               key=lambda x: -x[1])}
    print(f"  {persona.upper():4} | 상대RAISE비중={raise_share*100:5.1f}% "
          f"| 우리FACING도달율={facing_rate*100:5.1f}% | {dist}", flush=True)


if __name__ == '__main__':
    print("-" * 100)
    print(f"  26번 스모크: 성향별 {N_EPISODES} 에피소드, TEMP={TEMP}")
    print("-" * 100)
    for p in personas.PERSONA_NAMES:
        random.seed(42)
        run_persona(p)
    print("-" * 100)
