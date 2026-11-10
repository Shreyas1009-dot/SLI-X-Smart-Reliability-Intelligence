/**
 * dashboard.js - SLI-X Real-Time Dashboard Client
 * Fetches metrics, telemetry breakdown, and intelligent diagnoses every 1.5s.
 */

let activeDemoMode = 'normal';
let isTrafficActive = false;
let pollingInterval = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    fetchAndUpdateDashboard();
    pollingInterval = setInterval(fetchAndUpdateDashboard, 1500);
});

function initClock() {
    function updateClock() {
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        const clockEl = document.getElementById('live-clock');
        if (clockEl) clockEl.textContent = timeStr;
    }
    updateClock();
    setInterval(updateClock, 1000);
}

/**
 * Main polling orchestrator: fetches metrics, diagnosis, and history.
 */
async function fetchAndUpdateDashboard() {
    try {
        const [metricsRes, diagRes, historyRes] = await Promise.all([
            fetch('/api/metrics'),
            fetch('/api/diagnosis'),
            fetch('/api/history?limit=25')
        ]);

        if (metricsRes.ok) {
            const metricsData = await metricsRes.json();
            updateMetricsAndSLIs(metricsData);
        }

        if (diagRes.ok) {
            const diagData = await diagRes.json();
            updateDiagnosisHero(diagData);
        }

        if (historyRes.ok) {
            const historyData = await historyRes.json();
            updateRecentRequestsTable(historyData.requests || []);
        }
    } catch (err) {
        console.warn('Dashboard poll error (backend may be busy or reloading):', err);
    }
}

/**
 * Updates Infrastructure and SLI metric cards and breakdown bars.
 */
function updateMetricsAndSLIs(data) {
    const slis = data.slis || {};
    const infra = data.infrastructure || {};
    const compliance = slis.slo_compliance || {};

    // 1. Demo Mode & Traffic Sync
    if (data.active_demo_mode) {
        syncModeUI(data.active_demo_mode);
    }
    if (data.traffic_generator_active !== undefined) {
        syncTrafficUI(data.traffic_generator_active);
    }

    // 2. Host Infrastructure (psutil)
    const cpuPct = infra.cpu_usage_pct || 0;
    const memPct = infra.memory_usage_pct || 0;
    document.getElementById('infra-cpu-val').textContent = `${cpuPct.toFixed(1)}%`;
    document.getElementById('infra-cpu-bar').style.width = `${Math.min(cpuPct, 100)}%`;

    document.getElementById('infra-mem-val').textContent = `${memPct.toFixed(1)}%`;
    document.getElementById('infra-mem-bar').style.width = `${Math.min(memPct, 100)}%`;
    document.getElementById('infra-mem-detail').textContent = 
        `${infra.memory_used_mb || 0} MB / ${infra.memory_total_mb || 0} MB`;

    // 3. Core SLIs
    const availVal = slis.availability_pct !== undefined ? slis.availability_pct : 100.0;
    const p95Val = slis.p95_latency_ms !== undefined ? slis.p95_latency_ms : 0.0;
    const avgVal = slis.avg_latency_ms !== undefined ? slis.avg_latency_ms : 0.0;
    const p50Val = slis.p50_latency_ms !== undefined ? slis.p50_latency_ms : 0.0;
    const errVal = slis.error_rate_pct !== undefined ? slis.error_rate_pct : 0.0;
    const rpsVal = slis.requests_per_second !== undefined ? slis.requests_per_second : 0.0;
    const samplesVal = slis.sample_count !== undefined ? slis.sample_count : 0;

    document.getElementById('sli-availability').textContent = `${availVal.toFixed(1)}%`;
    document.getElementById('sli-p95').textContent = `${p95Val.toFixed(1)} ms`;
    document.getElementById('sli-avg-latency').textContent = `${avgVal.toFixed(1)} ms`;
    document.getElementById('sli-p50').textContent = `${p50Val.toFixed(1)} ms`;
    document.getElementById('sli-error-rate').textContent = `${errVal.toFixed(1)}%`;
    document.getElementById('sli-rps').textContent = `${rpsVal.toFixed(1)}`;
    document.getElementById('sli-samples').textContent = samplesVal;

    // Check SLO breaches & update visual card styling
    toggleBreachStyle('card-availability', !compliance.availability_compliant);
    toggleBreachStyle('card-p95', !compliance.p95_latency_compliant);
    toggleBreachStyle('card-error-rate', !compliance.error_rate_compliant);

    // 4. Request Breakdown (Timings & Stacked Visual Bar)
    const bMs = slis.breakdown_ms || { api_time_ms: 0, db_time_ms: 0, payment_time_ms: 0, total_latency_ms: 0 };
    const bPct = slis.breakdown_pct || { api_pct: 0, db_pct: 0, payment_pct: 0 };

    document.getElementById('breakdown-total-time').textContent = `${bMs.total_latency_ms.toFixed(1)} ms`;
    document.getElementById('time-api').textContent = bMs.api_time_ms.toFixed(1);
    document.getElementById('pct-api').textContent = `${bPct.api_pct.toFixed(1)}%`;

    document.getElementById('time-db').textContent = bMs.db_time_ms.toFixed(1);
    document.getElementById('pct-db').textContent = `${bPct.db_pct.toFixed(1)}%`;

    document.getElementById('time-payment').textContent = bMs.payment_time_ms.toFixed(1);
    document.getElementById('pct-payment').textContent = `${bPct.payment_pct.toFixed(1)}%`;

    // Adjust width of stacked bar
    document.getElementById('bar-seg-api').style.width = `${bPct.api_pct}%`;
    document.getElementById('bar-seg-db').style.width = `${bPct.db_pct}%`;
    document.getElementById('bar-seg-payment').style.width = `${bPct.payment_pct}%`;

    // Highlight dominant legend card
    const dbCard = document.getElementById('legend-db-card');
    const payCard = document.getElementById('legend-payment-card');
    dbCard.classList.toggle('dominant-stage', bPct.db_pct >= 50);
    payCard.classList.toggle('dominant-stage', bPct.payment_pct >= 50);
}

