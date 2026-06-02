"""
rulebased_personas.py  (26번 실험 — 룰베이스 상대 성향 다양화)
─────────────────────────────────────────────────────────────────────
19번 baseline 의 단일 결정 정책(_RULE_POLICY, 사실상 TAG)을
포커 표준 5종 성향으로 확장한다. base 모듈(train_eval_mc_prop_softmax_2000k)
은 일절 수정하지 않고, 여기서 정책 테이블과 상대 step 함수를 독립 제공한다.

설계 동기(실험일지 21절 결론 = 병목은 전이분포):
  - 25번 온도 스윕으로 "단일 스텝 탐색(softmax/온도)으로는 베팅 직면
    FOLD=CALL=0 미탐색 셀을 채울 수 없다"가 입증됨.
  - 우리 에이전트가 그 셀에 '도달'하려면 상대가 실제로 베팅/레이즈를
    던져야 한다 → 상대의 전이분포(성향)를 바꾸는 것이 직접적 해법.

성향 5종 (State 강→약: PREMIUM>STRONG>GOOD>DECENT>MEDIOCRE>WEAK>POOR>TRASH):
  TAG  Tight-Aggressive : 19 baseline 과 동일(정석 대조군)
  LAG  Loose-Aggressive : 넓게 레이즈 → 베팅직면 셀 도달 극대화(1순위 직격)
  MAN  Maniac           : 거의 모두 레이즈/재레이즈 → BIG_RAISE 컨텍스트 공급
  STA  Calling Station  : 레이즈 없음, 콜다운 → 턴·리버 깊은 라운드 도달 보강
  NIT  Nit / Rock       : PREMIUM/STRONG 만 플레이 → FOLD=정답 케이스 검증

각 성향은 facing_bet(bool) → {State: Action} 두 줄(row)로 정의하고,
모든 라운드에 동일 적용한다(상대 성향 격리 측정이 목적이므로 단순화).
"""
from abstraction import (
    State, Action,
    pk_to_round, pk_to_state,
    legal_our_actions, execute_action,
    classify_opp_action,
)

_S = State
_A = Action

