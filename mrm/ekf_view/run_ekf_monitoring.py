#!/usr/bin/env python3
"""
Integrated EKF monitoring script
Awkernel UDP -> ROS 2 Odometry -> RViz + Visualizer

Run: python3 run_ekf_monitoring.py [--rviz] [--visualizer 2d|3d|velocity]
Options:
    --rviz              Also launch RViz
    --visualizer TYPE   Launch visualizer (2d, 3d, velocity). Default: 2d
    --output CSV        Save EKF data to CSV
"""

import subprocess
import sys
import time
import signal
import os
import json
import socket
import threading
import csv
from pathlib import Path
import argparse
from typing import List, Optional, Tuple
from collections import deque
from datetime import datetime

# ROS 2 imports
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path as PathMsg
from geometry_msgs.msg import (
    Pose, PoseWithCovariance, Twist, TwistWithCovariance, 
    PoseStamped, TransformStamped
)
from std_msgs.msg import Header
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster

# Script directories
SCRIPT_DIR = Path(__file__).parent
AUTOWARE_DIR = Path('/home/nokosan/autoware')
AWKERNEL_DIR = Path('/home/nokosan/awkernel_20260118')

# ROS 2 setup script
ROS2_SETUP = """
source /opt/ros/humble/setup.bash
source /home/nokosan/autoware/install/setup.bash
"""

# UDP settings
UDP_PORT = 26099
MAX_QUEUE = 200


def split_stamp(nanos: int) -> Tuple[int, int]:
    """Convert nanoseconds to ROS time."""
    if nanos < 0:
        nanos = 0
    sec = nanos // 1_000_000_000
    nsec = nanos % 1_000_000_000
    return int(sec), int(nsec)


