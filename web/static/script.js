/* ═══════════════════════════════════════════════════════════════
   RootSearch Demo 1 T — Complete JavaScript Engine
   Live Search Tree · SSE Consumer · Vis.js Graph · Export Utils
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ─── GLOBALS ─────────────────────────────────────────────────
// ─── API BASE ────────────────────────────────
// عنوان الباك-اند. يُضبط من config.js (window.API_BASE).
// فارغ "" = نفس الأصل (تشغيل محلي) — أو رابط النفق عند النشر على Vercel.
let API_BASE = (window.API_BASE || '').replace(/\/+$/, '');

let visNetworkInstance = null;
let visNetworkData     = null;
let isGraphPhysicsEnabled = true;
let currentSearchData  = null;
let currentQuery       = '';
let activeSSE          = null;
let searchStartTime    = 0;

// K-Trusted & Depth limits state
let isKTrustedActive = localStorage.getItem('isKTrustedActive') === 'true';
let isDepthUpgraded = false;
let systemLimits = {
    fathom_s1_max_sources: 35,
    fathom_max_nodes: 150,
    fathom_max_concurrency: 12
};

// Live Tree state
const treeNodes = new Map();  // nodeId → DOM element
let liveTreeNodes = null;
let liveTreeEdges = null;
let liveTreeNetwork = null;
let currentTreeViewMode = 'visual'; // 'visual' | 'linear'


// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
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
    makeSheetSwipable('nodeSheet', closeNodeSheet);
    makeSheetSwipable('filterSheet', closeFilterSheet);
    
    // Keyboard shortcut Ctrl+K
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            toggleKTrustedMode();
        }
    });

    // Apply persisted K-Trust UI state
    applyKTrustedUI();
});

function updateEngineCounter() {
    const ec = document.getElementById('engineCount');
    if (!ec) return;
    
    const model = document.getElementById('searchModelInput')?.value || 'fathom_s1';
    let count = 0;
    if (model === 'fathom_s1') {
        count = systemLimits.fathom_s1_max_sources || 35;
    } else {
        count = systemLimits.fathom_max_nodes || 150;
    }
    
    // الـ HTML يحتوي بالفعل على كلمة "محركات" بعد الرقم، لذا نضع الرقم فقط (منع التكرار).
    ec.textContent = count;
}

function applyKTrustedUI() {
    const capsule  = document.getElementById('searchInputCapsule');
    const btn      = document.getElementById('kTrustedToggleBtn');
    const statusHint = document.getElementById('ktStatusHint');
    const statusText = document.getElementById('ktStatusText');
    const isFathomMax = document.getElementById('searchModelInput')?.value === 'fathom_max';

    // Toggle capsule active class
    if (capsule) {
        capsule.classList.toggle('k-trusted-active', isKTrustedActive);
    }

    // Update chip button aria state
    if (btn) {
        btn.setAttribute('aria-pressed', isKTrustedActive ? 'true' : 'false');
    }

    // Update status hint in search-meta
    if (statusHint) {
        statusHint.classList.toggle('is-active', isKTrustedActive);
        if (isKTrustedActive && isFathomMax) {
            statusHint.classList.add('fathom-max');
        } else {
            statusHint.classList.remove('fathom-max');
        }
    }
    if (statusText) {
        statusText.textContent = isKTrustedActive ? 'K-Trust: تشغيل' : 'K-Trust: إيقاف';
    }

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

// ─── TOAST ───────────────────────────────────────────────────
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

// ─── SYSTEM STATUS & DIAGNOSTICS ──────────────────────────────
async function loadSystemStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.fathom_s1_max_sources) systemLimits.fathom_s1_max_sources = data.fathom_s1_max_sources;
        if (data.fathom_max_nodes) systemLimits.fathom_max_nodes = data.fathom_max_nodes;
        if (data.fathom_max_concurrency) systemLimits.fathom_max_concurrency = data.fathom_max_concurrency;
        updateEngineCounter();
        setStatusDot('idle');

        // Hide diagnostic banner on success
        const banner = document.getElementById('diagnosticBanner');
        if (banner) banner.style.display = 'none';
    } catch (err) {
        runSystemDiagnostics(err);
    }
}

async function runSystemDiagnostics(error) {
    const apiBase = window.API_BASE || '';
    const cleanApiBase = apiBase.replace(/\/+$/, '');
    const isCloudflare = cleanApiBase.includes('trycloudflare.com');
    const isLocalhost = cleanApiBase.includes('localhost') || cleanApiBase.includes('127.0.0.1');
    const isOnline = navigator.onLine;

    // 1. Show diagnostic banner
    const banner = document.getElementById('diagnosticBanner');
    const bypassBtn = document.getElementById('diagnosticBypassBtn');
    if (banner) {
        banner.style.display = 'block';
        if (isCloudflare) {
            if (bypassBtn) {
                bypassBtn.style.display = 'inline-flex';
                bypassBtn.href = cleanApiBase + '/api/status';
            }
        } else {
            // General connection error
            const diagText = banner.querySelector('.diagnostic-text');
            if (diagText) {
                diagText.innerHTML = `
                    <strong>فشل الاتصال بالخادم المحلي (${escapeHtml(cleanApiBase || 'غير محدد')})</strong>
                    <span>الرجاء التأكد من تشغيل الباك-اند المحلي (uvicorn) وعمل نفق التوصيل بنجاح.</span>
                `;
            }
            if (bypassBtn) bypassBtn.style.display = 'none';
        }
    }

    // 2. Update UI Status Dot to error
    setStatusDot('error', 'offline');

    // 3. Print Giant styled Console Diagnostic Report
    console.clear();
    console.log(
        `%c┌────────────────────────────────────────────────────────────────────────┐\n` +
        `│                      ROOTSEARCH DIAGNOSTIC ENGINE                      │\n` +
        `└────────────────────────────────────────────────────────────────────────┘`,
        "color: #c9a84c; font-size: 14px; font-weight: bold; font-family: monospace;"
    );

    console.log(
        `%c[!] DIAGNOSTIC REPORT GENERATED AT: %c${new Date().toLocaleString('ar-EG')}`,
        "color: #ef4444; font-weight: bold;",
        "color: #cbd5e1;"
    );

    console.log(
        `%c[+] NETWORK INTERNET STATE: %c${isOnline ? '🟢 ONLINE (متصل بالإنترنت)' : '🔴 OFFLINE (غير متصل بالإنترنت)'}`,
        "color: #3b82f6; font-weight: bold;",
        "font-size: 11px;"
    );

    console.log(
        `%c[+] API BASE ENDPOINT: %c${cleanApiBase || 'Empty / Undefined'}`,
        "color: #3b82f6; font-weight: bold;",
        "color: #f59e0b; font-family: monospace; font-size: 11px;"
    );

    console.log(
        `%c[+] DETECTED ERROR: %c${error ? error.message : 'TypeError: Failed to fetch (CORS block)'}`,
        "color: #ef4444; font-weight: bold;",
        "color: #fca5a5; font-family: monospace;"
    );

    if (isCloudflare) {
        console.log(
            `%c[!] DIAGNOSIS: %cCORS POLICY BLOCK VIA CLOUDFLARE QUICK TUNNEL`,
            "color: #f97316; font-weight: bold;",
            "color: #ef4444; font-weight: bold;"
        );
        console.log(
            `%c\n💡 [طريقة حل المشكلة وتخطي حجب المتصفح للطلب]:\n` +
            `1. اضغط على رابط تفعيل الاتصال أدناه لفتحه في علامة تبويب جديدة:\n` +
            `   👉 %c${cleanApiBase}/api/status%c\n` +
            `2. ستظهر لك صفحة تحذيرية حمراء/رمادية من Cloudflare (لأنك تزور الرابط لأول مرة).\n` +
            `3. اضغط على زر %c"Proceed to site"%c أو %c"المتابعة إلى الموقع"%c لتخطي التحذير.\n` +
            `4. بمجرد ظهور بيانات الـ JSON على شاشتك، أغلق علامة التبويب وعُد إلى هنا واضغط على زر "إعادة التحقق"!\n`,
            "color: #10b981; font-weight: bold; font-size: 12.5px;",
            "color: #c9a84c; text-decoration: underline; font-family: monospace; font-size: 13px; font-weight: bold;",
            "color: #10b981; font-weight: bold; font-size: 12.5px;",
            "color: #fff; background: #059669; padding: 1px 4px; border-radius: 3px; font-weight: bold;",
            "color: #10b981; font-weight: bold; font-size: 12.5px;",
            "color: #fff; background: #059669; padding: 1px 4px; border-radius: 3px; font-weight: bold;",
            "color: #10b981; font-weight: bold; font-size: 12.5px;"
        );
    } else if (isLocalhost) {
        console.log(
            `%c[!] DIAGNOSIS: %cLOCAL BACKEND OFFLINE OR PORT BLOCKED`,
            "color: #f97316; font-weight: bold;",
            "color: #ef4444; font-weight: bold;"
        );
        console.log(
            `%c\n💡 [طريقة حل المشكلة]:\n` +
            `1. تأكد من تشغيل ملف uvicorn محلياً على جهازك على المنفذ 8123.\n` +
            `2. تأكد من أن السيرفر يعمل بنجاح بزيارة http://localhost:8123.\n`,
            "color: #10b981; font-weight: bold; font-size: 12.5px;"
        );
    }

    console.log(
        `%c┌────────────────────────────────────────────────────────────────────────┐\n` +
        `│                     AI INTEGRATED PIPELINE METRICS                     │\n` +
        `├────────────────────────────────────────────────────────────────────────┤\n` +
        `│  • Primary Model:         fathom_s1 (DeepSeek Chat API)                │\n` +
        `│  • Advanced Model:        fathom_max (DeepSeek Deep Reasoning)         │\n` +
        `│  • Gemini Fallback API:   Permanently REMOVED                          │\n` +
        `│  • Connection Pooling:    aiohttp.ClientSession (Pooling Enabled)        │\n` +
        `│  • Rate-Limit Guard:      Top 8 Parallel Summaries + 12 Extractive     │\n` +
        `└────────────────────────────────────────────────────────────────────────┘`,
        "color: #a855f7; font-family: monospace; font-size: 11px;"
    );
}

async function retryConnection() {
    const banner = document.getElementById('diagnosticBanner');
    setStatusDot('idle', 'Rechecking...');
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (res.ok) {
            const data = await res.json();
            if (data.fathom_s1_max_sources) systemLimits.fathom_s1_max_sources = data.fathom_s1_max_sources;
            if (data.fathom_max_nodes) systemLimits.fathom_max_nodes = data.fathom_max_nodes;
            if (data.fathom_max_concurrency) systemLimits.fathom_max_concurrency = data.fathom_max_concurrency;
            updateEngineCounter();
            setStatusDot('idle', 'Ready');
            if (banner) banner.style.display = 'none';
            showToast('✅ تم الاتصال بنجاح بالخلفية ونظام التحليل!', 'success');
            console.log('%c✅ Connection restored successfully!', 'color: #22c55e; font-weight: bold; font-size: 14px;');
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }
    } catch (err) {
        runSystemDiagnostics(err);
        showToast('❌ فشل الاتصال بالخادم من جديد، يرجى تفعيل التخطي أولاً.', 'error');
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

// ─── TABS ─────────────────────────────────────────────────────
const TAB_PANELS = {
    tree: 'searchTreeContainer',
    graph: 'knowledgeGraphContainer',
    analysis: 'analysisPanel',
    results: 'resultsListWrapper',
};

// ─── AI CAPSULE TOGGLE ────────────────────────────────────────
function toggleAiCapsule() {
    const body = document.getElementById('aiOverviewBody');
    const btn  = document.getElementById('aiToggleBtn');
    if (!body) return;
    const isCollapsed = body.style.display === 'none';
    body.style.display = isCollapsed ? '' : 'none';
    if (btn) btn.classList.toggle('collapsed', !isCollapsed);
}

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
    if (tabId === 'graph') {
        if (currentSearchData) {
            // Build graph now that container is visible (has clientWidth/clientHeight)
            buildKnowledgeGraph(currentSearchData);
            setTimeout(() => {
                if (visNetworkInstance) {
                    visNetworkInstance.setSize('100%', '100%');
                    visNetworkInstance.redraw();
                    visNetworkInstance.fit();
                }
            }, 100);
        }
    }
}

// ─── SEARCH INPUT MANAGEMENT ─────────────────────────────────
function initSearchInput() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    if (!input) return;
    input.addEventListener('input', () => {
        if (clearBtn) clearBtn.style.display = input.value ? 'flex' : 'none';
    });
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    if (input) { input.value = ''; input.focus(); }
    if (clearBtn) clearBtn.style.display = 'none';
}

function resetSearch() {
    // 1. إغلاق الاتصالات والعدادات النشطة
    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    if (activeSSE) { activeSSE.close(); activeSSE = null; }
    if (window.searchTimerInterval) { clearInterval(window.searchTimerInterval); window.searchTimerInterval = null; }
    
    // 2. حذف جميع ملفات تعريف الارتباط (Cookies)
    document.cookie.split(";").forEach(function(c) {
        document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
    });
    
    // 3. مسح الذاكرة المؤقتة للجلسة (Session Storage)
    sessionStorage.clear();
    
    // 4. مسح الذاكرة المحلية (Local Storage) مع الحفاظ على وضع K-Trust
    const kTrust = localStorage.getItem('isKTrustedActive');
    localStorage.clear();
    if (kTrust !== null) {
        localStorage.setItem('isKTrustedActive', kTrust);
    }
    
    // 5. إظهار رسالة تأكيد للمستخدم والتحميل النظيف للصفحة من جديد
    showToast('جاري بدء بحث جديد نظيف وتصفير الجلسة بالكامل...', 'info', 1500);
    setTimeout(() => {
        window.location.href = window.location.origin + window.location.pathname;
    }, 600);
}

function setSearchButtonLoading(isLoading) {
    const btn = document.getElementById('searchSubmitBtn');
    if (!btn) return;
    if (isLoading) {
        btn.disabled = true;
        btn.classList.add('loading-active');
        const isMobile = window.innerWidth <= 600;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i>${isMobile ? '' : ' <span>جاري البحث...</span>'}`;
    } else {
        btn.disabled = false;
        btn.classList.remove('loading-active');
        btn.innerHTML = `<span>ابحث</span><i class="fas fa-arrow-left" aria-hidden="true"></i>`;
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
    if (fill) {
        fill.style.width = percent + '%';
    }
}

function hideProgressBar() {
    const bar = document.getElementById('searchProgressBar');
    if (bar) {
        bar.style.display = 'none';
    }
}

// ─── HANDLE SEARCH ────────────────────────────────────────────
function handleSearch(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('searchInput');
    const query = input?.value?.trim();
    if (!query || query.length < 35) { 
        showToast('الرجاء كتابة استعلام بحث مفصل ومفهوم لا يقل عن 35 حرفاً.', 'error'); 
        return false; 
    }

    currentQuery = query;
    searchStartTime = Date.now();

    // Cancel any in-progress SSE (and any pending reconnect from a prior search)
    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    if (activeSSE) { activeSSE.close(); activeSSE = null; }

    // Toggle active status and results count containers
    const activeStatus = document.getElementById('searchActiveStatus');
    const resultsContainer = document.getElementById('searchResultsCountContainer');
    if (activeStatus) activeStatus.style.display = 'flex';
    if (resultsContainer) resultsContainer.style.display = 'none';

    const liveTimerEl = document.getElementById('liveSearchTimer');
    if (liveTimerEl) liveTimerEl.textContent = '0.1';

    if (window.searchTimerInterval) clearInterval(window.searchTimerInterval);
    window.searchTimerInterval = setInterval(() => {
        const elapsedVal = (Date.now() - searchStartTime) / 1000;
        const elapsed = Math.max(0.1, elapsedVal).toFixed(1);
        if (liveTimerEl) liveTimerEl.textContent = elapsed;
    }, 100);

    // Transition UI
    const heroSection = document.getElementById('heroSection');
    const resultsSection = document.getElementById('resultsSection');
    if (heroSection) heroSection.style.display = 'none';
    resultsSection.style.display = '';
    document.body.classList.add('results-active');

    // Hide AI Quick Overview
    const aiOverview = document.getElementById('aiOverviewCapsule');
    if (aiOverview) aiOverview.style.display = 'none';

    // Set button and progress bar
    setSearchButtonLoading(true);
    showProgressBar();
    updateProgressBar(10);

    // Reset tree
    resetLiveTree();

    // Show tree tab immediately
    switchTab('tree');

    // Start SSE stream
    const model = document.getElementById('searchModelInput')?.value || 'fathom_s1';
    startSSEStream(query, model);

    return false;
}

// ─── LIVE SEARCH TREE ─────────────────────────────────────────

const STAGE_ICONS = {
    trigger:           'fas fa-bolt',
    source_discovery:  'fas fa-search',
    extraction:        'fas fa-spider',
    semantic_analysis: 'fas fa-brain',
    verification:      'fas fa-shield-alt',
};

const STAGE_LABELS = {
    pending:    'قيد الانتظار',
    fetching:   'جاري الجلب',
    processing: 'جاري المعالجة',
    success:    'اكتمل بنجاح',
    failed:     'فشلت العملية',
    rerouted:   'تم تغيير المسار',
};


function formatScaryCount(n) {
    if (n === undefined || n === null) return '0';
    const num = parseInt(n, 10);
    if (isNaN(num) || num < 0) return '0';
    return num.toLocaleString();
}

function scrollTreeToActiveStage(stage) {
    const wrap = document.getElementById('treeCanvasWrap');
    if (!wrap) return;
    const col = document.getElementById(`col_${stage}`);
    if (!col) return;
    
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
        col.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
        col.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
}


function resetLiveTree() {
    treeNodes.clear();
    const cols = ['trigger', 'source_discovery', 'extraction', 'semantic_analysis', 'verification'];
    cols.forEach(s => {
        const col = document.getElementById(`col_${s}`);
        if (col) col.innerHTML = '';
    });
    const status = document.getElementById('treeStatus');
    if (status) status.textContent = 'Initialising pipeline...';

    // Reset stage header
    document.querySelectorAll('.stage-header-item').forEach(el => {
        el.classList.remove('active', 'done');
    });

    // Update badge
    const badge = document.getElementById('treeLiveBadge');
    if (badge) badge.style.display = 'flex';
}

function activateStageHeader(stage) {
    // mark previous as done
    const stages = ['trigger', 'source_discovery', 'extraction', 'semantic_analysis', 'verification'];
    const idx = stages.indexOf(stage);
    stages.forEach((s, i) => {
        const el = document.querySelector(`.stage-header-item[data-stage="${s}"]`);
        if (!el) return;
        el.classList.remove('active', 'done');
        if (i < idx) el.classList.add('done');
        else if (i === idx) el.classList.add('active');
    });
}

function createTreeNode(nodeId, stage, status, label, metadata, parentId) {
    const col = document.getElementById(`col_${stage}`);
    if (!col) return null;

    const node = document.createElement('div');
    node.className = 'tree-node';
    node.dataset.nodeId = nodeId;
    node.dataset.status = status;
    node.dataset.stage = stage;

    const initialMicro = status === 'pending' ? 'جاري التجهيز للعملية...' : '—';
    node.innerHTML = `
        <div class="node-status-row">
            <span class="node-status-dot"></span>
            <span class="node-status-tag">${STAGE_LABELS[status] || status}</span>
        </div>
        <div class="node-label">${escapeHtml(label)}</div>
        <div class="node-microcopy" id="micro_${nodeId}">${initialMicro}</div>
    `;

    // Click opens bottom sheet
    node.addEventListener('click', () => openNodeSheet(nodeId, stage, status, label, metadata));

    col.appendChild(node);
    treeNodes.set(nodeId, node);

    activateStageHeader(stage);
    scrollTreeToActiveStage(stage);
    return node;
}

function updateTreeNode(nodeId, status, label, metadata, parentId) {
    let node = treeNodes.get(nodeId);
    if (!node) return;

    node.dataset.status = status;

    const statusTag = node.querySelector('.node-status-tag');
    if (statusTag) statusTag.textContent = STAGE_LABELS[status] || status;

    const labelEl = node.querySelector('.node-label');
    if (labelEl) labelEl.textContent = label;

    const micro = node.querySelector('.node-microcopy');
    if (micro) {
        if (status === 'failed') {
            const err = metadata?.error || metadata?.reason || 'فشلت العملية';
            micro.textContent = `خطأ: ${err}`;
        } else if (status === 'pending') {
            micro.textContent = 'جاري التجهيز للعملية...';
        } else if (metadata) {
            const parts = [];
            if (metadata.words)   parts.push(`${metadata.words.toLocaleString()} كلمة`);
            if (metadata.count !== undefined) parts.push(`تم العثور على ${formatScaryCount(metadata.count)} مصدر`);
            if (metadata.method)  parts.push(metadata.method);
            if (metadata.cb_state && metadata.cb_state !== 'closed') parts.push(`CB: ${metadata.cb_state}`);
            micro.textContent = parts.join(' · ') || '—';
        } else {
            micro.textContent = label.length > 40 ? label.slice(0, 40) + '…' : label;
        }
    }

    // Add retry button on failed nodes with can_retry
    if (status === 'failed' && metadata?.can_retry) {
        if (!node.querySelector('.node-retry-btn')) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'node-retry-btn';
            retryBtn.innerHTML = '<i class="fas fa-redo-alt"></i> إعادة المحاولة';
            retryBtn.addEventListener('click', e => {
                e.stopPropagation();
                showToast('جاري إعادة تشغيل البحث...', 'info');
                handleSearch(null);
            });
            node.appendChild(retryBtn);
        }
    }

    // Mark stage header
    if (status === 'success' || status === 'done') {
        const stageHeader = document.querySelector(`.stage-header-item[data-stage="${node.dataset.stage}"]`);
        if (stageHeader) stageHeader.classList.add('done');
    }

    // Smooth scroll to this node's stage
    if (node.dataset.stage) {
        scrollTreeToActiveStage(node.dataset.stage);
    }
}



// ─── BOTTOM SHEET ─────────────────────────────────────────────
function openNodeSheet(nodeId, stage, status, label, metadata) {
    const sheet = document.getElementById('nodeSheet');
    const content = document.getElementById('sheetContent');
    if (!sheet || !content) return;

    const statusColors = {
        success: 'var(--success-text)', failed: 'var(--error-text)',
        fetching: 'var(--fetching-text)', rerouted: 'var(--rerouted-text)',
        processing: 'var(--accent)', pending: 'var(--text-muted)',
    };

    let metaHTML = '';
    if (metadata) {
        metaHTML = Object.entries(metadata)
            .filter(([k, v]) => v !== undefined && v !== null && v !== '')
            .map(([k, v]) => `<tr><td style="color:var(--text-muted);padding:4px 8px 4px 0">${escapeHtml(k)}</td><td style="font-family:'JetBrains Mono',monospace;font-size:12px">${escapeHtml(String(v))}</td></tr>`)
            .join('');
        if (metaHTML) metaHTML = `<table style="width:100%;border-collapse:collapse;margin-top:12px">${metaHTML}</table>`;
    }

    content.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
            <span style="color:${statusColors[status] || 'var(--text-muted)'};font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;text-transform:uppercase">${status}</span>
            <span style="color:var(--text-muted);font-size:11px">${STAGE_LABELS[stage] || stage}</span>
        </div>
        <h4 style="font-size:16px;margin-bottom:8px">${escapeHtml(label)}</h4>
        <div style="font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace">ID: ${escapeHtml(nodeId)}</div>
        ${metaHTML}
    `;

    sheet.classList.add('open');
    sheet.setAttribute('aria-hidden', 'false');
    document.getElementById('sheetBackdrop').style.display = 'block';
}

function closeNodeSheet() {
    const sheet = document.getElementById('nodeSheet');
    const backdrop = document.getElementById('sheetBackdrop');
    if (sheet) { sheet.classList.remove('open'); sheet.setAttribute('aria-hidden', 'true'); }
    if (backdrop) backdrop.style.display = 'none';
}

function openBottomContentSheet(html) {
    const sheet = document.getElementById('nodeSheet');
    const content = document.getElementById('sheetContent');
    if (!sheet || !content) return;
    content.innerHTML = html;
    sheet.classList.add('open');
    sheet.setAttribute('aria-hidden', 'false');
    const backdrop = document.getElementById('sheetBackdrop');
    if (backdrop) backdrop.style.display = 'block';
}


function startSSEStream(query, model, attempt = 0) {
    // `streamDone` guards the reconnect logic: once the server has sent `complete`
    // (or a deterministic `error` event), a subsequent transport close is normal
    // and must NOT trigger a reconnect.
    let streamDone = false;
    const MAX_RECONNECTS = 3;
    // Cancel any pending reconnect from a previous attempt of this stream.
    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    const url = `${API_BASE}/api/search/stream?q=${encodeURIComponent(query)}&model=${model}&nocache=true` + (isKTrustedActive ? '&k_trusted=true' : '');
    const sse = new EventSource(url);
    activeSSE = sse;

    setStatusDot('live', attempt > 0 ? `Reconnecting (${attempt}/${MAX_RECONNECTS})...` : 'Searching...');
    document.getElementById('treeStatus').textContent = attempt > 0
        ? `إعادة الاتصال (${attempt}/${MAX_RECONNECTS})...`
        : 'Pipeline starting...';

    // partial_results: incremental updates from crawler
    sse.addEventListener('partial_results', e => {
        try {
            const report = JSON.parse(e.data);
            currentSearchData = report;
            renderResultsList(report);
            renderAnalysis(report);
            const isGraphVisible = !document.getElementById('knowledgeGraphContainer').classList.contains('is-hidden');
            if (isGraphVisible) {
                buildKnowledgeGraph(report);
            }
        } catch (_) {}
    });

    // tree_node: create a new node
    sse.addEventListener('tree_node', e => {
        try {
            const d = JSON.parse(e.data);
            if (!treeNodes.has(d.nodeId)) {
                createTreeNode(d.nodeId, d.stage, d.status, d.label, d.metadata, d.parentId);
            } else {
                updateTreeNode(d.nodeId, d.status, d.label, d.metadata, d.parentId);
            }
            const stageProgress = {
                trigger: 20,
                source_discovery: 50,
                extraction: 80,
                semantic_analysis: 92,
                verification: 98
            };
            if (stageProgress[d.stage]) updateProgressBar(stageProgress[d.stage]);
        } catch (_) { /* ignore parse errors */ }
    });

    // node_status_update: update existing node
    sse.addEventListener('node_status_update', e => {
        try {
            const d = JSON.parse(e.data);
            if (!treeNodes.has(d.nodeId)) {
                return;
            }
            updateTreeNode(d.nodeId, d.status, d.label, d.metadata, d.parentId);
            // update status line with last interesting message
            if (['fetching','processing','success'].includes(d.status)) {
                document.getElementById('treeStatus').textContent = d.label;
            }
            const stageProgress = {
                trigger: 20,
                source_discovery: 50,
                extraction: 80,
                semantic_analysis: 92,
                verification: 98
            };
            if (stageProgress[d.stage]) updateProgressBar(stageProgress[d.stage]);
        } catch (_) {}
    });


    // tree_edge: visual connector (currently handled by CSS column layout)
    sse.addEventListener('tree_edge', () => { /* structural; CSS handles it */ });

    // progress: legacy progress events
    sse.addEventListener('progress', e => {
        try {
            const d = JSON.parse(e.data);
            if (d.message) document.getElementById('treeStatus').textContent = d.message;
            if (d.status === 'search_done' && d.count !== undefined) {
                document.getElementById('resultsCount').textContent = formatScaryCount(d.count);
            }
        } catch (_) {}
    });

    // complete: final report arrived
    sse.addEventListener('complete', e => {
        try {
            if (window.searchTimerInterval) {
                clearInterval(window.searchTimerInterval);
                window.searchTimerInterval = null;
            }

            const report = JSON.parse(e.data);
            currentSearchData = report;

            // Toggle active status and results count containers
            const activeStatus = document.getElementById('searchActiveStatus');
            const resultsContainer = document.getElementById('searchResultsCountContainer');
            if (activeStatus) activeStatus.style.display = 'none';
            if (resultsContainer) resultsContainer.style.display = 'inline-block';

            // ─── Populate AI Direct Answer Capsule ───────────────────────
            const aiOverview     = document.getElementById('aiOverviewCapsule');
            const aiOverviewBody = document.getElementById('aiOverviewBody');
            const directAnswer   = report.analysis?.direct_answer;

            if (aiOverview && aiOverviewBody && directAnswer?.answer) {
                // Build confidence indicator
                const conf     = Math.round((directAnswer.confidence || 0) * 100);
                const confColor = conf >= 80 ? '#34d399' : conf >= 60 ? '#fbbf24' : '#f87171';
                const verifiedBadge = directAnswer.verified
                    ? `<span class="da-verified-badge"><i class="fas fa-shield-alt"></i> K-Trust موثق</span>`
                    : '';
                const confBar = `
                    <div class="da-confidence-row">
                        ${verifiedBadge}
                        <div class="da-conf-label">الموثوقية</div>
                        <div class="da-conf-bar-wrap">
                            <div class="da-conf-bar-fill" style="width:${conf}%;background:${confColor}"></div>
                        </div>
                        <span class="da-conf-val" style="color:${confColor}">${conf}%</span>
                    </div>`;

                // Build answer text
                const answerHtml = DOMPurify.sanitize(marked.parse(directAnswer.answer || ''));

                // Build thinking steps accordion
                let thinkingHtml = '';
                if (directAnswer.thinking) {
                    thinkingHtml = `
                        <div class="da-thinking-box" id="daThinkingBox">
                            <div class="da-thinking-header" onclick="toggleThinkingBox()">
                                <span class="da-thinking-header-title">
                                    <i class="fas fa-microchip da-thinking-icon"></i>
                                    خطوات تفكير وتحليل الذكاء الاصطناعي (DeepSeek R1 Thinking)
                                </span>
                                <i class="fas fa-chevron-down da-thinking-chevron" id="daThinkingChevron"></i>
                            </div>
                            <div class="da-thinking-content" id="daThinkingContent" style="display: none;">
                                ${DOMPurify.sanitize(marked.parse(directAnswer.thinking))}
                            </div>
                        </div>
                    `;
                }

                // Build sources list
                const sources = directAnswer.sources || [];
                let sourcesHtml = '';
                if (sources.length) {
                    sourcesHtml = `<div class="da-sources">
                        <span class="da-sources-label"><i class="fas fa-link"></i> المصادر:</span>
                        ${sources.map((s, i) => `
                            <a class="da-source-chip" href="${escapeHtml(s.url || '#')}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(s.title || s.domain || '')}">
                                <i class="fas fa-external-link-alt"></i> ${escapeHtml(s.domain || s.title || `مصدر ${i+1}`)}
                            </a>`).join('')}
                    </div>`;
                }

                aiOverviewBody.innerHTML = `
                    <div class="da-answer-text">${answerHtml}</div>
                    ${thinkingHtml}
                    ${confBar}
                    ${sourcesHtml}`;
                aiOverview.style.display = 'block';

            } else if (aiOverview && aiOverviewBody && report.analysis?.summary) {
                // Legacy fallback: verbose summary
                aiOverviewBody.innerHTML = DOMPurify.sanitize(marked.parse(report.analysis.summary));
                aiOverview.style.display = 'block';
            }

            // Update model badge dynamically
            const aiModelBadge = document.getElementById('aiModelBadge');
            if (aiModelBadge) {
                const modelMap = {
                    fathom_max: 'Fathom Max',
                    fathom_s1: 'Fathom S1',
                };
                const modelKey = report.analysis?.model || report.model || 'fathom_s1';
                const kTrust   = report.analysis?.direct_answer?.verified ? ' · K-Trust ✓' : '';
                aiModelBadge.textContent = (modelMap[modelKey] || 'RootSearch AI') + kTrust;
            }

            const elapsedVal = (Date.now() - searchStartTime) / 1000;
            const elapsed = Math.max(0.1, elapsedVal).toFixed(1);
            document.getElementById('searchTime').textContent = elapsed;
            document.getElementById('resultsCount').textContent = formatScaryCount(report.total_results || 0);
            document.getElementById('treeStatus').textContent =
                `اكتمل البحث بنجاح — تم العثور على ${formatScaryCount(report.total_results || 0)} مصدر في ${elapsed} ثانية`;

            // Mark verification node done
            updateTreeNode('verification', 'success', 'التقرير جاهز', null);

            // Populate all panels
            renderAnalysis(report);
            renderResultsList(report);
            buildKnowledgeGraph(report);

            setStatusDot('idle', 'Done');
            showToast(`تم العثور على ${formatScaryCount(report.total_results || 0)} مصدر`, 'success');
            
            updateProgressBar(100);
            setTimeout(() => {
                hideProgressBar();
                setSearchButtonLoading(false);
            }, 600);

            // Auto-switch to results tab after search (direct answer shows above tabs)
            setTimeout(() => {
                switchTab('results');
            }, 1200);


        } catch(err) {
            console.error('complete parse error', err);
            setSearchButtonLoading(false);
            hideProgressBar();
        } finally {
            streamDone = true;
            sse.close();
            activeSSE = null;
        }
    });

    // Deterministic server-sent error event (carries a JSON payload): terminal,
    // do NOT reconnect — the pipeline failed on the server side on purpose.
    sse.addEventListener('error', e => {
        if (!e || !e.data) return;  // no payload => transport error, handled by onerror
        streamDone = true;
        if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
        if (window.searchTimerInterval) { clearInterval(window.searchTimerInterval); window.searchTimerInterval = null; }
        const activeStatus = document.getElementById('searchActiveStatus');
        if (activeStatus) activeStatus.style.display = 'none';
        setSearchButtonLoading(false);
        hideProgressBar();
        try {
            const d = JSON.parse(e.data);
            showToast(d.message || 'حدث خطأ', 'error');
            document.getElementById('treeStatus').textContent = `خطأ: ${d.message || 'غير معروف'}`;
        } catch (_) {}
        setStatusDot('error', 'Failed');
        try { sse.close(); } catch (_) {}
        activeSSE = null;
    });

    // Transport-level failure (connection dropped / server closed unexpectedly).
    // The browser would otherwise blindly auto-reconnect and re-run the ENTIRE
    // expensive pipeline forever. We take control: stop native retries, then do a
    // bounded exponential-backoff reconnect, and surface a Retry affordance if it
    // ultimately fails.
    sse.onerror = () => {
        if (streamDone) return;                       // normal end after `complete`
        if (sse.readyState !== EventSource.CLOSED) {
            // Browser is mid-reconnect; cancel its blind retry and manage it ourselves.
            try { sse.close(); } catch (_) {}
        }
        activeSSE = null;

        // Stale-guard: a newer search may have started while we were connecting.
        if (query !== currentQuery) return;

        if (attempt < MAX_RECONNECTS) {
            const backoffMs = Math.min(8000, 1000 * Math.pow(2, attempt));  // 1s, 2s, 4s
            setStatusDot('live', `Reconnecting (${attempt + 1}/${MAX_RECONNECTS})...`);
            document.getElementById('treeStatus').textContent =
                `انقطع الاتصال — إعادة المحاولة خلال ${Math.round(backoffMs / 1000)}ث...`;
            if (window._sseReconnectTimer) clearTimeout(window._sseReconnectTimer);
            window._sseReconnectTimer = setTimeout(() => {
                window._sseReconnectTimer = null;
                if (query === currentQuery) startSSEStream(query, model, attempt + 1);
            }, backoffMs);
            return;
        }

        // Reconnect budget exhausted — terminal failure with an explicit retry path.
        if (window.searchTimerInterval) { clearInterval(window.searchTimerInterval); window.searchTimerInterval = null; }
        const activeStatus = document.getElementById('searchActiveStatus');
        if (activeStatus) activeStatus.style.display = 'none';
        setSearchButtonLoading(false);
        hideProgressBar();
        setStatusDot('error', 'Connection lost');
        document.getElementById('treeStatus').textContent =
            'تعذّر الاتصال بالخادم بعد عدة محاولات. اضغط بحث للمحاولة مجدداً.';
        showToast('تعذر الاتصال بعد عدة محاولات', 'error');
        
        // Trigger smart diagnostics for connection failure
        runSystemDiagnostics(new Error("EventSource connection lost after multiple retry attempts"));
    };
}

