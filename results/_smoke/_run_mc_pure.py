import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit-ucb')
import train_eval_mc_pure as t
t.TOTAL_EPISODES = 400_000
t.EVAL_EVERY     = 2_000
t.CSV_PATH       = r'c:\code\minimizing\eval_results_mc_pure_400k.csv'
t.main()
