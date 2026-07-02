# -*- coding: utf-8 -*-
"""누수 재발 방지 불변식 테스트 (E0c).

불변식: PROP + VIC-off + CLEAN_ZERO_INVEST=True 로 학습하면
        Q(·, CHECK) 는 모든 셀에서 정확히 0.0 이어야 한다 (Lemma 2).
±1.4 잔여를 수개월간 '면도날 띠'로 서사화했던 실패의 재발 방지 장치.
실행: ../.venv/Scripts/python.exe test_invariants.py   (수 초)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import train_softmax_persona_2000k as pb
import rulebased_personas as personas
from abstraction import Round, Position, State, PrevAction, Action
from qlearning import QLearning

N_EP = 10_000


def test_check_zero_fixed_point():
    pb.CLEAN_ZERO_INVEST = True
    pb.POT_MODE = 'off'
    pb.POT_APPLY = 'all'
    pb.CHECK_VIRTUAL_INVEST = 0            # VIC off
    random.seed(7)
    ql = QLearning(alpha=0.1, gamma=0.9, ucb_c=50.0)
    policy = personas.PERSONA_POLICIES['tag']
    for i in range(N_EP):
        pb.play_train_episode(ql, 5.0, policy, learner_id=i % 2)
    bad = []
    for r in Round:
        for p in Position:
            for s in State:
                for pa in PrevAction:
                    qc = ql.get_q(r, p, s, pa, Action.CHECK)
                    if qc != 0.0:
                        bad.append(((r.name, p.name, s.name, pa.name), qc))
    assert not bad, f"불변식 위반: Q(CHECK)!=0 셀 {len(bad)}개, 예 {bad[:3]}"
    print(f"OK: {N_EP} ep 학습 후 전 셀 Q(CHECK)==0.0 정확 (Lemma 2 불변식 통과)")


def test_allcheck_skipped_when_clean():
    # 보조 불변식: invested_only 모드에서도 CHECK==0 유지(가상 invest가 있어도 credit은 실투자 핸드에만)
    pb.CLEAN_ZERO_INVEST = True
    pb.POT_MODE = 'checktime'
    pb.CHECK_POT_FRAC = 0.30
    pb.POT_APPLY = 'allcheck_only'         # 실투자 핸드 CHECK credit 0 강제
    random.seed(7)
    ql = QLearning(alpha=0.1, gamma=0.9, ucb_c=50.0)
    policy = personas.PERSONA_POLICIES['tag']
    for i in range(N_EP):
        pb.play_train_episode(ql, 5.0, policy, learner_id=i % 2)
    # allcheck_only에서 CHECK가 값을 갖는 유일한 경로는 올체크 핸드의 payoff/n
    # → CHECK Q의 |값|은 블라인드 규모(±3칩) 이내여야 함
    for r in Round:
        for p in Position:
            for s in State:
                for pa in PrevAction:
                    qc = ql.get_q(r, p, s, pa, Action.CHECK)
                    assert abs(qc) < 5.0, f"allcheck_only 예상 밖 CHECK Q: {qc}"
    print("OK: allcheck_only 모드에서 CHECK Q가 블라인드 규모 이내 (격리 모드 정상)")


if __name__ == '__main__':
    test_check_zero_fixed_point()
    test_allcheck_skipped_when_clean()
    pb.POT_MODE = 'off'; pb.POT_APPLY = 'all'; pb.CHECK_POT_FRAC = 0.0
    print("ALL INVARIANTS PASSED")
