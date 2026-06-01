import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit-prev')
import train_eval_mc_pure_eps_prev as t
t.TOTAL_EPISODES = 400_000
t.EVAL_EVERY     = 2_000
t.CSV_PATH       = r'c:\code\minimizing\results\14_mc_pure_eps_prev_400k\eval_results.csv'
t.main()
