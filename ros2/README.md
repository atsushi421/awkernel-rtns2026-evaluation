# ROS 2 Task Set

A performance benchmarking tool that simulates callback DAGs (Directed Acyclic Graphs) for measuring real-time scheduling behavior.

## Setup

### 1. Clone the repository

```bash
git clone --recursive https://github.com/atsushi421/awkernel-rtns2026-evaluation.git
cd awkernel-rtns2026-evaluation/ros2
```

### 2. Install dependencies

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
bash agnocast/scripts/setup
```

### 4. Build

```bash
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release --base-paths . agnocast/src --packages-up-to ros2_task_set agnocast_components
```

## Run

Place `dags.yaml` (see [Usage](#usage)) in the current directory, then:

```bash
source install/setup.bash
ros2 launch ros2_task_set dummy_node.launch.xml
```

## Run Benchmark

`run_benchmark.sh` iterates over the five DAG cases in `ActualDAGSet2/` and records response-time CSVs. `benchmark_results/20260227_130120` holds the results of the paper.

```bash
source install/setup.bash
bash run_benchmark.sh
```

An optional argument specifies a runtime buffer (in nanoseconds) to add to each SCHED_DEADLINE runtime parameter:

```bash
bash run_benchmark.sh 500000
```

Results are saved to `benchmark_results/`.

## Usage

### DAG YAML format

Create a YAML file that describes the desired DAG structure. An example is given below.

```yaml
callbacks:
  # DAG0
  - id: 0
    execution_time_ms: 100
    period_ms: 200
  - id: 1
    execution_time_ms: 50
  - id: 2
    execution_time_ms: 30

  # DAG1
  - id: 3
    execution_time_ms: 20
    period_ms: 100

  # DAG2
  - id: 4
    execution_time_ms: 100
    period_ms: 1000

  # DAG3
  - id: 5
    execution_time_ms: 30
    period_ms: 100

communications:
  - from: 0
    to: 1
  - from: 1
    to: 2
```

- Callbacks with `period_ms` become **timers** (DAG roots).
- Callbacks without it become **subscriptions** triggered via `communications` edges.
- A callback can have at most two incoming edges. If it has two, `message_filters::Synchronizer` with the `ExactTime` policy fires the callback after all upstream messages arrive.
- Optional `deadline_ms` enables response-time tracking and deadline-miss statistics printed at shutdown.

### CIE thread configuration

Each case in `ActualDAGSet2/` has a `cie_case_*.yaml` file. The file sets the scheduling policy (for example `SCHED_DEADLINE` or `SCHED_FIFO`) and the CPU affinity of each thread through `agnocast_cie_thread_configurator`.

### Execution time logs

The benchmark writes execution times to CSV files in `exec_time_logs/`.

### Response time comparison

`../plot/plot_comparison.py` draws Fig. 4 from the results of Awkernel, ROS 2, and YASMIN. The README at the top of this repository shows the command.
