<!--
2차 논문 초안 (v2) — 재작성본. v1(zca_vic_논문초안.md) 레거시 보존.
축(저자 의도): ZCA 진단(증명+실측 Q(CHECK)=0) + VIC=고정점을 깨는 최소 개입(0→0.11, 흡수 방향 감소).
  충분한 임계비용은 후속 과제. OOD 일반화·"필요조건"은 본문 주장 아님 → §VI 한계(누수 인공물·seed 취약).
수치 검증: analyze_qcheck.py 직접 측정 + clean 재현런(results/28_ablation_vic_2m_clean) + 누수 격리(LEAKON).
어휘: 참값·기댓값·낙관적 초기화·부정적 결과(KCI). 포커 hand="핸드".
-->

# 비례배분 기여도 하의 영-기여 흡수(Zero-Credit Absorption): 형식적 진단과 고정점을 깨는 최소 가상비용
## — tabular Monte-Carlo 헤즈업 홀덤 학습의 사례연구

**Zero-Credit Absorption under Proportional Credit Assignment: A Formal Diagnosis and a Minimal Virtual Cost that Breaks the Fixed Point — A Case Study in Tabular Monte-Carlo Heads-up Hold'em**

저자: [저자명]¹  ·  소속: [소속]¹

---

## 국문 요약

표 기반 Monte-Carlo(MC) 제어로 헤즈업 노리밋 홀덤을 학습할 때, 각 행동의 보상을 그 행동의 투자액 비율로 배분하는 **비례배분(proportional) 기여도 정형화**는 분산을 줄이는 합리적 선택이다. 본 연구는 이 방식이 **비용 0 행동**(예: CHECK)에 구조적 병리를 남김을 증명하고 실측한다. 비용 0 행동의 비례 credit은 매 에피소드 정확히 0이므로 그 MC 고정점은 행동의 참값과 무관하게 0에 고정되고, 모든 가용 행동이 음(−)의 기댓값인 결정점에서 이 0은 열등한 비용 0 행동을 greedy 정책이 영구히 선택하게 만든다. 우리는 이를 **영-기여 흡수(Zero-Credit Absorption, ZCA)**로 명명하고 최소 toy MDP에서 증명하며, 이것이 낙관적 초기화의 *일시적* 흡수와 질적으로 구별됨(영구적·고정점≠참값)을 보인다. 실측에서, 2,048-셀 tabular 봇의 Q(CHECK)는 표준 MC가 −73~+120칩으로 펼쳐지는 데 반해 비례배분에서는 정확히 0에 붕괴(평균 |Q(CHECK)| 4.48 → 0.00)하여 영-고정점이 직접 관측된다. 처방으로, 비용 0 행동에 무시 가능한 **가상비용(Virtual Information Cost, VIC)**을 부여하면 그 고정점이 깨져 Q(CHECK)가 0에서 떨어지고(0.00 → 0.11–0.15) CHECK가 공격 행동을 흡수하는 비율이 감소한다. 다만 1칩 가상비용은 본문에서 유도한 임계 ε_min에 미달하여 효과가 부분적(약 4–6%p)이며, **충분한 임계비용 설정은 후속 과제**다. 끝으로, 평가 과정에서 발견한 credit-배분 구현 인공물(전부-0투자 에피소드의 균등분배)과 그것이 단일 학습 seed와 결합해 만든 허위 일반화 신호를 *방법론적 부정적 결과*로 정직하게 보고한다.

**주제어:** 강화학습, Monte-Carlo 제어, 기여도 배분, 보상 형성, 영-기여 흡수, 고정점, tabular Q-learning, 헤즈업 노리밋 홀덤

## Abstract

In tabular Monte-Carlo (MC) control for heads-up no-limit Texas hold'em, assigning each action a share of the terminal payoff proportional to its invested chips—proportional credit assignment—is a reasonable variance-reduction choice. We prove and measure a structural pathology it leaves for zero-cost actions (e.g., CHECK): their proportional credit is exactly zero every episode, so the MC fixed point is pinned to zero regardless of true value, and where all actions have negative expected value this zero makes a greedy policy permanently select the inferior zero-cost action. We name this Zero-Credit Absorption (ZCA), prove it in a minimal toy MDP, and show it is distinct from the transient absorption of optimistic initialization (permanent; fixed point ≠ true value). Empirically, in a 2,048-cell agent the learned Q(CHECK) spans −73 to +120 chips under standard MC but collapses exactly to zero under proportional credit (mean |Q(CHECK)| 4.48 → 0.00), directly exhibiting the zero fixed point. As a remedy, a negligible Virtual Information Cost (VIC) breaks the fixed point so Q(CHECK) leaves zero (0.00 → 0.11–0.15) and CHECK's absorption of aggressive actions drops; however a one-chip cost is below the threshold ε_min we derive, so the effect is partial (~4–6 pp), and tuning a sufficient threshold cost is left as future work. We also honestly report, as a methodological negative result, a credit-assignment implementation artifact (equal split of all-zero-invest episodes) that, combined with a single training seed, produced a spurious generalization signal.