// ─── RENDER ANALYSIS PANEL ────────────────────────────────────
function renderAnalysis(report) {
    const analysis = report?.analysis || {};

    // Summary
    const summaryEl = document.getElementById('summaryContent');
    if (summaryEl) {
        const summary = analysis.summary || analysis.executive_summary || '';
        summaryEl.innerHTML = summary
            ? DOMPurify.sanitize(marked.parse(summary))
            : '<p style="color:var(--text-muted)">لا يوجد ملخص متاح.</p>';
    }

    // ROOTBASE / deep analysis
    const rootbaseEl = document.getElementById('fuckenbaseContent');
    if (rootbaseEl) {
        const deep = analysis.deep_analysis || analysis.fuckenbase_analysis || '';
        const thinking = analysis.thinking || '';
        
        let htmlContent = '';
        if (thinking) {
            htmlContent += `
                <div class="da-thinking-box" id="reportThinkingBox" style="margin-top:0;margin-bottom:var(--sp-4)">
                    <div class="da-thinking-header" onclick="toggleReportThinking()">
                        <span class="da-thinking-header-title">
                            <i class="fas fa-microchip da-thinking-icon"></i>
                            خطوات تفكير وتحليل التقرير (DeepSeek R1 Thinking)
                        </span>
                        <i class="fas fa-chevron-down da-thinking-chevron" id="reportThinkingChevron"></i>
                    </div>
                    <div class="da-thinking-content" id="reportThinkingContent" style="display: none;">
                        ${DOMPurify.sanitize(marked.parse(thinking))}
                    </div>
                </div>
            `;
        }
        
        htmlContent += deep ? DOMPurify.sanitize(marked.parse(deep)) : '<p style="color:var(--text-muted)">لا يوجد تحليل عميق متاح.</p>';
        rootbaseEl.innerHTML = htmlContent;
    }

    // Keywords
    const kwEl = document.getElementById('keywordsContent');
    if (kwEl) {
        const kws = analysis.keywords || analysis.top_keywords || [];
        if (kws.length) {
            kwEl.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:8px">` +
                kws.map(kw => {
                    const word = typeof kw === 'string' ? kw : (kw.word || kw.keyword || '');
                    const score = typeof kw === 'object' ? (kw.score || kw.frequency || '') : '';
                    return `<span class="kw-chip" onclick="openKeywordModal('${escapeHtml(word)}')">${escapeHtml(word)}<span class="kw-score">${score ? ` ·${score}` : ''}</span></span>`;
                }).join('') + '</div>';
        } else {
            kwEl.innerHTML = '<p style="color:var(--text-muted)">لا توجد كلمات مفتاحية.</p>';
        }
    }

    // Stats
    const statsEl = document.getElementById('statsContent');
    if (statsEl) {
        const stats = analysis.statistics || {};
        const rows = [
            ['إجمالي النتائج', report.total_results || 0],
            ['النتائج الفريدة', report.total_unique || 0],
            ['التصنيفات', Object.keys(report.categories || {}).join(', ') || '—'],
            ['المحركات المستخدمة', Object.keys(stats.sources_used || {}).join(', ') || '—'],
            ['وقت البحث', document.getElementById('searchTime')?.textContent + 'ث' || '—'],
        ];
        statsEl.innerHTML = `<table style="width:100%;border-collapse:collapse">` +
            rows.map(([k, v]) => `<tr>
                <td style="padding:8px 0;color:var(--text-muted);font-size:13px;border-bottom:1px solid var(--border)">${k}</td>
                <td style="padding:8px 0;font-size:13px;font-family:'JetBrains Mono',monospace;border-bottom:1px solid var(--border);text-align:end">${escapeHtml(String(v))}</td>
            </tr>`).join('') + '</table>';
    }
}

