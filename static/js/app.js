/**
 * Trail Running AI Assistant - Frontend Application
 * Desktop-only optimized, communicates with Flask backend API.
 */
class TrailApp {
    constructor() {
        this.apiBase = '/api';
        this.map = null;
        this.currentData = null;
        this.currentTab = 'route';
        this.charts = {};
        this.chatHistory = [];
        this.init();
    }

    init() {
        this.initMap();
        this.initNav();
        this.initEventListeners();
        this.loadHistory();
    }

    // ==================== MAP ====================
    initMap() {
        this.map = L.map('map').setView([39.9042, 116.4074], 10);

        // Use CartoDB Voyager as default (colorful, good for trails)
        this.baseLayers = {
            '彩色地图': L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; CartoDB',
                maxZoom: 19
            }),
            'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap'
            }),
            '地形图': L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenTopoMap',
                maxZoom: 17
            }),
            '卫星图': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '&copy; Esri'
            })
        };

        this.baseLayers['彩色地图'].addTo(this.map);

        // Add layer control
        L.control.layers(this.baseLayers, null, {
            position: 'topright',
            collapsed: true
        }).addTo(this.map);

        // Add drag-and-drop support
        this.initMapDragDrop();
    }

    initMapDragDrop() {
        const mapContainer = document.getElementById('map');
        const dropHint = document.getElementById('map-drop-hint');
        if (!mapContainer) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            mapContainer.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        mapContainer.addEventListener('dragenter', () => {
            if (dropHint) dropHint.classList.remove('hidden');
        });

        mapContainer.addEventListener('dragleave', () => {
            if (dropHint) dropHint.classList.add('hidden');
        });

        mapContainer.addEventListener('drop', (e) => {
            if (dropHint) dropHint.classList.add('hidden');
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].name.endsWith('.gpx')) {
                this.uploadGPX(files[0]);
            } else {
                this.showError('请拖入 .gpx 文件');
            }
        });
    }

    // ==================== NAVIGATION ====================
    initNav() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
            });
        });
    }

    switchTab(tab) {
        // Update nav buttons
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelector(`.nav-btn[data-tab="${tab}"]`)?.classList.add('active');
        
        // Update tab pages
        document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
        const tabEl = document.getElementById(`tab-${tab}`);
        if (tabEl) tabEl.classList.add('active');
        
        this.currentTab = tab;
        
        // Resize map if route tab
        if (tab === 'route' && this.map) {
            setTimeout(() => this.map.invalidateSize(), 100);
        }
        
        // Load tab-specific data
        if (tab === 'eco') {
            this.loadGreenEco();
        }
    }

    // ==================== EVENT LISTENERS ====================
    initEventListeners() {
        // GPX file upload
        const gpxInput = document.getElementById('gpx-input');
        if (gpxInput) {
            gpxInput.addEventListener('change', (e) => {
                if (e.target.files[0]) this.uploadGPX(e.target.files[0]);
            });
        }
        
        // Demo route
        const demoBtn = document.getElementById('load-demo');
        if (demoBtn) {
            demoBtn.addEventListener('click', () => this.loadDemoRoute());
        }
        
        // Generate training plan
        const planBtn = document.getElementById('btn-gen-plan');
        if (planBtn) {
            planBtn.addEventListener('click', () => this.generatePlan());
        }
        
        // AI Chat
        const chatBtn = document.getElementById('btn-chat-send');
        const chatInput = document.getElementById('chat-input');
        if (chatBtn) {
            chatBtn.addEventListener('click', () => this.sendChatMessage());
        }
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendChatMessage();
            });
        }
        
        // Clear history
        const clearHistoryBtn = document.getElementById('btn-clear-history');
        if (clearHistoryBtn) {
            clearHistoryBtn.addEventListener('click', () => this.clearHistory());
        }
    }

    // ==================== GPX UPLOAD & ANALYSIS ====================
    async uploadGPX(file) {
        this.showLoading('正在解析GPX并运行动态分段算法...');
        
        const form = new FormData();
        form.append('file', file);
        
        try {
            const res = await fetch(`${this.apiBase}/analyze`, {
                method: 'POST',
                body: form
            });
            const data = await res.json();
            
            if (!data.success) throw new Error(data.error || '分析失败');
            
            this.currentData = data;
            this.renderAll(data);
            this.switchTab('route');
            
        } catch (e) {
            this.showError('分析失败: ' + e.message);
        } finally {
            this.hideLoading();
        }
    }

    async loadDemoRoute() {
        this.showLoading('正在生成示例路线...');
        
        try {
            const res = await fetch(`${this.apiBase}/demo-route`);
            const data = await res.json();
            
            if (!data.success) throw new Error(data.error || '生成失败');
            
            this.currentData = data;
            this.renderAll(data);
            this.switchTab('route');
            
        } catch (e) {
            this.showError('示例路线加载失败: ' + e.message);
        } finally {
            this.hideLoading();
        }
    }

    // ==================== RENDER ALL ====================
    renderAll(data) {
        // Update status
        document.getElementById('sidebar-status').textContent = 
            `${data.metrics.total_distance_km}km 已分析`;
        
        // Render route analysis tab
        this.renderMetrics(data.metrics);
        this.renderMap(data.points);
        this.renderElevationChart(data.points);
        this.renderGradeChart(data.segments);
        this.renderRisks(data.risks);
        
        // Render AI strategy tab
        this.renderStrategy(data.strategy);
        this.renderStatePredictions(data.state_predictions);
        this.renderRouteSummary(data.route_summary);
    }

    renderMetrics(metrics) {
        document.getElementById('m-dist').textContent = metrics.total_distance_km;
        document.getElementById('m-ascent').textContent = metrics.total_ascent_m;
        document.getElementById('m-descent').textContent = metrics.total_descent_m;
        document.getElementById('m-maxele').textContent = metrics.max_elevation_m;
        document.getElementById('m-minele').textContent = metrics.min_elevation_m;
        document.getElementById('m-avggrad').textContent = metrics.avg_gradient + '%';
    }

    renderMap(points) {
        if (!points || points.length < 2) return;
        
        // Clear existing layers
        this.map.eachLayer(l => {
            if (l instanceof L.Polyline || l instanceof L.Marker || l instanceof L.CircleMarker) {
                this.map.removeLayer(l);
            }
        });
        
        // Re-add base layer
        let hasBase = false;
        this.map.eachLayer(l => {
            if (l instanceof L.TileLayer) hasBase = true;
        });
        if (!hasBase) this.baseLayers['地形图'].addTo(this.map);
        
        const latlngs = points.map(p => [p.lat, p.lon]);
        
        // Draw route line with gradient color based on elevation
        L.polyline(latlngs, { color: '#e11d48', weight: 4, opacity: 0.85 }).addTo(this.map);
        
        // Start marker
        L.marker(latlngs[0], {
            icon: L.divIcon({
                html: '<div style="width:26px;height:26px;background:#22c55e;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;font-weight:bold;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">S</div>',
                className: '', iconSize: [26, 26]
            })
        }).addTo(this.map).bindPopup('<b>起点</b>');
        
        // End marker
        L.marker(latlngs[latlngs.length - 1], {
            icon: L.divIcon({
                html: '<div style="width:26px;height:26px;background:#ef4444;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;font-weight:bold;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">E</div>',
                className: '', iconSize: [26, 26]
            })
        }).addTo(this.map).bindPopup('<b>终点</b>');
        
        // Fit bounds
        this.map.fitBounds(L.latLngBounds(latlngs), { padding: [40, 40] });
    }

    renderElevationChart(points) {
        const container = document.getElementById('ele-chart');
        if (!container) return;
        
        // Dispose existing chart
        if (this.charts.elevation) {
            this.charts.elevation.dispose();
        }
        
        const chart = echarts.init(container);
        this.charts.elevation = chart;
        
        const data = points.map((p, i) => [i, p.ele]);
        
        chart.setOption({
            backgroundColor: 'transparent',
            grid: { left: 45, right: 15, top: 15, bottom: 25 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: '#e11d48',
                textStyle: { color: '#fff', fontSize: 12 },
                formatter: (params) => {
                    const p = params[0];
                    return `点 ${p.dataIndex}<br/>海拔: ${p.value}m`;
                }
            },
            xAxis: { 
                type: 'category', 
                show: false,
                data: points.map((_, i) => i)
            },
            yAxis: { 
                type: 'value', 
                splitLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8', fontSize: 11 },
                name: 'm',
                nameTextStyle: { color: '#64748b', fontSize: 10 }
            },
            series: [{
                data: points.map(p => p.ele),
                type: 'line', 
                smooth: true,
                symbol: 'none',
                lineStyle: { color: '#e11d48', width: 2 },
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(225,29,72,0.25)' }, 
                            { offset: 1, color: 'rgba(225,29,72,0)' }
                        ]
                    }
                }
            }]
        });
        
        window.addEventListener('resize', () => chart.resize());
    }

    renderGradeChart(segments) {
        const container = document.getElementById('grade-chart');
        if (!container || !segments) return;

        if (this.charts.grade) {
            this.charts.grade.dispose();
        }

        const chart = echarts.init(container);
        this.charts.grade = chart;

        // Color mapping based on terrain type
        const colors = segments.map(s => {
            if (s.terrain_type.includes('steep')) return '#ef4444';
            if (s.terrain_type === 'flat') return '#22c55e';
            return '#eab308';
        });

        // If too many segments, hide x-axis labels to prevent crowding
        const showLabels = segments.length <= 20;

        chart.setOption({
            backgroundColor: 'transparent',
            grid: { left: 45, right: 15, top: 15, bottom: showLabels ? 35 : 15 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: '#475569',
                textStyle: { color: '#fff', fontSize: 12 },
                formatter: (params) => {
                    const p = params[0];
                    const seg = segments[p.dataIndex];
                    return `${seg.start}-${seg.end}km<br/>类型: ${this.terrainTypeLabel(seg.terrain_type)}<br/>坡度: ${p.value}%`;
                }
            },
            xAxis: {
                type: 'category',
                data: segments.map(s => `${s.start}-${s.end}km`),
                axisLabel: showLabels
                    ? { color: '#94a3b8', fontSize: 9, rotate: 35 }
                    : { show: false },
                axisLine: { lineStyle: { color: '#334155' } }
            },
            yAxis: {
                type: 'value',
                name: '%',
                nameTextStyle: { color: '#64748b', fontSize: 10 },
                splitLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8', fontSize: 11 }
            },
            series: [{
                data: segments.map((s, i) => ({
                    value: s.avg_grade,
                    itemStyle: { color: colors[i] }
                })),
                type: 'bar',
                barWidth: segments.length > 40 ? '40%' : '70%',
                label: {
                    show: segments.length <= 15,
                    position: 'top',
                    color: '#94a3b8',
                    fontSize: 9,
                    formatter: (p) => p.value > 0 ? `+${p.value}%` : `${p.value}%`
                }
            }]
        });

        window.addEventListener('resize', () => chart.resize());
    }

    renderRisks(risks) {
        const container = document.getElementById('risk-list');
        const countEl = document.getElementById('risk-count');
        
        if (!container || !countEl) return;
        
        countEl.textContent = `${risks.length} 条`;
        
        if (risks.length === 0) {
            container.innerHTML = `
                <div class="text-center py-6">
                    <i class="fas fa-check-circle text-green-500 text-3xl mb-2"></i>
                    <p class="text-sm text-slate-400">路线平缓，无显著风险</p>
                </div>`;
            return;
        }
        
        container.innerHTML = risks.map(r => `
            <div class="risk-card risk-${r.level}">
                <div class="flex justify-between items-start mb-1">
                    <span class="font-medium text-sm text-slate-200">${r.start}km - ${r.end}km</span>
                    <span class="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                        ${this.riskTypeLabel(r.type)}
                    </span>
                </div>
                <div class="text-xs text-slate-400 mb-1">${r.desc}</div>
                <div class="text-xs ${r.level === 'high' ? 'text-red-400' : 'text-yellow-400'}">
                    <i class="fas fa-exclamation-triangle mr-1"></i>${r.suggest}
                </div>
            </div>
        `).join('');
    }

    renderStrategy(strategy) {
        const tbody = document.getElementById('strategy-body');
        if (!tbody || !strategy) return;

        // Highlight pace with background for emphasis
        tbody.innerHTML = strategy.map(s => `
            <tr>
                <td class="font-medium text-slate-200">${s.segment}</td>
                <td class="text-slate-400">${s.type}</td>
                <td class="${s.grade > 5 ? 'text-red-400' : s.grade > 2 ? 'text-yellow-400' : 'text-green-400'}">
                    ${s.grade > 0 ? '+' : ''}${s.grade}%
                </td>
                <td><span class="inline-block bg-rose-500/20 text-rose-400 font-bold px-2 py-0.5 rounded text-sm">${s.pace}</span></td>
                <td class="text-xs">${s.state_warning || '<span class="text-green-500"><i class="fas fa-check-circle mr-1"></i>正常</span>'}</td>
            </tr>
        `).join('');

        // Update strategy header with segment count
        const strategyHeader = document.getElementById('strategy-header');
        if (strategyHeader) {
            strategyHeader.textContent = `共 ${strategy.length} 个分段`;
        }
    }

    renderStatePredictions(predictions) {
        const container = document.getElementById('state-preview');
        if (!container || !predictions) return;

        // Always show all predictions with their state values, not just warnings
        container.innerHTML = predictions.map(w => {
            const mColor = w.predicted_M < 40 ? 'text-red-400' : w.predicted_M < 60 ? 'text-yellow-400' : 'text-green-400';
            const cColor = w.predicted_C > 80 ? 'text-red-400' : w.predicted_C > 70 ? 'text-yellow-400' : 'text-green-400';
            const gColor = w.predicted_G < 100 ? 'text-red-400' : w.predicted_G < 200 ? 'text-yellow-400' : 'text-green-400';
            const hasWarning = w.warning && w.warning.length > 0;
            const borderColor = hasWarning
                ? (w.warning.includes('严重') || w.warning.includes('过高') || w.warning.includes('不足') ? 'border-red-500' : 'border-yellow-500')
                : 'border-green-500/30';

            return `
            <div class="bg-slate-700/50 rounded p-3 text-xs border-l-2 ${borderColor}">
                <div class="flex justify-between items-center mb-1">
                    <span class="font-medium text-slate-300">${w.segment}</span>
                    <span class="text-slate-500">${w.estimated_pace} / ${w.estimated_hr}bpm</span>
                </div>
                <div class="flex gap-3 text-slate-500">
                    <span>M:<span class="${mColor} font-medium">${w.predicted_M}</span></span>
                    <span>C:<span class="${cColor} font-medium">${w.predicted_C}</span></span>
                    <span>G:<span class="${gColor} font-medium">${w.predicted_G}g</span></span>
                </div>
                ${hasWarning ? `<div class="mt-1 ${w.warning.includes('严重') || w.warning.includes('过高') ? 'text-red-400' : 'text-yellow-400'}">${w.warning}</div>` : ''}
            </div>
        `}).join('');
    }

    renderRouteSummary(summary) {
        if (!summary) return;

        // Danger points
        const dangerCount = document.getElementById('summary-danger-count');
        const dangerList = document.getElementById('summary-danger-list');
        if (dangerCount) dangerCount.textContent = summary.danger_count + ' 处';
        if (dangerList) {
            if (summary.danger_points && summary.danger_points.length > 0) {
                dangerList.innerHTML = summary.danger_points.map(d =>
                    `<div class="text-slate-400"><span class="text-slate-500">${d.start}-${d.end}km</span> ${d.reason}</div>`
                ).join('');
            } else {
                dangerList.innerHTML = '<span class="text-green-500"><i class="fas fa-check-circle mr-1"></i>无显著危险路段</span>';
            }
        }

        // Scramble sections
        const scrambleCount = document.getElementById('summary-scramble-count');
        const scrambleList = document.getElementById('summary-scramble-list');
        if (scrambleCount) scrambleCount.textContent = summary.scramble_count + ' 处';
        if (scrambleList) {
            if (summary.scramble_sections && summary.scramble_sections.length > 0) {
                scrambleList.innerHTML = summary.scramble_sections.map(s =>
                    `<div class="text-slate-400"><span class="text-slate-500">${s.start}-${s.end}km</span> 爬升${s.grade.toFixed(0)}%</div>`
                ).join('');
            } else {
                scrambleList.innerHTML = '<span class="text-slate-600">无需攀爬路段</span>';
            }
        }

        // Speed-up points
        const speedupCount = document.getElementById('summary-speedup-count');
        const speedupList = document.getElementById('summary-speedup-list');
        if (speedupCount) speedupCount.textContent = summary.speedup_count + ' 处';
        if (speedupList) {
            if (summary.speedup_points && summary.speedup_points.length > 0) {
                // Show first 5 to avoid overflow
                const points = summary.speedup_points.slice(0, 5);
                speedupList.innerHTML = points.map(s =>
                    `<div class="text-slate-400"><span class="text-slate-500">${s.start}-${s.end}km</span> ${s.type} ${s.grade > 0 ? '+' : ''}${s.grade.toFixed(0)}%</div>`
                ).join('');
                if (summary.speedup_points.length > 5) {
                    speedupList.innerHTML += `<div class="text-slate-600">...还有 ${summary.speedup_points.length - 5} 处</div>`;
                }
            } else {
                speedupList.innerHTML = '<span class="text-slate-600">无可提速路段</span>';
            }
        }
    }

    // ==================== TRAINING PLAN ====================
    async generatePlan() {
        const btn = document.getElementById('btn-gen-plan');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>生成中...';
        btn.disabled = true;
        
        const params = {
            level: document.getElementById('plan-level').value,
            target_distance: parseInt(document.getElementById('plan-target').value),
            weeks: parseInt(document.getElementById('plan-weeks').value) || 12,
            weekly_distance: parseInt(document.getElementById('plan-weekly').value) || 40
        };
        
        try {
            const res = await fetch(`${this.apiBase}/ai/plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });
            
            const data = await res.json();
            
            if (!data.success) throw new Error(data.error || '生成失败');
            
            this.renderPlan(data.plan, data.source);
            
        } catch (e) {
            this.showError('训练计划生成失败: ' + e.message);
        } finally {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    }

    renderPlan(plan, source) {
        const container = document.getElementById('plan-container');
        if (!container || !plan) return;
        
        const badge = source === 'ai' 
            ? '<span class="source-badge ai"><i class="fas fa-robot mr-1"></i>Kimi AI</span>'
            : '<span class="source-badge local"><i class="fas fa-bolt mr-1"></i>本地算法</span>';
        
        const noteHtml = plan.note 
            ? `<div class="text-xs text-yellow-400 mt-2"><i class="fas fa-info-circle mr-1"></i>${plan.note}</div>` 
            : '';
        
        container.innerHTML = `
            <div class="mb-4 flex items-center justify-between">
                <div>
                    <h3 class="font-bold text-lg text-white">${plan.plan_name}</h3>
                    <div class="text-sm text-slate-400 mt-1">
                        ${plan.duration_weeks}周 | 目标${plan.target_distance}km
                    </div>
                    ${noteHtml}
                </div>
                ${badge}
            </div>
            <div class="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
                ${plan.weekly_schedule.map(w => `
                    <div class="plan-week rounded-lg p-3 bg-slate-800/50">
                        <div class="flex justify-between items-center mb-2">
                            <span class="font-medium text-white text-sm">第${w.week}周 - ${w.phase}</span>
                            <span class="text-xs text-slate-400">${w.total_distance_km}km</span>
                        </div>
                        <div class="text-xs text-slate-500 mb-2">${w.focus}</div>
                        <div class="grid grid-cols-7 gap-1">
                            ${w.workouts.map(d => `
                                <div class="workout-day ${d.type === '休息' || d.type === '休息/拉伸' ? 'opacity-50' : ''}">
                                    <div class="text-slate-500 text-xs">${d.day}</div>
                                    <div class="text-white font-medium text-xs mt-1 ${d.type === '长跑' ? 'text-rose-400' : d.type.includes('间歇') ? 'text-yellow-400' : ''}">${d.type}</div>
                                    <div class="text-slate-500 mt-1 text-xs leading-t">${d.description}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // ==================== AI CHAT ====================
    async sendChatMessage() {
        const input = document.getElementById('chat-input');
        const container = document.getElementById('chat-messages');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user mb-3';
        userMsg.textContent = message;
        container.appendChild(userMsg);
        
        input.value = '';
        container.scrollTop = container.scrollHeight;
        
        // Show loading
        const loadingId = 'chat-loading-' + Date.now();
        const loadingMsg = document.createElement('div');
        loadingMsg.id = loadingId;
        loadingMsg.className = 'chat-message ai mb-3';
        loadingMsg.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 思考中...';
        container.appendChild(loadingMsg);
        container.scrollTop = container.scrollHeight;
        
        try {
            const res = await fetch(`${this.apiBase}/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    context: { history: this.chatHistory.slice(-8) }
                })
            });
            
            const data = await res.json();
            
            // Remove loading
            document.getElementById(loadingId)?.remove();
            
            // Add AI response
            const aiMsg = document.createElement('div');
            aiMsg.className = 'chat-message ai mb-3';
            aiMsg.innerHTML = data.reply || '抱歉，暂时无法回答。';
            container.appendChild(aiMsg);
            
            // Update history
            this.chatHistory.push(
                { role: 'user', content: message },
                { role: 'assistant', content: data.reply || '' }
            );
            
        } catch (e) {
            document.getElementById(loadingId)?.remove();
            
            const errorMsg = document.createElement('div');
            errorMsg.className = 'chat-message ai mb-3 text-yellow-400';
            errorMsg.innerHTML = '<i class="fas fa-exclamation-circle mr-1"></i>AI服务暂时不可用，请稍后再试。';
            container.appendChild(errorMsg);
        }
        
        container.scrollTop = container.scrollHeight;
    }

    // ==================== HISTORY ====================
    async loadHistory() {
        try {
            const res = await fetch(`${this.apiBase}/history`);
            const data = await res.json();
            
            if (data.success) {
                this.renderHistory(data.records);
            }
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    }

    renderHistory(records) {
        const container = document.getElementById('history-list');
        if (!container) return;
        
        if (!records || records.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-slate-500">
                    <i class="fas fa-history text-3xl mb-3 opacity-30"></i>
                    <p class="text-sm">暂无历史记录</p>
                </div>`;
            return;
        }
        
        container.innerHTML = records.map(r => {
            const date = new Date(r.date);
            const dateStr = `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2,'0')}`;
            
            return `
                <div class="history-item mb-2">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <i class="fas ${r.type === 'route' ? 'fa-map-signs' : 'fa-dumbbell'} text-slate-500"></i>
                            <div>
                                <div class="text-sm text-white font-medium">${r.name}</div>
                                <div class="text-xs text-slate-500">${dateStr}</div>
                            </div>
                        </div>
                        <div class="text-xs text-slate-400">
                            ${r.distance ? r.distance + 'km' : ''}
                            ${r.ascent ? ' / ' + r.ascent + 'm' : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    async clearHistory() {
        if (!confirm('确定要清空所有历史记录吗？')) return;
        
        try {
            await fetch(`${this.apiBase}/history/clear`, { method: 'POST' });
            this.loadHistory();
        } catch (e) {
            this.showError('清空失败: ' + e.message);
        }
    }

    // ==================== GREEN ECO ====================
    async loadGreenEco() {
        try {
            const res = await fetch(`${this.apiBase}/green-eco`);
            const data = await res.json();
            
            if (data.success) {
                this.renderGreenEco(data.data);
            }
        } catch (e) {
            console.error('Failed to load green eco data:', e);
        }
    }

    renderGreenEco(data) {
        document.getElementById('eco-runs').textContent = data.total_runs;
        document.getElementById('eco-distance').textContent = data.total_distance.toFixed(1);
        document.getElementById('eco-carbon').textContent = data.carbon_saved.toFixed(1);
        document.getElementById('eco-points').textContent = data.green_points;
        document.getElementById('eco-level').textContent = data.level;
        document.getElementById('eco-progress').style.width = data.level_progress + '%';
        
        // Render carbon chart
        this.renderCarbonChart(data.monthly_data);
    }

    renderCarbonChart(monthlyData) {
        const container = document.getElementById('carbon-chart');
        if (!container || !monthlyData) return;
        
        if (this.charts.carbon) {
            this.charts.carbon.dispose();
        }
        
        const chart = echarts.init(container);
        this.charts.carbon = chart;
        
        chart.setOption({
            backgroundColor: 'transparent',
            grid: { left: 45, right: 15, top: 15, bottom: 30 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: '#22c55e',
                textStyle: { color: '#fff', fontSize: 12 },
                formatter: '{b}: 减少 {c} kg CO₂'
            },
            xAxis: {
                type: 'category',
                data: monthlyData.map(d => d.month),
                axisLabel: { color: '#94a3b8', fontSize: 11 },
                axisLine: { lineStyle: { color: '#334155' } }
            },
            yAxis: {
                type: 'value',
                name: 'kg',
                nameTextStyle: { color: '#64748b', fontSize: 10 },
                splitLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8', fontSize: 11 }
            },
            series: [{
                data: monthlyData.map(d => d.carbon),
                type: 'line',
                smooth: true,
                symbol: 'circle',
                symbolSize: 8,
                lineStyle: { color: '#22c55e', width: 3 },
                itemStyle: { color: '#22c55e', borderColor: '#fff', borderWidth: 2 },
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(34,197,94,0.3)' },
                            { offset: 1, color: 'rgba(34,197,94,0.02)' }
                        ]
                    }
                }
            }]
        });
        
        window.addEventListener('resize', () => chart.resize());
    }

    // ==================== EQUIPMENT ====================
    async loadEquipment() {
        if (!this.currentData) {
            document.getElementById('equip-content').innerHTML = `
                <div class="text-center py-12 text-slate-500">
                    <i class="fas fa-hiking text-3xl mb-3 opacity-30"></i>
                    <p class="text-sm">请先分析路线，获取装备推荐</p>
                </div>`;
            return;
        }
        
        this.showLoading('正在获取装备推荐...');
        
        try {
            const res = await fetch(`${this.apiBase}/ai/equipment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ metrics: this.currentData.metrics })
            });
            
            const data = await res.json();
            
            if (data.success) {
                this.renderEquipment(data.advice);
            } else {
                this.renderEquipment(this.getDefaultEquipment());
            }
        } catch (e) {
            this.renderEquipment(this.getDefaultEquipment());
        } finally {
            this.hideLoading();
        }
    }

    renderEquipment(advice) {
        const container = document.getElementById('equip-content');
        if (!container) return;
        
        container.innerHTML = `
            <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="equip-card">
                    <h4 class="font-medium text-white mb-2"><i class="fas fa-shoe-prints text-rose-400 mr-2"></i>${advice.shoes.name}</h4>
                    <div class="flex flex-wrap gap-1 mb-2">
                        ${advice.shoes.features.map(f => `<span class="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-300">${f}</span>`).join('')}
                    </div>
                    <p class="text-xs text-slate-400">${advice.shoes.reason}</p>
                </div>
                <div class="equip-card">
                    <h4 class="font-medium text-white mb-2"><i class="fas fa-tshirt text-rose-400 mr-2"></i>服装</h4>
                    <p class="text-sm text-slate-300">上衣: ${advice.clothing.top}</p>
                    <p class="text-sm text-slate-300">下装: ${advice.clothing.bottom}</p>
                    <p class="text-xs text-slate-400 mt-2">${advice.clothing.reason}</p>
                </div>
            </div>
            <div class="grid grid-cols-2 gap-4 mb-4">
                ${advice.gear.map(g => `
                    <div class="equip-card">
                        <div class="flex justify-between items-start">
                            <h4 class="font-medium text-white">${g.item}</h4>
                            <span class="priority-${g.priority}">${g.priority === 'essential' ? '必备' : '推荐'}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-1">${g.reason}</p>
                    </div>
                `).join('')}
            </div>
            <div class="equip-card">
                <h4 class="font-medium text-white mb-2"><i class="fas fa-utensils text-rose-400 mr-2"></i>补给建议</h4>
                <div class="grid grid-cols-2 gap-2">
                    ${advice.nutrition.map(n => `
                        <div class="text-xs">
                            <span class="text-slate-300 font-medium">${n.item}</span>
                            <span class="text-slate-500"> - ${n.timing}, ${n.amount}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    getDefaultEquipment() {
        return {
            shoes: { name: '专业越野跑鞋', features: ['Vibram大底', '防水面料', '4mm落差'], reason: '提供良好抓地力和足部保护' },
            clothing: { top: '速干长袖', bottom: '轻量越野短裤', reason: '适应多变天气，快速排汗' },
            gear: [
                { item: '水袋背包', priority: 'essential', reason: '长距离补水必备' },
                { item: '登山杖', priority: 'recommended', reason: '爬升路段省力' },
                { item: '头灯', priority: 'essential', reason: '安全装备' },
                { item: '急救包', priority: 'essential', reason: '应急处理' }
            ],
            nutrition: [
                { item: '能量胶', timing: '每45-60分钟', amount: '1支' },
                { item: '电解质饮料', timing: '全程', amount: '500ml/小时' }
            ]
        };
    }

    // ==================== HELPERS ====================
    terrainTypeLabel(type) {
        const labels = {
            'flat': '平路',
            'rolling': '起伏',
            'climb': '上坡',
            'steep_climb': '陡坡爬升',
            'descent': '下坡',
            'steep_descent': '陡坡下降'
        };
        return labels[type] || type;
    }

    riskTypeLabel(type) {
        const labels = {
            'steep_climb': '陡坡爬升',
            'steep_descent': '陡坡下降',
            'climb': '上坡',
            'descent': '下坡'
        };
        return labels[type] || type;
    }

    showLoading(text) {
        const el = document.getElementById('loading-overlay');
        const txt = document.getElementById('loading-text');
        if (el) el.classList.remove('hidden');
        if (txt) txt.textContent = text || '加载中...';
    }

    hideLoading() {
        const el = document.getElementById('loading-overlay');
        if (el) el.classList.add('hidden');
    }

    showError(msg) {
        alert(msg);
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TrailApp();
});
