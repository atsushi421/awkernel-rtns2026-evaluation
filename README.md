# Awkernel RTNS 2026 evaluation

This repository holds the code and data of the evaluation in the RTNS 2026 paper "Awkernel: RTOS Bridging DAG Scheduling Theory and Component-Oriented Real-Time Systems Practice". The Awkernel source is at https://github.com/tier4/awkernel.

The response-time comparison and the microbenchmarks ran on a Raspberry Pi 4 Model B with 4 GB of memory.

## Contents

| Directory | Paper content | Description |
| --- | --- | --- |
| `dags/` | Section 7.1, Table 5 | The nine RD-Gen DAGs of the five DAG sets |
| `awkernel/` | Fig. 4 | GEDF on Awkernel: image build, UDP log, and CSV conversion |
| `ros2/` | Fig. 4 | ROS 2 baseline with CallbackIsolatedExecutor and `SCHED_DEADLINE` |
| `yasmin/` | Fig. 4 | YASMIN baseline with global EDF in user space |
| `plot/` | Fig. 4 | Script that draws Fig. 4 from the three results |
| `microbenchmarks/` | Fig. 5, Fig. 6 | Pub/sub latency and scheduling-path latencies on Awkernel |
| `mrm/` | Fig. 8 | MRM case study: inputs, trajectory data, and plots |

Each TU value (the summed CPU load of the three DAGs) has one DAG set of three DAGs. The table in `awkernel/README.md` maps each TU to its three DAGs. `ros2/ActualDAGSet2` holds the same five sets in the format of the ROS 2 and YASMIN baselines.

## Requirements

The plot scripts need Python 3 with numpy, pandas, PyYAML, and matplotlib 3.9 or later.

## Draw the figures from the data

Fig. 4:

```
cd plot
python3 plot_comparison.py --ros2-dir ../ros2/benchmark_results/20260227_130120 \
    --yasmin-dir ../yasmin/benchmark_results/20260821_041727 --log-y
```

The default of `--awkernel-dir` is `../awkernel/evaluation_data/csv`. `response_time_comparison_3way.pdf` is Fig. 4.

Fig. 5 and Fig. 6:

```
cd microbenchmarks
python3 scripts/run_basic_evaluation.py
python3 src/basic_evaluation/plot_combined_basic_latency.py
```

`outputs/pubsub_latency_median_comparison.pdf` is Fig. 5. `outputs/basic_latency_combined_log.pdf` is Fig. 6.

Fig. 8:

```
cd mrm
python3 scripts/run_trajectory_evaluation.py
```

`inputs/` holds the IMU and velocity CSV files that the MRM port replays. `ekf_view/` holds the tools that record and compare the EKF output.

## Measure again

To measure again, follow `awkernel/README.md`, `ros2/README.md`, and `yasmin/README.md`.

Fig. 4 uses commit `6243e474` on the `fix/gedf-dag-instance-deadline` branch of the fork atsushi421/awkernel. tier4/awkernel merged this fix as PR #715 (commit `abbd2095`). The two commits differ only in the panic messages of `dag.rs`.

## Third-party code

This repository does not include the YASMIN source. `yasmin/README.md` shows how to get it and apply the patch. The ROS 2 baseline uses Agnocast as a Git submodule in `ros2/agnocast`. To get it, clone this repository with `--recursive`.