function toggleBreachStyle(cardId, isBreached) {
    const el = document.getElementById(cardId);
    if (el) {
        el.classList.toggle('sli-breached', isBreached);
    }
}

/**
 * Updates the Intelligent Diagnosis Hero Card.
 */
function updateDiagnosisHero(diag) {
    const heroCard = document.getElementById('diagnosis-card');
    const pill = document.getElementById('diag-status-pill');
    const banner = document.getElementById('diag-cause-banner');
    const causeEl = document.getElementById('diag-likely-cause');
    const compEl = document.getElementById('diag-affected-component');
    const expEl = document.getElementById('diag-explanation');
    const cpuRuleEl = document.getElementById('diag-cpu-assessment');
    const remedyList = document.getElementById('diag-remedy-list');

    const healthDot = document.getElementById('health-dot');
    const healthText = document.getElementById('health-text');

    const status = diag.status || 'UNKNOWN';
    pill.textContent = status;

    // Reset modifier classes
    heroCard.className = 'diagnosis-hero-card';
    banner.className = 'diagnosis-cause-banner';
    pill.className = 'diagnosis-status-pill';

    if (status === 'HEALTHY') {
        heroCard.classList.add('healthy');
        pill.classList.remove('pill-degraded', 'pill-critical');
        healthDot.className = 'status-dot healthy';
        healthText.textContent = 'SYSTEM OPTIMAL';
    } else if (status === 'DEGRADED') {
        pill.classList.add('pill-degraded');
        healthDot.className = 'status-dot degraded';
        healthText.textContent = 'SLO DEGRADED';

        if (diag.affected_component === 'Database') {
            heroCard.classList.add('degraded-db');
            banner.classList.add('banner-amber');
        } else if (diag.affected_component === 'Payment Gateway') {
            heroCard.classList.add('degraded-payment');
            banner.classList.add('banner-violet');
        }
    } else if (status === 'CRITICAL') {
        heroCard.classList.add('critical');
        banner.classList.add('banner-rose');
        pill.classList.add('pill-critical');
        healthDot.className = 'status-dot critical';
        healthText.textContent = 'SLO BREACHED';
    }

    causeEl.textContent = diag.likely_cause || 'Evaluating...';
    compEl.textContent = `Affected Component: ${diag.affected_component || 'None'}`;
    expEl.textContent = diag.explanation || '';
    cpuRuleEl.textContent = diag.cpu_assessment || 'Monitoring CPU...';

    // Populate recommendations
    remedyList.innerHTML = '';
    const fixes = diag.recommended_fix || [];
    fixes.forEach(fix => {
        const li = document.createElement('li');
        li.textContent = fix;
        remedyList.appendChild(li);
    });
}

