#!/usr/bin/env python3
"""Three-way response-time comparison: Awkernel GEDF vs CIE+SCHED_DEADLINE
(ROS 2) vs YASMIN G-EDF.

Follows the plotting conventions of ros2_task_set/compare_response_time.ipynb
and adds the YASMIN series. Run on the analysis machine after copying the
Raspberry Pi results back:

    python3 plot_comparison.py \
        --awkernel-dir ../awkernel/evaluation_data/csv \
        --ros2-dir     ../ros2/benchmark_results/<timestamp> \
        --yasmin-dir   ../yasmin/benchmark_results/<timestamp>
"""

import argparse
import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TU_VALUES = [1.0, 1.5, 2.0, 2.5, 3.0]
TU_BOX = [1.0, 2.0, 3.0]  # box plot subset (same as the notebook)


def load_awkernel(base):
    data, miss = {}, {}
    for tu in TU_VALUES:
        path = os.path.join(base, f"RD-Gen(GEDF3)_TU{int(tu * 10)}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        lat = pd.to_numeric(df["Latency"], errors="coerce")
        dl = pd.to_numeric(df["Relative Deadline"], errors="coerce")
        ok = lat.notna() & dl.notna()
        data[tu] = lat[ok].values / 1000  # ns -> us
        miss[tu] = (lat[ok] > dl[ok]).mean()
    return data, miss


def load_benchmark(base):
    """ros2_task_set / yasmin_benchmark result layout (identical)."""
    data, miss = {}, {}
    for tu in TU_VALUES:
        tu_dir = os.path.join(base, f"TU_{tu}")
        if not os.path.isdir(tu_dir):
            continue
        rt, dl = [], []
        for case_dir in sorted(glob.glob(os.path.join(tu_dir, "case_*"))):
            for f in glob.glob(os.path.join(case_dir, "response_time_*.csv")):
                df = pd.read_csv(f)
                rt.extend(df["response_time_us"].tolist())
                dl.extend(df["deadline_us"].tolist())
        if rt:
            rt = np.asarray(rt, dtype=float)
            dl = np.asarray(dl, dtype=float)
            data[tu] = rt
            miss[tu] = (rt > dl).mean()
    return data, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--awkernel-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "awkernel", "evaluation_data", "csv"))
    ap.add_argument("--ros2-dir", required=True,
                    help="ros2/benchmark_results/<timestamp>")
    ap.add_argument("--yasmin-dir", required=True,
                    help="yasmin/benchmark_results/<timestamp>")
    ap.add_argument("--out-prefix", default="")
    ap.add_argument("--log-y", action="store_true",
                    help="log-scale y axis for the response-time box plot")
    args = ap.parse_args()

    aw_data, aw_miss = load_awkernel(args.awkernel_dir)
    r2_data, r2_miss = load_benchmark(args.ros2_dir)
    ya_data, ya_miss = load_benchmark(args.yasmin_dir)

    plt.rcParams.update({"font.size": 16})

    # ---- box plot -----------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.5, 2.88))
    positions = np.arange(len(TU_BOX))
    width = 0.26
    flier = dict(marker=".", markersize=4,
                 markeredgecolor="black", markerfacecolor="black")
    common = dict(widths=width * 0.85, patch_artist=True,
                  medianprops=dict(color="black", linewidth=1.5),
                  whiskerprops=dict(color="black", linewidth=1),
                  capprops=dict(color="black", linewidth=1),
                  flierprops=flier)

    series = [
        ("Awkernel - GEDF", aw_data,
         dict(facecolor="white", edgecolor="black", linewidth=1)),
        ("YASMIN - G-EDF", ya_data,
         dict(facecolor="darkgray", edgecolor="black", linewidth=1, hatch="..")),
        ("CIE + SCHED_DEADLINE", r2_data,
         dict(facecolor="lightgray", edgecolor="black", linewidth=1, hatch="//")),
    ]
    handles = []
    for k, (label, data, boxprops) in enumerate(series):
        vals = [data.get(tu, []) for tu in TU_BOX]
        bp = ax.boxplot(vals, positions=positions + (k - 1) * width,
                        boxprops=boxprops, **common)
        handles.append(bp["boxes"][0])

    if args.log_y:
        ax.set_yscale("log")
        # extend the bottom to the decade below the smallest sample so that
        # its power-of-ten label appears on the axis
        gmin = min(min(d[tu]) for _, d, _ in series for tu in TU_BOX if tu in d)
        ax.set_ylim(bottom=10 ** np.floor(np.log10(gmin)))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{tu}" for tu in TU_BOX])
    ax.set_xlabel("Total Utilization", fontsize=15)
    ax.set_ylabel("Response Time [$\\mu$s]", fontsize=15)
    # single row above the axes: an in-axes legend would occlude the
    # SCHED_DEADLINE outliers once the figure is this short
    ax.legend(handles, [s[0] for s in series], fontsize=11, loc="lower left",
              bbox_to_anchor=(0, 1.0, 1, 0.12), ncol=3, mode="expand",
              borderaxespad=0, frameon=False, handlelength=1.6,
              columnspacing=1.0)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        out = f"{args.out_prefix}response_time_comparison_3way.{ext}"
        plt.savefig(out, dpi=150)
        print(f"wrote {out}")

    # ---- deadline miss ratio ------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, miss, marker, color in [
        ("Awkernel - GEDF", aw_miss, "o", "#4C72B0"),
        ("YASMIN - G-EDF", ya_miss, "^", "#55A868"),
        ("CIE + SCHED_DEADLINE", r2_miss, "s", "#DD8452"),
    ]:
        ys = [miss.get(tu, np.nan) * 100 for tu in TU_VALUES]
        ax.plot(TU_VALUES, ys, marker=marker, label=label, color=color)
    ax.set_xlabel("Total Utilization")
    ax.set_ylabel("Deadline Miss Ratio [%]")
    ax.set_xticks(TU_VALUES)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    out = f"{args.out_prefix}deadline_miss_ratio_comparison_3way.png"
    plt.savefig(out, dpi=150)
    print(f"wrote {out}")

    # ---- summary table -------------------------------------------------
    print("\nTU    system                med[us]    p99[us]    miss[%]    n")
    for tu in TU_VALUES:
        for label, data, miss in [("awkernel", aw_data, aw_miss),
                                  ("ros2-cie", r2_data, r2_miss),
                                  ("yasmin  ", ya_data, ya_miss)]:
            if tu in data and len(data[tu]):
                v = np.asarray(data[tu])
                print(f"{tu:<5} {label:<20} {np.median(v):>9.0f} "
                      f"{np.percentile(v, 99):>10.0f} "
                      f"{miss[tu] * 100:>9.2f} {len(v):>6}")


if __name__ == "__main__":
    main()