// ─── RENDER RESULTS LIST ──────────────────────────────────────
function renderResultsList(report) {
    const list = document.getElementById('resultsList');
    const loading = document.getElementById('loadingState');
    if (loading) loading.style.display = 'none';

    const results = report?.results || [];
    if (!results.length) {
        list.innerHTML = '<div class="loading-state"><p>لم يتم العثور على نتائج.</p></div>';
        return;
    }

    // Build category nav (Desktop)
    const catNav = document.getElementById('categoriesNav');
    const cats = report.categories || {};
    if (catNav && Object.keys(cats).length) {
        catNav.innerHTML =
            `<button class="category-filter-btn active" onclick="filterByCategory('all', this)">
                <i class="fas fa-globe"></i> الكل (${results.length})
            </button>` +
            Object.entries(cats).map(([k, v]) =>
                `<button class="category-filter-btn" onclick="filterByCategory('${k}', this)">
                    ${categoryIcon(k)} ${getCategoryLabel(k)} (${v.length})
                </button>`
            ).join('');
    }

    // Build mobile filter sheet items
    const mobileFilterSheet = document.getElementById('filterSheetContent');
    if (mobileFilterSheet && Object.keys(cats).length) {
        mobileFilterSheet.innerHTML = `
            <div class="mobile-filter-list">
                <button class="mobile-filter-item active" onclick="selectMobileCategory('all')">
                    <span class="m-fit-icon"><i class="fas fa-globe"></i></span>
                    <span class="m-fit-label">الكل</span>
                    <span class="m-fit-count">${results.length}</span>
                </button>
                ${Object.entries(cats).map(([k, v]) => `
                    <button class="mobile-filter-item" onclick="selectMobileCategory('${k}')">
                        <span class="m-fit-icon">${categoryIcon(k)}</span>
                        <span class="m-fit-label">${getCategoryLabel(k)}</span>
                        <span class="m-fit-count">${v.length}</span>
                    </button>
                `).join('')}
            </div>
        `;
    }

    // Render cards
    list.innerHTML = results.map((r, i) => resultCardHTML(r, i)).join('');
}

const CATEGORY_NAMES = {
    all: 'الكل',
    articles: 'مقالات وكتب',
    videos: 'مرئيات وفيديو',
    social: 'شبكات اجتماعية',
    academic: 'أبحاث ودراسات',
    news: 'أخبار وتقارير',
    code: 'برمجيات وأكواد',
    products: 'منتجات وتسوق',
    other: 'مصادر أخرى',
};

function getCategoryLabel(cat) {
    return CATEGORY_NAMES[cat] || cat;
}

function categoryIcon(cat) {
    const icons = {
        articles: '<i class="fas fa-newspaper"></i>',
        videos:   '<i class="fas fa-video"></i>',
        social:   '<i class="fas fa-share-alt"></i>',
        academic: '<i class="fas fa-graduation-cap"></i>',
        news:     '<i class="fas fa-broadcast-tower"></i>',
        code:     '<i class="fas fa-code"></i>',
        products: '<i class="fas fa-shopping-bag"></i>',
        other:    '<i class="fas fa-folder"></i>',
    };
    return icons[cat] || icons.other;
}

/** Format a relevance_score correctly regardless of range.
 *  Scores ≤ 1.0 are treated as 0-1 probability → shown as %.
 *  Scores > 1.0 are raw semantic similarity scores → shown as numeric score. */
function fmtScore(s, fallback = '') {
    if (!s && s !== 0) return fallback;
    return s <= 1.0 ? (s * 100).toFixed(0) + '%' : s.toFixed(2) + ' pts';
}

function resultCardHTML(r, idx) {

    const score = fmtScore(r.relevance_score);
    const src = (r.source || '').split('|')[0];
    const wc = r.metadata?.word_count ? `${r.metadata.word_count.toLocaleString()} كلمة` : '';
    const scraped = r.metadata?.scraped ? '<i class="fas fa-check" style="color:var(--success-text)"></i> تم استخراجه' : '';
    
    // Use AI summary if available and different from snippet, else fallback to snippet
    const isAISummary = r.summary && r.summary !== r.snippet && !r.summary.includes('Analysis failed');
    const bodyText = isAISummary ? r.summary : (r.snippet || '');
    const bodyDecoded = decodeHtml(bodyText);
    const bodyHighlighted = highlightTerms(escapeHtml(bodyDecoded), currentQuery);

    return `
    <article class="result-card" data-category="${r.content_type || 'other'}" onclick="openSourceDetailModal('${getUrlId(r.url)}')">
        <div class="result-source-row">
            <span class="result-source-badge">${escapeHtml(decodeHtml(src))}</span>
            ${score ? `<span class="result-score">${score}</span>` : ''}
        </div>
        <h3 class="result-title">
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation();">
                ${escapeHtml(decodeHtml(r.title || 'بدون عنوان'))}
            </a>
        </h3>
        <div class="result-url">${escapeHtml(r.url || '')}</div>
        <p class="result-snippet">
            ${isAISummary ? `<span class="ai-summary-badge"><i class="fas fa-sparkles"></i> تلخيص الذكاء الاصطناعي</span>` : ''}
            ${bodyHighlighted}
        </p>
        <div class="result-footer">
            ${wc ? `<span class="result-meta-tag"><i class="fas fa-file-word"></i> ${wc}</span>` : ''}
            ${scraped}
            <button class="result-open-btn" style="margin-inline-start:auto;background:none;border:none;color:var(--accent);font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:4px;" onclick="event.stopPropagation(); openSourceDetailModal('${getUrlId(r.url)}')">
                <i class="fas fa-info-circle"></i> تفاصيل المصدر
            </button>
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" class="result-open-btn" onclick="event.stopPropagation();">
                <i class="fas fa-external-link-alt"></i> فتح
            </a>
        </div>
    </article>`;
}

function highlightTerms(text, query) {
    if (!query || !text) return text;
    const terms = query.split(/\s+/).filter(t => t.length > 2);
    let result = text;
    terms.forEach(term => {
        const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        result = result.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>');
    });
    return result;
}

// Category filter
let _allResults = [];
function filterByCategory(cat, btn) {
    document.querySelectorAll('.category-filter-btn').forEach(b => {
        const isActive = b.getAttribute('onclick')?.includes(`'${cat}'`);
        b.classList.toggle('active', !!isActive);
    });

    document.querySelectorAll('.mobile-filter-item').forEach(b => {
        const isActive = b.getAttribute('onclick')?.includes(`'${cat}'`);
        b.classList.toggle('active', !!isActive);
    });

    const list = document.getElementById('resultsList');
    if (!currentSearchData) return;

    const results = cat === 'all'
        ? currentSearchData.results || []
        : (currentSearchData.categories || {})[cat] || [];
    list.innerHTML = results.map((r, i) => resultCardHTML(r, i)).join('');
}

