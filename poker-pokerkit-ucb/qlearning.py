"""
qlearning.py (UCB 탐색 버전)
─────────────────────────────────────────────────────────────────────
테이블 기반 Q-러닝 — ε-greedy 대신 UCB1 탐색 정책 사용.

Q-테이블 크기: 4(라운드) × 2(포지션) × 8(상태) × 8(행동) = 512 엔트리

UCB1 행동 선택:
    미방문 행동 → 즉시 선택 (무한 우선순위)
    방문한 행동 → Q(s,a) + c * sqrt(ln(N_s) / N(s,a))

    N_s    : 해당 (라운드, 포지션, 상태)를 방문한 총 횟수
    N(s,a) : 해당 (상태, 행동) 셀을 선택한 횟수
    c      : 탐색 강도 계수 (보상 스케일에 맞게 조정 필요)

업데이트 메서드:
    update_q  : TD(0) 벨만 업데이트
    update_mc : Monte Carlo 누적 리턴 G 업데이트
"""
import math
import pickle
import random
from io import StringIO
from pathlib import Path
from abstraction import Round, Position, State, Action


class QLearning:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9,
                 ucb_c: float = 50.0):
        self.alpha  = alpha
        self.gamma  = gamma
        self.ucb_c  = ucb_c

        # Q-테이블: [round][position][state][action] → float
        self.q = [[[[0.0] * len(Action) for _ in State]
                   for _ in Position] for _ in Round]

        # 방문 카운트: [round][position][state][action] → int
        self.n = [[[[0] * len(Action) for _ in State]
                   for _ in Position] for _ in Round]

    # ── Q값 조회/저장 ──────────────────────────────────
    def get_q(self, r: Round, p: Position, s: State, a: Action) -> float:
        return self.q[r.value][p.value][s.value][a.value]

    def _set_q(self, r: Round, p: Position, s: State, a: Action,
               v: float) -> None:
        self.q[r.value][p.value][s.value][a.value] = v

    # ── 방문 카운트 갱신 ───────────────────────────────
    def increment_n(self, r: Round, p: Position, s: State,
                    a: Action) -> None:
        self.n[r.value][p.value][s.value][a.value] += 1

    # ── UCB1 행동 선택 (학습용) ────────────────────────
    def ucb_action(self, r: Round, p: Position, s: State,
                   legal: list[Action]) -> Action:
        """
        합법 행동 중 UCB 값이 가장 높은 행동 반환.
        미방문 행동이 있으면 먼저 선택 (탐욕 이전 탐색 보장).
        """
        if not legal:
            return Action.FOLD

        # 미방문 행동 우선 탐색
        unvisited = [a for a in legal
                     if self.n[r.value][p.value][s.value][a.value] == 0]
        if unvisited:
            return random.choice(unvisited)

        # N_s = 이 (r, p, s)에서 legal 행동들의 방문 합
        n_s = sum(self.n[r.value][p.value][s.value][a.value] for a in legal)
        log_n_s = math.log(n_s)

        best_a, best_v = None, float('-inf')
        for a in legal:
            n_sa = self.n[r.value][p.value][s.value][a.value]
            ucb  = self.get_q(r, p, s, a) + self.ucb_c * math.sqrt(log_n_s / n_sa)
            if ucb > best_v:
                best_v, best_a = ucb, a
        return best_a

    # ── greedy 최선 행동 (평가용, ε=0) ────────────────
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

    # ── TD(0) 벨만 업데이트 ────────────────────────────
    def update_q(self, r: Round, p: Position, s: State, a: Action,
                 reward: float,
                 next_r: Round = None, next_s: State = None,
                 terminal: bool = True) -> float:
        old = self.get_q(r, p, s, a)
        if terminal:
            target = reward
        else:
            target = reward + self.gamma * max(
                self.q[next_r.value][p.value][next_s.value])
        new = old + self.alpha * (target - old)
        self._set_q(r, p, s, a, new)
        return new

    # ── Monte Carlo 업데이트 ───────────────────────────
    def update_mc(self, r: Round, p: Position, s: State, a: Action,
                  g: float) -> float:
        """Q(s,a) ← Q(s,a) + α [ G - Q(s,a) ]"""
        old = self.get_q(r, p, s, a)
        new = old + self.alpha * (g - old)
        self._set_q(r, p, s, a, new)
        return new

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

    def q_table_markdown(self, title: str = "=== Q-Table ===") -> str:
        buf = StringIO()
        print(title, file=buf)
        header = (f"{'Round':<8}{'Pos':<4}{'State':<10}"
                  + "".join(f"{a.name:>12}" for a in Action))
        print(header, file=buf)
        print("-" * len(header), file=buf)
        for r in Round:
            for p in Position:
                for s in State:
                    row = f"{r.name:<8}{p.name:<4}{s.name:<10}"
                    for a in Action:
                        row += f"{self.get_q(r, p, s, a):>12.3f}"
                    print(row, file=buf)
        return buf.getvalue()

    def save_qtable_markdown(self, path: str,
                             title: str = "=== Q-Table ===") -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(self.q_table_markdown(title))
        return str(p)

    # ── pickle 저장 / 로드 ─────────────────────────────
    def save(self, path) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as f:
            pickle.dump({
                'q': self.q, 'n': self.n,
                'alpha': self.alpha, 'gamma': self.gamma,
                'ucb_c': self.ucb_c,
                'schema': 'ucb-4dim',  # q[r][p][s][a]
            }, f)
        return str(p)

    @classmethod
    def load(cls, path) -> 'QLearning':
        with open(path, 'rb') as f:
            data = pickle.load(f)
        ql = cls(alpha=data['alpha'], gamma=data['gamma'],
                 ucb_c=data['ucb_c'])
        ql.q = data['q']
        ql.n = data['n']
        return ql
