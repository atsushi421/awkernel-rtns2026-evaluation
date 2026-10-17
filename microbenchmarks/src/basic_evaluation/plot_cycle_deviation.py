#!/usr/bin/env python3
"""
Box plot visualization for cycle deviation data.

Reads parsed CSV files and creates box plots for the column "Cycle_Deviation_ns".
Converts nanoseconds (ns) to microseconds (μs) for readability.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

# --- Path Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(ROOT_DIR / "src"))
from utils import plot_config

# Output PDF path
OUTPUT_PDF = ROOT_DIR / "outputs/cycle_deviation.pdf"

# Target column name in the CSV
TARGET_COLUMN = "Cycle_Deviation_ns"

# Data Sources Configuration
FILE_CONFIG: List[Dict[str, Any]] = [
    {
        "label": "Awkernel",
        "path": ROOT_DIR / "evaluation_data/data_basic_evaluation/cycle_deviation/RD-Gen(GEDF)_TU20_60_2.csv",
    },
]


def load_series(config: Dict[str, Any]) -> np.ndarray:
    """Load the target column from a CSV file with fallback encoding handling."""
    path = Path(config["path"])

    if not path.exists():
        print(f"Error: Missing file: {path}")
        sys.exit(1)

    try:
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="shift_jis")
    except Exception as e:
        print(f"Error reading CSV file '{path}': {e}")
        sys.exit(1)

    if TARGET_COLUMN not in df.columns:
        print(f"Error: Column '{TARGET_COLUMN}' not found in {path.name}.")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    # Clean data: remove non-numeric characters and convert to float
    clean_str_series = (
        df[TARGET_COLUMN].astype(str).str.replace(r"[^\d.-]", "", regex=True)
    )
    numeric_series = pd.to_numeric(clean_str_series, errors="coerce").dropna()

    if numeric_series.empty:
        print(
            f"Error: No valid numeric data in column '{TARGET_COLUMN}' for {path.name}"
        )
        sys.exit(1)

    # Convert from nanoseconds (ns) to microseconds (μs)
    return numeric_series.to_numpy() / 1000.0


def make_boxplot(data: List[np.ndarray], labels: List[str]) -> plt.Figure:
    """Create the box plot figure using shared plot_config."""
    fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_TRIPLE, dpi=plot_config.DPI)


    n_box = len(data)
    bp = ax.boxplot(
        data,
        tick_labels=labels,
        vert=True,
        patch_artist=True,
        widths=0.6,
        medianprops={"color": "black", "linewidth": 1.3},
        whiskerprops={"color": "black", "linewidth": 1.1},
        capprops={"color": "black", "linewidth": 1.1},
        flierprops={
            "marker": "o",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": 3,
            "alpha": 0.5,
        },
    )

    hatch_patterns = ["", "//", "xx", "..", "++", "oo"]
    colors = ["white", "lightgray", "white", "lightgray", "white", "lightgray"]
    for idx, patch in enumerate(bp["boxes"]):
        if n_box == 1:
            patch.set_facecolor("white")
            patch.set_hatch("")
        else:
            patch.set_facecolor(colors[idx % len(colors)])
            patch.set_hatch(hatch_patterns[idx % len(hatch_patterns)])
        patch.set_edgecolor("black")
        patch.set_alpha(1.0)

    ax.set_ylabel("Jitter [μs]")

    # Linear scale with 10 μs intervals
    ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{int(y)}"))

    # Range adjustment
    ax.set_ylim(bottom=0, top=100)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.grid(axis="y", which="major", linestyle="--", alpha=0.35)

    plot_config.apply_common_layout(fig)

    return fig


def main() -> None:
    plot_config.apply_font("triple")

    data: List[np.ndarray] = []
    labels: List[str] = []

    print("Processing cycle deviation data...")
    for cfg in FILE_CONFIG:
        print(f"  Loading {cfg['label']}...")
        series = load_series(cfg)
        data.append(series)
        labels.append(cfg["label"])
        print(f"    -> Loaded {len(series)} rows from {cfg['path'].name}")

    # Ensure output directory exists
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    fig = make_boxplot(data, labels)
    fig.savefig(OUTPUT_PDF)
    plt.close(fig)
    print(f"Saved cycle deviation box plot to {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
