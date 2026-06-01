import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit-ucb')
import train_eval_mc_prop_eps as t
t.TOTAL_EPISODES = 400_000
t.EVAL_EVERY     = 2_000
t.CSV_PATH       = r'c:\code\minimizing\results\11_mc_prop_eps_400k\eval_results.csv'
t.main()
