# Autoware vs Awkernel EKF Comparison Report

## Scope

This report summarizes how EKF-related data and trajectory outputs are compared between Autoware and Awkernel.

## Input Alignment

Compared categories:

- IMU values
- Velocity values
- Initial pose
- Timing behavior

## Expected Behavior

Both systems should:

1. Start from the same initial pose.
2. Integrate velocity over time for trajectory generation.
3. Apply yaw evolution consistently.
4. Produce comparable dead-reckoning trends.

## Verification Steps

```bash
# Terminal 1: start Autoware
cd /path/to/autoware
./launch_minimal_localization.sh

# Terminal 2: start Awkernel
cd /path/to/awkernel
make qemu-x86_64

# Terminal 3: visualize and compare
cd /path/to/ekf_view
python3 run_ekf_monitoring.py --rviz --visualizer 3d
```

## Current Status

- Input parameter alignment: completed
- Timing alignment: completed
- Overlay visualization and detailed output-diff review: in progress

## Next Work

1. Produce side-by-side overlay plots for all scenarios.
2. Quantify deviation by RMSE/mean/max statistics.
3. Track differences by phase (startup, straight run, turning segments).