// ─── KNOWLEDGE GRAPH ──────────────────────────────────────────
// ─── KNOWLEDGE GRAPH ──────────────────────────────────────────
function buildKnowledgeGraph(report) {
    const container = document.getElementById('knowledgeGraphCanvas');
    if (!container) return;
    if (typeof vis === 'undefined') {
        container.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text-muted);padding:20px;text-align:center">
                <i class="fas fa-exclamation-triangle" style="font-size:24px;color:#f59e0b;margin-bottom:10px"></i>
                <p style="font-size:14px;margin:0">لم يتم تحميل مكتبة رسم الشبكات (vis.js) بشكل صحيح.</p>
                <p style="font-size:12px;margin:5px 0 0">يرجى التأكد من اتصال الإنترنت أو تحديث الصفحة لتحميلها محلياً.</p>
            </div>
        `;
        return;
    }

    if (visNetworkInstance) { visNetworkInstance.destroy(); visNetworkInstance = null; }

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();
    const results = report.results || [];
    const analysis = report.analysis || {};
    const kws = (analysis.keywords || analysis.top_keywords || []).slice(0, 12);

    // 1. Center / Root Query Node
    nodes.add({
        id: 'query',
        label: escapeHtml(report.query || 'البحث'),
        shape: 'icon',
        icon: {
            face: '"Font Awesome 6 Free"',
            code: '\uf0e8', // sitemap
            size: 38,
            color: '#8B5CF6'
        },
        font: { color: '#E2E6EF', size: 14, face: 'Cairo, system-ui, sans-serif', bold: true }
    });

    // Tracking created intermediate nodes to avoid duplicates
    const createdSubqueries = new Set();
    const createdEngines = new Set();

    // Pass 1: Add all Nodes first to ensure parentUrl linkages are correctly resolved
    results.forEach((r, i) => {
        try {
            const id = getUrlId(r.url);
            if (nodes.get(id)) return;

            const domain = (r.url || '').replace(/https?:\/\//, '').split('/')[0];
            const isScraped = r.metadata?.scraped;

            nodes.add({
                id,
                label: escapeHtml(domain || r.title?.slice(0, 20) || `مصدر ${i + 1}`),
                shape: 'icon',
                icon: {
                    face: '"Font Awesome 6 Free"',
                    code: isScraped ? '\uf518' : '\uf0c1', // book-open or link
                    size: 24,
                    color: isScraped ? '#10b981' : '#6b7280'
                },
                font: { color: isScraped ? '#E2E6EF' : '#8892A4', size: 11, face: 'Cairo, system-ui, sans-serif' }
            });

            // Handle Subquery nodes creation
            const subqueryText = r.metadata?.subquery || report.query;
            const subqueryIdx = r.metadata?.subquery_idx !== undefined ? r.metadata.subquery_idx : 0;
            const subqueryNodeId = `sub_${subqueryIdx}`;

            if (subqueryText && !createdSubqueries.has(subqueryNodeId)) {
                createdSubqueries.add(subqueryNodeId);
                nodes.add({
                    id: subqueryNodeId,
                    label: escapeHtml(subqueryIdx === 0 ? `الرئيسي: "${subqueryText}"` : `تفريعة: "${subqueryText}"`),
                    shape: 'icon',
                    icon: {
                        face: '"Font Awesome 6 Free"',
                        code: '\uf126', // route/branch
                        size: 26,
                        color: '#a78bfa'
                    },
                    font: { color: '#D6BCFA', size: 11, face: 'Cairo, system-ui, sans-serif' }
                });
            }

            // Handle Engine nodes creation
            const discoveryNode = r.metadata?.discovery_node;
            if (discoveryNode) {
                const parts = discoveryNode.split('_');
                const engineName = parts.length >= 3 ? parts.slice(2).join('_') : parts.join('_');
                const engineNodeId = `eng_${subqueryNodeId}_${engineName}`;

                if (!createdEngines.has(engineNodeId)) {
                    createdEngines.add(engineNodeId);
                    nodes.add({
                        id: engineNodeId,
                        label: escapeHtml(engineName.toUpperCase()),
                        shape: 'icon',
                        icon: {
                            face: '"Font Awesome 6 Free"',
                            code: '\uf1c0', // database
                            size: 22,
                            color: '#3b82f6'
                        },
                        font: { color: '#90CDF4', size: 10, face: 'Cairo, system-ui, sans-serif' }
                    });
                }
            }
        } catch (e) {
            console.error("Error preparing node:", e, r);
        }
    });

    // Add Keyword Nodes
    kws.forEach((kw, i) => {
        try {
            const word = typeof kw === 'string' ? kw : (kw.word || '');
            if (!word) return;
            const id = `kw${i}`;
            nodes.add({
                id,
                label: escapeHtml(word),
                shape: 'icon',
                icon: {
                    face: '"Font Awesome 6 Free"',
                    code: '\uf5dc', // brain
                    size: 22,
                    color: '#f59e0b'
                },
                font: { color: '#fbd38d', size: 10, face: 'Cairo, system-ui, sans-serif' }
            });
        } catch (e) {
            console.error("Error adding keyword node:", e, kw);
        }
    });

    // Pass 2: Add all Edges
    results.forEach((r) => {
        try {
            const id = getUrlId(r.url);
            let parentNodeId = 'query';

            const subqueryIdx = r.metadata?.subquery_idx !== undefined ? r.metadata.subquery_idx : 0;
            const subqueryNodeId = `sub_${subqueryIdx}`;

            // Connect Query -> Subquery
            if (nodes.get(subqueryNodeId) && subqueryIdx !== undefined) {
                const edgeId = `edge_q_${subqueryNodeId}`;
                if (!edges.get(edgeId)) {
                    edges.add({
                        id: edgeId,
                        from: 'query',
                        to: subqueryNodeId,
                        color: { color: '#4A5568' },
                        width: 1.5
                    });
                }
                parentNodeId = subqueryNodeId;
            }

            // Connect Subquery -> Engine
            const discoveryNode = r.metadata?.discovery_node;
            if (discoveryNode) {
                const parts = discoveryNode.split('_');
                const engineName = parts.length >= 3 ? parts.slice(2).join('_') : parts.join('_');
                const engineNodeId = `eng_${subqueryNodeId}_${engineName}`;

                if (nodes.get(engineNodeId)) {
                    const edgeId = `edge_${subqueryNodeId}_${engineNodeId}`;
                    if (!edges.get(edgeId)) {
                        edges.add({
                            id: edgeId,
                            from: subqueryNodeId,
                            to: engineNodeId,
                            color: { color: '#3A4256' },
                            width: 1
                        });
                    }
                    parentNodeId = engineNodeId;
                }
            }

            // Check if this result is a link trace subpage (parent_url is available)
            if (r.metadata?.parent_url) {
                const parentUrlId = getUrlId(r.metadata.parent_url);
                if (nodes.get(parentUrlId)) {
                    edges.add({
                        from: parentUrlId,
                        to: id,
                        color: { color: '#10b981' }, // green for link traces
                        width: 1.5,
                        arrows: { to: { enabled: true, scaleFactor: 0.5 } }
                    });
                    return; // skip connecting to engine/subquery
                }
            }

            // Connect parent to result
            edges.add({
                from: parentNodeId,
                to: id,
                color: { color: '#2E3344' },
                width: 1,
                arrows: { to: { enabled: true, scaleFactor: 0.4 } }
            });
        } catch (e) {
            console.error("Error drawing edge:", e, r);
        }
    });

    // Connect keywords to main query
    kws.forEach((kw, i) => {
        try {
            const word = typeof kw === 'string' ? kw : (kw.word || '');
            if (!word) return;
            edges.add({
                from: 'query',
                to: `kw${i}`,
                color: { color: '#B7791F' },
                dashes: true,
                width: 0.8
            });
        } catch (e) {}
    });

    const graphData = { nodes, edges };
    visNetworkData = graphData;

    const opts = {
        nodes: {
            shadow: { enabled: true, color: 'rgba(0,0,0,0.6)', size: 5, x: 0, y: 3 }
        },
        edges: {
            smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.6 }
        },
        layout: {
            hierarchical: {
                direction: 'LR',
                sortMethod: 'directed',
                nodeSpacing: 110,
                levelSeparation: 260,
                parentCentralization: true
            }
        },
        physics: {
            enabled: isGraphPhysicsEnabled,
            hierarchicalRepulsion: {
                nodeDistance: 130,
                centralGravity: 0.0,
                springLength: 160,
                damping: 0.09
            },
            solver: 'hierarchicalRepulsion'
        },
        interaction: {
            hover: true,
            zoomView: true,
            dragView: true,
            tooltipDelay: 200
        }
    };

    visNetworkInstance = new vis.Network(container, graphData, opts);

    visNetworkInstance.on('click', params => {
        if (!params.nodes.length) return;
        const id = params.nodes[0];
        const sidebar = document.getElementById('graphSidebar');
        const empty = sidebar?.querySelector('.sidebar-empty');
        const details = sidebar?.querySelector('.sidebar-details');
        
        let detailsHTML = '';
        const r = results.find(res => getUrlId(res.url) === id);
        if (r) {
            const scrapedText = r.metadata?.scraped ? '<span class="status-badge success" style="background:#064e3b;color:#34d399;padding:2px 6px;border-radius:4px;font-size:10px;">تم استخراج المحتوى</span>' : '<span class="status-badge failed" style="background:#7f1d1d;color:#f87171;padding:2px 6px;border-radius:4px;font-size:10px;">لم يتم الاستخراج</span>';
            detailsHTML = `
                <h4 style="font-size:13px;margin-bottom:8px;line-height:1.4;">${escapeHtml(r.title || '')}</h4>
                <div style="font-size:10px;color:var(--text-muted);word-break:break-all;margin-bottom:8px;">${escapeHtml(r.url)}</div>
                <div style="margin-top:8px;margin-bottom:12px;">${scrapedText}</div>
                <p style="font-size:12px;color:var(--text-secondary);line-height:1.6;margin-bottom:12px;">${escapeHtml((r.snippet || '').slice(0, 180))}...</p>
                <button class="ghost-btn" style="width:100%;background:rgba(139,92,246,0.1);color:#c084fc;border:1px solid rgba(139,92,246,0.2);padding:6px;border-radius:4px;cursor:pointer;font-size:11px;display:block;" onclick="openSourceDetailModal('${id}')">
                    <i class="fas fa-file-invoice"></i> عرض تفاصيل المصدر المعرفي
                </button>
            `;
        } else {
            const kwIndex = id.startsWith('kw') ? parseInt(id.slice(2)) : -1;
            const kwName = kwIndex >= 0 && kws[kwIndex] ? (typeof kws[kwIndex] === 'string' ? kws[kwIndex] : kws[kwIndex].word) : '';
            if (kwName) {
                detailsHTML = `
                    <h4 style="font-size:14px;margin-bottom:8px"><i class="fas fa-tag"></i> ${escapeHtml(kwName)}</h4>
                    <p style="font-size:12px;color:var(--text-secondary)">مفهوم معرفي تم استخراجه دلالياً.</p>
                    <button class="ghost-btn" style="margin-top:10px;width:100%" onclick="openKeywordModal('${escapeHtml(kwName)}')">عرض التعريف والتفاصيل</button>
                `;
            } else if (id === 'query') {
                detailsHTML = `
                    <h4 style="font-size:14px;margin-bottom:8px"><i class="fas fa-search"></i> استعلام البحث</h4>
                    <p style="font-size:12px;color:var(--text-secondary)">"${escapeHtml(report.query || '')}"</p>
                `;
            } else if (id.startsWith('sub_')) {
                const subIndex = parseInt(id.split('_')[1]);
                const subText = results.find(res => res.metadata?.subquery_idx === subIndex)?.metadata?.subquery || '';
                detailsHTML = `
                    <h4 style="font-size:14px;margin-bottom:8px"><i class="fas fa-code-branch"></i> استعلام فرعي متفرع</h4>
                    <p style="font-size:12px;color:var(--text-secondary)">"${escapeHtml(subText)}"</p>
                `;
            } else if (id.startsWith('eng_')) {
                const engineName = id.split('_')[2];
                detailsHTML = `
                    <h4 style="font-size:14px;margin-bottom:8px"><i class="fas fa-search"></i> محرك البحث المكتشف</h4>
                    <p style="font-size:12px;color:var(--text-secondary)">محرك ${escapeHtml(engineName.toUpperCase())} المستخدم للتنقيب.</p>
                `;
            }
        }

        if (window.innerWidth <= 768 && detailsHTML) {
            openBottomContentSheet(detailsHTML);
        } else {
            if (empty) empty.style.display = detailsHTML ? 'none' : '';
            if (details) {
                details.style.display = detailsHTML ? '' : 'none';
                details.innerHTML = detailsHTML || '';
            }
        }
    });
}

function toggleGraphPhysics() {
    if (!visNetworkInstance) return;
    isGraphPhysicsEnabled = !isGraphPhysicsEnabled;
    visNetworkInstance.setOptions({ physics: { enabled: isGraphPhysicsEnabled } });
    const btn = document.getElementById('physicsBtn');
    if (btn) btn.innerHTML = isGraphPhysicsEnabled
        ? '<i class="fas fa-pause"></i> تجميد'
        : '<i class="fas fa-play"></i> تشغيل';
}

function resetGraphView() {
    if (visNetworkInstance) visNetworkInstance.fit({ animation: { duration: 400, easingFunction: 'easeInOutCubic' } });
}

// ─── SOURCE DETAIL MODAL ──────────────────────────────────────
function openSourceDetailModal(id) {
    const report = currentSearchData;
    if (!report) return;
    const results = report.results || [];
    const r = results.find(res => getUrlId(res.url) === id);
    if (!r) return;

    const modal = document.getElementById('sourceDetailModal');
    const body = document.getElementById('sourceDetailModalBody');
    const openLink = document.getElementById('sourceModalOpenLink');
    if (!modal || !body) return;

    openLink.href = r.url;

    const src = (r.source || '').split('|')[0];
    const score = fmtScore(r.relevance_score, '—');
    const isScraped = r.metadata?.scraped;
    const wc = r.metadata?.word_count ? r.metadata.word_count.toLocaleString() : 'غير معروف';
    const author = r.metadata?.author || 'غير معروف';
    const publishDate = r.metadata?.publish_date || r.metadata?.date || 'غير معروف';
    const language = r.metadata?.language || 'غير معروف';
    const readingTime = r.metadata?.reading_time ? `${r.metadata.reading_time} دقيقة` : (r.metadata?.word_count ? `${Math.ceil(r.metadata.word_count / 200)} دقيقة` : 'غير معروف');

    // Sentiment and tone analysis if available
    let sentimentHTML = '';
    if (r.metadata?.sentiment) {
        sentimentHTML = `<div class="metadata-item">
            <span class="metadata-label">النبرة / المشاعر</span>
            <span class="metadata-value">${escapeHtml(decodeHtml(r.metadata.sentiment))}</span>
        </div>`;
    }

    // AI Summary display with marked.js
    let aiSummaryHTML = '';
    if (r.summary && r.summary !== r.snippet && !r.summary.includes('Analysis failed')) {
        aiSummaryHTML = `
            <div class="ai-summary-section">
                <div class="ai-summary-title">
                    <i class="fas fa-sparkles"></i>
                    <span>تلخيص الذكاء الاصطناعي المعرفي (AI Summary)</span>
                </div>
                <div class="ai-summary-content">
                    ${DOMPurify.sanitize(marked.parse(decodeHtml(r.summary)))}
                </div>
            </div>
        `;
    }

    body.innerHTML = `
        <div style="margin-bottom:20px;">
            <span class="result-source-badge" style="font-size:12px;padding:4px 10px;">${escapeHtml(decodeHtml(src))}</span>
            <span class="result-score" style="font-size:12px;padding:4px 10px;margin-inline-start:8px;">معدل الصلة: ${score}</span>
        </div>
        <h2 style="font-size:18px;margin-bottom:12px;color:var(--text-primary);line-height:1.5;">${escapeHtml(decodeHtml(r.title || 'بدون عنوان'))}</h2>
        <div style="font-size:12px;color:var(--text-muted);word-break:break-all;margin-bottom:24px;">
            <i class="fas fa-link"></i> ${escapeHtml(decodeHtml(r.url))}
        </div>

        ${aiSummaryHTML}

        <h4 style="font-size:14px;margin-bottom:12px;color:var(--text-primary);"><i class="fas fa-info-circle"></i> البيانات الوصفية (Metadata)</h4>
        <div class="metadata-grid">
            <div class="metadata-item">
                <span class="metadata-label">محرك البحث المكتشف</span>
                <span class="metadata-value" style="color:var(--accent);">${escapeHtml(src.toUpperCase())}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">حالة سحب المحتوى</span>
                <span class="metadata-value" style="color:${isScraped ? 'var(--success-text)' : 'var(--error-text)'};">
                    ${isScraped ? 'تم الاستخراج بنجاح' : 'لم يتم الاستخراج'}
                </span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">عدد الكلمات</span>
                <span class="metadata-value">${wc} كلمة</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">زمن القراءة المتوقع</span>
                <span class="metadata-value">${readingTime}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">الكاتب / المؤلف</span>
                <span class="metadata-value">${escapeHtml(decodeHtml(author))}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">تاريخ النشر</span>
                <span class="metadata-value">${escapeHtml(decodeHtml(publishDate))}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">اللغة</span>
                <span class="metadata-value">${escapeHtml(decodeHtml(language.toUpperCase()))}</span>
            </div>
            ${sentimentHTML}
        </div>

        <h4 style="font-size:14px;margin-bottom:12px;color:var(--text-primary);"><i class="fas fa-quote-right"></i> مقتطف النص (Search Snippet)</h4>
        <div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--r-md);padding:16px;font-size:13px;line-height:1.7;color:var(--text-secondary);">
            ${highlightTerms(escapeHtml(decodeHtml(r.snippet || '')), currentQuery)}
        </div>
    `;

    modal.style.display = 'flex';
}

function closeSourceDetailModal() {
    const modal = document.getElementById('sourceDetailModal');
    if (modal) modal.style.display = 'none';
}

// ─── KEYWORD MODAL ────────────────────────────────────────────
function openKeywordModal(kw) {
    const modal = document.getElementById('keywordModal');
    if (!modal) return;
    document.getElementById('modalKeywordName').textContent = kw;
    modal.style.display = 'flex';

    // Populate from current data
    const report = currentSearchData;
    const analysis = report?.analysis || {};
    const allKws = analysis.keywords || analysis.top_keywords || [];
    const kwObj = allKws.find(k => (typeof k === 'string' ? k : k.word) === kw);
    const freq = kwObj?.frequency || kwObj?.score || '—';
    const sites = kwObj?.sites_count || '—';
    const density = kwObj?.density || '—';

    document.getElementById('modalKeywordFreq').textContent = freq;
    document.getElementById('modalKeywordSites').textContent = sites;
    document.getElementById('modalKeywordDensity').textContent = density;

    const explanationEl = document.getElementById('modalKeywordExplanation');
    if (explanationEl) {
        explanationEl.innerHTML = '<div class="skeleton-loader"></div>';
        fetch(`${API_BASE}/api/keyword/explain?q=${encodeURIComponent(currentQuery)}&kw=${encodeURIComponent(kw)}`)
            .then(r => r.json())
            .then(data => {
                if (data.explanation) {
                    explanationEl.innerHTML = DOMPurify.sanitize(marked.parse(data.explanation));
                } else {
                    explanationEl.textContent = 'لا يوجد تفسير متاح.';
                }
            })
            .catch(() => { explanationEl.textContent = 'فشل جلب التفسير.'; });
    }

    // Distribution
    const distEl = document.getElementById('modalKeywordDistribution');
    if (distEl) {
        const dist = kwObj?.distribution || [];
        const maxCount = dist.length ? Math.max(...dist.map(d => d.count || 1)) : 1;
        distEl.innerHTML = dist.length
            ? dist.slice(0, 8).map(d => {
                const pct = Math.max(5, Math.min(100, ((d.count || 0) / maxCount) * 100));
                return `
                <div class="dist-item">
                    <div class="dist-meta">
                        <span class="dist-site">${escapeHtml(d.site || d.url || '—')}</span>
                        <span class="dist-count">${d.count || 0}</span>
                    </div>
                    <div class="dist-bar-wrap">
                        <div class="dist-bar" style="width: ${pct}%"></div>
                    </div>
                </div>`;
            }).join('')
            : '<p style="color:var(--text-muted);font-size:12px">لا توجد بيانات توزيع.</p>';
    }

    // Contexts
    const ctxEl = document.getElementById('modalKeywordContexts');
    if (ctxEl) {
        const ctxs = kwObj?.contexts || [];
        ctxEl.innerHTML = ctxs.length
            ? ctxs.slice(0, 5).map(c => `<blockquote style="border-right:2px solid var(--accent-dim);padding-right:8px;font-size:12px;color:var(--text-secondary);margin:4px 0">${escapeHtml(c)}</blockquote>`).join('')
            : '<p style="color:var(--text-muted);font-size:12px">لا توجد سياقات.</p>';
    }

    // Scroll btn
    const scrollBtn = document.getElementById('modalScrollBtn');
    if (scrollBtn) {
        scrollBtn.onclick = () => {
            closeKeywordModal();
            switchTab('results');
        };
    }
}

function closeKeywordModal() {
    const modal = document.getElementById('keywordModal');
    if (modal) modal.style.display = 'none';
}

// Close modals on backdrop click
document.addEventListener('click', e => {
    const kwModal = document.getElementById('keywordModal');
    if (kwModal && e.target === kwModal) closeKeywordModal();

    const srcModal = document.getElementById('sourceDetailModal');
    if (srcModal && e.target === srcModal) closeSourceDetailModal();
});

// ─── EXPORT ───────────────────────────────────────────────────
// ── Export Dropdown Toggle ──────────────────────────────────────────────────
function toggleExportMenu(e) {
    if (e) e.stopPropagation();
    const dropdown = document.getElementById('exportDropdown');
    const btn = document.getElementById('exportDropdownBtn');
    if (!dropdown) return;
    const isOpen = dropdown.classList.contains('open');
    if (isOpen) {
        closeExportMenu();
    } else {
        dropdown.classList.add('open');
        btn && btn.classList.add('open');
        // Close on outside click
        setTimeout(() => {
            const handler = (event) => {
                const wrap = document.getElementById('exportDropdownWrap');
                if (wrap && !wrap.contains(event.target)) {
                    closeExportMenu();
                    document.removeEventListener('click', handler);
                }
            };
            document.addEventListener('click', handler);
        }, 10);
    }
}

function closeExportMenu() {
    const dropdown = document.getElementById('exportDropdown');
    const btn = document.getElementById('exportDropdownBtn');
    if (dropdown) dropdown.classList.remove('open');
    if (btn) btn.classList.remove('open');
}

function exportAsJSON() {

    if (!currentSearchData) { showToast('لا توجد نتائج للتصدير', 'error'); return; }
    const blob = new Blob([JSON.stringify(currentSearchData, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `rootsearch_${Date.now()}.json`);
    showToast('تم تصدير JSON', 'success');
}

function exportAsText() {
    if (!currentSearchData) { showToast('لا توجد نتائج للتصدير', 'error'); return; }

    const report        = currentSearchData;
    const analysis      = report.analysis || {};
    const stats         = analysis.statistics || {};
    const sentiment     = analysis.sentiment_overview || {};
    const keywords      = analysis.keywords || analysis.top_keywords || [];
    const results       = report.results || [];
    // Build categorized links check to prevent orphaned sources
    const rawCategories = report.categories || {};
    const categories    = JSON.parse(JSON.stringify(rawCategories));
    const categorizedUrls = new Set();
    Object.values(categories).forEach(arr => {
        if (Array.isArray(arr)) {
            arr.forEach(r => { if (r.url) categorizedUrls.add(r.url); });
        }
    });
    const uncategorized = results.filter(r => !categorizedUrls.has(r.url));
    if (uncategorized.length > 0) {
        const otherKey = 'أخرى (OTHER)';
        if (!categories[otherKey]) categories[otherKey] = [];
        // Add unique items to prevent duplicate records
        uncategorized.forEach(u => {
            if (!categories[otherKey].some(x => x.url === u.url)) {
                categories[otherKey].push(u);
            }
        });
    }
    const searchPath    = report.search_path || report.live_log || [];
    const deepAnalysis  = analysis.deep_analysis || analysis.aggregated_report || "";
    const entities      = analysis.entities || {};
    const topics        = analysis.topics || analysis.clusters || [];

    // ─── PURE ASCII HELPERS (no Arabic inside pad calculations) ───────────────
    const W = 90; // total line width

    // Repeat a char N times
    const rep = (ch, n) => ch.repeat(Math.max(0, n));

    // Left-pad or right-pad a string to exactly `len` spaces (BYTE-safe: counts chars not bytes)
    const padR = (s, len) => { s = String(s); return s + rep(' ', Math.max(0, len - s.length)); };
    const padL = (s, len) => { s = String(s); return rep(' ', Math.max(0, len - s.length)) + s; };
    const padC = (s, len) => {
        s = String(s);
        const total = Math.max(0, len - s.length);
        const l = Math.floor(total / 2);
        return rep(' ', l) + s + rep(' ', total - l);
    };

    // A full double-border line
    const dbl   = () => rep('═', W) + '\n';
    const sgl   = () => rep('─', W) + '\n';
    const bold  = () => rep('━', W) + '\n';

    // Box line: │ <content padded to W-4> │
    const row = (content) => {
        const inner = W - 4;
        const s = String(content);
        // If content longer than inner, hard-wrap
        if (s.length <= inner) return `│ ${padR(s, inner)} │\n`;
        // word-wrap
        let out = '';
        const words = s.split(' ');
        let line = '';
        words.forEach(w => {
            if ((line + w).length > inner) {
                out += `│ ${padR(line.trimEnd(), inner)} │\n`;
                line = w + ' ';
            } else {
                line += w + ' ';
            }
        });
        if (line.trim()) out += `│ ${padR(line.trimEnd(), inner)} │\n`;
        return out;
    };

    // Section header (double border)
    const sectionHeader = (label) =>
        `╔${rep('═', W - 2)}╗\n│ ${padR(label, W - 4)} │\n╚${rep('═', W - 2)}╝\n`;

    // Sub-header (single border)
    const subHeader = (label) =>
        `┌${rep('─', W - 2)}┐\n│ ${padC(label, W - 4)} │\n└${rep('─', W - 2)}┘\n`;

    // Simple ASCII bar (10 blocks)
    const bar = (val, max = 1.0) => {
        const pct = Math.max(0, Math.min(100, Math.round((val / max) * 100)));
        const filled = Math.round(pct / 10);
        return `[${'█'.repeat(filled)}${'░'.repeat(10 - filled)}] ${padL(pct + '%', 4)}`;
    };

    // Wrap long text into lines of max `w` chars, each prefixed with `prefix`
    const wrapText = (text, prefix = '', w = W - 6) => {
        if (!text) return '';
        const words = String(text).replace(/\s+/g, ' ').split(' ');
        let out = '', line = '';
        words.forEach(word => {
            if ((line + word).length > w) {
                out += prefix + line.trimEnd() + '\n';
                line = word + ' ';
            } else {
                line += word + ' ';
            }
        });
        if (line.trim()) out += prefix + line.trimEnd() + '\n';
        return out;
    };

    // ─── KEY DATA ─────────────────────────────────────────────────────────────
    const queryStr    = report.query || '—';
    const totalRes    = results.length;
    const uniqueRes   = new Set(results.map(r => r.url)).size;
    const searchTime  = report.elapsed_time || report.search_time || '—';
    const modelName   = report.model === 'fathom_max'
        ? 'Fathom Max — التنقيب العميق المتقدم'
        : 'Fathom S1 — البحث البرقي السريع';
    const timestamp   = new Date(report.timestamp || Date.now()).toLocaleString('ar-EG', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    const enginesUsed = [...new Set(results.map(r => r.source).filter(Boolean))];
    const _rawAvg = stats.average_relevance
        || (results.length > 0
            ? results.reduce((s, r) => s + (r.relevance_score || 0), 0) / results.length
            : null);
    const avgRel = _rawAvg == null
        ? '—'
        : (_rawAvg <= 1.0
            ? (_rawAvg * 100).toFixed(1) + '%'
            : _rawAvg.toFixed(4) + ' (نقاط دلالية)');
    const totalWords  = stats.total_words_analyzed || 0;

    let text = '';

    // ═══════════════════════════════════════════════════════════════════════════
    //   HEADER BRAND BLOCK
    // ═══════════════════════════════════════════════════════════════════════════
    text += dbl();
    text += '  ██████╗  ██████╗  ██████╗ ████████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗\n';
    text += '  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║\n';
    text += '  ██████╔╝██║   ██║██║   ██║   ██║   ███████╗█████╗  ███████║██████╔╝██║     ███████║\n';
    text += '  ██╔══██╗██║   ██║██║   ██║   ██║   ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║\n';
    text += '  ██║  ██║╚██████╔╝╚██████╔╝   ██║   ███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║\n';
    text += '  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝\n';
    text += `  Deep Cognitive Search & Analysis System — Demo 1 T   |   نظام البحث والتحليل المعرفي العميق\n`;
    text += dbl() + '\n';

    // ═══════════════════════════════════════════════════════════════════════════
    //   TABLE OF CONTENTS
    // ═══════════════════════════════════════════════════════════════════════════
    text += subHeader('جَدْوَلُ المُحْتَوَيَاتِ  —  Table of Contents');
    text += `  [١]  البيانات المرجعية ومقاييس البحث\n`;
    text += `  [٢]  الملخص التنفيذي (إجابة الذكاء الاصطناعي الفورية)\n`;
    text += `  [٣]  التحليل المعرفي العميق — ROOTBASE\n`;
    text += `  [٤]  تحليل المشاعر والنبرة الوجدانية للمصادر\n`;
    text += `  [٥]  جدول المفاهيم والكلمات المفتاحية الإحصائي\n`;
    text += `  [٦]  التوزيع السياقي والجغرافي للمفاهيم\n`;
    text += `  [٧]  تصنيف المصادر حسب النطاق والفئة\n`;
    text += `  [٨]  قائمة المراجع الكاملة بالتفصيل\n`;
    text += `  [٩]  سجل مسار عملية البحث الحي\n`;
    text += `  [١٠] خريطة الترابط المعرفي والطوبولوجيا الهيكلية\n`;
    text += '\n\n';

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 1: SEARCH METRICS
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ١]  البيانات المرجعية ومقاييس البحث');
    text += `╔${rep('═', W - 2)}╗\n`;
    text += row(`الاستعلام        : "${queryStr}"`);
    text += row(`تاريخ التقرير    : ${timestamp}`);
    text += row(`نموذج البحث      : ${modelName}`);
    text += `╠${rep('═', W - 2)}╣\n`;
    text += row(`إجمالي المصادر   : ${totalRes} مصدر مُتتبَّع  |  فريد: ${uniqueRes} مصدر`);
    text += row(`المحركات المُستخدمة: ${enginesUsed.join('  •  ') || '—'}`);
    text += row(`زمن البحث الكلي  : ${searchTime}ث`);
    text += row(`متوسط درجة الصلة : ${avgRel}`);
    text += row(`إجمالي الكلمات   : ${totalWords.toLocaleString()} كلمة تم تحليلها دلالياً`);
    text += `╚${rep('═', W - 2)}╝\n\n\n`;

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 2: AI QUICK ANSWER / EXECUTIVE SUMMARY
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٢]  الملخص التنفيذي — إجابة الذكاء الاصطناعي الفورية');
    const aiAnswer = analysis.quick_answer
        || analysis.ai_answer
        || analysis.direct_answer?.answer
        || null;
    const summaryText = analysis.summary || analysis.executive_summary || '';

    if (aiAnswer) {
        text += `  [إجابة مباشرة]\n`;
        text += wrapText(aiAnswer, '  ');
        text += '\n';
    }
    if (summaryText && summaryText !== aiAnswer) {
        text += `  [الملخص الشامل]\n`;
        text += wrapText(summaryText, '  ');
    }
    if (!aiAnswer && !summaryText) {
        text += '  لم يتوفر ملخص ذكاء اصطناعي لهذا البحث.\n';
    }
    text += '\n\n';

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 3: ROOTBASE DEEP ANALYSIS
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٣]  التحليل المعرفي العميق — ROOTBASE');
    if (deepAnalysis && deepAnalysis.trim().length > 50) {
        // Strip any markdown formatting characters cleanly
        const cleaned = deepAnalysis
            .replace(/#{1,6}\s*/g, '')          // remove markdown headers
            .replace(/\*\*(.+?)\*\*/g, '[$1]')  // bold → brackets
            .replace(/\*(.+?)\*/g, '$1')         // italic → plain
            .replace(/>\s*/g, '  >> ')           // blockquote
            .replace(/\n{3,}/g, '\n\n');         // max 2 blank lines
        text += wrapText(cleaned.trim(), '  ');
    } else {
        // Dynamic Inductive Synthesis Fallback
        text += '  التحليل الاستقرائي التركيبي للمصادر النشطة (Dynamic Inductive Analysis):\n';
        text += '  ' + rep('╍', W - 4) + '\n';
        text += '  تم استخلاص هذا التحليل الهيكلي تلقائياً من تقاطع البيانات المستخرجة للمصادر المتوفرة:\n\n';
        
        const catKeysForFallback = Object.keys(categories).filter(c => categories[c]?.length > 0);
        if (catKeysForFallback.length > 0) {
            catKeysForFallback.forEach(cat => {
                text += `  ◄ تصنيف الفئة المعرفية [${cat.toUpperCase()}]:\n`;
                const srcs = categories[cat].slice(0, 2);
                srcs.forEach((src, sIdx) => {
                    const summary = src.ai_summary || src.summary || src.snippet || 'لا يتوفر مقتطف دلالي حالياً.';
                    text += `     (${sIdx + 1}) مصدر: "${src.title || src.url}"\n`;
                    text += wrapText(`         الخلاصة المرجعية: ${summary.trim()}`, '         ');
                    text += '\n';
                });
            });
        } else {
            text += '  لا توجد مصادر مرجعية مصنفة كافية لصياغة التحليل الاستقرائي.\n';
        }
    }
    text += '\n\n';

    // Topics / clusters if available
    if (topics && topics.length > 0) {
        text += subHeader('المحاور الموضوعية المكتشفة');
        topics.forEach((t, i) => {
            const label  = t.label || t.topic || `محور ${i + 1}`;
            const count  = t.count || t.size || 0;
            const desc   = t.description || t.summary || '';
            text += `  [${i + 1}] ${label}  (${count} مصدر)\n`;
            if (desc) text += wrapText(desc, '      ');
        });
        text += '\n';
    }

    // Named entities if available
    const entryTypes = { people: 'الأشخاص', orgs: 'المنظمات', places: 'الأماكن', dates: 'التواريخ', concepts: 'المفاهيم' };
    let hasEntities = false;
    for (const key of Object.keys(entryTypes)) {
        if (entities[key] && entities[key].length > 0) { hasEntities = true; break; }
    }
    if (hasEntities) {
        text += subHeader('الكيانات المُستخرجة (Named Entities)');
        for (const [key, label] of Object.entries(entryTypes)) {
            const list = entities[key] || [];
            if (list.length > 0) {
                text += `  ${label}: ${list.slice(0, 20).join('  •  ')}\n`;
            }
        }
        text += '\n';
    }
    text += '\n';

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 4: SENTIMENT ANALYSIS
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٤]  تحليل المشاعر والنبرة الوجدانية للمصادر');
    if (sentiment && sentiment.overall) {
        text += `╔${rep('═', W - 2)}╗\n`;
        text += row(`النبرة السائدة     : ${sentiment.overall}`);
        const obj  = sentiment.objectivity  || 0;
        const subj = sentiment.subjectivity || 0;
        const pos  = sentiment.positive     || 0;
        const neg  = sentiment.negative     || 0;
        const neu  = sentiment.neutral      || 0;
        text += `╠${rep('═', W - 2)}╣\n`;
        text += row(`الموضوعية         : ${(obj  * 100).toFixed(1)}%   ${bar(obj)}`);
        text += row(`الذاتية           : ${(subj * 100).toFixed(1)}%   ${bar(subj)}`);
        if (pos || neg || neu) {
            text += `╠${rep('═', W - 2)}╣\n`;
            text += row(`المشاعر الإيجابية : ${(pos * 100).toFixed(1)}%   ${bar(pos)}`);
            text += row(`المشاعر السلبية   : ${(neg * 100).toFixed(1)}%   ${bar(neg)}`);
            text += row(`المشاعر المحايدة  : ${(neu * 100).toFixed(1)}%   ${bar(neu)}`);
        }
        const emotions = sentiment.emotions || {};
        const emoMap = { trust:'الثقة', joy:'الفرح/الرضا', anticipation:'التوقع', surprise:'المفاجأة', anger:'الغضب', fear:'الخوف', sadness:'الحزن', disgust:'الاشمئزاز' };
        const foundEmotions = Object.entries(emoMap).filter(([k]) => emotions[k] != null);
        if (foundEmotions.length > 0) {
            text += `╠${rep('═', W - 2)}╣\n`;
            text += row('توزيع المشاعر الأساسية (Plutchik Wheel):');
            foundEmotions.forEach(([k, name]) => {
                const val = emotions[k] || 0;
                if (val > 0) text += row(`  ${padR(name, 16)} : ${(val * 100).toFixed(1)}%   ${bar(val)}`);
            });
        }
        text += `╚${rep('═', W - 2)}╝\n\n\n`;
    } else {
        text += '  لم يتوفر تحليل وجداني للمصادر في بيانات هذا الاستعلام.\n\n\n';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 5: KEYWORDS TABLE
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٥]  جدول المفاهيم والكلمات المفتاحية الإحصائي');
    if (keywords.length > 0) {

        // Column widths (total = W)
        const C1=4, C2=28, C3=12, C4=12, C5=12, C6=14; // 4+28+12+12+12+14 = 82  + 7 dividers = 89 ≈ W
        const hdr = `│ ${padR('رقم',C1)} │ ${padR('المفهوم / الكلمة',C2)} │ ${padR('التكرار',C3)} │ ${padR('الكثافة',C4)} │ ${padR('المصادر',C5)} │ ${padR('الترتيب',C6)} │`;
        const divTop = `┌${rep('─',C1+2)}┬${rep('─',C2+2)}┬${rep('─',C3+2)}┬${rep('─',C4+2)}┬${rep('─',C5+2)}┬${rep('─',C6+2)}┐`;
        const divMid = `├${rep('─',C1+2)}┼${rep('─',C2+2)}┼${rep('─',C3+2)}┼${rep('─',C4+2)}┼${rep('─',C5+2)}┼${rep('─',C6+2)}┤`;
        const divBot = `└${rep('─',C1+2)}┴${rep('─',C2+2)}┴${rep('─',C3+2)}┴${rep('─',C4+2)}┴${rep('─',C5+2)}┴${rep('─',C6+2)}┘`;

        text += divTop + '\n' + hdr + '\n' + divMid + '\n';

        keywords.forEach((kw, idx) => {
            const isObj = typeof kw === 'object' && kw !== null;
            const word   = isObj ? (kw.word || '—') : String(kw);
            const freq   = isObj ? String(kw.frequency   || '—') : '—';
            const dens   = isObj ? String(kw.density     || '—') : '—';
            const sites  = isObj ? String(kw.sites_count || '—') : '—';
            const rank   = padL(String(idx + 1), 4);
            text += `│ ${padR(rank,C1)} │ ${padR(word,C2)} │ ${padR(freq,C3)} │ ${padR(dens,C4)} │ ${padR(sites,C5)} │ ${padR('#' + (idx+1),C6)} │\n`;
            if (idx < keywords.length - 1) text += divMid + '\n';
        });
        text += divBot + '\n\n\n';
    } else {
        text += '  لم يتم رصد كلمات مفتاحية إحصائية كافية لتوليد الجدول المعرفي.\n\n\n';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 6: KEYWORD CONTEXTS & DISTRIBUTION
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٦]  التوزيع السياقي والجغرافي للمفاهيم');
    const kwWithContext = keywords.filter(k => typeof k === 'object' && k !== null && ((k.distribution && k.distribution.length > 0) || (k.contexts && k.contexts.length > 0)));
    if (kwWithContext.length > 0) {

        kwWithContext.forEach((kw, idx) => {
            text += `  ┌─── [${idx + 1}] المفهوم: "${kw.word}"  (${kw.frequency || 0} تكرار — ${kw.sites_count || 0} مصدر)\n`;

            if (kw.distribution && kw.distribution.length > 0) {
                text += `  │   التوزيع على المصادر:\n`;
                kw.distribution.slice(0, 8).forEach(d => {
                    const dots = rep('.', Math.max(2, 50 - String(d.site || '').length));
                    text += `  │     • ${d.site || '—'} ${dots} ${d.count} ظهور\n`;
                });
            }

            if (kw.contexts && kw.contexts.length > 0) {
                text += `  │   السياقات الدلالية الحية:\n`;
                kw.contexts.slice(0, 5).forEach((c, ci) => {
                    const isLast = ci === Math.min(4, kw.contexts.length - 1);
                    const branch = isLast ? '  └──' : '  ├──';
                    text += `  │  ${branch} "...${c.trim()}..."\n`;
                });
            }
            text += '  └' + rep('─', W - 4) + '\n\n';
        });
    } else {
        text += '  لا توجد بيانات توزيع سياقي للمفاهيم.\n\n\n';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 7: CATEGORIES TREE
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٧]  تصنيف المصادر حسب النطاق والفئة');
    const catEntries = Object.entries(categories).filter(([, v]) => Array.isArray(v) && v.length > 0);
    if (catEntries.length > 0) {

        catEntries.forEach(([catName, catResults]) => {
            text += `\n  [الفئة: ${catName.toUpperCase()}]  —  ${catResults.length} مصدر\n`;
            catResults.forEach((r, idx) => {
                const isLast  = idx === catResults.length - 1;
                const branch  = isLast ? '  └── ' : '  ├── ';
                const indent  = isLast ? '       ' : '  │    ';
                const relPct  = fmtScore(r.relevance_score, '—');
                text += `${branch}${r.title || r.url} [${r.source || '—'} | صلة: ${relPct}]\n`;
                text += `${indent}${r.url || '—'}\n`;
            });
        });
        text += '\n\n';
    } else {
        text += '  لا توجد مصادر مصنفة متوفرة حالياً.\n\n\n';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 8: FULL SOURCES LIST
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٨]  قائمة المراجع الكاملة بالتفصيل');
    if (results.length > 0) {

        results.forEach((r, i) => {
            const relPct  = fmtScore(r.relevance_score, '—');
            const aiSum   = r.ai_summary || r.summary || '';
            const snippet = r.snippet || '';

            text += `┌${rep('─', W - 2)}┐\n`;
            text += row(`[${i + 1}] ${r.title || r.url}`);
            text += `├${rep('─', W - 2)}┤\n`;
            text += row(`الرابط        : ${r.url}`);
            text += row(`المصدر        : ${r.source || '—'}   |   درجة الصلة: ${relPct}`);
            if (r.date || r.published_date) {
                text += row(`تاريخ النشر   : ${r.date || r.published_date}`);
            }
            if (aiSum && aiSum.trim().length > 10) {
                text += `├${rep('─', W - 2)}┤\n`;
                text += row('الملخص الذكي:');
                text += wrapText(aiSum.trim().replace(/\n/g, ' '), '  ');
            } else if (snippet && snippet.trim().length > 10) {
                text += `├${rep('─', W - 2)}┤\n`;
                text += row('المقتطف:');
                text += wrapText(snippet.trim().replace(/\n/g, ' '), '  ');
            }
            text += `└${rep('─', W - 2)}┘\n\n`;
        });
    } else {
        text += '  لا توجد مصادر مرجعية متوفرة حالياً.\n\n\n';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 9: LIVE SEARCH PATH LOG
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ٩]  سجل مسار عملية البحث الحي');
    if (searchPath.length > 0) {
        searchPath.forEach((step, i) => {
            const msg  = typeof step === 'string' ? step : (step.message || step.msg || JSON.stringify(step));
            const time = typeof step === 'object' ? (step.time || step.timestamp || '') : '';
            text += `  [${padL(String(i + 1), 3)}] ${time ? '[' + time + ']  ' : ''}${msg}\n`;
        });
    } else {
        text += '  لا توجد سجلات متوفرة لمسار البحث الحي لهذا الاستعلام.\n';
    }
    text += '\n\n';

    // ═══════════════════════════════════════════════════════════════════════════
    //   SECTION 10: ARCHITECTURAL KNOWLEDGE TOPOLOGY & RELATIONS
    // ═══════════════════════════════════════════════════════════════════════════
    text += sectionHeader('[قسم ١٠] خريطة الترابط المعرفي والطوبولوجيا الهيكلية (Knowledge Topology)');
    
    // 10.1 Dynamic Relational Topology Blueprint (Vertical Framed Layout)
    text += '\n  أولاً: مخطط خريطة العلاقات المعرفية والربط الهيكلي (Cognitive Adjacency Tree):\n';
    text += '  ' + rep('─', W - 4) + '\n\n';
    
    // Root Node Box
    const rootTitle = `الجذر الرئيسي: "${queryStr}"`;
    text += `  ┌${rep('─', W - 6)}┐\n`;
    text += `  │ ${padR(rootTitle, W - 8)} │\n`;
    text += `  └${rep('─', W - 6)}┘\n`;
    text += '         │\n';
    
    // Sentiment Node Box
    if (sentiment.overall) {
        const sentTitle = `المشـاعر الـعامـة: ${sentiment.overall} | موضوعية: ${sentiment.objectivity ? (sentiment.objectivity*100).toFixed(0)+'%' : '—'}`;
        text += '         ▼\n';
        text += `  ┌${rep('─', W - 6)}┐\n`;
        text += `  │ ${padR(sentTitle, W - 8)} │\n`;
        text += `  └${rep('─', W - 6)}┘\n`;
        text += '         │\n';
    }
    
    // Iterate over categories
    const catKeys = Object.keys(categories).filter(c => categories[c]?.length > 0);
    catKeys.forEach((cat, catIdx) => {
        text += '         ▼\n';
        
        // Outer category box width: W - 2 (e.g. 88)
        const outerWidth = W - 2;
        const innerWidth = outerWidth - 4; // 84
        
        // Category Header
        text += `┌${rep('─', outerWidth - 2)}┐\n`;
        text += `│ ${padR(`الفئة المعرفية: ${cat.toUpperCase()}`, innerWidth)} │\n`;
        text += `├${rep('─', outerWidth - 2)}┤\n`;
        
        const catSrcs = categories[cat].slice(0, 3); // top 3 sources
        catSrcs.forEach((r, rIdx) => {
            const isLastSrc = rIdx === catSrcs.length - 1;
            
            // Source Title & relevance
            const rTitle = r.title || r.url || 'مصدر مرجعي';
            const score = fmtScore(r.relevance_score, '—');
            const srcHeader = `العنوان: ${rTitle.slice(0, 42)} (${score})`;
            
            // Draw source box top
            text += `│  [مصدر] ──> ┌${rep('─', 63)}┐  │\n`;
            text += `│             │ ${padR(srcHeader, 61)} │  │\n`;
            text += `│             ├${rep('─', 63)}┤  │\n`;
            
            // Find keyword/entity matches in this source content
            const matches = [];
            const rContent = ((r.content || '') + (r.snippet || '') + (r.title || '')).toLowerCase();
            
            // Keywords matches
            keywords.slice(0, 5).forEach(kw => {
                const word = typeof kw === 'object' ? kw.word : String(kw);
                if (rContent.includes(word.toLowerCase())) {
                    matches.push({ type: 'دلالة', val: word });
                }
            });
            
            // Entities matches
            const personsList = (entities.persons || []).slice(0, 3);
            const orgsList = (entities.organizations || []).slice(0, 3);
            personsList.concat(orgsList).forEach(ent => {
                if (rContent.includes(ent.toLowerCase().slice(0, 10))) {
                    matches.push({ type: 'كيان', val: ent });
                }
            });
            
            // Draw matched child nodes inside source box
            const displayMatches = matches.slice(0, 3); // show up to 3 connections
            if (displayMatches.length > 0) {
                displayMatches.forEach((m, mIdx) => {
                    const isLastMatch = mIdx === displayMatches.length - 1;
                    const matchBranch = isLastMatch ? '└─ ' : '├─ ';
                    const matchText = `${matchBranch}[${m.type}]: ${m.val.slice(0, 38)}`;
                    text += `│             │ ${padR(matchText, 61)} │  │\n`;
                });
            } else {
                text += `│             │ ${padR('لا توجد تقاطعات دلالية مباشرة', 61)} │  │\n`;
            }
            
            // Draw source box bottom
            text += `│             └${rep('─', 63)}┘  │\n`;
            
            if (!isLastSrc) {
                text += `│                                                                                    │\n`;
            }
        });
        
        text += `└${rep('─', outerWidth - 2)}┘\n`;
        
        if (catIdx < catKeys.length - 1) {
            text += '         │\n';
        }
    });
    text += '\n\n';

    // 10.2 Cognitive Nodes Register
    text += '  ثانياً: سجل العقد المعرفية في الشبكة (Cognitive Nodes Register):\n';
    text += '  ' + rep('─', W - 4) + '\n';
    let nodeIndex = 1;
    text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: استعلام جذر]  "${queryStr}"\n`;
    if (sentiment.overall) {
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: نبرة مشاعر ]  "${sentiment.overall}" (موضوعية: ${sentiment.objectivity ? (sentiment.objectivity*100).toFixed(0)+'%' : '—'} | ذاتية: ${sentiment.subjectivity ? (sentiment.subjectivity*100).toFixed(0)+'%' : '—'})\n`;
    }
    catKeys.forEach(cat => {
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: فئة معرفية]  "${cat.toUpperCase()}" (تضم ${categories[cat].length} مصادر)\n`;
    });
    results.forEach((r, idx) => {
        const score = fmtScore(r.relevance_score, '—');
        const rTitle = r.title || r.url || `مصدر ${idx+1}`;
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: مصدر مرجعي ]  "${rTitle.slice(0, 50)}" [الصلة: ${score}] (حجم: ${r.content_length || r.metadata?.word_count || 0} ك)\n`;
    });
    const topKwsRegister = keywords.slice(0, 15);
    topKwsRegister.forEach(kw => {
        const word = typeof kw === 'object' ? kw.word : String(kw);
        const freq = typeof kw === 'object' ? kw.frequency : 1;
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: مصطلح دلالي]  "${word}" (تكرار: ${freq} مرات في التحليل)\n`;
    });
    
    // Add Entities to nodes
    const personsList = (entities.persons || []).slice(0, 5);
    const orgsList = (entities.organizations || []).slice(0, 5);
    const locsList = (entities.locations || []).slice(0, 5);
    
    personsList.forEach(p => {
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: كيان (شخص)  ]  "${p}"\n`;
    });
    orgsList.forEach(o => {
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: كيان (منظمة) ]  "${o}"\n`;
    });
    locsList.forEach(l => {
        text += `  [العقدة #${padL(String(nodeIndex++), 2)}] [نوع: كيان (موقع)  ]  "${l}"\n`;
    });
    text += '\n';

    // 10.3 Directed Edges Registry
    text += '  ثالثاً: سجل العلاقات والروابط المعرفية (Directed Knowledge Edges):\n';
    text += '  ' + rep('─', W - 4) + '\n';
    let edgeIndex = 1;
    if (sentiment.overall) {
        text += `  [${padL(String(edgeIndex++), 2)}] [استعلام جذر] ════(تحليل الانطباع)════> [تحليل مشاعر: ${sentiment.overall}]\n`;
    }
    catKeys.forEach(cat => {
        text += `  [${padL(String(edgeIndex++), 2)}] [استعلام جذر] ════(يُصنف تحت فئة)════> [فئة: ${cat.toUpperCase()}]\n`;
        categories[cat].forEach(r => {
            const rTitle = r.title || r.url || 'مصدر';
            const score = fmtScore(r.relevance_score, '—');
            text += `  [${padL(String(edgeIndex++), 2)}] [فئة: ${cat.toUpperCase()}] ════(يحتوي على مصدر)════> [مصدر: ${rTitle.slice(0, 30)}] (صلة: ${score})\n`;
        });
    });
    
    // Map keywords to sources
    keywords.slice(0, 10).forEach(kw => {
        const word = typeof kw === 'object' ? kw.word : String(kw);
        if (typeof kw === 'object' && kw.distribution) {
            kw.distribution.slice(0, 2).forEach(dist => {
                const matchSrc = results.find(r => r.url && r.url.includes(dist.site));
                if (matchSrc) {
                    text += `  [${padL(String(edgeIndex++), 2)}] [مصدر: ${(matchSrc.title||'').slice(0, 20)}] ════(يحتوي مصطلح)════> [دلالة: ${word}] (كرر: ${dist.count})\n`;
                }
            });
        }
    });
    text += '\n';

    // 10.4 Semantic Dissemination Matrix Grid (Keywords x Sources)
    text += '  رابعاً: مصفوفة الانتشار والترابط الدلالي للمصطلحات (Semantic Co-occurrence Matrix):\n';
    text += '  ' + rep('─', W - 4) + '\n';
    if (keywords.length > 0 && results.length > 0) {
        const matrixKws = keywords.slice(0, 12).map(k => typeof k === 'object' ? k.word : String(k));
        const matrixSrcs = results.slice(0, 5); // Max 5 columns
        
        const getDomain = (url) => {
            try {
                if (!url) return 'SOURCE';
                const domainStr = new URL(url).hostname.replace('www.', '');
                return domainStr.length > 10 ? domainStr.slice(0, 9) + '…' : domainStr;
            } catch (_) {
                return url ? (url.length > 10 ? url.slice(0, 9) + '…' : url) : 'SOURCE';
            }
        };

        // Print header row with actual domains
        let headerRow = '  ' + padR('المصطلحات الدلالية', 18) + '│';
        matrixSrcs.forEach((srcObj) => {
            const dom = getDomain(srcObj.url);
            headerRow += padC(dom, 12) + '│';
        });
        text += headerRow + '\n';
        text += '  ' + rep('─', 18) + '┼' + rep(rep('─', 12) + '┼', matrixSrcs.length) + '\n';
        
        // Pre-compute and cache lowercase contents
        const cachedContents = matrixSrcs.map((srcObj) => {
            return ((srcObj.content || '') + (srcObj.snippet || '')).toLowerCase();
        });

        // Print matrix content
        matrixKws.forEach(kw => {
            let rowText = '  ' + padR(kw, 18) + '│';
            const kwLower = kw.toLowerCase();
            matrixSrcs.forEach((_, sIdx) => {
                const contentText = cachedContents[sIdx];
                const count = contentText.split(kwLower).length - 1;
                if (count > 0) {
                    rowText += padC(`✓ (${count})`, 12) + '│';
                } else {
                    rowText += padC('—', 12) + '│';
                }
            });
            text += rowText + '\n';
        });
        
        text += '  ' + rep('─', 18) + '┴' + rep(rep('─', 12) + '┴', matrixSrcs.length) + '\n';
        
        // Print reference list of source index mapping
        text += '\n  * دليل المصادر والمراجع في المصفوفة (Source Catalog Legend):\n';
        matrixSrcs.forEach((srcObj) => {
            const dom = getDomain(srcObj.url);
            const title = srcObj.title || srcObj.url || 'مصدر مرجعي';
            text += `    [${padR(dom, 10)}] ──> "${title}" (${srcObj.url})\n`;
        });
    } else {
        text += '  لا توجد بيانات كافية لبناء مصفوفة الانتشار الدلالي.\n';
    }
    text += '\n\n';


    // ═══════════════════════════════════════════════════════════════════════════
    //   FOOTER
    // ═══════════════════════════════════════════════════════════════════════════
    text += bold();
    text += padC('تم إصدار هذا التقرير بواسطة محرك ROOTSEARCH', W) + '\n';
    text += padC('Deep Cognitive Search & Analysis System — Demo 1 T', W) + '\n';
    text += padC(`الاستعلام: "${queryStr}"  |  ${timestamp}`, W) + '\n';
    text += bold();

    const blob = new Blob(['\uFEFF' + text], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `rootsearch_report_${queryStr.replace(/\s+/g, '_').slice(0, 40)}_${Date.now()}.txt`);
    showToast('تم تصدير التقرير الشامل فائق الجودة بنجاح', 'success');
}
// ═══════════════════════════════════════════════════════════════════════════
//   ARCHITECTURAL TOPOLOGY EXPORT SYSTEM
//   Generates: interactive HTML (vis-network), GraphML, DOT/Graphviz
// ═══════════════════════════════════════════════════════════════════════════

