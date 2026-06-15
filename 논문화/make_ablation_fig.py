"""VIC ablation 2x3 결과 그룹 막대 그래프 생성 (논문용)."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "ablation_vic_2m" / "_summary_100kx5.csv"
OUT_DIR = ROOT / "논문화" / "fig"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 한글 폰트
for name in ("Malgun Gothic", "맑은 고딕"):
    try:
        fm.findfont(name, fallback_to_default=False)
        plt.rcParams["font.family"] = name
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
schemes = ["single", "cycle", "mixed"]
labels = {"single": "Single (TAG)", "cycle": "Cycle", "mixed": "Mixed"}

def get(scheme, vic, key):
    for r in rows:
        if r["scheme"] == scheme and r["vic"] == vic:
            return float(r[key])
    return float("nan")

x = np.arange(len(schemes))
w = 0.2
fig, (axR, axT) = plt.subplots(1, 2, figsize=(11, 4.4))

for ax, (metric, title) in zip(
    (axR, axT),
    (("vs_random", "vs Random (미학습 상대 · 일반화)"),
     ("vs_tag", "vs TAG (학습 분포 내)")),
):
    on = [get(s, "on", f"{metric}_mbb") for s in schemes]
    off = [get(s, "off", f"{metric}_mbb") for s in schemes]
    on_sd = [get(s, "on", f"{metric}_sd") for s in schemes]
    off_sd = [get(s, "off", f"{metric}_sd") for s in schemes]
    b1 = ax.bar(x - w/2, on, w*0.9, yerr=on_sd, capsize=4,
                color="#2c7fb8", label="VIC on")
    b2 = ax.bar(x + w/2, off, w*0.9, yerr=off_sd, capsize=4,
                color="#d95f0e", label="VIC off")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([labels[s] for s in schemes])
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("mbb/g")
    ax.legend(fontsize=9)
    ax.grid(axis="y", ls=":", alpha=0.5)
    for bars in (b1, b2):
        for rect in bars:
            h = rect.get_height()
            va = "bottom" if h >= 0 else "top"
            ax.annotate(f"{h:+.0f}", (rect.get_x()+rect.get_width()/2, h),
                        ha="center", va=va, fontsize=8,
                        xytext=(0, 3 if h >= 0 else -3), textcoords="offset points")

fig.suptitle("VIC ablation (2×3, 2M 학습 · 100k×5 정밀평가): VIC off → 미학습 상대 일반화 붕괴, 학습 분포 내 성능은 유지",
             fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.95))
out = OUT_DIR / "fig_vic_ablation.png"
fig.savefig(out, dpi=160)
print(f"saved: {out}")
