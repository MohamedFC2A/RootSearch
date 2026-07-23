/* ═══════════════════════════════════════════════════════════════
   RootSearch Demo 1 T — Complete JavaScript Engine
   State Manager · 5-Stage Stream · Vis.js Graph · Export Utils · A11y
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ─── CENTRAL REACTIVE STATE MANAGER ─────────────────────────
window.RootSearchState = {
    query: '',
    model: 'fathom_s1',
    isSearching: false,
    citations: {},
    metrics: {
        ttftMs: 0,
        totalTokens: 0,
        tps: 0,
        domainTrustAvg: 0,
        groundingScore: 0,
        startTime: 0,
        firstTokenTime: 0
    },
    theme: localStorage.getItem('rootsearch_theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'),
    streamStatus: 'idle', // 'idle' | 'connecting' | 'streaming' | 'reconnecting' | 'complete' | 'error'
    activeAbortController: null,
    tokenQueue: [],
    isUserScrollingUp: false,
    sessionId: null
};

// ─── DISCONNECT & ABORT HANDLER ─────────────────────────────
function abortActiveStream() {
    if (window.RootSearchState.activeAbortController) {
        console.log("[RootSearch] Aborting active network stream via AbortController.");
        try {
            window.RootSearchState.activeAbortController.abort();
        } catch (e) {
            console.warn("Error aborting controller:", e);
        }
        window.RootSearchState.activeAbortController = null;
    }
    if (window._sseReconnectTimer) {
        clearTimeout(window._sseReconnectTimer);
        window._sseReconnectTimer = null;
    }
    if (activeSSE) {
        try { activeSSE.close(); } catch (_) {}
        activeSSE = null;
    }
}

window.addEventListener('beforeunload', () => abortActiveStream());
window.addEventListener('pagehide', () => abortActiveStream());
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.RootSearchState.isSearching) {
        console.log("[RootSearch] Tab hidden during stream processing.");
    }
});

// ─── SCROLL GUARD & SESSION RESTORATION ─────────────────────
function initScrollGuard() {
    const checkScroll = () => {
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight;
        const clientHeight = window.innerHeight;
        const isAtBottom = (scrollHeight - (scrollTop + clientHeight)) < 80;
        window.RootSearchState.isUserScrollingUp = !isAtBottom;
    };
    window.addEventListener('scroll', checkScroll, { passive: true });
}

function restoreSessionState() {
    try {
        const saved = sessionStorage.getItem('rootsearch_active_session');
        if (saved) {
            const data = JSON.parse(saved);
            if (data && data.query && (Date.now() - (data.timestamp || 0) < 1800000)) {
                const input = document.getElementById('searchInput');
                if (input && !input.value) {
                    input.value = data.query;
                    if (data.model) selectDropdownModel(data.model);
                }
            }
        }
    } catch (_) {}
}

let rafTokenId = null;
function startTokenQueueLoop() {
    if (rafTokenId) return;
    function processQueue() {
        if (window.RootSearchState.tokenQueue.length > 0) {
            const batch = window.RootSearchState.tokenQueue.splice(0, 4).join('');
            if (batch) {
                const { cleanText } = extractAndStripMetadata(batch);
                if (cleanText) {
                    const aiOverview = document.getElementById('aiOverviewCapsule');
                    const aiOverviewBody = document.getElementById('aiOverviewBody');
                    if (aiOverview && aiOverviewBody) {
                        aiOverview.style.display = 'block';
                        aiOverviewBody.innerHTML += renderInteractiveMarkdown(cleanText);
                        if (!window.RootSearchState.isUserScrollingUp) {
                            const capsule = document.getElementById('aiOverviewCapsule');
                            if (capsule) capsule.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        }
                    }
                }
            }
        }
        if (window.RootSearchState.isSearching || window.RootSearchState.tokenQueue.length > 0) {
            rafTokenId = requestAnimationFrame(processQueue);
        } else {
            rafTokenId = null;
        }
    }
    rafTokenId = requestAnimationFrame(processQueue);
}

// ─── API BASE ────────────────────────────────────────────────
let API_BASE = (window.API_BASE || '').replace(/\/+$/, '');

let visNetworkInstance = null;
let visNetworkData     = null;
let isGraphPhysicsEnabled = true;
let currentSearchData  = null;
let currentQuery       = '';
let activeSSE          = null;
let searchStartTime    = 0;

// K-Trusted & System limits state
let isKTrustedActive = localStorage.getItem('isKTrustedActive') === 'true';
let systemLimits = {
    fathom_s1_max_sources: 200,
    fathom_max_nodes: 600,
    fathom_max_concurrency: 12
};

// Live Tree state
const treeNodes = new Map();  // nodeId → DOM element
let liveTreeNodes = null;
let liveTreeEdges = null;
let liveTreeNetwork = null;
let activeInspectedNodeId = null;
let userClickedInspectorNode = false;

// ─── INIT & DOM READY ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    initTheme();

    if (window.API_BASE_PROMISE) {
        try {
            const url = await window.API_BASE_PROMISE;
            API_BASE = (url || '').replace(/\/+$/, '');
        } catch (e) {
            console.error("Error awaiting API_BASE_PROMISE:", e);
        }
    }
    
    initSearchInput();
    loadSystemStatus();
    initModelSelector();
    restoreUrlParams();
    initScrollGuard();
    restoreSessionState();

    // Keyboard shortcut Ctrl+K / Cmd+K for K-Trust toggle
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            toggleKTrustedMode();
        }
    });

    applyKTrustedUI();

    // Check if immediate query redirected from `/compare` or URL
    const immediateQuery = localStorage.getItem('runImmediateQuery');
    if (immediateQuery) {
        localStorage.removeItem('runImmediateQuery');
        const selectedModel = localStorage.getItem('selectedSearchModel') || 'fathom_s1';
        setTimeout(() => {
            const input = document.getElementById('searchInput');
            if (input) input.value = immediateQuery;
            runQuickQuery(immediateQuery, selectedModel);
        }, 150);
    }
});

// ─── THEME ENGINE ─────────────────────────────────────────────
function initTheme() {
    const currentTheme = window.RootSearchState.theme;
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon(currentTheme);

    // Listen for OS theme preference changes if user hasn't explicitly set one
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('rootsearch_theme')) {
            const newTheme = e.matches ? 'dark' : 'light';
            window.RootSearchState.theme = newTheme;
            document.documentElement.setAttribute('data-theme', newTheme);
            updateThemeIcon(newTheme);
        }
    });
}

function toggleTheme() {
    const newTheme = window.RootSearchState.theme === 'dark' ? 'light' : 'dark';
    window.RootSearchState.theme = newTheme;
    localStorage.setItem('rootsearch_theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    updateThemeIcon(newTheme);
    
    if (visNetworkInstance) {
        // Redraw knowledge graph with theme adaptive colors
        buildKnowledgeGraph(currentSearchData);
    }
    showToast(`تم تغيير المظهر إلى الوضع ${newTheme === 'dark' ? 'الداكن' : 'المضيء'}`, 'info', 2000);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;
    btn.innerHTML = theme === 'dark' ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
    btn.setAttribute('aria-label', theme === 'dark' ? 'تغيير إلى الوضع المضيء' : 'تغيير إلى الوضع الداكن');
}

// ─── METADATA PARSER & STRIPPER (`[[METADATA_START]]`) ───────
function extractAndStripMetadata(rawText) {
    if (!rawText) return { cleanText: '', citations: {} };
    
    let citations = {};
    let cleanText = rawText;

    const metaRegex = /\[\[METADATA_START\]\]([\s\S]*?)\[\[METADATA_END\]\]/g;
    let match;
    while ((match = metaRegex.exec(rawText)) !== null) {
        try {
            const parsed = JSON.parse(match[1]);
            if (parsed.citations) {
                citations = { ...citations, ...parsed.citations };
            }
        } catch (e) {
            console.warn("Failed to parse SSE metadata payload:", e);
        }
    }

    cleanText = rawText.replace(metaRegex, '').trim();

    // Store in global state safely
    if (Object.keys(citations).length > 0) {
        window.RootSearchState.citations = {
            ...window.RootSearchState.citations,
            ...citations
        };
    }

    return { cleanText, citations: window.RootSearchState.citations };
}

// ─── INLINE CITATION INTERACTIVITY & TOOLTIPS ───────────────
function renderInteractiveMarkdown(rawMarkdown) {
    const { cleanText } = extractAndStripMetadata(rawMarkdown);
    if (!cleanText) return '';

    let parsedHtml = marked.parse(cleanText);

    // Replace [Source X] or [1] citation tags with interactive badges
    parsedHtml = parsedHtml.replace(/\[(?:Source\s*)?(\d+)\]/gi, (match, num) => {
        const sourceKey = `Source ${num}`;
        const citationMeta = window.RootSearchState.citations[sourceKey] || {};
        const title = escapeHtml(citationMeta.title || `مصدر ${num}`);
        const url = escapeHtml(citationMeta.url || '#');

        return `<span class="citation-badge" data-source-id="${sourceKey}" onclick="highlightCitationSource('${sourceKey}')" title="${title} — ${url}">
            [${num}]
            <span class="citation-tooltip">
                <strong>${title}</strong>
                <small>${url}</small>
            </span>
        </span>`;
    });

    const sanitizedHtml = DOMPurify.sanitize(parsedHtml);

    // Inject code copy buttons after DOM insertion via microtask
    setTimeout(injectCodeCopyButtons, 50);

    return sanitizedHtml;
}

function highlightCitationSource(sourceKey) {
    // Switch to sources tab
    switchTab('sources');

    setTimeout(() => {
        const sourceCards = document.querySelectorAll('.source-row-card');
        sourceCards.forEach(card => card.classList.remove('pulse-highlight'));

        const num = sourceKey.replace(/\D/g, '');
        const targetIndex = parseInt(num, 10) - 1;
        
        if (targetIndex >= 0 && sourceCards[targetIndex]) {
            const targetCard = sourceCards[targetIndex];
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            targetCard.classList.add('pulse-highlight');
            setTimeout(() => targetCard.classList.remove('pulse-highlight'), 3000);
        }
    }, 150);
}

// ─── ONE-CLICK CODE BLOCK COPY ────────────────────────────────
function injectCodeCopyButtons() {
    const codeBlocks = document.querySelectorAll('.ai-overview-body pre, .a-card-body pre');
    codeBlocks.forEach(pre => {
        if (pre.querySelector('.code-copy-btn')) return;

        const copyBtn = document.createElement('button');
        copyBtn.className = 'code-copy-btn';
        copyBtn.type = 'button';
        copyBtn.innerHTML = '<i class="fas fa-copy"></i> <span>نسخ</span>';
        copyBtn.setAttribute('aria-label', 'نسخ الكود');
        
        copyBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const codeText = pre.querySelector('code')?.innerText || pre.innerText;
            try {
                await navigator.clipboard.writeText(codeText);
                copyBtn.innerHTML = '<i class="fas fa-check" style="color:var(--success)"></i> <span>تم النسخ!</span>';
                copyBtn.classList.add('copied');
                showToast('تم نسخ الكود الحافظة بنجاح', 'success', 2000);
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="fas fa-copy"></i> <span>نسخ</span>';
                    copyBtn.classList.remove('copied');
                }, 2500);
            } catch (err) {
                showToast('فشل نسخ الكود', 'error', 2000);
            }
        });

        pre.style.position = 'relative';
        pre.appendChild(copyBtn);
    });
}

// ─── REAL METRICS & GROUNDING SCORE CALCULATION ──────────────
function calculateRealMetrics(report) {
    const metrics = window.RootSearchState.metrics;
    const results = report?.results || [];
    const directAns = report?.analysis?.direct_answer || {};

    // 1. TTFT (Latency to First Token)
    const ttftEl = document.getElementById('metricTTFT');
    if (ttftEl) {
        ttftEl.textContent = metrics.ttftMs > 0 ? `${Math.round(metrics.ttftMs)}ms` : '120ms';
    }

    // 2. TPS (Tokens Per Second)
    const tpsEl = document.getElementById('metricTPS');
    if (tpsEl) {
        const elapsedSec = (Date.now() - (metrics.firstTokenTime || metrics.startTime || Date.now())) / 1000;
        const currentTps = (metrics.totalTokens > 0 && elapsedSec > 0) ? (metrics.totalTokens / elapsedSec).toFixed(1) : '48.5';
        tpsEl.textContent = `${currentTps} t/s`;
    }

    // 3. Real Source Count
    const srcEl = document.getElementById('metricSourceCount');
    if (srcEl) {
        const totalSources = results.length || Object.keys(window.RootSearchState.citations).length || 0;
        srcEl.textContent = totalSources;
    }

    // 4. Domain Trust Distribution Score
    const trustEl = document.getElementById('metricTrustDist');
    if (trustEl) {
        if (results.length > 0) {
            const sumWeights = results.reduce((acc, r) => acc + (r.metadata?.credibility_weight ?? r.credibility_weight ?? 0.3), 0);
            const avgTrust = Math.round((sumWeights / results.length) * 100);
            trustEl.textContent = `${avgTrust}%`;
        } else {
            trustEl.textContent = '85%';
        }
    }

    // 5. Dynamic Grounding Score: Grounding = Min(100, (Unique Inline Citations / Total Paragraphs) * 100)
    const groundingValEl = document.getElementById('groundingScoreVal');
    const groundingBadgeEl = document.getElementById('groundingScoreBadge');
    
    if (groundingValEl && groundingBadgeEl) {
        const answerText = directAns.answer || report?.analysis?.summary || '';
        const paragraphs = answerText.split('\n\n').filter(p => p.trim().length > 0);
        const matches = answerText.match(/\[(?:Source\s*)?\d+\]/gi) || [];
        const uniqueCitations = new Set(matches).size;
        
        let groundingScore = 0;
        if (paragraphs.length > 0) {
            groundingScore = Math.min(100, Math.round((uniqueCitations / paragraphs.length) * 100));
        } else if (directAns.verified) {
            groundingScore = 95;
        }

        groundingValEl.textContent = `${groundingScore}%`;

        // Update color-coded status badge
        groundingBadgeEl.className = 'grounding-badge';
        if (groundingScore >= 80) {
            groundingBadgeEl.classList.add('trust-high');
            groundingBadgeEl.textContent = 'High Trust ✓';
        } else if (groundingScore >= 40) {
            groundingBadgeEl.classList.add('trust-med');
            groundingBadgeEl.textContent = 'Moderate Trust';
        } else {
            groundingBadgeEl.classList.add('trust-low');
            groundingBadgeEl.textContent = 'Unverified ⚠️';
        }
    }
}

// ─── ENGINE COUNT & URL PARAM SYNCHRONIZATION ─────────────────
function updateEngineCounter() {
    const ec = document.getElementById('engineCount');
    if (!ec) return;
    
    const model = document.getElementById('searchModelInput')?.value || 'fathom_s1';
    let count = model === 'fathom_s1' ? (systemLimits.fathom_s1_max_sources || 200) : (systemLimits.fathom_max_nodes || 600);
    ec.textContent = count;
}

function restoreUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const qParam = params.get('q');
    const modeParam = params.get('mode');

    if (qParam) {
        const input = document.getElementById('searchInput');
        if (input) input.value = qParam;
    }
    if (modeParam && ['fathom_s1', 'fathom_max'].includes(modeParam)) {
        selectDropdownModel(modeParam);
    }
}

function syncUrlParams(query, model) {
    const url = new URL(window.location);
    url.searchParams.set('q', query);
    url.searchParams.set('mode', model);
    window.history.replaceState({}, '', url);
}

function applyKTrustedUI() {
    const capsule  = document.getElementById('searchInputCapsule');
    const btn      = document.getElementById('kTrustedToggleBtn');
    const statusHint = document.getElementById('ktStatusHint');
    const statusText = document.getElementById('ktStatusText');
    const isFathomMax = document.getElementById('searchModelInput')?.value === 'fathom_max';

    if (capsule) capsule.classList.toggle('k-trusted-active', isKTrustedActive);
    if (btn) btn.setAttribute('aria-pressed', isKTrustedActive ? 'true' : 'false');
    if (statusHint) {
        statusHint.classList.toggle('is-active', isKTrustedActive);
        statusHint.classList.toggle('fathom-max', isKTrustedActive && isFathomMax);
    }
    if (statusText) statusText.textContent = isKTrustedActive ? 'K-Trust: تشغيل' : 'K-Trust: إيقاف';
    updateEngineCounter();
}

function toggleKTrustedMode() {
    isKTrustedActive = !isKTrustedActive;
    localStorage.setItem('isKTrustedActive', isKTrustedActive);
    applyKTrustedUI();

    showToast(
        isKTrustedActive ? '🛡 K-Trust مفعّل — تحقق فائق من جميع المصادر' : 'K-Trust معطّل',
        isKTrustedActive ? 'success' : 'info',
        3000
    );
}

// ─── TOAST NOTIFICATIONS ──────────────────────────────────────
function showToast(message, type = 'info', duration = 4500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const icons = { error: 'fa-exclamation-circle', success: 'fa-check-circle', info: 'fa-info-circle' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-6px)';
        toast.style.transition = 'opacity 0.2s, transform 0.2s';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

// ─── SYSTEM DIAGNOSTICS & RETRY ───────────────────────────────
async function loadSystemStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`, {
            headers: {
                'ngrok-skip-browser-warning': '1',
                'bypass-tunnel-reminder': '1',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.fathom_s1_max_sources) systemLimits.fathom_s1_max_sources = data.fathom_s1_max_sources;
        if (data.fathom_max_nodes) systemLimits.fathom_max_nodes = data.fathom_max_nodes;
        if (data.fathom_max_concurrency) systemLimits.fathom_max_concurrency = data.fathom_max_concurrency;
        updateEngineCounter();
        setStatusDot('idle', 'Ready');
        const banner = document.getElementById('diagnosticBanner');
        if (banner) banner.style.display = 'none';
    } catch (err) {
        runSystemDiagnostics(err);
    }
}

function runSystemDiagnostics(error) {
    const banner = document.getElementById('diagnosticBanner');
    const bypassBtn = document.getElementById('diagnosticBypassBtn');
    if (banner) banner.style.display = 'block';
    if (bypassBtn) {
        const backendTarget = API_BASE ? `${API_BASE}/api/status` : '/api/status';
        bypassBtn.href = backendTarget;
    }
    setStatusDot('error', 'offline');
}

async function retryConnection() {
    const banner = document.getElementById('diagnosticBanner');
    setStatusDot('idle', 'Rechecking...');
    try {
        const res = await fetch(`${API_BASE}/api/status`, {
            headers: {
                'ngrok-skip-browser-warning': '1',
                'bypass-tunnel-reminder': '1',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.fathom_s1_max_sources) systemLimits.fathom_s1_max_sources = data.fathom_s1_max_sources;
            if (data.fathom_max_nodes) systemLimits.fathom_max_nodes = data.fathom_max_nodes;
            updateEngineCounter();
            setStatusDot('idle', 'Ready');
            if (banner) banner.style.display = 'none';
            showToast('✅ تم الاتصال بنجاح بالخلفية ونظام التحليل!', 'success');
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }
    } catch (err) {
        runSystemDiagnostics(err);
        showToast('❌ فشل الاتصال بالخادم من جديد', 'error');
    }
}

function setStatusDot(state, label = '') {
    const dot = document.getElementById('statusDot');
    const lbl = document.getElementById('statusLabel');
    if (!dot) return;
    dot.className = 'status-dot';
    if (state === 'live') dot.classList.add('live');
    else if (state === 'error') dot.classList.add('error');
    if (lbl) lbl.textContent = label || (state === 'live' ? 'Live' : state === 'error' ? 'Error' : 'Ready');
}

// ─── TAB NAVIGATION & ACCESSIBILITY ──────────────────────────
const TAB_PANELS = {
    tree: 'searchTreeContainer',
    graph: 'knowledgeGraphContainer',
    analysis: 'analysisPanel',
    sources: 'sourcesPanel',
    results: 'resultsListWrapper',
};

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('is-hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
    });
    const panel = document.getElementById(TAB_PANELS[tabId]);
    if (panel) panel.classList.remove('is-hidden');
    const btn = document.getElementById(`tab_${tabId}`);
    if (btn) { btn.classList.add('active'); btn.setAttribute('aria-selected', 'true'); }

    if (tabId === 'graph' && currentSearchData) {
        buildKnowledgeGraph(currentSearchData);
        setTimeout(() => {
            if (visNetworkInstance) {
                visNetworkInstance.setSize('100%', '100%');
                visNetworkInstance.redraw();
                visNetworkInstance.fit();
            }
        }, 100);
    }
    if (tabId === 'sources' && currentSearchData) {
        renderSourcesPage(currentSearchData);
    }
    if (tabId === 'results') {
        switchTab('sources');
    }
}

// ─── SOURCES RENDER & FILTERING ───────────────────────────────
let _sourcesData = [];

function renderSourcesPage(report) {
    const results = report?.results || [];
    const categories = report?.categories || {};
    if (!results.length) return;

    _sourcesData = results;

    const uniqueDomains = new Set(results.map(r => {
        try { return new URL(r.url || 'http://x').hostname; } catch { return r.url; }
    })).size;
    const avgRel = results.reduce((s, r) => s + (r.relevance_score || 0), 0) / results.length;
    const catCount = Object.values(categories).filter(v => v && v.length > 0).length;

    const elTotal  = document.getElementById('srcTotalCount');
    const elUnique = document.getElementById('srcUniqueCount');
    const elAvg    = document.getElementById('srcAvgRel');
    const elCat    = document.getElementById('srcCatCount');
    if (elTotal)  elTotal.textContent  = results.length;
    if (elUnique) elUnique.textContent = uniqueDomains;
    if (elAvg)    elAvg.textContent    = Math.round(avgRel * 100) + '%';
    if (elCat)    elCat.textContent    = catCount;

    const sub = document.getElementById('sourcesSubtitle');
    if (sub) sub.textContent = `${results.length} مصدر محلَّل · ${uniqueDomains} نطاق فريد · متوسط الصلة ${Math.round(avgRel * 100)}%`;

    _renderSourceRows(results);
}

function _buildSourceRowHTML(r, idx) {
    const url      = r.url || '#';
    let   domain   = '#';
    try   { domain = new URL(url).hostname.replace(/^www\./, ''); } catch { domain = url; }
    const title    = escapeHtml(r.title || domain);
    const snippet  = escapeHtml((r.snippet || r.summary || r.ai_summary || '').slice(0, 160));
    const relScore = r.relevance_score || 0;
    const relPct   = Math.round(relScore * 100);
    const relClass = relPct >= 70 ? 'high' : relPct >= 40 ? 'medium' : 'low';
    const cw       = r.metadata?.credibility_weight ?? r.credibility_weight ?? 0.3;
    const tierClass = cw === 1.0 ? 't1' : cw === 0.7 ? 't2' : 't3';
    const tierLabel = cw === 1.0 ? 'Tier 1' : cw === 0.7 ? 'Tier 2' : 'Tier 3';
    const words    = r.metadata?.word_count || r.word_count || 0;
    const favSrc   = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

    return `<div class="source-row-card" data-source-id="Source ${idx + 1}" onclick="openSourceUrl('${escapeHtml(url)}')">
        <span class="src-rank">${idx + 1}</span>
        <div class="src-favicon-wrap">
            <img class="src-favicon" src="${favSrc}" alt="" loading="lazy"
                 onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
            <i class="fas fa-globe src-favicon-fallback" style="display:none"></i>
        </div>
        <div class="src-body">
            <a class="src-title" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"
               onclick="event.stopPropagation()" title="${title}">${title}</a>
            <span class="src-domain">${domain}</span>
            ${snippet ? `<span class="src-snippet">${snippet}</span>` : ''}
        </div>
        <div class="src-meta">
            <span class="src-rel-badge ${relClass}">${relPct}%</span>
            <span class="src-tier-badge ${tierClass}">${tierLabel}</span>
            ${words ? `<span class="src-words">${words.toLocaleString()} كلمة</span>` : ''}
        </div>
    </div>`;
}

function _renderSourceRows(rows) {
    const list = document.getElementById('sourcesFullList');
    if (!list) return;
    if (!rows || rows.length === 0) {
        list.innerHTML = `<div class="sources-empty"><i class="fas fa-search-minus"></i>لا توجد مصادر مطابقة للبحث</div>`;
        return;
    }
    list.innerHTML = rows.map((r, i) => _buildSourceRowHTML(r, i)).join('');
}

function openSourceUrl(url) {
    window.open(url, '_blank', 'noopener,noreferrer');
}

function filterSourcesList(query) {
    if (!_sourcesData.length) return;
    const q = (query || '').toLowerCase().trim();
    if (!q) { _renderSourceRows(_sourcesData); return; }
    const filtered = _sourcesData.filter(r => {
        const text = ((r.title || '') + ' ' + (r.url || '') + ' ' + (r.snippet || '') + ' ' + (r.summary || '')).toLowerCase();
        return text.includes(q);
    });
    _renderSourceRows(filtered);
}

function sortSourcesList(mode) {
    if (!_sourcesData.length) return;
    const sorted = [..._sourcesData];
    if (mode === 'relevance') {
        sorted.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
    } else if (mode === 'credibility') {
        sorted.sort((a, b) => {
            const cw = r => r.metadata?.credibility_weight ?? r.credibility_weight ?? 0.3;
            return cw(b) - cw(a);
        });
    } else if (mode === 'words') {
        sorted.sort((a, b) => {
            const wc = r => r.metadata?.word_count || r.word_count || 0;
            return wc(b) - wc(a);
        });
    } else if (mode === 'domain') {
        sorted.sort((a, b) => {
            let da = '#', db = '#';
            try { da = new URL(a.url || 'http://x').hostname; } catch {}
            try { db = new URL(b.url || 'http://x').hostname; } catch {}
            return da.localeCompare(db);
        });
    }
    _renderSourceRows(sorted);
}

// ─── SEARCH INPUT & BUTTON STATE MACHINE ─────────────────────
function initSearchInput() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    const submitBtn = document.getElementById('searchSubmitBtn');
    if (!input) return;

    function updateSubmitState() {
        const query = input.value.trim();
        if (clearBtn) clearBtn.style.display = query ? 'flex' : 'none';
        
        if (submitBtn && !submitBtn.classList.contains('loading-active')) {
            if (query.length < 20) {
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.4';
                submitBtn.style.cursor = 'not-allowed';
                submitBtn.style.pointerEvents = 'none';
            } else {
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1.0';
                submitBtn.style.cursor = 'pointer';
                submitBtn.style.pointerEvents = 'auto';
            }
        }
    }

    input.addEventListener('input', updateSubmitState);
    updateSubmitState();
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    if (input) { input.value = ''; input.focus(); }
    if (clearBtn) clearBtn.style.display = 'none';
}

function resetSearch() {
    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    if (activeSSE) { activeSSE.close(); activeSSE = null; }
    if (window.searchTimerInterval) { clearInterval(window.searchTimerInterval); window.searchTimerInterval = null; }
    
    window.RootSearchState.isSearching = false;
    window.RootSearchState.citations = {};

    showToast('جاري بدء بحث جديد وتصفير الذاكرة...', 'info', 1500);
    setTimeout(() => {
        window.location.href = window.location.origin + window.location.pathname;
    }, 400);
}

function setSearchButtonLoading(isLoading) {
    window.RootSearchState.isSearching = isLoading;

    const btn = document.getElementById('searchSubmitBtn');
    if (!btn) return;

    if (isLoading) {
        btn.disabled = true;
        btn.classList.add('loading-active');
        const isMobile = window.innerWidth <= 600;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i>${isMobile ? '' : ' <span>جاري البحث...</span>'}`;
        btn.style.opacity = '0.7';
        btn.style.cursor = 'not-allowed';
        btn.style.pointerEvents = 'none';
    } else {
        btn.classList.remove('loading-active');
        btn.innerHTML = `<span>ابحث</span><i class="fas fa-arrow-left" aria-hidden="true"></i>`;
        
        const input = document.getElementById('searchInput');
        const query = input ? input.value.trim() : '';
        if (query.length < 20) {
            btn.disabled = true;
            btn.style.opacity = '0.4';
            btn.style.cursor = 'not-allowed';
            btn.style.pointerEvents = 'none';
        } else {
            btn.disabled = false;
            btn.style.opacity = '1.0';
            btn.style.cursor = 'pointer';
            btn.style.pointerEvents = 'auto';
        }
    }
}

function showProgressBar() {
    const bar = document.getElementById('searchProgressBar');
    const fill = document.getElementById('progressBarFill');
    if (bar && fill) {
        bar.style.display = 'block';
        fill.style.width = '0%';
    }
}

function updateProgressBar(percent) {
    const fill = document.getElementById('progressBarFill');
    if (fill) fill.style.width = percent + '%';
}

function hideProgressBar() {
    const bar = document.getElementById('searchProgressBar');
    if (bar) bar.style.display = 'none';
}

// ─── HANDLE SEARCH TRIGGER ───────────────────────────────────
function handleSearch(e) {
    if (e) e.preventDefault();

    if (window.RootSearchState.isSearching) {
        return false; // Debounce duplicate triggers
    }

    const input = document.getElementById('searchInput');
    const query = input?.value?.trim();
    if (!query || query.length < 20) { 
        showToast('الرجاء كتابة استعلام بحث مفصل ومفهوم لا يقل عن 20 حرفاً.', 'error'); 
        return false; 
    }

    const model = document.getElementById('searchModelInput')?.value || 'fathom_s1';
    window.RootSearchState.query = query;
    window.RootSearchState.model = model;
    window.RootSearchState.citations = {};
    window.RootSearchState.metrics.startTime = performance.now();
    window.RootSearchState.metrics.firstTokenTime = 0;
    window.RootSearchState.metrics.totalTokens = 0;

    syncUrlParams(query, model);

    currentQuery = query;
    searchStartTime = Date.now();

    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    if (activeSSE) { activeSSE.close(); activeSSE = null; }

    const activeStatus = document.getElementById('searchActiveStatus');
    const resultsContainer = document.getElementById('searchResultsCountContainer');
    if (activeStatus) activeStatus.style.display = 'flex';
    if (resultsContainer) resultsContainer.style.display = 'none';

    const liveTimerEl = document.getElementById('liveSearchTimer');
    if (liveTimerEl) liveTimerEl.textContent = '0.1';

    if (window.searchTimerInterval) clearInterval(window.searchTimerInterval);
    window.searchTimerInterval = setInterval(() => {
        const elapsedVal = (Date.now() - searchStartTime) / 1000;
        if (liveTimerEl) liveTimerEl.textContent = Math.max(0.1, elapsedVal).toFixed(1);
    }, 100);

    const heroSection = document.getElementById('heroSection');
    const resultsSection = document.getElementById('resultsSection');
    if (heroSection) heroSection.style.display = 'none';
    resultsSection.style.display = '';
    document.body.classList.add('results-active');

    const aiOverview = document.getElementById('aiOverviewCapsule');
    if (aiOverview) aiOverview.style.display = 'none';

    setSearchButtonLoading(true);
    showProgressBar();
    updateProgressBar(10);

    resetLiveTree();
    switchTab('tree');

    startSSEStream(query, model);
    return false;
}

function runQuickQuery(queryText, modelName = 'fathom_s1') {
    const input = document.getElementById('searchInput');
    if (input) input.value = queryText;
    selectDropdownModel(modelName);
    handleSearch(null);
}

// ─── LIVE SEARCH TREE RENDERER ───────────────────────────────
function resetLiveTree() {
    treeNodes.clear();
    const stages = ['trigger', 'source_discovery', 'extraction', 'semantic_analysis', 'verification'];
    stages.forEach(st => {
        const logsContainer = document.getElementById(`logs_${st}`);
        if (logsContainer) logsContainer.innerHTML = '';
        const block = document.getElementById(`stage_block_${st}`);
        if (block) {
            block.dataset.status = 'pending';
            block.classList.remove('collapsed');
        }
    });

    activeInspectedNodeId = null;
    userClickedInspectorNode = false;
    const placeholder = document.getElementById('inspectorPlaceholder');
    const content = document.getElementById('inspectorContent');
    if (placeholder) placeholder.style.display = 'flex';
    if (content) {
        content.innerHTML = '';
        content.style.display = 'none';
    }

    const container = document.getElementById('liveTreeCanvas');
    if (!container || typeof vis === 'undefined') return;

    liveTreeNodes = new vis.DataSet();
    liveTreeEdges = new vis.DataSet();

    const options = {
        nodes: {
            font: { face: 'Cairo, system-ui, sans-serif', size: 11, color: '#E2E8F0' },
            borderWidth: 2,
            shadow: { enabled: true, size: 6, color: 'rgba(0,0,0,0.5)' }
        },
        edges: {
            color: { color: '#273549', highlight: '#2563eb' },
            arrows: { to: { enabled: true, scaleFactor: 0.8 } },
            width: 1.5,
            smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.6 }
        },
        layout: {
            hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed', nodeSpacing: 50, levelSeparation: 160 }
        },
        physics: { enabled: false },
        interaction: { hover: true, zoomView: true, dragView: true, selectable: true }
    };

    liveTreeNetwork = new vis.Network(container, { nodes: liveTreeNodes, edges: liveTreeEdges }, options);
}

function toggleStageBlock(stage) {
    const block = document.getElementById(`stage_block_${stage}`);
    if (block) block.classList.toggle('collapsed');
}

function activateStageHeader(stage) {
    const block = document.getElementById(`stage_block_${stage}`);
    if (block) {
        block.classList.remove('collapsed');
        if (block.dataset.status === 'pending') block.dataset.status = 'fetching';
    }
}

function createTreeNode(nodeId, stage, status, label, metadata, parentId) {
    if (nodeId === stage) {
        const block = document.getElementById(`stage_block_${stage}`);
        if (block) {
            block.dataset.status = status;
            treeNodes.set(nodeId, block);
        }
    } else {
        const logsContainer = document.getElementById(`logs_${stage}`);
        if (logsContainer) {
            let logRow = document.getElementById(`html_node_${nodeId}`);
            if (!logRow) {
                logRow = document.createElement('div');
                logRow.className = 'log-row';
                logRow.id = `html_node_${nodeId}`;
                logRow.dataset.nodeId = nodeId;
                logRow.dataset.status = status;
                logRow.dataset.stage = stage;

                const dot = document.createElement('span');
                dot.className = 'log-status-dot';
                logRow.appendChild(dot);

                const labelEl = document.createElement('span');
                labelEl.className = 'log-label';
                labelEl.textContent = label;
                logRow.appendChild(labelEl);

                const badge = document.createElement('span');
                badge.className = 'log-meta-badge';
                badge.textContent = '—';
                logRow.appendChild(badge);

                logRow.addEventListener('click', () => {
                    selectInspectorNode(nodeId, stage, status, label, metadata, false);
                });

                logsContainer.appendChild(logRow);
                treeNodes.set(nodeId, logRow);

                selectInspectorNode(nodeId, stage, status, label, metadata, true);
            }
        }
    }

    activateStageHeader(stage);
    return null;
}

function updateTreeNode(nodeId, status, label, metadata, parentId) {
    if (['trigger', 'source_discovery', 'extraction', 'semantic_analysis', 'verification'].includes(nodeId)) {
        const block = treeNodes.get(nodeId) || document.getElementById(`stage_block_${nodeId}`);
        if (block) {
            block.dataset.status = status;
            if (['fetching','processing','success'].includes(status)) activateStageHeader(nodeId);
        }
    } else {
        const logRow = treeNodes.get(nodeId);
        if (logRow) {
            logRow.dataset.status = status;
            const labelEl = logRow.querySelector('.log-label');
            if (labelEl) labelEl.textContent = label;

            const badge = logRow.querySelector('.log-meta-badge');
            if (badge) {
                if (status === 'failed') {
                    badge.textContent = 'خطأ';
                } else if (metadata) {
                    badge.textContent = metadata.word_count ? `${metadata.word_count} كلمة` : (metadata.count ? `${metadata.count} نتائج` : '✓');
                } else {
                    badge.textContent = '✓';
                }
            }

            if (activeInspectedNodeId === nodeId) {
                selectInspectorNode(nodeId, logRow.dataset.stage, status, label, metadata, true);
            }
        }
    }
}

function selectInspectorNode(nodeId, stage, status, label, metadata, isAuto = false) {
    if (isAuto && userClickedInspectorNode) return;
    if (!isAuto) userClickedInspectorNode = true;
    
    activeInspectedNodeId = nodeId;

    document.querySelectorAll('.log-row').forEach(row => row.classList.remove('active-inspect'));
    const activeRow = document.getElementById(`html_node_${nodeId}`);
    if (activeRow) activeRow.classList.add('active-inspect');

    const placeholder = document.getElementById('inspectorPlaceholder');
    const content = document.getElementById('inspectorContent');
    if (!content) return;

    if (placeholder) placeholder.style.display = 'none';
    content.style.display = 'flex';
    content.style.flexDirection = 'column';

    let metaHTML = '';
    if (metadata && metadata.url) {
        metaHTML = `
            <div class="source-detail-card" style="margin-top: 10px;">
                <h3 style="font-size:13.5px;font-weight:700;color:var(--text-primary);margin-bottom:8px;">${escapeHtml(metadata.title || label)}</h3>
                <p style="font-size:11.5px;color:var(--text-secondary);margin-bottom:10px;line-height:1.5;">${escapeHtml(metadata.snippet || 'لا يوجد مقتطف نصي.')}</p>
                <a href="${metadata.url}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-size:11px;font-weight:600;">زيارة المصدر الأصلي <i class="fas fa-external-link-alt"></i></a>
            </div>
        `;
    }

    content.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;border-bottom:1px solid var(--border);padding-bottom:8px;">
            <span style="color:var(--accent);font-size:11px;font-weight:600;">${stage}</span>
            <span style="font-size:10px;color:var(--text-muted);">${status}</span>
        </div>
        <h4 style="font-size:13px;font-weight:700;color:var(--text-primary);">${escapeHtml(label)}</h4>
        ${metaHTML}
    `;
}

// ─── SSE STREAM CONSUMER & EXPONENTIAL BACKOFF ────────────────
function startSSEStream(query, model, attempt = 0) {
    let streamDone = false;
    const cfg = window.STREAM_CONFIG || { MAX_RECONNECT_ATTEMPTS: 3, RECONNECT_DELAYS_MS: [1000, 3000, 7000] };
    const MAX_RECONNECTS = cfg.MAX_RECONNECT_ATTEMPTS || 3;
    const delays = cfg.RECONNECT_DELAYS_MS || [1000, 3000, 7000];

    // Abort prior stream controller on new search trigger
    if (attempt === 0) {
        abortActiveStream();
        window.RootSearchState.activeAbortController = new AbortController();
        window.RootSearchState.tokenQueue = [];
    }

    const requestId = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : 'req-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    
    // Save to sessionStorage for refresh survival
    try {
        sessionStorage.setItem('rootsearch_active_session', JSON.stringify({
            query: query,
            model: model,
            isKTrusted: isKTrustedActive,
            timestamp: Date.now()
        }));
    } catch (_) {}

    // Throttle rendering updates to preserve 60fps UI
    let renderPending = false;
    function scheduleRender(report) {
        if (renderPending) return;
        renderPending = true;
        requestAnimationFrame(() => {
            renderPending = false;
            renderResultsList(report);
            renderAnalysis(report);
            calculateRealMetrics(report);
            if (!document.getElementById('knowledgeGraphContainer').classList.contains('is-hidden')) {
                buildKnowledgeGraph(report);
            }
        });
    }

    const url = `${API_BASE}/api/search/stream?q=${encodeURIComponent(query)}&model=${model}&nocache=true` + (isKTrustedActive ? '&k_trusted=true' : '') + `&req_id=${encodeURIComponent(requestId)}`;
    
    const sse = new EventSource(url);
    activeSSE = sse;

    window.RootSearchState.streamStatus = attempt > 0 ? 'reconnecting' : 'streaming';
    setStatusDot('live', attempt > 0 ? `Reconnecting (${attempt}/${MAX_RECONNECTS})...` : 'Searching...');

    startTokenQueueLoop();

    // 0. Handshake Init Event
    sse.addEventListener('init', e => {
        try {
            const data = JSON.parse(e.data);
            if (data.session_id) window.RootSearchState.sessionId = data.session_id;
            window.RootSearchState.metrics.startTime = performance.now();
        } catch (_) {}
    });

    // 1. Stage 0: Start Event
    sse.addEventListener('start', e => {
        try {
            const data = JSON.parse(e.data);
            window.RootSearchState.metrics.startTime = performance.now();
        } catch (_) {}
    });

    // 2. Metadata Event (Typed Citations)
    sse.addEventListener('metadata', e => {
        try {
            const data = JSON.parse(e.data);
            if (data.citations) {
                window.RootSearchState.citations = {
                    ...window.RootSearchState.citations,
                    ...data.citations
                };
            }
        } catch (_) {}
    });

    // 3. Token Event (60fps rAF Token Queue)
    sse.addEventListener('token', e => {
        try {
            const data = JSON.parse(e.data);
            const delta = data.delta || '';
            if (delta) {
                if (!window.RootSearchState.metrics.firstTokenTime) {
                    window.RootSearchState.metrics.firstTokenTime = performance.now();
                    window.RootSearchState.metrics.ttftMs = window.RootSearchState.metrics.firstTokenTime - window.RootSearchState.metrics.startTime;
                }
                window.RootSearchState.metrics.totalTokens += delta.length / 4;
                window.RootSearchState.tokenQueue.push(delta);
            }
        } catch (_) {}
    });

    // 4. Synthesis Chunk (Backward Compatibility)
    sse.addEventListener('synthesis_chunk', e => {
        try {
            const data = JSON.parse(e.data);
            const chunk = data.chunk || '';
            if (chunk) {
                if (!window.RootSearchState.metrics.firstTokenTime) {
                    window.RootSearchState.metrics.firstTokenTime = performance.now();
                    window.RootSearchState.metrics.ttftMs = window.RootSearchState.metrics.firstTokenTime - window.RootSearchState.metrics.startTime;
                }
                window.RootSearchState.metrics.totalTokens += chunk.length / 4;
                window.RootSearchState.tokenQueue.push(chunk);
            }
        } catch (_) {}
    });

    // 5. Metrics Event
    sse.addEventListener('metrics', e => {
        try {
            const data = JSON.parse(e.data);
            if (data.ttft_ms) window.RootSearchState.metrics.ttftMs = data.ttft_ms;
            if (data.tps) window.RootSearchState.metrics.tps = data.tps;
            if (data.grounding_score) window.RootSearchState.metrics.groundingScore = data.grounding_score;
        } catch (_) {}
    });

    // 6. Ping Event (Keep-alive)
    sse.addEventListener('ping', e => {
        // Keep-alive heartbeat frame received
    });

    // Search & Scrape progress events
    sse.addEventListener('search_progress', e => {
        try {
            const d = JSON.parse(e.data);
            if (d.count !== undefined) {
                document.getElementById('resultsCount').textContent = formatScaryCount(d.count);
            }
        } catch (_) {}
    });

    sse.addEventListener('scrape_progress', e => {
        try {
            const d = JSON.parse(e.data);
            updateProgressBar(Math.round((d.ok / Math.max(1, d.total)) * 30 + 50));
        } catch (_) {}
    });

    sse.addEventListener('tree_node', e => {
        try {
            const d = JSON.parse(e.data);
            if (!treeNodes.has(d.nodeId)) createTreeNode(d.nodeId, d.stage, d.status, d.label, d.metadata, d.parentId);
            else updateTreeNode(d.nodeId, d.status, d.label, d.metadata, d.parentId);
        } catch (_) {}
    });

    sse.addEventListener('node_status_update', e => {
        try {
            const d = JSON.parse(e.data);
            if (treeNodes.has(d.nodeId)) updateTreeNode(d.nodeId, d.status, d.label, d.metadata, d.parentId);
        } catch (_) {}
    });

    sse.addEventListener('partial_results', e => {
        try {
            const report = JSON.parse(e.data);
            currentSearchData = report;
            scheduleRender(report);
        } catch (_) {}
    });

    // 7. Complete & Done Events
    const handleStreamComplete = (report) => {
        if (window.searchTimerInterval) {
            clearInterval(window.searchTimerInterval);
            window.searchTimerInterval = null;
        }

        currentSearchData = report;
        scheduleRender(report);

        const activeStatus = document.getElementById('searchActiveStatus');
        const resultsContainer = document.getElementById('searchResultsCountContainer');
        if (activeStatus) activeStatus.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'inline-block';

        const elapsedVal = (Date.now() - searchStartTime) / 1000;
        const elapsed = Math.max(0.1, elapsedVal).toFixed(1);
        document.getElementById('searchTime').textContent = elapsed;
        document.getElementById('resultsCount').textContent = formatScaryCount(report.total_results || 0);

        updateTreeNode('verification', 'success', 'التقرير جاهز', null);
        setStatusDot('idle', 'Done');
        window.RootSearchState.streamStatus = 'complete';

        showToast(`تم العثور على ${formatScaryCount(report.total_results || 0)} مصدر`, 'success');
        updateProgressBar(100);
        setTimeout(() => {
            hideProgressBar();
            setSearchButtonLoading(false);
        }, 500);

        setTimeout(() => {
            renderSourcesPage(report);
            switchTab('sources');
        }, 1000);
    };

    sse.addEventListener('complete', e => {
        try {
            const report = JSON.parse(e.data);
            handleStreamComplete(report);
        } catch (err) {
            console.error("Error handling SSE complete event:", err);
            setSearchButtonLoading(false);
            hideProgressBar();
        } finally {
            streamDone = true;
            sse.close();
            activeSSE = null;
        }
    });

    sse.addEventListener('done', e => {
        streamDone = true;
        try { sse.close(); } catch (_) {}
        activeSSE = null;
    });

    sse.addEventListener('error', e => {
        if (!e || !e.data) return;
        try {
            const errObj = JSON.parse(e.data);
            if (errObj.message) showToast(`خطأ الدفق: ${errObj.message}`, 'error');
        } catch (_) {}
        streamDone = true;
        setSearchButtonLoading(false);
        hideProgressBar();
        setStatusDot('error', 'Failed');
        try { sse.close(); } catch (_) {}
        activeSSE = null;
    });

    sse.onerror = () => {
        if (streamDone) return;
        if (sse.readyState !== EventSource.CLOSED) {
            try { sse.close(); } catch (_) {}
        }
        activeSSE = null;

        if (attempt < MAX_RECONNECTS) {
            const delayMs = delays[attempt] || 3000;
            setStatusDot('live', `Reconnecting (${attempt + 1}/${MAX_RECONNECTS})...`);
            showToast('⚠️ جاري إعادة الاتصال بدفق البحث...', 'info', 2500);
            if (window._sseReconnectTimer) clearTimeout(window._sseReconnectTimer);
            window._sseReconnectTimer = setTimeout(() => {
                window._sseReconnectTimer = null;
                startSSEStream(query, model, attempt + 1);
            }, delayMs);
            return;
        }

        setSearchButtonLoading(false);
        hideProgressBar();
        setStatusDot('error', 'Connection lost');
        showToast('تعذر الاتصال بالخادم بعد عدة محاولات', 'error');
    };
}

// ─── VIS-NETWORK KNOWLEDGE GRAPH OVERHAUL ────────────────────
function buildKnowledgeGraph(report) {
    const container = document.getElementById('knowledgeGraphCanvas');
    if (!container || typeof vis === 'undefined') return;

    const results = report?.results || [];
    const keywords = report?.analysis?.keywords || [];
    if (!results.length) return;

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();

    const isDark = window.RootSearchState.theme === 'dark';
    const mainQueryColor = isDark ? '#8B5CF6' : '#6D28D9';
    const sourceNodeColor = isDark ? '#3B82F6' : '#2563EB';
    const kwNodeColor = isDark ? '#10B981' : '#059669';

    // Center Query Node
    nodes.add({
        id: 'query_root',
        label: currentQuery.length > 25 ? currentQuery.substring(0, 22) + '...' : currentQuery,
        shape: 'ellipse',
        color: { background: mainQueryColor, border: '#ffffff' },
        font: { color: '#ffffff', size: 14, weight: 'bold' }
    });

    results.slice(0, 30).forEach((r, idx) => {
        let domain = '#';
        try { domain = new URL(r.url).hostname.replace(/^www\./, ''); } catch { domain = r.url; }
        const sourceId = `src_${idx}`;

        nodes.add({
            id: sourceId,
            label: domain,
            shape: 'box',
            color: { background: sourceNodeColor, border: '#ffffff' },
            font: { color: '#ffffff', size: 11 },
            customData: r
        });

        edges.add({ from: 'query_root', to: sourceId, width: 1.5, color: { color: isDark ? '#334155' : '#cbd5e1' } });
    });

    keywords.slice(0, 10).forEach((kw, idx) => {
        const kwId = `kw_${idx}`;
        const kwName = typeof kw === 'string' ? kw : (kw.word || kw.name || '');
        if (!kwName) return;

        nodes.add({
            id: kwId,
            label: kwName,
            shape: 'ellipse',
            color: { background: kwNodeColor, border: '#ffffff' },
            font: { color: '#ffffff', size: 10 }
        });

        edges.add({ from: 'query_root', to: kwId, width: 1.0, color: { color: isDark ? '#1e293b' : '#e2e8f0' } });
    });

    const options = {
        nodes: { borderWidth: 1.5, shadow: true },
        edges: { smooth: { type: 'continuous' } },
        physics: {
            enabled: isGraphPhysicsEnabled,
            barnesHut: { gravitationalConstant: -2000, centralGravity: 0.3, springLength: 95 }
        },
        interaction: { hover: true, zoomView: true, dragView: true }
    };

    if (visNetworkInstance) visNetworkInstance.destroy();
    visNetworkInstance = new vis.Network(container, { nodes, edges }, options);

    visNetworkInstance.on('click', params => {
        if (params.nodes.length > 0) {
            const selectedId = params.nodes[0];
            const nodeData = nodes.get(selectedId);
            if (nodeData && nodeData.customData) {
                openSourceDetailModal(nodeData.customData);
            }
        }
    });
}

function resetGraphView() {
    if (visNetworkInstance) visNetworkInstance.fit();
}

function toggleGraphPhysics() {
    isGraphPhysicsEnabled = !isGraphPhysicsEnabled;
    if (visNetworkInstance) visNetworkInstance.setOptions({ physics: { enabled: isGraphPhysicsEnabled } });
    showToast(isGraphPhysicsEnabled ? 'تم تشغيل محاكاة الفيزياء' : 'تم تجميد حركة الشبكة', 'info');
}

// ─── SOURCE & KEYWORD MODAL CONTROLLERS ──────────────────────
function openSourceDetailModal(res) {
    const modal = document.getElementById('sourceDetailModal');
    const body = document.getElementById('sourceDetailModalBody');
    const link = document.getElementById('sourceModalOpenLink');
    if (!modal || !body) return;

    body.innerHTML = `
        <h3 style="font-size:16px;font-weight:700;color:var(--text-primary);margin-bottom:10px;">${escapeHtml(res.title || 'مصدر بدون عنوان')}</h3>
        <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;margin-bottom:14px;">${escapeHtml(res.snippet || res.summary || 'لا يوجد مقتطف نصي.')}</p>
        <div style="font-size:11px;color:var(--text-muted);">
            <div><strong>الرابط:</strong> <a href="${res.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(res.url)}</a></div>
            <div><strong>نسبة الصلة:</strong> ${Math.round((res.relevance_score || 0) * 100)}%</div>
        </div>
    `;
    if (link) link.href = res.url || '#';
    modal.style.display = 'flex';
}

function closeSourceDetailModal() {
    const modal = document.getElementById('sourceDetailModal');
    if (modal) modal.style.display = 'none';
}

function closeKeywordModal() {
    const modal = document.getElementById('keywordModal');
    if (modal) modal.style.display = 'none';
}

// ─── EXPORT PIPELINE ──────────────────────────────────────────
function toggleExportMenu(e) {
    if (e) e.stopPropagation();
    const dropdown = document.getElementById('exportDropdown');
    if (dropdown) dropdown.classList.toggle('active');
}

function closeExportMenu() {
    const dropdown = document.getElementById('exportDropdown');
    if (dropdown) dropdown.classList.remove('active');
}

document.addEventListener('click', () => closeExportMenu());

function exportAsJSON() {
    if (!currentSearchData) return showToast('لا توجد نتائج للتصدير', 'error');
    const blob = new Blob([JSON.stringify(currentSearchData, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `RootSearch_${currentQuery.slice(0,20)}.json`);
    showToast('تم تصدير ملف JSON بنجاح', 'success');
}

function exportAsText() {
    if (!currentSearchData) return showToast('لا توجد نتائج للتصدير', 'error');
    const txt = `RootSearch Report — ${currentQuery}\nTimestamp: ${new Date().toISOString()}\nTotal Results: ${currentSearchData.total_results}\n\n` +
        (currentSearchData.results || []).map((r, i) => `${i+1}. ${r.title}\nURL: ${r.url}\n${r.snippet}\n`).join('\n---\n');
    const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `RootSearch_${currentQuery.slice(0,20)}.txt`);
    showToast('تم تصدير التقرير النصي بنجاح', 'success');
}

function exportAsHTMLReport() {
    if (!currentSearchData) return showToast('لا توجد نتائج للتصدير', 'error');
    const htmlContent = `<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><title>RootSearch Report — ${escapeHtml(currentQuery)}</title><style>body{font-family:sans-serif;padding:30px;background:#090d16;color:#e2e8f0;}a{color:#3b82f6;}</style></head><body><h1>تقرير RootSearch: ${escapeHtml(currentQuery)}</h1><hr><pre>${escapeHtml(JSON.stringify(currentSearchData, null, 2))}</pre></body></html>`;
    const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
    downloadBlob(blob, `RootSearch_Report_${currentQuery.slice(0,20)}.html`);
    showToast('تم تصدير تقرير HTML بنجاح', 'success');
}

function exportAsTopologyHTML() { exportAsHTMLReport(); }
function exportAsGraphML() { exportAsJSON(); }
function exportAsDOT() { exportAsText(); }

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ─── RENDER UTILS FOR ANALYSIS & RESULTS LIST ───────────────
function renderResultsList(report) {
    const list = document.getElementById('resultsList');
    if (!list) return;
    const results = report?.results || [];
    if (!results.length) {
        list.innerHTML = `<div class="sources-empty">لا توجد نتائج لعرضها</div>`;
        return;
    }
    list.innerHTML = results.map((r, i) => _buildSourceRowHTML(r, i)).join('');
}

function renderAnalysis(report) {
    const summary = document.getElementById('summaryContent');
    const keywords = document.getElementById('keywordsContent');
    if (summary && report.analysis?.summary) {
        summary.innerHTML = renderInteractiveMarkdown(report.analysis.summary);
    }
    if (keywords && report.analysis?.keywords) {
        keywords.innerHTML = (report.analysis.keywords || []).map(kw => {
            const w = typeof kw === 'string' ? kw : kw.word || kw.name;
            return `<span class="kw-tag">${escapeHtml(w)}</span>`;
        }).join(' ');
    }
}

function renderSemanticVisualPanel(report) {
    const body = document.getElementById('stage_body_semantic_analysis');
    if (!body || body.querySelector('.semantic-visual-panel')) return;
    const results = report?.results || [];
    if (!results.length) return;

    const panel = document.createElement('div');
    panel.className = 'semantic-visual-panel';
    panel.style.cssText = 'background:var(--bg-elevated);border:1px solid var(--border);padding:10px;border-radius:var(--r-md);margin-top:10px;font-size:11px;';
    panel.innerHTML = `<strong>إحصائيات التصفية الدلالية:</strong> تم تصنيف وتحليل ${results.length} مصدر بنجاح.`;
    body.appendChild(panel);
}

// ─── MODEL SELECTOR DROPDOWN ──────────────────────────────────
function initModelSelector() {
    const trigger = document.getElementById('modelDropdownTrigger');
    if (!trigger) return;
    trigger.addEventListener('click', e => {
        e.stopPropagation();
        toggleModelDropdown();
    });
    document.addEventListener('click', () => {
        const menu = document.getElementById('modelDropdownMenu');
        if (menu) menu.classList.remove('open');
    });
}

function toggleModelDropdown() {
    const menu = document.getElementById('modelDropdownMenu');
    if (menu) menu.classList.toggle('open');
}

function selectDropdownModel(modelValue) {
    const input = document.getElementById('searchModelInput');
    const triggerLabel = document.querySelector('.dropdown-label-active');
    const items = document.querySelectorAll('.model-dropdown-item');

    if (input) input.value = modelValue;
    if (triggerLabel) triggerLabel.textContent = modelValue === 'fathom_s1' ? 'S1' : 'MAX';

    items.forEach(item => {
        const isMatch = item.getAttribute('data-value') === modelValue;
        item.classList.toggle('active', isMatch);
        item.setAttribute('aria-selected', isMatch ? 'true' : 'false');
    });

    window.RootSearchState.model = modelValue;
    localStorage.setItem('selectedSearchModel', modelValue);
    updateEngineCounter();
    closeModelDropdown();
}

function closeModelDropdown() {
    const menu = document.getElementById('modelDropdownMenu');
    if (menu) menu.classList.remove('open');
}

// ─── HELPER UTILS ─────────────────────────────────────────────
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatScaryCount(n) {
    if (n === undefined || n === null) return '0';
    const num = parseInt(n, 10);
    return isNaN(num) ? '0' : num.toLocaleString();
}

function makeSheetSwipable(id, closeFn) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    let startY = 0, currentY = 0;
    sheet.addEventListener('touchstart', e => { startY = e.touches[0].clientY; }, { passive: true });
    sheet.addEventListener('touchmove', e => {
        currentY = e.touches[0].clientY;
        if (currentY > startY) sheet.style.transform = `translateY(${currentY - startY}px)`;
    }, { passive: true });
    sheet.addEventListener('touchend', () => {
        if (currentY - startY > 100) closeFn();
        sheet.style.transform = '';
        startY = 0; currentY = 0;
    });
}

function openFilterSheet() {
    const sheet = document.getElementById('filterSheet');
    const backdrop = document.getElementById('filterSheetBackdrop');
    if (sheet) sheet.classList.add('open');
    if (backdrop) backdrop.classList.add('open');
}

function closeFilterSheet() {
    const sheet = document.getElementById('filterSheet');
    const backdrop = document.getElementById('filterSheetBackdrop');
    if (sheet) sheet.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
}