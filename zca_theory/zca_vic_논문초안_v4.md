<!--
논문 초안 v4 (2026-08-21) — 지도 컨펌 반영판. v3.2 보존(본 판의 원본).
반영(컨펌 12항 + 결정 B 확정, 논문개정안_v3.2.md "지도 컨펌 반영 계획" 참조):
  1  본문 인라인 기호 전량 풀기(—, →, =, ①, (1)) — 별행 수식의 =와 수식 번호 ···· (N)은 유지(항목 10과 정합 해석)
  4·5·6  표 내용 영어화 + 표 제목 국문·영문 병기 + 본문 "표 N은 …" 설명문 + 표 각주(¹²³*)를 본문 서술로 이동
  7  본문 굵게 전량 해제(표 안 강조만 유지)
  9  5장 재편: I. Introduction / II. Related Works / III. The Proposed Method: Threshold Virtual Cost
     / IV. Experimental Results / V. Conclusions and Discussion (장 제목 영문 = 대상지 관행, 코퍼스 8편 중 7편)
  10 수식 별행 + ···· (N) 번호 + 파라미터 설명 문장 (수식 1~6)
  11 서론 동기 보강(잠복 결함의 실용 위험) + 말미 장 구성 안내
  12 관련 연구 3소절(2.1 문제 진단 계보 / 2.2 기여도 배분 해법 / 2.3 인접 수정 기법과 위치)
  13 재현성 환경 절 신설(3.3 — HW·SW·환경·평가·seed)
  14 부정적 결과(4.8)와 한계(4.9) 소절 분리
  15 "향후 연구." 표제 서술화("향후 연구로는 …")
  17(결정 B, 저자 확정 2026-08-21) 병리→현상/문제(국문 전면; 영문 Abstract의 pathology는 영어권 통용어라 유지),
     처방→해법/대안(명사)·해소/적용(동사), 개입→수정/가상비용(구체어), 실패 모드→문제(원어 병기 1회),
     진단·순위 왜곡·해소 유지 — 국내 용례 조사(개정안 결정 B 항) 근거
  18 대상지(JKSCI) 인용 2건 추가: [25] 다중 리플레이 심층 Q-학습(30권 9호, 2025), [26] QPLEX/PER 군집 드론(29권 11호, 2024)
미반영(저자·교수 유예): 그림 2종·docx(컨펌 2·3), 제목 형식(컨펌 8), DQN·PPO 비교(컨펌 16 — 결정 A 대기)
★저자 결정 대기(v3.2에서 승계): 개정 6 최소안 적용 중(V장 1문장) / 개정 8 VIC 약어 유지 / 개정 4 미적용(폴드 침묵 유지)
검증 반영(2026-08-21, 4-에이전트: 컨펌 12항/수치 무결성/교차참조/어법): E 2건([14] 미인용 → I장 인용 부착,
  표 2 60칩 "toward overdose" 판정이 본문 seed 요동 판단과 모순 → Effective로) + W 15건(캡션 영문부 국문 혼입 3표,
  요약·기여문·4.6 주술 불일치 4건, "참값을 학습" 과대 진술 → "참값의 부호를 반영한 음수 값"(수식 5 정합),
  4종 홀드아웃 대 표 3 5행 → Random 참조 명시, 서론 무인용 확산 주장 → [24] 부착·수량어 완화, 기타 비문·% 누락 등) 전량 수정.
  잔여: 3.3절 CPU [모델명]·RAM [용량]은 저자 기입 필요.
수치 출처: 실험일지 31~33절, results/28_ablation_vic_2m_clean, results/30_vic_potfrac_*.
-->

# 비례배분 기여도의 영-기여 흡수(Zero-Credit Absorption)와 임계 가상비용에 의한 해소: tabular Monte-Carlo 헤즈업 홀덤 학습의 사례연구

Zero-Credit Absorption under Proportional Credit Assignment and Its Resolution by a Threshold Virtual Cost: A Case Study in Tabular Monte-Carlo Heads-up Hold'em Learning

저자: [저자명]¹  ·  소속: [소속]¹

---

## Abstract

In tabular Monte-Carlo (MC) control, assigning each action a share of the terminal payoff proportional to its invested chips (proportional credit assignment) is a reasonable variance-reduction choice, but it leaves a structural pathology for zero-cost actions (e.g., CHECK): their credit is exactly zero in every episode, pinning the MC fixed point at zero regardless of the true value. We name this Zero-Credit Absorption (ZCA) and treat it at three levels. At the level of theory, in a minimal toy MDP we prove the zero fixed point and the resulting bidirectional mis-ranking (overvaluing bad checks, which we call absorption, and undervaluing good checks, which we call masking), show that the pathology is a structural property of the whole family of contribution-proportional schemes (zero contribution implies zero credit) rather than of one particular formula, distinguish it from the transient absorption of optimistic initialization (it is permanent, and its fixed point differs from the true value), and derive the threshold virtual cost required to dissolve it. At the level of measurement, in a 2,048-cell heads-up hold'em agent the learned Q(CHECK) collapses exactly to zero (versus a spread of −73 to +120 chips under standard MC), and we show behaviorally that the policy consequence is an excessively passive policy that checks 65% of turn decisions. At the level of resolution, a one-chip cost fails to reproduce recovery, with its sign fluctuating across training seeds (mean −117 mbb/g, 2 of 6 positive, a transition zone), whereas a constant cost of five chips or more exceeds the threshold: the passive policy dissolves (65% small bets on the turn) and performance against the unseen opponent that exploited the pathology (a random policy) recovers across training seeds (from −318±123 to +1230±693 mbb/g with the constant five-chip cost, 0/6 to 5/5 positive; +1546±535 and 6/6 with a check-time pot fraction of 30%). The recovery reproduces under causally clean variants (a decision-time constant cost and a check-time pot fraction), ruling out hindsight-information and implementation-artifact explanations by controlled experiments. Finally, we honestly report that this is not generalization: with the cost fixed in advance, gains against four held-out opponents are opponent-dependent (a slight loss against a calling station), and the effect is confined to single-opponent training.

▸Key words: reinforcement learning, Monte-Carlo control, credit assignment, reward shaping, zero-credit absorption, fixed point, tabular Q-learning, heads-up no-limit hold'em

## 요 약

