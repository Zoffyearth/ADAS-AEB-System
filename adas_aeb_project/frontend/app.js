/**
 * ADAS AEB 系统 — 前端交互逻辑
 */
(function() {
'use strict';

// ============================================================
// DOM 工具
// ============================================================
const $ = (id) => document.getElementById(id);
const safeEl = (id) => $(id) || { addEventListener:()=>{}, style:{}, textContent:'', disabled:false };

// ============================================================
// 全局状态
// ============================================================
const state = {
    ws: null,
    videoLoaded: false,
    running: false,
    paused: false,
    fps: 25,
    totalFrames: 0,
    duration: 0,
    charts: {},
    chartData: { time:[], distance:[], ttc:[], speed:[], signal:[] },
};

// ============================================================
// 初始化 — DOM 加载后执行 (兼容 DOM 已就绪 & CDN 延迟)
// ============================================================
function doInit() {
    if (typeof Chart === 'undefined') {
        console.error('[ADAS] Chart.js 未加载! 重试中...');
        setTimeout(doInit, 200);  // CDN 可能延迟，200ms后重试
        return;
    }
    console.log('[ADAS] 初始化...');
    initCharts();
    bindEvents();
    console.log('[ADAS] 初始化完成 — Charts:', Object.keys(state.charts).length, 'events bound');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', doInit);
} else {
    doInit();
}

// ============================================================
// Chart.js 初始化
// ============================================================
function makeCfg(label, color, yLabel) {
    return {
        type: 'line',
        data: { labels:[], datasets:[{ label, data:[], borderColor:color, backgroundColor:color+'30', borderWidth:1.5, pointRadius:0, fill:true, tension:0.3 }] },
        options: {
            responsive:true, maintainAspectRatio:false, animation:{duration:0},
            plugins:{ legend:{display:false} },
            scales: {
                x:{ display:true, title:{display:true,text:'时间(s)',color:'#9498b0'}, ticks:{color:'#9498b0',maxTicksLimit:8}, grid:{color:'#2e335040'} },
                y:{ display:true, title:{display:true,text:yLabel,color:'#9498b0'}, ticks:{color:'#9498b0',maxTicksLimit:6}, grid:{color:'#2e335040'} },
            },
        },
    };
}

function initCharts() {
    // canvas_id → chart_key (统一小写)
    const chartMap = {
        'chartDistance': 'distance', 'chartTTC': 'ttc', 'chartSpeed': 'speed', 'chartBrake': 'brake',
        'chartSim1': 'sim1', 'chartSim2': 'sim2', 'chartSim3': 'sim3', 'chartSim4': 'sim4',
    };
    const chartLabels = {
        'distance':'距离(m)','ttc':'TTC(s)','speed':'车速(km/h)','brake':'信号',
        'sim1':'','sim2':'','sim3':'','sim4':'',
    };
    const chartColors = {
        'distance':'#3b82f6','ttc':'#eab308','speed':'#22c55e','brake':'#ef4444',
        'sim1':'#3b82f6','sim2':'#ef4444','sim3':'#8b5cf6','sim4':'#f97316',
    };
    for (const [canvasId, key] of Object.entries(chartMap)) {
        const el = $(canvasId);
        if (!el) { console.warn('[ADAS] Canvas缺失:', canvasId); continue; }
        try {
            state.charts[key] = new Chart(el.getContext('2d'),
                makeCfg('', chartColors[key], chartLabels[key]));
        } catch(e) { console.warn('[ADAS] Chart创建失败:', canvasId, e.message); }
    }
    console.log('[ADAS] Charts:', Object.keys(state.charts).join(', '));
}

function setTitles(t1,t2,t3,t4) {
    [t1,t2,t3,t4].forEach((t,i) => {
        const el = $('simTitle'+(i+1)); if (el) el.textContent = t || '';
    });
}

function updateChart(chart, labels, data, maxPts=150) {
    if (!chart) return;
    if (labels.length > maxPts) {
        chart.data.labels = labels.slice(-maxPts);
        chart.data.datasets[0].data = data.slice(-maxPts);
    } else {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
    }
    chart.update('none');
}

// ============================================================
// 事件绑定
// ============================================================
function bindEvents() {
    // 视频上传
    const vu = $('videoUpload'); if (vu) vu.addEventListener('change', onUpload);
    // 速度设置
    const es = $('egoSpeed'); if (es) es.addEventListener('change', onSpeedChange);
    // 按钮
    const bs = $('btnStart'); if (bs) bs.addEventListener('click', startDetection);
    const bp = $('btnPause'); if (bp) bp.addEventListener('click', togglePause);
    const bst = $('btnStop'); if (bst) bst.addEventListener('click', stopDetection);
    const br = $('btnReset'); if (br) br.addEventListener('click', resetSession);
    // 仿真模式按钮
    document.querySelectorAll('.sim-buttons .btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.sim-buttons .btn').forEach(b=>b.classList.remove('active'));
            this.classList.add('active');
            simMode = this.dataset.mode;
            const ml=$('simModeLabel'); if(ml) ml.textContent=this.textContent.trim();
            runSimMode(simMode);
        });
    });
    // 仿真滑块
    // 时间线
    const slider = $('seekSlider');
    if (slider) {
        slider.addEventListener('input', ()=>{
            const f=parseInt(slider.value);
            const tc=$('timeCurrent'); if(tc && state.fps) tc.textContent=fmtTime(f/state.fps);
        });
        slider.addEventListener('change', ()=>{
            const f=parseInt(slider.value);
            if (state.ws && state.ws.readyState===WebSocket.OPEN) {
                state.ws.send(JSON.stringify({cmd:'seek',frame:f}));
                for (const k of ['time','distance','ttc','speed','signal']) state.chartData[k]=[];
                Object.values(state.charts).forEach(c=>{ if(c){c.data.labels=[];c.data.datasets[0].data=[];c.update('none');}});
            }
        });
    }
    console.log('[ADAS] 事件绑定完成');
}

