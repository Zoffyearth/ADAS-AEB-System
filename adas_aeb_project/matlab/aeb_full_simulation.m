%% aeb_full_simulation.m
%% ADAS AEB 完整场景仿真 — 包含4种驾驶场景
%% 用于课程设计答辩展示
%  直接运行此脚本即可生成所有仿真结果

clear; close all; clc;

fprintf('=============================================================\n');
fprintf('  ADAS AEB 自动紧急制动系统 — 完整场景仿真\n');
fprintf('=============================================================\n\n');

%% ====== 公共参数 ======
m = 1500;           % 整车质量 (kg)
a_max = 8.0;        % 最大制动减速度 (m/s^2)
tau = 0.3;          % 制动系统响应延迟 (s)
Cd = 0.3;           % 空气阻力系数
Cr = 0.015;         % 滚动阻力系数
g = 9.81;           % 重力加速度
rho = 1.225;        % 空气密度
A = 2.2;            % 迎风面积

dt = 0.01;          % 仿真步长
total_time = 10;    % 总仿真时间
t = (0:dt:total_time)';
n_steps = length(t);

% AEB 阈值
TTC_WARNING = 2.0;
TTC_BRAKE   = 1.0;

%% ====== 创建结果目录 ======
out_dir = fullfile(pwd, 'simulation_results');
if ~exist(out_dir, 'dir')
    mkdir(out_dir);
end

%% ============================================================
%% 场景1: 前车正常行驶 (无风险)
%% ============================================================
fprintf('[场景1] 前车正常行驶 — 安全跟车\n');

% 场景设置: 前车匀速80m外，自车60km/h，距离大 → TTC > 2s
initial_speed_1 = 60 / 3.6;  % 16.67 m/s
target_distance_1 = 80;       % 前车距离80m

% 模拟前车距离变化 (前车也在60km/h → 距离基本不变)
distance_1 = target_distance_1 * ones(n_steps, 1);
relative_speed_1 = 0.5 * ones(n_steps, 1);  % 略快于前车

% TTC 计算
ttc_1 = distance_1 ./ relative_speed_1;

% AEB 决策
[warning_1, brake_1] = aeb_decision_vector(distance_1, relative_speed_1, TTC_WARNING, TTC_BRAKE);

% 车辆动力学
[speed_1, decel_1, dist_traveled_1] = simulate_vehicle_dynamics(...
    brake_1, initial_speed_1, dt, m, a_max, tau, Cd, Cr, g, rho, A);

%% ============================================================
%% 场景2: 前车突然减速 (高风险 → 触发制动)
%% ============================================================
fprintf('[场景2] 前车突然减速 — 触发紧急制动\n');

initial_speed_2 = 80 / 3.6;  % 80km/h
% 前车距离: 开始50m，2秒后前车急刹，距离快速缩小
distance_2 = zeros(n_steps, 1);
relative_speed_2 = zeros(n_steps, 1);

for i = 1:n_steps
    t_i = t(i);
    if t_i < 2.0
        distance_2(i) = 50 - 2*t_i;           % 缓慢接近
        relative_speed_2(i) = 2;
    elseif t_i < 3.0
        distance_2(i) = max(2, distance_2(i-1) - 8*dt);  % 前车急刹，距离骤降
        relative_speed_2(i) = 15;
    else
        distance_2(i) = max(1, distance_2(i-1) - 3*dt);
        relative_speed_2(i) = 8;
    end
end

% TTC 计算
ttc_2 = distance_2 ./ max(relative_speed_2, 0.1);

% AEB 决策
[warning_2, brake_2] = aeb_decision_vector(distance_2, relative_speed_2, TTC_WARNING, TTC_BRAKE);

% 车辆动力学
[speed_2, decel_2, dist_traveled_2] = simulate_vehicle_dynamics(...
    brake_2, initial_speed_2, dt, m, a_max, tau, Cd, Cr, g, rho, A);

%% ============================================================
%% 场景3: 行人突然进入车道
%% ============================================================
fprintf('[场景3] 行人突然横穿 — 紧急避撞\n');

