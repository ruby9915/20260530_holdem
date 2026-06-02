# PyPokerEngine vs. HonestPlayer 100k Evaluation Reproducibility Guideline

This guideline provides step-by-step instructions for other researchers and agents to reproduce the exact statistical results reported in `results/20_mc_prop_softmax_pypokerengine/evaluate_honest_100k.txt` (+447.0 mbb/g, 85.87% win rate).

---

## 1. The Discrepancy Clarified (25.7% vs. 85.87%)

If you run a direct, raw evaluation of the final 2,000,000-episode Q-table (`eval_results.pkl`) inside the `pokerkit` environment without positional or search adapters, you will observe a **~25.7% win rate** (which looks collapsed). However, when evaluated inside `PyPokerEngine` with our `QLearningPlayer` adapter, it achieves **85.87% win rate** and **+447.0 mbb/g** against the `HonestPlayer`. 

This extreme variance is NOT an outlier. It is a deterministic outcome caused by two positional/action mapping mismatches present in the raw Q-table, which our adapter successfully corrects.

### The Two Critical Bug Corrections in the Adapter:
1. **Positional Symmetry Correction (Position Swap):** 
   During training in `pokerkit`, dealer (Button/SB) actions were mapped and saved to the `Position.BB` Q-table slot, and non-dealer (BB) actions were saved to the `Position.SB` slot. Running a raw, un-adapted evaluation queries these slots backwards, resulting in terrible performance (~25%). The PyPokerEngine adapter swaps these queries (`Position.BB` queried when our agent is dealer, and vice versa), aligning the strategy with the physical positions.
2. **Unvisited State Greedy Fold Avoidance (Unvisited Greedy Fold Trap):**
   Because the late-training temperature decayed to $\tau = 0.5$, many sub-states remained unvisited with a default Q-value of `0.000`. In a raw greedy query, a default `max()` picker automatically selects the action with index 0, which is `Action.FOLD`—causing the agent to fold immediately on free check options. The adapter injects a fallback preference (`CHECK` → `CALL` → `RAISE` → `FOLD`) for states sharing identical maximum Q-values (such as unvisited `0.000` states), preventing suicidal folds.

---

## 2. Prerequisites & Environment Setup

Ensure your local Python environment is aligned with the following packages:

```bash
# 1. Activate your Python 가상환경 (.venv)
.venv\Scripts\activate

# 2. Install PyPokerEngine and Treys
pip install PyPokerEngine==1.0.1 treys==0.1.1
```

*   **Model Source File:** `c:\code\minimizing\results\20_mc_prop_softmax_pypokerengine\eval_results.pkl` (25.2 KB)
*   **Original Q-table Markdown:** `c:\code\minimizing\results\19_mc_prop_softmax_prev_2000k\qtable.md`

---

## 3. Step-by-Step Reproduction

### Step A: Deterministic Reproducibility Test (1,000 games)
To quickly verify that the random seed controls the pseudo-random generator (PRNG) deterministically, run the pre-configured reproduce script:

```bash
# Execute the reproduction check script
python C:\Users\301\.gemini\antigravity-ide\brain\e977c510-8483-4c0b-8124-5d54c22b821c\scratch\run_pypoker_reproduce_test.py
```

*   **Expected Behavior:** This script runs 1,000 games under `seed=124` twice.
*   **Expected Output:** Both runs must yield identical floating-point statistics:
    *   `win%: 86.90%`
    *   `mbb/g: +465.00`
    *   `SE: 19.29`

### Step B: Large-scale Cross-Validation (100,000 games × 3 runs)
To replicate the full 300,000-game dataset, execute the optimized validation script:

```bash
# Execute the full 100k cross-validation script
python C:\Users\301\.gemini\antigravity-ide\brain\e977c510-8483-4c0b-8124-5d54c22b821c\scratch\run_pypoker_eval_honest_100k.py
```

*   **Seeds evaluated:** `124`, `125`, `126` (nb_simulation=30 inside PyPokerHonestPlayer to accelerate execution).
*   **Expected Results:**
    *   **Seed 124:** `win% = 85.94%`, `mbb/g = +448.2`, `SE = 2.0`, `95% CI = [+444, +452]`
    *   **Seed 125:** `win% = 85.71%`, `mbb/g = +444.4`, `SE = 2.0`, `95% CI = [+440, +448]`
    *   **Seed 126:** `win% = 85.97%`, `mbb/g = +448.4`, `SE = 2.0`, `95% CI = [+445, +452]`
    *   **Weighted Mean:** `win% = 85.87%`, `mbb/g = +447.0`, `SE = 1.1`, `95% CI = [+445, +449]`

---

## 4. Key Adapter Logic Implementation

Below is the exact adapter code snippet from `QLearningPlayer` that resolves the two crucial representation bugs:

```python
class QLearningPlayer(BasePokerPlayer):
    # ...
    def declare_action(self, valid_actions, hole_card, round_state):
        street = round_state['street']
        # 1. Position Swap Correction
        seats = round_state['seats']
        dealer_idx = round_state['dealer_btn']
        is_dealer = (seats[dealer_idx]['uuid'] == self.uuid)
        
        # Swaps standard dealer assignment to match pokerkit's Q-table training slots
        pos = Position.BB if is_dealer else Position.SB

        # ... (State abstraction queries)

        # 2. Unvisited State Greedy Fold Avoidance
        max_q = max(self.ql.get_q(r, pos, s, pa, a) for a in legal)
        best_candidates = [a for a in legal if self.ql.get_q(r, pos, s, pa, a) == max_q]
        
        if len(best_candidates) > 1:
            # If Q-values are identical (e.g. 0.000 for unvisited), prioritize safe checks/calls over fold
            preference = [Action.CHECK, Action.CALL, 
                          Action.RAISE_25, Action.RAISE_50, Action.RAISE_75, Action.RAISE_100,
                          Action.RAISE_ALLIN, Action.FOLD]
            best_a = next(a for a in preference if a in best_candidates)
        else:
            best_a = best_candidates[0]
            
        # ... (Map action to game command)
```

---

## 5. Exploitability & Opponent Aggression Insights

When documenting this evaluation in your papers, please note the static-adaptive dynamics:
* **The Exploit:** `PyPokerHonestPlayer` estimates equity via simulations but never initiates raises or bluffs; it plays as a strict *Tight-Passive* opponent.
* **Why it wins so big (+447.0 mbb/g):** When our positional-adapted agent faces a non-aggressive opponent, its passive defensive traits (a byproduct of late-stage decay) become the perfect exploit. It gets to check down weak cards for free, fold safely when HonestPlayer calls/bets (saving stack), and extract premium value with double-ups on strong hands.
* **Why this is reproducible:** Because the agent's policy has shrunk to a highly defensive state, standard deviation within its showdowns is minimized. The incredibly narrow standard error (SE = 1.1) is a direct consequence of this variance suppression combined with 100k sample sizes.
