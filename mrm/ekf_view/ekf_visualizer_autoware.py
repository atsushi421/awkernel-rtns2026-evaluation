#!/usr/bin/env python3
"""
Autoware EKF Localizer visualization tool.
Directly reads ROS 2 topics and plots trajectories.
"""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped
import threading
from collections import deque
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import sys
import time

class AutowareEKFVisualizer(Node):
    def __init__(self, max_points=1000, record_interval=0.1):
        super().__init__('autoware_ekf_visualizer')
        
        self.max_points = max_points
        self.data_received = False
        self.last_update_time = time.time()
        self.record_interval = record_interval  # Recording interval (seconds)
        self.last_record_time = 0.0  # Last recorded timestamp
        
        # Position data buffers
        self.x_data = deque(maxlen=max_points)
        self.y_data = deque(maxlen=max_points)
        self.z_data = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        
        # Velocity data buffers
        self.vx_data = deque(maxlen=max_points)
        self.vy_data = deque(maxlen=max_points)
        self.vz_data = deque(maxlen=max_points)
        
        # Covariance data buffers
        self.cov_x = deque(maxlen=max_points)
        self.cov_y = deque(maxlen=max_points)
        self.cov_yaw = deque(maxlen=max_points)
        
        self.data_lock = threading.Lock()
        self.counter = 0
        
        print("[DEBUG] Creating subscriptions...")
        
        # Subscriber: Odometry (kinematic_state)
        self.odom_sub = self.create_subscription(
            Odometry,
            '/localization/pose_twist_fusion_filter/kinematic_state',
            self.odom_callback,
            10
        )
        print("[DEBUG] Subscription to /localization/pose_twist_fusion_filter/kinematic_state created")
        # Subscriber: PoseWithCovarianceStamped (pose_with_covariance)
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/localization/pose_twist_fusion_filter/pose_with_covariance',
            self.pose_callback,
            10
        )
        print("[DEBUG] Subscription to /localization/pose_twist_fusion_filter/pose_with_covariance created")
        
        self.get_logger().info('Autoware EKF Visualizer started')
        self.get_logger().info('Subscribing to:')
        self.get_logger().info('  - /localization/pose_twist_fusion_filter/kinematic_state')
        self.get_logger().info('  - /localization/pose_twist_fusion_filter/pose_with_covariance')
        print("[DEBUG] Init complete")
    
    def odom_callback(self, msg):
        """Odometry topic callback."""
        self.data_received = True
        self.counter += 1
        self.last_update_time = time.time()
        
        # Position
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        z = msg.pose.pose.position.z
        
        # Velocity
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        vz = msg.twist.twist.linear.z
        
        # Timestamp
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        
        # Covariance (position: index 0, 7, 14 for x, y, z)
        cov_x = msg.pose.covariance[0]
        cov_y = msg.pose.covariance[7]
        cov_z = msg.pose.covariance[14]
        # Yaw covariance (index 35)
        cov_yaw = msg.pose.covariance[35]
        
        # Recording interval check (append only when interval elapsed)
        if timestamp - self.last_record_time >= self.record_interval:
            with self.data_lock:
                self.x_data.append(x)
                self.y_data.append(y)
                self.z_data.append(z)
                self.vx_data.append(vx)
                self.vy_data.append(vy)
                self.vz_data.append(vz)
                self.timestamps.append(timestamp)
                self.cov_x.append(np.sqrt(cov_x))
                self.cov_y.append(np.sqrt(cov_y))
                self.cov_yaw.append(np.sqrt(cov_yaw))
                self.last_record_time = timestamp
        
        # Log every 10th message
        if self.counter % 10 == 0:
            self.get_logger().info(
                f'Callback #{self.counter}: pos=({x:.3f}, {y:.3f}, {z:.3f}), '
                f'vel=({vx:.3f}, {vy:.3f}, {vz:.3f}), '
                f'std=(x:{np.sqrt(cov_x):.3f}, y:{np.sqrt(cov_y):.3f})'
            )
    
    def pose_callback(self, msg):
        """PoseWithCovarianceStamped topic callback (auxiliary)."""
        # Reserved for future use (Odometry is currently sufficient)
        pass
    
    def plot_2d_trajectory(self, max_runtime=120):
        """2D trajectory (top view) with covariance."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        
        # Timeout management thread
        startup_time = time.time()
        def timeout_handler():
            while time.time() - startup_time < max_runtime:
                time.sleep(1)
            print(f"\n[TIMEOUT] Reached {max_runtime}s runtime limit. Closing window...")
            plt.close(fig)
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        def animate(frame):
            ax1.clear()
            ax2.clear()
            ax3.clear()
            ax4.clear()
            
            with self.data_lock:
                if len(self.x_data) > 0:
                    xs = list(self.x_data)
                    ys = list(self.y_data)
                    zs = list(self.z_data)
                    covs_x = list(self.cov_x)
                    covs_y = list(self.cov_y)
                    covs_yaw = list(self.cov_yaw)
                    
                    # XY plane (top-down)
                    ax1.plot(xs, ys, 'b-', label='EKF Trajectory', linewidth=2, alpha=0.7)
                    ax1.scatter(xs[-1], ys[-1], c='r', s=100, label='Current Position', zorder=5)
                    
                    # Draw covariance ellipse
                    if len(xs) > 0:
                        from matplotlib.patches import Ellipse
                        ellipse = Ellipse(
                            (xs[-1], ys[-1]), 
                            width=2*covs_x[-1], 
                            height=2*covs_y[-1],
                            alpha=0.3, 
                            color='red', 
                            label='Uncertainty'
                        )
                        ax1.add_patch(ellipse)
                    
                    ax1.set_xlabel('X [m]')
                    ax1.set_ylabel('Y [m]')
                    ax1.set_title('EKF Trajectory (Top View)')
                    ax1.legend()
                    ax1.grid(True)
                    ax1.axis('equal')
                    
                    # Z trajectory
                    frames = range(len(zs))
                    ax2.plot(frames, zs, 'g-', label='Z Coordinate', linewidth=2)
                    ax2.set_xlabel('Sample Number')
                    ax2.set_ylabel('Z [m]')
                    ax2.set_title('Height Change')
                    ax2.legend()
                    ax2.grid(True)
                    
                    # Covariance (standard deviation) over time
                    ax3.plot(frames, covs_x, label='σ_x', linewidth=2)
                    ax3.plot(frames, covs_y, label='σ_y', linewidth=2)
                    ax3.plot(frames, covs_yaw, label='σ_yaw', linewidth=2)
                    ax3.set_xlabel('Sample Number')
                    ax3.set_ylabel('Standard Deviation [m or rad]')
                    ax3.set_title('Uncertainty (Covariance)')
                    ax3.legend()
                    ax3.grid(True)
                    ax3.set_yscale('log')
                    
                    # Velocity
                    ax4.plot(frames, list(self.vx_data), label='Vx', linewidth=2)
                    ax4.plot(frames, list(self.vy_data), label='Vy', linewidth=2)
                    ax4.set_xlabel('Sample Number')
                    ax4.set_ylabel('Velocity [m/s]')
                    ax4.set_title('Velocity')
                    ax4.legend()
                    ax4.grid(True)
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.tight_layout()
        plt.show()
    
    def plot_3d_trajectory(self, max_runtime=120):
        """3D trajectory plot."""
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Timeout management thread
        startup_time = time.time()
        def timeout_handler():
            while time.time() - startup_time < max_runtime:
                time.sleep(1)
            print(f"\n[TIMEOUT] Reached {max_runtime}s runtime limit. Closing window...")
            plt.close(fig)
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        def animate(frame):
            ax.clear()
            
            with self.data_lock:
                if len(self.x_data) > 0:
                    xs = list(self.x_data)
                    ys = list(self.y_data)
                    zs = list(self.z_data)
                    
                    ax.plot(xs, ys, zs, 'b-', label='EKF Trajectory', linewidth=2)
                    ax.scatter(xs[-1], ys[-1], zs[-1], c='r', s=100, label='Current Position', zorder=5)
                    ax.set_xlabel('X [m]')
                    ax.set_ylabel('Y [m]')
                    ax.set_zlabel('Z [m]')
                    ax.set_title('Autoware EKF Trajectory (3D)')
                    ax.legend()
                    ax.grid(True)
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.show()
    
    def plot_velocity(self, max_runtime=120):
        """Velocity time-series plot."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Timeout management thread
        startup_time = time.time()
        def timeout_handler():
            while time.time() - startup_time < max_runtime:
                time.sleep(1)
            print(f"\n[TIMEOUT] Reached {max_runtime}s runtime limit. Closing window...")
            plt.close(fig)
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        def animate(frame):
            ax1.clear()
            ax2.clear()
            
            with self.data_lock:
                if len(self.vx_data) > 0:
                    frames = range(len(self.vx_data))
                    
                    # Linear velocity
                    ax1.plot(frames, list(self.vx_data), label='Vx', linewidth=2)
                    ax1.plot(frames, list(self.vy_data), label='Vy', linewidth=2)
                    ax1.plot(frames, list(self.vz_data), label='Vz', linewidth=2)
                    ax1.set_xlabel('Sample Number')
                    ax1.set_ylabel('Linear Velocity [m/s]')
                    ax1.set_title('EKF Linear Velocity')
                    ax1.legend()
                    ax1.grid(True)
                    
                    # Speed magnitude
                    v_norm = [np.sqrt(vx**2 + vy**2 + vz**2) for vx, vy, vz in 
                              zip(self.vx_data, self.vy_data, self.vz_data)]
                    ax2.plot(frames, v_norm, label='|V|', linewidth=2, color='purple')
                    ax2.set_xlabel('Sample Number')
                    ax2.set_ylabel('Speed [m/s]')
                    ax2.set_title('EKF Speed')
                    ax2.legend()
                    ax2.grid(True)
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.tight_layout()
        plt.show()
    
    def save_csv(self, filename=None):
        """Save data to CSV."""
        import csv
        from pathlib import Path
        from datetime import datetime
        
        # Auto-generate filename when not specified
        if filename is None:
            csv_dir = Path(__file__).parent / 'csv'
            csv_dir.mkdir(parents=True, exist_ok=True)
            filename = csv_dir / f'autoware_ekf_trajectory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        else:
            # Even when filename is specified, save under csv/
            csv_dir = Path(__file__).parent / 'csv'
            csv_dir.mkdir(parents=True, exist_ok=True)
            filename = csv_dir / filename
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'std_x', 'std_y', 'std_yaw'])
                
                with self.data_lock:
                    for ts, x, y, z, vx, vy, vz, sx, sy, syaw in zip(
                        self.timestamps, self.x_data, self.y_data, self.z_data,
                        self.vx_data, self.vy_data, self.vz_data,
                        self.cov_x, self.cov_y, self.cov_yaw
                    ):
                        writer.writerow([ts, x, y, z, vx, vy, vz, sx, sy, syaw])
            
            self.get_logger().info(f"CSV saved: {filename}")
            print(f"[INFO] CSV save completed: {filename}")
        except Exception as e:
            print(f"[WARNING] Failed to save CSV: {e}")