initial_speed_3 = 50 / 3.6;  % 50km/h (市区)

% 行人突然出现: 前方15m处，第1.5秒出现
distance_3 = zeros(n_steps, 1);
relative_speed_3 = zeros(n_steps, 1);

for i = 1:n_steps
    t_i = t(i);
    if t_i < 1.5
        distance_3(i) = 200;           % 无目标
        relative_speed_3(i) = 0;
    else
        % 行人出现: 15m → 快速接近
        remaining = max(0.5, 15 - (t_i - 1.5) * initial_speed_3);
        distance_3(i) = remaining;
        relative_speed_3(i) = initial_speed_3;  % 行人静止，自车接近
    end
end

% TTC
ttc_3 = zeros(n_steps, 1);
for i = 1:n_steps
    if relative_speed_3(i) > 0.1 && distance_3(i) < 100
        ttc_3(i) = distance_3(i) / relative_speed_3(i);
    else
        ttc_3(i) = 100;  % 无风险
    end
end

% AEB 决策
[warning_3, brake_3] = aeb_decision_vector(distance_3, relative_speed_3, TTC_WARNING, TTC_BRAKE);

% 车辆动力学
[speed_3, decel_3, dist_traveled_3] = simulate_vehicle_dynamics(...
    brake_3, initial_speed_3, dt, m, a_max, tau, Cd, Cr, g, rho, A);

%% ============================================================
%% 场景4: 红绿灯变化 (绿→红)
%% ============================================================
fprintf('[场景4] 红绿灯变化 — 绿变红停车\n');

initial_speed_4 = 60 / 3.6;  % 60km/h

% 红绿灯场景: 前方50m有停止线，第2秒变红灯
distance_4 = zeros(n_steps, 1);
relative_speed_4 = zeros(n_steps, 1);

for i = 1:n_steps
    t_i = t(i);
    if t_i < 2.0
        distance_4(i) = 50 - t_i * initial_speed_4;  % 正常接近停止线
        relative_speed_4(i) = initial_speed_4;
    else
        % 红灯: 需要停车
        remaining = max(0, 50 - 2*initial_speed_4 - (t_i-2)*initial_speed_4);
        distance_4(i) = remaining;
        relative_speed_4(i) = initial_speed_4;
    end
end

% TTC
ttc_4 = distance_4 ./ max(relative_speed_4, 0.1);

% AEB 决策 (红绿灯场景: 检测到红灯 → 主动制动)
[warning_4, brake_4] = aeb_decision_vector(distance_4, relative_speed_4, TTC_WARNING, TTC_BRAKE);

% 强制在第2秒开始制动 (模拟红灯检测)
brake_4(t < 2.0) = 0;
brake_4(t >= 2.0) = 1;

[speed_4, decel_4, dist_traveled_4] = simulate_vehicle_dynamics(...
    brake_4, initial_speed_4, dt, m, a_max, tau, Cd, Cr, g, rho, A);

fprintf('\n✅ 四种场景仿真完成!\n');

%% ============================================================
%% 绘制综合对比图 (用于答辩展示)
%% ============================================================
fprintf('生成答辩展示图表...\n');

figure('Position', [100, 100, 1400, 900], 'Color', 'white');

% ---- 场景1: 正常行驶 ----
subplot(4, 4, 1);
yyaxis left;
plot(t, speed_1*3.6, 'b-', 'LineWidth', 1.8); hold on;
ylabel('车速 (km/h)', 'Color', 'b');
yyaxis right;
stairs(t, brake_1, 'r-', 'LineWidth', 1.2);
ylabel('制动', 'Color', 'r'); ylim([-0.1, 1.2]);
title('场景1: 前车正常行驶 — 速度'); grid on; xlabel('时间 (s)');

subplot(4, 4, 2);
semilogy(t, ttc_1, 'g-', 'LineWidth', 1.8); hold on;
yline(TTC_WARNING, 'y--', 'WARN 2s', 'LineWidth', 1.2);
yline(TTC_BRAKE, 'r--', 'BRAKE 1s', 'LineWidth', 1.2);
ylabel('TTC (s)'); title('TTC变化'); grid on; xlabel('时间 (s)');