function exportAsTopologyHTML() {
    if (!currentSearchData) { showToast('لا توجد بيانات للتصدير', 'error'); return; }

    const report    = currentSearchData;
    const analysis  = report.analysis || {};
    const results   = report.results  || [];
    const keywords  = analysis.keywords || analysis.top_keywords || [];
    const entities  = analysis.entities || {};
    // Build categorized links check to prevent orphaned sources
    const rawCategories = report.categories || {};
    const categories    = JSON.parse(JSON.stringify(rawCategories));
    const categorizedUrls = new Set();
    Object.values(categories).forEach(arr => {
        if (Array.isArray(arr)) {
            arr.forEach(r => { if (r.url) categorizedUrls.add(r.url); });
        }
    });
    const uncategorized = results.filter(r => !categorizedUrls.has(r.url));
    if (uncategorized.length > 0) {
        const otherKey = 'أخرى (OTHER)';
        if (!categories[otherKey]) categories[otherKey] = [];
        uncategorized.forEach(u => {
            if (!categories[otherKey].some(x => x.url === u.url)) {
                categories[otherKey].push(u);
            }
        });
    }
    const sentiment = analysis.sentiment_overview || {};
    const stats     = analysis.statistics || {};
    const queryStr  = report.query || '';
    const timestamp = new Date(report.timestamp || Date.now()).toLocaleString('ar-EG');

    // ── Build the Knowledge Graph ────────────────────────────────────────────
    let uid = 0;
    const newId = () => ++uid;
    const nodes = [];
    const edges = [];

    // ─ DEPTH 0 · Root Query Node ──────────────────────────────────────────
    const qid = newId();
    nodes.push({
        id: qid, label: queryStr.length > 35 ? queryStr.slice(0,33)+'…' : queryStr,
        fullLabel: queryStr,
        title: `<b>استعلام البحث</b><br>${queryStr}<br><hr>نتائج: ${results.length}<br>كلمات: ${(stats.total_words_analyzed||0).toLocaleString()}<br>زمن: ${stats.search_time ? stats.search_time+'ث' : '—'}`,
        group: 'query', size: 55, shape: 'star',
        font: { size: 16, face: 'Cairo, sans-serif', bold: { color: '#000', size: 16 } },
        borderWidth: 3, shadow: { enabled: true, size: 15, color: '#c9a84c80' }
    });

    // ─ DEPTH 1 · Category Nodes ───────────────────────────────────────────
    const catNodeIds = {};
    const catEntries = Object.entries(categories).filter(([,v]) => Array.isArray(v) && v.length > 0);
    catEntries.forEach(([catName, catItems]) => {
        const cid = newId();
        catNodeIds[catName] = cid;
        nodes.push({
            id: cid, label: catName.toUpperCase(),
            title: `<b>فئة معرفية</b><br>${catName}<br>المصادر: ${catItems.length}`,
            group: 'category', size: 28 + catItems.length * 2, shape: 'hexagon',
            font: { size: 12, face: 'Cairo, system-ui, sans-serif' }
        });
        edges.push({ from: qid, to: cid, width: 3, color: { color: '#6366f1cc', highlight: '#818cf8' },
            arrows: { to: { enabled: true, scaleFactor: 0.8 } }, title: `فئة: ${catName}`, smooth: { type: 'curvedCW', roundness: 0.2 } });
    });

    // ─ DEPTH 1 · Sentiment Aggregate Node ────────────────────────────────
    let sentNodeId = null;
    if (sentiment.overall) {
        const sid = newId();
        sentNodeId = sid;
        const sLabel = sentiment.overall.slice(0, 20);
        const sEmotions = Object.entries(sentiment.emotions || {})
            .sort(([,a],[,b]) => b - a).slice(0, 3)
            .map(([e, v]) => `${e}: ${(v*100).toFixed(0)}%`).join(' | ');
        nodes.push({
            id: sid, label: sLabel,
            title: `<b>تحليل المشاعر العام</b><br>النبرة: ${sentiment.overall}<br>موضوعية: ${sentiment.objectivity ? (sentiment.objectivity*100).toFixed(0)+'%' : '—'}<br>ذاتية: ${sentiment.subjectivity ? (sentiment.subjectivity*100).toFixed(0)+'%' : '—'}<br>${sEmotions}`,
            group: 'sentiment', size: 22, shape: 'diamond',
            font: { size: 11, face: 'Cairo, system-ui, sans-serif' }
        });
        edges.push({ from: qid, to: sid, width: 1.5, dashes: [6, 4],
            color: { color: '#a78bfa88' }, arrows: { to: { enabled: true, scaleFactor: 0.6 } }, title: 'انطباع وجداني' });
    }

    // ─ DEPTH 2 · Source / Result Nodes ────────────────────────────────────
    const srcNodeIds = {};
    const subqueryGroups = {};

    results.forEach((r, i) => {
        const rsid = newId();
        srcNodeIds[r.url || i] = rsid;
        const rel  = r.relevance_score || 1;
        const relSz = Math.max(14, Math.min(38, 12 + rel * 3));
        const metaInfo = [
            r.metadata?.word_count ? `الكلمات: ${r.metadata.word_count.toLocaleString()}` : '',
            r.metadata?.scraped ? 'تم الاستخراج الكامل' : '',
            r.metadata?.subquery ? `الاستعلام الفرعي: ${r.metadata.subquery}` : ''
        ].filter(Boolean).join('<br>');

        nodes.push({
            id: rsid,
            label: (r.title || r.url || `مصدر ${i+1}`).slice(0, 38),
            fullLabel: r.title || r.url,
            title: `<b>${r.title || r.url}</b><br><a href="${r.url}" style="color:#38bdf8">${r.url}</a><br>المصدر: ${r.source}<br>درجة الصلة: ${fmtScore(rel, '—')}<br>${metaInfo}`,
            group: 'source', size: relSz, shape: 'dot', url: r.url,
            font: { size: 10, face: 'Cairo, system-ui, sans-serif' }
        });

        // Group by subquery if available
        const sq = r.metadata?.subquery || r.metadata?.subquery_idx;
        if (sq !== undefined) {
            if (!subqueryGroups[sq]) subqueryGroups[sq] = [];
            subqueryGroups[sq].push(rsid);
        }

        // Find parent category
        const catName = Object.keys(categories).find(cat =>
            (categories[cat] || []).some(cr => cr.url === r.url));
        const parentId = catNodeIds[catName] || qid;
        edges.push({
            from: parentId, to: rsid,
            width: Math.max(0.5, Math.min(rel * 0.6, 4)),
            color: { color: '#22c55e99', highlight: '#22c55e' },
            arrows: { to: { enabled: true, scaleFactor: 0.7 } },
            title: `صلة: ${fmtScore(rel, '—')} | ${r.source}`,
            smooth: { type: 'dynamic' }
        });
    });

    // ─ DEPTH 2 · Subquery Cluster Nodes (discovery paths) ────────────────
    const sqNodeIds = {};
    Object.entries(subqueryGroups).forEach(([sq, srcs]) => {
        if (srcs.length < 2) return; // skip singletons
        const sqid = newId();
        sqNodeIds[sq] = sqid;
        nodes.push({
            id: sqid, label: String(sq).slice(0, 30),
            title: `<b>مسار البحث الفرعي</b><br>${sq}<br>${srcs.length} مصادر مكتشفة`,
            group: 'subquery', size: 18, shape: 'triangleDown',
            font: { size: 10, face: 'Cairo, system-ui, sans-serif' }
        });
        edges.push({ from: qid, to: sqid, width: 1, dashes: [4, 4],
            color: { color: '#64748b88' }, arrows: { to: { enabled: true, scaleFactor: 0.6 } }, title: 'مسار فرعي' });
        srcs.forEach(srcId => {
            edges.push({ from: sqid, to: srcId, width: 0.8, dashes: [3, 5],
                color: { color: '#64748b55' }, arrows: { to: { enabled: true, scaleFactor: 0.5 } } });
        });
    });

    // ─ DEPTH 3 · Top Keyword Nodes (top 30) ──────────────────────────────
    const kwNodeIds = {};
    const topKws = (Array.isArray(keywords) ? keywords : []).slice(0, 30);
    topKws.forEach((kw, i) => {
        const isObj = typeof kw === 'object' && kw !== null;
        const word  = isObj ? (kw.word || '') : String(kw);
        if (!word) return;
        const freq  = isObj ? (kw.frequency || 1) : 1;
        const sites = isObj ? (kw.sites_count || 1) : 1;
        const kwsz  = Math.max(8, Math.min(22, 6 + Math.log2(freq + 1) * 2.5));
        const kid   = newId();
        kwNodeIds[word] = kid;

        const ctxPreview = isObj && kw.contexts ? kw.contexts[0]?.slice(0, 120) + '…' : '';
        nodes.push({
            id: kid, label: word.slice(0, 22),
            title: `<b>كلمة مفتاحية</b><br>${word}<br>تكرار: ${freq}<br>مواقع: ${sites}<br><i>${ctxPreview}</i>`,
            group: 'keyword', size: kwsz, shape: 'box',
            font: { size: 9, face: 'Cairo, system-ui, sans-serif' }
        });

        // Connect keyword to the specific sources it appears in
        let connected = false;
        if (isObj && kw.distribution) {
            kw.distribution.slice(0, 4).forEach(d => {
                const matchSrc = results.find(r => r.url && (r.url.includes(d.site) || (d.url && r.url === d.url)));
                if (matchSrc) {
                    const sid = srcNodeIds[matchSrc.url || results.indexOf(matchSrc)];
                    if (sid) {
                        edges.push({ from: sid, to: kid,
                            width: Math.max(0.3, Math.min(d.count / 20, 2.5)),
                            color: { color: '#38bdf855', highlight: '#38bdf8' },
                            dashes: [3, 4],
                            arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                            title: `${d.count} ظهور في ${d.site}` });
                        connected = true;
                    }
                }
            });
        }
        if (!connected) {
            // fallback: connect to query
            edges.push({ from: qid, to: kid, width: 0.5, dashes: [2, 6],
                color: { color: '#38bdf833' }, arrows: { to: { enabled: true, scaleFactor: 0.4 } } });
        }
    });

    // ─ DEPTH 3 · Entity Nodes ─────────────────────────────────────────────
    // Pre-compute and cache lowercase haystacks for all results to prevent redundant O(N^2) CPU-heavy operations
    const cachedHaystacks = results.map(r => {
        return ((r.content || '') + (r.snippet || '') + (r.title || '')).toLowerCase();
    });

    const entConfig = {
        persons:       { group: 'person',   shape: 'circularImage', size: 15, maxN: 10 },
        organizations: { group: 'org',      shape: 'ellipse',       size: 14, maxN: 10 },
        locations:     { group: 'location', shape: 'triangle',      size: 14, maxN: 8  },
        dates:         { group: 'date',     shape: 'box',           size: 11, maxN: 6  }
    };
    Object.entries(entConfig).forEach(([key, cfg]) => {
        const ents = (entities[key] || []).slice(0, cfg.maxN);
        ents.forEach(ent => {
            const eid = newId();
            const entStr = String(ent);
            nodes.push({
                id: eid, label: entStr.slice(0, 22),
                title: `<b>كيان: ${key}</b><br>${entStr}`,
                group: cfg.group, size: cfg.size, shape: cfg.shape,
                font: { size: 9, face: 'Cairo, system-ui, sans-serif' }
            });
            // Try to find which sources mention this entity
            let linked = false;
            const entStrLower = entStr.toLowerCase().slice(0, 10);
            results.forEach((r, rIdx) => {
                const haystack = cachedHaystacks[rIdx];
                if (haystack.includes(entStrLower)) {
                    const sid = srcNodeIds[r.url || rIdx];
                    if (sid) {
                        edges.push({ from: sid, to: eid, width: 0.6, dashes: [2, 5],
                            color: { color: '#88888855' }, arrows: { to: { enabled: true, scaleFactor: 0.4 } },
                            title: `كيان في: ${r.title?.slice(0,40)}` });
                        linked = true;
                    }
                }
            });
            if (!linked) {
                edges.push({ from: qid, to: eid, width: 0.4, dashes: [2, 8],
                    color: { color: '#88888833' }, arrows: { to: { enabled: true, scaleFactor: 0.4 } } });
            }
        });
    });

    // ─ DEPTH 4 · Keyword–Keyword Co-occurrence Edges ─────────────────────
    // If two keywords appear in the same source, draw a thin semantic edge
    const kwList = Object.keys(kwNodeIds);
    const srcKwMap = {}; // url → [keyword_words]
    topKws.forEach(kw => {
        const isObj = typeof kw === 'object';
        const word  = isObj ? kw.word : String(kw);
        if (!isObj || !kw.distribution) return;
        kw.distribution.slice(0, 3).forEach(d => {
            const k = d.url || d.site;
            if (!srcKwMap[k]) srcKwMap[k] = [];
            srcKwMap[k].push(word);
        });
    });
    // For each source that has multiple keywords, add semantic edges between them
    Object.values(srcKwMap).forEach(words => {
        for (let i = 0; i < words.length - 1; i++) {
            for (let j = i + 1; j < words.length && j < i + 4; j++) {
                const k1 = kwNodeIds[words[i]], k2 = kwNodeIds[words[j]];
                if (k1 && k2) {
                    edges.push({ from: k1, to: k2, width: 0.3, dashes: [1, 6],
                        color: { color: '#38bdf822' }, smooth: { type: 'curvedCW', roundness: 0.5 },
                        title: `ترابط دلالي: ${words[i]} ↔ ${words[j]}` });
                }
            }
        }
    });

    // ── Assemble Summary Metadata ─────────────────────────────────────────
    const graphMeta = {
        query: queryStr, timestamp,
        totalNodes: nodes.length, totalEdges: edges.length,
        nodeBreakdown: {
            sources: results.length, keywords: topKws.length,
            categories: catEntries.length,
            entities: Object.values(entities).flat().length
        },
        avgRelevance: fmtScore(stats.average_relevance, '—'),
        totalWords: (stats.total_words_analyzed || 0).toLocaleString(),
        engines: [...new Set(results.map(r => r.source).filter(Boolean))].join(', '),
        deepAnalysis: (analysis.deep_analysis || '').slice(0, 800),
        aiSummary: (analysis.summary || analysis.executive_summary || '').slice(0, 600)
    };

    // ── Generate and Download the HTML ────────────────────────────────────
    const html = _buildTopologyHTML(nodes, edges, graphMeta);
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    downloadBlob(blob, `rootsearch_topology_${queryStr.replace(/\s+/g,'_').slice(0,40)}_${Date.now()}.html`);
    showToast(`تم تصدير خريطة الترابط المعرفي (${nodes.length} عقدة، ${edges.length} رابط)`, 'success');
}

