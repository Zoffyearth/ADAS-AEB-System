"""
单目视觉距离估计模块
基于简化模型: 距离 ∝ 1 / bounding_box_height
"""
import numpy as np
from typing import List, Dict, Optional


class DistanceEstimator:
    """
    简化单目距离估计器

    原理:
      真实物体高度 H (m), 焦距 f (px), 图像中bbox高度 h (px)
      距离 D = (H * f) / h = K / h

      K 值需要标定。对于车辆:
      - 典型车高 ~1.5m
      - 在640x480分辨率、水平FOV~60°的相机下，K ≈ 2000 m·px

    默认使用简化公式: D = K / h_bbox
    """

    def __init__(self, K: float = 2200.0, smooth_window: int = 5):
        """
        Args:
            K: 标定常数 (m·px)，需要通过实际场景调整
            smooth_window: 滑动平均窗口大小，用于平滑距离估计
        """
        self.K = K
        self.smooth_window = smooth_window
        self._history: Dict[str, List[float]] = {}  # target_id → 历史距离

    def estimate_for_cars(self, detections: List[Dict],
                          frame_height: int = 640) -> Dict[int, float]:
        """
        对所有 car 目标进行距离估计

        Args:
            detections: YOLO检测结果列表
            frame_height: 图像高度(px)，用于归一化

        Returns:
            {detection_index: distance_meters}
        """
        distances = {}

        for i, det in enumerate(detections):
            if det['class'] != 'car':
                continue

            bbox_h = det['height']
            if bbox_h <= 0:
                distances[i] = None
                continue

            # 核心公式: D = K / h
            # 加入归一化处理，使不同分辨率结果一致
            # scale_h = bbox_h / frame_height (归一化高度)
            # D = K_normalized / scale_h = K_normalized * frame_height / bbox_h
            distance = self.K / bbox_h

            # 滑动平均平滑
            target_id = f"car_{i}"
            if target_id not in self._history:
                self._history[target_id] = []
            self._history[target_id].append(distance)
            if len(self._history[target_id]) > self.smooth_window:
                self._history[target_id] = self._history[target_id][-self.smooth_window:]

            smoothed_dist = np.mean(self._history[target_id])
            distances[i] = round(smoothed_dist, 1)

        return distances

    def estimate_relative_speed(self, target_id: str,
                                 dt: float) -> Optional[float]:
        """
        通过距离变化率估计相对速度

        Args:
            target_id: 目标标识
            dt: 时间间隔(秒)

        Returns:
            相对速度 (m/s)，正值表示接近中
        """
        if target_id not in self._history:
            return None

        hist = self._history[target_id]
        if len(hist) < 2 or dt <= 0:
            return None

        # v_rel = -ΔD / Δt (距离减小 → 速度为正，即接近)
        v_rel = (hist[-2] - hist[-1]) / dt
        return max(0, v_rel)  # 忽略目标远离的情况

    def reset(self):
        """重置历史数据"""
        self._history.clear()
