# Awkernel GEDF measurement for Fig. 4

This directory holds the re-measurement of GEDF on Awkernel for Fig. 4 and Section 7.2 of the RTNS 2026 camera-ready paper. The measurement ran on 2026-10-17 on a Raspberry Pi 4 Model B.

## Why the data was measured again

The Awkernel data of 2026-02-27 came from a GEDF scheduler with three defects. tier4/awkernel merged the fix as PR #715 (commit `abbd2095`). The images of this data used commit `6243e474` of the fork atsushi421/awkernel, which differs from `abbd2095` only in the panic messages of `dag.rs`. The defects were the following:

- It added the relative deadline in milliseconds to a clock in microseconds.
- It derived the DAG deadline again whenever the source subtask woke up.
- It kept one deadline per DAG instead of one per job.

TU is the summed CPU load of the three DAGs of a case. The Awkernel run at TU=1.0 also used a different DAG set from ROS 2 and YASMIN. This measurement uses the same five DAG sets as both baselines.

## Changes in the measurement image

`measurement/build_images.sh` clones tier4/awkernel at `abbd2095` and applies the following changes. To build the images of this data, set `AWKERNEL_REPO=https://github.com/atsushi421/awkernel.git` and `COMMIT=6243e474`.

- `rd_gen_to_dags` loads the three RD-Gen DAGs of one case and schedules them with `SchedulerType::GEDF(0)`.
- `patch_sink_end.py` records the end timestamp after the sink function runs. The response time then runs from the source start to the sink end. The data of 2026-02-27 and the ROS 2 and YASMIN baselines use the same definition.
- `patch_udp_report.py` and `report.rs` send the timestamp table over UDP, because the board has no UART connection. The report task takes the table 90 s after the DAGs start. It then stops the simulated execution of the subtasks, so that the network tasks get CPU time, and sends the table three times.
- The UART print of the table is off, because it stalls the timers on CPU 0.

## DAG sets

| TU | ROS 2 and YASMIN case | RD-Gen DAGs in `../dags` |
| --- | --- | --- |
| 1.0 | case_1 | TU=0.4/DAGs/dag_0, TU=0.3/DAGs/dag_0, TU=0.3/DAGs/dag_3 |
| 1.5 | case_2 | TU=0.5/DAGs/dag_0, TU=0.5/DAGs/dag_7, TU=0.5/DAGs/dag_8 |
| 2.0 | case_3 | TU=1/DAGs/dag_0, TU=0.5/DAGs/dag_0, TU=0.5/DAGs/dag_7 |
| 2.5 | case_4 | TU=1/DAGs/dag_0, TU=1/DAGs/dag_2, TU=0.5/DAGs/dag_0 |
| 3.0 | case_5 | TU=1/DAGs/dag_0, TU=1/DAGs/dag_1, TU=1/DAGs/dag_2 |

## Procedure

### Build the images

1. Install the Rust toolchain that the Awkernel Makefile names (`nightly-2026-07-20`), `clang`, and `llvm-objcopy-18`.
2. Run `bash measurement/build_images.sh`.

The images go to `measurement/work/images/kernel8_TU10.img` through `kernel8_TU30.img`. To test the UDP report in QEMU first, run `bash measurement/build_images.sh qemu` and then the following command. It sends the table to the host at 10.0.2.2.

```
qemu-system-aarch64 -M virt,gic-version=3 -cpu cortex-a72 -m 1G -smp cpus=4 \
    -kernel measurement/work/images/kernel8_qemu_TU10.img \
    -netdev user,id=net0 -device e1000e,netdev=net0 \
    -display none -serial stdio -monitor none
```

### Prepare the SD card

1. Back up `config.txt` on the boot partition.
2. Copy `measurement/config.txt` to the boot partition. It is the Raspberry Pi 4 configuration of Awkernel (`misc/raspi4/config.txt`) with `kernel=awkernel.img`.
3. Copy the image of the next case to the boot partition as `awkernel.img`.

### Connect the network

1. Connect the Ethernet port of the board to a free Ethernet port of the PC, directly or through a switch.
2. Give that PC port the address 192.168.77.1/24, for example with the following commands.

```
nmcli connection add type ethernet ifname enp2s0 con-name awkernel-test \
    ipv4.method manual ipv4.addresses 192.168.77.1/24 ipv6.method disabled
nmcli connection up awkernel-test
```

The board uses 192.168.77.2 and sends to 192.168.77.1, UDP port 26099.

### Measure one case

1. On the PC, run `python3 measurement/udp_receive.py tu10.log`.
2. Power on the board. `#HELLO` lines arrive about 5 s after boot.
3. Wait until the receiver prints `done`. One case takes about 2 minutes.
4. Power off the board, and copy the image of the next case to the SD card.

### Convert and plot

```
for tu in 10 15 20 25 30; do
    python3 measurement/aw_log_to_csv.py evaluation_data/logs/tu$tu.log \
        "evaluation_data/csv/RD-Gen(GEDF3)_TU$tu.csv" --tu $tu
done
python3 ../plot/plot_comparison.py --awkernel-dir evaluation_data/csv \
    --ros2-dir ../ros2/benchmark_results/20260227_130120 \
    --yasmin-dir ../yasmin/benchmark_results/20260821_041727 --log-y --out-prefix <prefix>
```

`plot_comparison.py` is in `../plot`. The ROS 2 and YASMIN results are in `../ros2` and `../yasmin`. `outputs/response_time_comparison_3way.pdf` is Fig. 4 of the camera-ready paper.

## Results

The table gives median response times in ms. `outputs/summary_new.txt` and `outputs/summary_old_20260227.txt` hold the full tables.

| TU | Awkernel, this data | Awkernel, 2026-02-27 | YASMIN | ROS 2 | YASMIN / Awkernel |
| --- | --- | --- | --- | --- | --- |
| 1.0 | 31.5 | 27.1 (other DAG set) | 35.1 | 44.5 | 1.11 |
| 1.5 | 48.2 | 48.3 | 53.8 | 30.5 | 1.12 |
| 2.0 | 48.2 | 48.5 | 56.5 | 90.8 | 1.17 |
| 2.5 | 64.3 | 60.6 | 85.1 | 246.6 | 1.32 |
| 3.0 | 65.1 | 68.4 | 123.6 | 369.7 | 1.90 |

The deadline-miss ratio of Awkernel is 1.3 % to 36 %. It is lower than that of YASMIN (27 % to 61 %) at every TU. In the data of 2026-02-27, one of the three DAGs missed every deadline at TU=1.5, 2.5, and 3.0.

## Files

- `measurement/` holds the build script, the patches, the UDP report, the receiver, the log converter, and the SD card configuration.
- `evaluation_data/logs/` holds the raw UDP logs.
- `evaluation_data/csv/` holds the converted CSV files.
- `outputs/` holds the plots and the summary tables.