subplot(4, 4, 3);
plot(t, distance_1, 'b-', 'LineWidth', 1.8);
ylabel('距离 (m)'); title('前车距离'); grid on; xlabel('时间 (s)');

subplot(4, 4, 4);
plot(t, decel_1, 'r-', 'LineWidth', 1.8);
ylabel('减速度 (m/s^2)'); title('制动减速度'); grid on; xlabel('时间 (s)');

% ---- 场景2: 前车急刹 ----
subplot(4, 4, 5);
yyaxis left;
plot(t, speed_2*3.6, 'b-', 'LineWidth', 1.8); hold on;
ylabel('车速 (km/h)', 'Color', 'b');
yyaxis right;
stairs(t, brake_2, 'r-', 'LineWidth', 1.2);
ylabel('制动', 'Color', 'r'); ylim([-0.1, 1.2]);
title('场景2: 前车突然减速 — 速度'); grid on; xlabel('时间 (s)');

subplot(4, 4, 6);
semilogy(t, ttc_2, 'g-', 'LineWidth', 1.8); hold on;
yline(TTC_WARNING, 'y--', 'WARN', 'LineWidth', 1.2);
yline(TTC_BRAKE, 'r--', 'BRAKE', 'LineWidth', 1.2);
ylabel('TTC (s)'); title('TTC骤降 → 触发制动'); grid on; xlabel('时间 (s)');

subplot(4, 4, 7);
plot(t, distance_2, 'b-', 'LineWidth', 1.8);
ylabel('距离 (m)'); title('距离快速缩小'); grid on; xlabel('时间 (s)');

subplot(4, 4, 8);
plot(t, decel_2, 'r-', 'LineWidth', 1.8);
ylabel('减速度 (m/s^2)'); title('急刹减速度'); grid on; xlabel('时间 (s)');

% ---- 场景3: 行人横穿 ----
subplot(4, 4, 9);
yyaxis left;
plot(t, speed_3*3.6, 'b-', 'LineWidth', 1.8); hold on;
ylabel('车速 (km/h)', 'Color', 'b');
yyaxis right;
stairs(t, brake_3, 'r-', 'LineWidth', 1.2);
ylabel('制动', 'Color', 'r'); ylim([-0.1, 1.2]);
title('场景3: 行人突然进入 — 速度'); grid on; xlabel('时间 (s)');

subplot(4, 4, 10);
plot(t, ttc_3, 'g-', 'LineWidth', 1.8); hold on;
yline(TTC_WARNING, 'y--', 'WARN', 'LineWidth', 1.2);
yline(TTC_BRAKE, 'r--', 'BRAKE', 'LineWidth', 1.2);
ylim([0, 5]);
ylabel('TTC (s)'); title('TTC突变 (行人出现)'); grid on; xlabel('时间 (s)');

subplot(4, 4, 11);
plot(t, distance_3, 'b-', 'LineWidth', 1.8);
ylabel('距离 (m)'); title('行人距离'); grid on; xlabel('时间 (s)');

subplot(4, 4, 12);
plot(t, decel_3, 'r-', 'LineWidth', 1.8);
ylabel('减速度 (m/s^2)'); title('紧急制动'); grid on; xlabel('时间 (s)');

% ---- 场景4: 红绿灯 ----
subplot(4, 4, 13);
yyaxis left;
plot(t, speed_4*3.6, 'b-', 'LineWidth', 1.8); hold on;
ylabel('车速 (km/h)', 'Color', 'b');
yyaxis right;
stairs(t, brake_4, 'r-', 'LineWidth', 1.2);
ylabel('制动', 'Color', 'r'); ylim([-0.1, 1.2]);
title('场景4: 红绿灯 绿→红 — 速度'); grid on; xlabel('时间 (s)');

subplot(4, 4, 14);
plot(t, ttc_4, 'g-', 'LineWidth', 1.8); hold on;
yline(TTC_WARNING, 'y--', 'WARN', 'LineWidth', 1.2);
yline(TTC_BRAKE, 'r--', 'BRAKE', 'LineWidth', 1.2);
ylabel('TTC (s)'); title('TTC变化'); grid on; xlabel('时间 (s)');

