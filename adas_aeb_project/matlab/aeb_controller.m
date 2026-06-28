%% aeb_controller.m
%% ADAS AEB 制动控制器 — MATLAB 函数
%% 用于 Simulink 模型或 MATLAB Engine API 调用

function [speed, deceleration, distance] = aeb_simulate(brake_signal, initial_speed, dt)
    % AEB_SIMULATE 车辆制动动力学仿真
    %
    % 输入:
    %   brake_signal  - 制动信号向量 [nx1], 0=不制动, 1=制动
    %   initial_speed - 初始速度 (m/s)
    %   dt            - 时间步长 (s)
    %
    % 输出:
    %   speed        - 速度曲线 (m/s)
    %   deceleration - 减速度曲线 (m/s^2)
    %   distance     - 行驶距离 (m)

    %% 车辆参数
    m = 1500;           % 整车质量 (kg)
    a_max = 8.0;        % 最大制动减速度 (m/s^2)
    tau = 0.3;          % 制动系统响应延迟 (s)
    Cd = 0.3;           % 空气阻力系数
    Cr = 0.015;         % 滚动阻力系数
    g = 9.81;           % 重力加速度 (m/s^2)
    rho = 1.225;        % 空气密度 (kg/m^3)
    A = 2.2;            % 迎风面积 (m^2)

    %% 仿真
    n_steps = length(brake_signal);
    speed = zeros(n_steps, 1);
    deceleration = zeros(n_steps, 1);
    distance = zeros(n_steps, 1);

    speed(1) = initial_speed;
    brake_pressure = 0;

    for i = 2:n_steps
        % 制动系统一阶延迟
        target_brake = brake_signal(i);
        brake_pressure = brake_pressure + (target_brake - brake_pressure) * dt / tau;

        % 制动力
        F_brake = brake_pressure * m * a_max;

        % 空气阻力: F = 0.5*rho*Cd*A*v^2
        F_drag = 0.5 * rho * Cd * A * speed(i-1)^2;

        % 滚动阻力
        F_roll = Cr * m * g;

        % 总阻力
        F_total = F_brake + F_drag + F_roll;

        % 加速度 (负值=减速)
        acc = -F_total / m;
        acc = max(acc, -a_max * 1.2);  % 限幅

        % 欧拉积分
        speed(i) = max(0, speed(i-1) + acc * dt);
        deceleration(i) = abs(acc);

        % 距离积分 (梯形)
        distance(i) = distance(i-1) + 0.5 * (speed(i-1) + speed(i)) * dt;
    end

    fprintf('[MATLAB] 仿真完成: 初速=%.1f m/s, 刹停时间=%.2f s, 刹停距离=%.1f m\n', ...
        initial_speed, ...
        find(speed <= 0.1, 1, 'first') * dt, ...
        distance(end));
end


%% ====== 额外: TTC风险评估函数 ======

function [warning_signal, brake_signal, ttc] = aeb_decision(distance, relative_speed)
    % AEB_DECISION 碰撞风险决策
    %
    % 输入:
    %   distance       - 到前车距离 (m)
    %   relative_speed - 相对速度 (m/s), 正值接近
    %
    % 输出:
    %   warning_signal - 预警信号 (bool)
    %   brake_signal   - 制动信号 (bool)
    %   ttc            - 碰撞时间 (s)

    TTC_WARNING = 2.0;   % 预警阈值
    TTC_BRAKE = 1.0;     % 制动阈值

    warning_signal = false;
    brake_signal = false;
    ttc = inf;

    if relative_speed > 0 && distance > 0
        ttc = distance / relative_speed;

        if ttc < TTC_BRAKE
            brake_signal = true;
            warning_signal = true;
        elseif ttc < TTC_WARNING
            warning_signal = true;
        end
    end
end


%% ====== 测试脚本 ======
% 在 MATLAB 中运行以下代码测试:

if false  % 改为 true 运行测试
    % 测试场景: 60km/h 急刹车
    dt = 0.05;
    total_time = 10;
    brake_start = 2.0;  % 第2秒制动
    n_steps = total_time / dt;

    brake_signal = zeros(n_steps, 1);
    brake_signal(round(brake_start/dt):end) = 1;

    [speed, decel, dist] = aeb_simulate(brake_signal, 60/3.6, dt);

    % 绘图
    time = (0:n_steps-1)' * dt;
    figure;

    subplot(3,1,1);
    plot(time, speed*3.6, 'b-', 'LineWidth', 1.5);
    ylabel('速度 (km/h)'); grid on;
    title('AEB 紧急制动仿真');

    subplot(3,1,2);
    plot(time, decel, 'r-', 'LineWidth', 1.5);
    ylabel('减速度 (m/s^2)'); grid on;

    subplot(3,1,3);
    plot(time, dist, 'k-', 'LineWidth', 1.5);
    xlabel('时间 (s)'); ylabel('距离 (m)'); grid on;
end