// ============================================================
// 视频上传
// ============================================================
async function onUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const sb = $('statusBadge'); if (sb) { sb.textContent='上传中...'; sb.className='badge'; }
    try {
        const fd = new FormData(); fd.append('file', file);
        const r = await fetch('/api/upload', {method:'POST', body:fd});
        const d = await r.json();
        if (d.error) { alert('上传失败: '+d.error); return; }
        state.videoLoaded = true;
        const b = $('btnStart'); if (b) b.disabled = false;
        if (sb) { sb.textContent='已加载'; sb.className='badge'; }
        const vp = $('videoPlaceholder');
        if (vp) vp.innerHTML = '<p style="color:#22c55e;">\\u2705 '+d.filename+'</p><p style="color:#9498b0;">大小: '+d.size_mb+' MB</p>';
    } catch(err) { alert('上传出错: '+err.message); if (sb) { sb.textContent='错误'; sb.className='badge danger'; } }
}

// ============================================================
// 速度同步
// ============================================================
async function onSpeedChange() {
    const es = $('egoSpeed');
    const speed = es ? (parseFloat(es.value)||60) : 60;
    const sv = $('speedValue'); if (sv) sv.textContent = speed.toFixed(1);
    try { await fetch('/api/vehicle/speed', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speed})}); } catch(e){}
}