subplot(4, 4, 15);
plot(t, distance_4, 'b-', 'LineWidth', 1.8);
ylabel('距离 (m)'); title('距停止线距离'); grid on; xlabel('时间 (s)');

subplot(4, 4, 16);
plot(t, decel_4, 'r-', 'LineWidth', 1.8);
ylabel('减速度 (m/s^2)'); title('制动减速度'); grid on; xlabel('时间 (s)');

sgtitle('ADAS AEB 自动紧急制动系统 — 四场景仿真结果', ...
    'FontSize', 16, 'FontWeight', 'bold');

saveas(gcf, fullfile(out_dir, 'aeb_four_scenarios.png'));
fprintf('✅ 四场景综合图已保存\n');

%% ============================================================
%% 绘制关键曲线 (用于论文/报告)
%% ============================================================

% ---- 图1: 速度对比 ----
figure('Position', [100, 100, 800, 500], 'Color', 'white');
plot(t, speed_1*3.6, 'g-', 'LineWidth', 2, 'DisplayName', '场景1: 正常行驶'); hold on;
plot(t, speed_2*3.6, 'b-', 'LineWidth', 2, 'DisplayName', '场景2: 前车急刹');
plot(t, speed_3*3.6, 'r-', 'LineWidth', 2, 'DisplayName', '场景3: 行人横穿');
plot(t, speed_4*3.6, 'm-', 'LineWidth', 2, 'DisplayName', '场景4: 红绿灯停车');
xlabel('时间 (s)', 'FontSize', 12);
ylabel('车速 (km/h)', 'FontSize', 12);
title('AEB 制动 — 车速变化曲线', 'FontSize', 14, 'FontWeight', 'bold');
legend('Location', 'best', 'FontSize', 10);
grid on;
saveas(gcf, fullfile(out_dir, 'speed_comparison.png'));
fprintf('✅ 速度对比图已保存\n');

% ---- 图2: TTC对比 ----
figure('Position', [100, 100, 800, 500], 'Color', 'white');
semilogy(t, ttc_2, 'b-', 'LineWidth', 2, 'DisplayName', '场景2: 前车急刹'); hold on;
semilogy(t, ttc_3, 'r-', 'LineWidth', 2, 'DisplayName', '场景3: 行人横穿');
semilogy(t, ttc_4, 'm-', 'LineWidth', 2, 'DisplayName', '场景4: 红绿灯');
yline(TTC_WARNING, 'y--', 'WARNING=2s', 'LineWidth', 2, 'FontSize', 11);
yline(TTC_BRAKE, 'r--', 'BRAKE=1s', 'LineWidth', 2, 'FontSize', 11);
xlabel('时间 (s)', 'FontSize', 12);
ylabel('TTC (s) — 对数坐标', 'FontSize', 12);
title('碰撞时间 TTC 变化曲线', 'FontSize', 14, 'FontWeight', 'bold');
legend('Location', 'best', 'FontSize', 10);
grid on;
saveas(gcf, fullfile(out_dir, 'ttc_comparison.png'));
fprintf('✅ TTC对比图已保存\n');

% ---- 图3: 制动信号 + 减速度 (场景2) ----
figure('Position', [100, 100, 800, 500], 'Color', 'white');
subplot(2,1,1);
area(t, brake_2, 'FaceColor', [1 0.2 0.2], 'EdgeColor', 'r', 'LineWidth', 1.5, 'FaceAlpha', 0.5);
ylabel('制动信号', 'FontSize', 12);
title('AEB 制动触发信号 (场景2: 前车急刹)', 'FontSize', 14, 'FontWeight', 'bold');
ylim([0, 1.2]); grid on;
text(4, 0.5, '← AEB触发', 'FontSize', 12, 'Color', 'r', 'FontWeight', 'bold');

