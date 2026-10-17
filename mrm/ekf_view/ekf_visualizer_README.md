# Autoware EKF Visualizer

Visualization tool for Autoware EKF outputs from ROS 2 topics.

## Installation

```bash
pip3 install matplotlib numpy
```

## Usage

### 1. Start Autoware

```bash
cd /workspace
./launch_minimal_localization.sh
```

### 2. Start the visualizer in another terminal

```bash
# 2D trajectory + covariance + velocity (recommended)
python3 /workspace/ekf_visualizer_autoware.py 2d

# 3D trajectory
python3 /workspace/ekf_visualizer_autoware.py 3d

# Velocity time-series
python3 /workspace/ekf_visualizer_autoware.py velocity

# CSV only (save on Ctrl+C)
python3 /workspace/ekf_visualizer_autoware.py csv
```

## Display Contents

### 2D Mode
- XY-plane trajectory (top view)
- Covariance ellipse at current position
- Height (Z coordinate) trend
- Position/orientation uncertainty (standard deviation)
- XY velocity

### 3D Mode
- 3D trajectory in XYZ space

### Velocity Mode
- Vx, Vy, Vz time-series
- Speed norm ($|V|$)

## Subscribed Topics
- `/localization/pose_twist_fusion_filter/kinematic_state` (Odometry)
- `/localization/pose_twist_fusion_filter/pose_with_covariance` (PoseWithCovarianceStamped)