// ============================================================
// WebSocket 实时检测
// ============================================================
async function startDetection() {
    if (!state.videoLoaded) { alert('请先上传视频'); return; }
    if (state.ws && state.ws.readyState===WebSocket.OPEN && !state.paused) return;

    if (state.paused && state.ws && state.ws.readyState===WebSocket.OPEN) {
        state.ws.send(JSON.stringify({cmd:'resume'}));
        state.paused = false;
        const bp = $('btnPause'); if (bp) bp.textContent = '\\u23F8 \\u6682\\u505C';
        return;
    }

    const es = $('egoSpeed'); const egoSpeed = es ? (parseFloat(es.value)||60) : 60;
    const sv = $('speedValue'); if (sv) sv.textContent = egoSpeed.toFixed(1);
    await fetch('/api/vehicle/speed', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speed:egoSpeed})});

    state.running = true; state.paused = false;
    setBtn('btnStart','none'); setBtn('btnPause','inline-block');
    const bp2 = $('btnPause'); if (bp2) { bp2.textContent='\\u23F8 \\u6682\\u505C'; bp2.disabled=false; }
    const bst = $('btnStop'); if (bst) bst.disabled = false;
    const sb = $('statusBadge'); if (sb) { sb.textContent='\\u8FD0\\u884C\\u4E2D'; sb.className='badge'; }
    const pb = $('progressBar'); if (pb) pb.style.display='block';
    const vf = $('videoFrame'); if (vf) vf.style.display='block';
    const vp = $('videoPlaceholder'); if (vp) vp.style.display='none';
    const tb = $('timelineBar'); if (tb) tb.style.display='flex';

    for (const k of ['time','distance','ttc','speed','signal']) state.chartData[k] = [];

    const proto = location.protocol==='https:'?'wss:':'ws:';
    state.ws = new WebSocket(proto+'//'+location.host+'/ws/detect');

    state.ws.onopen = () => console.log('[WS] 已连接');
    state.ws.onclose = () => { console.log('[WS] 断开'); if (state.running) stopDetection(); };
    state.ws.onerror = () => { console.error('[WS] 错误'); stopDetection(); };

    state.ws.onmessage = (ev) => {
        try {
            const msg = JSON.parse(ev.data);
            if (msg.type==='metadata') {
                state.fps=msg.fps; state.totalFrames=msg.frame_count; state.duration=msg.duration;
                const sl=$('seekSlider'); if(sl){sl.max=msg.frame_count;}
                const tt=$('timeTotal'); if(tt){tt.textContent=fmtTime(msg.duration);}
                return;
            }
            if (msg.type==='finished') { stopDetection(); const sb=$('statusBadge'); if(sb){sb.textContent='\\u5B8C\\u6210';sb.className='badge';} return; }
            if (msg.error) { console.error(msg.error); stopDetection(); return; }
            if (msg.frame_jpeg) {
                const bytes = new Uint8Array(msg.frame_jpeg.match(/.{2}/g).map(b=>parseInt(b,16)));
                const blob = new Blob([bytes],{type:'image/jpeg'});
                const vf=$('videoFrame'); if(vf) vf.src = URL.createObjectURL(blob);
            }
            updateDashboard(msg);
            updateCurves(msg);
            if (msg.total_frames) {
                const pf=$('progressFill'); if(pf) pf.style.width = (msg.frame_idx/msg.total_frames*100)+'%';
                const pt=$('progressText'); if(pt) pt.textContent = '帧 '+msg.frame_idx+'/'+msg.total_frames+' | '+fmtTime(msg.time||0);
                const tc=$('timeCurrent'); if(tc) tc.textContent = fmtTime(msg.time||0);
                const sl=$('seekSlider'); if(sl) sl.value = msg.frame_idx;
            }
            updateCarAnim(msg);
        } catch(err) { console.error('[WS] 解析错误:', err); }
    };
}

function stopDetection() {
    state.running = false; state.paused = false;
    setBtn('btnStart','inline-block');
    const bs = $('btnStart'); if (bs) bs.disabled = !state.videoLoaded;
    setBtn('btnPause','none');
    const bp = $('btnPause'); if (bp) bp.disabled = true;
    const bst = $('btnStop'); if (bst) bst.disabled = true;
    const sb = $('statusBadge'); if (sb) { sb.textContent='\\u5DF2\\u505C\\u6B62'; sb.className='badge warning'; }
    if (state.ws) { try{state.ws.send(JSON.stringify({cmd:'stop'}));}catch(e){} state.ws.close(); state.ws=null; }
}

async function resetSession() {
    stopDetection();
    await fetch('/api/reset',{method:'POST'});
    const vf=$('videoFrame'); if(vf) vf.style.display='none';
    const vp=$('videoPlaceholder'); if(vp){vp.style.display='flex';vp.innerHTML='<div class="upload-icon">\\uD83C\\uDFAC</div><p>上传视频文件开始检测</p><p class="hint">支持 MP4 / AVI / MOV 格式</p>';}
    const pb=$('progressBar'); if(pb) pb.style.display='none';
    const pf=$('progressFill'); if(pf) pf.style.width='0%';
    const pt=$('progressText'); if(pt) pt.textContent='';
    const tb=$('timelineBar'); if(tb) tb.style.display='none';
    const sl=$('seekSlider'); if(sl) sl.value=0;
    const tc=$('timeCurrent'); if(tc) tc.textContent='0:00';
    const tt=$('timeTotal'); if(tt) tt.textContent='0:00';
    setBtn('btnStart','inline-block'); setBtn('btnPause','none');
    const bp=$('btnPause'); if(bp) bp.disabled=true;
    const sb=$('statusBadge'); if(sb){sb.textContent='就绪';sb.className='badge';}
    const tv=$('ttcValue'); if(tv) tv.textContent='--';
    const dv=$('distanceValue'); if(dv) dv.textContent='--';
    const sv=$('speedValue'); if(sv) sv.textContent='60.0';
    const stv=$('statusValue'); if(stv){stv.textContent='🟢 SAFE';stv.className='gauge-value status-safe';}
    state.videoLoaded=false; state.paused=false;
    const bs=$('btnStart'); if(bs) bs.disabled=true;
    Object.values(state.charts).forEach(c=>{if(c){c.data.labels=[];c.data.datasets[0].data=[];c.update('none');}});
}

