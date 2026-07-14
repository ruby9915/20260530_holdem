# -*- coding: utf-8 -*-
"""추상 HUNL 베팅 트리 생성기 (4단 부품 ④-1).

게임 규약 = poker-ladder 와 동일: SB 1 / BB 2 / 스택 200 (100bb).
등급 메뉴 (35절 (3) — Jackson 2013 축소판):
  1레벨(첫 벳·오픈레이즈): 팟의 {0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4}  ← 학습자 A12 와 일치
  2레벨(레이즈):           팟의 {0.5, 1, 2}
  3레벨 이상(3-벳+):       팟의 {1}
  올인: 항상 허용 / 폴드·콜·체크: 규칙대로
벳 산술은 학습자 execute_action 과 동일(팟 = 기여 총합, raise = cmax + max(int(pot·f), BB),
최소 레이즈 = 직전 레이즈 폭, 스택 클램프) — 번역 제로의 전제.

트리 노드(불변 객체) 종류:
  DecisionNode(street, to_act, contrib, last_raise, level, seq, actions->child)
  ChanceNode(street 경계 — 버킷 전이 지점)
  TerminalNode(kind='fold'|'showdown'|'allin_runout', ...)
usage: python hunl_tree.py  → 노드 수 실측 리포트
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SB, BB, STACK = 1, 2, 200
# 2026-07-14 확폭: 2레벨(레이즈)도 학습자 A12 8종과 일치 — 실측 번역 27%가
# 사전등록 의도("번역 최소화")를 위반해 수정 (트리 2.1배 감수, 실험일지 35절 보강).
MENU = {1: (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0),
        2: (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)}
MENU_DEEP = (1.0,)                      # 3레벨 이상
N_STREETS = 4                            # 프리플랍/플랍/턴/리버


class Terminal:
    __slots__ = ('kind', 'street', 'contrib', 'folder')

    def __init__(self, kind, street, contrib, folder=None):
        self.kind = kind                 # 'fold' | 'showdown' | 'allin'
        self.street = street             # 종결(또는 올인) 시점 라운드
        self.contrib = contrib           # (p0 총투입, p1 총투입)
        self.folder = folder


class Chance:
    __slots__ = ('street', 'child')      # street 경계: street→street+1 버킷 전이

    def __init__(self, street, child):
        self.street = street
        self.child = child


class Decision:
    __slots__ = ('street', 'to_act', 'contrib', 'children', 'seq',
                 'acts', 'regret', 'ssum')       # 뒤 3개는 솔버가 부착

    def __init__(self, street, to_act, contrib, seq):
        self.street = street
        self.to_act = to_act             # 0=SB석, 1=BB석 (좌석 기준)
        self.contrib = contrib
        self.children = {}               # action label -> node
        self.seq = seq                   # 베팅 시퀀스 문자열 (정보집합 키 성분)


def _menu(level):
    return MENU.get(level, MENU_DEEP)


def build():
    """전체 베팅 트리 생성. 반환: 루트(프리플랍 SB 결정) + 통계."""
    stats = {'decision': 0, 'chance': 0, 'terminal': 0, 'seqs_per_street': [0] * N_STREETS}

    def make_decision(street, to_act, contrib, owed, last_raise, level,
                      checked, seq):
        """owed = (to_act 가 콜하려면 낼 추가 칩). checked = 이번 라운드 체크 수."""
        node = Decision(street, to_act, contrib, seq)
        stats['decision'] += 1
        stats['seqs_per_street'][street] += 1
        me, opp = to_act, 1 - to_act
        my_c, opp_c = contrib[me], contrib[opp]
        pot = contrib[0] + contrib[1]
        my_stack = STACK - my_c

        def advance(new_contrib):
            """콜/체크로 라운드 종결 → 다음 라운드 or 쇼다운."""
            if street == N_STREETS - 1:
                return Terminal('showdown', street, new_contrib)
            stats['chance'] += 1
            nxt = make_decision(street + 1, 1, new_contrib, 0, BB, 0, 0, '')
            return Chance(street, nxt)

        # ── 폴드/콜/체크 ──
        if owed > 0:
            node.children['f'] = Terminal('fold', street, contrib, folder=me)
            stats['terminal'] += 1
            call_amt = min(owed, my_stack)
            nc = list(contrib); nc[me] += call_amt
            nc = tuple(nc)
            if contrib[opp] >= STACK or call_amt < owed:      # 상대 올인 콜 → 런아웃
                node.children['c'] = Terminal('allin', street, nc)
                stats['terminal'] += 1
            elif street == 0 and level == 1:
                # 프리플랍 림프: BB 옵션 (체크=라운드 종결 / 레이즈=1레벨 메뉴)
                node.children['c'] = make_decision(street, opp, nc, 0, BB,
                                                   level, 1, seq + 'c')
            else:
                node.children['c'] = advance(nc)
        else:
            if checked == 0 and not (street == 0 and level == 1):
                # 첫 체크 → 상대 차례 (프리플랍 BB 옵션 포함)
                node.children['k'] = make_decision(street, opp, contrib, 0,
                                                   last_raise, level, 1, seq + 'k')
            else:
                node.children['k'] = advance(contrib)          # 체크-체크 종결

        # ── 레이즈 메뉴 (+올인) ──
        if my_stack > owed:                                    # 레이즈 여력
            targets = set()
            for f in _menu(level):
                raise_size = max(int(pot * f), BB)
                target = opp_c + raise_size                    # bet-to (상대 기여 기준)
                target = max(target, opp_c + last_raise)       # 최소 레이즈
                target = min(target, STACK)
                if target > opp_c and target - my_c > owed:
                    targets.add(target)
            targets.add(STACK)                                 # 올인 상시
            for target in sorted(targets):
                nc = list(contrib); nc[me] = target
                nc = tuple(nc)
                lbl = f'b{target}'
                new_owed = target - contrib[opp]
                if target >= STACK:
                    child_owed_stack = STACK - contrib[opp]
                if new_owed <= 0:
                    continue
                node.children[lbl] = make_decision(
                    street, opp, nc, new_owed,
                    max(target - opp_c, BB), level + 1, checked, seq + lbl)
        return node

    # 프리플랍: 블라인드 SB=1, BB=2 게시. SB(좌석0) 선행동, owed=1, level=1(BB=첫 벳 취급
    # 이되 오픈레이즈는 1레벨 메뉴 — 학습자 행동공간 정합)
    root = make_decision(0, 0, (SB, BB), BB - SB, BB, 1, 0, '')
    return root, stats


def main():
    import time
    t0 = time.time()
    sys.setrecursionlimit(100000)
    root, stats = build()
    print(f"빌드 {time.time()-t0:.1f}s")
    print(f"결정 노드: {stats['decision']:,}")
    print(f"찬스 노드: {stats['chance']:,}")
    print(f"종단 노드: {stats['terminal']:,}")
    for st, n in enumerate(stats['seqs_per_street']):
        print(f"  라운드 {st} 결정 노드: {n:,}")
    K = 50
    infosets = stats['seqs_per_street'][0] * 169 + sum(stats['seqs_per_street'][1:]) * K
    print(f"정보집합 추정 (프리플랍 169 무손실 + 포스트플랍 K={K}): {infosets:,}")


if __name__ == '__main__':
    main()