# ─────────────────────────────────────────────────────────────────────
# 성향별 정책: persona → {facing_bet(bool): {State: Action}}
# ─────────────────────────────────────────────────────────────────────
PERSONA_POLICIES: dict[str, dict[bool, dict]] = {
    # ── TAG : 19 baseline(_RULE_POLICY)의 평균적 성향 ──────────────
    'tag': {
        False: {
            _S.PREMIUM: _A.RAISE_100, _S.STRONG: _A.RAISE_75,
            _S.GOOD:    _A.RAISE_50,  _S.DECENT: _A.RAISE_25,
            _S.MEDIOCRE:_A.CHECK,     _S.WEAK:   _A.CHECK,
            _S.POOR:    _A.CHECK,     _S.TRASH:  _A.CHECK,
        },
        True: {
            _S.PREMIUM: _A.RAISE_75,  _S.STRONG: _A.RAISE_50,
            _S.GOOD:    _A.CALL,      _S.DECENT: _A.CALL,
            _S.MEDIOCRE:_A.FOLD,      _S.WEAK:   _A.FOLD,
            _S.POOR:    _A.FOLD,      _S.TRASH:  _A.FOLD,
        },
    },
    # ── LAG : 넓게 레이즈, 직면 시에도 넓게 콜 ─────────────────────
    'lag': {
        False: {
            _S.PREMIUM: _A.RAISE_100, _S.STRONG: _A.RAISE_75,
            _S.GOOD:    _A.RAISE_75,  _S.DECENT: _A.RAISE_50,
            _S.MEDIOCRE:_A.RAISE_25,  _S.WEAK:   _A.RAISE_25,
            _S.POOR:    _A.CHECK,     _S.TRASH:  _A.CHECK,
        },
        True: {
            _S.PREMIUM: _A.RAISE_75,  _S.STRONG: _A.RAISE_50,
            _S.GOOD:    _A.CALL,      _S.DECENT: _A.CALL,
            _S.MEDIOCRE:_A.CALL,      _S.WEAK:   _A.FOLD,
            _S.POOR:    _A.FOLD,      _S.TRASH:  _A.FOLD,
        },
    },
    # ── MAN : 거의 전부 레이즈/재레이즈 ───────────────────────────
    'man': {
        False: {
            _S.PREMIUM: _A.RAISE_100, _S.STRONG: _A.RAISE_100,
            _S.GOOD:    _A.RAISE_75,  _S.DECENT: _A.RAISE_75,
            _S.MEDIOCRE:_A.RAISE_50,  _S.WEAK:   _A.RAISE_50,
            _S.POOR:    _A.RAISE_25,  _S.TRASH:  _A.RAISE_25,
        },
        True: {
            _S.PREMIUM: _A.RAISE_100, _S.STRONG: _A.RAISE_75,
            _S.GOOD:    _A.RAISE_50,  _S.DECENT: _A.CALL,
            _S.MEDIOCRE:_A.CALL,      _S.WEAK:   _A.CALL,
            _S.POOR:    _A.CALL,      _S.TRASH:  _A.FOLD,
        },
    },
    # ── STA : 레이즈 없음, 넓게 콜다운 ────────────────────────────
    'sta': {
        False: {
            _S.PREMIUM: _A.CHECK,     _S.STRONG: _A.CHECK,
            _S.GOOD:    _A.CHECK,     _S.DECENT: _A.CHECK,
            _S.MEDIOCRE:_A.CHECK,     _S.WEAK:   _A.CHECK,
            _S.POOR:    _A.CHECK,     _S.TRASH:  _A.CHECK,
        },
        True: {
            _S.PREMIUM: _A.CALL,      _S.STRONG: _A.CALL,
            _S.GOOD:    _A.CALL,      _S.DECENT: _A.CALL,
            _S.MEDIOCRE:_A.CALL,      _S.WEAK:   _A.CALL,
            _S.POOR:    _A.FOLD,      _S.TRASH:  _A.FOLD,
        },
    },
    # ── NIT : PREMIUM/STRONG 만 플레이, 나머지 폴드/체크 ──────────
    'nit': {
        False: {
            _S.PREMIUM: _A.RAISE_75,  _S.STRONG: _A.RAISE_75,
            _S.GOOD:    _A.CHECK,     _S.DECENT: _A.CHECK,
            _S.MEDIOCRE:_A.CHECK,     _S.WEAK:   _A.CHECK,
            _S.POOR:    _A.CHECK,     _S.TRASH:  _A.CHECK,
        },
        True: {
            _S.PREMIUM: _A.RAISE_75,  _S.STRONG: _A.CALL,
            _S.GOOD:    _A.FOLD,      _S.DECENT: _A.FOLD,
            _S.MEDIOCRE:_A.FOLD,      _S.WEAK:   _A.FOLD,
            _S.POOR:    _A.FOLD,      _S.TRASH:  _A.FOLD,
        },
    },
}

PERSONA_NAMES = tuple(PERSONA_POLICIES.keys())

_FALLBACK_ORDER = [
    Action.CHECK, Action.CALL, Action.FOLD,
    Action.RAISE_25, Action.RAISE_50,
    Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN,
]


def persona_action(pk_state, player_idx: int, policy: dict) -> None:
    """주어진 성향 정책(policy = {facing_bet: {State: Action}})으로 1 액션 실행."""
    s          = pk_to_state(pk_state, player_idx)
    facing_bet = pk_state.checking_or_calling_amount > 0
    action     = policy[facing_bet][s]
    legal      = legal_our_actions(pk_state)

    if action not in legal:
        action = next((a for a in _FALLBACK_ORDER if a in legal), legal[0])

    execute_action(pk_state, action)


def step_persona_opponent(pk_state, opp_id: int, policy: dict,
                          prev_action_by_round: dict) -> None:
    """base._step_opponent 의 PrevAction 갱신 로직을 그대로 따르되 성향 정책 사용."""
    r_before      = pk_to_round(pk_state)
    pot_before    = (sum(pot.amount for pot in pk_state.pots)
                     + sum(pk_state.bets))
    cca_before    = pk_state.checking_or_calling_amount
    stack_before  = pk_state.stacks[opp_id]
    max_to_amount = pk_state.max_completion_betting_or_raising_to_amount

    persona_action(pk_state, opp_id, policy)

    stack_after = pk_state.stacks[opp_id]
    invest      = stack_before - stack_after
    was_allin   = (stack_after == 0 and invest > cca_before + 1e-9) \
                  or (max_to_amount == stack_before
                      and invest > cca_before + 1e-9
                      and stack_before == max_to_amount)

    pa = classify_opp_action(stack_before, stack_after, cca_before,
                             pot_before, was_allin=was_allin)
    if pa is not None:
        prev_action_by_round[r_before] = pa