function togglePause() {
    if (!state.running||!state.ws) return;
    if (state.paused) {
        state.ws.send(JSON.stringify({cmd:'resume'}));
        state.paused = false;
        const bp=$('btnPause'); if(bp) bp.textContent='⏸ 暂停';
        const sb=$('statusBadge'); if(sb){sb.textContent='运行中';sb.className='badge';}
    } else {
        state.ws.send(JSON.stringify({cmd:'pause'}));
        state.paused = true;
        const bp=$('btnPause'); if(bp) bp.textContent='▶ 继续';
        const sb=$('statusBadge'); if(sb){sb.textContent='已暂停';sb.className='badge warning';}
    }
}

// ============================================================
// 仪表盘
// ============================================================
function updateDashboard(msg) {
    const risk = msg.risk || {};
    const tv=$('ttcValue');
    if (tv) tv.textContent = (risk.ttc!=null) ? risk.ttc.toFixed(2) : '∞';
    const cars = (msg.detections||[]).filter(d=>d.class==='car'&&d.distance);
    const dv=$('distanceValue');
    if (dv) dv.textContent = cars.length ? Math.min(...cars.map(c=>c.distance)).toFixed(1) : '--';
    const sv=$('speedValue');
    if (sv && msg.vehicle_speed!=null) sv.textContent = msg.vehicle_speed.toFixed(1);
    const stv=$('statusValue'); if (!stv) return;
    stv.className = 'gauge-value';
    if (risk.signal==='BRAKE') { stv.textContent='🔴 BRAKE'; stv.classList.add('status-brake'); }
    else if (risk.signal==='WARNING') { stv.textContent='🟡 WARN'; stv.classList.add('status-warning'); }
    else { stv.textContent='🟢 SAFE'; stv.classList.add('status-safe'); }
}

// ============================================================
// 实时曲线
// ============================================================
function updateCurves(msg) {
    const t = msg.time || 0;
    const risk = msg.risk || {};
    const distVal = parseFloat((($('distanceValue')||{}).textContent)||0);

    state.chartData.time.push(t);
    state.chartData.distance.push(distVal);
    state.chartData.ttc.push((risk.ttc!=null && risk.ttc>0)?risk.ttc:NaN);
    state.chartData.speed.push((msg.vehicle_speed!=null)?msg.vehicle_speed:60);
    state.chartData.signal.push(risk.signal==='BRAKE'?2:risk.signal==='WARNING'?1:0);

    updateChart(state.charts['distance'], state.chartData.time, state.chartData.distance);
    updateChart(state.charts['ttc'], state.chartData.time, state.chartData.ttc);
    updateChart(state.charts['speed'], state.chartData.time, state.chartData.speed);
    updateChart(state.charts['brake'], state.chartData.time, state.chartData.signal);
}

// ============================================================
// 制动仿真 — 6种分析模式 + 可调参数
// ============================================================
let simMode = 'single';

function getSimParams() {
    const g = (id, def) => { const e=$(id); return e ? parseFloat(e.value) : def; };
    return {
        speed: g('simSpeed', 60),
        brakeT: g('simBrakeT', 2.0),
        mass: g('simMass', 1500),
        friction: g('simFriction', 0.8),
        dt: 0.05,
    };
}

function updateSummary(d) {
    const st=$('simStopTime'); if(st) st.textContent = d.stopping_time || '--';
    const sd=$('simStopDist'); if(sd) sd.textContent = d.stopping_distance || '--';
    const md=$('simMaxDecel'); if(md) md.textContent = d.max_deceleration || '--';
}

// 参数滑块实时显示
['simSpeed','simMass','simFriction'].forEach(id => {
    const el = $(id); if (!el) return;
    const disp = $(id+'Value'); if (!disp) return;
    const units = {simSpeed:' km/h', simMass:' kg', simFriction:''};
    el.addEventListener('input', () => {
        disp.textContent = el.value + (units[id]||'');
    });
});
const sbt = $('simBrakeT');
if (sbt) sbt.addEventListener('input', ()=>{
    const d=$('simBrakeTValue'); if(d) d.textContent=parseFloat(sbt.value).toFixed(1)+' s';
});

// 模式按钮已在 bindEvents 中注册, 此处不需要重复