**Keywords:** reinforcement learning, Monte-Carlo control, credit assignment, reward shaping, zero-credit absorption, fixed point, tabular Q-learning, heads-up no-limit hold'em

---

## I. 서론

표 기반 강화학습은 함수근사의 블랙박스 효과 없이 학습 동역학을 단일변수로 통제·관찰할 수 있다. 본 연구의 무대는 헤즈업 노리밋 홀덤을 순수 tabular Monte-Carlo로 학습하는 환경이며, 목적은 강한 봇이 아니라 구조적 기여도 배분이 남기는 측정 가능한 병리의 진단과 그 최소 처방이다.

Monte-Carlo 제어에서 종단 보상을 행동에 배분하는 방식은 학습 신호의 분산·편향을 좌우한다. 표준 Monte-Carlo는 편향이 없지만 분산이 크고, 자연스러운 대안은 각 행동이 판돈에 투입한 금액의 비율로 보상을 나누는 **비례배분(proportional)**이다. 그러나 비용 0 행동(투자액 0, 대표적으로 CHECK)의 비례 credit은 분자가 0이라 항상 0이고, 그 가치 추정의 고정점은 실제 기댓값과 무관하게 0에 고정된다. 이 0은 음의 값으로 올바르게 학습된 공격 행동들보다 높아 보여, greedy 정책이 열등한 CHECK를 영구히 선택한다.

본 논문의 기여는 다음과 같다. **(1) 진단** — 위 현상을 **영-기여 흡수(ZCA)**로 명명해 toy MDP에서 증명하고(III장), 실제 2,048-셀 봇에서 Q(CHECK)의 영-고정점을 측정한다(V장). **(2) 처방** — 비용 0 행동에 무시 가능한 **가상비용(VIC)**을 부여해 그 고정점을 깨는 최소 개입과, 작동에 필요한 **임계 가상비용**을 유도하며(IV장), 1칩 개입이 고정점을 실제로 깨되 임계 미달이라 부분적임을 측정한다(V장). **(3) 방법론** — 평가에서 발견한 credit-배분 구현 인공물과 그것이 만든 허위 신호를 정직하게 보고한다(VI장). 본 연구의 가치는 성능이 아니라, 구조적 기여도 배분의 병리를 증명·측정하고 처방의 작동·한계를 정직하게 드러낸 데 있다.

## II. 관련 연구

ZCA를 이루는 부품은 인접 문헌에 모두 존재하나, 본 연구는 그 부호를 뒤집어 같은 구조를 *실패 모드*로 진단한다. 협력게임 이론의 Shapley value[3] 및 Shapley Q-value[4]는 null-player 공리(한계 기여 0 → 배분 0)를 공정성의 바람직한 성질로 둔다 — 본 연구의 "비용 0 → credit 0"은 그 정확한 대응물이나 진단의 방향이 반대다. 같은 직관은 difference rewards[1]·COMA[2]에도 깔려 있다. RUDDER[5]는 return-equivalent 재분배가 최적 정책을 보존함을 보이는데, 비례배분은 비용 0 행동에 대해 return-equivalent가 아니며 ZCA는 정확히 그 비등가 영역에서 발생한다(보존 정리의 대우). 처방 측면에서 VIC는 potential-based reward shaping(PBRS)이 Q-value 초기화와 등가[6][7]인 틀 안에 위치하나, "비용 0 행동에 선택적·음·credit 기반 가상비용을 부여해 영-고정 흡수를 깬다"는 처방을 명시한 선행은 확인되지 않았고, 가장 가까운 action-penalty[8]는 모든 행동에 일률적이라 선택적이지 않다. 미방문/낙관적 0의 *일시적* 흡수[9]는 초기화 기인으로 비례 credit이 구조적으로 0을 생성하는 본 연구와 기제가 다르다. 단일 seed 오도 위험은 재현성 문헌[10][11][12]이 확립했으며 본 연구는 VI장에서 직접 보고한다.

## III. 영-기여 흡수의 형식적 특성화

**문제 설정(toy MDP).** 결정 상태 s에서 행동 a₁을 한 번 선택한다. 각 행동은 투자액 inv(a₁)≥0을 가지며 비용 0 행동(CHECK)은 inv=0이다. 선택 후 궤적은 투자액 c>0인 후속 행동을 적어도 하나 포함하고 종단 보상 P로 끝난다(γ=1, 종단 보상만). μ(a₁):=𝔼[P|a₁]로 두면 참값은 q\*(s,a₁)=μ(a₁)이다. 행동별 return은 〈Table 1〉과 같다.