class AwkernelUdpBridge(Node):
    """Awkernel UDP EKF JSON -> ROS 2 Odometry + Path + TF bridge."""
    
    def __init__(self, csv_output: Optional[Path] = None, record_interval: float = 0.05):
        super().__init__('awkernel_udp_bridge')
        self.record_interval = record_interval  # Recording interval (seconds)
        self.last_record_time = 0.0  # Last recorded timestamp

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.odom_pub = self.create_publisher(
            Odometry, '/awkernel/ekf/kinematic_state', qos
        )
        self.path_pub = self.create_publisher(PathMsg, '/awkernel/ekf/path', qos)
        
        # TF broadcasters
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)

        self.path = PathMsg()
        self.path.header.frame_id = 'map'
        self.path_buffer = deque(maxlen=2000)

        self.queue = deque(maxlen=MAX_QUEUE)
        self.received_count = 0
        self.sock_thread = threading.Thread(target=self._udp_loop, daemon=True)
        self.sock_thread.start()
        
        # CSV output settings
        self.csv_output = csv_output
        self.csv_data = []  # Recording buffer
        self.csv_lock = threading.Lock()
        
        # Publish static TF once (base_link -> imu_link)
        self._publish_static_tfs()

        self.timer = self.create_timer(0.005, self._publish_latest)  # 200 Hz (5 ms, aligned to UDP sender rate)
        self.get_logger().info(f'Awkernel UDP bridge started (port {UDP_PORT})')
        self.get_logger().info(f'Publishing rate: 200 Hz (5ms), Recording interval: {record_interval}s')
        self.get_logger().info('Publishing TF: map -> base_link -> imu_link')
        if csv_output:
            self.get_logger().info(f'CSV output will be saved to: {csv_output}')
        self.get_logger().info('Waiting for UDP packets from Awkernel...')

    def _udp_loop(self):
        """UDP listening loop."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', UDP_PORT))
        print(f'[UDP] Listening on 0.0.0.0:{UDP_PORT}')
        while rclpy.ok():
            try:
                data, addr = sock.recvfrom(8192)
                self.received_count += 1
                if self.received_count % 10 == 1:
                    print(f'[UDP] Received packet #{self.received_count} from {addr}, size={len(data)} bytes')
                self.queue.append(data)
            except Exception as e:
                print(f'[UDP] Error: {e}')
                continue

    def _publish_static_tfs(self):
        """Publish static TF: base_link -> imu_link (identity transform)."""
        static_tf = TransformStamped()
        static_tf.header.stamp = self.get_clock().now().to_msg()
        static_tf.header.frame_id = 'base_link'
        static_tf.child_frame_id = 'imu_link'
        
        # Identity transform
        static_tf.transform.translation.x = 0.0
        static_tf.transform.translation.y = 0.0
        static_tf.transform.translation.z = 0.0
        static_tf.transform.rotation.x = 0.0
        static_tf.transform.rotation.y = 0.0
        static_tf.transform.rotation.z = 0.0
        static_tf.transform.rotation.w = 1.0
        
        self.static_tf_broadcaster.sendTransform(static_tf)
        self.get_logger().info('[TF] Static TF published: base_link -> imu_link')

    def _publish_latest(self):
        """Publish latest Odometry."""
        if not self.queue:
            return
        raw = self.queue.pop()
        self.queue.clear()
        try:
            payload = json.loads(raw.decode('utf-8'))
            self.get_logger().info(
                f'Publishing data: pos=('
                f'{payload.get("pose", {}).get("pose", {}).get("position", {}).get("x", 0):.2f}, '
                f'{payload.get("pose", {}).get("pose", {}).get("position", {}).get("y", 0):.2f})'
            )
        except Exception as e:
            self.get_logger().warn(f'JSON parse error: {e}')
            return

        # Note: Awkernel sends timestamp in SECONDS (not nanoseconds)
        odom = self._to_odometry(payload)
        if odom is None:
            return

        self.odom_pub.publish(odom)
        
        # Publish dynamic TF: map -> base_link
        self._publish_tf_from_odometry(odom)

        # Update Path
        pose_stamped = PoseStamped()
        pose_stamped.header = odom.header
        pose_stamped.pose = odom.pose.pose
        self.path_buffer.append(pose_stamped)
        self.path.header = odom.header
        self.path.poses = list(self.path_buffer)
        self.path_pub.publish(self.path)
        
        # Record to CSV
        if self.csv_output:
            self._record_to_csv(odom, payload)

    def _publish_tf_from_odometry(self, odom: Odometry):
        """Publish TF from Odometry: map -> base_link."""
        tf = TransformStamped()
        tf.header = odom.header
        tf.child_frame_id = odom.child_frame_id
        
        tf.transform.translation.x = odom.pose.pose.position.x
        tf.transform.translation.y = odom.pose.pose.position.y
        tf.transform.translation.z = odom.pose.pose.position.z
        tf.transform.rotation = odom.pose.pose.orientation
        
        self.tf_broadcaster.sendTransform(tf)

    def _record_to_csv(self, odom: Odometry, raw_payload: dict):
        """Record Odometry data in CSV format."""
        timestamp = odom.header.stamp.sec + odom.header.stamp.nanosec / 1e9
        
        # Recording interval check (skip if interval has not elapsed)
        if timestamp - self.last_record_time < self.record_interval:
            return
        
        self.last_record_time = timestamp
        
        row = {
            'timestamp': timestamp,
            'pos_x': odom.pose.pose.position.x,
            'pos_y': odom.pose.pose.position.y,
            'pos_z': odom.pose.pose.position.z,
            'ori_x': odom.pose.pose.orientation.x,
            'ori_y': odom.pose.pose.orientation.y,
            'ori_z': odom.pose.pose.orientation.z,
            'ori_w': odom.pose.pose.orientation.w,
            'vel_x': odom.twist.twist.linear.x,
            'vel_y': odom.twist.twist.linear.y,
            'vel_z': odom.twist.twist.linear.z,
            'ang_x': odom.twist.twist.angular.x,
            'ang_y': odom.twist.twist.angular.y,
            'ang_z': odom.twist.twist.angular.z,
            'pose_cov_0': odom.pose.covariance[0],
            'pose_cov_5': odom.pose.covariance[5],
            'pose_cov_10': odom.pose.covariance[10],
            'twist_cov_0': odom.twist.covariance[0],
            'twist_cov_5': odom.twist.covariance[5],
            'twist_cov_10': odom.twist.covariance[10],
        }
        
        with self.csv_lock:
            self.csv_data.append(row)
    
    def save_csv(self):
        """Save recorded data to CSV file."""
        if not self.csv_output or not self.csv_data:
            return
        
        try:
            with self.csv_lock:
                with open(self.csv_output, 'w', newline='') as f:
                    fieldnames = list(self.csv_data[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.csv_data)
            
            self.get_logger().info(
                f'[CSV] Saved {len(self.csv_data)} records to {self.csv_output}'
            )
        except Exception as e:
            self.get_logger().error(f'[CSV] Failed to save: {e}')

    def _to_odometry(self, msg: dict) -> Optional[Odometry]:
        """Convert JSON payload to an Odometry message."""
        header_dict = msg.get('header', {})
        frame_id = header_dict.get('frame_id', 'map')
        # Note: Awkernel sends timestamp in NANOSECONDS (from uptime_nano())
        timestamp_nanos = int(header_dict.get('timestamp', 0))
        sec, nsec = split_stamp(timestamp_nanos)

        child_frame_id = msg.get('child_frame_id', 'base_link')
        pose_dict = msg.get('pose', {}).get('pose', {})
        pos = pose_dict.get('position', {})
        ori = pose_dict.get('orientation', {})
        pose_cov = msg.get('pose', {}).get('covariance', [])

        twist_dict = msg.get('twist', {}).get('twist', {})
        lin = twist_dict.get('linear', {})
        ang = twist_dict.get('angular', {})
        twist_cov = msg.get('twist', {}).get('covariance', [])

        odom = Odometry()
        odom.header = Header(
            stamp=rclpy.time.Time(seconds=sec, nanoseconds=nsec).to_msg(),
            frame_id=frame_id
        )
        odom.child_frame_id = child_frame_id

        odom.pose.pose = Pose()
        odom.pose.pose.position.x = float(pos.get('x', 0.0))
        odom.pose.pose.position.y = float(pos.get('y', 0.0))
        odom.pose.pose.position.z = float(pos.get('z', 0.0))
        odom.pose.pose.orientation.x = float(ori.get('x', 0.0))
        odom.pose.pose.orientation.y = float(ori.get('y', 0.0))
        odom.pose.pose.orientation.z = float(ori.get('z', 0.0))
        odom.pose.pose.orientation.w = float(ori.get('w', 1.0))

        cov_padded = list(pose_cov) + [0.0] * (36 - len(pose_cov))
        odom.pose.covariance = cov_padded[:36]

        odom.twist.twist = Twist()
        odom.twist.twist.linear.x = float(lin.get('x', 0.0))
        odom.twist.twist.linear.y = float(lin.get('y', 0.0))
        odom.twist.twist.linear.z = float(lin.get('z', 0.0))
        odom.twist.twist.angular.x = float(ang.get('x', 0.0))
        odom.twist.twist.angular.y = float(ang.get('y', 0.0))
        odom.twist.twist.angular.z = float(ang.get('z', 0.0))

        cov_twist_padded = list(twist_cov) + [0.0] * (36 - len(twist_cov))
        odom.twist.covariance = cov_twist_padded[:36]

        return odom


class ProcessManager:
    """Manage multiple processes and threads."""
    def __init__(self, csv_output: Optional[Path] = None):
        self.processes: List[subprocess.Popen] = []
        self.threads: List[threading.Thread] = []
        self.ros_node: Optional[AwkernelUdpBridge] = None
        self.ros_thread: Optional[threading.Thread] = None
        self.running = True
        self.csv_output = csv_output
        
        # Ctrl+C handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Signal handler."""
        print("\n[INFO] Shutdown signal received")
        self.shutdown()
        sys.exit(0)
    
    def start_ros_bridge(self) -> bool:
        """Start ROS 2 UDP bridge."""
        try:
            print("[ROS UDP Bridge] Initializing...")
            rclpy.init()
            self.ros_node = AwkernelUdpBridge(csv_output=self.csv_output)
            
            # Run ROS node in a separate thread
            def run_ros():
                try:
                    rclpy.spin(self.ros_node)
                except KeyboardInterrupt:
                    pass
                finally:
                    if self.ros_node:
                        self.ros_node.destroy_node()
                    rclpy.shutdown()
            
            self.ros_thread = threading.Thread(target=run_ros, daemon=True)
            self.ros_thread.start()
            print("[ROS UDP Bridge] Started")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start ROS UDP Bridge: {e}")
            return False
    
    def run_command(
        self,
        cmd: str,
        name: str,
        background: bool = True,
        cwd: Optional[Path] = None
    ) -> Optional[subprocess.Popen]:
        """
        Run a command.

        Args:
            cmd: Command to execute.
            name: Process name for logs.
            background: Whether to run in background.
            cwd: Working directory.

        Returns:
            Popen object (None when background=False).
        """
        try:
            # Build shell command with ROS 2 environment setup
            full_cmd = f"bash -c '{ROS2_SETUP} {cmd}'"
            
            print(f"[{name}] Start: {cmd}")
            
            if background:
                process = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd
                )
                self.processes.append(process)
                
                # Log output thread
                thread = threading.Thread(
                    target=self._log_output,
                    args=(process, name),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)
                
                print(f"[{name}] Started (PID: {process.pid})")
                return process
            else:
                result = subprocess.run(
                    full_cmd,
                    shell=True,
                    cwd=cwd
                )
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to start {name}: {e}")
            return None
    
    def _log_output(self, process: subprocess.Popen, name: str):
        """Log process output."""
        try:
            while process.poll() is None:
                line = process.stdout.readline()
                if line:
                    print(f"[{name}] {line.decode().rstrip()}")
                time.sleep(0.01)
        except:
            pass
    
    def shutdown(self):
        """Terminate all processes and threads."""
        print("\n[INFO] Shutting down all processes...")
        
        # Stop ROS node (including CSV save)
        if self.ros_node:
            try:
                print("[ROS UDP Bridge] Saving CSV data...")
                self.ros_node.save_csv()
                print("[ROS UDP Bridge] Stopping...")
                self.ros_node.destroy_node()
            except Exception as e:
                print(f"[ERROR] ROS node shutdown error: {e}")
        
        # Terminate processes
        for i, proc in enumerate(self.processes):
            if proc and proc.poll() is None:
                try:
                    print(f"[Process {i+1}] Stopping... (PID: {proc.pid})")
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                except Exception as e:
                    print(f"[ERROR] Process termination error: {e}")
        
        print("[INFO] Shutdown complete")
    
    def wait_for_all(self):
        """Wait for all processes to terminate."""
        try:
            for proc in self.processes:
                if proc:
                    proc.wait()
        except KeyboardInterrupt:
            self.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description='Integrated EKF monitoring script\nAwkernel UDP -> ROS 2 -> RViz + Visualizer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--rviz',
        action='store_true',
        help='Launch RViz'
    )
    parser.add_argument(
        '--visualizer',
        choices=['2d', '3d', 'velocity'],
        default='2d',
        help='Visualizer type (default: 2d)'
    )
    parser.add_argument(
        '--output',
        type=str,
        metavar='CSV_PATH',
        help='Save EKF data to a CSV file'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=120,
        metavar='SECONDS',
        help='Execution timeout in seconds (default: 120)'
    )
    
    args = parser.parse_args()
    
    # Create CSV output directory
    csv_dir = SCRIPT_DIR / 'csv'
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    # Resolve CSV output path
    csv_output = None
    if args.output:
        csv_output = csv_dir / Path(args.output).name
    else:
        # Default output path
        csv_output = csv_dir / f'ekf_data_bridge_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    print("=" * 70)
    print("Integrated EKF Monitoring Script - Multi-process / Multi-thread")
    print("=" * 70)
    print(f"CSV output: {csv_output}")
    print()
    
    manager = ProcessManager(csv_output=csv_output)
    
    # Step 1: Start ROS 2 UDP bridge (thread)
    print("[Step 1] Starting ROS 2 UDP bridge...")
    if not manager.start_ros_bridge():
        print("[ERROR] Failed to start ROS 2 UDP bridge")
        return
    time.sleep(1)  # Wait for bridge initialization
    
    # Step 2: Start visualizer (2D/3D trajectory)
    print(f"[Step 2] Starting visualizer ({args.visualizer} mode)...")
    viz_script = SCRIPT_DIR / 'ekf_visualizer.py'
    if viz_script.exists():
        manager.run_command(
            f"python3 {viz_script} {args.visualizer}",
            f"Visualizer ({args.visualizer})",
            background=True
        )
        time.sleep(1)
    else:
        print(f"[WARNING] Visualizer script not found: {viz_script}")
    
    # Step 3: Launch RViz (optional)
    if args.rviz:
        print("[Step 3] Launching RViz...")
        rviz_config = AUTOWARE_DIR / 'src/launcher/autoware_launch/rviz/autoware.rviz'
        if rviz_config.exists():
            manager.run_command(
                f"rviz2 -d {rviz_config}",
                "RViz",
                background=True
            )
        else:
            manager.run_command(
                "rviz2",
                "RViz",
                background=True
            )
        time.sleep(2)
    
    print()
    print("=" * 70)
    print("All components started")
    print("=" * 70)
    print()
    print("Monitoring... (Ctrl+C to stop)")
    print()
    
    # Timeout setting
    if args.timeout > 0:
        print(f"Timeout: {args.timeout} seconds")
        threading.Timer(args.timeout, manager.shutdown).start()
    
    # Wait for all processes
    try:
        manager.wait_for_all()
    except KeyboardInterrupt:
        manager.shutdown()
    finally:
        print("\n[INFO] Script finished")


if __name__ == '__main__':
    main()