async function runSimMode(mode) {
    const modeLabel = $('simModeLabel');
    if (modeLabel) modeLabel.textContent = '加载中...';
    try {
    const p = getSimParams();
    const brakeFrame = Math.round(p.brakeT / p.dt);
    const totalFrames = Math.min(Math.ceil((p.brakeT + 8) / p.dt), 400);
    const COLORS = ['#3b82f6','#22c55e','#eab308','#f97316','#ef4444','#8b5cf6','#ec4899'];
    ['sim1','sim2','sim3','sim4'].forEach(k => {
        const c = state.charts[k]; if (c) c.config.type = 'line';
    });

    const sa = (d, path, msg) => { // safe access: "d.results[0].time" -> value or throw
        const parts = path.split('.');
        let v = d;
        for (const part of parts) {
            const m = part.match(/^(\w+)\[(\d+)\]$/);
            if (m) { v = v[m[1]]; if (!v) throw new Error(msg||(m[1]+' is missing')); v = v[parseInt(m[2])]; }
            else { v = v[part]; }
            if (v === undefined || v === null) throw new Error(msg||(path+' is missing'));
        }
        return v;
    };

    let r, d, lbl;

    switch(mode) {
    case 'single':
        r = await fetch('/api/simulate/brake', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({initial_speed:p.speed, brake_at_frame:brakeFrame, total_frames:totalFrames, dt:p.dt, mass:p.mass, friction:p.friction})});
        d = await r.json();
        lbl = sa(d, 'time', 'API未返回time').map(t=>parseFloat(t).toFixed(1));
        setChart('sim1', '车速('+p.speed+'km/h)', sa(d,'speed_kmh'), lbl, '#3b82f6');
        setChart('sim2', '减速度', sa(d,'deceleration'), lbl, '#ef4444');
        setChart('sim3', '行驶距离(m)', sa(d,'distance'), lbl, '#22c55e');
        setChart('sim4', null, [], [], null);
        setTitles('车速 (m='+p.mass+'kg, μ='+p.friction+')', '制动减速度', '累计行驶距离', '');
        updateSummary(d);
        break;

    case 'speeds':
        r = await fetch('/api/simulate/speeds', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({brake_trigger_time:p.brakeT, dt:p.dt, mass:p.mass, friction:p.friction, speeds:[20,40,60,80,100,120]})});
        d = await r.json();
        const spR = sa(d, 'results'); lbl = spR[0].time.map(t=>parseFloat(t).toFixed(1));
        setMultiChart('sim1', spR, 'speed_kmh', 'initial_speed', 'km/h', lbl, COLORS);
        setMultiChart('sim2', spR, 'deceleration', 'initial_speed', 'km/h', lbl, COLORS);
        setBarChart('sim3', '刹车距离(m)', spR.map(r=>r.initial_speed+''), spR.map(r=>r.stopping_distance), COLORS[0]);
        setBarChart('sim4', '刹停时间(s)', spR.map(r=>r.initial_speed+''), spR.map(r=>r.stopping_time), '#3b82f6');
        setTitles('多速度制动 (m='+p.mass+'kg, μ='+p.friction+')', '减速度对比', '刹车距离 vs 初速', '刹停时间 vs 初速');
        updateSummary(spR[3]||spR[0]||{});
        break;

    case 'scenarios':
        r = await fetch('/api/simulate/scenarios?mass='+p.mass+'&friction='+p.friction+'&speed='+p.speed+'&brake_t='+p.brakeT);
        d = await r.json();
        const scn = sa(d, 'scenarios');
        lbl = sa(d, 'scenarios[0].time').map(t=>parseFloat(t).toFixed(1));
        setMultiChart('sim1', scn, 'speed_kmh', 'name', 'km/h', lbl, COLORS);
        setMultiChart('sim2', scn, 'deceleration', 'name', 'km/h', lbl, COLORS);
        const sc = sa(d, 'speed_compare');
        setBarChart('sim3', '刹车距离(m)', scn.map(function(s){return s.name}), scn.map(function(s){return s.stopping_distance}), '#ef4444');
        setMultiChart('sim4', sc, 'speed_kmh', 'initial_speed', 'km/h', sc[0].time.map(t=>parseFloat(t).toFixed(1)), COLORS);
        updateSummary(scn[2]||scn[0]||{});
        setTitles('环境场景:速度曲线('+p.speed+'km/h, m='+p.mass+'kg)', '环境场景:减速度曲线', '刹车距离对比', '多初速制动('+p.mass+'kg,μ='+p.friction+')');
        break;

    case 'distance':
        r = await fetch('/api/simulate/distance-analysis', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({mass:p.mass, friction:p.friction})});
        d = await r.json();
        const distR = sa(d, 'results');
        setBarChart('sim1', '刹车距离(m) vs 初速', distR.map(r=>r.initial_speed+''), distR.map(r=>r.stopping_distance), '#ef4444');
        setBarChart('sim2', '刹停时间(s) vs 初速', distR.map(r=>r.initial_speed+''), distR.map(r=>r.stopping_time), '#3b82f6');
        setChart('sim3', null, [], [], null);
        setChart('sim4', null, [], [], null);
        setTitles('刹车距离 vs 初速(m='+p.mass+'kg,μ='+p.friction+')', '刹停时间 vs 初速', '刹车距离 vs v²(理论d∝v²)', '');
        updateSummary(distR[5]||distR[0]||{});
        break;

    case 'decel':
        r = await fetch('/api/simulate/speeds', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({brake_trigger_time:p.brakeT, dt:p.dt, mass:p.mass, friction:p.friction, speeds:[30,50,70,90,110]})});
        d = await r.json();
        const decR = sa(d, 'results');
        lbl = decR[0].time.map(t=>parseFloat(t).toFixed(1));
        setMultiChart('sim1', decR, 'speed_kmh', 'initial_speed', 'km/h', lbl, COLORS);
        setMultiChart('sim2', decR, 'deceleration', 'initial_speed', 'km/h', lbl, COLORS);
        setBarChart('sim3', '峰值减速度(m/s²)', decR.map(r=>r.initial_speed+'km/h'), decR.map(r=>Math.max(...(r.deceleration||[0]))), '#f97316');
        setChart('sim4', null, [], [], null);
        setTitles('减速度分析:速度曲线(m='+p.mass+'kg,μ='+p.friction+')', '减速度曲线', '峰值减速度(μa_max='+(7.5*p.friction).toFixed(1)+')', '刹车距离');
        updateSummary(decR[2]||{});
        break;
    }
    if (modeLabel) modeLabel.textContent = mode;
    } catch(err) {
        console.error('[Sim]', mode, 'Error:', err.message, err);
        if (modeLabel) modeLabel.textContent = mode + ' 错误: ' + err.message;
    }
}