// ─────────────────────────────────────────────────────────────────────────────
// BUILD TOPOLOGY HTML  (self-contained vis-network interactive graph)
// ─────────────────────────────────────────────────────────────────────────────
function _buildTopologyHTML(nodes, edges, meta) {
    const nodesJSON = JSON.stringify(nodes);
    const edgesJSON = JSON.stringify(edges);
    const metaJSON  = JSON.stringify(meta);

    return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RootSearch · Topology — ${meta.query}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"><\/script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{
    --bg:#090d16;--surface:#0f1624;--surface2:#151e30;--border:#1e2a3a;
    --text:#e2e8f0;--muted:#64748b;--accent:#c9a84c;--success:#22c55e;
    --info:#38bdf8;--purple:#a78bfa;--indigo:#6366f1;--orange:#fb923c;
    --red:#f87171;--yellow:#facc15;
  }
  html,body{width:100%;height:100%;background:var(--bg);color:var(--text);font-family:'Cairo',sans-serif;overflow:hidden}
  #app{display:flex;height:100vh;width:100vw}

  /* ── LEFT SIDEBAR ── */
  #sidebar{
    width:300px;min-width:220px;max-width:380px;background:var(--surface);
    border-left:1px solid var(--border);display:flex;flex-direction:column;
    overflow:hidden;z-index:10;resize:horizontal;flex-shrink:0;
  }
  #sidebar-header{
    padding:18px 16px 12px;border-bottom:1px solid var(--border);
    background:linear-gradient(135deg,#0f1624,#151e30);
  }
  .rs-logo{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;
    letter-spacing:0.08em;color:var(--accent)}
  .rs-sub{font-size:10px;color:var(--muted);letter-spacing:0.15em;text-transform:uppercase;margin-top:2px}
  .query-badge{
    margin-top:10px;padding:7px 10px;background:var(--surface2);border:1px solid var(--border);
    border-radius:6px;font-size:11px;color:var(--text);line-height:1.5;
    word-break:break-word;
  }
  #sidebar-body{flex:1;overflow-y:auto;padding:12px}
  #sidebar-body::-webkit-scrollbar{width:4px}
  #sidebar-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}

  /* Stats */
  .stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
  .stat-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
    padding:10px 8px;text-align:center}
  .stat-val{font-size:20px;font-weight:700;color:var(--accent);font-family:'JetBrains Mono',monospace}
  .stat-lbl{font-size:9px;color:var(--muted);margin-top:2px;letter-spacing:0.05em}

  /* Legend */
  .section-title{font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;
    color:var(--muted);padding:6px 0 8px;border-bottom:1px solid var(--border);margin-bottom:8px}
  .legend-item{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:11px;color:var(--text)}
  .legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;border:2px solid transparent}

  /* Controls */
  .ctrl-btn{
    width:100%;padding:8px 10px;margin-bottom:6px;background:var(--surface2);
    border:1px solid var(--border);border-radius:6px;color:var(--text);
    font-size:11px;font-family:'Cairo';cursor:pointer;text-align:center;
    transition:all 0.15s;
  }
  .ctrl-btn:hover{background:var(--border);border-color:var(--accent)}
  .ctrl-btn.active{border-color:var(--accent);color:var(--accent)}
  .slider-row{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:10px;color:var(--muted)}
  .slider-row input{flex:1;accent-color:var(--accent)}

  /* Search */
  #nodeSearch{
    width:100%;padding:7px 10px;background:var(--surface2);border:1px solid var(--border);
    border-radius:6px;color:var(--text);font-family:'Cairo';font-size:11px;
    margin-bottom:10px;outline:none;
  }
  #nodeSearch:focus{border-color:var(--accent)}
  #searchResults{max-height:120px;overflow-y:auto}
  .search-result{padding:4px 8px;font-size:10px;cursor:pointer;border-radius:4px;color:var(--muted)}
  .search-result:hover{background:var(--surface2);color:var(--text)}

  /* Node detail panel */
  #detail-panel{
    border-top:1px solid var(--border);padding:12px;background:var(--surface2);
    min-height:120px;max-height:220px;overflow-y:auto;font-size:11px;line-height:1.6;
  }
  #detail-panel a{color:var(--info);word-break:break-all}
  #detail-panel h4{color:var(--accent);margin-bottom:6px;font-size:12px}

  /* ── GRAPH CANVAS ── */
  #graph-wrap{flex:1;position:relative;overflow:hidden}
  #graph{width:100%;height:100%}

  /* Top bar */
  #topbar{
    position:absolute;top:0;left:0;right:0;height:44px;background:var(--surface);
    border-bottom:1px solid var(--border);display:flex;align-items:center;
    padding:0 16px;gap:12px;z-index:5;
  }
  .topbar-title{font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:700;
    color:var(--accent);letter-spacing:0.06em}
  .topbar-sep{width:1px;height:20px;background:var(--border)}
  .topbar-label{font-size:11px;color:var(--muted)}
  .topbar-val{font-size:11px;color:var(--text);margin-right:4px}
  .topbar-actions{margin-right:auto;display:flex;gap:8px}
  .tb-btn{padding:5px 12px;background:var(--surface2);border:1px solid var(--border);
    border-radius:5px;color:var(--text);font-size:10px;cursor:pointer;
    font-family:'Cairo';transition:all 0.15s}
  .tb-btn:hover{border-color:var(--accent);color:var(--accent)}

  /* Graph overlays */
  #minimap{position:absolute;bottom:12px;right:12px;width:160px;height:100px;
    border:1px solid var(--border);border-radius:6px;background:var(--surface);opacity:0.8;z-index:4}
  #depth-legend{position:absolute;bottom:12px;left:12px;background:var(--surface);
    border:1px solid var(--border);border-radius:6px;padding:10px;font-size:9px;z-index:4;color:var(--muted)}
  .dl-row{display:flex;align-items:center;gap:6px;margin-bottom:4px}
  .dl-num{width:18px;height:18px;border-radius:50%;background:var(--border);display:flex;
    align-items:center;justify-content:center;font-size:9px;font-weight:700;color:var(--accent)}

  /* Toast */
  #toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:var(--success);color:#000;padding:8px 20px;border-radius:20px;
    font-size:12px;display:none;z-index:999;font-family:'Cairo'}

  /* Group filter chips */
  .filter-chips{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
  .chip{padding:3px 8px;border-radius:12px;font-size:9px;cursor:pointer;border:1px solid;
    transition:all 0.15s;user-select:none}
  .chip.off{opacity:0.35}
</style>
</head>
<body>
<div id="app">

<!-- ═══ SIDEBAR ═══ -->
<div id="sidebar">
  <div id="sidebar-header">
    <div class="rs-logo">ROOTSEARCH</div>
    <div class="rs-sub">Architectural Knowledge Topology</div>
    <div class="query-badge" id="queryBadge"><!-- query --></div>
  </div>

  <div id="sidebar-body">

    <!-- Stats -->
    <div class="section-title">احصائيات الطوبولوجيا</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-val" id="sNodes">—</div><div class="stat-lbl">عقدة</div></div>
      <div class="stat-card"><div class="stat-val" id="sEdges">—</div><div class="stat-lbl">رابط</div></div>
      <div class="stat-card"><div class="stat-val" id="sSources">—</div><div class="stat-lbl">مصدر</div></div>
      <div class="stat-card"><div class="stat-val" id="sKeywords">—</div><div class="stat-lbl">كلمة مفتاحية</div></div>
    </div>

    <!-- Additional stats -->
    <div style="font-size:10px;color:var(--muted);margin-bottom:14px;line-height:1.8">
      <div>متوسط الصلة: <span style="color:var(--text)" id="sAvg">—</span></div>
      <div>إجمالي الكلمات: <span style="color:var(--text)" id="sWords">—</span></div>
      <div>محركات البحث: <span style="color:var(--text)" id="sEngines">—</span></div>
      <div>تاريخ التحليل: <span style="color:var(--text)" id="sDate">—</span></div>
    </div>

    <!-- Node type filters -->
    <div class="section-title">تصفية أنواع العقد</div>
    <div class="filter-chips" id="filterChips"></div>

    <!-- Layout controls -->
    <div class="section-title" style="margin-top:6px">التخطيط والفيزياء</div>
    <button class="ctrl-btn" onclick="setLayout('force')">تخطيط القوة الديناميكي</button>
    <button class="ctrl-btn" onclick="setLayout('hierarchical')">تخطيط هرمي (حسب العمق)</button>
    <button class="ctrl-btn" onclick="setLayout('radial')">تخطيط شعاعي من المركز</button>
    <button class="ctrl-btn" onclick="togglePhysics()">تبديل الفيزياء</button>
    <button class="ctrl-btn" onclick="fitAll()">ضبط العرض الكامل</button>

    <div class="slider-row">
      <span>جاذبية:</span>
      <input type="range" id="gravSlider" min="-5000" max="-50" value="-1200" step="50" oninput="updateGravity(this.value)">
      <span id="gravVal">-1200</span>
    </div>
    <div class="slider-row">
      <span>تنافر:</span>
      <input type="range" id="repSlider" min="0" max="400" value="150" step="10" oninput="updateRepulsion(this.value)">
      <span id="repVal">150</span>
    </div>

    <!-- Node search -->
    <div class="section-title" style="margin-top:6px">بحث عن عقدة</div>
    <input id="nodeSearch" type="text" placeholder="ابحث عن عقدة..." oninput="searchNodes(this.value)">
    <div id="searchResults"></div>

    <!-- Legend -->
    <div class="section-title" style="margin-top:6px">دليل الألوان</div>
    <div id="legendItems"></div>

  </div><!-- /sidebar-body -->

  <!-- Node detail -->
  <div id="detail-panel">
    <div style="color:var(--muted);font-size:11px">اضغط على أي عقدة لعرض تفاصيلها</div>
  </div>
</div><!-- /sidebar -->

<!-- ═══ GRAPH ═══ -->
<div id="graph-wrap">
  <div id="topbar">
    <span class="topbar-title">ROOTSEARCH · Knowledge Topology</span>
    <div class="topbar-sep"></div>
    <span class="topbar-label">الاستعلام:</span>
    <span class="topbar-val" id="tbQuery">—</span>
    <div class="topbar-sep"></div>
    <span class="topbar-label" id="tbEdges">—</span>
    <div class="topbar-actions">
      <button class="tb-btn" onclick="exportPNG()">تصدير PNG</button>
      <button class="tb-btn" onclick="toggleLabels()">تبديل التسميات</button>
      <button class="tb-btn" onclick="window.close()">إغلاق</button>
    </div>
  </div>
  <div id="graph" style="padding-top:44px"></div>

  <!-- Depth legend overlay -->
  <div id="depth-legend">
    <div style="font-size:9px;font-weight:700;margin-bottom:6px;color:var(--text)">أعماق الطوبولوجيا</div>
    <div class="dl-row"><div class="dl-num">0</div><span>استعلام البحث (الجذر)</span></div>
    <div class="dl-row"><div class="dl-num">1</div><span>الفئات / المشاعر</span></div>
    <div class="dl-row"><div class="dl-num">2</div><span>المصادر / النتائج</span></div>
    <div class="dl-row"><div class="dl-num">3</div><span>الكلمات / الكيانات</span></div>
    <div class="dl-row"><div class="dl-num">4</div><span>الترابط الدلالي</span></div>
  </div>
</div><!-- /graph-wrap -->

</div><!-- /app -->
<div id="toast"></div>

<script>
'use strict';

// ── Data ─────────────────────────────────────────────────────────────────────
const RAW_NODES = ${nodesJSON};
const RAW_EDGES = ${edgesJSON};
const META      = ${metaJSON};

// ── Group configuration ───────────────────────────────────────────────────────
const GROUPS = {
  query:     { color:{background:'#c9a84c',border:'#f5d76e',highlight:{background:'#f5d76e',border:'#c9a84c'}}, font:{color:'#000',size:15,bold:true}, shape:'star' },
  category:  { color:{background:'#1e1e40',border:'#6366f1',highlight:{background:'#6366f1',border:'#818cf8'}}, font:{color:'#818cf8',size:11}, shape:'hexagon' },
  source:    { color:{background:'#0d2010',border:'#22c55e',highlight:{background:'#22c55e33',border:'#22c55e'}}, font:{color:'#86efac',size:10} },
  keyword:   { color:{background:'#0a1e2d',border:'#38bdf8',highlight:{background:'#38bdf833',border:'#38bdf8'}}, font:{color:'#7dd3fc',size:9}, shape:'box' },
  person:    { color:{background:'#2d1515',border:'#f87171',highlight:{background:'#f8717133',border:'#f87171'}}, font:{color:'#fca5a5',size:9}, shape:'ellipse' },
  org:       { color:{background:'#2d1e10',border:'#fb923c',highlight:{background:'#fb923c33',border:'#fb923c'}}, font:{color:'#fdba74',size:9}, shape:'ellipse' },
  location:  { color:{background:'#2d2a10',border:'#facc15',highlight:{background:'#facc1533',border:'#facc15'}}, font:{color:'#fde047',size:9}, shape:'triangle' },
  date:      { color:{background:'#1a1a2d',border:'#94a3b8',highlight:{background:'#94a3b833',border:'#94a3b8'}}, font:{color:'#cbd5e1',size:9}, shape:'box' },
  sentiment: { color:{background:'#1e1530',border:'#a78bfa',highlight:{background:'#a78bfa33',border:'#a78bfa'}}, font:{color:'#c4b5fd',size:11}, shape:'diamond' },
  subquery:  { color:{background:'#151e30',border:'#64748b',highlight:{background:'#64748b33',border:'#94a3b8'}}, font:{color:'#94a3b8',size:9}, shape:'triangleDown' }
};

const LEGEND_LABELS = {
  query:'استعلام البحث (الجذر)', category:'فئة معرفية', source:'مصدر/نتيجة',
  keyword:'كلمة مفتاحية', person:'شخص', org:'منظمة',
  location:'موقع جغرافي', date:'تاريخ', sentiment:'تحليل مشاعر', subquery:'مسار بحث فرعي'
};

// ── State ─────────────────────────────────────────────────────────────────────
let network, nodesDS, edgesDS;
let physicsOn = true;
let labelsOn  = true;
const hiddenGroups = new Set();

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Populate meta
  document.getElementById('queryBadge').textContent = META.query;
  document.getElementById('tbQuery').textContent     = META.query.length > 50 ? META.query.slice(0,48)+'…' : META.query;
  document.getElementById('sNodes').textContent      = META.totalNodes;
  document.getElementById('sEdges').textContent      = META.totalEdges;
  document.getElementById('sSources').textContent    = META.nodeBreakdown.sources;
  document.getElementById('sKeywords').textContent   = META.nodeBreakdown.keywords;
  document.getElementById('sAvg').textContent        = META.avgRelevance;
  document.getElementById('sWords').textContent      = META.totalWords;
  document.getElementById('sEngines').textContent    = META.engines || '—';
  document.getElementById('sDate').textContent       = META.timestamp;
  document.getElementById('tbEdges').textContent     = META.totalNodes + ' عقدة | ' + META.totalEdges + ' رابط';

  buildLegend();
  buildFilterChips();
  initGraph();
});

