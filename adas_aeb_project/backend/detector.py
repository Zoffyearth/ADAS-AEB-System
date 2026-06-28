"""
YOLOv8 目标检测模块
检测三类目标: car, person, traffic light
"""
import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import List, Tuple, Optional, Dict


class YOLODetector:
    """YOLOv8 目标检测器，专用于ADAS场景"""

    # 需要检测的三类目标
    TARGET_CLASSES = {
        'car':              [2],       # COCO: car
        'person':           [0],       # COCO: person
        'traffic light':    [9],       # COCO: traffic light
    }

    # 显示颜色映射 (BGR)
    CLASS_COLORS = {
        'car':              (0, 255, 0),     # 绿色
        'person':           (0, 165, 255),   # 橙色
        'traffic light':    (0, 255, 255),   # 黄色
    }

    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.35):
        """
        初始化检测器

        Args:
            model_path: YOLOv8 模型权重路径
            conf_threshold: 置信度阈值
        """
        self.conf_threshold = conf_threshold

        # 查找模型文件
        if not Path(model_path).exists():
            # 尝试在多个位置查找
            search_paths = [
                Path(__file__).parent.parent / model_path,           # adas_aeb_project/
                Path(__file__).parent.parent.parent / model_path,   # ros2/ (上层项目根)
                Path.cwd() / model_path,                              # 当前工作目录
            ]
            found = False
            for alt_path in search_paths:
                if alt_path.exists():
                    model_path = str(alt_path)
                    found = True
                    break
            if not found:
                searched = '\n  '.join(str(p) for p in search_paths)
                raise FileNotFoundError(
                    f"模型文件未找到: {model_path}\n"
                    f"已搜索:\n  {searched}\n"
                    f"请确保 yolov8n.pt 存在于上述路径之一"
                )

        self.model = YOLO(model_path)
        self.model.to('cpu')  # CPU 运行

        # 构建反向映射: COCO class_id → 我们的类别名
        self.coco_to_label: Dict[int, str] = {}
        for label, coco_ids in self.TARGET_CLASSES.items():
            for cid in coco_ids:
                self.coco_to_label[cid] = label

        self.allowed_ids = set(self.coco_to_label.keys())

        print(f"[Detector] YOLOv8 模型已加载: {model_path}")
        print(f"[Detector] 检测类别: {list(self.TARGET_CLASSES.keys())}")
        print(f"[Detector] 置信度阈值: {self.conf_threshold}")

    def detect_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        对单帧图像进行目标检测

        Args:
            frame: BGR图像 (numpy array)

        Returns:
            检测结果列表，每个元素包含:
            {
                'class': str,          # 类别名
                'confidence': float,   # 置信度
                'bbox': [x1,y1,x2,y2], # 边界框
                'center_x': int,
                'center_y': int,
                'width': int,
                'height': int,
            }
        """
        results = self.model(frame, verbose=False)
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if cls_id not in self.allowed_ids:
                    continue
                if conf < self.conf_threshold:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                label = self.coco_to_label[cls_id]
                w = x2 - x1
                h = y2 - y1

                detections.append({
                    'class': label,
                    'confidence': round(conf, 3),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'center_x': int((x1 + x2) / 2),
                    'center_y': int((y1 + y2) / 2),
                    'width': int(w),
                    'height': int(h),
                })

        return detections

    def draw_detections(self, frame: np.ndarray, detections: List[Dict],
                        distances: Optional[Dict[int, float]] = None,
                        risk_info: Optional[Dict] = None) -> np.ndarray:
        """
        在图像上绘制检测框和信息叠加

        Args:
            frame: 原始图像
            detections: 检测结果列表
            distances: 每个检测目标(索引)的距离
            risk_info: {'ttc': float, 'status': str, 'signal': str}

        Returns:
            绘制后的图像
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det['bbox']
            cls_name = det['class']
            conf = det['confidence']
            color = self.CLASS_COLORS.get(cls_name, (255, 255, 255))

            # 绘制边界框
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # 构建标签文本
            label_parts = [f"{cls_name} {conf:.2f}"]

            if distances and i in distances:
                dist = distances[i]
                if dist is not None:
                    label_parts.append(f"D:{dist:.1f}m")

            label = " | ".join(label_parts)

            # 标签背景
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(vis, (x1, y1 - text_h - 8), (x1 + text_w + 6, y1), color, -1)
            cv2.putText(vis, label, (x1 + 3, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)

        # 绘制风险信息叠加 (顶部状态栏)
        if risk_info:
            self._draw_risk_overlay(vis, risk_info)

        return vis

    def _draw_risk_overlay(self, vis: np.ndarray, risk_info: Dict):
        """在画面顶部绘制风险状态栏"""
        h, w = vis.shape[:2]
        status = risk_info.get('status', 'SAFE')
        ttc = risk_info.get('ttc', None)
        signal = risk_info.get('signal', 'NONE')

        # 状态颜色
        if signal == 'BRAKE':
            bar_color = (0, 0, 255)  # 红色
            status_text = "🔴 BRAKE!"
        elif signal == 'WARNING':
            bar_color = (0, 200, 255)  # 黄色
            status_text = "🟡 WARNING"
        else:
            bar_color = (0, 180, 0)  # 绿色
            status_text = "🟢 SAFE"

        # 顶部状态栏
        bar_height = 40
        overlay = vis.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_height), bar_color, -1)
        vis = cv2.addWeighted(overlay, 0.55, vis, 0.45, 0)

        # 状态文本
        cv2.putText(vis, status_text, (15, 29),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # TTC信息
        if ttc is not None and ttc > 0:
            ttc_str = f"TTC: {ttc:.2f}s"
            cv2.putText(vis, ttc_str, (w - 200, 29),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
