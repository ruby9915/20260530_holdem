"""
qlearning.py  (PrevAction 차원 확장 버전)
─────────────────────────────────────────────────────────────────────
원본 poker-pokerkit-ucb/qlearning.py 를 그대로 따르되,
**Q/N 테이블에 PrevAction 한 축을 추가**한다.

테이블 모양:
    q[round][position][hand_state][prev_action][action]
    n[round][position][hand_state][prev_action][action]

= 4 × 2 × 8 × 4 × 8 = 2,048 셀.

모든 시그니처에 `pa: PrevAction` 인자가 끼어든다.
"""
import math
import pickle
import random
from io import StringIO
from pathlib import Path
from abstraction import Round, Position, State, PrevAction, Action


class QLearning:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9,
                 ucb_c: float = 50.0):
        self.alpha = alpha
        self.gamma = gamma
        self.ucb_c = ucb_c

        # Q-테이블: [round][position][state][prev_action][action] → float
        self.q = [[[[[0.0] * len(Action) for _ in PrevAction]
                    for _ in State]
                   for _ in Position] for _ in Round]

        # 방문 카운트
        self.n = [[[[[0] * len(Action) for _ in PrevAction]
                    for _ in State]
                   for _ in Position] for _ in Round]

    # ── Q값 조회/저장 ──────────────────────────────────
    def get_q(self, r: Round, p: Position, s: State,
              pa: PrevAction, a: Action) -> float:
        return self.q[r.value][p.value][s.value][pa.value][a.value]

    def _set_q(self, r: Round, p: Position, s: State,
               pa: PrevAction, a: Action, v: float) -> None:
        self.q[r.value][p.value][s.value][pa.value][a.value] = v

    def increment_n(self, r: Round, p: Position, s: State,
                    pa: PrevAction, a: Action) -> None:
        self.n[r.value][p.value][s.value][pa.value][a.value] += 1

    # ── UCB1 행동 선택 ────────────────────────────────
    def ucb_action(self, r: Round, p: Position, s: State,
                   pa: PrevAction, legal: list[Action]) -> Action:
        if not legal:
            return Action.FOLD

        unvisited = [a for a in legal
                     if self.n[r.value][p.value][s.value][pa.value][a.value] == 0]
        if unvisited:
            return random.choice(unvisited)

        n_s = sum(self.n[r.value][p.value][s.value][pa.value][a.value]
                  for a in legal)
        log_n_s = math.log(n_s)

        best_a, best_v = None, float('-inf')
        for a in legal:
            n_sa = self.n[r.value][p.value][s.value][pa.value][a.value]
            ucb  = self.get_q(r, p, s, pa, a) + self.ucb_c * math.sqrt(log_n_s / n_sa)
            if ucb > best_v:
                best_v, best_a = ucb, a
        return best_a

    # ── greedy ────────────────────────────────────────
    def best_action(self, r: Round, p: Position, s: State,
                    pa: PrevAction, legal: list[Action] = None) -> Action:
        candidates = legal if legal else list(Action)
        return max(candidates, key=lambda a: self.get_q(r, p, s, pa, a))

    # ── ε-greedy ──────────────────────────────────────
    def epsilon_greedy(self, r: Round, p: Position, s: State,
                       pa: PrevAction, legal: list[Action],
                       epsilon: float) -> Action:
        if not legal:
            return Action.FOLD
        if random.random() < epsilon:
            return random.choice(legal)
        return self.best_action(r, p, s, pa, legal)

    # ── Softmax (Boltzmann) Exploration ───────────────
    def softmax_action(self, r: Round, p: Position, s: State,
                       pa: PrevAction, legal: list[Action],
                       temperature: float) -> Action:
        if not legal:
            return Action.FOLD
        
        # 1. Get Q-values for legal actions
        q_vals = [self.get_q(r, p, s, pa, a) for a in legal]
        
        # 2. Shift to prevent numeric overflow in exp
        max_q = max(q_vals)
        shifted = [(q - max_q) / temperature for q in q_vals]
        
        # 3. Compute exponentials and probabilities safely
        try:
            exps = [math.exp(val) for val in shifted]
            sum_exps = sum(exps)
            probs = [val / sum_exps for val in exps]
        except OverflowError:
            # Fallback to greedy if overflow occurs
            best_idx = q_vals.index(max_q)
            probs = [0.0] * len(legal)
            probs[best_idx] = 1.0
            
        # 4. Sample action based on probabilities
        return random.choices(legal, weights=probs, k=1)[0]

    # ── Softmax + UCB 하이브리드 (Boltzmann–Gumbel 계열) ──
    def softmax_ucb_action(self, r: Round, p: Position, s: State,
                           pa: PrevAction, legal: list[Action],
                           temperature: float,
                           ucb_c: float = None) -> Action:
        """
        값(Q)과 불확실성(UCB 보너스)을 합친 증강값 위에서 softmax 샘플링.

            v(a) = Q(a) + c * sqrt( log(N_s + 1) / (n(a) + 1) )

        - 미방문(n=0) 액션은 보너스가 최대(유한)라 확률이 높게 잡힘
          → softmax 의 "tail-action 확률 0" 약점을 UCB 가 보완.
        - n 이 커질수록 보너스 → 0, 순수 softmax(값 기반)로 수렴.
        순수 softmax(index-invariant) 성질은 그대로 유지된다.
        """
        if not legal:
            return Action.FOLD

        c = self.ucb_c if ucb_c is None else ucb_c
        n_s = sum(self.n[r.value][p.value][s.value][pa.value][a.value]
                  for a in legal)
        log_term = math.log(n_s + 1)

        # 1. 증강값 = Q + UCB 보너스
        aug = []
        for a in legal:
            n_sa  = self.n[r.value][p.value][s.value][pa.value][a.value]
            bonus = c * math.sqrt(log_term / (n_sa + 1))
            aug.append(self.get_q(r, p, s, pa, a) + bonus)

        # 2. 수치 안정화 후 softmax
        max_v   = max(aug)
        shifted = [(v - max_v) / temperature for v in aug]
        try:
            exps     = [math.exp(val) for val in shifted]
            sum_exps = sum(exps)
            probs    = [val / sum_exps for val in exps]
        except OverflowError:
            best_idx = aug.index(max_v)
            probs = [0.0] * len(legal)
            probs[best_idx] = 1.0

        return random.choices(legal, weights=probs, k=1)[0]

    # ── TD(0) ─────────────────────────────────────────
    def update_q(self, r: Round, p: Position, s: State,
                 pa: PrevAction, a: Action, reward: float,
                 next_r: Round = None, next_s: State = None,
                 next_pa: PrevAction = None,
                 terminal: bool = True) -> float:
        old = self.get_q(r, p, s, pa, a)
        if terminal:
            target = reward
        else:
            npa = next_pa if next_pa is not None else PrevAction.NONE
            target = reward + self.gamma * max(
                self.q[next_r.value][p.value][next_s.value][npa.value])
        new = old + self.alpha * (target - old)
        self._set_q(r, p, s, pa, a, new)
        return new

    # ── Monte Carlo ───────────────────────────────────
    def update_mc(self, r: Round, p: Position, s: State,
                  pa: PrevAction, a: Action, g: float) -> float:
        old = self.get_q(r, p, s, pa, a)
        new = old + self.alpha * (g - old)
        self._set_q(r, p, s, pa, a, new)
        return new

    # ── 디버깅용 출력 ────────────────────────────────
    def print_q_table(self) -> None:
        header = (f"{'Round':<8}{'Pos':<4}{'State':<10}{'PrevA':<12}"
                  + "".join(f"{a.name:>12}" for a in Action))
        print(header)
        print("-" * len(header))
        for r in Round:
            for p in Position:
                for s in State:
                    for pa in PrevAction:
                        row = (f"{r.name:<8}{p.name:<4}{s.name:<10}"
                               f"{pa.name:<12}")
                        for a in Action:
                            row += f"{self.get_q(r, p, s, pa, a):>12.3f}"
                        print(row)

    def q_table_markdown(self, title: str = "=== Q-Table ===") -> str:
        buf = StringIO()
        print(title, file=buf)
        header = (f"{'Round':<8}{'Pos':<4}{'State':<10}{'PrevA':<12}"
                  + "".join(f"{a.name:>12}" for a in Action))
        print(header, file=buf)
        print("-" * len(header), file=buf)
        for r in Round:
            for p in Position:
                for s in State:
                    for pa in PrevAction:
                        row = (f"{r.name:<8}{p.name:<4}{s.name:<10}"
                               f"{pa.name:<12}")
                        for a in Action:
                            row += f"{self.get_q(r, p, s, pa, a):>12.3f}"
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
                'schema': 'prev-5dim',  # q[r][p][s][pa][a]
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
