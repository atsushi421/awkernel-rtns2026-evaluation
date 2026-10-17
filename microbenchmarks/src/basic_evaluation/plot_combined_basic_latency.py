#!/usr/bin/env python3
"""Combined boxplot for four basic-evaluation latency metrics.

Renders Release→Enqueue, Preemption, Ctx-Sw (yield) and Ctx-Sw (run_main)
on a single Y axis in microseconds. Produces both a linear-scale and a
log-scale PDF so the paper can adopt whichever reads better.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

RELEASE_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/release/(release)GEDF_TU20.csv"
PREEMPTION_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/preemption/preemption_parsed.csv"
CTX_YIELD_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/context/context_switch_parsed_TU20_pub5_9.csv"
CTX_MAIN_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/context/context_switch_parsed_TU20_pub5_9_main.csv"

OUTPUT_LINEAR = ROOT_DIR / "outputs/basic_latency_combined.pdf"
OUTPUT_LOG = ROOT_DIR / "outputs/basic_latency_combined_log.pdf"

LABELS = ["Release→Enqueue", "Preemption", "Ctx-Sw (yield)", "Ctx-Sw (run_main)"]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"Error: input file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="shift_jis")


def release_to_enqueue_us() -> pd.Series:
    df = load_csv(RELEASE_CSV)
    df = df[df["Index"] != 0]
    df = df[df["NODE-ID"].isin([0, 1, 4])]
    df = df[~((df["Index"] == 1) & (df["NODE-ID"] == 0))]
    return df["duration"].dropna() / 1000.0


def preemption_us() -> pd.Series:
    df = load_csv(PREEMPTION_CSV)
    return df["Diff(ns)"].dropna() / 1000.0


def _diff_column(df: pd.DataFrame) -> str:
    for col in df.columns:
        if "diff" in col.lower():
            return col
    print(f"Error: no 'diff' column found. Columns: {list(df.columns)}", file=sys.stderr)
    sys.exit(1)


def context_us(path: Path) -> pd.Series:
    df = load_csv(path)
    col = _diff_column(df)
    return df[col].dropna() / 1000.0


def render(series_list, labels, output_path: Path, log_scale: bool):
    fig, ax = plt.subplots(
        figsize=plot_config.FIGSIZE_HALF,
        dpi=plot_config.DPI,
    )

    bp = ax.boxplot(
        [s.values for s in series_list],
        tick_labels=labels,
        vert=True,
        patch_artist=True,
        widths=0.5,
        boxprops=dict(edgecolor="black", linewidth=1.0),
        medianprops=dict(color="black", linewidth=1.5),
        whiskerprops=dict(color="black", linewidth=1.0),
        capprops=dict(color="black", linewidth=1.0),
        flierprops=dict(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=3, alpha=0.5),
    )
    for patch in bp["boxes"]:
        patch.set_facecolor("white")
        patch.set_hatch("")
        patch.set_edgecolor("black")

    ax.set_ylabel("Latency [μs]")
    plt.setp(ax.get_xticklabels(), fontsize=7, rotation=30, ha="right")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    if log_scale:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0)

    plot_config.apply_common_layout(fig)
    fig.subplots_adjust(left=0.28, bottom=0.40, top=0.92)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved {output_path}")
    plt.close()


def main():
    plot_config.apply_font("half")

    series = [
        release_to_enqueue_us(),
        preemption_us(),
        context_us(CTX_YIELD_CSV),
        context_us(CTX_MAIN_CSV),
    ]

    for label, s in zip(LABELS, series):
        print(f"{label}: n={len(s)}  median={s.median():.3f} μs")

    render(series, LABELS, OUTPUT_LINEAR, log_scale=False)
    render(series, LABELS, OUTPUT_LOG, log_scale=True)


if __name__ == "__main__":
    main()
