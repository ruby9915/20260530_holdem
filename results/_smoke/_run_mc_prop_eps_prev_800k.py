import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit-prev')
import train_eval_mc_prop_eps_prev as t
t.TOTAL_EPISODES = 800_000
t.EVAL_EVERY     = 4_000
t.CSV_PATH       = r'c:\code\minimizing\results\12c_mc_prop_eps_prev_800k\eval_results.csv'
t.main()