/**
 * Updates the real-time request table stream.
 */
function updateRecentRequestsTable(requests) {
    const tbody = document.getElementById('requests-table-body');
    if (!requests || requests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No telemetry recorded yet. Click "Send Single Order" to test.</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    requests.forEach(r => {
        const tr = document.createElement('tr');
        const timeStr = new Date(r.timestamp * 1000).toTimeString().split(' ')[0];
        
        const isSlow = r.total_latency_ms > 200;
        const latencyClass = isSlow ? 'cell-latency-slow' : 'cell-latency-fast';
        const statusHtml = r.success 
            ? '<span class="status-tag tag-success">200 OK</span>'
            : `<span class="status-tag tag-failure" title="${r.error_message || 'Error'}">FAILED</span>`;

        let flagHtml = '<span class="flag-tag flag-normal">Normal</span>';
        if (r.db_time_ms > 1000) {
            flagHtml = '<span class="flag-tag flag-db">DB Bottleneck</span>';
        } else if (r.payment_time_ms > 1000) {
            flagHtml = '<span class="flag-tag flag-payment">Payment Delay</span>';
        }

        tr.innerHTML = `
            <td><code>${r.request_id}</code></td>
            <td>${timeStr}</td>
            <td class="${latencyClass}"><strong>${r.total_latency_ms.toFixed(1)} ms</strong></td>
            <td>${r.api_time_ms.toFixed(1)}</td>
            <td style="${r.db_time_ms > 500 ? 'color:#fbbf24;font-weight:bold' : ''}">${r.db_time_ms.toFixed(1)}</td>
            <td style="${r.payment_time_ms > 500 ? 'color:#c4b5fd;font-weight:bold' : ''}">${r.payment_time_ms.toFixed(1)}</td>
            <td>${statusHtml}</td>
            <td>${flagHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Fault Injection Mode Switcher.
 */
async function setDemoMode(mode) {
    try {
        const res = await fetch('/api/demo-mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });
        if (res.ok) {
            const data = await res.json();
            syncModeUI(data.active_demo_mode);
            // Immediately run a request to reflect the new mode right away
            await sendSingleRequest();
        }
    } catch (err) {
        console.error('Failed to set demo mode:', err);
    }
}

function resetToNormal() {
    setDemoMode('normal');
}

function syncModeUI(mode) {
    activeDemoMode = mode;
    const badge = document.getElementById('active-mode-name');
    if (badge) badge.textContent = mode.replace('_', ' ').toUpperCase();

    // Update active button styling
    document.getElementById('btn-mode-normal').classList.toggle('active', mode === 'normal');
    document.getElementById('btn-mode-slow-db').classList.toggle('active', mode === 'slow_database');
    document.getElementById('btn-mode-slow-pay').classList.toggle('active', mode === 'slow_payment');
}

/**
 * Triggers a single manual checkout request.
 */
async function sendSingleRequest() {
    const btn = document.getElementById('btn-send-single');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="icon">⏳</span> Processing...';
    btn.disabled = true;

    try {
        await fetch('/api/run-request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: 'SKU-PRO-LAPTOP', quantity: 1 })
        });
        await fetchAndUpdateDashboard();
    } catch (err) {
        console.error('Request failed:', err);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

/**
 * Toggles continuous background traffic generator.
 */
async function toggleLiveTraffic() {
    try {
        const res = await fetch('/api/traffic/toggle', { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            syncTrafficUI(data.traffic_generator_running);
        }
    } catch (err) {
        console.error('Failed to toggle traffic:', err);
    }
}

function syncTrafficUI(isRunning) {
    isTrafficActive = isRunning;
    const btn = document.getElementById('btn-toggle-traffic');
    const textEl = document.getElementById('traffic-btn-text');
    if (btn && textEl) {
        btn.classList.toggle('active', isRunning);
        textEl.textContent = isRunning ? 'Stop Live Traffic' : 'Start Live Traffic';
    }
}

