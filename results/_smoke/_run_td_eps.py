import sys
sys.path.insert(0, r'c:\code\minimizing\poker-pokerkit')
import train_eval as t
t.TOTAL_EPISODES = 400_000
t.EVAL_EVERY     = 2_000
t.CSV_PATH       = r'c:\code\minimizing\results\06_td_eps_400k\eval_results.csv'
t.main()
