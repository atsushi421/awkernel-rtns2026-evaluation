#!/usr/bin/env python3
"""
Compute median of pubsub_latency for multiple CSV files and plot as PDF.
Compares two configurations (Arc-based vs non-Arc-based) on the same plot.

- Data is loaded from evaluation_data/data_basic_evaluation/datasize/
- Latency is converted from ns to ms.
- X-axis labels are formatted (e.g., 1024 -> 1K).
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt

# --- Path Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

# Input Data Directory
DATA_DIR = ROOT_DIR / "evaluation_data/data_basic_evaluation/datasize"

# CSV files keyed by data size (bytes) - Arc-based version
DATA_FILES_ARC: Dict[int, Path] = {
    256: DATA_DIR / "test_dag_datasize256_arc.csv",
    512: DATA_DIR / "test_dag_datasize512_arc.csv",
    1024: DATA_DIR / "test_dag_datasize1024_arc.csv",
    2048: DATA_DIR / "test_dag_datasize2048_arc.csv",
    4096: DATA_DIR / "test_dag_datasize4096_arc.csv",
    8192: DATA_DIR / "test_dag_datasize8192_arc.csv",
    16384: DATA_DIR / "test_dag_datasize16384_arc.csv",
    32768: DATA_DIR / "test_dag_datasize32768_arc.csv",
    65536: DATA_DIR / "test_dag_datasize65536_arc.csv",
}

# CSV files keyed by data size (bytes) - Non-Arc version
DATA_FILES_NOARC: Dict[int, Path] = {
    256: DATA_DIR / "test_dag_datasize256.csv",
    512: DATA_DIR / "test_dag_datasize512.csv",
    1024: DATA_DIR / "test_dag_datasize1024.csv",
    2048: DATA_DIR / "test_dag_datasize2048.csv",
    4096: DATA_DIR / "test_dag_datasize4096.csv",
    8192: DATA_DIR / "test_dag_datasize8192.csv",
    16483: DATA_DIR / "test_dag_datasize16483.csv",
    32966: DATA_DIR / "test_dag_datasize32966.csv",
    65932: DATA_DIR / "test_dag_datasize65932.csv",
}

# Column and Unit settings
LATENCY_COLUMN = "pubsub_latency"
LATENCY_DIVISOR = 1_000_000.0  # convert ns to ms
LATENCY_UNIT = "ms"

# Output PDF path
OUTPUT_PDF = ROOT_DIR / "outputs/pubsub_latency_median_comparison.pdf"


def format_size(size: int) -> str:
    """Format bytes to human-friendly label (e.g., 1024 -> 1K)."""
    if size >= 1024:
        return f"{int(size/1024)}K"
    return str(size)


def load_medians(
    data_files: Dict[int, Path], label: str
) -> Tuple[List[int], List[float], List[int]]:
    """Load median values from a set of CSV files."""
    data_sizes = []
    medians_ms = []
    failed_sizes = []

    for size, path in sorted(data_files.items()):
        if not path.exists():
            print(f"Warning: File not found for {label} size {size}: {path.name}")
            failed_sizes.append(size)
            continue

        try:
            try:
                df = pd.read_csv(path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="shift_jis")

            if LATENCY_COLUMN in df.columns:
                series = df[LATENCY_COLUMN].dropna()
            else:
                required_cols = ["Index", "Node_ID", "Subscribe_Time", "Publish_Time"]
                if not all(col in df.columns for col in required_cols):
                    failed_sizes.append(size)
                    continue

                df_filtered = df[
                    (df["Index"] >= 1) & (df["Node_ID"].isin([1, 2, 3, 4]))
                ].copy()
                pub_map = {
                    (r.Index, r.Node_ID): r.Publish_Time
                    for r in df.itertuples(index=False)
                }

                latencies = []
                for row in df_filtered.itertuples(index=False):
                    src_id = {1: 0, 2: 1, 3: 1, 4: 3}.get(row.Node_ID)
                    if src_id is not None and (row.Index, src_id) in pub_map:
                        latencies.append(
                            row.Subscribe_Time - pub_map[(row.Index, src_id)]
                        )

                series = pd.Series(latencies)

            if series.empty:
                failed_sizes.append(size)
                continue

            medians_ms.append(series.median() / LATENCY_DIVISOR)
            data_sizes.append(size)

        except Exception as e:
            print(f"Error reading {path.name}: {e}")
            failed_sizes.append(size)

    return data_sizes, medians_ms, failed_sizes


def main() -> None:
    print("Processing pubsub latency data...")
    sizes_arc, medians_arc, failed_arc = load_medians(DATA_FILES_ARC, "Arc")
    sizes_noarc, medians_noarc, failed_noarc = load_medians(DATA_FILES_NOARC, "No Arc")

    if not sizes_arc or not sizes_noarc:
        print("Error: Failed to load data from one or both configurations.")
        return

    # Create unified X-axis labels
    all_sizes = sorted(set(sizes_arc) | set(sizes_noarc))
    formatted_labels = []
    seen = set()
    for s in all_sizes:
        fmt = format_size(s)
        if fmt not in seen:
            formatted_labels.append(fmt)
            seen.add(fmt)

    label_to_x = {lbl: i for i, lbl in enumerate(formatted_labels)}
    x_arc = [label_to_x[format_size(s)] for s in sizes_arc]
    x_noarc = [label_to_x[format_size(s)] for s in sizes_noarc]

    # Plotting
    plot_config.apply_font("half")
    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_HALF, dpi=plot_config.DPI)

    ax.plot(
        x_arc,
        medians_arc,
        marker="o",
        color="#1f3c88",
        linewidth=1.5,
        markersize=4,
        label="Arc-based (Awkernel)",
    )
    ax.plot(
        x_noarc,
        medians_noarc,
        marker="s",
        color="#E63946",
        linewidth=1.5,
        markersize=4,
        label="Non-Arc",
    )

    ax.set_xticks(range(len(formatted_labels)))
    ax.set_xticklabels(formatted_labels, rotation=45)
    ax.set_xlabel("Data Size [byte]")
    ax.set_ylabel(f"Latency [{LATENCY_UNIT}]")

    ax.set_ylim(0.0, 1.5)
    ax.set_yticks([0.0, 0.5, 1.0, 1.5])
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    ax.legend(loc="upper left", fontsize=6)

    plot_config.apply_common_layout(fig)
    fig.subplots_adjust(bottom=0.325, top=0.90)

    # Save output
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PDF, format="pdf")
    print(f"Saved comparison plot to {OUTPUT_PDF}")

    if failed_arc or failed_noarc:
        print(f"  Note: Failed sizes Arc:{failed_arc}, NoArc:{failed_noarc}")


if __name__ == "__main__":
    main()
