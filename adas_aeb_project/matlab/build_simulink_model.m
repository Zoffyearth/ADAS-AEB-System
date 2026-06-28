%% build_simulink_model.m
%% 自动构建 AEB 车辆动力学 Simulink 模型
%  运行此脚本自动创建完整的 Simulink 模型，无需手动连线

function build_simulink_model()
    %% 创建新模型
    model_name = 'aeb_vehicle_model';

    % 关闭已存在的模型
    if bdIsLoaded(model_name)
        close_system(model_name, 1);
    end

    % 创建空白模型
    new_system(model_name);
    open_system(model_name);

    %% 模型参数
    m = 1500;           % 整车质量 kg
    a_max = 8.0;        % 最大制动减速度 m/s^2
    tau = 0.3;          % 制动响应延迟 s
    Cd = 0.3;           % 空气阻力系数
    Cr = 0.015;         % 滚动阻力系数
    g = 9.81;           % 重力加速度
    initial_speed = 60/3.6;  % 初始速度 m/s (60km/h)

    %% ====== 创建 Block ======

    % --- 制动信号输入 ---
    % Step: 在 t=2s 触发制动
    add_block('simulink/Sources/Step', [model_name '/Brake_Trigger']);
    set_param([model_name '/Brake_Trigger'], ...
        'Time', '2', ...
        'Before', '0', ...
        'After', '1');

    % --- 制动系统一阶延迟 ---
    add_block('simulink/Continuous/Transfer Fcn', [model_name '/Brake_Delay']);
    set_param([model_name '/Brake_Delay'], ...
        'Denominator', ['[', num2str(tau), ' 1]']);

    % --- 制动力增益 ---
    add_block('simulink/Math Operations/Gain', [model_name '/Brake_Force_Gain']);
    set_param([model_name '/Brake_Force_Gain'], ...
        'Gain', num2str(m * a_max));

    % --- 空气阻力计算 ---
    % F_drag = 0.5*rho*Cd*A*v^2，简化为 K_drag * v^2
    K_drag = 0.3;

    add_block('simulink/Math Operations/Math Function', [model_name '/Speed_Square']);
    set_param([model_name '/Speed_Square'], ...
        'Operator', 'square');

    add_block('simulink/Math Operations/Gain', [model_name '/Drag_Gain']);
    set_param([model_name '/Drag_Gain'], ...
        'Gain', num2str(K_drag));

    % --- 滚动阻力常数 ---
    F_roll = Cr * m * g;
    add_block('simulink/Sources/Constant', [model_name '/Rolling_Resistance']);
    set_param([model_name '/Rolling_Resistance'], ...
        'Value', num2str(F_roll));

    % --- 合力求和 ---
    add_block('simulink/Math Operations/Add', [model_name '/Total_Force']);
    set_param([model_name '/Total_Force'], ...
        'Inputs', '+++', ...
        'IconShape', 'round');

    % --- 力→加速度 (1/m) ---
    add_block('simulink/Math Operations/Gain', [model_name '/Accel_Gain']);
    set_param([model_name '/Accel_Gain'], ...
        'Gain', num2str(1/m));

    % --- 饱和限幅 (限制最大减速度) ---
    add_block('simulink/Discontinuities/Saturation', [model_name '/Accel_Limit']);
    set_param([model_name '/Accel_Limit'], ...
        'UpperLimit', '5', ...
        'LowerLimit', num2str(-a_max * 1.2));

    % --- 积分器: 加速度→速度 ---
    add_block('simulink/Continuous/Integrator', [model_name '/Integrator_Speed']);
    set_param([model_name '/Integrator_Speed'], ...
        'InitialCondition', num2str(initial_speed));

    % --- 速度限幅 (不低于0) ---
    add_block('simulink/Discontinuities/Saturation', [model_name '/Speed_Limit']);
    set_param([model_name '/Speed_Limit'], ...
        'UpperLimit', '100', ...
        'LowerLimit', '0');

    % --- 积分器: 速度→位移 ---
    add_block('simulink/Continuous/Integrator', [model_name '/Integrator_Distance']);
    set_param([model_name '/Integrator_Distance'], ...
        'InitialCondition', '0');

    % --- 输出端口 ---
    add_block('simulink/Sinks/Out1', [model_name '/Speed_Out']);
    add_block('simulink/Sinks/Out1', [model_name '/Distance_Out']);
    add_block('simulink/Sinks/Out1', [model_name '/Decel_Out']);

    set_param([model_name '/Speed_Out'], 'Port', '1');
    set_param([model_name '/Distance_Out'], 'Port', '2');
    set_param([model_name '/Decel_Out'], 'Port', '3');

    % --- Scope 显示 ---
    add_block('simulink/Sinks/Scope', [model_name '/Speed_Distance_Scope']);
    set_param([model_name '/Speed_Distance_Scope'], ...
        'NumInputPorts', '3');

    %% ====== 连线 ======

    % 制动链路
    add_line(model_name, 'Brake_Trigger/1', 'Brake_Delay/1');
    add_line(model_name, 'Brake_Delay/1', 'Brake_Force_Gain/1');
    add_line(model_name, 'Brake_Force_Gain/1', 'Total_Force/1');

    % 空气阻力链路 (从速度反馈)
    add_line(model_name, 'Speed_Limit/1', 'Speed_Square/1');
    add_line(model_name, 'Speed_Square/1', 'Drag_Gain/1');
    add_line(model_name, 'Drag_Gain/1', 'Total_Force/2');

    % 滚动阻力链路
    add_line(model_name, 'Rolling_Resistance/1', 'Total_Force/3');

    % 合力→加速度→速度→位移
    add_line(model_name, 'Total_Force/1', 'Accel_Gain/1');
    add_line(model_name, 'Accel_Gain/1', 'Accel_Limit/1');
    add_line(model_name, 'Accel_Limit/1', 'Integrator_Speed/1');
    add_line(model_name, 'Integrator_Speed/1', 'Speed_Limit/1');
    add_line(model_name, 'Speed_Limit/1', 'Integrator_Distance/1');

    % 输出
    add_line(model_name, 'Speed_Limit/1', 'Speed_Out/1');
    add_line(model_name, 'Integrator_Distance/1', 'Distance_Out/1');
    add_line(model_name, 'Accel_Limit/1', 'Decel_Out/1');

    % Scope
    add_line(model_name, 'Speed_Limit/1', 'Speed_Distance_Scope/1');
    add_line(model_name, 'Integrator_Distance/1', 'Speed_Distance_Scope/2');
    add_line(model_name, 'Accel_Limit/1', 'Speed_Distance_Scope/3');

    %% ====== 布局优化 ======
    % 自动排列
    Simulink.BlockDiagram.arrangeSystem(model_name);

    %% ====== 模型配置 ======
    set_param(model_name, ...
        'StopTime', '10', ...
        'Solver', 'ode4', ...
        'FixedStep', '0.01');

    %% 保存
    save_system(model_name);
    fprintf('✅ Simulink 模型 "%s.slx" 已创建并保存\n', model_name);
    fprintf('   路径: %s\n', fullfile(pwd, [model_name, '.slx']));
    fprintf('\n运行仿真: sim(''%s'')\n', model_name);
end

%% ====== 运行 ======
% 在 MATLAB 命令行执行: build_simulink_model
