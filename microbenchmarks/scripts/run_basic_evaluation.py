#!/usr/bin/env python3
"""
Master execution script for basic evaluation plots.
Runs all plotting scripts located in src/basic_evaluation/ and saves results to outputs/.

Usage:
    python scripts/run_basic_evaluation.py
"""

import subprocess
import sys
from pathlib import Path

# --- Path Configuration ---
# Get the project root (one level up from 'scripts')
ROOT_DIR = Path(__file__).resolve().parent.parent
CODE_DIR = ROOT_DIR / "src" / "basic_evaluation"

# List of scripts to execute in order
PLOTTING_SCRIPTS = [
    "plot_pubsub_latency_median.py",
    "plot_release_to_enqueue.py",
    "plot_cycle_deviation.py",
    "plot_preemption.py",
    "plot_context_switch.py",
]


def run_script(script_name: str):
    """Executes a single python script and reports its status."""
    script_path = CODE_DIR / script_name

    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_path}")
        return False

    print(f"[RUNNING] {script_name}...")

    try:
        # Run the script using the current Python interpreter
        # Setting check=True will raise an error if the script fails
        subprocess.run([sys.executable, str(script_path)], check=True)
        print(f"[SUCCESS] Finished {script_name}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAILED]  {script_name} exited with error: {e}\n")
        return False


def main():
    print("=" * 60)
    print("Starting Global Graph Generation")
    print(f"Project Root: {ROOT_DIR}")
    print("=" * 60 + "\n")

    # Ensure outputs directory exists
    (ROOT_DIR / "outputs").mkdir(parents=True, exist_ok=True)

    success_count = 0
    for script in PLOTTING_SCRIPTS:
        if run_script(script):
            success_count += 1

    print("=" * 60)
    print(
        f"Generation Complete: {success_count}/{len(PLOTTING_SCRIPTS)} scripts succeeded."
    )
    print(f"Check the outputs in: {ROOT_DIR / 'outputs'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
