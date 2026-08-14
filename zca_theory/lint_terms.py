# -*- coding: utf-8 -*-
"""어휘 검수 하네스 — 용어집.md + 주장정리.md §6 서술 지침의 실행판.

usage: python lint_terms.py <파일.md> [...]
검사 3층:
  A. 용어집 지양 표기 (음차·비표준·직역): 스킴/셋업/노이즈/기대값/진짜값/손(hand)/냄비 등
  B. 라벨·수식어 규칙 (저자 교정 2026-08-14): "표준 처방"·"경쟁 처방"·출처 없는 수식어
  C. 감사 규칙: "TD를 쓸 수 없" 류 도메인 불가능성, 부재 주장 무한정("확인되지 않는다"
     — 조사 범위 한정 미병기 검출은 근사: 같은 문장에 "범위" 없으면 경고)
한계(정직): 문자열 패턴 검사라 문맥 오탐 가능(예: 인용문 안의 지양 표기·'스킴' 포함
고유명). 결과는 후보 목록이며 최종 판단은 사람이 한다.
"""
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# (패턴, 지향 표기/사유, 심각도) — 심각도: E(위반) / W(검토 후보)
RULES = [
    # A. 용어집 §2 지양 음차
    (r'스킴', '방식/기법 (용어집 §2)', 'E'),
    (r'셋업', '설정/구성 (§2)', 'E'),
    (r'노이즈', '잡음 (§2)', 'E'),
    (r'로버스트', '강건한/강건성 (§2)', 'E'),
    (r'트레이드오프', '절충/상충 (§2)', 'E'),
    (r'베이스라인', '기준선 (§2)', 'E'),
    (r'리워드', '보상 (§2)', 'E'),
    (r'컨버전스', '수렴 (§2)', 'E'),
    (r'디스소시에이션', '해리 (§2)', 'E'),
    # A. KCI 표준어
    (r'기대값', '기댓값 (사이시옷 표준)', 'E'),
    (r'진짜값|진짜 가치', '참값/참 가치', 'E'),
    (r'음성 결과', '부정적 결과', 'E'),
    (r'보상 정형화', '보상 형성 (기여도 정형화의 "정형화"는 유지)', 'E'),
    (r'탐욕적', 'greedy 원어 유지 (용어집 §2)', 'E'),
    # A. 포커 직역 금지 (§1)
    (r'체크한 손|한 손[을이]|손마다|손을 접', 'hand=핸드 — "손" 직역 금지', 'E'),
    (r'냄비', 'pot=팟', 'E'),
    (r'판돈', '팟 (용어집 §1 — pot 음차 통일)', 'W'),
    # B. 라벨·수식어 (주장정리 §6, 저자 교정)
    (r'표준 처방', '금지 라벨 — 처방 명시 열거 (개정 13)', 'E'),
    (r'경쟁 처방', '금지 라벨(에이전트 자작) — 명시 열거 (개정 13)', 'E'),
    (r'널리 쓰이는|잘 알려진', '출처 없는 수식어 — 명시 열거+인용', 'W'),
    # C. 감사 규칙
    (r'TD를 쓸 수 없|TD가 불가능', '"말단 귀속 회계를 채택한 정식화" 조건부로 (감사 ①)', 'E'),
]

ABSENCE = re.compile(r'확인되지 않는|명명되어 있지 않')
SCOPE = re.compile(r'범위|기준\)')


def lint(path: str) -> int:
    n = 0
    text = io.open(path, encoding='utf-8').read()
    in_comment = False
    for i, line in enumerate(text.splitlines(), 1):
        # HTML 주석(판올림 이력·작업 메모)은 지면에 안 나가므로 검사 제외
        if in_comment:
            if '-->' in line:
                in_comment = False
            continue
        if line.lstrip().startswith('<!--'):
            if '-->' not in line:
                in_comment = True
            continue
        for pat, msg, sev in RULES:
            for m in re.finditer(pat, line):
                n += 1
                print(f'{path}:{i} [{sev}] "{m.group(0)}" -> {msg}')
        if ABSENCE.search(line) and not SCOPE.search(line):
            n += 1
            print(f'{path}:{i} [W] 부재 주장 — 조사 범위 한정 미병기 후보 (감사 ⑤)')
    return n


if __name__ == '__main__':
    total = 0
    for p in sys.argv[1:]:
        total += lint(p)
    print(f'-- 검출 {total}건 (E=위반, W=검토 후보; 문맥 오탐 가능 — 최종 판단은 사람)')
