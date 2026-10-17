#!/usr/bin/env python3
"""
Box plot visualization for Context Switch data.

This script compares two context switch paths (yield and run_main).
It generates both aggregated and by-CPU comparison plots.
Latency values are converted from ns to ms.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Path Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

# Input CSV Paths
INPUT_CSV1 = ROOT_DIR / "evaluation_data/data_basic_evaluation/context/context_switch_parsed_TU20_pub5_9.csv"
INPUT_CSV2 = ROOT_DIR / "evaluation_data/data_basic_evaluation/context/context_switch_parsed_TU20_pub5_9_main.csv"

# Labels for the two paths
LABEL1 = "yield"
LABEL2 = "run_main"

# Output PDF Paths
OUTPUT_PDF_ALL = ROOT_DIR / "outputs/context_switch_comparison.pdf"
OUTPUT_PDF_CPU = ROOT_DIR / "outputs/context_switch_comparison_by_cpu.pdf"


def load_csv(file_path: Path) -> pd.DataFrame:
    """Load CSV with fallback encoding handling."""
    if not file_path.exists():
        print(f"Error: Input file '{file_path}' not found.")
        sys.exit(1)

    try:
        try:
            return pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding="shift_jis")
    except Exception as e:
        print(f"Error reading CSV file '{file_path}': {e}")
        sys.exit(1)


def get_columns(df: pd.DataFrame) -> tuple:
    """Automatically identify the latency (diff) and CPU ID columns."""
    diff_col, cpu_col = None, None
    for col in df.columns:
        if "diff" in col.lower():
            diff_col = col
        if "cpu" in col.lower() and "id" in col.lower():
            cpu_col = col
    return diff_col, cpu_col


def create_comparison_boxplot(df1: pd.DataFrame, df2: pd.DataFrame, output_path: Path):
    """Create an aggregated comparison box plot for the two paths."""
    diff_col1, _ = get_columns(df1)
    diff_col2, _ = get_columns(df2)

    if diff_col1 is None or diff_col2 is None:
        print("Error: Could not find 'Diff' column in one or both files")
        sys.exit(1)

    # Convert ns to ms
    data1 = df1[diff_col1].dropna().values / 1000000.0
    data2 = df2[diff_col2].dropna().values / 1000000.0

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_TRIPLE, dpi=plot_config.DPI)


    bp = ax.boxplot(
        [data1, data2],
        tick_labels=[LABEL1, LABEL2],
        vert=True,
        patch_artist=True,
        widths=0.5,
        boxprops=dict(edgecolor="black", linewidth=1.5),
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(color="black", linewidth=1.5),
        capprops=dict(color="black", linewidth=1.5),
        flierprops=dict(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=5, alpha=0.5),
    )
    # yield: white, run_main: gray+line
    bp["boxes"][0].set_facecolor("white")
    bp["boxes"][0].set_hatch("")
    bp["boxes"][0].set_edgecolor("black")
    bp["boxes"][1].set_facecolor("#D2D2D2")
    bp["boxes"][1].set_hatch("//")
    bp["boxes"][1].set_edgecolor("black")

    ax.set_ylabel("Latency [ms]")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    plot_config.apply_common_layout(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved aggregated comparison plot to {output_path}")
    plt.close()


def create_comparison_boxplot_by_cpu(
    df1: pd.DataFrame, df2: pd.DataFrame, output_path: Path
):
    """Create a CPU-separated comparison box plot."""
    diff_col1, cpu_col1 = get_columns(df1)
    diff_col2, cpu_col2 = get_columns(df2)

    if None in (diff_col1, cpu_col1, diff_col2, cpu_col2):
        print("Error: Could not find 'Diff' or 'CPU_ID' columns")
        sys.exit(1)

    cpu_ids1 = set(df1[cpu_col1].dropna().unique())
    cpu_ids2 = set(df2[cpu_col2].dropna().unique())
    cpu_ids = sorted(cpu_ids1 | cpu_ids2)

    data_list = []
    labels_list = []
    counts = []

    for cpu_id in cpu_ids:
        cpu_data1 = df1[df1[cpu_col1] == cpu_id][diff_col1].dropna().values
        counts.append(len(cpu_data1))
        data_list.append(cpu_data1 / 1000000.0 if len(cpu_data1) > 0 else [0])
        labels_list.append(f"{LABEL1}\nCPU {int(cpu_id)}")

        cpu_data2 = df2[df2[cpu_col2] == cpu_id][diff_col2].dropna().values
        counts.append(len(cpu_data2))
        data_list.append(cpu_data2 / 1000000.0 if len(cpu_data2) > 0 else [0])
        labels_list.append(f"{LABEL2}\nCPU {int(cpu_id)}")

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_WIDE, dpi=plot_config.DPI)

    bp = ax.boxplot(
        data_list,
        tick_labels=labels_list,
        vert=True,
        patch_artist=True,
        widths=0.6,
        boxprops=dict(alpha=0.7),
        medianprops=dict(color="#E63946", linewidth=2),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        flierprops=dict(marker="o", markerfacecolor="#E63946", markersize=5, alpha=0.5),
    )

    # yield: white, run_main: gray+line
    for i, patch in enumerate(bp["boxes"]):
        if i % 2 == 0:
            patch.set_facecolor("white")
            patch.set_hatch("")
        else:
            patch.set_facecolor("#cccccc")
            patch.set_hatch("//")
        patch.set_edgecolor("black")

    ax.set_ylabel("Latency (ms)")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    # Annotate sample counts
    for i, count in enumerate(counts):
        if count > 0:
            ax.text(
                i + 1,
                ax.get_ylim()[1] * 0.95,
                f"n={count}",
                ha="center",
                fontsize=plot_config.FONT_TRIPLE["annot"],
                style="italic",
            )

    plot_config.apply_common_layout(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved CPU-separated comparison plot to {output_path}")
    plt.close()


def main():
    plot_config.apply_font("triple")

    print("Processing context switch data...")
    print(f"  Source 1: {INPUT_CSV1.name}")
    print(f"  Source 2: {INPUT_CSV2.name}")

    df1 = load_csv(INPUT_CSV1)
    df2 = load_csv(INPUT_CSV2)

    create_comparison_boxplot(df1, df2, OUTPUT_PDF_ALL)
    create_comparison_boxplot_by_cpu(df1, df2, OUTPUT_PDF_CPU)


if __name__ == "__main__":
    main()
