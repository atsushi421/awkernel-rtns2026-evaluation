#!/usr/bin/env python3
"""
EKF trajectory comparison tool.
Loads two CSV trajectories, plots them on XY plane, and computes similarity.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from scipy.interpolate import interp1d
from scipy.spatial.distance import euclidean


def load_csv(filepath):
    """Load CSV file."""
    df = pd.read_csv(filepath)
    print(f"[INFO] Loaded: {filepath}")
    print(f"       Records: {len(df)}, Columns: {list(df.columns)}")
    return df


def analyze_velocity_components(df1, df2, label1='Dataset 1', label2='Dataset 2'):
    """Analyze velocity components (Vx, Vy, Vz)."""
    print("\n" + "="*70)
    print(f"Velocity Analysis")
    print("="*70)
    
    # Check whether Vy (Y velocity) exists
    if 'vy' in df1.columns and 'vy' in df2.columns:
        vy1_mean = df1['vy'].mean()
        vy1_std = df1['vy'].std()
        vy2_mean = df2['vy'].mean()
        vy2_std = df2['vy'].std()
        
        vy1_max = df1['vy'].max()
        vy1_min = df1['vy'].min()
        vy2_max = df2['vy'].max()
        vy2_min = df2['vy'].min()
        
        print(f"\n[Y Velocity (Vy)]")
        print(f"  {label1}:")
        print(f"    Mean: {vy1_mean:.6f} m/s, Std: {vy1_std:.6f} m/s")
        print(f"    Range: {vy1_min:.6f} ~ {vy1_max:.6f} m/s")
        print(f"  {label2}:")
        print(f"    Mean: {vy2_mean:.6f} m/s, Std: {vy2_std:.6f} m/s")
        print(f"    Range: {vy2_min:.6f} ~ {vy2_max:.6f} m/s")
        
        # Integrate Y velocity (predicted Y displacement)
        y_displacement_from_vy_1 = vy1_mean * (df1['timestamp'].max() - df1['timestamp'].min())
        y_displacement_from_vy_2 = vy2_mean * (df2['timestamp'].max() - df2['timestamp'].min())
        
        print(f"\n[Predicted Y Displacement from Vy]")
        print(f"  {label1}: {y_displacement_from_vy_1:.4f} m")
        print(f"  {label2}: {y_displacement_from_vy_2:.4f} m")
        
        # Actual Y displacement
        actual_y_1 = df1['y'].iloc[-1] - df1['y'].iloc[0]
        actual_y_2 = df2['y'].iloc[-1] - df2['y'].iloc[0]
        
        print(f"\n[Actual Y Displacement]")
        print(f"  {label1}: {actual_y_1:.4f} m")
        print(f"  {label2}: {actual_y_2:.4f} m")
        
        print(f"\n[KEY FINDING: Y Displacement Caused by Rotation]")
        print(f"  Since Vy ≈ 0 but Y changes significantly,")
        print(f"  Y-displacement is caused by Yaw rotation × forward velocity (Vx)")
        print(f"  Formula: dY = -Vx * sin(Yaw) * dt")
        
        # Estimate yaw from Y = ∫ Vx * sin(Yaw) dt
        if 'vx' in df1.columns:
            vx1_mean = df1['vx'].mean()
            duration_1 = df1['timestamp'].max() - df1['timestamp'].min()
            implied_yaw_1 = np.arcsin(actual_y_1 / (vx1_mean * duration_1)) if vx1_mean * duration_1 != 0 else 0
            
            vx2_mean = df2['vx'].mean() 
            duration_2 = df2['timestamp'].max() - df2['timestamp'].min()
            implied_yaw_2 = np.arcsin(min(1, max(-1, actual_y_2 / (vx2_mean * duration_2)))) if vx2_mean * duration_2 != 0 else 0
            
            print(f"\n[Implied Initial Yaw from Y Displacement]")
            print(f"  {label1}: {np.degrees(implied_yaw_1):.1f}° (initial rotation)")
            print(f"  {label2}: {np.degrees(implied_yaw_2):.1f}° (initial rotation)")
    
    # Check Vx (X velocity)
    if 'vx' in df1.columns and 'vx' in df2.columns:
        vx1_mean = df1['vx'].mean()
        vx1_std = df1['vx'].std()
        vx2_mean = df2['vx'].mean()
        vx2_std = df2['vx'].std()
        
        print(f"\n[X Velocity (Vx)]")
        print(f"  {label1}: Mean={vx1_mean:.6f} m/s, Std={vx1_std:.6f} m/s")
        print(f"  {label2}: Mean={vx2_mean:.6f} m/s, Std={vx2_std:.6f} m/s")
        print(f"  Difference: {abs(vx1_mean - vx2_mean):.6f} m/s")
    
    print("\n" + "="*70)


def align_recording_start_times(df1, df2):
    """Align recording start times.

    If Awkernel starts recording later, shift Autoware timestamps to compensate.
    Example: if Awkernel starts 7 seconds later, apply a +7 second offset.
    """
    t1_start = df1['timestamp'].min()
    t2_start = df2['timestamp'].min()
    
    startup_delay = t1_start - t2_start
    
    print(f"\n[INFO] Checking recording startup times:")
    print(f"       Awkernel started at: {t1_start:.6f} sec")
    print(f"       Autoware started at: {t2_start:.6f} sec")
    print(f"       Startup delay (Awkernel - Autoware): {startup_delay:.6f} sec")
    
    if abs(startup_delay) > 0.01:
        # If Awkernel starts late, delay Autoware timestamps accordingly
        df2_adjusted = df2.copy()
        df2_adjusted['timestamp'] = df2['timestamp'] + startup_delay
        print(f"       Applied adjustment: Autoware timestamps shifted by +{startup_delay:.6f} sec")
        print(f"       (This aligns both datasets to start at the same real-world time)")
        return df1, df2_adjusted
    else:
        print(f"       Startup times are aligned (difference < 10ms)")
        return df1, df2


def normalize_timestamps_to_relative(df1, df2):
    """Normalize both timestamps to relative time (elapsed time from start)
    
    This converts both datasets to the same reference frame:
    - Awkernel: Already uses relative time (uptime_nano)
    - Autoware: Uses ROS system time, convert to relative by subtracting first timestamp
    """
    # Get initial timestamps
    t1_min = df1['timestamp'].min()
    t2_min = df2['timestamp'].min()
    
    print(f"\n[INFO] Timestamp normalization to relative time:")
    print(f"       Dataset 1 initial timestamp: {t1_min:.9f}")
    print(f"       Dataset 2 initial timestamp: {t2_min:.9f}")
    
    # Convert to relative time (elapsed from start)
    df1_normalized = df1.copy()
    df1_normalized['timestamp'] = df1['timestamp'] - t1_min
    
    df2_normalized = df2.copy()
    df2_normalized['timestamp'] = df2['timestamp'] - t2_min
    
    print(f"       Dataset 1 normalized: 0.000 ~ {df1_normalized['timestamp'].max():.3f} sec")
    print(f"       Dataset 2 normalized: 0.000 ~ {df2_normalized['timestamp'].max():.3f} sec")
    print(f"       Both now use relative time (elapsed seconds from start)")
    
    return df1_normalized, df2_normalized


def find_movement_start(df, threshold=0.1):
    """Find the first timestamp with significant movement.
    
    Args:
        df: DataFrame containing 'timestamp', 'x', and 'y'.
        threshold: Minimum distance to consider movement [m].
    
    Returns:
        Relative timestamp when significant movement starts.
    """
    if len(df) < 2:
        return 0.0
    
    for i in range(1, len(df)):
        dx = df['x'].iloc[i] - df['x'].iloc[i-1]
        dy = df['y'].iloc[i] - df['y'].iloc[i-1]
        distance = (dx**2 + dy**2)**0.5
        
        if distance > threshold:
            start_time = df['timestamp'].iloc[i]
            print(f"       Movement detected at timestamp {start_time:.6f} sec")
            return start_time
    
    # No significant movement detected
    return 0.0


def align_initial_position(df1, df2):
    """Align initial position by shifting both datasets to origin."""
    # Get initial positions
    x1_init, y1_init = df1['x'].iloc[0], df1['y'].iloc[0]
    x2_init, y2_init = df2['x'].iloc[0], df2['y'].iloc[0]
    
    # Shift initial positions to origin
    df1_aligned = df1.copy()
    df1_aligned['x'] = df1['x'] - x1_init
    df1_aligned['y'] = df1['y'] - y1_init
    
    df2_aligned = df2.copy()
    df2_aligned['x'] = df2['x'] - x2_init
    df2_aligned['y'] = df2['y'] - y2_init
    
    print(f"[INFO] Initial position alignment:")
    print(f"       Dataset 1: ({x1_init:.3f}, {y1_init:.3f}) -> (0.000, 0.000)")
    print(f"       Dataset 2: ({x2_init:.3f}, {y2_init:.3f}) -> (0.000, 0.000)")
    
    return df1_aligned, df2_aligned


def align_movement_timestamps(df1, df2):
    """Align timestamps based on each dataset's first significant movement.

    Autoware startup can take longer, so actual movement start may be offset.
    This method detects movement start in both datasets and compensates by delta.
    """
    print(f"\n[INFO] Aligning movement timestamps:")
    
    # Detect first significant movement timestamp
    print(f"       Dataset 1: Detecting movement start...", end='')
    df1_start = find_movement_start(df1)
    
    print(f"       Dataset 2: Detecting movement start...", end='')
    df2_start = find_movement_start(df2)
    
    # Compute time offset
    time_offset = df2_start - df1_start
    
    print(f"\n       Dataset 1 movement start: {df1_start:.6f} sec")
    print(f"       Dataset 2 movement start: {df2_start:.6f} sec")
    print(f"       Time offset (Dataset2 - Dataset1): {time_offset:.6f} sec")
    
    # Adjust Autoware timestamps
    if abs(time_offset) > 0.01:  # Apply when offset is larger than 10 ms
        df2_aligned = df2.copy()
        df2_aligned['timestamp'] = df2['timestamp'] - time_offset
        print(f"       Applied offset adjustment: {time_offset:.6f} sec")
        return df1, df2_aligned, time_offset
    else:
        print(f"       Time offset is negligible, no adjustment applied")
        return df1, df2, 0.0


def interpolate_trajectory(df, time_points):
    """Resample trajectory at given timestamps (linear interpolation)."""
    # Remove duplicate timestamps
    df_unique = df.drop_duplicates(subset='timestamp').sort_values('timestamp')
    
    if len(df_unique) < 2:
        print("[WARNING] Not enough unique timestamps for interpolation")
        return None
    
    # Create interpolation functions
    interp_x = interp1d(df_unique['timestamp'], df_unique['x'], 
                        kind='linear', bounds_error=False, fill_value='extrapolate')
    interp_y = interp1d(df_unique['timestamp'], df_unique['y'], 
                        kind='linear', bounds_error=False, fill_value='extrapolate')
    
    # Interpolate at requested timestamps
    x_interp = interp_x(time_points)
    y_interp = interp_y(time_points)
    
    return x_interp, y_interp


def calculate_metrics(df1, df2):
    """Calculate trajectory matching metrics"""
    print("\n" + "="*70)
    print("Trajectory Comparison Metrics")
    print("="*70)
    
    # Get common time range
    t1_min, t1_max = df1['timestamp'].min(), df1['timestamp'].max()
    t2_min, t2_max = df2['timestamp'].min(), df2['timestamp'].max()
    t_start = max(t1_min, t2_min)
    t_end = min(t1_max, t2_max)
    
    print(f"\n[Time Range]")
    print(f"  Dataset 1: {t1_min:.2f} ~ {t1_max:.2f} sec (duration: {t1_max - t1_min:.2f} sec)")
    print(f"  Dataset 2: {t2_min:.2f} ~ {t2_max:.2f} sec (duration: {t2_max - t2_min:.2f} sec)")
    print(f"  Common:    {t_start:.2f} ~ {t_end:.2f} sec (duration: {t_end - t_start:.2f} sec)")
    
    # Sample over common time range
    num_samples = 1000
    time_points = np.linspace(t_start, t_end, num_samples)
    
    # Interpolate both trajectories
    x1_interp, y1_interp = interpolate_trajectory(df1, time_points)
    x2_interp, y2_interp = interpolate_trajectory(df2, time_points)
    
    if x1_interp is None or x2_interp is None:
        print("[ERROR] Interpolation failed")
        return None
    
    # Compute per-timestamp distance
    distances = np.sqrt((x1_interp - x2_interp)**2 + (y1_interp - y2_interp)**2)
    
    # Compute metrics
    rmse = np.sqrt(np.mean(distances**2))
    mean_error = np.mean(distances)
    max_error = np.max(distances)
    min_error = np.min(distances)
    std_error = np.std(distances)
    
    # Compute trajectory lengths
    def trajectory_length(x, y):
        return np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2))
    
    length1 = trajectory_length(df1['x'].values, df1['y'].values)
    length2 = trajectory_length(df2['x'].values, df2['y'].values)
    
    # End-point distance
    end_distance = euclidean([df1['x'].iloc[-1], df1['y'].iloc[-1]], 
                             [df2['x'].iloc[-1], df2['y'].iloc[-1]])
    
    # ===== Similarity metrics =====
    # 1. Correlation-based similarity
    correlation = np.corrcoef(x1_interp, x2_interp)[0, 1] * np.corrcoef(y1_interp, y2_interp)[0, 1]
    correlation = max(-1, min(1, correlation))  # Clamp to [-1, 1]
    correlation_similarity = (correlation + 1) / 2 * 100  # Normalize to [0, 100]
    
    # 2. Error-based similarity (smaller RMSE is better)
    # Baseline: 5% of maximum trajectory span as tolerance
    trajectory_span = np.sqrt((df1['x'].max() - df1['x'].min())**2 + 
                              (df1['y'].max() - df1['y'].min())**2)
    tolerance = trajectory_span * 0.05
    error_based_similarity = max(0, (1 - rmse / tolerance) * 100)  # 0 ~ 100%
    
    # 3. Ratio below error thresholds
    threshold_1m = np.sum(distances <= 1.0) / len(distances) * 100
    threshold_5m = np.sum(distances <= 5.0) / len(distances) * 100
    threshold_10m = np.sum(distances <= 10.0) / len(distances) * 100
    
    # 4. Trajectory-length similarity
    length_similarity = min(length1, length2) / max(length1, length2) * 100
    
    # 5. Composite overall similarity
    overall_similarity = (correlation_similarity + error_based_similarity + length_similarity) / 3
    
    print(f"\n[Position Error Statistics]")
    print(f"  RMSE (Root Mean Square Error): {rmse:.4f} m")
    print(f"  Mean Error:                     {mean_error:.4f} m")
    print(f"  Std Deviation:                  {std_error:.4f} m")
    print(f"  Max Error:                      {max_error:.4f} m")
    print(f"  Min Error:                      {min_error:.4f} m")
    
    print(f"\n[Trajectory Length]")
    print(f"  Dataset 1: {length1:.2f} m")
    print(f"  Dataset 2: {length2:.2f} m")
    print(f"  Difference: {abs(length1 - length2):.2f} m ({abs(length1-length2)/max(length1,length2)*100:.2f}%)")
    
    print(f"\n[End Point Distance]")
    print(f"  {end_distance:.4f} m")
    
    print(f"\n[Similarity / Matching Rate]")
    print(f"  Correlation-based Similarity:  {correlation_similarity:.2f}%")
    print(f"  Error-based Similarity:        {error_based_similarity:.2f}%")
    print(f"  Trajectory Length Similarity:  {length_similarity:.2f}%")
    print(f"  ─────────────────────────────────")
    print(f"  Overall Similarity Score:      {overall_similarity:.2f}%")
    print(f"\n  Error within thresholds:")
    print(f"    Within 1m:   {threshold_1m:.1f}%")
    print(f"    Within 5m:   {threshold_5m:.1f}%")
    print(f"    Within 10m:  {threshold_10m:.1f}%")
    
    print("\n" + "="*70)
    
    metrics = {
        'rmse': rmse,
        'mean_error': mean_error,
        'std_error': std_error,
        'max_error': max_error,
        'min_error': min_error,
        'length1': length1,
        'length2': length2,
        'end_distance': end_distance,
        'time_points': time_points,
        'distances': distances,
        'x1_interp': x1_interp,
        'y1_interp': y1_interp,
        'x2_interp': x2_interp,
        'y2_interp': y2_interp,
        'correlation_similarity': correlation_similarity,
        'error_based_similarity': error_based_similarity,
        'length_similarity': length_similarity,
        'overall_similarity': overall_similarity,
        'threshold_1m': threshold_1m,
        'threshold_5m': threshold_5m,
        'threshold_10m': threshold_10m,
    }
    
    return metrics


def plot_trajectory_comparison(df1, df2, label1='Dataset 1', label2='Dataset 2', save_path=None):
    """Plot trajectory comparison on the XY plane."""
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.plot(df1['x'], df1['y'], 'b-', linewidth=2, alpha=0.7, label=label1)
    ax.plot(df2['x'], df2['y'], 'r-', linewidth=2, alpha=0.7, label=label2)
    ax.plot(df1['x'].iloc[0], df1['y'].iloc[0], 'go', markersize=10, label='Start')
    # Draw end markers without adding to legend
    ax.plot(df1['x'].iloc[-1], df1['y'].iloc[-1], 'bs', markersize=10)
    ax.plot(df2['x'].iloc[-1], df2['y'].iloc[-1], 'r^', markersize=10)
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Trajectory Comparison (XY Plane)')
    ax.legend(loc='upper left', bbox_to_anchor=(0, 1.02), borderaxespad=0.5)
    ax.grid(True, alpha=0.3)
    # Auto-calculate X range, keep Y fixed to +/-25, preserve aspect ratio
    x_margin = 5
    xmin = min(df1['x'].min(), df2['x'].min()) - x_margin
    xmax = max(df1['x'].max(), df2['x'].max()) + x_margin
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal', adjustable='box')
    plt.tight_layout()
    
    if save_path:
        # If PDF-only is requested, decide by save_path extension
        if save_path.suffix.lower() == '.pdf':
            plt.savefig(save_path, bbox_inches='tight')
            print(f"[INFO] Plot saved to: {save_path}")
        else:
            # Save in multiple formats: PNG, PDF, SVG
            base_path = save_path.with_suffix('')
            png_path = base_path.with_suffix('.png')
            plt.savefig(png_path, dpi=150, bbox_inches='tight')
            print(f"[INFO] Plot saved to: {png_path}")
            pdf_path = base_path.with_suffix('.pdf')
            plt.savefig(pdf_path, bbox_inches='tight')
            print(f"[INFO] Plot saved to: {pdf_path}")
            svg_path = base_path.with_suffix('.svg')
            plt.savefig(svg_path, bbox_inches='tight')
            print(f"[INFO] Plot saved to: {svg_path}")
    plt.show()


def plot_trajectory_zoom(df1, df2, label1='Dataset 1', label2='Dataset 2'):
    """Zoomed trajectory view (initial section)."""
    fig, ax = plt.subplots(figsize=(10, 8))
    n_start = min(100, len(df1), len(df2))
    ax.plot(df1['x'].iloc[:n_start], df1['y'].iloc[:n_start], 'b-', linewidth=2, alpha=0.7, label=label1)
    ax.plot(df2['x'].iloc[:n_start], df2['y'].iloc[:n_start], 'r-', linewidth=2, alpha=0.7, label=label2)
    ax.plot(df1['x'].iloc[0], df1['y'].iloc[0], 'go', markersize=10, label='Start')
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Trajectory Comparison (Start Section Zoom)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axis('equal')
    ax.set_ylim(-25, 25)  # Must be called after axis('equal') to enforce range
    plt.tight_layout()
    plt.show()


def plot_position_error_over_time(metrics):
    """Plot position error over time."""
    if not metrics:
        print("[ERROR] No metrics provided")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    time_relative = metrics['time_points'] - metrics['time_points'][0]
    ax.plot(time_relative, metrics['distances'], 'g-', linewidth=1.5, label='Position Error')
    ax.axhline(y=metrics['rmse'], color='r', linestyle='--', linewidth=2, label=f'RMSE: {metrics["rmse"]:.4f} m')
    ax.axhline(y=metrics['mean_error'], color='b', linestyle='--', linewidth=2, label=f'Mean: {metrics["mean_error"]:.4f} m')
    ax.fill_between(time_relative, 0, metrics['distances'], alpha=0.2, color='green')
    ax.set_xlabel('Time [sec]')
    ax.set_ylabel('Position Error [m]')
    ax.set_title('Position Error over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def plot_x_coordinate_comparison(df1, df2, label1='Dataset 1', label2='Dataset 2'):
    """Plot X coordinate comparison over time."""
    fig, ax = plt.subplots(figsize=(12, 6))
    t1_relative = df1['timestamp'] - df1['timestamp'].iloc[0]
    t2_relative = df2['timestamp'] - df2['timestamp'].iloc[0]
    ax.plot(t1_relative, df1['x'], 'b-', linewidth=1.5, alpha=0.7, label=label1)
    ax.plot(t2_relative, df2['x'], 'r-', linewidth=1.5, alpha=0.7, label=label2)
    ax.set_xlabel('Time [sec]')
    ax.set_ylabel('X [m]')
    ax.set_title('X Coordinate Comparison')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def plot_y_coordinate_comparison(df1, df2, label1='Dataset 1', label2='Dataset 2'):
    """Plot Y coordinate comparison over time."""
    fig, ax = plt.subplots(figsize=(12, 6))
    t1_relative = df1['timestamp'] - df1['timestamp'].iloc[0]
    t2_relative = df2['timestamp'] - df2['timestamp'].iloc[0]
    ax.plot(t1_relative, df1['y'], 'b-', linewidth=1.5, alpha=0.7, label=label1)
    ax.plot(t2_relative, df2['y'], 'r-', linewidth=1.5, alpha=0.7, label=label2)
    ax.set_xlabel('Time [sec]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Y Coordinate Comparison')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-25, 25)
    plt.tight_layout()
    plt.show()


def plot_error_distribution(metrics):
    """Histogram of error distribution."""
    if not metrics:
        print("[ERROR] No metrics provided")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(metrics['distances'], bins=50, color='green', alpha=0.7, edgecolor='black', label='Error Distribution')
    ax.axvline(x=metrics['rmse'], color='r', linestyle='--', linewidth=2, label=f'RMSE: {metrics["rmse"]:.4f} m')
    ax.axvline(x=metrics['mean_error'], color='b', linestyle='--', linewidth=2, label=f'Mean: {metrics["mean_error"]:.4f} m')
    ax.set_xlabel('Position Error [m]')
    ax.set_ylabel('Frequency')
    ax.set_title('Position Error Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.show()


def plot_comparison(df1, df2, metrics, label1='Dataset 1', label2='Dataset 2', save_path=None):
    """Combine all plots into one figure (optional)."""
    fig = plt.figure(figsize=(16, 10))
    
    # 1. XY-plane trajectories
    ax1 = plt.subplot(2, 3, 1)
    ax1.plot(df1['x'], df1['y'], 'b-', linewidth=2, alpha=0.7, label=label1)
    ax1.plot(df2['x'], df2['y'], 'r-', linewidth=2, alpha=0.7, label=label2)
    ax1.plot(df1['x'].iloc[0], df1['y'].iloc[0], 'go', markersize=10, label='Start')
    ax1.plot(df1['x'].iloc[-1], df1['y'].iloc[-1], 'bs', markersize=10, label=f'{label1} End')
    ax1.plot(df2['x'].iloc[-1], df2['y'].iloc[-1], 'r^', markersize=10, label=f'{label2} End')
    ax1.set_xlabel('X [m]')
    ax1.set_ylabel('Y [m]')
    ax1.set_title('Trajectory Comparison (XY Plane)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axis('equal')
    ax1.set_ylim(-25, 25)
    
    # 2. Trajectory zoom (start section)
    ax2 = plt.subplot(2, 3, 2)
    n_start = min(100, len(df1), len(df2))
    ax2.plot(df1['x'].iloc[:n_start], df1['y'].iloc[:n_start], 'b-', linewidth=2, alpha=0.7, label=label1)
    ax2.plot(df2['x'].iloc[:n_start], df2['y'].iloc[:n_start], 'r-', linewidth=2, alpha=0.7, label=label2)
    ax2.plot(df1['x'].iloc[0], df1['y'].iloc[0], 'go', markersize=10, label='Start')
    ax2.set_xlabel('X [m]')
    ax2.set_ylabel('Y [m]')
    ax2.set_title('Trajectory Comparison (Start Zoom)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axis('equal')
    ax2.set_ylim(-25, 25)
    
    # 3. Position error over time
    if metrics:
        ax3 = plt.subplot(2, 3, 3)
        time_relative = metrics['time_points'] - metrics['time_points'][0]
        ax3.plot(time_relative, metrics['distances'], 'g-', linewidth=1.5)
        ax3.axhline(y=metrics['rmse'], color='r', linestyle='--', label=f'RMSE: {metrics["rmse"]:.4f} m')
        ax3.axhline(y=metrics['mean_error'], color='b', linestyle='--', label=f'Mean: {metrics["mean_error"]:.4f} m')
        ax3.set_xlabel('Time [sec]')
        ax3.set_ylabel('Position Error [m]')
        ax3.set_title('Position Error over Time')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # 4. X coordinate time series
    ax4 = plt.subplot(2, 3, 4)
    t1_relative = df1['timestamp'] - df1['timestamp'].iloc[0]
    t2_relative = df2['timestamp'] - df2['timestamp'].iloc[0]
    ax4.plot(t1_relative, df1['x'], 'b-', linewidth=1.5, alpha=0.7, label=label1)
    ax4.plot(t2_relative, df2['x'], 'r-', linewidth=1.5, alpha=0.7, label=label2)
    ax4.set_xlabel('Time [sec]')
    ax4.set_ylabel('X [m]')
    ax4.set_title('X Coordinate Comparison')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. Y coordinate time series
    ax5 = plt.subplot(2, 3, 5)
    ax5.plot(t1_relative, df1['y'], 'b-', linewidth=1.5, alpha=0.7, label=label1)
    ax5.plot(t2_relative, df2['y'], 'r-', linewidth=1.5, alpha=0.7, label=label2)
    ax5.set_xlabel('Time [sec]')
    ax5.set_ylabel('Y [m]')
    ax5.set_title('Y Coordinate Comparison')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    ax5.set_ylim(-25, 25)
    
    # 6. Error histogram
    if metrics:
        ax6 = plt.subplot(2, 3, 6)
        ax6.hist(metrics['distances'], bins=50, color='green', alpha=0.7, edgecolor='black')
        ax6.axvline(x=metrics['rmse'], color='r', linestyle='--', linewidth=2, label=f'RMSE: {metrics["rmse"]:.4f} m')
        ax6.axvline(x=metrics['mean_error'], color='b', linestyle='--', linewidth=2, label=f'Mean: {metrics["mean_error"]:.4f} m')
        ax6.set_xlabel('Position Error [m]')
        ax6.set_ylabel('Frequency')
        ax6.set_title('Position Error Distribution')
        ax6.legend()
        ax6.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    if save_path:
        # Save in multiple formats: PNG, PDF, SVG
        base_path = save_path.with_suffix('')
        
        png_path = base_path.with_suffix('.png')
        plt.savefig(png_path, dpi=150, bbox_inches='tight')
        print(f"[INFO] Plot saved to: {png_path}")
        
        pdf_path = base_path.with_suffix('.pdf')
        plt.savefig(pdf_path, bbox_inches='tight')
        print(f"[INFO] Plot saved to: {pdf_path}")
        
        svg_path = base_path.with_suffix('.svg')
        plt.savefig(svg_path, bbox_inches='tight')
        print(f"[INFO] Plot saved to: {svg_path}")
    
    plt.show()


def main():
    # ========================================
    # Specify file paths here
    # ========================================
    CSV_FILE_1 = 'csv/ekf_data_visualizer_20260131_035152.csv'  # Awkernel
    CSV_FILE_2 = 'csv/autoware_10.csv'  # Autoware
    LABEL_1 = 'Awkernel'
    LABEL_2 = 'Autoware'
    # ========================================
    
        # Usage message
    usage_msg = """
