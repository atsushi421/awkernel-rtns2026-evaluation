#!/usr/bin/env python3
"""Converts the log of the UDP report (or of print_timestamp_table() on the
UART) into the CSV layout of the Awkernel results that plot_comparison.py of
yasmin_benchmark reads.

Usage: aw_log_to_csv.py <tu10.log> <RD-Gen(GEDF3)_TU10.csv> [--tu 10]

The fixed GEDF branch prints "-" in the deadline columns, and
plot_comparison.py drops rows without a relative deadline. With --tu, the
relative deadline of each DAG is filled in from its RD-Gen YAML file. DAG-ID k
is the k-th file of the set, as in build_images.sh.
"""
import argparse
import csv
import os
import re

import yaml

ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Index | DAG-ID | Send-Outer | Recv-Outer | Latency | Absolute Deadline | Relative Deadline
ROW = re.compile(r"(\d+)" + r"\s*\|\s*(\S+)" * 6 + r"\s*$")
HEADER = ["Index", "DAG-ID", "Send-Outer", "Recv-Outer", "Latency",
          "Absolute Deadline", "Relative Deadline"]
DAGSET = os.environ.get(
    "DAGSET", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dags"))
SETS = {
    "10": ["TU=0.4/DAGs/dag_0", "TU=0.3/DAGs/dag_0", "TU=0.3/DAGs/dag_3"],
    "15": ["TU=0.5/DAGs/dag_0", "TU=0.5/DAGs/dag_7", "TU=0.5/DAGs/dag_8"],
    "20": ["TU=1/DAGs/dag_0", "TU=0.5/DAGs/dag_0", "TU=0.5/DAGs/dag_7"],
    "25": ["TU=1/DAGs/dag_0", "TU=1/DAGs/dag_2", "TU=0.5/DAGs/dag_0"],
    "30": ["TU=1/DAGs/dag_0", "TU=1/DAGs/dag_1", "TU=1/DAGs/dag_2"],
}


def deadlines_ns(tu):
    """DAG-ID (1-based, as a string) -> relative deadline in ns."""
    out = {}
    for k, name in enumerate(SETS[tu], start=1):
        with open(f"{DAGSET}/{name}.yaml") as f:
            nodes = yaml.safe_load(f)["nodes"]
        ms = next(n["end_to_end_deadline"] for n in nodes if "end_to_end_deadline" in n)
        out[str(k)] = str(ms * 1_000_000)
    return out


def convert(log_path, csv_path, tu=None):
    fill = deadlines_ns(tu) if tu else {}
    rows = {}
    with open(log_path, errors="replace") as f:
        for line in f:
            m = ROW.search(ANSI.sub("", line).rstrip())
            if m:
                row = list(m.groups())
                if row[6] == "-" and row[1] in fill:
                    row[6] = fill[row[1]]
                # A later copy of the same (index, DAG) replaces an earlier one.
                rows[(int(row[0]), row[1])] = row
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for key in sorted(rows):
            w.writerow(rows[key])
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("csv")
    ap.add_argument("--tu", choices=sorted(SETS))
    a = ap.parse_args()
    n = convert(a.log, a.csv, a.tu)
    print(f"{n} rows -> {a.csv}")