function initGraph() {
  const container = document.getElementById('graph');

  nodesDS = new vis.DataSet(RAW_NODES);
  edgesDS = new vis.DataSet(RAW_EDGES);

  const options = {
    groups: GROUPS,
    nodes: {
      borderWidth: 1.5,
      shadow: { enabled: false },
      font: { face: 'Cairo, sans-serif', vadjust: 0 },
      chosen: { node: (values) => { values.shadowSize = 12; values.shadowColor = '#c9a84c60'; } }
    },
    edges: {
      smooth: { type: 'dynamic', roundness: 0.3 },
      selectionWidth: 3,
      hoverWidth: 2
    },
    physics: {
      enabled: true,
      forceAtlas2Based: {
        gravitationalConstant: -1200,
        centralGravity: 0.005,
        springLength: 160,
        springConstant: 0.04,
        damping: 0.4,
        avoidOverlap: 0.8
      },
      maxVelocity: 50,
      minVelocity: 0.1,
      solver: 'forceAtlas2Based',
      stabilization: { enabled: true, iterations: 800, updateInterval: 25 }
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      navigationButtons: true,
      keyboard: { enabled: true },
      zoomView: true
    },
    layout: { improvedLayout: true }
  };

  network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, options);

  network.on('click', onNodeClick);
  network.on('stabilizationProgress', (p) => {
    const pct = Math.round(p.iterations / p.total * 100);
    document.getElementById('tbEdges').textContent = 'جاري الاستقرار… ' + pct + '%';
  });
  network.on('stabilizationIterationsDone', () => {
    document.getElementById('tbEdges').textContent = META.totalNodes + ' عقدة | ' + META.totalEdges + ' رابط';
    network.setOptions({ physics: { stabilization: false } });
  });
}

