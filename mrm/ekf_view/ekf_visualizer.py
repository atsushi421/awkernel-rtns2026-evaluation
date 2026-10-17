#!/usr/bin/env python3
"""
EKF Odometry ROS topic receiver -> trajectory visualization tool.
Subscribes to ROS 2 /awkernel/ekf/kinematic_state and plots trajectories.
"""
import threading
import time
import csv
from collections import deque
from pathlib import Path
from datetime import datetime
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


class EKFVisualizerNode(Node):
    """Subscribe to ROS 2 Odometry topic and visualize trajectory."""
    
    def __init__(self, max_points=1000, plot_type='2d', csv_output: str = None):
        super().__init__('ekf_visualizer')
        
        self.max_points = max_points
        self.plot_type = plot_type
        
        # CSV output settings
        if csv_output:
            self.csv_output = Path(csv_output)
        else:
            # Default: save to ekf_view/csv directory
            csv_dir = Path(__file__).parent / 'csv'
            csv_dir.mkdir(parents=True, exist_ok=True)
            self.csv_output = csv_dir / f'ekf_data_visualizer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Position data buffers
        self.x_data = deque(maxlen=max_points)
        self.y_data = deque(maxlen=max_points)
        self.z_data = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        
        # Velocity data buffers
        self.vx_data = deque(maxlen=max_points)
        self.vy_data = deque(maxlen=max_points)
        self.vz_data = deque(maxlen=max_points)
        
        self.data_lock = threading.Lock()
        self.counter = 0
        
        # ROS topic subscription
        self.subscription = self.create_subscription(
            Odometry,
            '/awkernel/ekf/kinematic_state',
            self.odometry_callback,
            10
        )
        
        self.get_logger().info('EKF Visualizer node initialized')
        self.get_logger().info(f'Listening to /awkernel/ekf/kinematic_state')
        self.get_logger().info(f'CSV output: {self.csv_output}')
    
    def odometry_callback(self, msg: Odometry):
        """Odometry message callback."""
        self.counter += 1
        
        # Extract position
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        z = msg.pose.pose.position.z
        
        # Extract velocity
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        vz = msg.twist.twist.linear.z
        
        # Timestamp
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
        
        with self.data_lock:
            self.x_data.append(x)
            self.y_data.append(y)
            self.z_data.append(z)
            self.vx_data.append(vx)
            self.vy_data.append(vy)
            self.vz_data.append(vz)
            self.timestamps.append(timestamp)
        
        if self.counter % 10 == 0:
            self.get_logger().info(
                f'Received #{self.counter}: pos=({x:.3f}, {y:.3f}, {z:.3f}), '
                f'vel=({vx:.3f}, {vy:.3f}, {vz:.3f})'
            )
    
    def plot_2d_trajectory(self):
        """2D trajectory plot (top-down view)."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        def animate(frame):
            ax1.clear()
            ax2.clear()
            
            with self.data_lock:
                if len(self.x_data) > 0:
                    xs = list(self.x_data)
                    ys = list(self.y_data)
                    zs = list(self.z_data)
                    
                    # XY plane (top-down)
                    ax1.plot(xs, ys, 'b-', label='EKF Trajectory', linewidth=2)
                    ax1.scatter(xs[-1], ys[-1], c='r', s=100, label='Current Position', zorder=5)
                    ax1.set_xlabel('X [m]')
                    ax1.set_ylabel('Y [m]')
                    ax1.set_title('EKF Trajectory')
                    ax1.legend()
                    ax1.grid(True)
                    ax1.axis('equal')
                    
                    # Z trajectory
                    ax2.plot(range(len(zs)), zs, 'g-', label='Z Coordinate', linewidth=2)
                    ax2.set_xlabel('Sample Number')
                    ax2.set_ylabel('Z [m]')
                    ax2.set_title('Height Change')
                    ax2.legend()
                    ax2.grid(True)
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.tight_layout()
        plt.show()
    
    def plot_3d_trajectory(self):
        """3D trajectory plot."""
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
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
                    ax.set_title('EKF Trajectory (3D)')
                    ax.legend()
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.show()
    
    def plot_velocity(self):
        """Velocity time-series plot."""
        fig, ax = plt.subplots(figsize=(12, 5))
        
        def animate(frame):
            ax.clear()
            
            with self.data_lock:
                if len(self.vx_data) > 0:
                    frames = range(len(self.vx_data))
                    ax.plot(frames, list(self.vx_data), label='Vx', linewidth=2)
                    ax.plot(frames, list(self.vy_data), label='Vy', linewidth=2)
                    ax.plot(frames, list(self.vz_data), label='Vz', linewidth=2)
                    ax.set_xlabel('Sample Number')
                    ax.set_ylabel('Velocity [m/s]')
                    ax.set_title('EKF Velocity Transition')
                    ax.legend()
                    ax.grid(True)
        
        ani = FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
        plt.show()
    
    def save_csv(self):
        """Save data to CSV."""
        try:
            with open(self.csv_output, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'x', 'y', 'z', 'vx', 'vy', 'vz'])
                
                with self.data_lock:
                    for ts, x, y, z, vx, vy, vz in zip(
                        self.timestamps, self.x_data, self.y_data, self.z_data,
                        self.vx_data, self.vy_data, self.vz_data
                    ):
                        writer.writerow([ts, x, y, z, vx, vy, vz])
            
            print(f"[CSV] Saved to: {self.csv_output}")
        except Exception as e:
            print(f"[ERROR] Failed to save CSV: {e}")
    
    def start(self, plot_type='2d'):
        """Start ROS node and visualization"""
        # Wait for data to arrive
        print("[INFO] Waiting for EKF data...")
        time.sleep(2)
        
        # Check if data was received
        with self.data_lock:
            if len(self.x_data) == 0:
                print("[WARNING] No data received from ROS topic")
        
        # Start visualization
        self.get_logger().info(f"Starting {plot_type} visualization")
        if plot_type == '2d':
            self.plot_2d_trajectory()
        elif plot_type == '3d':
            self.plot_3d_trajectory()
        elif plot_type == 'velocity':
            self.plot_velocity()
        else:
            print("Unknown plot type")
        
        self.save_csv()

if __name__ == '__main__':
    import sys
    
    # Get plot type from command line
    plot_type = sys.argv[1] if len(sys.argv) > 1 else '2d'
    csv_output = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Initialize ROS 2 first
        rclpy.init(args=None)
        
        print(f"[INFO] Starting EKF Visualizer (plot_type={plot_type})")
        print("[INFO] Subscribing to ROS topic: /awkernel/ekf/kinematic_state")
        print("[INFO] Press Ctrl+C to shutdown")
        
        visualizer = EKFVisualizerNode(max_points=1000, plot_type=plot_type, csv_output=csv_output)
        
        # Create spinner thread to receive ROS messages
        spinner_thread = threading.Thread(target=rclpy.spin, args=(visualizer,), daemon=True)
        spinner_thread.start()
        
        visualizer.start(plot_type=plot_type)
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Shutting down...")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        rclpy.shutdown()
