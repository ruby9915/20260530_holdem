"""
qlearning.py
─────────────────────────────────────────────────────────────────────
테이블 기반 Q-러닝 (Java QLearning.java의 Python 포팅)

Q-테이블 크기: 4(라운드) × 5(상태) × 8(행동) = 160 엔트리
벨만 업데이트:
    Q(r,s,a) ← Q(r,s,a) + α[r + γ · max_a' Q(r+1,s',a') - Q(r,s,a)]
"""
import random
from abstraction import Round, State, Action


class QLearning:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9):
        # 하이퍼파라미터
        self.alpha = alpha   # 학습률
        self.gamma = gamma   # 할인율
        # Q-테이블: [round][state][action] → float
        self.q = [[[0.0] * len(Action) for _ in State] for _ in Round]

    # ── Q값 조회/저장 ──────────────────────────────────
    def get_q(self, r: Round, s: State, a: Action) -> float:
        return self.q[r.value][s.value][a.value]

    def _set_q(self, r: Round, s: State, a: Action, v: float) -> None:
        self.q[r.value][s.value][a.value] = v

    # ── 다음 라운드 최대 Q값 (벨만의 max_a' Q(s',a') 부분) ──
    def max_q_next(self, next_r: Round, next_s: State) -> float:
        return max(self.q[next_r.value][next_s.value])

    # ── 벨만 업데이트 (터미널/비터미널 통합) ──────────
    def update_q(self, r: Round, s: State, a: Action,
                reward: float,
                next_r: Round = None, next_s: State = None,
                terminal: bool = True) -> float:
        old = self.get_q(r, s, a)
        if terminal:
            # 라운드 종료: 미래 보상 없음
            target = reward
        else:
            # 비터미널: reward + γ · max Q(s', a')
            target = reward + self.gamma * self.max_q_next(next_r, next_s)
        new = old + self.alpha * (target - old)
        self._set_q(r, s, a, new)
        return new

    # ── greedy 최선 행동 ───────────────────────────────
    def best_action(self, r: Round, s: State,
                    legal: list[Action] = None) -> Action:
        """legal이 주어지면 그 안에서만 선택, 아니면 전체에서 선택"""
        candidates = legal if legal else list(Action)
        return max(candidates, key=lambda a: self.get_q(r, s, a))

    # ── ε-탐욕 정책 ────────────────────────────────────
    def epsilon_greedy(self, r: Round, s: State,
                    legal: list[Action], epsilon: float) -> Action:
        if not legal:
            return Action.FOLD   # 안전장치
        if random.random() < epsilon:
            return random.choice(legal)
        return self.best_action(r, s, legal)

    # ── 테이블 출력 (디버깅용) ────────────────────────
    def print_q_table(self) -> None:
        header = f"{'Round':<8}{'State':<10}" + "".join(
            f"{a.name:>12}" for a in Action)
        print(header)
        print("-" * len(header))
        for r in Round:
            for s in State:
                row = f"{r.name:<8}{s.name:<10}"
                for a in Action:
                    row += f"{self.get_q(r, s, a):>12.3f}"
                print(row)
