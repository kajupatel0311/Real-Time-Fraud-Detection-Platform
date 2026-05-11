/**
 * FraudSentinel - Production Dashboard Logic
 * Handles real-time transaction analysis, persistent state, and professional UI.
 */

'use strict';

const state = {
    transactions: [],
    isAnalyzing: false
};

// Automatically point to Render backend in production, or localhost in development
const BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:8000' 
    : 'https://real-time-fraud-detection-platform.onrender.com';

const dom = {
    chatContainer: document.getElementById('chat-container'),
    chatInput: document.getElementById('chat-input'),
    chatForm: document.getElementById('chat-form'),
    chatSubmit: document.getElementById('chat-submit'),
    resultSection: document.getElementById('result-section'),
    alertsList: document.getElementById('alerts-list'),
    recentTbody: document.getElementById('recent-tbody'),
    clock: document.getElementById('topbar-clock'),
    stats: {
        preds: document.getElementById('topbar-preds'),
        alerts: document.getElementById('alerts-count'),
        healthPreds: document.getElementById('health-preds'),
        activeAlerts: document.getElementById('alerts-count'),
        uptime: document.getElementById('health-uptime')
    }
};

const riskColors = {
    Low: '#10b981',
    Medium: '#f59e0b',
    High: '#ef4444'
};

/**
 * Updates the dashboard clock.
 */
function initializeClock() {
    function tick() {
        const now = new Date();
        dom.clock.textContent = now.toLocaleTimeString('en-US', { hour12: false }) +
                                ' ' + now.toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
    }
    tick();
    setInterval(tick, 1000);
}

/**
 * Appends a message to the security assistant chat.
 */
function addChatMessage(role, content) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}-message`;
    messageElement.innerHTML = content.replace(/\n/g, '<br>');
    dom.chatContainer.appendChild(messageElement);
    dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
}

/**
 * Handles the transaction analysis request.
 */
async function handleAnalysis(event) {
    event?.preventDefault();
    
    const message = dom.chatInput.value.trim();
    if (!message || state.isAnalyzing) return;

    addChatMessage('user', message);
    dom.chatInput.value = '';
    
    state.isAnalyzing = true;
    dom.chatSubmit.disabled = true;
    dom.chatSubmit.textContent = 'Analyzing...';

    try {
        const response = await fetch(`${BASE_URL}/chat_predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (!response.ok) throw new Error('Security engine communication failed');

        const data = await response.json();
        
        addChatMessage('bot', data.message);
        updateResultCard(data.prediction);
        
        // Refresh everything from backend to maintain single source of truth
        await refreshSystemStatus();
        await fetchHistory();

    } catch (error) {
        addChatMessage('bot', 'Network error or backend timeout. Please check your connection and try again.');
        console.error(error);
    } finally {
        state.isAnalyzing = false;
        dom.chatSubmit.disabled = false;
        dom.chatSubmit.textContent = 'Analyze';
    }
}

/**
 * Renders the analysis breakdown in the sidebar.
 */
function updateResultCard(prediction) {
    if (!prediction) return;

    // Use final_risk_score (normalized 0-100 via confidence_score)
    const riskScore = prediction.confidence_score;

    dom.resultSection.innerHTML = `
        <div class="result-display">
            <div class="risk-level risk-${prediction.risk_level}">${prediction.risk_level} Risk</div>
            <div class="prob-circle">${riskScore}%</div>
            <p style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700;">Behavioral Confidence</p>
            <div style="margin-top: 8px; font-size: 10px; font-weight: 800; color: ${prediction.scoring_mode === 'Hybrid' ? 'var(--accent)' : '#f59e0b'}; border: 1px solid currentColor; padding: 4px 8px; border-radius: 12px; display: inline-block;">
                ENGINE: ${prediction.scoring_mode.toUpperCase()}
            </div>
        </div>
        
        <div style="background-color: var(--bg-main); padding: 20px; border-radius: var(--radius); margin-bottom: 24px; border: 1px solid var(--border);">
            <p style="font-size: 10px; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; font-weight: 800; letter-spacing: 1px;">Recommended Action</p>
            <p style="font-weight: 700; color: var(--text-dark); font-size: 15px;">${prediction.action}</p>
        </div>

        <ul class="reasons-list" style="padding-left: 0;">
            ${prediction.reasons.map(reason => `
                <li style="list-style: none; padding: 12px 16px; background: var(--bg-main); border-radius: 8px; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--text-dark); border-left: 4px solid var(--accent);">
                    ${reason}
                </li>
            `).join('')}
        </ul>
    `;

    // Show behavioral breakdown indicators
    const breakdown = document.getElementById('analysis-breakdown');
    const summary = document.getElementById('pattern-summary');
    const indicators = document.getElementById('risk-indicators');
    
    if (breakdown && summary && indicators) {
        breakdown.style.display = 'block';
        summary.textContent = prediction.pattern_summary;
        indicators.innerHTML = prediction.indicators.map(ind => `
            <span style="font-size: 10px; background: var(--accent-soft); color: var(--accent); padding: 4px 12px; border-radius: 20px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">
                ${ind}
            </span>
        `).join('');
    }
}

