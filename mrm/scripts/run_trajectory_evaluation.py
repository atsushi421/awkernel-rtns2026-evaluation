#!/usr/bin/env python3
"""
Runner script for trajectory evaluation plots.

Usage:
    python3 scripts/run_trajectory_evaluation.py
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

script = ROOT_DIR / "src" / "trajectory_evaluation" / "plot_trajectory.py"

result = subprocess.run(
    [sys.executable, str(script), "trajectory", "--pdf-only"],
    cwd=str(ROOT_DIR),
)
sys.exit(result.returncode)