def spin_ros(node):
    """Run ROS 2 spin in background."""
    rclpy.spin(node)


def main():
    # Usage
    if len(sys.argv) < 2:
        print("Usage: python3 ekf_visualizer_autoware.py [2d|3d|velocity|csv] [csv_output_file]")
        print("  2d       - 2D trajectory + covariance + velocity")
        print("  3d       - 3D trajectory")
        print("  velocity - Velocity time series")
        print("  csv      - CSV only (no visualization)")
        print("")
        print("  csv_output_file: CSV output filename (optional)")
        print("                   Auto-generated when omitted")
        sys.exit(1)
    
    plot_type = sys.argv[1]
    csv_output = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print("[INIT] Initializing ROS 2...")
        rclpy.init()
        
        print("[INIT] Creating visualizer node...")
        record_interval = 0.1  # 10 Hz
        visualizer = AutowareEKFVisualizer(max_points=1000, record_interval=record_interval)
        print(f"[INIT] Recording interval: {record_interval}s (10 Hz)")
        
        # Spin ROS 2 in background
        print("[INIT] Starting ROS 2 spin thread...")
        ros_thread = threading.Thread(target=spin_ros, args=(visualizer,), daemon=True)
        ros_thread.start()
        
        print(f"[MAIN] Autoware EKF Visualizer started: plot_type={plot_type}")
        print("[MAIN] Waiting for data reception... (Ctrl+C to stop)")
        
        # Wait for incoming data (timeout: 120 seconds)
        wait_count = 0
        max_wait = 120
        while not visualizer.data_received and wait_count < max_wait:
            wait_count += 1
            print(f"[WAIT] Waiting for data... ({wait_count}/{max_wait}s)", end='\r')
            time.sleep(1)
        
        if wait_count >= max_wait:
            print(f"\n[TIMEOUT] Data reception timeout after {max_wait}s. Shutting down...")
            raise TimeoutError("No data received within timeout period")
        
        print()
        print(f"[MAIN] Data reception started (#{visualizer.counter})")
        time.sleep(2)  # Continue receiving for 2 more seconds
        
        # Start runtime timeout (120 seconds)
        startup_time = time.time()
        max_runtime = 120
        
        # Start plotting
        if plot_type == '2d':
            visualizer.plot_2d_trajectory()
        elif plot_type == '3d':
            visualizer.plot_3d_trajectory()
        elif plot_type == 'velocity':
            visualizer.plot_velocity()
        elif plot_type == 'csv':
            print(f"[INFO] Running for max {max_runtime} seconds (Ctrl+C to exit early)...")
            try:
                while time.time() - startup_time < max_runtime:
                    time.sleep(1)
                print(f"\n[TIMEOUT] Reached {max_runtime}s runtime limit. Shutting down...")
            except KeyboardInterrupt:
                pass
        else:
            print(f"Unknown plot type: {plot_type}")
    
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Shutting down...")
    except TimeoutError as e:
        print(f"\n[TIMEOUT] {e}")
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[INFO] Cleaning up...")
        try:
            # Save CSV
            if 'visualizer' in locals():
                if csv_output:
                    visualizer.save_csv(csv_output)
                else:
                    visualizer.save_csv()
        except Exception as e:
            print(f"[WARNING] Failed to save CSV: {e}")
        try:
            rclpy.shutdown()
        except:
            pass
        print("[INFO] Done.")


if __name__ == '__main__':
    main()
