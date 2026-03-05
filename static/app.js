/* ═══════════════════════════════════════════════════════════════
   FinWell — Frontend Application Logic
   Chat handling, API calls, page transitions, message rendering
   ═══════════════════════════════════════════════════════════════ */

// ── Page Navigation ─────────────────────────────────────────────

function showDashboard() {
    document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
    document.getElementById('dashboard').classList.add('active');
    setActivePill('dashboard');
}

function showChat(agent) {
    document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
    document.getElementById(`${agent}-page`).classList.add('active');
    setActivePill(agent);
    // Focus input
    setTimeout(() => {
        const input = document.getElementById(`${agent}-input`);
        if (input) input.focus();
    }, 400);
}

function setActivePill(page) {
    document.querySelectorAll('.nav-pill').forEach(p => p.classList.remove('active'));
    const pill = document.querySelector(`.nav-pill[data-page="${page}"]`);
    if (pill) pill.classList.add('active');
}

// ── Message Rendering ───────────────────────────────────────────

function addMessage(agent, text, isUser = false) {
    const container = document.getElementById(`${agent}-messages`);
    const icons = { health: '\u2695', stocks: '\u2197', crypto: '\u26A1' };

    const msg = document.createElement('div');
    msg.className = `message ${isUser ? 'user' : 'bot'}`;
    msg.innerHTML = `
        <div class="message-avatar">${isUser ? '\uD83D\uDC64' : icons[agent]}</div>
        <div class="message-bubble">${text}</div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
    return msg;
}

function addTypingIndicator(agent) {
    const container = document.getElementById(`${agent}-messages`);
    const icons = { health: '\u2695', stocks: '\u2197', crypto: '\u26A1' };

    const msg = document.createElement('div');
    msg.className = 'message bot';
    msg.id = `${agent}-typing`;
    msg.innerHTML = `
        <div class="message-avatar">${icons[agent]}</div>
        <div class="message-bubble">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator(agent) {
    const el = document.getElementById(`${agent}-typing`);
    if (el) el.remove();
}

// ── Quick Messages ──────────────────────────────────────────────

function sendQuickMessage(agent, text) {
    const input = document.getElementById(`${agent}-input`);
    input.value = text;
    sendMessage(agent);
}

// ── Send Message ────────────────────────────────────────────────

async function sendMessage(agent) {
    const input = document.getElementById(`${agent}-input`);
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    addMessage(agent, text, true);
    addTypingIndicator(agent);

    try {
        let result;
        switch (agent) {
            case 'health': result = await handleHealthQuery(text); break;
            case 'stocks': result = await handleStocksQuery(text); break;
            case 'crypto': result = await handleCryptoQuery(text); break;
        }
        removeTypingIndicator(agent);
        addMessage(agent, result);
    } catch (error) {
        removeTypingIndicator(agent);
        addMessage(agent, `<span style="color:#ef4444;">Error: ${error.message}. Please try again.</span>`);
    }
}

// ── Health Handler ──────────────────────────────────────────────

async function handleHealthQuery(text) {
    // Check if it's an income input
    const incomeMatch = text.match(/^\d+$/);

    const body = incomeMatch
        ? { message: text, income: parseInt(text) }
        : { message: text };

    const resp = await fetch('/api/health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const data = await resp.json();

    if (data.type === 'insurance') {
        let html = `<strong>${data.message}</strong>`;
        data.plans.forEach(plan => {
            const stars = '\u2605'.repeat(Math.floor(plan.rating)) + (plan.rating % 1 >= 0.5 ? '\u00BD' : '');
            html += `
                <div class="plan-card">
                    <div class="plan-name">${plan.name}</div>
                    <div class="plan-details">
                        <span>Premium: ${plan.premium}</span>
                        <span>Coverage: ${plan.coverage}</span>
                        <span class="star-rating">${stars} ${plan.rating}</span>
                    </div>
                </div>
            `;
        });
        return html;
    }

    let html = `<div>${data.analysis}</div>`;

    if (data.is_serious) {
        html += `
            <div class="result-card" style="border-color: rgba(239,68,68,0.3); margin-top: 12px;">
                <h4 style="color: #ef4444;">&#x26A0; Serious Condition Detected</h4>
                <p style="font-size: 0.85rem; color: var(--text-secondary);">
                    This may require urgent medical attention. If you don't have insurance, 
                    enter your monthly income to get plan recommendations.
                </p>
                <div class="quick-actions" style="margin-top: 8px;">
                    <button class="quick-chip" onclick="sendQuickMessage('health', '20000')">Rs.20,000</button>
                    <button class="quick-chip" onclick="sendQuickMessage('health', '35000')">Rs.35,000</button>
                    <button class="quick-chip" onclick="sendQuickMessage('health', '75000')">Rs.75,000</button>
                </div>
            </div>
        `;
    }

    html += `<div class="disclaimer">${data.disclaimer}</div>`;
    return html;
}

// ── Stocks Handler ──────────────────────────────────────────────

async function handleStocksQuery(text) {
    const resp = await fetch('/api/stocks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await resp.json();

    if (data.type === "conversation") {
        return `<div>${data.message}</div>`;
    }

    const ratingClass = (data.rating || '').toLowerCase();
    const changeClass = (data.change || '').startsWith('+') ? 'positive' : 'negative';

    let html = '';

    if (data.analysis && data.analysis.length > 200) {
        // Gemini response — format as markdown-like
        html = `
            <div class="result-card">
                <h4>${data.ticker} — AI Analysis</h4>
                <div style="white-space: pre-wrap; font-size: 0.85rem; line-height: 1.6; color: var(--text-secondary);">${data.analysis}</div>
            </div>
            <div class="disclaimer">Source: ${data.source}</div>
        `;
    } else {
        html = `
            <div class="result-card">
                <h4>${data.name || data.ticker} (${data.ticker})</h4>
                <div class="metric-row">
                    <span class="metric-label">Price</span>
                    <span class="metric-value">${data.price || 'N/A'}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Change</span>
                    <span class="metric-value ${changeClass}">${data.change || 'N/A'}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Rating</span>
                    <span class="metric-value"><span class="rating-badge ${ratingClass}">${data.rating || 'N/A'}</span></span>
                </div>
            </div>
            <div style="margin-top: 12px; font-size: 0.88rem; line-height: 1.6; color: var(--text-secondary);">
                ${data.analysis || ''}
            </div>
            <div class="disclaimer">Source: ${data.source}</div>
        `;
    }

    return html;
}

// ── Crypto Handler ──────────────────────────────────────────────

function formatNumber(num) {
    if (num >= 1e12) return '$' + (num / 1e12).toFixed(2) + 'T';
    if (num >= 1e9) return '$' + (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return '$' + (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return '$' + (num / 1e3).toFixed(2) + 'K';
    return '$' + num.toFixed(2);
}

function formatPrice(price) {
    if (price >= 1) return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return '$' + price.toFixed(6);
}

async function handleCryptoQuery(text) {
    const resp = await fetch('/api/crypto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await resp.json();

    if (data.type === "conversation") {
        return `<div>${data.message}</div>`;
    }

    const change24Class = data.change_24h >= 0 ? 'positive' : 'negative';
    const change7dClass = data.change_7d >= 0 ? 'positive' : 'negative';
    const sentScore = data.sentiment_score || 0.5;

    let sentColor;
    if (sentScore >= 0.7) sentColor = 'var(--accent-health)';
    else if (sentScore >= 0.5) sentColor = 'var(--accent-crypto)';
    else sentColor = '#ef4444';

    let imageHtml = '';
    if (data.image) {
        imageHtml = `<img src="${data.image}" alt="${data.name}" style="width: 24px; height: 24px; border-radius: 50%; vertical-align: middle; margin-right: 8px;">`;
    }

    let html = `
        <div class="result-card">
            <h4>${imageHtml}${data.name || data.symbol} (${data.symbol})</h4>
            <div class="metric-row">
                <span class="metric-label">Price</span>
                <span class="metric-value">${formatPrice(data.price || 0)}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">24h Change</span>
                <span class="metric-value ${change24Class}">${data.change_24h}%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Volume (24h)</span>
                <span class="metric-value">${formatNumber(data.volume_24h || 0)}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Market Cap</span>
                <span class="metric-value">${formatNumber(data.market_cap || 0)}</span>
            </div>
            
            <div class="sentiment-bar-container">
                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted);">
                    <span>Bearish</span><span>Bullish</span>
                </div>
                <div class="sentiment-bar">
                    <div class="sentiment-fill" style="width: ${sentScore * 100}%; background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);"></div>
                </div>
            </div>
        </div>
        <div class="disclaimer">Source: ${data.source}</div>
    `;

    return html;
}

// ── Portfolio & Crisis Protocol ───────────────────────────────

let userPortfolio = [
    { symbol: "AAPL", type: "Stock", shares: 15, avg_buy: 150.0 },
    { symbol: "TSLA", type: "Stock", shares: 20, avg_buy: 200.0 },
    { symbol: "BTC", type: "Crypto", shares: 0.5, avg_buy: 40000.0 },
    { symbol: "SOL", type: "Crypto", shares: 100, avg_buy: 50.0 }
];

// Load from local storage if exists
try {
    const saved = localStorage.getItem('finwell_portfolio');
    if (saved) userPortfolio = JSON.parse(saved);
} catch (e) { }

function updateBrokerBtnStage() {
    const btn = document.getElementById('connect-broker-btn');
    if (btn) {
        btn.innerHTML = `🛡️ SECURE: ${userPortfolio.length} Assets Linked`;
        btn.style.background = 'rgba(16, 185, 129, 0.1)';
        btn.style.borderColor = 'var(--accent-health)';
        btn.style.color = 'var(--accent-health)';
    }
}

// Call on load
document.addEventListener('DOMContentLoaded', updateBrokerBtnStage);

function openPortfolioModal() {
    document.getElementById('portfolio-modal').classList.add('active');
    renderPortfolioRows();
}

function closePortfolioModal() {
    document.getElementById('portfolio-modal').classList.remove('active');
}

function renderPortfolioRows() {
    const container = document.getElementById('portfolio-inputs');
    container.innerHTML = '';

    userPortfolio.forEach((asset, index) => {
        const row = document.createElement('div');
        row.className = 'portfolio-row';
        row.innerHTML = `
            <input type="text" class="portfolio-input p-symbol" value="${asset.symbol}" placeholder="Symbol (e.g. AAPL)" />
            <select class="portfolio-input p-type">
                <option value="Stock" ${asset.type === 'Stock' ? 'selected' : ''}>Stock</option>
                <option value="Crypto" ${asset.type === 'Crypto' ? 'selected' : ''}>Crypto</option>
            </select>
            <input type="number" class="portfolio-input p-shares" value="${asset.shares}" placeholder="Qty" step="any" />
            <input type="number" class="portfolio-input p-buy" value="${asset.avg_buy}" placeholder="Avg Buy $" step="any" />
            <button class="portfolio-btn" onclick="removePortfolioRow(${index})">🗑</button>
        `;
        container.appendChild(row);
    });
}

function addPortfolioRow() {
    userPortfolio.push({ symbol: "", type: "Stock", shares: 0, avg_buy: 0 });
    renderPortfolioRows();
}

function removePortfolioRow(index) {
    userPortfolio.splice(index, 1);
    renderPortfolioRows();
}

function savePortfolio() {
    const rows = document.querySelectorAll('#portfolio-inputs .portfolio-row');
    const newPortfolio = [];

    rows.forEach(row => {
        const symbol = row.querySelector('.p-symbol').value.toUpperCase().trim();
        const type = row.querySelector('.p-type').value;
        const shares = parseFloat(row.querySelector('.p-shares').value) || 0;
        const avg_buy = parseFloat(row.querySelector('.p-buy').value) || 0;

        if (symbol && shares > 0) {
            newPortfolio.push({ symbol, type, shares, avg_buy });
        }
    });

    if (newPortfolio.length === 0) {
        alert("Please add at least one valid asset.");
        return;
    }

    userPortfolio = newPortfolio;
    localStorage.setItem('finwell_portfolio', JSON.stringify(userPortfolio));
    updateBrokerBtnStage();
    closePortfolioModal();
}

function triggerCrisisMode() {
    const targetAmount = 5000; // Hardcoded $5,000 for emergency
    const modal = document.getElementById('crisis-modal');
    const body = document.getElementById('crisis-body');

    modal.classList.add('active');

    body.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="typing-indicator" style="justify-content: center;"><span></span><span></span><span></span></div>
            <p style="margin-top: 20px; color: #ef4444; font-weight: 600;">Health Agent Level 5 Emergency Detected</p>
            <p style="margin-top: 10px; font-size: 0.9rem; color: var(--text-secondary);">Requesting $${targetAmount} liquidity...</p>
            <p style="margin-top: 5px; font-size: 0.9rem; color: var(--text-secondary);">Stock Analyst & Crypto Tracker analyzing cross-portfolio targets...</p>
        </div>
    `;

    // Simulate Agent negotiation delay
    setTimeout(async () => {
        try {
            const resp = await fetch('/api/crisis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_amount: targetAmount,
                    portfolio: userPortfolio
                })
            });
            const data = await resp.json();

            let html = `
                <div style="background: rgba(239,68,68,0.1); border-left: 4px solid #ef4444; padding: 16px; border-radius: 4px; margin-bottom: 24px;">
                    <strong style="color: #ef4444;">${data.message}</strong>
                </div>
                
                <h3 style="margin-bottom: 16px; border-bottom: 1px solid var(--border-glass); padding-bottom: 8px;">Smart Liquidation Proposal (Target: $${data.target})</h3>
                
                <table class="crisis-sell-table">
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th>Amount</th>
                            <th>Value</th>
                            <th>Agent Rationale</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.plan.forEach(item => {
                html += `
                    <tr>
                        <td><strong>${item.symbol}</strong> <span style="font-size: 0.75rem; color: var(--text-muted);">(${item.type})</span></td>
                        <td>${item.shares}</td>
                        <td style="color: var(--accent-health); font-weight: 600;">$${item.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td style="font-size: 0.8rem; color: var(--text-secondary);">${item.reason}</td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
                <div style="text-align: right; margin-top: 16px; font-size: 1.1rem;">
                    Total Raised: <strong style="color: var(--accent-health);">$${data.raised.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
                </div>
                
                <button class="crisis-execute-btn" onclick="executeCrisisLiquidation()">
                    AUTHORIZE & LIQUIDATE TO BANK
                </button>
            `;

            body.innerHTML = html;
        } catch (e) {
            body.innerHTML = `<div style="color: #ef4444; padding: 20px;">Error executing SOS Protocol: ${e.message}</div>`;
        }
    }, 2500); // 2.5s for narrative
}

function closeCrisisModal() {
    document.getElementById('crisis-modal').classList.remove('active');
}

function executeCrisisLiquidation() {
    const body = document.getElementById('crisis-body');
    const txHash = '0x' + Array.from({ length: 40 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
    const timestamp = new Date().toISOString();

    body.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div style="font-size: 4rem; color: var(--accent-health); margin-bottom: 20px;">✓</div>
            <h3 style="color: var(--text-primary); margin-bottom: 5px;">Secure Transfer Initiated</h3>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">Agents have executed limit orders via integrated brokerage API. Funds transferring to linked emergency checking account.</p>
            
            <div class="receipt-text">
                <div><strong>TXN HASH:</strong> ${txHash}</div>
                <div><strong>TIMESTAMP:</strong> ${timestamp}</div>
                <div><strong>STATUS:</strong> EXECUTED (CLEARING)</div>
                <div><strong>NETWORK:</strong> FEDWIRE / ACH</div>
            </div>

            <button class="back-btn" style="margin-top: 30px;" onclick="closeCrisisModal()">Close Protocol</button>
        </div>
    `;
}