function onNodeClick(params) {
  if (!params.nodes.length) { resetDetail(); return; }
  const nodeId = params.nodes[0];
  const node   = nodesDS.get(nodeId);
  if (!node) return;

  const groupCfg = GROUPS[node.group] || {};
  const borderColor = groupCfg.color?.border || '#888';

  const connectedEdges = network.getConnectedEdges(nodeId);
  const connectedNodes = network.getConnectedNodes(nodeId);

  let html = '<h4>' + (node.fullLabel || node.label) + '</h4>';
  html += '<div style="color:var(--muted);margin-bottom:6px">';
  html += 'النوع: <span style="color:' + borderColor + '">' + (LEGEND_LABELS[node.group] || node.group) + '</span> | ';
  html += 'الروابط: ' + connectedEdges.length + ' | العقد المتصلة: ' + connectedNodes.length;
  html += '</div>';
  if (node.url) html += '<div><a href="' + node.url + '" target="_blank">' + node.url + '</a></div>';

  // Focus in graph
  network.focus(nodeId, { scale: 1.4, animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
  network.selectNodes([nodeId]);
  document.getElementById('detail-panel').innerHTML = html;
}

function resetDetail() {
  document.getElementById('detail-panel').innerHTML = '<div style="color:var(--muted);font-size:11px">اضغط على أي عقدة لعرض تفاصيلها</div>';
}

// ── Layout Presets ─────────────────────────────────────────────────────────────
function setLayout(type) {
  if (type === 'hierarchical') {
    network.setOptions({
      layout: { hierarchical: { enabled: true, direction: 'UD', sortMethod: 'directed', levelSeparation: 160, nodeSpacing: 120 } },
      physics: { enabled: false }
    });
  } else if (type === 'radial') {
    network.setOptions({
      layout: { hierarchical: { enabled: true, direction: 'UD', sortMethod: 'hubsize', levelSeparation: 200 } },
      physics: { enabled: false }
    });
  } else {
    network.setOptions({
      layout: { hierarchical: { enabled: false } },
      physics: { enabled: true, solver: 'forceAtlas2Based' }
    });
  }
  network.fit({ animation: { duration: 800 } });
}

function togglePhysics() {
  physicsOn = !physicsOn;
  network.setOptions({ physics: { enabled: physicsOn } });
  showToast(physicsOn ? 'الفيزياء مفعّلة' : 'الفيزياء متوقفة');
}

function fitAll() {
  network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
}

function toggleLabels() {
  labelsOn = !labelsOn;
  const updated = nodesDS.get().map(n => ({ id: n.id, label: labelsOn ? (n.fullLabel || n._origLabel || n.label) : '' }));
  nodesDS.update(updated);
}

function updateGravity(val) {
  document.getElementById('gravVal').textContent = val;
  network.setOptions({ physics: { forceAtlas2Based: { gravitationalConstant: Number(val) } } });
}

function updateRepulsion(val) {
  document.getElementById('repVal').textContent = val;
  network.setOptions({ physics: { forceAtlas2Based: { avoidOverlap: Number(val) / 200 } } });
}

// ── Group Filters ─────────────────────────────────────────────────────────────
function buildFilterChips() {
  const groups = [...new Set(RAW_NODES.map(n => n.group))];
  const container = document.getElementById('filterChips');
  groups.forEach(g => {
    const borderColor = GROUPS[g]?.color?.border || '#888';
    const chip = document.createElement('div');
    chip.className = 'chip';
    chip.textContent = LEGEND_LABELS[g] || g;
    chip.style.borderColor = borderColor;
    chip.style.color = borderColor;
    chip.style.background = borderColor + '15';
    chip.title = 'إخفاء/إظهار: ' + (LEGEND_LABELS[g] || g);
    chip.onclick = () => toggleGroup(g, chip, borderColor);
    container.appendChild(chip);
  });
}

function toggleGroup(group, chip, color) {
  if (hiddenGroups.has(group)) {
    hiddenGroups.delete(group);
    chip.classList.remove('off');
    const ids = RAW_NODES.filter(n => n.group === group).map(n => n.id);
    nodesDS.update(ids.map(id => ({ id, hidden: false })));
  } else {
    hiddenGroups.add(group);
    chip.classList.add('off');
    const ids = RAW_NODES.filter(n => n.group === group).map(n => n.id);
    nodesDS.update(ids.map(id => ({ id, hidden: true })));
  }
}

// ── Legend ────────────────────────────────────────────────────────────────────
function buildLegend() {
  const container = document.getElementById('legendItems');
  const groups = [...new Set(RAW_NODES.map(n => n.group))];
  groups.forEach(g => {
    const borderColor = GROUPS[g]?.color?.border || '#888';
    const count = RAW_NODES.filter(n => n.group === g).length;
    const row = document.createElement('div');
    row.className = 'legend-item';
    row.innerHTML =
      '<div class="legend-dot" style="background:' + borderColor + '33;border-color:' + borderColor + '"></div>' +
      '<span>' + (LEGEND_LABELS[g] || g) + '</span>' +
      '<span style="margin-right:auto;color:var(--muted);font-family:monospace">' + count + '</span>';
    container.appendChild(row);
  });
}

// ── Node Search ───────────────────────────────────────────────────────────────
function searchNodes(val) {
  const container = document.getElementById('searchResults');
  container.innerHTML = '';
  if (!val || val.length < 2) return;
  const q = val.toLowerCase();
  const matches = RAW_NODES.filter(n =>
    (n.label||'').toLowerCase().includes(q) ||
    (n.fullLabel||'').toLowerCase().includes(q)
  ).slice(0, 10);
  matches.forEach(n => {
    const div = document.createElement('div');
    div.className = 'search-result';
    div.textContent = n.fullLabel || n.label;
    div.onclick = () => {
      network.focus(n.id, { scale: 1.8, animation: { duration: 500 } });
      network.selectNodes([n.id]);
      onNodeClick({ nodes: [n.id] });
    };
    container.appendChild(div);
  });
  if (!matches.length) {
    container.innerHTML = '<div style="color:var(--muted);font-size:10px;padding:4px 8px">لا توجد نتائج</div>';
  }
}

// ── Export PNG ────────────────────────────────────────────────────────────────
function exportPNG() {
  const canvas = document.querySelector('#graph canvas');
  if (!canvas) { showToast('تعذّر التصدير'); return; }
  const link = document.createElement('a');
  link.download = 'rootsearch_topology.png';
  link.href = canvas.toDataURL('image/png');
  link.click();
  showToast('تم تصدير الصورة');
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => { t.style.display = 'none'; }, 2500);
}
<\/script>
</body>
</html>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// GRAPHML EXPORT  (for yEd, Gephi, Cytoscape)
// ─────────────────────────────────────────────────────────────────────────────
function exportAsGraphML() {
    if (!currentSearchData) { showToast('لا توجد بيانات للتصدير', 'error'); return; }

    const report    = currentSearchData;
    const analysis  = report.analysis || {};
    const results   = report.results  || [];
    const keywords  = analysis.keywords || [];
    const entities  = analysis.entities || {};
    // Build categorized links check to prevent orphaned sources
    const rawCategories = report.categories || {};
    const categories    = JSON.parse(JSON.stringify(rawCategories));
    const categorizedUrls = new Set();
    Object.values(categories).forEach(arr => {
        if (Array.isArray(arr)) {
            arr.forEach(r => { if (r.url) categorizedUrls.add(r.url); });
        }
    });
    const uncategorized = results.filter(r => !categorizedUrls.has(r.url));
    if (uncategorized.length > 0) {
        const otherKey = 'أخرى (OTHER)';
        if (!categories[otherKey]) categories[otherKey] = [];
        uncategorized.forEach(u => {
            if (!categories[otherKey].some(x => x.url === u.url)) {
                categories[otherKey].push(u);
            }
        });
    }
    const queryStr  = report.query || '';

    const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    let gNodes = '';
    let gEdges = '';
    let uid = 0;
    const nid = () => 'n' + (++uid);
    const eid = () => 'e' + (++uid);
    const nodeIds = {};

    const addNode = (id, label, type, size, url, desc) => {
        nodeIds[id] = id;
        gNodes += `  <node id="${esc(id)}"><data key="label">${esc(label)}</data><data key="type">${esc(type)}</data><data key="size">${size||10}</data><data key="url">${esc(url||'')}</data><data key="desc">${esc((desc||'').slice(0,200))}</data></node>\n`;
    };
    const addEdge = (from, to, rel, weight) => {
        gEdges += `  <edge id="${eid()}" source="${esc(from)}" target="${esc(to)}"><data key="relation">${esc(rel)}</data><data key="weight">${weight||1}</data></edge>\n`;
    };

    // Query node
    const qid = 'query_root';
    addNode(qid, queryStr, 'query', 50, '', `استعلام: ${queryStr}`);

    // Category nodes
    const catIds = {};
    Object.entries(categories).forEach(([cat, items]) => {
        if (!Array.isArray(items) || !items.length) return;
        const cid = 'cat_' + cat.replace(/\s+/g,'_');
        catIds[cat] = cid;
        addNode(cid, cat, 'category', 25, '', `فئة: ${cat} | ${items.length} مصادر`);
        addEdge(qid, cid, 'has_category', 3);
    });

    // Result nodes
    const srcIds = {};
    results.forEach((r, i) => {
        const sid = 'src_' + i;
        srcIds[r.url || i] = sid;
        addNode(sid, r.title || r.url || `مصدر ${i+1}`, 'source',
            Math.round(10 + (r.relevance_score||1)*3), r.url||'',
            `${r.title}\n${r.url}\nصلة: ${fmtScore(r.relevance_score,'—')}`);
        const catName = Object.keys(categories).find(c => (categories[c]||[]).some(cr => cr.url === r.url));
        addEdge(catIds[catName] || qid, sid, 'contains_source', r.relevance_score||1);
    });

    // Keyword nodes
    (Array.isArray(keywords)?keywords:[]).slice(0,25).forEach((kw, i) => {
        const isObj = typeof kw === 'object';
        const word  = isObj ? kw.word : String(kw);
        const freq  = isObj ? (kw.frequency||1) : 1;
        const kid   = 'kw_' + i;
        addNode(kid, word, 'keyword', Math.round(8 + Math.log(freq+1)*2), '', `تكرار: ${freq}`);
        if (isObj && kw.distribution) {
            kw.distribution.slice(0,3).forEach(d => {
                const matchSrc = results.find(r => r.url && r.url.includes(d.site));
                if (matchSrc) addEdge(srcIds[matchSrc.url||results.indexOf(matchSrc)], kid, 'contains_keyword', d.count);
                else addEdge(qid, kid, 'has_keyword', freq);
            });
        } else {
            addEdge(qid, kid, 'has_keyword', freq);
        }
    });

    // Entity nodes
    const entTypes = { persons:'person', organizations:'org', locations:'location', dates:'date' };
    Object.entries(entTypes).forEach(([key, type]) => {
        (entities[key]||[]).slice(0,8).forEach((ent, i) => {
            const eid2 = `ent_${type}_${i}`;
            addNode(eid2, String(ent), type, 12, '', `كيان ${key}: ${ent}`);
            addEdge(qid, eid2, 'has_entity', 1);
        });
    });

    // Sentiment node
    const sent = analysis.sentiment_overview || {};
    if (sent.overall) {
        addNode('sentiment_root', sent.overall, 'sentiment', 18, '', `مشاعر: ${sent.overall}`);
        addEdge(qid, 'sentiment_root', 'has_sentiment', 2);
    }

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<!-- RootSearch Knowledge Graph — GraphML Export -->
<!-- Query: ${esc(queryStr)} -->
<!-- Nodes: ${uid} | Generated: ${new Date().toISOString()} -->
<graphml xmlns="http://graphml.graphdrawing.org/graphml"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://graphml.graphdrawing.org/graphml http://graphml.graphdrawing.org/graphml/graphml.xsd">

  <key id="label"    for="node" attr.name="label"    attr.type="string"/>
  <key id="type"     for="node" attr.name="type"     attr.type="string"/>
  <key id="size"     for="node" attr.name="size"     attr.type="double"/>
  <key id="url"      for="node" attr.name="url"      attr.type="string"/>
  <key id="desc"     for="node" attr.name="desc"     attr.type="string"/>
  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>
  <key id="weight"   for="edge" attr.name="weight"   attr.type="double"/>

  <graph id="RootSearchKnowledge" edgedefault="directed">
${gNodes}${gEdges}  </graph>
</graphml>`;

    const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' });
    downloadBlob(blob, `rootsearch_topology_${queryStr.replace(/\s+/g,'_').slice(0,40)}_${Date.now()}.graphml`);
    showToast('تم تصدير GraphML (يفتح في yEd / Gephi / Cytoscape)', 'success');
}

// ─────────────────────────────────────────────────────────────────────────────
// DOT / GRAPHVIZ EXPORT  (.gv file — renders with Graphviz or Kroki.io)
// ─────────────────────────────────────────────────────────────────────────────
function exportAsDOT() {
    if (!currentSearchData) { showToast('لا توجد بيانات للتصدير', 'error'); return; }

    const report    = currentSearchData;
    const analysis  = report.analysis || {};
    const results   = report.results  || [];
    const keywords  = analysis.keywords || [];
    const entities  = analysis.entities || {};
    // Build categorized links check to prevent orphaned sources
    const rawCategories = report.categories || {};
    const categories    = JSON.parse(JSON.stringify(rawCategories));
    const categorizedUrls = new Set();
    Object.values(categories).forEach(arr => {
        if (Array.isArray(arr)) {
            arr.forEach(r => { if (r.url) categorizedUrls.add(r.url); });
        }
    });
    const uncategorized = results.filter(r => !categorizedUrls.has(r.url));
    if (uncategorized.length > 0) {
        const otherKey = 'أخرى (OTHER)';
        if (!categories[otherKey]) categories[otherKey] = [];
        uncategorized.forEach(u => {
            if (!categories[otherKey].some(x => x.url === u.url)) {
                categories[otherKey].push(u);
            }
        });
    }
    const queryStr  = report.query || '';

    const esc  = s => String(s||'').replace(/"/g,'\\"').replace(/\n/g,' ').replace(/[<>]/g,'');
    const nid  = s => '"' + esc(s).slice(0,60) + '"';

    let dot = `digraph RootSearchTopology {\n`;
    dot += `  // RootSearch Knowledge Topology — DOT Export\n`;
    dot += `  // Query: ${esc(queryStr)}\n`;
    dot += `  // Generated: ${new Date().toISOString()}\n\n`;
    dot += `  graph [rankdir=TB bgcolor="#090d16" fontname="Cairo" label="${esc(queryStr)}" labelloc=t fontsize=18 fontcolor="#c9a84c"]\n`;
    dot += `  node  [fontname="Cairo" style=filled penwidth=1.5]\n`;
    dot += `  edge  [fontname="Cairo" fontsize=9]\n\n`;

    // Node style macros
    const styleMap = {
        query:     'shape=star fillcolor="#c9a84c" fontcolor="#000" color="#f5d76e" width=1.5 fontsize=14',
        category:  'shape=hexagon fillcolor="#1e1e40" fontcolor="#818cf8" color="#6366f1"',
        source:    'shape=ellipse fillcolor="#0d2010" fontcolor="#86efac" color="#22c55e"',
        keyword:   'shape=box fillcolor="#0a1e2d" fontcolor="#7dd3fc" color="#38bdf8" style="filled,rounded"',
        person:    'shape=oval fillcolor="#2d1515" fontcolor="#fca5a5" color="#f87171"',
        org:       'shape=oval fillcolor="#2d1e10" fontcolor="#fdba74" color="#fb923c"',
        location:  'shape=triangle fillcolor="#2d2a10" fontcolor="#fde047" color="#facc15"',
        sentiment: 'shape=diamond fillcolor="#1e1530" fontcolor="#c4b5fd" color="#a78bfa"',
    };

    // Node declarations
    dot += `  // ─── Query Root\n`;
    dot += `  ${nid(queryStr)} [${styleMap.query} label="${esc(queryStr.slice(0,40))}" width=2]\n\n`;

    dot += `  // ─── Category Nodes\n`;
    const catUsed = {};
    Object.entries(categories).forEach(([cat, items]) => {
        if (!Array.isArray(items) || !items.length) return;
        catUsed[cat] = true;
        dot += `  ${nid('CAT:'+cat)} [${styleMap.category} label="${esc(cat.toUpperCase())}"]\n`;
        dot += `  ${nid(queryStr)} -> ${nid('CAT:'+cat)} [color="#6366f1" penwidth=2]\n`;
    });

    dot += `\n  // ─── Source Nodes\n`;
    results.forEach((r, i) => {
        const lbl = esc((r.title||r.url||'').slice(0,45));
        const rel  = (r.relevance_score || 1).toFixed(2);
        dot += `  ${nid('SRC:'+i)} [${styleMap.source} label="${lbl}\\n${fmtScore(r.relevance_score,'—')}"]\n`;
        const catName = Object.keys(categories).find(c => (categories[c]||[]).some(cr => cr.url === r.url));
        const parent  = catName ? nid('CAT:'+catName) : nid(queryStr);
        dot += `  ${parent} -> ${nid('SRC:'+i)} [color="#22c55e55" penwidth=${Math.min(rel,3)} label="${rel} pts"]\n`;
    });

    dot += `\n  // ─── Keyword Nodes\n`;
    dot += `  subgraph cluster_keywords {\n    label="الكلمات المفتاحية" color="#38bdf833" style=dashed fontcolor="#38bdf8"\n`;
    (Array.isArray(keywords)?keywords:[]).slice(0,20).forEach((kw, i) => {
        const isObj = typeof kw === 'object';
        const word  = esc(isObj ? kw.word : String(kw));
        const freq  = isObj ? (kw.frequency||1) : 1;
        dot += `    ${nid('KW:'+i)} [${styleMap.keyword} label="${word}\\n×${freq}"]\n`;
        if (isObj && kw.distribution) {
            const d = kw.distribution[0];
            const matchSrc = results.findIndex(r => r.url && r.url.includes(d?.site||''));
            if (matchSrc >= 0) dot += `    ${nid('SRC:'+matchSrc)} -> ${nid('KW:'+i)} [color="#38bdf833" style=dashed]\n`;
            else dot += `    ${nid(queryStr)} -> ${nid('KW:'+i)} [color="#38bdf822" style=dotted]\n`;
        } else {
            dot += `    ${nid(queryStr)} -> ${nid('KW:'+i)} [color="#38bdf822" style=dotted]\n`;
        }
    });
    dot += `  }\n`;

    dot += `\n  // ─── Entity Nodes\n`;
    [['persons','person'],['organizations','org'],['locations','location']].forEach(([key,type]) => {
        const ents = (entities[key]||[]).slice(0,6);
        if (!ents.length) return;
        dot += `  subgraph cluster_${type} {\n    label="${key}" color="#88888833" style=dashed fontcolor="#888"\n`;
        ents.forEach((ent, i) => {
            dot += `    ${nid('ENT:'+type+i)} [${styleMap[type]||styleMap.org} label="${esc(String(ent).slice(0,25))}"]\n`;
            dot += `    ${nid(queryStr)} -> ${nid('ENT:'+type+i)} [color="#88888833" style=dashed]\n`;
        });
        dot += `  }\n`;
    });

    // Sentiment
    const sent = analysis.sentiment_overview || {};
    if (sent.overall) {
        dot += `\n  // ─── Sentiment Node\n`;
        dot += `  ${nid('SENT:'+sent.overall)} [${styleMap.sentiment} label="${esc(sent.overall)}"]\n`;
        dot += `  ${nid(queryStr)} -> ${nid('SENT:'+sent.overall)} [color="#a78bfa55" style=dashed penwidth=1.5]\n`;
    }

    dot += `}\n`;

    const blob = new Blob([dot], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `rootsearch_topology_${queryStr.replace(/\s+/g,'_').slice(0,40)}_${Date.now()}.gv`);
    showToast('تم تصدير DOT/Graphviz — افتح بـ Graphviz أو Kroki.io', 'success');
}

// ─────────────────────────────────────────────────────────────────────────────

function exportAsHTMLReport() {

    if (!currentSearchData) { showToast('لا توجد بيانات', 'error'); return; }
    const cards = (currentSearchData.results || []).map(r => `
        <div style="border:1px solid #2E3344;border-radius:8px;padding:16px;margin-bottom:12px;background:#13161C">
            <h3 style="margin:0 0 6px;color:#E2E6EF"><a href="${r.url}" style="color:#4A6CF7">${r.title}</a></h3>
            <div style="font-size:11px;color:#4A5266;margin-bottom:8px">${r.url}</div>
            <p style="font-size:13px;color:#7E8799;margin:0">${r.snippet}</p>
        </div>`).join('');
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>RootSearch — ${escapeHtml(currentQuery)}</title>
        <style>body{font-family:Inter,sans-serif;background:#0B0D10;color:#E2E6EF;max-width:900px;margin:0 auto;padding:32px}a{color:#4A6CF7}</style>
        </head><body><h1>RootSearch Report: ${escapeHtml(currentQuery)}</h1><p>تم العثور على ${formatScaryCount(currentSearchData.total_results || 0)} مصدر</p>${cards}</body></html>`;
    const blob = new Blob([html], { type: 'text/html' });
    downloadBlob(blob, `rootsearch_${Date.now()}.html`);
    showToast('تم تصدير HTML', 'success');
}

function downloadBlob(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

// ─── UTILITY ──────────────────────────────────────────────────
function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

function decodeHtml(html) {
    if (!html) return '';
    const txt = document.createElement('textarea');
    txt.innerHTML = html;
    return txt.value;
}

function getUrlId(url) {
    if (!url) return '';
    let hash = 0;
    for (let i = 0; i < url.length; i++) {
        hash = (hash << 5) - hash + url.charCodeAt(i);
        hash |= 0;
    }
    return 'node_' + Math.abs(hash).toString(36);
}

function toggleModelDropdown() {
    const wrap = document.querySelector('.model-dropdown-wrap');
    if (!wrap) return;
    const isOpen = wrap.classList.contains('open');
    if (isOpen) {
        wrap.classList.remove('open');
        document.getElementById('modelDropdownTrigger')?.setAttribute('aria-expanded', 'false');
    } else {
        wrap.classList.add('open');
        document.getElementById('modelDropdownTrigger')?.setAttribute('aria-expanded', 'true');
    }
}

function selectDropdownModel(model) {
    const input = document.getElementById('searchModelInput');
    const triggerIcon = document.querySelector('.model-dropdown-trigger .dropdown-icon-active');
    const triggerLabel = document.querySelector('.model-dropdown-trigger .dropdown-label-active');
    const wrap = document.querySelector('.model-dropdown-wrap');
    
    if (input) input.value = model;
    localStorage.setItem('selectedSearchModel', model);

    // Update active class in items
    document.querySelectorAll('.model-dropdown-item').forEach(item => {
        const isTarget = item.getAttribute('data-value') === model;
        item.classList.toggle('active', isTarget);
        item.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });

    // Update wrap model selection class
    if (wrap) {
        wrap.classList.toggle('fathom-max-selected', model === 'fathom_max');
        const capsule = wrap.closest('.search-input-capsule');
        if (capsule) {
            capsule.classList.toggle('fathom-max-selected', model === 'fathom_max');
        }
        const form = wrap.closest('#searchForm');
        if (form) {
            form.classList.toggle('fathom-max-selected', model === 'fathom_max');
        }
    }

    // Update trigger UI
    if (model === 'fathom_s1') {
        if (triggerIcon) {
            triggerIcon.className = 'fas fa-bolt dropdown-icon-active';
        }
        if (triggerLabel) triggerLabel.textContent = 'S1';
    } else {
        if (triggerIcon) {
            triggerIcon.className = 'fas fa-spider dropdown-icon-active';
        }
        if (triggerLabel) triggerLabel.textContent = 'Max';
    }

    // Close dropdown
    if (wrap) {
        wrap.classList.remove('open');
        document.getElementById('modelDropdownTrigger')?.setAttribute('aria-expanded', 'false');
    }
    updateEngineCounter();

    // Re-sync K-Trust status hint color if K-Trust is active
    if (isKTrustedActive) {
        const statusHint = document.getElementById('ktStatusHint');
        if (statusHint) {
            if (model === 'fathom_max') {
                statusHint.classList.add('fathom-max');
            } else {
                statusHint.classList.remove('fathom-max');
            }
        }
    }
}

// Close dropdown on click outside
document.addEventListener('click', e => {
    const wrap = document.querySelector('.model-dropdown-wrap');
    if (wrap && !wrap.contains(e.target)) {
        wrap.classList.remove('open');
        document.getElementById('modelDropdownTrigger')?.setAttribute('aria-expanded', 'false');
    }
});

// Restore last used model from localStorage
function initModelSelector() {
    const savedModel = localStorage.getItem('selectedSearchModel');
    if (savedModel) {
        selectDropdownModel(savedModel);
    }
}

function makeSheetSwipable(sheetId, closeCallback) {
    const sheet = document.getElementById(sheetId);
    if (!sheet) return;

    let startY = 0;
    let currentY = 0;
    let isDragging = false;

    sheet.addEventListener('touchstart', e => {
        startY = e.touches[0].clientY;
        isDragging = true;
        sheet.style.transition = 'none';
    }, { passive: true });

    sheet.addEventListener('touchmove', e => {
        if (!isDragging) return;
        currentY = e.touches[0].clientY;
        const deltaY = currentY - startY;
        if (deltaY > 0) {
            sheet.style.transform = `translateY(${deltaY}px)`;
        }
    }, { passive: true });

    sheet.addEventListener('touchend', e => {
        if (!isDragging) return;
        isDragging = false;
        sheet.style.transition = '';
        
        const deltaY = currentY - startY;
        if (deltaY > 100) {
            closeCallback();
        }
        sheet.style.transform = '';
        startY = 0;
        currentY = 0;
    });
}

function openFilterSheet() {
    const sheet = document.getElementById('filterSheet');
    const backdrop = document.getElementById('filterSheetBackdrop');
    if (sheet) { sheet.classList.add('open'); sheet.setAttribute('aria-hidden', 'false'); }
    if (backdrop) backdrop.style.display = 'block';
}

function closeFilterSheet() {
    const sheet = document.getElementById('filterSheet');
    const backdrop = document.getElementById('filterSheetBackdrop');
    if (sheet) { sheet.classList.remove('open'); sheet.setAttribute('aria-hidden', 'true'); }
    if (backdrop) backdrop.style.display = 'none';
}

function selectMobileCategory(cat) {
    const btnMock = document.createElement('button');
    filterByCategory(cat, btnMock);
    closeFilterSheet();
}

function toggleThinkingBox() {
    const box = document.getElementById('daThinkingBox');
    const content = document.getElementById('daThinkingContent');
    const chevron = document.getElementById('daThinkingChevron');
    if (!box || !content || !chevron) return;
    
    const isExpanded = box.classList.contains('is-expanded');
    if (isExpanded) {
        box.classList.remove('is-expanded');
        content.style.display = 'none';
    } else {
        box.classList.add('is-expanded');
        content.style.display = 'block';
    }
}

function toggleReportThinking() {
    const box = document.getElementById('reportThinkingBox');
    const content = document.getElementById('reportThinkingContent');
    const chevron = document.getElementById('reportThinkingChevron');
    if (!box || !content || !chevron) return;
    
    const isExpanded = box.classList.contains('is-expanded');
    if (isExpanded) {
        box.classList.remove('is-expanded');
        content.style.display = 'none';
    } else {
        box.classList.add('is-expanded');
        content.style.display = 'block';
    }
}