표 기반 Monte-Carlo(MC) 제어에서 말단 보상을 각 행동에 그 행동의 투자액 비율로 배분하는 비례배분(proportional) 기여도 정형화는 분산을 줄이는 합리적 선택이지만, 비용 0 행동(예: CHECK)의 credit이 매 에피소드 정확히 0이 되어 가치 추정의 MC 고정점이 참값과 무관하게 0에 고정되는 구조적 문제, 곧 영-기여 흡수(Zero-Credit Absorption, ZCA)를 남긴다. 본 연구는 이를 세 층위에서 다룬다. 이론 층위에서는 최소 toy MDP에서 영-고정점과 그로 인한 양방향 순위 왜곡(참값이 음수인 체크의 과대평가인 흡수, 참값이 양수인 체크의 과소평가인 은폐)을 증명하고, 이 문제가 특정 배분식이 아니라 기여도 0인 행동에 credit 0을 주는 비례 배분 계열 전체의 구조적 성질임을 보이며, 낙관적 초기화(optimistic initialization)의 일시적 흡수와 질적으로 구별하고(영구적이며 고정점이 참값과 다름), 해소에 필요한 임계 가상비용을 유도한다. 실측 층위에서는 2,048-셀 헤즈업 홀덤 에이전트에서 Q(CHECK)가 정확히 0으로 붕괴함을 관측하고(표준 MC는 −73에서 +120칩까지 분포), 그 정책적 결과가 턴(제3 베팅 라운드) 결정의 65%를 체크하는 과도하게 소극적인 정책임을 행동 수준에서 보인다. 해소 실증 층위에서는 1칩 가상비용이 회복을 재현하지 못하고 학습 seed에 따라 부호가 요동하는 반면(6-seed 평균 −117 mbb/g, 양수 2/6, 전이구간), 임계를 넘는 상수 5칩 이상이면 소극적 정책이 풀리고(턴 소액 베팅 65%로 전환) 이 문제를 착취하던 미학습 상대(무작위 정책)에 대한 성능이 학습 seed 전반에서 회복됨을 보인다(가상비용 없음 −318±123에서 상수 5칩 +1230±693 mbb/g에 양수 5/5로; 체크시점 팟-비례 30%는 +1546±535에 양수 6/6). 회복은 결정시점 상수 비용과 체크시점 팟-비례 등 교란 요인이 통제된 변형에서 재현되어, 사후정보 가설과 구현 인공물 가설은 통제실험으로 배제되었다. 끝으로 이 효과가 일반화가 아님을 정직하게 보고한다. 사전 고정한 비용으로 4종 홀드아웃 상대에 대해 검증한 결과 이득은 상대 의존적이며(콜링스테이션 상대는 소폭 손해), 효과는 단일 상대 학습 구성에 한정된다.

▸주제어: 강화학습, Monte-Carlo 제어, 기여도 배분, 보상 형성, 영-기여 흡수, 고정점, tabular Q-learning, 헤즈업 노리밋 홀덤

---

## I. Introduction

강화학습은 게임을 넘어 실시간 광고 입찰[24], 에너지 스케줄링처럼 실물 자원을 집행하는 영역에 적용되고 있다. 이런 환경에서는 성과가 주기 말에 한 번 실현되는 경우가 있고, 그때 학습 신호는 성과를 궤적 위의 행동들에 나누어 귀속시키는 배분 설계를 거친다. 문제는 배분식의 결함이 겉으로 드러나지 않을 수 있다는 데 있다. 본 연구가 다루는 결함은 학습 분포 내 성능 지표를 정상으로 유지한 채 특정 행동 부류의 가치 추정만 왜곡하므로, 통상적인 학습 곡선 점검으로는 발견되지 않고 미학습 분포의 상대를 만나서야 손실로 나타난다. 자원을 실제로 집행하는 응용에서 이런 잠복 결함은 곧 손실 위험이다. 따라서 어떤 배분 설계가 어떤 조건에서 이런 결함을 만들고, 최소한의 수정으로 언제 해소되는지를 규명하는 일에는 실용적 요구가 있다.

이에 따라 본 연구의 대상은 특정 게임이 아니라, 구조적 기여도 배분이 남기는 측정 가능한 문제의 진단과 그 문제를 해소하는 최소 수정의 임계 조건 규명이다. 표 기반 강화학습은 함수근사의 블랙박스 효과 없이 학습 동역학을 단일변수로 통제하고 관찰할 수 있으므로, 검증 환경으로는 헤즈업 노리밋 홀덤의 순수 tabular Monte-Carlo 학습을 선택한다. 이 선택은 네 가지 성질 때문이다. 첫째, 비용 0 행동(CHECK)이 게임 규칙 자체에 내장되어 있어 인위적 삽입이 아니다. 둘째, 보상이 말단에서 크고 확률적으로 실현된다. 셋째, 팟 규모가 궤적마다 변해 고정 가상비용의 희석(3.2절)까지 시험된다. 넷째, 문제의 발현인 소극적 정책을 착취하는 상대를 두어 그 크기를 측정할 수 있다.

지연 보상(delayed reward)을 궤적 위의 어느 행동에 얼마나 귀속시킬 것인가 하는 기여도 배분(credit assignment; 국내 문헌에 따라 '신뢰할당'[20])은 강화학습의 오랜 난제로, 최근 전용 조사 연구가 나올 만큼 활발히 연구되고 있다[19]. Monte-Carlo 제어에서 이 배분 방식은 학습 신호의 분산과 편향을 좌우한다[14]. 표준 Monte-Carlo는 편향이 없지만 분산이 크고, 자연스러운 대안은 각 행동이 팟에 투입한 금액의 비율로 보상을 나누는 비례배분(proportional)이다. 행동 a의 credit은 다음과 같이 정의된다.

