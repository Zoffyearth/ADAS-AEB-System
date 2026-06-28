"""
简化车辆动力学模型 (Python版)
当 MATLAB 不可用时作为备选方案

模型描述:
    - 一维纵向动力学
    - 输入: brake_signal (0/1), initial_speed (m/s)
    - 输出: speed curve, deceleration curve

参数:
    - m = 1500 kg      (整车质量)
    - a_max = 8 m/s²   (最大制动减速度)
    - response_delay = 0.3s (制动响应延迟)
"""
import numpy as np
from typing import Tuple, List, Dict


class VehicleDynamics:
    """一维车辆纵向动力学模型"""

    def __init__(self,
                 mass: float = 1500.0,
                 max_deceleration: float = 8.0,
                 response_delay: float = 0.3,
                 drag_coefficient: float = 0.3,
                 rolling_resistance: float = 0.015,
                 road_friction: float = 0.8):
        """
        Args:
            mass: 整车质量 (kg)
            max_deceleration: 最大制动减速度 (m/s²)
            response_delay: 制动系统响应延迟 (s)
            drag_coefficient: 空气阻力系数
            rolling_resistance: 滚动阻力系数
            road_friction: 路面摩擦系数
        """
        self.m = mass
        self.a_max = max_deceleration * road_friction  # 考虑路面摩擦
        self.tau = response_delay
        self.Cd = drag_coefficient
        self.Cr = rolling_resistance
        self.g = 9.81

    def simulate(self,
                 brake_signal: List[float],
                 initial_speed: float,
                 dt: float = 0.05) -> Dict[str, np.ndarray]:
        """
        仿真车辆在制动信号下的动力学响应

        Args:
            brake_signal: 制动信号序列 [0=不制动, 1=制动]
            initial_speed: 初始速度 (m/s) 或 (km/h)
            dt: 仿真步长 (秒)

        Returns:
            {
                'time': np.ndarray,          # 时间序列
                'speed': np.ndarray,         # 速度 (m/s)
                'speed_kmh': np.ndarray,     # 速度 (km/h)
                'deceleration': np.ndarray,  # 减速度 (m/s²)
                'distance': np.ndarray,      # 行驶距离 (m)
                'brake_active': np.ndarray,  # 制动状态
                'stopping_time': float,      # 刹停时间
                'stopping_distance': float,  # 刹车距离
            }
        """
        n_steps = len(brake_signal)
        time = np.arange(n_steps) * dt

        speed = np.zeros(n_steps)
        decel = np.zeros(n_steps)
        distance = np.zeros(n_steps)
        brake_delayed = np.zeros(n_steps)

        speed[0] = initial_speed
        brake_pressure = 0.0

        for i in range(1, n_steps):
            # 制动系统延迟 (一阶滞后)
            target_brake = brake_signal[i]
            brake_pressure += (target_brake - brake_pressure) * dt / self.tau
            brake_delayed[i] = brake_pressure if brake_pressure > 0.1 else 0.0

            # 制动力
            F_brake = brake_pressure * self.m * self.a_max

            # 空气阻力: F_drag = 0.5 * ρ * Cd * A * v² ≈ Cd * v² (简化)
            F_drag = self.Cd * speed[i-1]**2 * 0.3

            # 滚动阻力
            F_roll = self.Cr * self.m * self.g

            # 总阻力
            F_total = F_brake + F_drag + F_roll

            # 加速度 (F_total 是阻力，产生减速度)
            acc = -F_total / self.m
            acc = max(acc, -self.a_max * 1.1)  # 限制最大减速度

            # 欧拉积分
            speed[i] = max(0, speed[i-1] + acc * dt)
            decel[i] = abs(acc)

            # 距离积分 (梯形法则)
            distance[i] = distance[i-1] + 0.5 * (speed[i-1] + speed[i]) * dt

        # 找到刹停时间
        stopped_idx = np.argmax(speed <= 0.1)
        if speed[stopped_idx] > 0.1:
            stopping_time = time[-1]
            stopping_distance = distance[-1]
        else:
            stopping_time = time[stopped_idx]
            stopping_distance = distance[stopped_idx]

        return {
            'time': time,
            'speed': speed,
            'speed_kmh': speed * 3.6,
            'deceleration': decel,
            'distance': distance,
            'brake_active': brake_delayed,
            'stopping_time': round(float(stopping_time), 2),
            'stopping_distance': round(float(stopping_distance), 2),
        }

    def emergency_brake_scenario(self,
                                  initial_speed_kmh: float = 60.0,
                                  brake_trigger_frame: int = 100,
                                  total_frames: int = 300,
                                  dt: float = 0.05) -> Dict:
        """
        紧急制动场景: 在指定帧触发制动

        Args:
            initial_speed_kmh: 初始车速 (km/h)
            brake_trigger_frame: 制动触发帧
            total_frames: 总仿真帧数
            dt: 时间步长

        Returns:
            仿真结果字典
        """
        brake_signal = np.zeros(total_frames)
        brake_signal[brake_trigger_frame:] = 1.0

        return self.simulate(
            brake_signal=brake_signal.tolist(),
            initial_speed=initial_speed_kmh / 3.6,
            dt=dt,
        )
