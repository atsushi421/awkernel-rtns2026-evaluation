#!/usr/bin/env python3
"""
Box plot visualization for Preemption timing data.

Reads parsed preemption CSV file and creates box plots (Overall & By CPU).
Converts nanoseconds (ns) to microseconds (μs) for readability.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Path Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

# Input CSV Path
INPUT_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/preemption/preemption_parsed.csv"

# Output PDF Paths
OUTPUT_PDF_ALL = ROOT_DIR / "outputs/preemption.pdf"
OUTPUT_PDF_CPU = ROOT_DIR / "outputs/preemption_by_cpu.pdf"

CUSTOM_LABEL = "Awkernel"
# ---------------------------------------------------------------------------


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
        print(f"Error reading CSV file: {e}")
        sys.exit(1)


def create_boxplot(df: pd.DataFrame, label: str, output_path: Path):
    """Create an aggregated box plot for all CPUs."""
    # Convert ns to μs
    data_us = df["Diff(ns)"].dropna() / 1000.0

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_TRIPLE, dpi=plot_config.DPI)


    box = ax.boxplot(
        data_us,
        tick_labels=[label],
        vert=True,
        patch_artist=True,
        widths=0.5,
        boxprops=dict(edgecolor="black", linewidth=1.5),
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(color="black", linewidth=1.5),
        capprops=dict(color="black", linewidth=1.5),
        flierprops=dict(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=5, alpha=0.5),
    )

    box['boxes'][0].set_facecolor('white')
    box['boxes'][0].set_hatch('')
    box['boxes'][0].set_edgecolor('black')

    ax.set_ylabel("Latency [μs]")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    plot_config.apply_common_layout(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved aggregated plot to {output_path}")
    plt.close()


def create_boxplot_by_cpu(df: pd.DataFrame, output_path: Path):
    """Create a box plot separated by CPU_ID."""
    df_us = df.copy()
    df_us["Diff(μs)"] = df_us["Diff(ns)"] / 1000.0

    cpus = sorted(df_us["CPU_ID"].dropna().unique())
    data_by_cpu = [df_us[df_us["CPU_ID"] == cpu]["Diff(μs)"].values for cpu in cpus]

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_WIDE, dpi=plot_config.DPI)


    hatch_patterns = ['', '//', 'xx', '..', '++', 'oo']
    colors = ['white', 'lightgray', 'white', 'lightgray', 'white', 'lightgray']
    bp = ax.boxplot(
        data_by_cpu,
        tick_labels=[f"CPU {int(cpu)}" for cpu in cpus],
        vert=True,
        patch_artist=True,
        widths=0.6,
        boxprops=dict(edgecolor="black", linewidth=1.5),
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(color="black", linewidth=1.5),
        capprops=dict(color="black", linewidth=1.5),
        flierprops=dict(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=5, alpha=0.5),
    )
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(colors[i % len(colors)])
        patch.set_hatch(hatch_patterns[i % len(hatch_patterns)])
        patch.set_edgecolor('black')

    ax.set_ylabel("Preemption Latency (μs)")
    ax.set_xlabel("CPU ID")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    for i, cpu in enumerate(cpus):
        count = len(df_us[df_us["CPU_ID"] == cpu])
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
    print(f"Saved CPU-separated plot to {output_path}")
    plt.close()


def main():
    plot_config.apply_font("triple")

    print(f"Processing preemption data...")
    print(f"  Source: {INPUT_CSV.name}")

    df = load_csv(INPUT_CSV)

    if "CPU_ID" not in df.columns or "Diff(ns)" not in df.columns:
        print("Error: CSV file must contain 'CPU_ID' and 'Diff(ns)' columns")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    create_boxplot(df, label=CUSTOM_LABEL, output_path=OUTPUT_PDF_ALL)
    create_boxplot_by_cpu(df, output_path=OUTPUT_PDF_CPU)


if __name__ == "__main__":
    main()
