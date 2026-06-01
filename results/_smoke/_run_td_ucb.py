import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit-ucb')
import train_eval_td as t
t.TOTAL_EPISODES = 400_000
t.EVAL_EVERY     = 2_000
t.CSV_PATH       = r'c:\code\minimizing\results\07_td_ucb_400k\eval_results.csv'
t.main()
