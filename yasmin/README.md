# YASMIN baseline for Fig. 4

This directory runs the five DAG sets of the ROS 2 baseline on YASMIN (Rouxel et al., Middleware 2021). YASMIN runs global EDF in user space on Linux.

## YASMIN source

This repository does not include the YASMIN source. Clone YASMIN into `coordinationruntime/`, and apply the patch of this directory:

```
git clone https://bitbucket.org/uva-sne/coordinationruntime.git coordinationruntime
cd coordinationruntime
git checkout e6fb877593a5a4acf917b2ecb4a9c2a5ffd6c000
git apply ../patches/yasmin-gedf-fixes.patch
```

YASMIN uses the GPLv3 license. The patch modifies YASMIN, so the patch is under the GPLv3 license too.

## Changes of the patch

The public YASMIN has an EDF setting, but it does not run as global EDF. Each change of the patch makes the baseline stronger:

1. EDF priorities: the patch sets the priority of a task to the absolute deadline of its job at each periodic release. Without the patch, no code sets the EDF priority.
2. Job deadline: a subtask that a channel activates takes the priority of the producer. All subtasks of a job then share the absolute deadline of the job.
3. Preemption: `y_activate_task` requests a preemption check. Without the patch, only the periodic scheduler requests preemption.
4. Sleep: `yas_utils_nanosleep` no longer spins for the same time again after `clock_nanosleep`. Without the patch, the period doubles.
5. Semaphore: if the preemption check does not pop a task, it now returns the semaphore. Without the patch, a queued task waits until the next push.

## Procedure

1. Generate one application for each DAG set. The command reads `../ros2/ActualDAGSet2` and writes `gen/`.

    ```
    python3 generate_case.py
    ```

2. On the Raspberry Pi 4, build the applications.

    ```
    bash build_all.sh
    ```

3. On the Raspberry Pi 4, run the applications. One case takes 60 s.

    ```
    sudo bash run_benchmark.sh
    ```

    While the script runs, it disables the real-time throttling of Linux and sets the performance governor on all CPUs. It restores both at the end.

4. The results go to `benchmark_results/<timestamp>/TU_<tu>/case_<n>/`. `benchmark_results/20260821_041727` holds the results of the paper.

## Equivalence with the ROS 2 baseline

| Item | ROS 2 (`../ros2/src/dummy_node.cpp`) | YASMIN (generated code) |
| --- | --- | --- |
| Workload | `ActualDAGSet2/TU_*/case_*.yaml` | Same files |
| Source | Wall timer callback | Periodic task, released by a thread on CPU 0 |
| Edge | Topic with a subscription of depth 1 | FIFO channel with a capacity of one token |
| Join | `message_filters` ExactTime | Fires after all input channels get a token |
| Execution time | Calibrated busy loop | Calibrated busy loop of the same structure |
| Response time | Sink end minus source start | Same definition |
| Cores | Four cores | CPU 0 for releases, CPUs 1 to 3 for three workers |
| CSV | `index,response_time_us,deadline_us` | Same schema |
