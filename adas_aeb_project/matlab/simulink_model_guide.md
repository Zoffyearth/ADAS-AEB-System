# Simulink 车辆动力学模型 — 构建指南

## 模型概述

本 Simulink 模型实现简化车辆纵向动力学，用于 AEB 制动仿真。

## 快速构建 (推荐)

```matlab
% 在 MATLAB 命令行直接运行:
build_simulink_model
```

该脚本会自动创建完整的 Simulink 模型 `aeb_vehicle_model.slx`，包括所有模块和连线。

## 手动构建步骤 (备选)

### 1. 新建 Simulink 模型
```
MATLAB 命令行 → 输入: simulink → Blank Model → 保存为 aeb_vehicle_model.slx
```

### 2. 添加以下 Blocks

| Block 名称 | Library 路径 | 用途 |
|-----------|-------------|------|
| Constant | Sources | 制动信号输入 (0/1) |
| Step | Sources | 模拟突然制动触发 |
| Switch | Signal Routing | 选择制动/不制动 |
| Transfer Fcn | Continuous | 制动系统一阶延迟 1/(tau*s+1) |
| Gain | Math Operations | 制动力增益 (m*a_max) |
| Add | Math Operations | 合力求和 (制动力+阻力) |
| Gain1 | Math Operations | 1/m (合力→加速度) |
| Integrator | Continuous | 加速度→速度 |
| Integrator1 | Continuous | 速度→位移 |
| Scope | Sinks | 显示速度/距离曲线 |
| To Workspace | Sinks | 导出数据到 MATLAB |

### 3. 连接方式

```
Step(制动触发) ──→ Switch ──→ Transfer Fcn ──→ Gain ──→ Add(负号) ──→ Gain(1/m) ──→ Integrator ──→ 速度
初始速度 ──→ Integrator(初值)                                          ↑阻力              ↓
                                                                       │             Integrator1 ──→ 位移
空气阻力 ←── Cd*0.5*rho*A*v^2 ←── Math Function                       │
滚动阻力 ←── Cr*m*g ←── Constant                                       │
                                                                       └── Add(正号) ←──┘
```

### 4. 参数设置

| Block | 参数 | 值 |
|-------|------|-----|
| Step | Step time | 2.0 (第2秒触发) |
| Switch | Threshold | 0.5 |
| Transfer Fcn | Denominator | [0.3 1] (tau=0.3s) |
| Gain (制动) | Gain | 1500*8 = 12000 |
| Gain (1/m) | Gain | 1/1500 |
| Integrator (速度) | Initial condition | 60/3.6 ≈ 16.67 (60km/h) |
| Integrator1 (位移) | Initial condition | 0 |

### 5. MATLAB Function Block (替代方案)
如果不想手动连线，可以用 MATLAB Function Block 代替:

```matlab
function [speed, distance, decel] = vehicle_dynamics(brake, initial_speed, dt)
    persistent v_prev d_prev
    if isempty(v_prev)
        v_prev = initial_speed;
        d_prev = 0;
    end

    m = 1500; a_max = 8.0; tau = 0.3;
    % 简化为欧拉积分
    decel = brake * a_max;
    v = max(0, v_prev - decel * dt);
    d = d_prev + 0.5*(v_prev + v)*dt;

    speed = v; distance = d;

    v_prev = v; d_prev = d;
end
```

### 6. 运行仿真
```
Simulation → Run (或 Ctrl+T)
双击 Scope 查看速度/距离曲线
```

## Python 调用 Simulink (通过 MATLAB Engine)

确保已安装 MATLAB Engine API for Python，然后在 Python 中:

```python
import matlab.engine
eng = matlab.engine.start_matlab()

# 加载 Simulink 模型
eng.load_system('aeb_vehicle_model')

# 设置参数
eng.set_param('aeb_vehicle_model/Step', 'Time', '2.0')

# 运行仿真
eng.sim('aeb_vehicle_model')

# 获取结果
speed = eng.workspace['speed']
distance = eng.workspace['distance']

eng.quit()
```
