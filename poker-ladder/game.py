# -*- coding: utf-8 -*-
"""에피소드 실행 — 게임 구성·학습/평가 루프 (레거시 의미론 동일).

학습 credit 규약 (전 조건 clean — 누수 폴백 없음):
  PROP      : R(a) = invest(a)/Σinvest × payoff.  Σinvest==0(가상 포함)이면 갱신 생략.
  VIC off   : CHECK invest = 0
  VIC fixed : CHECK invest = K칩 (invest==0인 CHECK에만)
  VIC checktime : CHECK invest = α × (체크 시점 팟)
  FOLD-VIC (vic_fold) : FOLD invest = K칩(fixed) 또는 α_f × (폴드 직전 팟)(foldtime)
                        — 기본 off = 기존 결과와 완전 동일
  FOLD-regret (vic_fold='regret', 35번 2단계) : 후회 계열 — VIC 재가격 아님.
    채널① 실제 폴드: invest = α_f×(폴드 직전 팟), credit 부호 반전 → +s_f×기투자
    채널② 유령 폴드: FOLD 합법(벳 직면)인데 딴 행동을 고른 결정점마다
      v_i = α_f×(그 시점 팟), 갱신 = v_i/(양수투자합+v_i) × (−payoff) 를 FOLD 칸에.
      유령끼리는 분모 미공유(상호 배타 반사실) · 실행 열 credit 은 1비트도 불변.
  PURE      : G = γ^(뒤에서 t번째) × payoff 역전파 (invest 미사용 — VIC inert)
"""
from pokerkit import Automation, NoLimitTexasHoldem

from actions import Action, legal_actions, execute_action
from defs import PrevAction, pk_to_position, pk_to_round, pot_size
from personas import step_opponent

STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2

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


def make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS, True, 0, (SMALL_BLIND, BIG_BLIND), BIG_BLIND,
        (STARTING_STACK, STARTING_STACK), 2)