subplot(2,1,2);
plot(t, decel_2, 'r-', 'LineWidth', 2);
xlabel('时间 (s)', 'FontSize', 12);
ylabel('减速度 (m/s^2)', 'FontSize', 12);
title('制动减速度', 'FontSize', 12);
grid on;
saveas(gcf, fullfile(out_dir, 'brake_signal_deceleration.png'));
fprintf('✅ 制动信号图已保存\n');

%% ============================================================
%% 输出统计结果
%% ============================================================
fprintf('\n=============================================================\n');
fprintf('  仿真结果统计\n');
fprintf('=============================================================\n');

scenarios = {
    '前车正常行驶', speed_1, brake_1, ttc_1;
    '前车突然减速', speed_2, brake_2, ttc_2;
    '行人突然进入', speed_3, brake_3, ttc_3;
    '红绿灯 绿→红', speed_4, brake_4, ttc_4;
};

fprintf('%-16s %-10s %-12s %-14s %-12s\n', ...
    '场景', '初速km/h', '刹停时间s', '刹车距离m', '最小TTC');
fprintf('%-16s %-10s %-12s %-14s %-12s\n', ...
    '----', '----', '------', '------', '------');

for i = 1:size(scenarios, 1)
    name = scenarios{i, 1};
    spd = scenarios{i, 2};
    brk = scenarios{i, 3};
    tc = scenarios{i, 4};

    v0 = spd(1) * 3.6;
    stop_idx = find(spd <= 0.2, 1, 'first');
    if isempty(stop_idx), stop_idx = length(spd); end
    stop_time = t(stop_idx);

    % 刹车距离
    brake_start = find(brk > 0.5, 1, 'first');
    if isempty(brake_start)
        brake_dist = 0;
    else
        brake_dist = sum(spd(brake_start:stop_idx)) * dt;
    end

    min_ttc = min(tc(tc > 0));

    fprintf('%-16s %-10.0f %-12.2f %-14.1f %-12.2f\n', ...
        name, v0, stop_time, brake_dist, min_ttc);
end

fprintf('\n📁 所有图表已保存到: %s\n', out_dir);
fprintf('=============================================================\n');

%% ============================================================
%% 辅助函数
%% ============================================================

function [warning_signal, brake_signal] = aeb_decision_vector(distance, rel_speed, ...
        TTC_WARNING, TTC_BRAKE)
    % 向量化 AEB 决策
    n = length(distance);
    warning_signal = zeros(n, 1);
    brake_signal = zeros(n, 1);

    for i = 1:n
        if rel_speed(i) > 0.1 && distance(i) > 0
            ttc = distance(i) / rel_speed(i);
            if ttc < TTC_BRAKE
                brake_signal(i) = 1;
                warning_signal(i) = 1;
            elseif ttc < TTC_WARNING
                warning_signal(i) = 1;
            end
        end
    end
end

function [speed, deceleration, distance] = simulate_vehicle_dynamics(...
        brake_signal, initial_speed, dt, m, a_max, tau, Cd, Cr, g, rho, A)
    % 车辆动力学仿真

    n = length(brake_signal);
    speed = zeros(n, 1);
    deceleration = zeros(n, 1);
    distance = zeros(n, 1);

    speed(1) = initial_speed;
    brake_pressure = 0;

    for i = 2:n
        % 制动一阶延迟
        target = brake_signal(i);
        brake_pressure = brake_pressure + (target - brake_pressure) * dt / tau;
        brake_effective = brake_pressure;

        % 制动力
        F_brake = brake_effective * m * a_max;

        % 空气阻力
        F_drag = 0.5 * rho * Cd * A * speed(i-1)^2;

        % 滚动阻力
        F_roll = Cr * m * g;

        % 总阻力
        F_total = F_brake + F_drag + F_roll;

        % 加速度
        acc = -F_total / m;
        acc = max(acc, -a_max * 1.2);

        % 欧拉积分
        speed(i) = max(0, speed(i-1) + acc * dt);
        deceleration(i) = abs(acc);

        % 距离积分
        distance(i) = distance(i-1) + 0.5*(speed(i-1)+speed(i))*dt;
    end
end