Usage:
  python3 compare_trajectories.py [csv1] [csv2] [label1] [label2] [plot_type]
  
plot_type options:
    all          - Show all plots in one figure (default)
    trajectory   - XY-plane trajectory comparison
    zoom         - Zoomed trajectory view (initial section)
    error        - Position error over time
    x            - X coordinate comparison over time
    y            - Y coordinate comparison over time
    distribution - Error distribution histogram

Examples:
  python3 compare_trajectories.py csv/awkernel.csv csv/autoware.csv Awkernel Autoware trajectory
  python3 compare_trajectories.py csv/awkernel.csv csv/autoware.csv Awkernel Autoware error
    """
    
    # Prefer command-line arguments when provided
    if len(sys.argv) >= 3:
        csv1_path = Path(sys.argv[1])
        csv2_path = Path(sys.argv[2])
        label1 = sys.argv[3] if len(sys.argv) > 3 else csv1_path.stem
        label2 = sys.argv[4] if len(sys.argv) > 4 else csv2_path.stem
        plot_type = sys.argv[5].lower() if len(sys.argv) > 5 else 'all'
    else:
        # Use files configured in source code
        csv1_path = Path(__file__).parent / CSV_FILE_1
        csv2_path = Path(__file__).parent / CSV_FILE_2
        label1 = LABEL_1
        label2 = LABEL_2
        plot_type = 'all'
        print("[INFO] Using files specified in source code:")
        print(f"       File 1: {csv1_path}")
        print(f"       File 2: {csv2_path}")
        print(f"       Plot type: {plot_type}")
        print(usage_msg)
    
    if not csv1_path.exists():
        print(f"[ERROR] File not found: {csv1_path}")
        sys.exit(1)
    
    if not csv2_path.exists():
        print(f"[ERROR] File not found: {csv2_path}")
        sys.exit(1)
    
    print("="*70)
    print("EKF Trajectory Comparison Tool")
    print("="*70)
    
    # Load CSVs
    df1 = load_csv(csv1_path)
    df2 = load_csv(csv2_path)
    
    # Check required columns
    required_cols = ['timestamp', 'x', 'y']
    for col in required_cols:
        if col not in df1.columns or col not in df2.columns:
            print(f"[ERROR] Required column '{col}' not found in CSV files")
            sys.exit(1)
    
    # Align recording start times (compensate if Awkernel started later)
    df1_startup_aligned, df2_startup_aligned = align_recording_start_times(df1, df2)
    
    # Normalize timestamps to relative time (both systems use elapsed time from start)
    df1_normalized, df2_normalized = normalize_timestamps_to_relative(df1_startup_aligned, df2_startup_aligned)
    
    # Re-align start times after normalization
    df1_normalized, df2_normalized = align_recording_start_times(df1_normalized, df2_normalized)
    
    # Align timestamps by first significant movement
    df1_time_aligned, df2_time_aligned, time_offset = align_movement_timestamps(df1_normalized, df2_normalized)
    
    # Align initial positions
    df1_aligned, df2_aligned = align_initial_position(df1_time_aligned, df2_time_aligned)
    
    # Compute metrics
    metrics = calculate_metrics(df1_aligned, df2_aligned)
    
    # Analyze velocity components
    analyze_velocity_components(df1_aligned, df2_aligned, label1=label1, label2=label2)
    
    # Plot output path
    # Save PDF only if trajectory mode and --pdf-only flag is set
    pdf_only = False
    if plot_type == 'trajectory' and '--pdf-only' in sys.argv:
        pdf_only = True
        save_path = Path(__file__).parent / 'csv' / f'trajectory_comparison_{csv1_path.stem}_vs_{csv2_path.stem}.pdf'
    else:
        save_path = Path(__file__).parent / 'csv' / f'trajectory_comparison_{csv1_path.stem}_vs_{csv2_path.stem}.png'
    
    # Render by selected plot type
    print(f"\n[INFO] Displaying plot type: {plot_type}")
    
    if plot_type == 'all':
        plot_comparison(df1_aligned, df2_aligned, metrics, label1=label1, label2=label2, save_path=save_path)
    elif plot_type == 'trajectory':
        # y-axis limits are always enforced in plot_trajectory_comparison
        plot_trajectory_comparison(df1_aligned, df2_aligned, label1=label1, label2=label2, save_path=save_path)
    elif plot_type == 'zoom':
        plot_trajectory_zoom(df1_aligned, df2_aligned, label1=label1, label2=label2)
    elif plot_type == 'error':
        plot_position_error_over_time(metrics)
    elif plot_type == 'x':
        plot_x_coordinate_comparison(df1_aligned, df2_aligned, label1=label1, label2=label2)
    elif plot_type == 'y':
        plot_y_coordinate_comparison(df1_aligned, df2_aligned, label1=label1, label2=label2)
    elif plot_type == 'distribution':
        plot_error_distribution(metrics)
    else:
        print(f"[ERROR] Unknown plot type: {plot_type}")
        print(usage_msg)
        sys.exit(1)
    
    print(f"\n[INFO] Comparison completed")


if __name__ == '__main__':
    main()
