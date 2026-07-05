# -*- coding: utf-8 -*-
"""논문 v3 그림 생성 (재현 가능 — results/의 로그·CSV에서 직접 파싱).
실행: ../.venv/Scripts/python.exe build_figs.py   (zca_theory/ 에서) → figs/*.png (300dpi)

흑백 인쇄 안전 설계(dataviz): 회색조 + 선스타일·마커·해칭 이중 인코딩, 직접 라벨,
y-기준선(0) 명시, 격자 최소화. 라벨은 영문(별표1: 그림 내용 영문 표기).
Fig 1  용량-반응: 가상비용 크기별 vs Random 성능 (seed 점 + 평균±SD)
Fig 2  학습 곡선: PURE vs PROP vs PROP+VIC (vs TAG, 5-seed 평균, 이동평균)
Fig 3  턴 행동 분포: 무개입 vs 임계 VIC (수동화 해소)
"""
import csv
import re
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "results"
LOG = RES / "_logs"
OUT = HERE / "figs"
OUT.mkdir(exist_ok=True)

INK = "#1a1a1a"       # 본문 잉크
GRAY = "#8a8a8a"      # 보조
LIGHT = "#c9c9c9"     # seed 점
plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "figure.dpi": 300,
})


def grab_pair(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    m = re.search(r"vsRand mean\s*([+-][\d.]+).*?vsTAG mean\s*([+-][\d.]+)", t, re.S)
    return (float(m.group(1)), float(m.group(2))) if m else None


# ───────────────────────── Fig 1: 용량-반응 ─────────────────────────
def fig1():
    conds = [  # (라벨, seed별 로그 경로 목록)
        ("No cost\n(ε=0)",  [LOG / f"sse_off_s{s}.log" for s in range(1, 6)] + [LOG / "clean_eval_single_vic_off.log"]),
        ("Fixed\n1 chip",   [LOG / "clean_eval_single_vic_on.log"]),
        ("Fixed\n5 chips",  [LOG / f"night_e3e_k5_s{s}.log" for s in range(1, 6)]),
        ("Fixed\n20 chips", [LOG / f"night_e3e_k20_s{s}.log" for s in range(1, 6)]),
        ("Fixed\n60 chips", [LOG / f"night_e3e_k60_s{s}.log" for s in range(1, 6)]),
        ("Pot 10%",         [LOG / f"sse_chec_a10_s{s}.log" for s in range(1, 6)] + [LOG / "peval_checktime_a10.log"]),
        ("Pot 20%",         [LOG / f"sse_chec_a20_s{s}.log" for s in range(1, 6)] + [LOG / "peval_checktime_a20.log"]),
        ("Pot 30%",         [LOG / f"sse_chec_a30_s{s}.log" for s in range(1, 6)] + [LOG / "peval_checktime_a30.log"]),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    for i, (lbl, paths) in enumerate(conds):
        vals = [grab_pair(p)[0] for p in paths if p.exists() and grab_pair(p)]
        ax.scatter([i] * len(vals), vals, s=13, color=LIGHT, zorder=2,
                   edgecolors=GRAY, linewidths=0.4)
        mu = st.mean(vals)
        sd = st.pstdev(vals) if len(vals) > 1 else 0.0
        ax.errorbar([i], [mu], yerr=[sd], fmt="o", color=INK, ms=5,
                    capsize=3, lw=1.4, zorder=3)
        note = f"{mu:+.0f}" + (" (n=1)" if len(vals) == 1 else "")
        ax.annotate(note, (i, mu), textcoords="offset points",
                    xytext=(8, 4), fontsize=7.5, color=INK)
    ax.axhline(0, color=GRAY, lw=0.8, ls=(0, (4, 3)), zorder=1)
    ax.axvline(4.5, color=LIGHT, lw=0.7)   # 계열 구분: 상수 | 팟-비례
    ax.text(2.0, 2900, "Constant virtual cost (chips)", fontsize=7.5,
            color=GRAY, ha="center")
    ax.text(6.2, 2900, "Pot-proportional (%)", fontsize=7.5,
            color=GRAY, ha="center")
    ax.set_xticks(range(len(conds)), [c[0] for c in conds], fontsize=7.5)
    ax.set_ylabel("mbb/g vs. unseen random opponent")
    ax.set_xlabel("Virtual cost assigned to CHECK")
    ax.grid(axis="y", color=LIGHT, lw=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_dose_response.png")
    plt.close(fig)


# ───────────────────────── Fig 2: 학습 곡선 ─────────────────────────
def read_curve(run):
    xs, ys = [], []
    with open(RES / "30_vic_potfrac_seedsweep" / run / "eval_results.csv",
              encoding="utf-8") as f:
        for row in csv.DictReader(f):
            xs.append(int(row["episode"]))
            ys.append(float(row["mbb/g_vs_rulebased"]))
    return xs, ys


def smooth(ys, w=9):
    out = []
    for i in range(len(ys)):
        lo = max(0, i - w // 2)
        out.append(st.mean(ys[lo:i + w // 2 + 1]))
    return out


def fig2():
    groups = [
        ("Standard MC (PURE)", [f"pure_single_s{s}" for s in range(1, 6)], (0, (2, 2)), GRAY),
        ("Proportional, no cost", [f"off_s{s}" for s in range(1, 6)], (0, (5, 3)), "#5a5a5a"),
        ("Proportional + threshold cost", [f"chec_a30_s{s}" for s in range(1, 6)], "solid", INK),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    for lbl, runs, ls, col in groups:
        curves = [read_curve(r) for r in runs]
        xs = curves[0][0]
        mean_y = [st.mean([c[1][i] for c in curves]) for i in range(len(xs))]
        ax.plot([x / 1e6 for x in xs], smooth(mean_y), ls=ls, color=col,
                lw=1.6, label=lbl)
    ax.axhline(0, color=LIGHT, lw=0.8)
    ax.set_xlabel("Training episodes (millions)")
    ax.set_ylabel("mbb/g vs. training opponent (TAG)")
    ax.grid(axis="y", color=LIGHT, lw=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    # 직접 라벨(끝점)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_learning_curves.png")
    plt.close(fig)


# ───────────────────────── Fig 3: 턴 행동 분포 ─────────────────────────
def turn_dist(logname):
    t = open(LOG / logname, encoding="utf-8", errors="ignore").read()
    m = re.search(r"TURN\s+(.+)", t)
    d = {}
    for tok in m.group(1).split():
        k, v = tok.split(":")
        d[k] = int(v.rstrip("%"))
    return d


def fig3():
    off = turn_dist("night_e4_prof_off_s1.log")
    vic = turn_dist("night_e4_prof_chec_a30_s1.log")
    cats = ["CHECK", "FOLD", "RAISE_25", "RAISE_50", "RAISE_100", "RAISE_ALLIN"]
    labels = ["CHECK", "FOLD", "RAISE\n25%", "RAISE\n50%", "RAISE\n100%", "ALL-IN"]
    ov = [off.get(c, 0) for c in cats]
    vv = [vic.get(c, 0) for c in cats]
    x = range(len(cats))
    w = 0.36
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    ax.bar([i - w / 2 for i in x], ov, w, color="white", edgecolor=INK,
           hatch="////", lw=0.9, label="No cost (passive)")
    ax.bar([i + w / 2 for i in x], vv, w, color=GRAY, edgecolor=INK,
           lw=0.9, label="Threshold cost")
    for i in x:  # 직접 라벨(0 제외)
        if ov[i]:
            ax.annotate(f"{ov[i]}", (i - w / 2, ov[i]), ha="center",
                        textcoords="offset points", xytext=(0, 2), fontsize=7.5)
        if vv[i]:
            ax.annotate(f"{vv[i]}", (i + w / 2, vv[i]), ha="center",
                        textcoords="offset points", xytext=(0, 2), fontsize=7.5)
    ax.set_xticks(list(x), labels, fontsize=7.5)
    ax.set_ylabel("Turn decisions (%)")
    ax.set_ylim(0, 78)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="y", color=LIGHT, lw=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_turn_behavior.png")
    plt.close(fig)


if __name__ == "__main__":
    fig1(); fig2(); fig3()
    print("saved:", ", ".join(p.name for p in sorted(OUT.glob("*.png"))))