/**
 * Fetches and renders the persistent audit trail.
 */
async function fetchHistory() {
    try {
        const response = await fetch(`${BASE_URL}/history`);
        const data = await response.json();
        state.transactions = data;
        renderTransactionTable();
    } catch (error) {
        console.error('Failed to fetch transaction history');
    }
}

function renderTransactionTable() {
    if (state.transactions.length === 0) {
        dom.recentTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 32px; color: var(--text-muted);">No transaction history available.</td></tr>';
        return;
    }

    dom.recentTbody.innerHTML = state.transactions.map(txn => {
        // Parse timestamp for clean display
        const timeStr = txn.timestamp.split('T')[1].split('Z')[0];
        // We might not have amount in PredictionResponse directly if fetched from history, 
        // but our updated DB schema and PredictionResponse model should align.
        // If not, we fall back to 0.
        const amount = txn.amount || 0;

        return `
            <tr>
                <td style="font-family: monospace; font-size: 13px; font-weight: 700; color: var(--text-dark);">${txn.transaction_id}</td>
                <td><span style="font-weight: 800; color: var(--text-dark);">₹${amount.toLocaleString()}</span></td>
                <td style="font-weight: 700;">${Math.round(txn.final_risk_score * 100)}%</td>
                <td><span class="risk-level risk-${txn.risk_level}">${txn.risk_level}</span></td>
                <td style="font-size: 13px; font-weight: 600;">${txn.action}</td>
                <td style="font-size: 12px; color: var(--text-muted); font-weight: 600;">${timeStr}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Refreshes system health and alert data.
 */
async function refreshSystemStatus() {
    try {
        const response = await fetch(`${BASE_URL}/health`);
        const data = await response.json();

        dom.stats.preds.textContent = data.total_predictions.toLocaleString();
        dom.stats.alerts.textContent = data.total_alerts.toLocaleString();
        dom.stats.healthPreds.textContent = data.total_predictions.toLocaleString();
        dom.stats.activeAlerts.textContent = data.total_alerts.toLocaleString();
        dom.stats.uptime.textContent = `${Math.floor(data.uptime_seconds / 60)}m`;

        const alertsResponse = await fetch(`${BASE_URL}/alerts`);
        const alertsData = await alertsResponse.json();
        renderAlertsList(alertsData);

    } catch (error) {
        // Silent fail for polling
    }
}

function renderAlertsList(alerts) {
    if (!alerts || alerts.length === 0) {
        dom.alertsList.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 24px;">No active high-risk alerts detected.</p>';
        return;
    }

    dom.alertsList.innerHTML = alerts.map(alert => `
        <div class="alert-item" style="border: 1px solid var(--border); background: #fff; padding: 20px; border-radius: var(--radius); margin-bottom: 12px; border-left: 4px solid var(--danger);">
            <div class="alert-header" style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <span class="alert-title" style="color: var(--danger); font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">High Risk Alert</span>
                <span class="alert-meta" style="color: var(--text-muted); font-size: 11px; font-weight: 600;">${alert.timestamp.split('T')[1].split('Z')[0]}</span>
            </div>
            <div style="font-weight: 800; color: var(--text-dark); font-size: 15px; margin-bottom: 6px;">₹${alert.amount.toLocaleString()} - ${alert.transaction_id}</div>
            <div style="font-size: 13px; color: var(--text-main); font-weight: 500;">${alert.reasons[0] || 'Multiple risk factors identified'}</div>
        </div>
    `).join('');
}

/**
 * Initialization.
 */
function init() {
    initializeClock();
    
    dom.chatForm?.addEventListener('submit', handleAnalysis);
    
    // Preset handler - Now only populates input as requested
    document.querySelectorAll('[data-chat-preset]').forEach(button => {
        button.addEventListener('click', () => {
            const type = button.dataset.chatPreset;
            if (type === 'high') {
                dom.chatInput.value = "URGENT: Emptying my account balance. Transferring 850,000 from C5551234 to merchant M1112223 immediately.";
            } else if (type === 'low') {
                dom.chatInput.value = "Transfer 500 to recipient M123 from C456. Available balance is 10,000.";
            } else {
                dom.chatInput.value = "Sent 50,000 to C888 from C456. Several similar transfers today.";
            }
            // handleAnalysis(); // REMOVED: Deterministic behavior - user must click analyze
            dom.chatInput.focus();
        });
    });

    // Load initial data
    refreshSystemStatus();
    fetchHistory();
    
    // Polling for health/alerts
    setInterval(refreshSystemStatus, 15000);
}

document.addEventListener('DOMContentLoaded', init);
