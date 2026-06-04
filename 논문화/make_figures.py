# -*- coding: utf-8 -*-
"""논문용 그림 생성: (1) 성능 비교 막대그래프(에러바), (2) 27b 학습곡선.
출력: 논문화/fig/ 아래 PNG. matplotlib만 사용.
"""
import os
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

# 한글 폰트(맑은 고딕) 설정 — 없으면 기본 폰트
for cand in ("Malgun Gothic", "맑은 고딕", "AppleGothic", "NanumGothic"):
    if any(cand.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        rcParams["font.family"] = cand
        break
rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(HERE, "fig")
os.makedirs(FIGDIR, exist_ok=True)

# ----- Fig A: 성능 비교 막대그래프 (Table 2) -----
runs = ["26a\nLAG single", "26c\nSTA single", "27a\nCYCLE", "27b\nMIXED"]
vs_random = [-650.4, -674.9, 681.3, 1083.9]
vs_random_sd = [19.3, 6.5, 51.4, 110.5]
vs_tag = [924.4, 774.3, 868.3, 885.2]
vs_tag_sd = [12.2, 1.4, 12.1, 10.9]

x = range(len(runs))
w = 0.38
fig, ax = plt.subplots(figsize=(8, 4.5))
b1 = ax.bar([i - w / 2 for i in x], vs_random, w, yerr=vs_random_sd, capsize=4,
            label="vs Random", color="#4C72B0")
b2 = ax.bar([i + w / 2 for i in x], vs_tag, w, yerr=vs_tag_sd, capsize=4,
            label="vs fixed TAG", color="#DD8452")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_ylabel("mbb/g")
ax.set_title("Performance by Training Distribution (raw-greedy, 100k x 5)")
ax.set_xticks(list(x))
ax.set_xticklabels(runs)
ax.legend()
for bars, vals in ((b1, vs_random), (b2, vs_tag)):
    for rect, v in zip(bars, vals):
        ax.annotate(f"{v:+.0f}", (rect.get_x() + rect.get_width() / 2,
                    v + (30 if v >= 0 else -45)), ha="center", fontsize=8)
fig.tight_layout()
figA = os.path.join(FIGDIR, "fig2_performance_bar.png")
fig.savefig(figA, dpi=200)
plt.close(fig)

# ----- Fig B: 27b 학습곡선 -----
csv_path = os.path.join(HERE, "..", "results", "27b_persona_mixed_2000k", "eval_results.csv")
ep, mr, mt = [], [], []
with open(csv_path, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ep.append(int(row["episode"]))
        mr.append(float(row["mbb/g_vs_random"]))
        mt.append(float(row["mbb/g_vs_rulebased"]))

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(ep, mr, label="vs Random", color="#4C72B0", linewidth=1.2)
ax.plot(ep, mt, label="vs fixed TAG", color="#DD8452", linewidth=1.2)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xlabel("Episode")
ax.set_ylabel("mbb/g")
ax.set_title("27b MIXED Learning Curve")
ax.legend()
fig.tight_layout()
figB = os.path.join(FIGDIR, "fig3_learning_curve.png")
fig.savefig(figB, dpi=200)
plt.close(fig)

print("saved:", figA)
print("saved:", figB)