**〈Table 1〉 행동별 return R(s, a₁)**

| 방식 | R(s, a₁) |
|---|---|
| 표준 MC | P |
| 비례배분(PROP) | [inv(a₁)/(inv(a₁)+c)] · P |
| VIC | PROP과 동일, 단 inv(CHECK) ← ε > 0 |

**Lemma 1 (표준 MC).** Q_std(s,a₁) → μ(a₁) = q\*(s,a₁).

**Lemma 2 (영-고정점).** Q_prop(s,CHECK)=[0/(0+c)]·μ(CHECK)=0 (∀ μ(CHECK)). CHECK의 고정점은 참값과 무관하게 0이며, R≡0이라 표본 분산도 0인 **구조적 고정점**이다(초기화 잔재 아님).

**Theorem (흡수).** q\*(CHECK)=μ_C < μ_B=q\*(BET)이고 μ_B<0이면, 비례배분 greedy는 열등한 CHECK를(0 > [b/(b+c)]μ_B), 표준 MC는 최적 BET을 선택한다. *적용 범위*: 흡수는 더 나은 대안조차 −EV일 때만 발생한다(어떤 행동이 +EV이면 정상 선택).

**Proposition 1 (낙관적 초기화와의 구분).** 0-초기화의 0-선호는 충분한 방문 후 Q→μ로 소거되어 *일시적*·고정점=참값이나(Lemma 1), Q_prop(CHECK)=0은 수렴 후에도 유지되는 고정점이며 참값과 다르다(Lemma 2). 즉 낙관적 초기화는 "아직 학습 못 해서"(일시적), **ZCA는 "구조적으로 학습 불가라서"**(영구)이다.

## IV. VIC: 고정점을 깨는 최소 가상비용과 임계

**Proposition 2 (VIC와 임계).** CHECK에 가상 투자 ε>0을 주면 Q_vic(CHECK)=[ε/(ε+c)]·μ_C로 **고정점이 0에서 떨어진다.** Theorem 설정에서 greedy가 BET을 선택할 필요충분조건은 k:=[b/(b+c)](μ_B/μ_C)∈(0,1)에 대해 **ε > ε_min = k·c/(1−k)** 이다. 즉 VIC는 *크기 무관하게 고정점을 깨지만*, 흡수를 실제로 *해소*하려면 ε이 임계를 넘어야 한다. 임계 미달이면 Q_vic(CHECK)≈0으로 흡수가 잔존한다 — 이 점이 V장 실측(1칩=부분 효과)을 예측한다.

**탈출 메커니즘 비교.** 비례배분 위 처방 중 **tie-break·무정보 노이즈는 strict 흡수(0 > 음수, 부등식이지 동률 아님)를 탈출하지 못한다**(노이즈는 고정점 0 불변, tie-break은 미발동). VIC와 고정 페널티만 고정점을 옮기며, VIC의 고정점만 참값 μ_C에 연동(informed)된다.

## V. 실제 MDP에서의 측정

모든 수치는 학습된 Q-table 직접 진단(`analyze_qcheck.py`) 또는 100k×5 평가에서 얻었다. 환경: (라운드 × 포지션 × 핸드 버킷 × 직전 행동) 2,048-셀 추상화, 8 행동, softmax 탐색, 2M 에피소드, 5종 페르소나(TAG/LAG/Maniac/Station/Nit) 학습 상대. mbb/g = payoff×500.

### 5.1 ZCA 지문 — Q(CHECK)의 영-고정점
표준 MC(PURE)와 비례배분(PROP)으로 학습한 Q(CHECK)의 분포(〈Table 2〉):

**〈Table 2〉 학습된 Q(CHECK) (active 셀, 직접 진단)**

| 기여도 배분 | mean\|Q(CHECK)\| | Q(CHECK) 범위(칩) |
|---|---|---|
| 표준 MC (PURE) | **4.48** | [−72.9, +119.8] |
| 비례배분 (PROP) | **0.00** | [0, 0] |

표준 MC에서 Q(CHECK)는 −73~+120칩으로 펼쳐지는 반면 비례배분에서는 **정확히 0으로 붕괴**한다. Lemma 2의 영-고정점이 실제 2,048-셀 시스템에서 직접 관측된다 — 학습 seed·표본과 무관한 구조적 사실이다.

### 5.2 VIC가 고정점을 깬다 (방향은 맞고, 1칩은 임계 미달)
VIC(CHECK에 1칩 가상비용)는 〈Table 3〉처럼 Q(CHECK)를 0에서 떼어내고(0.00 → 0.11–0.15) CHECK가 공격 행동(RAISE류)을 흡수하는 셀 비율을 낮춘다.

