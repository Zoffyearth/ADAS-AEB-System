"""
MATLAB Engine API 桥接模块
用于在 Python 中调用 MATLAB/Simulink 进行车辆动力学仿真

前提条件:
    1. 已安装 MATLAB (R2020a+)
    2. 已安装 MATLAB Engine API for Python:
       cd "C:\Program Files\MATLAB\R20xxx\extern\engines\python"
       python setup.py install

使用方式:
    bridge = MatlabBridge()
    result = bridge.run_vehicle_sim(brake_signal, initial_speed)
    bridge.close()
"""
import numpy as np
from typing import Dict, List, Optional
import warnings


class MatlabBridge:
    """MATLAB Engine 桥接"""

    def __init__(self):
        self.eng = None
        self.available = False

        try:
            import matlab.engine
            self.eng = matlab.engine.start_matlab()
            self.available = True
            print("[MatlabBridge] MATLAB Engine 连接成功")
        except ImportError:
            warnings.warn(
                "[MatlabBridge] MATLAB Engine API 未安装。\n"
                "  安装方法:\n"
                '  cd "MATLAB安装目录\\extern\\engines\\python"\n'
                "  python setup.py install\n"
                "  将使用 Python 车辆模型作为备选。"
            )
        except Exception as e:
            warnings.warn(f"[MatlabBridge] MATLAB 启动失败: {e}\n  将使用 Python 车辆模型作为备选。")

    def run_vehicle_sim(self,
                        brake_signal: List[float],
                        initial_speed: float,
                        dt: float = 0.05) -> Dict:
        """
        通过 MATLAB Simulink 运行车辆动力学仿真

        Args:
            brake_signal: 制动信号列表
            initial_speed: 初始速度 (m/s)
            dt: 时间步长

        Returns:
            仿真结果字典
        """
        if not self.available:
            # 回退到 Python 模型
            from .vehicle_model import VehicleDynamics
            model = VehicleDynamics()
            return model.simulate(brake_signal, initial_speed, dt)

        try:
            # 转换为 MATLAB 数组
            brake_mat = matlab.double(brake_signal)
            time = np.arange(len(brake_signal)) * dt
            time_mat = matlab.double(time.tolist())

            # 调用 MATLAB 函数 (见 matlab/aeb_controller.m)
            speed, decel, distance = self.eng.aeb_simulate(
                brake_mat, float(initial_speed), float(dt), nargout=3
            )

            speed_np = np.array(speed).flatten()
            decel_np = np.array(decel).flatten()
            distance_np = np.array(distance).flatten()

            return {
                'time': np.array(time),
                'speed': speed_np,
                'speed_kmh': speed_np * 3.6,
                'deceleration': decel_np,
                'distance': distance_np,
                'brake_active': np.array(brake_signal),
                'stopping_time': float(time[-1]) if speed_np[-1] > 0.01
                                  else float(time[np.argmax(speed_np <= 0.01)]),
                'stopping_distance': float(distance_np[-1]),
            }

        except Exception as e:
            warnings.warn(f"[MatlabBridge] 仿真出错，回退到 Python 模型: {e}")
            from .vehicle_model import VehicleDynamics
            model = VehicleDynamics()
            return model.simulate(brake_signal, initial_speed, dt)

    def close(self):
        """关闭 MATLAB Engine"""
        if self.eng is not None:
            try:
                self.eng.quit()
            except:
                pass
            self.eng = None
