"""
TTC 碰撞风险评估 + AEB 制动决策模块
"""
from typing import Dict, Optional, Tuple
from enum import Enum
import time


class AEBState(Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BRAKE = "BRAKE"


class RiskAssessor:
    """
    TTC (Time To Collision) 评估器

    决策规则:
        TTC > 2.0s  → SAFE     (安全)
        TTC 1.0-2.0s → WARNING  (预警)
        TTC < 1.0s  → BRAKE    (紧急制动)

    输出信号:
        - warning_signal: bool
        - brake_signal: bool
    """

    # AEB 阈值
    TTC_WARNING = 2.0   # 预警阈值
    TTC_BRAKE   = 1.0   # 制动阈值

    def __init__(self, ttc_warning: float = 2.0, ttc_brake: float = 1.0):
        """
        Args:
            ttc_warning: TTC 预警阈值 (秒)
            ttc_brake: TTC 紧急制动阈值 (秒)
        """
        self.TTC_WARNING = ttc_warning
        self.TTC_BRAKE = ttc_brake

        # 记录历史
        self._ttc_history = []
        self._state_history = []
        self._signal_history = []

    def calculate_ttc(self, distance: float, relative_speed: float) -> Optional[float]:
        """
        计算 TTC (Time To Collision)

        Args:
            distance: 距离 (米)
            relative_speed: 相对速度 (米/秒)，正值表示接近

        Returns:
            TTC (秒)，无碰撞风险时返回 None
        """
        if relative_speed <= 0:
            # 相对速度为0或负值(远离)，无碰撞风险
            return None

        if distance <= 0:
            return 0.0

        ttc = distance / relative_speed
        return round(ttc, 3)

    def assess(self, distance: float, relative_speed: float) -> Dict:
        """
        综合风险评估

        Args:
            distance: 到最近车辆的距离 (米)
            relative_speed: 相对速度 (米/秒)

        Returns:
            {
                'ttc': float or None,
                'state': AEBState,
                'signal': str ('NONE' | 'WARNING' | 'BRAKE'),
                'warning': bool,
                'brake': bool,
                'message': str,
                'color': str,      # 用于前端显示
            }
        """
        ttc = self.calculate_ttc(distance, relative_speed)

        if ttc is None:
            state = AEBState.SAFE
            signal = 'NONE'
            message = '安全 — 无碰撞风险'
            color = '#22c55e'  # green
        elif ttc < self.TTC_BRAKE:
            state = AEBState.BRAKE
            signal = 'BRAKE'
            message = f'紧急制动! TTC={ttc:.2f}s'
            color = '#ef4444'  # red
        elif ttc < self.TTC_WARNING:
            state = AEBState.WARNING
            signal = 'WARNING'
            message = f'碰撞预警! TTC={ttc:.2f}s'
            color = '#eab308'  # yellow
        else:
            state = AEBState.SAFE
            signal = 'NONE'
            message = f'安全 TTC={ttc:.2f}s'
            color = '#22c55e'  # green

        result = {
            'ttc': ttc,
            'state': state.value,
            'signal': signal,
            'warning': signal == 'WARNING',
            'brake': signal == 'BRAKE',
            'message': message,
            'color': color,
        }

        self._ttc_history.append(ttc)
        self._state_history.append(state)
        self._signal_history.append(signal)

        return result

    def get_history(self) -> Dict:
        """获取评估历史"""
        return {
            'ttc': self._ttc_history,
            'state': [s.value for s in self._state_history],
            'signal': self._signal_history,
        }

    def reset(self):
        """重置历史"""
        self._ttc_history.clear()
        self._state_history.clear()
        self._signal_history.clear()
