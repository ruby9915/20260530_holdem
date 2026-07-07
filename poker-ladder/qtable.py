# -*- coding: utf-8 -*-
"""차원 파라미터화 Q-테이블 (레거시 qlearning.py 의 State-8 하드코딩 제거).

q[round][pos][state][prev][action], 상수 α — 레거시와 동일한 갱신·선택 의미론.
"""
import math
import pickle
import random
from pathlib import Path

from actions import Action
from defs import PrevAction, Position, Round


class QTable:
    def __init__(self, n_states: int, alpha: float = 0.1, gamma: float = 0.9,
                 init_q: float = 0.0, n_actions: int = 8):
        self.n_states = n_states
        self.n_actions = n_actions      # A8=8, A12=12 (행동축 버전별 행 길이)
        self.alpha = alpha
        self.gamma = gamma
        self.init_q = init_q            # E8-② 낙관적 초기화 재현용 (기본 0)
        dims = (len(Round), len(Position), n_states, len(PrevAction), n_actions)
        self.q = [[[[[init_q] * dims[4] for _ in range(dims[3])]
                    for _ in range(dims[2])]
                   for _ in range(dims[1])] for _ in range(dims[0])]
        self.n = [[[[[0] * dims[4] for _ in range(dims[3])]
                    for _ in range(dims[2])]
                   for _ in range(dims[1])] for _ in range(dims[0])]

    def get_q(self, r: Round, p: Position, s: int, pa: PrevAction, a: Action) -> float:
        return self.q[r.value][p.value][s][pa.value][a.value]

    def update_mc(self, r: Round, p: Position, s: int, pa: PrevAction,
                  a: Action, g: float) -> None:
        row = self.q[r.value][p.value][s][pa.value]
        row[a.value] += self.alpha * (g - row[a.value])
        self.n[r.value][p.value][s][pa.value][a.value] += 1

    def best_action(self, r: Round, p: Position, s: int, pa: PrevAction,
                    legal: list[Action]) -> Action:
        row = self.q[r.value][p.value][s][pa.value]
        return max(legal, key=lambda a: row[a.value])

    def softmax_action(self, r: Round, p: Position, s: int, pa: PrevAction,
                       legal: list[Action], temperature: float) -> Action:
        if not legal:
            return Action.FOLD
        row = self.q[r.value][p.value][s][pa.value]
        q_vals = [row[a.value] for a in legal]
        max_q = max(q_vals)
        shifted = [(q - max_q) / temperature for q in q_vals]
        try:
            exps = [math.exp(v) for v in shifted]
            total = sum(exps)
            probs = [v / total for v in exps]
        except OverflowError:
            probs = [0.0] * len(legal)
            probs[q_vals.index(max_q)] = 1.0
        return random.choices(legal, weights=probs, k=1)[0]

    # ── 저장/로드 ──────────────────────────────────────────
    def save(self, path, meta: dict | None = None) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as f:
            pickle.dump({'schema': 'ladder-v1', 'n_states': self.n_states,
                         'n_actions': self.n_actions,
                         'alpha': self.alpha, 'gamma': self.gamma,
                         'q': self.q, 'n': self.n, 'meta': meta or {}}, f)
        return str(p)

    @classmethod
    def load(cls, path) -> 'QTable':
        with open(path, 'rb') as f:
            d = pickle.load(f)
        assert d['schema'] == 'ladder-v1', f"schema mismatch: {d.get('schema')}"
        qt = cls(d['n_states'], alpha=d['alpha'], gamma=d['gamma'],
                 n_actions=d.get('n_actions', 8))
        qt.q, qt.n = d['q'], d['n']
        qt.meta = d.get('meta', {})
        return qt
