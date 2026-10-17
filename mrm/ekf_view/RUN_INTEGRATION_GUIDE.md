# EKF Integrated Monitoring Guide

This guide explains how to monitor and visualize EKF data from Awkernel and Autoware with ROS 2.

## Overview

```text
Awkernel (QEMU)
   -> UDP JSON
AwkernelUdpBridge
   -> ROS 2 topics
RViz + ekf_visualizer.py
```

## Main Script

```bash
python3 run_ekf_monitoring.py [options]
```

### Options

- `--rviz`: launch RViz
- `--visualizer TYPE`: `2d`, `3d`, or `velocity` (default: `2d`)
- `--output CSV_PATH`: save EKF data to CSV
- `--timeout SECONDS`: stop after a fixed runtime
- `--no-ros-bridge`: skip internal bridge if another bridge is already running

### Examples

```bash
# Lightweight 2D
python3 run_ekf_monitoring.py

# Full monitoring
python3 run_ekf_monitoring.py --rviz --visualizer 3d

# Velocity
python3 run_ekf_monitoring.py --visualizer velocity
```

## Prerequisites

1. ROS 2 Humble installed
2. Autoware built and sourced
3. Awkernel running in QEMU
4. UDP port `26099` reachable

## Startup Flow

```bash
# Terminal 1
cd /path/to/awkernel
make qemu-x86_64

# Terminal 2
cd /path/to/autoware
./launch_minimal_localization.sh

# Terminal 3
cd /path/to/ekf_view
python3 run_ekf_monitoring.py --rviz --visualizer 3d
```

## Troubleshooting

### No UDP packets

```bash
ss -ulnp | grep 26099
```

### ROS topic missing

```bash
ros2 topic list | grep awkernel
```

### RViz fails to start

```bash
rviz2
```