credit(a) = [inv(a) / Σ inv(a')] × P ···· (1)

수식 1은 한 에피소드(핸드)의 말단 보상을 행동별로 나누는 비례배분식이다. inv(a)는 행동 a가 팟에 투입한 칩(투자액)이고, 분모의 Σ inv(a')는 그 에피소드에서 에이전트가 투입한 총 칩이며, P는 에피소드 종료 시 실현되는 말단 보상(payoff)이다. 이 배분식 자체는 본 연구의 설계이나, '기여 0이면 배분 0'이라는 성질은 협력게임 이론의 null-player 공리[3]가 공정한 배분의 바람직한 성질(무임승차 방지)로 확립한 것과 형식적으로 동일하며, 3.1절의 Lemma 3은 이 문제가 설계의 세부가 아니라 그 성질을 만족하는 계열 전체의 구조임을 보인다. 비용 0 행동(투자액 0, 대표적으로 CHECK)은 수식 1의 분자가 0이므로 credit이 항상 0이고, 그 가치 추정의 고정점은 참값과 무관하게 0에 고정된다. 이 0은 행동 순위를 양방향으로 왜곡한다. 참값이 음수인 체크는 과대평가되어 학습된 음수 행동들을 greedy에서 가리고(흡수), 참값이 양수인 체크는 과소평가되어 열등한 양의 기댓값 행동에 밀린다(은폐).

본 논문의 기여는 세 가지다. 첫째(진단), 위 현상을 영-기여 흡수(ZCA)로 명명해 toy MDP에서 양방향 순위 왜곡으로 증명하고, 이것이 특정 배분식의 결함이 아니라 기여도-비례 배분 계열 전체의 구조적 성질(기여도 함수가 비용 0 행동에 0을 주는 모든 방식, Lemma 3)임을 보이며(3.1절), 실제 2,048-셀 에이전트에서 Q(CHECK)의 정확한 영-고정점과 그 정책적 결과(턴 결정의 65%를 체크하는 과도하게 소극적인 정책)를 측정한다(4.1절과 4.2절). 둘째(임계 이론과 실증), 비용 0 행동에 가상비용 ε을 부여하면 고정점이 참값 방향으로 풀림을 보이고, 해소에 필요한 임계를 유도하며(3.2절), 실제 시스템에서 1칩은 회복을 재현하지 못하고 부호가 seed에 따라 요동하며(전이구간), 임계를 충분히 넘는 상수 5칩 이상은 전 seed 유효함을 재현한다(4.3절). 이론이 예측한 임계의 존재가 하한의 급격한 전이로 확인된 사례다(임계의 위치까지 예측하는 것은 아니다. 4.9절 첫째 한계 참조. 임계 초과 후 상한은 확장 탐색에서도 검출되지 않았다). 아울러 동일 예산의 표준 MC와 3자 비교로 이 해법의 실용적 가치, 곧 저분산 배분을 보존한 채 문제만 제거함을 분리하고(4.4절), 탐색 강화·낙관적 초기화·일률 벌점의 세 대안이 전부 문제를 해소하지 못함을 통제 비교로 보인다(4.7절). 셋째(정직한 범위 규정), 이 회복이 "일반화"가 아니라 문제를 착취하던 상대에 대한 회복임을 사전 고정 비용의 홀드아웃 검증으로 보이고(콜링스테이션 상대는 소폭 손해), 평가 과정에서 발견하고 정정한 구현 인공물(credit 폴백 누수)과 단일 seed의 위험을 방법론적 부정적 결과로 보고한다(4.8절).

본 논문의 구성은 다음과 같다. II장에서는 관련 연구를 문제 진단 연구의 계보, 기여도 배분 해법, 인접 수정 기법의 세 갈래로 정리한다. III장에서는 toy MDP로 영-기여 흡수를 형식적으로 특성화하고 해소 임계를 유도하며 실험 환경을 명시한다. IV장에서는 실제 에이전트에서의 실측과 해소 실증, 방법론적 부정적 결과와 한계를 보고한다. V장에서는 결론을 맺고 향후 연구를 논의한다.

## II. Related Works

### 2.1 학습 알고리즘의 문제 진단 연구

기존 알고리즘의 문제를 명명하고 진단하는 연구는 강화학습에서 확립된 계보를 갖는다. Q-learning의 과대추정 편향 진단[15]은 Double Q-learning[16]이라는 해법으로 이어졌고, 최근에도 primacy bias[17]와 dormant neuron[18]처럼 문제 명명, 진단, 최소 해법으로 이어지는 형식이 반복된다. 본 연구는 같은 형식을 기여도 배분의 영-고정점에 적용한 것이다. 국내에서도 Q-learning 계열의 학습 효율과 안정성을 개선하는 연구가 이어지고 있다[25].

### 2.2 기여도 배분 해법 연구

기여도 배분을 직접 공략하는 해법 연구는 두 축으로 정리된다. 지연 보상을 어느 시점의 행동에 귀속시키는가 하는 시간축(재분배와 조사 연구[5][19])과, 공동 보상을 어느 에이전트에 귀속시키는가 하는 에이전트축(반사실적 기준선[2]과 가치 분해 계열)이다. 국내 문헌에서도 이 문제는 다중 에이전트 맥락의 '신뢰할당'으로 소개되고[20] 가치 분해 계열 해법의 적용 연구가 이어지고 있으나[21][26], 배분식 자체가 특정 행동 부류에 남기는 문제를 다루는 원저는 저자들이 조사한 범위에서 확인되지 않는다. 본 연구는 여러 방법 중 기여도-비례 계열의 배분식 자체가 발생시키는 문제(failure mode)를 다루며, 최신 조사 연구[19]의 분류에는 본 문제(비용 0 행동의 영-고정점)가 명명되어 있지 않다(해당 조사의 분류 체계 기준).

### 2.3 인접 수정 기법과 본 연구의 위치

ZCA를 이루는 구성 요소는 인접 문헌에 모두 존재하나, 본 연구는 그 부호를 뒤집어 같은 구조를 결함으로 진단한다. 협력게임 이론의 Shapley value[3]와 Shapley Q-value[4]는 null-player 공리(한계 기여 0이면 배분 0)를 공정성의 바람직한 성질로 둔다. 본 연구의 "비용 0이면 credit 0"은 기여 측도를 투자액으로 둘 때의 형식적 대응물이나 진단 방향이 반대다. 같은 직관은 difference rewards[1]와 COMA[2]에도 깔려 있다. RUDDER[5]는 return-equivalent 재분배가 최적 정책을 보존함을 보이는데, 비례배분은 비용 0 행동의 return을 참값과 무관한 상수 0으로 대체하므로 그 보존 정리의 적용 범위 밖이며, ZCA는 그 보장이 미치지 않는 영역에서 발생한다. 해소 측면에서 가상비용은 potential-based reward shaping(PBRS)이 Q-value 초기화와 등가[6][7]인 틀 안에 위치한다. 소극적 행동에 비용을 부과하는 임계 분석으로는 Lazy-MDP[22]가 있고(기본 정책 위임의 양측 임계 정리), 최근에는 삼진 채점의 기권-0 행동이 정책 기울기 학습을 붕괴시키는 법칙과 그 구조적 회피(훈련에서 기권을 제거하고 배포 시 임계 규칙 적용)가 보고되었다[23]. 본 연구의 구별점은 층위다. 설계된 보상 0이 아니라 비례배분 credit 산술이 파생시키는 0을 대상으로, 배분 방식을 보존한 채 학습 중 재가격의 임계를 편향된 MC 추정기의 학습 고정점에서 유도하고 실측으로 검증한다. 가장 가까운 action-penalty[8]는 모든 행동에 일률적이라 선택적이지 않다. 미방문 상태나 낙관적 초기화가 만드는 0의 일시적 흡수[9]는 초기화에 기인하므로, 비례 credit이 구조적으로 0을 재고정하는 본 연구와 기제가 다르다. 단일 seed의 오도 위험은 재현성 문헌[10][11][12]이 확립했으며, 본 연구는 모든 성능 주장을 6개 학습 seed에서 검증하고 단일 seed가 실제로 오도했던 사례를 4.8절에서 보고한다.

## III. The Proposed Method: Threshold Virtual Cost

### 3.1 영-기여 흡수의 형식적 특성화

문제 설정(toy MDP)은 다음과 같다. 결정 상태 s에서 행동 a₁을 한 번 선택한다. 각 행동 a₁은 0 이상의 투자액 inv(a₁)를 가지며, 비용 0 행동(CHECK)은 투자액이 0이다. 선택 후 궤적은 투자액 c(양수)인 후속 행동을 포함하고 말단 보상(terminal payoff) P로 끝난다(할인 없음). 행동 a₁의 참값을 다음과 같이 둔다.

μ(a₁) = E[P | a₁] ···· (2)

수식 2에서 E[P | a₁]는 행동 a₁을 선택했을 때 말단 보상 P의 조건부 기댓값이며, 이것이 참 가치 q\*(s, a₁)이다. 표 1은 배분 방식별로 행동 a₁에 귀속되는 return을 정리한 것이다.

표 1. 배분 방식별 행동 return (Table 1. Per-action return of each credit assignment method)

| Method | Return R(s, a₁) |
|---|---|
| Standard MC | P |
| Proportional (PROP) | [inv(a₁) / (inv(a₁) + c)] · P |
| Virtual cost (VIC) | Same as PROP, with inv(CHECK) replaced by ε > 0 |

Lemma 1 (표준 MC). 표준 MC의 추정치 Q_std(s, a₁)는 참값 μ(a₁)로 수렴한다.

Lemma 2 (영-고정점). 비례배분에서 CHECK의 추정치는 다음과 같다.

Q_prop(s, CHECK) = [0 / (0 + c)] · μ(CHECK) = 0 ···· (3)

수식 3은 μ(CHECK)의 값과 무관하게 성립한다. c는 궤적의 후속 투자액, μ(CHECK)는 체크의 참값이다. 이 0은 참값과 무관하고, return이 항상 0이라 표본 분산도 0인 구조적 고정점이다. 초기화의 잔재가 아니며, 방문할수록 0으로 다시 고정된다.

Lemma 3 (계열 일반화). 임의의 음이 아닌 기여도 함수 φ에 대해 다음 꼴의 비례 credit을 생각하자.

credit(a) = [φ(a) / Σ φ(a')] · P ···· (4)

수식 4에서 φ(a)는 행동 a의 기여도를 재는 임의의 함수이고, 분모는 궤적 내 총 기여도이다. 이 꼴의 배분은 φ(a)가 0인 행동에서 수식 3과 동일한 영-고정점을 갖는다. 즉 ZCA는 비용 0 행동의 기여도가 0인 것과 동치다. 투자액을 기여도로 쓰는 경우뿐 아니라 칩과 무관한 공격성 지표(베팅 여부의 1 또는 0)에서도 재현되고, 균등 기여(φ가 상수 1)와 표준 MC(return-equivalent)에서는 발생하지 않는다(수치 검증: `verify_toy_family.py`). 즉 ZCA는 본 연구가 채택한 특정 배분식의 결함이 아니라, null-player 공리(기여 0이면 배분 0)[3]를 가치 학습 신호로 쓰는 계열 전체의 구조적 취약점이다.

Theorem 1 (흡수: 나쁜 체크의 과대평가). 체크와 베팅의 참값이 모두 음수이고 체크가 더 나쁜 경우(μ_C < μ_B < 0), 비례배분 greedy는 Q_prop(CHECK)인 0이 [b/(b+c)]μ_B보다 크므로 열등한 CHECK를 선택한다. 표준 MC는 최적 행동인 BET을 선택한다. 여기서 b는 BET의 투자액이다.

Theorem 2 (은폐: 좋은 체크의 과소평가). 체크와 베팅의 참값이 모두 양수이고 체크가 더 좋은 경우(μ_C > μ_B > 0), 비례배분 greedy는 Q_prop(CHECK)인 0이 [b/(b+c)]μ_B보다 작으므로 최적 행동인 CHECK 대신 열등한 양의 기댓값 BET을 선택한다. 강한 핸드를 숨기는 트랩, 팟 크기를 억제하는 팟 컨트롤처럼 체크가 최적인 경로를 잃는다. 즉 ZCA는 특정 부호 조건의 문제가 아니라, CHECK의 참값이 0이 아닌 모든 결정 상태에서 나타나는 양방향 순위 왜곡이다.

Proposition 1 (낙관적 초기화와의 구분). 0-초기화가 만드는 0-선호는 충분한 방문 후 추정치가 참값으로 수렴하며 소거되는 일시적 현상이고 고정점은 참값이다(Lemma 1). 반면 수식 3의 0은 수렴 후에도 유지되는 고정점이며 참값과 다르다(Lemma 2). 낙관적 초기화의 0은 미학습에 기인한 일시적 선호이고, ZCA의 0은 구조적으로 학습이 불가능한 고정이다.

### 3.2 임계 가상비용의 유도

Proposition 2 (해소 임계). CHECK에 가상 투자 ε(양수)을 주면 고정점이 참값 방향으로 풀린다.

Q_vic(CHECK) = [ε / (ε + c)] · μ_C ···· (5)

수식 5에서 ε은 CHECK에 부여하는 가상 투자액, c는 후속 투자액, μ_C는 체크의 참값이다. 흡수와 은폐 두 모드 공통으로, greedy가 최적 행동을 선택할 필요충분조건은 ε이 다음 임계를 초과하는 것이다.

ε_min = k · c / (1 − k),  k = [b / (b + c)] · (μ_B / μ_C) ···· (6)

수식 6에서 b는 대안 행동(BET)의 투자액, μ_B는 그 참값이며, k는 0과 1 사이의 값이다(두 모드에서 동형이고 수치 검증이 일치한다). 임계 미달이면 Q_vic(CHECK)이 0 근방에 머물러 순위 왜곡이 잔존한다. 이 예측이 IV장에서 "1칩은 회복 재현 실패(부호 요동), 5칩 이상 전 seed 유효"로 확인된다. 팟 규모 c가 궤적마다 변하는 환경에서는 고정 소액 ε의 비중 ε/(ε+c)가 큰 팟에서 0에 가까워지므로(희석), 임계는 대표 팟 규모 기준으로 설정해야 한다(toy 검증: `verify_toy_stochastic_eps.py`). 나아가 결정 상태(셀)마다 팟 규모가 달라 임계도 셀마다 다르므로, 고정 ε이 일부 셀에서만 임계를 넘는 중간 크기에서는 부분적이고 seed 의존적인 회복(전이구간)이 예상된다. IV장에서 1칩이 정확히 이 양상을 보인다.

무정보 수정은 이 순위 왜곡을 풀지 못한다. 결정 시 노이즈는 고정점 0을 바꾸지 못하고, 동률 처리(tie-break)는 엄격한(strict) 부등식(0이 음수보다 큼)에서는 발동하지 않는다. 가상비용과 고정 벌점만 고정점을 옮기며, 가상비용의 고정점만 참값 μ_C에 연동된다(informed).

### 3.3 실험 환경 및 재현성

실제 환경의 상태 추상화는 라운드(프리플랍·플랍·턴·리버), 포지션, 핸드 버킷, 직전 행동의 곱으로 2,048개 결정 상태(셀)를 두고, 행동은 8개다. 탐색은 softmax(온도 감쇠), 학습량은 에피소드 200만, 학습 상대는 TAG(타이트-공격 규칙 기반 정책) 단일이다. 블라인드는 1칩과 2칩, 시작 스택은 200칩(100 빅블라인드)이며, 성능 단위는 mbb/g(1000분의 1 빅블라인드/게임, payoff에 500을 곱한 값)다. 평가는 게임 10만 회씩 5회(평가 seed 고정)를 greedy 정책으로 수행하고, 성능 주장은 학습 seed 6개(1부터 5까지, 그리고 42)에서 검증한다. 구현은 Python 3.13과 포커 게임 엔진 pokerkit[13]을 사용했고, Windows 11 데스크톱(CPU [모델명], RAM [용량])의 단일 CPU 코어에서 학습 1회(에피소드 200만)에 약 10분이 소요된다. 모든 학습은 4.8절에서 보고하는 credit 폴백 인공물을 제거한 코드로 수행했으며, 조건별 원자료(CSV)와 학습·평가 seed는 저장소에 보존하였다.

## IV. Experimental Results

### 4.1 영-고정점의 실측

표준 MC(PURE)로 학습하면 Q(CHECK)가 −72.9칩에서 +119.8칩까지 펼쳐지지만(평균 절댓값 4.48), 비례배분에서는 모든 셀에서 정확히 0이다(평균 0.00, 범위 [0, 0]). Lemma 2의 직접 관측이며 학습 seed와 표본에 무관한 구조적 사실이다. 이 불변식(비례배분에 가상비용이 없으면 Q(CHECK)는 정확히 0)은 자동 테스트로 저장소에 고정하였다.

### 4.2 영-고정점의 정책적 결과: 소극적 정책

영-고정점의 행동적 결과를 보기 위해 학습된 정책의 행동 분포를 측정하면(20k 게임), 가상비용 없는 정책은 턴 결정의 65%를 체크한다. 공격 행동의 Q가 0 근방(학습 부족)이거나 음수인 셀에서 CHECK의 0이 greedy를 차지하기 때문이다(Theorem 1의 실제 형태). 이 소극적 정책은 그것을 착취하는 상대에게 체계적으로 진다. 무작위 정책(미학습 상대) 대상 성능이 6개 학습 seed 전부에서 음수다(−318±123 mbb/g, 양수 0/6). 무작위 상대조차 이기지 못하는 것은 일반 성능의 문제가 아니라 구조적 문제의 증거다(단순 공격 규칙 기반 정책은 같은 상대에 +11705 mbb/g를 얻는다).

### 4.3 임계 실증: 1칩은 전이구간, 5칩 이상은 유효

가상비용의 크기만 단일변수로 바꿔 가며 무작위 상대 성능을 측정하였다. 표 2는 그 결과로, Proposition 2의 예측과 정합하게 하한에서 급격한 전이를 보이며, 임계를 충분히 넘는 조건에서만 성능이 전 seed에서 양수가 됨을 보여 준다. 임계 초과 후 상한은 관측되지 않았다. 후속 확장 탐색(팟-비례 800%와 상수 240칩까지)에서도 평균 성능 저하는 검출되지 않았으며(seed 5개, 검정력 한계), 60칩 조건의 평균 하락(+1659에서 +806으로)은 독립 재현 145회에서 재현되지 않아 seed 요동 범위로 판단한다.

표 2. 가상비용 크기별 무작위 상대 성능(단위 mbb/g, 학습 seed 5개에서 6개, 괄호는 양수 seed 비율) (Table 2. Performance against the random opponent by virtual-cost magnitude)

| Virtual cost on CHECK | Performance | Verdict |
|---|---|---|
| (Reference) Standard MC, no proportional credit | −312±91 (0/5) | No ZCA, but inferior on both metrics (Sec. 4.4) |
| None (ε = 0) | −318±123 (0/6) | Passive policy (baseline) |
| Constant 1 chip | −117±252 (2/6) | Transition zone: negative mean, sign fluctuation |
| **Constant 5 chips** | **+1230±693 (5/5)** | **Above threshold: effective** |
| Constant 20 chips | +1659±825 (5/5) | Effective |
| Constant 60 chips | +806±451 (5/5) | Effective |
| Check-time 30% of pot | +1546±535 (6/6) | Effective |
| Check-time 15% of pot or less | −276 to −94 (0 to 3/5) | Transition zone: unreliable |

표 2의 1칩 조건에 관해 두 가지를 명시한다. 첫째, 초기 단일 seed(42) 측정은 −376으로 "무효"를 시사했으나, 6-seed 확장에서 부호 요동(양수 2/6)이 드러났다. 단일 seed의 오도 위험(4.8절)의 추가 사례이며, 셀별 임계 이질성에 의한 전이구간 해석(3.2절)과 정합한다. 둘째, 후속 진단(표준 추상화 플랫폼의 비율 축)은 흡수가 전부 해소된 뒤에도 성능이 회복되지 않는 별도 경로(또 다른 비용 0 행동인 FOLD의 영-고정점)를 확인했으므로, 전이구간 해석에는 "흡수 해소 임계"와 "성능 회복 문턱"의 분리 가능성에 유의해야 한다(4.5절). 본 표의 셀별 임계 해석은 그 한도 내의 추정이다. 아울러 상수 20칩과 60칩의 5/5는 구코드 계열 기준이고, 독립 재현 계열(재작성 코드, 5-seed)에서는 각각 4/5(각 1개 seed 음수)였다.

핵심 대비는 Welch t 검정에서 모두 유의하다. 가상비용 없음 대 상수 5칩은 t 값 7.36, 가상비용 없음 대 체크시점 30%는 t 값 7.18, 일률 벌점 대 선택적 5칩은 t 값 7.97로, 모두 p < .001이다. 검정은 독립 재현 계열(5-seed, 재현 가능한 CSV 기준)에서 수행한 것으로, 본문 수치(구코드 계열의 5개에서 6개 seed)와 계열이 다름을 명시한다.

행동 수준에서 임계 초과 가상비용은 소극적 정책을 정확히 뒤집는다. 턴 결정의 65%를 체크하던 정책이 턴 소액 베팅 65%로 바뀌고, 승률은 51.8%에서 54.5%로, 승리 핸드 평균 수익은 +19.9칩에서 +25.3칩으로 오른다. 즉 Q(CHECK)가 참값의 부호를 반영한 음수 값을 학습하자(무작위 상대에게 턴 체크는 밸류 벳과 폴드 유도로 얻을 수익을 포기하는 선택이라 참값이 음수) greedy가 베팅으로 전환한 것이다. 회복이 결정시점 상수 비용(fixed-K)에서 재현되므로 사후정보(최종 팟 사용) 가설은 배제되고, 이론(결정시점 상수 ε)과 정확히 대응한다.

### 4.4 표준 MC와의 동일 예산 비교

"비례배분이 문제를 만드니 처음부터 표준 MC를 쓰면 된다"는 자연스러운 반박을 동일 조건 3자 비교로 검증하였다(single-TAG, 에피소드 200만, seed 5개). 표준 MC(PURE)는 vs TAG +115±25, vs 무작위 −312±91(양수 0/5)로 양 지표 모두 열세다. 비례배분에 임계 비용을 더한 조건(+909 / +1230에서 +1546)에 비해 크게 낮다. 학습 곡선은 그 원인이 학습 속도가 아니라 안정성임을 보여준다. 표준 MC는 학습 중반까지 비례배분과 대등한 성능(vs TAG 약 +900)을 보이다가 탐색 온도가 낮아지는 후반(약 140만 에피소드)에 붕괴한다(고분산 MC의 알려진 불안정). 비례배분 계열은 가상비용 유무와 무관하게 붕괴하지 않는다. 즉 비례배분은 저분산으로 후반 안정성을 얻는 대신 ZCA를 남기며, 임계 가상비용이 그 문제만 해소한다. 세 방식 중 "문제 없이 강하게 배우는" 조합은 비례배분에 임계 비용을 더한 것뿐이다.

### 4.5 임계의 두 층: 흡수 해소와 성능 회복

본 연구의 임계 조건이 직접 지배하는 것은 흡수의 해소, 곧 greedy가 가짜 0에 고정된 행동 대신 최적 행동을 선택하게 되는 것이다. 후속 진단(표준 추상화 플랫폼)에서 흡수가 전부 해소된 뒤에도 성능이 회복되지 않는 사례가 확인되었는데, 그 원인은 동일 배분식 안의 또 다른 비용 0 행동(FOLD)의 영-고정점이었다. Lemma 2의 설정이 예측하는 두 번째 사례이며, 성능 회복은 흡수 해소에 더해 이 잔여 문제와 학습 분포 요인이 함께 결정한다. 따라서 본 장의 용량-반응(dose-response)은 "흡수 해소 임계"의 실증으로 읽어야 하며, 성능 회복 문턱과의 분리 가능성은 4.9절 한계에 명기한다.

### 4.6 홀드아웃 상대 검증: 일반화가 아닌 선택적 회복

비용을 사전에 고정하고(체크시점 팟 30%) 학습에 쓰지 않은 4종 상대로 검증하였다(문제를 착취하던 무작위 상대는 참조로 표 3에 함께 제시한다). 표 3은 홀드아웃 상대별로 가상비용 부여 전후의 성능 변화량을 정리한 것으로, 이득은 상대 의존적이다.

표 3. 홀드아웃 상대별 성능 변화량(Δ는 가상비용 없는 조건 대비, 단위 mbb/g, 학습 seed 5개에서 6개 평균) (Table 3. Performance change per held-out opponent)

| Held-out opponent | Δ | Improved seeds |
|---|---|---|
| Random (exploits the passive policy) | +1864 | 6/6 |
| LAG (loose-aggressive) | +73 | 3/5 |
| Maniac (hyper-aggressive) | +307 | 3/5 |
| Nit (ultra-tight) | +16 | 5/5 |
| **Station (calling station)** | **−177** | **0/5** |

콜링스테이션 상대의 절대 성능은 가상비용 유무와 무관하게 모든 조건에서 큰 폭의 적자이며(독립 재현 계열의 원값으로 −2600에서 −3200 mbb/g, 용량 무관), 이는 가상비용이 건드리지 못하는 별도 요인(과공격)에 기인한다. 향후 과제로 남긴다.

소극적 정책의 해소는 플레이 성향 변화(공격성 증가)이므로, 공격이 유효한 상대(무작위: 큰 회복)와 유효하지 않은 상대(콜링스테이션: 베팅에 폴드하지 않으므로 소폭 손해)에서 손익이 갈린다. 따라서 본 효과의 정확한 서술은 "분포 외 일반화"가 아니라 "영-고정점이 만든 소극적 정책의 해소, 곧 그 문제를 착취하던 상대에 대한 회복"이다. 또한 효과는 단일 상대(TAG) 학습에 한정된다. 5종 상대 순환·혼합 학습에서는 같은 가상비용으로 무작위 상대 성능이 회복되지 않았다(−112와 −159). 학습 분포 내 성능(vs TAG)은 모든 조건에서 +849에서 +952 사이로 보존된다.

### 4.7 세 가지 대안과의 통제 비교

3.2절의 이론적 기각(무정보 수정은 고정점의 순위를 바꾸지 못함)을 동일 조건 통제 비교로 실증하였다(대안별 학습 seed 5개, 나머지 설정은 3.3절과 동일). 비교 대상은 ZCA에 대해 제안될 법한 세 대안이다. 첫째는 탐색 강화로, softmax 온도 하한을 2.0으로 둔다. 둘째는 낙관적 초기화로, 전 셀의 초깃값을 +50으로 둔다(Proposition 1의 검증). 셋째는 일률 가산 벌점으로, 전 행동의 credit에서 5칩을 차감한다(action-penalty[8]류의 비선택적 비용). 표 4는 세 대안과 선택적 가상비용의 결과를 정리한 것이다.

표 4. 세 대안과의 통제 비교(단위 mbb/g, 학습 seed 5개에서 6개) (Table 4. Controlled comparison with three alternative remedies)

| Method | vs Random | Positive seeds | vs TAG |
|---|---|---|---|
| None (baseline) | −318±123 | 0/6 | +866 |
| Exploration boost (softmax temperature at least 2.0) | −291±267 | 1/5 | +880±25 (preserved) |
| Optimistic initialization (initial Q of 50) | −241±302 | 1/5 | +184±43 (degraded) |
| Uniform penalty (5 chips off every action) | −485±32 | 0/5 | +119±34 (degraded) |
| **Selective virtual cost (CHECK only, 5 chips)** | **+1230±693** | **5/5** | **+909±50 (preserved)** |

표 4의 선택적 가상비용에 5칩을 쓴 것은 두 기준에 따른다. 일률 벌점과 크기를 일치시켜 선택성만을 분리하는 값이면서, 임계를 넘는 최소 유효 용량이라는 보수적 대푯값이다. 더 높은 수치의 조건(체크시점 팟 30%는 +1546±535에 6/6, 상수 20칩은 +1659±825에 5/5)으로 바꿔도 결론은 불변하며, 조건 간 순위는 표준편차 중첩 때문에 주장하지 않는다(표 2).

첫째 대안(탐색 강화)은 예측대로 무효다. 방문이 늘수록 0으로 다시 고정되므로 탐색량은 고정점을 바꾸지 못한다(학습 분포 내 성능은 보존). 둘째 대안(낙관적 초기화)은 회복 실패에 더해 학습 분포 내 성능까지 훼손했다. 낙관적 초깃값이 전 셀에서 소거되는 데 학습 예산이 소모된다(Proposition 1의 일시성이 유한 예산에서는 비용이 됨). 셋째 대안(일률 벌점)은 이론 예측(순위 불변이므로 기준선과 동일)보다 나빴다. 고정점의 순위는 불변이나, 방문한 셀의 Q만 벌점이 5칩 내려 미방문 셀의 0 초깃값과 상대 격차를 만들고(의도치 않은 상대적 낙관 초기화), 유한 예산 학습을 양 지표 모두에서 훼손했다. 이 예측 편차 자체를 부정적 결과로 함께 보고한다. 다섯 조건 중 양 지표를 지키며 문제를 해소한 것은 선택적 임계 가상비용뿐이며, 특히 셋째 대안과의 대비는 이 해법의 본질이 비용 부여 일반이 아니라 비용 0 행동에 대한 선택성임을 분리 실증한다.

### 4.8 방법론적 부정적 결과: credit 폴백 인공물의 발견과 정정

초기 구현은 총투자 0인 핸드(전부 체크 또는 폴드)에서 비례배분이 미정의라 균등 배분(payoff/n)으로 폴백했고, 이 누수가 비용 0 행동에 비(非)비례 credit을 흘렸다. 단일 학습 seed(42)와 결합해 "1칩 가상비용이 분포 외 일반화의 필요조건"이라는 허위 신호를 만들었으며, 폴백 격리 실행(원본 수치 완전 재현)과 제거 재실행(효과 소멸)으로 인공물임을 확정하고 폐기하였다. 단일 seed의 오도 위험을 경고한 재현성 문헌[10][11][12]과 정합하는 사례다. 본 논문의 모든 수치는 폴백 제거 후의 것이며, 나아가 가상비용을 실투자 핸드에만 적용하는 격리 실험으로 4.3절과 4.6절의 회복이 폴백 유사 신호가 아니라 CHECK credit 경로임을 확인했다(실투자-한정 +1245에 5/5로, 전체 적용 +1546과 근사; 폴백-신호-한정은 +206에 고분산). 아울러 결론을 지탱하는 핵심 실험들은 독립 재작성 코드로 145회 재현되어 주요 조건별 기준 수치가 전부 유지되었다(상수 20칩과 60칩은 5/5에서 독립 재현 계열 4/5로의 경계 편차, seed 요동 범위).

### 4.9 연구의 한계

본 연구의 한계는 네 가지다. 첫째, 임계의 정확한 위치는 미확정이다. 전이구간(팟-비례 8%에서 15%, 상수 1칩 부근)은 seed 요동이 크며(1칩의 6-seed 평균 −117에 양수 2/6), 본 연구는 "충분 초과 시 전 seed 유효"라는 임계의 존재만 주장한다. 아울러 이 임계는 흡수 해소의 임계이며, 성능 회복 문턱과는 분리될 수 있다(4.5절). 둘째, 효과의 범위는 단일 상대 학습, 단일 게임(헤즈업 노리밋 홀덤), 단일 추상화에 한정된다. 셋째, 홀드아웃 상대도 자체 제작 규칙 기반 정책이다. 외부의 균형 상대 검증은 이후 수행되었다. CFR+ 동결 전략(추상 내 착취가능성 3.91 mbb/g)을 학습 상대로 한 후속 실험에서, 가상비용을 적용해도 균형 상대 자체에 대한 성능은 전 조건 음수였으나(표 기반 표현력의 이론적 한계로 균형 상대 기댓값의 상한이 0 근방), 무작위 상대 홀드아웃에서의 선택적 회복은 재현되었다(부정적 결과 포함). 넷째, ZCA의 구성 요소(null-player 공리, return-equivalence, 낙관적 초기화, PBRS와 Q-초기화의 등가성)는 이미 알려진 것이며, 기여는 이들을 구조적 문제로 재진단하고 임계를 유도·실증하며 범위를 정직히 규정한 데 있다.

## V. Conclusions and Discussion

비례배분 기여도는 비용 0 행동에 구조적 영-고정점(ZCA)을 남기고, 이는 행동 순위를 양방향으로 왜곡하며(흡수와 은폐), 낙관적 초기화의 일시적 0-선호와 달리 방문으로 해소되지 않는다. 이상을 toy MDP에서 증명하고, 실제 2,048-셀 에이전트에서 Q(CHECK)의 정확한 0 붕괴와 그 결과인 과도하게 소극적인 정책(턴 체크 65%)으로 실측하였다. 유도한 임계 조건의 예측은 비대칭 용량-반응으로 확인되었다. 하한은 급격한 전이를 보였고, 임계 초과 후 상한은 검출되지 않았다. 가상비용이 없으면 전 seed 음수(0/6), 1칩은 부호가 요동하는 전이구간(2/6), 상수 5칩 이상이면 소극적 정책이 풀리고(턴 소액 베팅 65%로 전환) 문제를 착취하던 미학습 상대에 대한 성능이 학습 seed 전반에서 회복된다(5/5와 6/6 양수). 확인된 것은 임계의 존재이며 위치의 예측이 아니다(4.9절). 사후정보 가설, 구현 인공물 가설, 평가 순환성 가설은 각각 결정시점 상수 비용, 격리 실험, 사전 고정 홀드아웃으로 배제하였고, "표준 MC를 쓰면 된다"는 대안은 동일 예산 3자 비교(양 지표 열세)로 기각하였다. 동시에 이 회복이 일반화가 아니라 상대 의존적 플레이 성향 변화임을, 콜링스테이션 상대의 소폭 손해까지 포함해 정직하게 보고하였다. 본 사례연구의 가치는 구조적 기여도 배분의 문제를 증명하고 측정하며, 해법의 작동 조건(임계)을 이론과 실험의 대응으로 규명하고, 그 한계를 부정적 결과와 함께 드러낸 데 있다.

향후 연구로는 도메인 이동 검증을 계획한다. 임계의 하한 조건은 후속 연구 프로그램에서 유도와 사전 등록으로 검증되었다(칩 축에서 5칩 초과 8칩 이하 구간 적중; 팟-비례 축은 정적 유도가 기각되어 유효 범위가 칩 축에 한정됨을 함께 보고한다). ZCA의 발생 조건은 게임 특수적이지 않다. 성과가 말단에 한 번 실현되고, 행동이 성과와 같은 단위의 자원 투입이며, 투입 0 행동이 존재하는 순차 결정 환경에서 말단 귀속(배분) 정식화를 채택하면, 계열 정리(Lemma 3)가 동일 문제의 발생을 예측한다. 문제의 소재는 도메인이 아니라 이 정식화의 채택에 있다. 같은 도메인이라도 순차 동적계획 정식화(예: 실시간 입찰에서 무입찰을 행동에 포함한 가치 계산[24])에서는 발생하지 않는다. 이 조건은 예컨대 실시간 광고 입찰의 예산 집행(무입찰 행동의 투입 0, 주기 말 성과의 지출-비례 귀속이며 사후 귀속(attribution)이 실무 관행으로 실재함), V2G 충·방전 스케줄링(대기 행동의 투입 0, 청구 주기 말 요금), 에너지 하베스팅 IoT 전송 스케줄링(sleep 행동의 투입 0, 보고 주기 말 효용)에서 성립한다. 후속 연구는 지출-비례 귀속을 쓰는 광고 입찰 환경에서의 재현과 임계 사전 계산을 첫 순위로 진행한다.

---

## 참고문헌

[1] D. H. Wolpert and K. Tumer, "Optimal payoff functions for members of collectives," Advances in Complex Systems, Vol. 4, No. 2/3, pp. 265-279, 2001.

[2] J. Foerster, G. Farquhar, T. Afouras, N. Nardelli, and S. Whiteson, "Counterfactual multi-agent policy gradients," Proc. AAAI Conf. on Artificial Intelligence, pp. 2974-2982, 2018.

[3] L. S. Shapley, "A value for n-person games," Contributions to the Theory of Games II, Princeton Univ. Press, pp. 307-317, 1953.

[4] J. Wang, Y. Zhang, T.-K. Kim, and Y. Gu, "Shapley Q-value: A local reward approach to solve global reward games," Proc. AAAI Conf. on Artificial Intelligence, pp. 7285-7292, 2020.

[5] J. A. Arjona-Medina, M. Gillhofer, M. Widrich, T. Unterthiner, J. Brandstetter, and S. Hochreiter, "RUDDER: Return decomposition for delayed rewards," Advances in Neural Information Processing Systems, pp. 13544-13555, 2019.

[6] A. Y. Ng, D. Harada, and S. Russell, "Policy invariance under reward transformations: Theory and application to reward shaping," Proc. Int. Conf. on Machine Learning, pp. 278-287, 1999.

[7] E. Wiewiora, "Potential-based shaping and Q-value initialization are equivalent," Journal of Artificial Intelligence Research, Vol. 19, pp. 205-208, 2003.

[8] S. Koenig and R. G. Simmons, "The effect of representation and knowledge on goal-directed exploration with reinforcement-learning algorithms," Machine Learning, Vol. 22, pp. 227-250, 1996.

[9] T. Rashid, B. Peng, W. Boehmer, and S. Whiteson, "Optimistic exploration even with a pessimistic initialisation," Proc. Int. Conf. on Learning Representations, 2020.

[10] P. Henderson, R. Islam, P. Bachman, J. Pineau, D. Precup, and D. Meger, "Deep reinforcement learning that matters," Proc. AAAI Conf. on Artificial Intelligence, pp. 3207-3214, 2018.

[11] C. Colas, O. Sigaud, and P.-Y. Oudeyer, "How many random seeds? Statistical power analysis in deep reinforcement learning experiments," arXiv:1806.08295, 2018.

[12] R. Agarwal, M. Schwarzer, P. S. Castro, A. C. Courville, and M. G. Bellemare, "Deep reinforcement learning at the edge of the statistical precipice," Advances in Neural Information Processing Systems, pp. 29304-29320, 2021.

[13] J. Kim, "PokerKit: A comprehensive Python library for fine-grained multi-variant poker game simulations," IEEE Trans. on Games, 2023.

[14] R. S. Sutton and A. G. Barto, Reinforcement Learning: An Introduction, 2nd ed., MIT Press, 2018.

[15] S. Thrun and A. Schwartz, "Issues in using function approximation for reinforcement learning," Proc. of the 1993 Connectionist Models Summer School, pp. 255-263, 1993.

[16] H. van Hasselt, "Double Q-learning," Advances in Neural Information Processing Systems, pp. 2613-2621, 2010.

[17] E. Nikishin, M. Schwarzer, P. D'Oro, P.-L. Bacon, and A. Courville, "The primacy bias in deep reinforcement learning," Proc. Int. Conf. on Machine Learning, pp. 16828-16847, 2022.

[18] G. Sokar, R. Agarwal, P. S. Castro, and U. Evci, "The dormant neuron phenomenon in deep reinforcement learning," Proc. Int. Conf. on Machine Learning, pp. 32145-32168, 2023.

[19] E. Pignatelli, J. Ferret, M. Geist, T. Mesnard, H. van Hasselt, and L. Toni, "A survey of temporal credit assignment in deep reinforcement learning," arXiv:2312.01072, 2023.

[20] 유병현, 데브라니 데비, 김현우, 송화전, 박경문, 이성원, "멀티 에이전트 강화학습 기술 동향," 전자통신동향분석, 제35권 제6호, pp. 137-149, 2020.

[21] 김민경, "Ray RLlib 기반 QMIX와 RND를 이용한 희소 보상 전장 환경에서의 멀티에이전트 강화학습 협업," 한국컴퓨터정보학회논문지, 제29권 제1호, pp. 11-19, 2024.

[22] A. Jacq, J. Ferret, O. Pietquin, and M. Geist, "Lazy-MDPs: Towards interpretable reinforcement learning by learning when to act," Proc. Int. Conf. on Autonomous Agents and Multiagent Systems, 2022 (arXiv:2203.08542).

[23] X. Che, Y. Yuan, W. Zhao, and C. Yu, "Abstention as an action can kill both the reward gradient and the KL anchor: Collapse law and repair for error-penalized reinforcement learning," arXiv:2608.00301, 2026.

[24] H. Cai, K. Ren, W. Zhang, K. Malialis, J. Wang, Y. Yu, and D. Guo, "Real-time bidding by reinforcement learning in display advertising," Proc. 10th ACM Int. Conf. on Web Search and Data Mining (WSDM), pp. 661-670, 2017.

[25] J. Hwang, "Enhanced deep Q-learning with multiple replay memories: A heuristic-based approach," Journal of The Korea Society of Computer and Information, Vol. 30, No. 9, pp. 1-10, 2025.

[26] J.-H. Ahn, B.-I. Choi, T.-Y. Lee, H.-M. Kim, and H.-H. Kim, "Multi-agent reinforcement learning based swarm drone using QPLEX and PER," Journal of The Korea Society of Computer and Information, Vol. 29, No. 11, pp. 79-88, 2024.

---

## 저자소개

[저자명] (Author Name): [소속/직위]. E-mail: [e-mail]. 관심분야: 강화학습, 게임 AI, 학습 동역학 분석.

<!-- 증명: toy_zca_proof.md(구 명명 Theorem′ = 본고 Theorem 2) · 검증: verify_toy_{zca,mirror,stochastic_eps,family,breakers}.py
     데이터: ../results/28_ablation_vic_2m_clean, ../results/30_vic_potfrac_{2m,seedsweep} · 경위: ../실험일지.md 31~33절 -->