def play_train_episode(qt, cards, opponent_policy, temperature: float,
                       credit: str, vic: str, vic_amount: float,
                       learner_id: int, pot_apply: str = 'all',
                       uniform_penalty: float = 0.0,
                       actions_version: str = 'A8',
                       dose_sink: list | None = None,
                       vic_fold: str = 'off', vic_fold_amount: float = 0.0) -> float:
    """1 핸드 학습. credit ∈ {prop, pure}, vic ∈ {off, fixed, checktime, terminal}.

    pot_apply (E1 격리 재현): all | invested_only | allcheck_only
    uniform_penalty (E8-③ 재현): 모든 credit 에서 상수 감산
    actions_version: 학습자 행동축 (A8 | A12) — 상대는 항상 A8
    dose_sink (계측 훅, 기본 None=완전 무변화): CHECK 투여 관측 —
      에피소드에 체크가 있으면 (checks[(round,p_i)...], real_total) 을 append.
      순수 관측(난수 미소비·Q 무영향) — 결정론 보존.
    """
    pk = make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    if hasattr(opponent_policy, 'reset'):          # 상태형 상대 (CFR+ 등)
        opponent_policy.reset(opp_id)
    prev: dict = {}
    trace = []                                     # (r, s, pa, a, invest|None)
    ghost_folds = []                               # regret: (r, s, pa, 그 시점 팟)
    pot_peak = 0.0
    real_total = 0.0                               # 실투자 합 (가상 제외)

    while pk.status:
        if vic == 'terminal':
            pot_peak = max(pot_peak, pot_size(pk))
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if pk.actor_index == learner_id:
                r = pk_to_round(pk)
                s = cards.state_of(pk, learner_id)
                pa = prev.get(r, PrevAction.NONE)
                legal = legal_actions(pk, actions_version)
                stack_before = pk.stacks[learner_id]
                pot_before = pot_size(pk)      # 폴드는 실행 후 팟이 회수되므로 사전 캡처
                a = qt.softmax_action(r, pos, s, pa, legal, temperature)
                if (credit == 'prop' and vic_fold == 'regret'
                        and a != Action.FOLD and Action.FOLD in legal):
                    ghost_folds.append((r, s, pa, pot_before))
                execute_action(pk, a)
                invest = float(stack_before - pk.stacks[learner_id])
                real_total += invest
                if credit == 'prop' and a == Action.FOLD and invest == 0                         and vic_fold != 'off':
                    if vic_fold == 'fixed':
                        invest = float(vic_fold_amount)
                    elif vic_fold in ('foldtime', 'regret'):
                        invest = vic_fold_amount * pot_before
                if credit == 'prop' and a == Action.CHECK and invest == 0:
                    if vic == 'fixed':
                        invest = float(vic_amount)
                    elif vic == 'checktime':
                        invest = vic_amount * pot_size(pk)
                    elif vic == 'terminal':
                        invest = None              # 종료 후 α×최종팟으로 채움
                trace.append((r, s, pa, a, invest))
            else:
                step_opponent(pk, opp_id, opponent_policy, prev)
        else:
            break

    if vic == 'terminal':
        vinv = vic_amount * pot_peak
        trace = [(r, s, pa, a, (vinv if inv is None else inv))
                 for (r, s, pa, a, inv) in trace]

    if dose_sink is not None:
        checks = [(r.value, (inv / vic_amount if vic == 'checktime' and inv else 0.0))
                  for (r, s, pa, a, inv) in trace if a == Action.CHECK]
        if checks:
            dose_sink.append((checks, real_total))

    payoff = float(pk.stacks[learner_id] - STARTING_STACK)

    if credit == 'pure':
        g = payoff
        for (r, s, pa, a, _inv) in reversed(trace):
            qt.update_mc(r, pos, s, pa, a, g)
            g = qt.gamma * g
        return payoff

    # ── prop (clean) ── E1 격리: 올체크-핸드 신호 분리 (레거시 의미론 동일)
    if pot_apply == 'invested_only' and real_total == 0:
        return payoff                              # 올체크 핸드 갱신 생략
    if pot_apply == 'allcheck_only':
        if real_total > 0:                         # 실투자 핸드: CHECK credit 0
            trace = [(r, s, pa, a, (0.0 if a == Action.CHECK else inv))
                     for (r, s, pa, a, inv) in trace]
        else:                                      # 올체크: 균등분배(옛 누수 신호)만
            n = len(trace)
            if n:
                g = payoff / n
                for (r, s, pa, a, _inv) in trace:
                    qt.update_mc(r, pos, s, pa, a, g)
            return payoff

    total = sum(inv for (_, _, _, _, inv) in trace)
    if total > 0:
        for (r, s, pa, a, inv) in trace:
            g = (inv / total) * payoff
            if vic_fold == 'regret' and a == Action.FOLD:
                g = -g                             # 채널①: 실제 폴드 부호 반전
            qt.update_mc(r, pos, s, pa, a, g - uniform_penalty)
    if credit == 'prop' and vic_fold == 'regret' and ghost_folds:
        # 유령 분모는 "넣은 돈"(양수 투자)만 합산. 최종 콜로 이긴 판은 invest 에 팟 수령이
        # 섞여 음수(레거시 회계)라 total 을 쓰면 분모 0/음수 — 0나눗셈(실측 크래시)에 더해
        # 이긴 판의 음수 증거("접었으면 이 팟을 놓쳤다")가 부호 반전으로 오염된다.
        pos_total = sum(inv for (_, _, _, _, inv) in trace if inv > 0)
        for (r, s, pa, potb) in ghost_folds:       # 채널②: 유령 폴드 (분모 독립)
            v = vic_fold_amount * potb
            if v > 0:
                qt.update_mc(r, pos, s, pa, Action.FOLD,
                             (v / (pos_total + v)) * (-payoff))
    return payoff


def play_eval_episode(qt, cards, opponent_kind, learner_id: int,
                      actions_version: str = 'A8') -> float:
    """greedy 1 핸드 (Q 갱신 없음). opponent_kind: 'random' | 'eval_tag' | 페르소나 | 상태형."""
    pk = make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    if hasattr(opponent_kind, 'reset'):
        opponent_kind.reset(opp_id)
    prev: dict = {}

    while pk.status:
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if pk.actor_index == learner_id:
                r = pk_to_round(pk)
                s = cards.state_of(pk, learner_id)
                pa = prev.get(r, PrevAction.NONE)
                a = qt.best_action(r, pos, s, pa,
                                   legal_actions(pk, actions_version))
                execute_action(pk, a)
            else:
                step_opponent(pk, opp_id, opponent_kind, prev)
        else:
            break
    return float(pk.stacks[learner_id] - STARTING_STACK)
