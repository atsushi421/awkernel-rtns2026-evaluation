#!/usr/bin/env python3
"""
Box plot visualization for Release Pub/Sub latency data.

Reads parsed pubsub CSV file and creates box plots (Overall & By Node).
Filters data: Index != 0, NODE-ID in [0, 1, 4], and excludes (Index == 1 & NODE-ID == 0).
Converts ns to μs for readability.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Path Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

# Input file path
INPUT_CSV = ROOT_DIR / "evaluation_data/data_basic_evaluation/release/(release)GEDF_TU20.csv"

# Output PDF paths
OUTPUT_PDF_ALL = ROOT_DIR / "outputs/pubsub_release_to_enqueue.pdf"
OUTPUT_PDF_NODE = ROOT_DIR / "outputs/pubsub_release_to_enqueue_by_node.pdf"

# Label for the aggregated box plot
CUSTOM_LABEL = "Awkernel"
# ---------------------------------------------------------------------------


def load_csv(file_path: Path) -> pd.DataFrame:
    """Load CSV file with fallback encoding handling."""
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


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter data according to requirements:
    - Exclude Index == 0
    - Include only NODE-ID in [0, 1, 4]
    - Exclude Index == 1 AND NODE-ID == 0
    """
    df_filtered = df[df["Index"] != 0].copy()
    df_filtered = df_filtered[df_filtered["NODE-ID"].isin([0, 1, 4])].copy()
    df_filtered = df_filtered[
        ~((df_filtered["Index"] == 1) & (df_filtered["NODE-ID"] == 0))
    ].copy()

    print(f"Original records: {len(df)}")
    print(f"After filtering: {len(df_filtered)}")
    return df_filtered


def create_boxplot(df: pd.DataFrame, label: str, output_path: Path):
    """Create a single aggregated box plot using shared config."""
    # Convert ns to μs
    data_us = df["duration"] / 1000.0

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_DOUBLE, dpi=plot_config.DPI)


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
    ax.set_xlabel(" ")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    plot_config.apply_common_layout(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved aggregated plot to {output_path}")
    plt.close()


def create_boxplot_by_node(df: pd.DataFrame, output_path: Path):
    """Create separate box plots for each node ID using wide config."""
    df_us = df.copy()
    df_us["Latency_us"] = df_us["duration"] / 1000.0

    nodes = sorted(df_us["NODE-ID"].dropna().unique())
    data_by_node = [
        df_us[df_us["NODE-ID"] == node]["Latency_us"].values for node in nodes
    ]

    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_DOUBLE, dpi=plot_config.DPI)


    hatch_patterns = ['', '//', 'xx', '...', 'oo', '++']
    colors = ['white', 'lightgray', 'white', 'lightgray', 'white', 'lightgray']
    bp = ax.boxplot(
        data_by_node,
        tick_labels=[f"Node {int(node)}" for node in nodes],
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

    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(facecolor=colors[i % len(colors)], hatch=hatch_patterns[i % len(hatch_patterns)], edgecolor='#1f3c88', label=f'Node {int(nodes[i])}')
        for i in range(len(nodes))
    ]
    ax.legend(handles=legend_handles, loc='upper right', title='Node')

    ax.set_ylabel("Latency from release to enqueue (μs)")
    ax.set_xlabel("Node ID")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    for i, node in enumerate(nodes):
        count = len(df_us[df_us["NODE-ID"] == node])
        ax.text(
            i + 1,
            ax.get_ylim()[1] * 0.95,
            f"n={count}",
            ha="center",
            fontsize=plot_config.FONT_ANNOT,
            style="italic",
        )

    plot_config.apply_common_layout(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="pdf")
    print(f"Saved Node-separated plot to {output_path}")
    plt.close()


def main():
    print(f"Processing pubsub release data...")
    df = load_csv(INPUT_CSV)

    required_cols = ["Index", "NODE-ID", "duration"]
    if not all(col in df.columns for col in required_cols):
        print(f"Error: Missing columns. Required: {required_cols}")
        sys.exit(1)

    df_filtered = filter_data(df)

    if df_filtered.empty:
        print("Error: No data left after filtering.")
        sys.exit(1)

    create_boxplot(df_filtered, label=CUSTOM_LABEL, output_path=OUTPUT_PDF_ALL)
    create_boxplot_by_node(df_filtered, output_path=OUTPUT_PDF_NODE)


if __name__ == "__main__":
    main()
