# poker-cfrplus — CFR+ near-Nash 학습 상대 봇 (4단 착수)

> **상태: 착수 (2026-07-14, 사다리 1~3단 통과 후 저자 승인). 1단계 = 확률 행렬 사전계산 (`precompute_matrices.py`).**
> `poker-pokerkit-prev/`(Q-학습 본 실험)와 격리된 별도 트랙 (저자 지시).

## 성능 판정 기준 (사전 고정 — 저자 승인 2026-07-14: "약하면 해상도 업" 반복 개선)

다이얼 2개를 구분한다 — 증상에 따라 돌릴 다이얼이 다르다:

| 증상 | 판정 지표 | 다이얼 |
|---|---|---|
| 덜 수렴 | 추상 게임 내 exploitability > **5 mbb/g** (Tammelin 실험 목표치 준용) | 반복 수 증가 |
| 추상화 거침 | 수렴 후에도 ① 페르소나 5종 중 적자 존재 또는 ② vs Slumbot < **−1831**(tabular 최고치) | 해상도 업: 카드 K 50→150 먼저(저렴), 그다음 메뉴 |

**해상도 반복은 5단 착수 전 종료·봇 동결** — 5단 도중 상대 변경 금지(단일변수).

## 목적

**near-Nash 학습 상대 제작** — 경쟁 봇 아님. 원척도 재현(리밋 홀덤 풀기, ~900 CPU-년)은 목표가 아니다.
용처: ① "약한 상대로만 학습" 공격 해소, ② VIC on/off를 균형 상대 학습·ID 평가로 재검증
(Δ>0이면 C1·C2 반격, Δ≈0이면 "이득의 필요조건 = 상대의 착취 가능성" 경계 확정 — 어느 쪽이든 가치).

## 알고리즘

**CFR+** (Tammelin 2014, arXiv:1407.5042): regret matching+ (음수 후회 절단) · 교대 갱신 · 가중 평균 전략.
원형 전수 순회 — 샘플링 없음 (트리를 아래 추상화로 충분히 작게 만든다).

## 추상화 설계 (실험일지 35절 (3) 고정)

| 축 | 출처 | 설계 |
|---|---|---|
| 카드 | Johanson et al. 2013 (AAMAS) | **프리플랍 169 무손실** + 포스트플랍 percentile E[HS] 버킷 — `poker-pokerkit-prev` 파일럿의 버킷 테이블 **재사용** (K는 사다리 판정 후 확정) |
| 기억 | 〃 | imperfect recall (현재 라운드 버킷만; 보장 약화 논문에 공개) |
| 행동 | Jackson 2013 (Slumbot NL) 축소판 | 등급 메뉴: 첫 벳 {0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4}×팟 (= **A12 Q봇 레이즈 8종 전체 포함**) → 레이즈 {0.5, 1, 2} → 3-벳 이후 {1}만 + **올인 상시 허용** |
| 번역 | Ganzfried & Sandholm 2013 | pseudo-harmonic 확률 배분. **Q봇 크기가 첫 벳 메뉴에 전부 포함되므로 발동 최소화** (레이즈 깊이의 메뉴 축소 지점에서만 예외) |

트리 규모 목표: 베팅 시퀀스 ~10⁴~10⁵ × 버킷 → 정보집합 ~10⁶ (메모리 수십~수백 MB, 워크스테이션 수 시간~수일 수렴).
트리 설계 확정 시 노드 수 실측으로 이 추정을 갱신할 것.

## 검증 체인 (자가 봇 공신력 — 순서 고정)

1. **Kuhn poker** — 해석적 내쉬해와 수렴 정확성 정답 대조
2. **Leduc hold'em** — 문헌 exploitability 수렴 곡선 대조 (CFR 대비 CFR+ 가속 재현)
3. **추상 HUNL** — 추상화 내 exploitability 측정 (CFR+의 계산 가능 이점)
4. **Slumbot 교차 대국** — 외부 앵커 (`poker-pokerkit-prev/slumbot_eval.py` 어댑터 재사용, 세션 2k 로테이션)

## 실험 설계 (사전 못박음)

- 학습: Q-학습자(VIC on/off)를 **동결된 CFR+ 봇** 상대로 학습 — 단일변수: 상대만 교체 (사다리 4단)
- 평가: **학습 상대 = 평가 상대 (ID)** — 일반화 주장 없음, 균형 상대에 대한 학습 품질 차이만 분리.
  기존 페르소나 홀드아웃 평가 병행 (상대 스펙트럼 지도 연속성)
- 표기 주의: "내쉬 균형 상대" 금지 — **"균형 근사(near-equilibrium) 상대"** (노리밋은 헤즈업도 미해결)

## 참고 문헌 (원문 PDF 대조 완료 2026-07-07)

- Tammelin 2014, *Solving Large Imperfect Information Games Using CFR+* (arXiv:1407.5042)
- Zinkevich et al. 2007, *Regret Minimization in Games with Incomplete Information* (NIPS) — CFR 원조
- Johanson et al. 2013, *Evaluating State-Space Abstractions in Extensive-Form Games* (AAMAS) — 카드 축
- Jackson 2013, *Slumbot NL* (AAAI-13 워크숍) — 행동 축 (등급 메뉴 11→8→3→1 + 올인)
- Ganzfried & Sandholm 2013, *Action Translation* (IJCAI) — pseudo-harmonic
- Waugh et al. 2009, *Abstraction Pathologies in Extensive Games* — 방어 인용 (해상도 ≠ 단조 개선)
- Lisý & Bowling 2017 — 추상화 봇 착취 가능성 (Slumbot도 근사임의 근거)