**〈Table 3〉 VIC의 효과 (clean, 학습 seed=42, 100k×5)**

| 스킴 | mean\|Q(CHECK)\| off→on | CHECK의 공격 흡수율 off→on |
|---|---|---|
| single | 0.00 → 0.11 | 57.3% → 53.7% |
| cycle | 0.00 → 0.15 | 72.4% → 68.5% |
| mixed | 0.00 → 0.15 | 69.9% → 64.4% |

VIC는 **설계대로 고정점을 깬다**(Q(CHECK)가 0을 벗어남). 그러나 흡수 감소는 약 4–6%p에 그친다. 이는 IV장 임계와 정합한다 — 팟이 큰 결정점에서 1칩 가상비용의 비중(예: 팟 400에서 약 0.25%)은 임계 ε_min에 크게 미달하여 Q_vic(CHECK)≈0.1로, 음수 RAISE(예: −5)보다 여전히 높다. 즉 **1칩은 고정점을 깨되 흡수를 해소할 만큼은 아니다. 충분한 임계비용의 설정은 후속 과제다.**

## VI. 한계와 방법론적 부정적 결과 (정직)

**(1) 방어 가능(견고):** 비례배분의 영-고정점 이론(III)과 실측(§5.1, Q(CHECK)=0)은 학습 seed·표본과 무관하다. VIC가 고정점을 깬다는 사실(§5.2, 0→0.11)도 구조적이다.

**(2) credit-배분 구현 인공물(발견·정정):** 학습 구현은 한 에피소드의 총투자가 0인 경우(전부 CHECK 또는 전부 FOLD) 비례 분배가 미정의라 **균등 분배(payoff/n)로 폴백**한다. 이 폴백은 비용 0 행동에 비(非)비례 credit을 누출시킨다. 본 폴백을 0-credit으로 교정한 통제런과 원본의 단일변수 비교에서, 폴백 유무가 평가 성능을 크게 흔듦을 확인했다(예: mixed-off vs Random −362 vs −1,262 mbb/g). 따라서 폴백이 포함된 초기 평가의 절대 수치는 인공물을 포함한다. 본 결과는 단일 seed가 결과를 오도할 수 있다는 재현성 문헌[10][11][12]과 정합한다.

**(3) 일반화는 본 연구의 주장이 아니다:** 폴백을 교정한 통제런(seed=42, 100k×5)에서 VIC-on의 미학습(OOD) 상대 성능은 VIC-off와 차이가 없었다(예: mixed on/off vs Random −400/−362). 따라서 "VIC가 분포 외 일반화를 좌우한다"는 강한 주장은 **본 연구가 지지하지 않으며**, 본 논문은 VIC를 *일반화 처방*이 아니라 *고정점을 깨는 메커니즘*으로만 주장한다.

**(4) ZCA는 다(多)행동 현상:** FOLD도 비용 0이라 같은 영-고정점을 가지며, 베팅에 직면한 결정점에서 FOLD=0이 음수 행동을 지배한다(다만 대부분은 정당한 폴드이며 CHECK와 동시 합법이 아니라 직접 경쟁하지 않는다). VIC는 CHECK에만 개입하므로 FOLD의 고정점은 다루지 않는다 — 비용 0 행동 전반에 대한 처방은 향후 과제다.

**(5) 범위:** 단일 추상화·단일 게임에 한정된다.

## VII. 결론

본 연구는 tabular Monte-Carlo 비례배분 기여도가 비용 0 행동에 남기는 구조적 병리를 **영-기여 흡수(ZCA)**로 명명하고, toy MDP에서 영-고정점과 흡수를 증명하며 실제 2,048-셀 봇에서 Q(CHECK)=0을 직접 측정하였다. ZCA는 낙관적 초기화와 고정점 수준에서 질적으로 구별된다. 최소 가상비용 VIC는 그 고정점을 **설계대로 깨나**(Q(CHECK) 0→0.11), 1칩은 유도된 임계 ε_min에 미달하여 흡수 해소는 부분적이며 충분한 임계비용은 후속 과제다. 아울러 평가에서 발견한 credit-배분 인공물과 그것이 만든 허위 일반화 신호를 정직하게 보고하였다. 본 사례연구의 가치는, 구조적 기여도 배분의 병리를 증명·측정하고 최소 처방의 작동·한계를 정직하게 규명한 데 있다.

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

---

## 저자소개

[저자명] (Author Name) — [소속/직위]. E-mail: [e-mail]. 관심분야: 강화학습, 게임 AI, 학습 동역학 분석.

<!-- 형식 증명: toy_zca_proof.md · 진단: ../poker-pokerkit-prev/analyze_qcheck.py · clean 재현: ../results/28_ablation_vic_2m_clean · 누수 격리: mixed_vic_off_LEAKON -->