// 图表辅助函数
function setChart(key, label, data, labels, color) {
    const c = state.charts[key]; if (!c) { console.warn('[Sim] chart not found:', key); return; }
    c.config.type = 'line'; // 确保是折线图
    if (!label) { c.data.labels=[]; c.data.datasets=[]; c.update('none'); return; }
    c.data.labels = labels;
    c.data.datasets = [{label, data, borderColor:color, backgroundColor:color+'20', borderWidth:2, pointRadius:0, tension:0.3}];
    c.update('none');
}

function setMultiChart(key, results, dataField, labelField, unit, labels, colors) {
    const c = state.charts[key]; if (!c) return;
    c.data.labels = labels;
    c.data.datasets = results.map((r,i) => ({
        label: r[labelField] + ' ' + unit,
        data: r[dataField],
        borderColor: colors[i % colors.length],
        borderWidth: 2, pointRadius: 0, tension: 0.3,
    }));
    c.update('none');
}

function setBarChart(key, label, labels, data, color) {
    const c = state.charts[key]; if (!c) return;
    c.config.type = 'bar';
    c.data.labels = labels;
    c.data.datasets = [{label, data, backgroundColor:color+'60', borderColor:color, borderWidth:1}];
    c.update('none');
}

// ============================================================
// 车辆动画
// ============================================================
function updateCarAnim(msg) {
    const speed = (msg.vehicle_speed!=null) ? msg.vehicle_speed : 60;
    const ego = $('egoCar'); if (ego) ego.style.left = (10 + speed/120*30) + '%';
    const tgt = $('targetCar'); if (!tgt) return;
    const cars = (msg.detections||[]).filter(d=>d.class==='car'&&d.distance);
    const pos = cars.length ? Math.min(85, 40 + Math.min(...cars.map(c=>c.distance))*1.5) : 60;
    tgt.style.left = pos + '%';
    tgt.textContent = msg.braking ? '🚗💥' : '🚙';
}

// ============================================================
// 工具
// ============================================================
function fmtTime(sec) {
    const s = parseFloat(sec)||0;
    return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
}
function setBtn(id, display) {
    const el = $(id); if (el) el.style.display = display;
}

})();
