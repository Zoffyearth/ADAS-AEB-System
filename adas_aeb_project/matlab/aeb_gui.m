%% aeb_gui.m
%% ADAS AEB 系统 — MATLAB GUI 交互界面
%% 提供参数调节 + 实时仿真 + 可视化
%  运行: aeb_gui

function aeb_gui()
    % 创建主窗口
    fig = figure('Name', 'ADAS AEB 自动紧急制动系统', ...
        'NumberTitle', 'off', ...
        'Position', [150, 150, 1100, 750], ...
        'Color', [0.94 0.94 0.94], ...
        'MenuBar', 'none', ...
        'ToolBar', 'figure', ...
        'Resize', 'on');

    %% ====== 全局数据存储 ======
    data = struct();
    data.simulated = false;
    data.t = [];
    data.speed = [];
    data.decel = [];
    data.distance = [];
    data.ttc = [];
    data.brake = [];
    data.warning = [];

    guidata(fig, data);

    %% ====== UI 布局 ======

    % --- 标题 ---
    uicontrol('Style', 'text', ...
        'String', 'ADAS AEB 自动紧急制动系统', ...
        'FontSize', 18, 'FontWeight', 'bold', ...
        'ForegroundColor', [0.1 0.3 0.6], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'Position', [20, 700, 600, 35], ...
        'HorizontalAlignment', 'left');

    uicontrol('Style', 'text', ...
        'String', '车辆动力学仿真 + TTC风险评估', ...
        'FontSize', 11, ...
        'ForegroundColor', [0.4 0.4 0.4], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'Position', [20, 680, 400, 20], ...
        'HorizontalAlignment', 'left');

    %% ------ 左侧: 参数面板 ------
    panel_params = uipanel('Title', '仿真参数设置', ...
        'FontSize', 12, 'FontWeight', 'bold', ...
        'Position', [0.02, 0.08, 0.28, 0.82]);

    % 初始速度
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '初始车速 (km/h):', ...
        'Position', [15, 440, 130, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    slider_speed = uicontrol('Parent', panel_params, 'Style', 'slider', ...
        'Min', 20, 'Max', 120, 'Value', 60, ...
        'Position', [15, 415, 180, 20], ...
        'Callback', {@update_param_display, 'speed'});

    txt_speed = uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '60 km/h', ...
        'Position', [200, 415, 60, 20], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'FontWeight', 'bold', 'ForegroundColor', [0.1 0.4 0.8]);

    % 制动触发时间
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '制动触发时间 (s):', ...
        'Position', [15, 380, 140, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    slider_brake_t = uicontrol('Parent', panel_params, 'Style', 'slider', ...
        'Min', 0.5, 'Max', 5.0, 'Value', 2.0, ...
        'Position', [15, 355, 180, 20], ...
        'Callback', {@update_param_display, 'brake_t'});

    txt_brake_t = uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '2.0 s', ...
        'Position', [200, 355, 60, 20], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'FontWeight', 'bold', 'ForegroundColor', [0.8 0.3 0.1]);

    % 目标距离
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '初始车距 (m):', ...
        'Position', [15, 320, 140, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    slider_dist = uicontrol('Parent', panel_params, 'Style', 'slider', ...
        'Min', 5, 'Max', 120, 'Value', 40, ...
        'Position', [15, 295, 180, 20], ...
        'Callback', {@update_param_display, 'dist'});

    txt_dist = uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '40 m', ...
        'Position', [200, 295, 60, 20], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'FontWeight', 'bold', 'ForegroundColor', [0.2 0.6 0.2]);

    % 相对速度
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '相对接近速度 (m/s):', ...
        'Position', [15, 260, 150, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    slider_vrel = uicontrol('Parent', panel_params, 'Style', 'slider', ...
        'Min', 1, 'Max', 30, 'Value', 5, ...
        'Position', [15, 235, 180, 20], ...
        'Callback', {@update_param_display, 'vrel'});

    txt_vrel = uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '5 m/s', ...
        'Position', [200, 235, 60, 20], ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'FontWeight', 'bold', 'ForegroundColor', [0.6 0.3 0.8]);

    % AEB 阈值
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', 'TTC 预警阈值 (s):', ...
        'Position', [15, 190, 130, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    edit_ttc_warn = uicontrol('Parent', panel_params, 'Style', 'edit', ...
        'String', '2.0', ...
        'Position', [155, 190, 50, 22], ...
        'BackgroundColor', 'white');

    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', 'TTC 制动阈值 (s):', ...
        'Position', [15, 160, 130, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94]);

    edit_ttc_brake = uicontrol('Parent', panel_params, 'Style', 'edit', ...
        'String', '1.0', ...
        'Position', [155, 160, 50, 22], ...
        'BackgroundColor', 'white');

    % 场景选择
    uicontrol('Parent', panel_params, 'Style', 'text', ...
        'String', '仿真场景:', ...
        'Position', [15, 125, 80, 22], ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', [0.94 0.94 0.94], ...
        'FontWeight', 'bold');

    popup_scene = uicontrol('Parent', panel_params, 'Style', 'popupmenu', ...
        'String', {'前车正常行驶', '前车突然减速', '行人突然进入', '红绿灯 绿→红', '自定义参数'}, ...
        'Position', [100, 125, 160, 22], ...
        'Callback', {@scene_changed, slider_speed, slider_brake_t, slider_dist, slider_vrel, ...
                     txt_speed, txt_brake_t, txt_dist, txt_vrel});

    % 运行按钮
    btn_run = uicontrol('Parent', panel_params, 'Style', 'pushbutton', ...
        'String', '▶  运 行 仿 真', ...
        'FontSize', 14, 'FontWeight', 'bold', ...
        'ForegroundColor', 'white', ...
        'BackgroundColor', [0.2 0.6 0.2], ...
        'Position', [20, 70, 250, 40], ...
        'Callback', @run_simulation);

    % 导出按钮
    btn_export = uicontrol('Parent', panel_params, 'Style', 'pushbutton', ...
        'String', '📊 导出图表', ...
        'FontSize', 11, ...
        'Position', [20, 30, 120, 30], ...
        'Callback', @export_figures);

    btn_reset = uicontrol('Parent', panel_params, 'Style', 'pushbutton', ...
        'String', '🔄 重置', ...
        'FontSize', 11, ...
        'Position', [150, 30, 120, 30], ...
        'Callback', @reset_simulation);

    %% ------ 右侧: 显示面板 ------
    % 速度曲线
    ax_speed = axes('Parent', fig, 'Position', [0.34, 0.57, 0.30, 0.36]);
    title('车速变化曲线', 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('时间 (s)'); ylabel('车速 (km/h)');
    grid on; hold on;

    % TTC曲线
    ax_ttc = axes('Parent', fig, 'Position', [0.68, 0.57, 0.30, 0.36]);
    title('TTC 碰撞时间', 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('时间 (s)'); ylabel('TTC (s)');
    grid on; hold on;
    yline(2.0, 'y--', 'WARN', 'LineWidth', 1.2);
    yline(1.0, 'r--', 'BRAKE', 'LineWidth', 1.2);

    % 减速度曲线
    ax_decel = axes('Parent', fig, 'Position', [0.34, 0.12, 0.30, 0.36]);
    title('制动减速度', 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('时间 (s)'); ylabel('减速度 (m/s^2)');
    grid on; hold on;

    % 制动信号
    ax_brake = axes('Parent', fig, 'Position', [0.68, 0.12, 0.30, 0.36]);
    title('AEB 制动信号', 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('时间 (s)'); ylabel('信号');
    ylim([-0.1, 1.2]);
    grid on; hold on;

    % 状态指示器
    ax_status = axes('Parent', fig, 'Position', [0.34, 0.50, 0.64, 0.04]);
    axis off;

    %% ====== 存储所有控件的句柄 ======
    handles = struct();
    handles.fig = fig;
    handles.panel_params = panel_params;
    handles.slider_speed = slider_speed;
    handles.txt_speed = txt_speed;
    handles.slider_brake_t = slider_brake_t;
    handles.txt_brake_t = txt_brake_t;
    handles.slider_dist = slider_dist;
    handles.txt_dist = txt_dist;
    handles.slider_vrel = slider_vrel;
    handles.txt_vrel = txt_vrel;
    handles.edit_ttc_warn = edit_ttc_warn;
    handles.edit_ttc_brake = edit_ttc_brake;
    handles.popup_scene = popup_scene;
    handles.btn_run = btn_run;
    handles.btn_export = btn_export;
    handles.btn_reset = btn_reset;
    handles.ax_speed = ax_speed;
    handles.ax_ttc = ax_ttc;
    handles.ax_decel = ax_decel;
    handles.ax_brake = ax_brake;
    handles.ax_status = ax_status;

    guidata(fig, handles);

    %% ====== 回调函数 ======

    function update_param_display(~, ~, param_name)
        handles = guidata(fig);
        switch param_name
            case 'speed'
                val = round(get(handles.slider_speed, 'Value'));
                set(handles.txt_speed, 'String', sprintf('%d km/h', val));
            case 'brake_t'
                val = get(handles.slider_brake_t, 'Value');
                set(handles.txt_brake_t, 'String', sprintf('%.1f s', val));
            case 'dist'
                val = round(get(handles.slider_dist, 'Value'));
                set(handles.txt_dist, 'String', sprintf('%d m', val));
            case 'vrel'
                val = round(get(handles.slider_vrel, 'Value'));
                set(handles.txt_vrel, 'String', sprintf('%d m/s', val));
        end
    end

    function scene_changed(~, ~, slider_speed, slider_brake_t, slider_dist, slider_vrel, ...
            txt_speed, txt_brake_t, txt_dist, txt_vrel)
        scene_idx = get(popup_scene, 'Value');
        % 预设场景参数 [speed, brake_t, dist, vrel]
        presets = {
            [60, 10.0, 80, 2];    % 场景1: 正常行驶 (制动晚触发=无制动)
            [80, 2.0,  40, 12];    % 场景2: 前车急刹
            [50, 1.5,  15, 14];    % 场景3: 行人横穿
            [60, 2.0,  50, 17];    % 场景4: 红绿灯
            [60, 2.0,  40, 5];     % 自定义
        };
        p = presets{scene_idx};

        set(slider_speed, 'Value', p(1));
        set(txt_speed, 'String', sprintf('%d km/h', p(1)));

        set(slider_brake_t, 'Value', p(2));
        set(txt_brake_t, 'String', sprintf('%.1f s', p(2)));

        set(slider_dist, 'Value', p(3));
        set(txt_dist, 'String', sprintf('%d m', p(3)));

        set(slider_vrel, 'Value', p(4));
        set(txt_vrel, 'String', sprintf('%d m/s', p(4)));
    end

    function run_simulation(~, ~)
        handles = guidata(fig);

        % 读取参数
        v0_kmh = get(handles.slider_speed, 'Value');
        brake_trigger = get(handles.slider_brake_t, 'Value');
        init_dist = get(handles.slider_dist, 'Value');
        v_rel = get(handles.slider_vrel, 'Value');
        ttc_warn = str2double(get(handles.edit_ttc_warn, 'String'));
        ttc_brake = str2double(get(handles.edit_ttc_brake, 'String'));

        v0 = v0_kmh / 3.6;

        % 仿真参数
        dt = 0.01;
        total_t = ceil(brake_trigger + 8);
        t_sim = (0:dt:total_t)';
        n = length(t_sim);

        % 生成距离曲线 (简化: 线性接近)
        dist = max(1, init_dist - v_rel * t_sim);

        % 计算TTC
        ttc = zeros(n, 1);
        for i = 1:n
            if v_rel > 0.1 && dist(i) > 0
                ttc(i) = dist(i) / v_rel;
            else
                ttc(i) = 100;
            end
        end

        % AEB决策
        warning_sig = ttc < ttc_warn;
        brake_sig = ttc < ttc_brake;

        % 车辆动力学
        [speed, decel, ~] = simulate_vehicle(v0, brake_sig, dt, total_t);

        % 更新图表
        cla(handles.ax_speed);
        plot(handles.ax_speed, t_sim, speed*3.6, 'b-', 'LineWidth', 2.5);
        xlabel(handles.ax_speed, '时间 (s)');
        ylabel(handles.ax_speed, '车速 (km/h)');
        title(handles.ax_speed, sprintf('车速变化 (初速 %.0f km/h)', v0_kmh), ...
            'FontSize', 12, 'FontWeight', 'bold');
        grid(handles.ax_speed, 'on');
        % 标出制动起始点
        hold(handles.ax_speed, 'on');
        if brake_trigger < total_t
            xline(handles.ax_speed, brake_trigger, 'r--', '制动触发', 'LineWidth', 1.5);
        end
        hold(handles.ax_speed, 'off');

        cla(handles.ax_ttc);
        semilogy(handles.ax_ttc, t_sim, max(ttc, 0.1), 'g-', 'LineWidth', 2);
        hold(handles.ax_ttc, 'on');
        yline(handles.ax_ttc, ttc_warn, 'y--', 'WARN', 'LineWidth', 1.5);
        yline(handles.ax_ttc, ttc_brake, 'r--', 'BRAKE', 'LineWidth', 1.5);
        hold(handles.ax_ttc, 'off');
        xlabel(handles.ax_ttc, '时间 (s)');
        ylabel(handles.ax_ttc, 'TTC (s) — log');
        title(handles.ax_ttc, 'TTC 碰撞时间', 'FontSize', 12, 'FontWeight', 'bold');
        grid(handles.ax_ttc, 'on');

        cla(handles.ax_decel);
        plot(handles.ax_decel, t_sim, decel, 'r-', 'LineWidth', 2);
        xlabel(handles.ax_decel, '时间 (s)');
        ylabel(handles.ax_decel, '减速度 (m/s^2)');
        title(handles.ax_decel, '制动减速度', 'FontSize', 12, 'FontWeight', 'bold');
        grid(handles.ax_decel, 'on');

        cla(handles.ax_brake);
        area(handles.ax_brake, t_sim, double(brake_sig), ...
            'FaceColor', [1 0.2 0.2], 'FaceAlpha', 0.6, 'EdgeColor', 'r');
        ylim(handles.ax_brake, [-0.1, 1.2]);
        xlabel(handles.ax_brake, '时间 (s)');
        ylabel(handles.ax_brake, '制动信号');
        title(handles.ax_brake, 'AEB 制动触发', 'FontSize', 12, 'FontWeight', 'bold');
        grid(handles.ax_brake, 'on');

        % 状态指示
        stop_idx = find(speed <= 0.2, 1, 'first');
        if isempty(stop_idx), stop_idx = n; end
        stop_t = t_sim(stop_idx);

        cla(handles.ax_status);
        text(0.5, 0.5, ...
            sprintf('刹停时间: %.2fs  |  最小TTC: %.2fs  |  制动状态: %s', ...
                stop_t, min(ttc(ttc>0)), ...
                cond(max(ttc<ttc_brake)>0, '🛑 紧急制动', ...
                     cond(max(ttc<ttc_warn)>0, '⚠️ 预警', '✅ 安全'))), ...
            'FontSize', 13, 'FontWeight', 'bold', ...
            'HorizontalAlignment', 'center', ...
            'Parent', handles.ax_status);
        axis(handles.ax_status, 'off');

        % 保存数据
        data.simulated = true;
        data.t = t_sim;
        data.speed = speed;
        data.decel = decel;
        data.distance = dist;
        data.ttc = ttc;
        data.brake = brake_sig;
        data.warning = warning_sig;
        guidata(fig, data);

        fprintf('仿真完成: 速度=%.0f → 0 km/h, 刹停=%.2fs, TTC_min=%.2fs\n', ...
            v0_kmh, stop_t, min(ttc(ttc>0)));
    end

    function export_figures(~, ~)
        data = guidata(fig);
        if ~data.simulated
            msgbox('请先运行仿真再导出图表', '提示', 'warn');
            return;
        end

        out_dir = fullfile(pwd, 'simulation_results');
        if ~exist(out_dir, 'dir'), mkdir(out_dir); end

        % 创建导出图
        fig_export = figure('Visible', 'off', 'Position', [100,100,1200,800]);

        subplot(2,2,1);
        plot(data.t, data.speed*3.6, 'b-', 'LineWidth', 2);
        xlabel('时间 (s)'); ylabel('速度 (km/h)');
        title('车速变化'); grid on;

        subplot(2,2,2);
        semilogy(data.t, max(data.ttc,0.1), 'g-', 'LineWidth', 2); hold on;
        yline(2.0, 'y--'); yline(1.0, 'r--');
        xlabel('时间 (s)'); ylabel('TTC (s)');
        title('TTC 碰撞时间'); grid on;

        subplot(2,2,3);
        plot(data.t, data.decel, 'r-', 'LineWidth', 2);
        xlabel('时间 (s)'); ylabel('减速度 (m/s^2)');
        title('制动减速度'); grid on;

        subplot(2,2,4);
        area(data.t, double(data.brake), 'FaceColor',[1 0.2 0.2], 'FaceAlpha',0.5);
        ylim([-0.1, 1.2]);
        xlabel('时间 (s)'); ylabel('信号');
        title('AEB 制动信号'); grid on;

        sgtitle('ADAS AEB 制动仿真结果', 'FontSize', 14, 'FontWeight', 'bold');

        timestamp = datestr(now, 'yyyy-mm-dd_HH-MM-SS');
        fname = fullfile(out_dir, ['aeb_gui_export_', timestamp, '.png']);
        saveas(fig_export, fname);
        close(fig_export);

        msgbox(sprintf('图表已导出:\n%s', fname), '导出成功');
        fprintf('图表已保存: %s\n', fname);
    end

    function reset_simulation(~, ~)
        handles = guidata(fig);
        cla(handles.ax_speed);
        cla(handles.ax_ttc);
        cla(handles.ax_decel);
        cla(handles.ax_brake);
        cla(handles.ax_status);
        data.simulated = false;
        guidata(fig, data);
    end

    function res = cond(condition, true_val, false_val)
        if condition
            res = true_val;
        else
            res = false_val;
        end
    end
end

%% ====== 车辆动力学仿真 (内部函数) ======

function [speed, decel, distance] = simulate_vehicle(v0, brake_signal, dt, total_t)
    % 参数
    m = 1500; a_max = 8.0; tau = 0.3;
    Cd = 0.3; Cr = 0.015; g = 9.81; rho = 1.225; A = 2.2;

    n = length(brake_signal);
    speed = zeros(n, 1);
    decel = zeros(n, 1);
    distance = zeros(n, 1);
    speed(1) = v0;

    brake_pressure = 0;
    for i = 2:n
        target = brake_signal(i);
        brake_pressure = brake_pressure + (target - brake_pressure) * dt / tau;
        bp = brake_pressure;

        F_brake = bp * m * a_max;
        F_drag = 0.5 * rho * Cd * A * speed(i-1)^2;
        F_roll = Cr * m * g;
        F_total = F_brake + F_drag + F_roll;

        acc = -F_total / m;
        acc = max(acc, -a_max * 1.2);

        speed(i) = max(0, speed(i-1) + acc * dt);
        decel(i) = abs(acc);
        distance(i) = distance(i-1) + 0.5*(speed(i-1)+speed(i))*dt;
    end
end
