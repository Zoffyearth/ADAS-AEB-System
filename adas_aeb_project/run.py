#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ADAS AEB 自动紧急制动系统 — 一键启动脚本

用法:
    python run.py              # 启动 Web 服务
    python run.py --port 8080  # 指定端口
    python run.py --cli        # 命令行模式 (无Web界面，处理视频并生成结果)
    python run.py --generate   # 生成仿真曲线图片 (无需视频)

环境要求:
    Conda 环境: adas_aeb_env
    激活方式: conda activate adas_aeb_env
    或在项目目录直接运行:
    d:/文档/vscode/ros2/adas_aeb_env/python.exe run.py [选项]
"""
import sys
import argparse
import os
from pathlib import Path

# 修复 Windows GBK 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# 确保项目目录在 Python 路径中
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))


def main_web(port: int):
    """启动 Web 服务"""
    from backend.main import start_server
    start_server(port=port)


def main_cli(video_path: str, output_dir: str):
    """
    命令行模式: 处理视频，生成所有结果输出

    用于在没有 Web 界面时批量处理视频，
    输出检测视频、曲线图等供报告使用。
    """
    import cv2
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    from backend.detector import YOLODetector
    from backend.distance import DistanceEstimator
    from backend.risk import RiskAssessor

    print("=" * 55)
    print("   ADAS AEB 系统 — CLI 模式")
    print("=" * 55)

    # 初始化
    detector = YOLODetector()
    estimator = DistanceEstimator()
    assessor = RiskAssessor()

    # 打开视频
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 无法打开视频: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dt = 1.0 / fps
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"视频: {video_path}")
    print(f"分辨率: {width}x{height}, FPS: {fps:.1f}, 总帧: {frame_count}")

    # 输出目录
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 输出视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video = cv2.VideoWriter(
        str(out_path / 'detection_result.mp4'),
        fourcc, fps, (width, height)
    )

    # 数据记录
    t_list, dist_list, ttc_list, signal_list = [], [], [], []
    prev_distances = {}
    vehicle_speed_kmh = 60.0

    print("处理中...")
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        t = frame_idx * dt

        # 检测
        detections = detector.detect_frame(frame)
        distances = estimator.estimate_for_cars(detections, height)

        # 最近车辆
        min_dist = None
        min_idx = None
        for idx, d in distances.items():
            if d is not None and (min_dist is None or d < min_dist):
                min_dist = d
                min_idx = idx

        # 相对速度
        v_rel = 0.0
        if min_idx is not None and min_idx in prev_distances:
            prev_d = prev_distances[min_idx]
            if min_dist is not None:
                v_rel = max(0, (prev_d - min_dist) / dt)

        # TTC
        risk_info = assessor.assess(
            min_dist if min_dist else 999,
            v_rel
        )

        # 车速更新
        if risk_info['brake']:
            vehicle_speed_kmh = max(0, vehicle_speed_kmh - 7.0 * 3.6 * dt)

        # 画框
        vis = detector.draw_detections(frame, detections, distances, risk_info)
        out_video.write(vis)

        # 记录
        t_list.append(t)
        dist_list.append(min_dist if min_dist else 0)
        ttc_list.append(risk_info['ttc'] if risk_info['ttc'] else 0)
        signal_list.append(2 if risk_info['brake'] else (1 if risk_info['warning'] else 0))

        prev_distances = distances.copy()

        if frame_idx % 30 == 0:
            print(f"  进度: {frame_idx}/{frame_count} ({100*frame_idx/frame_count:.0f}%)")

    cap.release()
    out_video.release()
    print(f"✅ 处理完成: {frame_idx} 帧")

    # ======== 生成图表 ========
    print("生成分析图表...")
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']

    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)

    # 距离
    axes[0].plot(t_list, dist_list, 'b-', linewidth=1.5)
    axes[0].set_ylabel('距离 (m)')
    axes[0].set_title('前车距离 — 时间')
    axes[0].grid(True, alpha=0.3)

    # TTC
    axes[1].plot(t_list, ttc_list, 'orange', linewidth=1.5)
    axes[1].axhline(y=2.0, color='yellow', linestyle='--', label='WARNING 阈值 (2s)')
    axes[1].axhline(y=1.0, color='red', linestyle='--', label='BRAKE 阈值 (1s)')
    axes[1].set_ylabel('TTC (s)')
    axes[1].set_title('TTC — 时间')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # 制动信号
    axes[2].fill_between(t_list, 0, signal_list, step='post', alpha=0.5,
                          color=['green', 'yellow', 'red'])
    axes[2].set_ylabel('信号等级')
    axes[2].set_yticks([0, 1, 2])
    axes[2].set_yticklabels(['SAFE', 'WARNING', 'BRAKE'])
    axes[2].set_title('AEB 制动信号')
    axes[2].grid(True, alpha=0.3)

    # 车速
    axes[3].plot(t_list, [max(0, 60 - s*7*3.6*dt) for s in signal_list], 'g-', linewidth=1.5)
    axes[3].set_xlabel('时间 (s)')
    axes[3].set_ylabel('车速 (km/h)')
    axes[3].set_title('自车速度 — 时间')
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    chart_path = out_path / 'analysis_curves.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ 图表已保存: {chart_path}")

    # 输出统计
    print("\n" + "=" * 55)
    print("  分析结果汇总")
    print("=" * 55)
    brake_frames = sum(1 for s in signal_list if s == 2)
    warn_frames = sum(1 for s in signal_list if s == 1)
    print(f"  总帧数: {frame_idx}")
    print(f"  警告帧: {warn_frames} ({100*warn_frames/frame_idx:.1f}%)")
    print(f"  制动帧: {brake_frames} ({100*brake_frames/frame_idx:.1f}%)")
    print(f"  输出视频: {out_path / 'detection_result.mp4'}")
    print(f"  分析图表: {chart_path}")


def main_generate(output_dir: str):
    """
    生成模式: 仅生成仿真曲线 (无需视频)
    用于快速生成报告所需的制动仿真曲线
    """
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from backend.vehicle_model import VehicleDynamics

    print("=" * 55)
    print("   ADAS AEB 系统 — 仿真曲线生成")
    print("=" * 55)

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    model = VehicleDynamics()

    # 场景1: 60km/h 急刹车
    result = model.emergency_brake_scenario(60, brake_trigger_frame=40, total_frames=200)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    # 速度
    axes[0, 0].plot(result['time'], result['speed_kmh'], 'b-', linewidth=2)
    axes[0, 0].set_xlabel('时间 (s)')
    axes[0, 0].set_ylabel('速度 (km/h)')
    axes[0, 0].set_title('车速变化曲线 (60km/h → 0)')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].annotate(f"刹停: {result['stopping_time']}s",
                         xy=(result['stopping_time'], 0),
                         xytext=(result['stopping_time']+0.5, 10),
                         arrowprops=dict(arrowstyle='->'))

    # 减速度
    axes[0, 1].plot(result['time'], result['deceleration'], 'r-', linewidth=2)
    axes[0, 1].set_xlabel('时间 (s)')
    axes[0, 1].set_ylabel('减速度 (m/s²)')
    axes[0, 1].set_title('制动减速度曲线')
    axes[0, 1].grid(True, alpha=0.3)

    # 距离
    axes[1, 0].plot(result['time'], result['distance'], 'g-', linewidth=2)
    axes[1, 0].set_xlabel('时间 (s)')
    axes[1, 0].set_ylabel('行驶距离 (m)')
    axes[1, 0].set_title(f'刹车距离: {result["stopping_distance"]}m')
    axes[1, 0].grid(True, alpha=0.3)

    # 不同初速对比
    for v0 in [30, 50, 70, 90, 110]:
        r = model.emergency_brake_scenario(v0, brake_trigger_frame=40, total_frames=200)
        axes[1, 1].plot(r['time'], r['speed_kmh'], linewidth=1.5, label=f'{v0} km/h')
    axes[1, 1].set_xlabel('时间 (s)')
    axes[1, 1].set_ylabel('速度 (km/h)')
    axes[1, 1].set_title('不同初速制动对比')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.suptitle('ADAS AEB 车辆制动仿真结果', fontsize=14, fontweight='bold')
    plt.tight_layout()
    chart_path = out_path / 'brake_simulation.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ 仿真曲线已保存: {chart_path}")

    # 打印刹停数据表
    print(f"\n{'初速(km/h)':<12} {'刹停时间(s)':<14} {'刹停距离(m)':<14}")
    print("-" * 42)
    for v0 in [30, 50, 60, 70, 90, 110]:
        r = model.emergency_brake_scenario(v0, brake_trigger_frame=40, total_frames=300)
        print(f"  {v0:<10} {r['stopping_time']:<14} {r['stopping_distance']:<14}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='ADAS AEB 自动紧急制动系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                      # 启动 Web 服务 (默认端口8000)
  python run.py --port 8080          # 指定端口
  python run.py --cli video.mp4      # 命令行处理视频
  python run.py --generate           # 生成仿真曲线图片
        """
    )
    parser.add_argument('--port', type=int, default=8000, help='Web服务端口')
    parser.add_argument('--cli', type=str, metavar='VIDEO_PATH',
                        help='CLI模式，处理指定视频')
    parser.add_argument('--generate', action='store_true',
                        help='生成模式，仅输出仿真曲线')
    parser.add_argument('--output', type=str, default='data/output',
                        help='输出目录')

    args = parser.parse_args()

    if args.generate:
        main_generate(args.output)
    elif args.cli:
        main_cli(args.cli, args.output)
    else:
        main_web(args.port)
