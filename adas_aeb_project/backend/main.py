"""
ADAS AEB 系统 — FastAPI Web 后端
"""
import cv2
import numpy as np
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from collections import deque

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from .detector import YOLODetector
from .distance import DistanceEstimator
from .risk import RiskAssessor
from .vehicle_model import VehicleDynamics

# ============================================================
# 全局系统状态
# ============================================================
app = FastAPI(title="ADAS AEB System", version="1.0.0")

# 初始化各模块
detector = YOLODetector()
estimator = DistanceEstimator()
assessor = RiskAssessor()
vehicle_model = VehicleDynamics()

# 运行时数据存储
session_data = {
    'running': False,
    'video_path': None,
    'results': deque(maxlen=5000),  # 每帧的结果
    'curves': {  # 累积的曲线数据
        'time': [],
        'distance': [],
        'ttc': [],
        'speed': [],
        'signal': [],
    },
}

# 车辆仿真状态
vehicle_state = {
    'speed': 60.0,      # 当前速度 (km/h), 默认60
    'braking': False,
}

# ============================================================
# 静态文件服务 (前端)
# ============================================================
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def index():
    """主页面"""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse({"status": "ok", "message": "ADAS AEB System API"})


# ============================================================
# API 路由
# ============================================================

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return {
        'running': session_data['running'],
        'video_loaded': session_data['video_path'] is not None,
        'vehicle_speed': vehicle_state['speed'],
        'braking': vehicle_state['braking'],
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传视频文件"""
    if not file.filename:
        return JSONResponse({'error': '文件名为空'}, status_code=400)

    # 保存上传的视频
    ext = Path(file.filename).suffix or '.mp4'
    save_path = Path(__file__).parent.parent / "data" / f"uploaded{ext}"

    with open(save_path, 'wb') as f:
        content = await file.read()
        f.write(content)

    session_data['video_path'] = str(save_path)
    session_data['results'].clear()
    for key in session_data['curves']:
        session_data['curves'][key].clear()
    assessor.reset()
    estimator.reset()

    return {
        'status': 'ok',
        'filename': file.filename,
        'size_mb': round(len(content) / 1024 / 1024, 2),
    }


@app.get("/api/curves")
async def get_curves():
    """获取累积的曲线数据"""
    return dict(session_data['curves'])


@app.post("/api/reset")
async def reset_session():
    """重置会话"""
    session_data['running'] = False
    session_data['results'].clear()
    for key in session_data['curves']:
        session_data['curves'][key].clear()
    assessor.reset()
    estimator.reset()
    vehicle_state['braking'] = False
    return {'status': 'ok'}


@app.post("/api/vehicle/speed")
async def set_vehicle_speed(data: dict):
    """设置初始车速"""
    speed = data.get('speed', 60)
    vehicle_state['speed'] = float(speed)
    return {'speed': vehicle_state['speed']}


@app.post("/api/simulate/brake")
async def run_brake_simulation(data: dict):
    """运行单次制动仿真 (支持自定义车辆参数)"""
    initial_speed_kmh = float(data.get('initial_speed', 60))
    brake_at_frame = int(data.get('brake_at_frame', 40))
    total_frames = int(data.get('total_frames', 200))
    dt = float(data.get('dt', 0.05))

    # 自定义车辆参数
    mass = float(data.get('mass', 1500))
    friction = float(data.get('friction', 0.8))

    # 创建带自定义参数的模型
    model = VehicleDynamics(mass=mass, road_friction=friction)
    result = model.emergency_brake_scenario(
        initial_speed_kmh=initial_speed_kmh,
        brake_trigger_frame=brake_at_frame,
        total_frames=total_frames,
        dt=dt,
    )

    return {
        'time': result['time'].tolist(),
        'speed': result['speed'].tolist(),
        'speed_kmh': result['speed_kmh'].tolist(),
        'deceleration': result['deceleration'].tolist(),
        'distance': result['distance'].tolist(),
        'stopping_time': result['stopping_time'],
        'stopping_distance': result['stopping_distance'],
        'max_deceleration': round(float(result['deceleration'].max()), 2),
    }


@app.post("/api/simulate/speeds")
async def run_speed_comparison(data: dict):
    """多初速对比: 同一制动时机, 不同初速"""
    brake_t = float(data.get('brake_trigger_time', 2.0))
    dt = float(data.get('dt', 0.05))
    speeds = data.get('speeds', [30, 50, 60, 80, 100, 120])
    mass = float(data.get('mass', 1500))
    friction = float(data.get('friction', 0.8))

    brake_frame = int(brake_t / dt)
    total_frames = int((brake_t + 8) / dt)

    results = []
    for v0 in speeds:
        model = VehicleDynamics(mass=mass, road_friction=friction)
        r = model.emergency_brake_scenario(v0, brake_frame, total_frames, dt)
        results.append({
            'initial_speed': v0,
            'time': r['time'].tolist(),
            'speed_kmh': r['speed_kmh'].tolist(),
            'deceleration': r['deceleration'].tolist(),
            'stopping_time': r['stopping_time'],
            'stopping_distance': r['stopping_distance'],
        })
    return {'results': results, 'brake_trigger_time': brake_t}


@app.post("/api/simulate/distance-analysis")
async def run_distance_analysis(data: dict):
    """刹车距离 vs 初速 全面分析"""
    dt = float(data.get('dt', 0.05))
    speeds = list(range(20, 140, 10))
    mass = float(data.get('mass', 1500))
    friction = float(data.get('friction', 0.8))

    brake_frame = int(2.0 / dt)
    total_frames = int(12 / dt)

    results = []
    for v0 in speeds:
        model = VehicleDynamics(mass=mass, road_friction=friction)
        r = model.emergency_brake_scenario(v0, brake_frame, total_frames, dt)
        results.append({
            'initial_speed': v0,
            'stopping_time': r['stopping_time'],
            'stopping_distance': r['stopping_distance'],
        })
    return {'results': results}


@app.post("/api/simulate/ttc-analysis")
async def run_ttc_analysis(data: dict):
    """TTC阈值分析: 不同速度/距离组合下的TTC和制动效果"""
    dt = float(data.get('dt', 0.05))
    initial_speed = float(data.get('initial_speed', 60))
    mass = float(data.get('mass', 1500))
    friction = float(data.get('friction', 0.8))

    # 不同初始距离对应的TTC
    distances = [10, 15, 20, 30, 50, 80]
    v0_mps = initial_speed / 3.6

    results = []
    for dist in distances:
        ttc_initial = dist / v0_mps if v0_mps > 0 else float('inf')
        brake_frame = max(1, int((max(0, ttc_initial - 1.0)) / dt))
        total_frames = int(ttc_initial / dt + 5 / dt)

        model = VehicleDynamics(mass=mass, road_friction=friction)
        r = model.emergency_brake_scenario(initial_speed, brake_frame, min(total_frames, 400), dt)
        results.append({
            'initial_distance': dist,
            'ttc_initial': round(ttc_initial, 2),
            'time': r['time'].tolist(),
            'speed_kmh': r['speed_kmh'].tolist(),
            'stopping_time': r['stopping_time'],
            'stopping_distance': r['stopping_distance'],
            'avoided_collision': r['stopping_distance'] < dist,
        })
    return {'results': results, 'initial_speed': initial_speed}


@app.get("/api/simulate/scenarios")
async def run_multi_scenario_simulation(
    mass: float = 1500,
    friction: float = 0.8,
    speed: float = 60,
    brake_t: float = 2.0,
):
    """
    环境场景仿真: 不同天气/路况下的制动对比

    场景 (同一速度, 不同路面/载重):
        1. 干燥沥青 μ=0.8 (基准)
        2. 雨天路面 μ=0.5
        3. 积雪路面 μ=0.25
        4. 重载+干燥 m=2500kg μ=0.8
        5. 空载+雨天 m=1000kg μ=0.5
    """
    dt = 0.05
    brake_frame = int(brake_t / dt)
    total_frames = int((brake_t + 10) / dt)

    # 环境定义: (名称, mass, friction, color)
    environments = [
        ('干燥沥青 μ=0.80', mass, 0.80, '#22c55e'),
        ('雨天路面 μ=0.50', mass, 0.50, '#3b82f6'),
        ('积雪路面 μ=0.25', mass, 0.25, '#eab308'),
        ('重载+干燥 2500kg', 2500, 0.80, '#ef4444'),
        ('空载+雨天 1000kg', 1000, 0.50, '#8b5cf6'),
    ]

    scenarios = []
    for name, m, mu, color in environments:
        model = VehicleDynamics(mass=m, road_friction=mu)
        r = model.emergency_brake_scenario(speed, brake_frame, total_frames, dt)
        scenarios.append({
            'name': name,
            'initial_speed': speed,
            'mass': m,
            'friction': mu,
            'brake_trigger': f't={brake_t}s',
            'time': r['time'].tolist(),
            'speed_kmh': r['speed_kmh'].tolist(),
            'deceleration': r['deceleration'].tolist(),
            'stopping_time': r['stopping_time'],
            'stopping_distance': r['stopping_distance'],
            'color': color,
        })

    # 多速度对比 (用当前参数)
    speed_compare = []
    for v0 in [30, 50, 70, 90, 110]:
        model = VehicleDynamics(mass=mass, road_friction=friction)
        r = model.emergency_brake_scenario(v0, brake_frame, total_frames, dt)
        speed_compare.append({
            'initial_speed': v0,
            'time': r['time'].tolist(),
            'speed_kmh': r['speed_kmh'].tolist(),
            'deceleration': r['deceleration'].tolist(),
            'stopping_time': r['stopping_time'],
            'stopping_distance': r['stopping_distance'],
        })

    return {
        'scenarios': scenarios,
        'speed_compare': speed_compare,
    }


# ============================================================
# WebSocket — 实时视频处理
# ============================================================

@app.websocket("/ws/detect")
async def websocket_detect(websocket: WebSocket):
    """
    WebSocket 端点: 逐帧发送检测结果给前端

    支持命令:
        - 自动从 frame_idx=1 开始播放
        - 接收前端 {"cmd":"seek", "frame": <N>} 跳转到任意帧
        - 接收前端 {"cmd":"pause"} 暂停 / {"cmd":"resume"} 继续
        - 接收前端 {"cmd":"stop"} 停止

    流程:
        1. 前端连接后自动开始
        2. 逐帧读取视频 → YOLO检测 → 距离估计 → TTC评估
        3. 每帧结果通过 WebSocket 推送给前端
        4. 前端实时更新画面和曲线
        5. 前端可随时发送 seek/pause/resume/stop 命令
    """
    await websocket.accept()
    print("[WS] 客户端已连接")

    video_path = session_data.get('video_path')
    if not video_path:
        await websocket.send_json({'error': '请先上传视频文件'})
        await websocket.close()
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        await websocket.send_json({'error': '无法打开视频文件'})
        await websocket.close()
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dt = 1.0 / fps

    print(f"[WS] 视频: {video_path}")
    print(f"[WS] FPS={fps:.1f}, 总帧数={frame_count}, dt={dt:.3f}s")

    # 先发送视频元信息
    await websocket.send_json({
        'type': 'metadata',
        'fps': fps,
        'frame_count': frame_count,
        'duration': round(frame_count / fps, 1),
    })

    session_data['running'] = True
    frame_idx = 0
    prev_distances = {}
    prev_brake = False
    vehicle_speed_kmh = vehicle_state['speed']
    paused = False

    # 用于接收前端命令的异步队列
    cmd_queue = asyncio.Queue()

    async def recv_commands():
        """后台监听前端发来的命令"""
        nonlocal paused
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except:
                    continue
                await cmd_queue.put(msg)
        except (WebSocketDisconnect, Exception):
            await cmd_queue.put({'cmd': 'stop'})

    recv_task = asyncio.create_task(recv_commands())

    try:
        while session_data['running']:
            # --- 处理前端命令 ---
            try:
                while not cmd_queue.empty():
                    cmd_msg = cmd_queue.get_nowait()
                    cmd = cmd_msg.get('cmd', '')
                    if cmd == 'seek':
                        target_frame = int(cmd_msg.get('frame', 0))
                        target_frame = max(1, min(target_frame, frame_count))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame - 1)
                        frame_idx = target_frame - 1
                        # 清除跳转前的历史数据
                        estimator.reset()
                        assessor.reset()
                        prev_distances = {}
                        session_data['curves']['time'].clear()
                        session_data['curves']['distance'].clear()
                        session_data['curves']['ttc'].clear()
                        session_data['curves']['speed'].clear()
                        session_data['curves']['signal'].clear()
                        print(f"[WS] Seek → 帧 {target_frame}")
                    elif cmd == 'pause':
                        paused = True
                        print("[WS] 暂停")
                    elif cmd == 'resume':
                        paused = False
                        print("[WS] 继续")
                    elif cmd == 'stop':
                        session_data['running'] = False
                        print("[WS] 停止")
            except Exception:
                pass

            # --- 暂停状态: 等待 ---
            if paused:
                await asyncio.sleep(0.1)
                continue

            # --- 读取下一帧 ---
            ret, frame = cap.read()
            if not ret:
                # 到达视频末尾
                await websocket.send_json({'type': 'finished', 'message': '视频播放完毕'})
                break

            frame_idx += 1

            # === Step 1: YOLO目标检测 ===
            detections = detector.detect_frame(frame)

            # === Step 2: 距离估计 (针对 car 目标) ===
            distances = estimator.estimate_for_cars(detections, frame.shape[0])

            # === Step 3: TTC 风险评估 ===
            min_distance = None
            min_distance_idx = None
            for idx, dist in distances.items():
                if dist is not None and (min_distance is None or dist < min_distance):
                    min_distance = dist
                    min_distance_idx = idx

            relative_speed = 0.0
            if min_distance_idx is not None and min_distance_idx in prev_distances:
                prev_d = prev_distances[min_distance_idx]
                if min_distance is not None:
                    delta_d = prev_d - min_distance
                    relative_speed = max(0, delta_d / dt) if dt > 0 else 0.0

            if min_distance is not None and relative_speed > 0:
                risk_info = assessor.assess(min_distance, relative_speed)
            elif min_distance is not None:
                risk_info = {
                    'ttc': None, 'state': 'SAFE', 'signal': 'NONE',
                    'warning': False, 'brake': False,
                    'message': '安全 — 距离稳定', 'color': '#22c55e',
                }
            else:
                risk_info = {
                    'ttc': None, 'state': 'SAFE', 'signal': 'NONE',
                    'warning': False, 'brake': False,
                    'message': '前方无车辆', 'color': '#22c55e',
                }

            # === Step 4: 车辆速度动力学更新 ===
            # 根据 AEB 状态选择不同的减速度等级
            if risk_info['brake']:
                # 紧急制动: 全力刹车 ~7.5 m/s²
                decel_rate = 7.5
                vehicle_state['braking'] = True
            elif risk_info['warning']:
                # 碰撞预警: 轻度制动 ~3.0 m/s²
                decel_rate = 3.0
                vehicle_state['braking'] = False
            else:
                # 安全: 不制动，保持速度
                decel_rate = 0.0
                vehicle_state['braking'] = False

            # 速度更新 (欧拉积分)
            vehicle_speed_mps = vehicle_speed_kmh / 3.6
            vehicle_speed_mps = max(0, vehicle_speed_mps - decel_rate * dt)
            vehicle_speed_kmh = vehicle_speed_mps * 3.6
            vehicle_state['speed'] = round(vehicle_speed_kmh, 1)

            # === Step 5: 绘制检测结果 ===
            vis_frame = detector.draw_detections(frame, detections, distances, risk_info)

            _, buffer = cv2.imencode('.jpg', vis_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_b64 = buffer.tobytes()

            # === Step 6: 记录曲线数据 ===
            t = frame_idx * dt
            session_data['curves']['time'].append(round(t, 2))
            session_data['curves']['distance'].append(min_distance if min_distance else 0)
            session_data['curves']['ttc'].append(risk_info['ttc'] if risk_info['ttc'] else 0)
            session_data['curves']['speed'].append(vehicle_speed_kmh)
            session_data['curves']['signal'].append(
                2 if risk_info['brake'] else (1 if risk_info['warning'] else 0))

            # === Step 7: 发送响应 ===
            dets_serializable = []
            for i, det in enumerate(detections):
                d = {
                    'class': det['class'],
                    'confidence': det['confidence'],
                    'bbox': det['bbox'],
                    'width': det['width'],
                    'height': det['height'],
                }
                if i in distances:
                    d['distance'] = distances[i]
                dets_serializable.append(d)

            response = {
                'type': 'frame',
                'frame_idx': frame_idx,
                'total_frames': frame_count,
                'fps': fps,
                'time': round(t, 2),
                'detections': dets_serializable,
                'risk': {
                    'ttc': risk_info['ttc'],
                    'state': risk_info['state'],
                    'signal': risk_info['signal'],
                    'message': risk_info['message'],
                    'color': risk_info['color'],
                },
                'vehicle_speed': round(vehicle_speed_kmh, 1),
                'braking': vehicle_state['braking'],
                'frame_jpeg': frame_b64.hex(),
            }

            await websocket.send_json(response)
            prev_distances = distances.copy()
            prev_brake = risk_info.get('brake', False)
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        print("[WS] 客户端断开")
    except Exception as e:
        print(f"[WS] 错误: {e}")
        try:
            await websocket.send_json({'error': str(e)})
        except:
            pass
    finally:
        recv_task.cancel()
        try: await recv_task
        except: pass
        cap.release()
        session_data['running'] = False
        print(f"[WS] 处理完成, 共 {frame_idx} 帧")


# ============================================================
# 启动入口
# ============================================================

def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """启动 FastAPI 服务"""
    print("=" * 55)
    print("   ADAS AEB 自动紧急制动系统")
    print("=" * 55)
    print(f"   Web 界面: http://localhost:{port}")
    print(f"   API 文档: http://localhost:{port}/docs")
    print("=" * 55)
    # 直接传 app 对象, 避免 uvicorn 字符串导入路径问题
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
