"""
qlearning.py
─────────────────────────────────────────────────────────────────────
테이블 기반 Q-러닝 (TD(0) bootstrap)

Q-테이블 크기: 4(라운드) × 2(포지션) × 5(상태) × 8(행동) = 320 엔트리

포지션을 상태 차원에 포함시킨 이유:
  헤즈업에서 SB/BB는 행동 순서·강제 베팅·정보량이 모두 달라 사실상
  서로 다른 게임이다. 같은 핸드라도 포지션에 따라 최적 행동이 다르므로
  Q-테이블이 두 포지션을 별도 셀로 학습한다.

벨만 업데이트:
    Q(r,p,s,a) ← Q(r,p,s,a) + α[reward + γ · max_a' Q(r',p,s',a') - Q(r,p,s,a)]
"""
import pickle
import random
from pathlib import Path
from abstraction import Round, Position, State, Action


class QLearning:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9):
        self.alpha = alpha
        self.gamma = gamma
        # Q-테이블: [round][position][state][action] → float
        self.q = [[[[0.0] * len(Action) for _ in State]
                   for _ in Position] for _ in Round]

    # ── Q값 조회/저장 ──────────────────────────────────
    def get_q(self, r: Round, p: Position, s: State, a: Action) -> float:
        return self.q[r.value][p.value][s.value][a.value]

    def _set_q(self, r: Round, p: Position, s: State, a: Action, v: float) -> None:
        self.q[r.value][p.value][s.value][a.value] = v

    # ── 다음 (라운드, 포지션, 상태)의 최대 Q값 ────────
    def max_q_next(self, next_r: Round, p: Position, next_s: State) -> float:
        return max(self.q[next_r.value][p.value][next_s.value])

    # ── 벨만 업데이트 (터미널/비터미널 통합) ──────────
    def update_q(self, r: Round, p: Position, s: State, a: Action,
                 reward: float,
                 next_r: Round = None, next_s: State = None,
                 terminal: bool = True) -> float:
        old = self.get_q(r, p, s, a)
        if terminal:
            target = reward
        else:
            target = reward + self.gamma * self.max_q_next(next_r, p, next_s)
        new = old + self.alpha * (target - old)
        self._set_q(r, p, s, a, new)
        return new

    # ── greedy 최선 행동 ───────────────────────────────
    def best_action(self, r: Round, p: Position, s: State,
                    legal: list[Action] = None) -> Action:
        candidates = legal if legal else list(Action)
        return max(candidates, key=lambda a: self.get_q(r, p, s, a))

    # ── ε-탐욕 정책 ────────────────────────────────────
    def epsilon_greedy(self, r: Round, p: Position, s: State,
                       legal: list[Action], epsilon: float) -> Action:
        if not legal:
            return Action.FOLD
        if random.random() < epsilon:
            return random.choice(legal)
        return self.best_action(r, p, s, legal)

    # ── 테이블 출력 (디버깅용) ────────────────────────
    def print_q_table(self) -> None:
        header = (f"{'Round':<8}{'Pos':<4}{'State':<10}"
                  + "".join(f"{a.name:>12}" for a in Action))
        print(header)
        print("-" * len(header))
        for r in Round:
            for p in Position:
                for s in State:
                    row = f"{r.name:<8}{p.name:<4}{s.name:<10}"
                    for a in Action:
                        row += f"{self.get_q(r, p, s, a):>12.3f}"
                    print(row)

    # ── pickle 저장 / 로드 ─────────────────────────────
    def save(self, path) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as f:
            pickle.dump({
                'q': self.q,
                'alpha': self.alpha, 'gamma': self.gamma,
                'schema': 'td-eps-4dim',  # q[r][p][s][a]
            }, f)
        return str(p)

    @classmethod
    def load(cls, path) -> 'QLearning':
        with open(path, 'rb') as f:
            data = pickle.load(f)
        ql = cls(alpha=data['alpha'], gamma=data['gamma'])
        ql.q = data['q']
        return ql
