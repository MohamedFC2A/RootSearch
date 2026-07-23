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
    fathom_s1_max_sources: 200,
    fathom_max_nodes: 600,
    fathom_max_concurrency: 12
};

// Live Tree state
const treeNodes = new Map();  // nodeId → DOM element
let liveTreeNodes = null;
let liveTreeEdges = null;
let liveTreeNetwork = null;
let currentTreeViewMode = 'visual'; // 'visual' | 'linear'
let activeInspectedNodeId = null;
let userClickedInspectorNode = false;



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

    // Initialize count-up animation for stats
    initCountUpCounters();

    // Check if there is an immediate query redirected from `/compare`
    const immediateQuery = localStorage.getItem('runImmediateQuery');
    if (immediateQuery) {
        localStorage.removeItem('runImmediateQuery');
        const selectedModel = localStorage.getItem('selectedSearchModel') || 'fathom_s1';
        
        // Wait a small delay to make sure UI is fully loaded
        setTimeout(() => {
            runQuickQuery(immediateQuery, selectedModel);
        }, 100);
    }
});

function updateEngineCounter() {
    const ec = document.getElementById('engineCount');
    if (!ec) return;
    
    const model = document.getElementById('searchModelInput')?.value || 'fathom_s1';
    let count = 0;
    if (model === 'fathom_s1') {
        count = systemLimits.fathom_s1_max_sources || 200;
    } else {
        count = systemLimits.fathom_max_nodes || 600;
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
    sources: 'sourcesPanel',
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
    if (tabId === 'sources' && currentSearchData) {
        renderSourcesPage(currentSearchData);
    }
    // 'results' is an alias for sources in the new UI
    if (tabId === 'results') {
        switchTab('sources');
    }
}

// ─── SOURCES PAGE RENDER ──────────────────────────────────────
let _sourcesData = []; // cached for filter/sort

function renderSourcesPage(report) {
    const results    = report?.results || [];
    const categories = report?.categories || {};
    if (!results.length) return;

    _sourcesData = results;

    // Update stats bar
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

    // Update subtitle
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

    return `<div class="source-row-card" onclick="openSourceUrl('${escapeHtml(url)}')">
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

// ─── SEARCH INPUT MANAGEMENT ─────────────────────────────────
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
    updateSubmitState(); // Initial check
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
        btn.style.opacity = '0.7';
        btn.style.cursor = 'not-allowed';
        btn.style.pointerEvents = 'none';
    } else {
        btn.classList.remove('loading-active');
        btn.innerHTML = `<span>ابحث</span><i class="fas fa-arrow-left" aria-hidden="true"></i>`;
        
        // Restore dynamic state based on length
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
    if (!query || query.length < 20) { 
        showToast('الرجاء كتابة استعلام بحث مفصل ومفهوم لا يقل عن 20 حرفاً.', 'error'); 
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
    
    // Reset our vertical stages and collapse/expanded states
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

    // Reset inspector
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
    if (!container) return;

    if (typeof vis === 'undefined') {
        container.innerHTML = `<div style="padding:20px;color:var(--text-muted);text-align:center;">مكتبة رسم الشبكات (vis.js) غير متوفرة.</div>`;
        return;
    }

    liveTreeNodes = new vis.DataSet();
    liveTreeEdges = new vis.DataSet();

    const options = {
        nodes: {
            font: {
                face: 'Cairo, system-ui, sans-serif',
                size: 11,
                color: '#E2E8F0'
            },
            borderWidth: 2,
            shadow: { enabled: true, size: 6, color: 'rgba(0,0,0,0.5)' }
        },
        edges: {
            color: { color: '#273549', highlight: '#c9a84c', hover: '#c9a84c' },
            arrows: { to: { enabled: true, scaleFactor: 0.8 } },
            width: 1.5,
            smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.6 }
        },
        layout: {
            hierarchical: {
                enabled: true,
                direction: 'LR', // Left-to-Right structure
                sortMethod: 'directed',
                nodeSpacing: 50,
                levelSeparation: 160
            }
        },
        physics: {
            enabled: false
        },
        interaction: {
            hover: true,
            zoomView: true,
            dragView: true,
            selectable: true
        }
    };

    liveTreeNetwork = new vis.Network(container, { nodes: liveTreeNodes, edges: liveTreeEdges }, options);
    
    // Node selection opens the sheet (which now targets our inspector panel)
    liveTreeNetwork.on('click', function(params) {
        if (params.nodes && params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const nodeData = liveTreeNodes.get(nodeId);
            if (nodeData && nodeData.customData) {
                openNodeSheet(nodeId, nodeData.customData.stage, nodeData.customData.status, nodeData.customData.label, nodeData.customData.metadata);
            }
        }
    });

    const status = document.getElementById('treeStatus');
    if (status) status.textContent = 'جاري تهيئة خط الأنابيب...';

    // Show badge
    const badge = document.getElementById('treeLiveBadge');
    if (badge) badge.style.display = 'flex';
}

function toggleStageBlock(stage) {
    const block = document.getElementById(`stage_block_${stage}`);
    if (block) {
        block.classList.toggle('collapsed');
    }
}
window.toggleStageBlock = toggleStageBlock;

function activateStageHeader(stage) {
    const block = document.getElementById(`stage_block_${stage}`);
    if (block) {
        block.classList.remove('collapsed');
        if (block.dataset.status === 'pending') {
            block.dataset.status = 'fetching';
        }
    }
}

function createTreeNode(nodeId, stage, status, label, metadata, parentId) {
    // 1. Manage HTML stage logs
    if (nodeId === stage) {
        const block = document.getElementById(`stage_block_${stage}`);
        if (block) {
            block.dataset.status = status;
            treeNodes.set(nodeId, block); // Map the stage ID to the block element
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

                // Auto inspect in real-time
                selectInspectorNode(nodeId, stage, status, label, metadata, true);
            }
        }
    }

    // 2. Also add to vis.js dataset for network graph
    if (liveTreeNodes && !liveTreeNodes.get(nodeId)) {
        let color = { background: '#1e293b', border: '#475569' };
        let shape = 'dot';
        let level = 0;

        if (stage === 'trigger') {
            color = { background: '#6d28d9', border: '#a78bfa' }; // purple
            shape = 'ellipse';
            level = 0;
        } else if (nodeId.startsWith('subquery_')) {
            color = { background: '#1e3a8a', border: '#3b82f6' }; // blue
            shape = 'box';
            level = 1;
        } else if (nodeId.startsWith('engine_')) {
            color = { background: '#311042', border: '#c084fc' }; // violet/indigo
            shape = 'box';
            level = 2;
        } else if (stage === 'source_discovery') {
            color = { background: '#1e293b', border: '#64748b' };
            shape = 'dot';
            level = 2;
        } else if (stage === 'extraction') {
            color = { background: '#022c22', border: '#10b981' }; // green
            shape = 'dot';
            level = 3;
        } else if (stage === 'semantic_analysis') {
            color = { background: '#581c87', border: '#c084fc' };
            shape = 'ellipse';
            level = 4;
        } else if (stage === 'verification') {
            color = { background: '#701a75', border: '#f472b6' };
            shape = 'ellipse';
            level = 5;
        }

        // Status adjustments
        if (status === 'fetching' || status === 'processing') {
            color = { background: '#78350f', border: '#fbbf24' }; // amber
        } else if (status === 'failed') {
            color = { background: '#7f1d1d', border: '#ef4444' }; // red
        } else if (status === 'success') {
            color.border = '#10b981';
        }

        let cleanLabel = label;
        if (cleanLabel.length > 20) {
            cleanLabel = cleanLabel.substring(0, 18) + '...';
        }

        liveTreeNodes.add({
            id: nodeId,
            label: cleanLabel,
            level: level,
            shape: shape,
            color: color,
            customData: { stage, status, label, metadata }
        });

        // Add connection edges
        if (parentId && liveTreeNodes.get(parentId)) {
            liveTreeEdges.add({ from: parentId, to: nodeId });
        } else if (level > 0) {
            let fallback = 'trigger';
            if (level === 2 && nodeId.startsWith('engine_')) {
                const parts = nodeId.split('_');
                fallback = `subquery_${parts[1]}`;
            } else if (level === 3) {
                const discNode = metadata?.discovery_node;
                if (discNode && liveTreeNodes.get(discNode)) {
                    fallback = discNode;
                } else {
                    fallback = 'source_discovery';
                }
            } else if (level === 4) {
                fallback = 'extraction';
            } else if (level === 5) {
                fallback = 'semantic_analysis';
            }

            if (liveTreeNodes.get(fallback)) {
                liveTreeEdges.add({ from: fallback, to: nodeId });
            }
        }
    }

    activateStageHeader(stage);
    return null;
}

function updateTreeNode(nodeId, status, label, metadata, parentId) {
    // 1. Update HTML Stage block or Log row
    if (nodeId === 'trigger' || nodeId === 'source_discovery' || nodeId === 'extraction' || nodeId === 'semantic_analysis' || nodeId === 'verification') {
        const block = treeNodes.get(nodeId) || document.getElementById(`stage_block_${nodeId}`);
        if (block) {
            block.dataset.status = status;
            if (status === 'fetching' || status === 'processing' || status === 'success') {
                activateStageHeader(nodeId);
            }
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
                    const err = metadata?.error || metadata?.reason || 'فشل';
                    badge.textContent = 'خطأ';
                    badge.title = err;
                } else if (metadata) {
                    const parts = [];
                    if (metadata.word_count !== undefined) parts.push(`${metadata.word_count} كلمة`);
                    else if (metadata.words !== undefined) parts.push(`${metadata.words} كلمة`);

                    if (metadata.count !== undefined) parts.push(`${metadata.count} نتائج`);

                    badge.textContent = parts.join(' · ') || '✓';
                } else {
                    badge.textContent = '✓';
                }
            }

            // Retry button
            if (status === 'failed' && metadata?.can_retry) {
                if (!logRow.querySelector('.log-retry-btn')) {
                    const retryBtn = document.createElement('button');
                    retryBtn.className = 'log-retry-btn';
                    retryBtn.innerHTML = '<i class="fas fa-redo-alt"></i>';
                    retryBtn.title = 'إعادة المحاولة';
                    retryBtn.addEventListener('click', e => {
                        e.stopPropagation();
                        showToast('جاري إعادة تشغيل البحث...', 'info');
                        handleSearch(null);
                    });
                    logRow.appendChild(retryBtn);
                }
            }

            // Sync with active inspector
            if (activeInspectedNodeId === nodeId) {
                selectInspectorNode(nodeId, logRow.dataset.stage, status, label, metadata, true);
            }
        }
    }

    // 2. Also update vis.js network node
    if (liveTreeNodes) {
        const visNode = liveTreeNodes.get(nodeId);
        if (visNode) {
            let color = visNode.color;
            if (status === 'fetching' || status === 'processing') {
                color = { background: '#78350f', border: '#fbbf24' };
            } else if (status === 'failed') {
                color = { background: '#7f1d1d', border: '#ef4444' };
            } else if (status === 'success') {
                color = { background: visNode.color.background, border: '#10b981' };
            }

            let cleanLabel = label;
            if (cleanLabel.length > 20) {
                cleanLabel = cleanLabel.substring(0, 18) + '...';
            }

            liveTreeNodes.update({
                id: nodeId,
                label: cleanLabel,
                color: color,
                customData: {
                    stage: visNode.customData?.stage || 'general',
                    status: status,
                    label: label,
                    metadata: { ...visNode.customData?.metadata, ...metadata }
                }
            });
        }
    }

    if (['fetching','processing','success'].includes(status)) {
        const treeStatus = document.getElementById('treeStatus');
        if (treeStatus) treeStatus.textContent = label;
    }
}

function selectInspectorNode(nodeId, stage, status, label, metadata, isAuto = false) {
    if (isAuto && userClickedInspectorNode) {
        return; // manual click locks inspector
    }
    
    if (!isAuto) {
        userClickedInspectorNode = true;
    }
    
    activeInspectedNodeId = nodeId;

    // Toggle active row highlights
    document.querySelectorAll('.log-row').forEach(row => {
        row.classList.remove('active-inspect');
    });
    const activeRow = document.getElementById(`html_node_${nodeId}`);
    if (activeRow) {
        activeRow.classList.add('active-inspect');
    }

    const placeholder = document.getElementById('inspectorPlaceholder');
    const content = document.getElementById('inspectorContent');
    if (!content) return;

    if (placeholder) placeholder.style.display = 'none';
    content.style.display = 'flex';
    content.style.flexDirection = 'column';

    const statusColors = {
        success: 'var(--success-text)', failed: 'var(--error-text)',
        fetching: 'var(--fetching-text)', rerouted: 'var(--rerouted-text)',
        processing: 'var(--accent)', pending: 'var(--text-muted)',
    };

    let metaHTML = '';
    if (metadata) {
        if (metadata.url) {
            const wordsCount = metadata.words || metadata.word_count || 0;
            const extractionMethod = metadata.method || metadata.extraction_method || 'N/A';
            const credibilityTier = metadata.credibility_tier || 'مصدر عام';
            const credibilityWeight = metadata.credibility_weight !== undefined ? metadata.credibility_weight : 0.3;
            const relevanceScore = metadata.relevance_score !== undefined ? metadata.relevance_score : 0.5;
            const cbState = metadata.cb_state || 'closed';
            const resolvedIp = metadata.resolved_ip || '127.0.0.1';

            let badgeColor = '#94a3b8';
            let badgeBg = 'rgba(148, 163, 184, 0.1)';
            if (credibilityWeight === 1.0) {
                badgeColor = '#fbbf24';
                badgeBg = 'rgba(251, 191, 36, 0.1)';
            } else if (credibilityWeight === 0.7) {
                badgeColor = '#10b981';
                badgeBg = 'rgba(16, 185, 129, 0.1)';
            }

            const relevancePercent = Math.round(relevanceScore * 100);

            metaHTML = `
                <div class="source-detail-card" style="margin-top: 10px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;background:rgba(255,255,255,0.02);padding:10px;border-radius:var(--r-md);border:1px solid var(--border);gap:10px;">
                        <div style="display:flex;align-items:center;gap:6px;overflow:hidden;flex-grow:1;">
                            <i class="fas fa-globe" style="color:var(--accent);font-size:13px;flex-shrink:0;"></i>
                            <a href="${metadata.url}" target="_blank" style="color:var(--text);font-weight:600;text-decoration:none;font-size:11.5px;word-break:break-all;text-overflow:ellipsis;white-space:nowrap;overflow:hidden;" title="${metadata.url}">
                                ${escapeHtml(metadata.url.replace(/https?:\/\//, '').split('/')[0])}
                                <i class="fas fa-external-link-alt" style="font-size:8px;margin-right:4px;"></i>
                            </a>
                        </div>
                        <span class="cred-badge" style="color:${badgeColor};background:${badgeBg};border:1px solid ${badgeColor}33;padding:2px 6px;border-radius:30px;font-size:9px;font-weight:600;flex-shrink:0;">
                            ${credibilityTier}
                        </span>
                    </div>

                    <h3 style="font-size:13.5px;font-weight:700;color:var(--text);margin-bottom:10px;line-height:1.5;text-align:right;">${escapeHtml(metadata.title || label)}</h3>

                    <div class="details-snippet-box" style="background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--r-md);padding:10px;margin-bottom:12px;max-height:140px;overflow-y:auto;font-size:11.5px;color:var(--text-muted);line-height:1.6;direction:rtl;text-align:right;">
                        ${escapeHtml(metadata.snippet || 'لا يوجد مقتطف نصي متاح.')}
                    </div>

                    <div style="margin-bottom:14px;">
                        <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:5px;">
                            <span style="color:var(--text-muted)">نسبة المطابقة والموثوقية:</span>
                            <span style="color:var(--accent);font-weight:bold;">${relevancePercent}%</span>
                        </div>
                        <div style="width:100%;height:5px;background:var(--border);border-radius:10px;overflow:hidden;">
                            <div style="width:${relevancePercent}%;height:100%;background:linear-gradient(90deg, var(--accent), #a78bfa);border-radius:10px;box-shadow:0 0 6px var(--accent);"></div>
                        </div>
                    </div>

                    <div style="display:flex;flex-direction:column;gap:6px;font-size:11px;color:var(--text-muted);background:rgba(255,255,255,0.01);padding:10px;border-radius:var(--r-md);border:1px solid var(--border)">
                        <div style="display:flex;justify-content:space-between;"><span><i class="fas fa-file-alt" style="margin-left:6px;"></i> الكلمات المستخرجة:</span> <strong style="color:var(--text)">${wordsCount.toLocaleString()} كلمة</strong></div>
                        <div style="display:flex;justify-content:space-between;"><span><i class="fas fa-robot" style="margin-left:6px;"></i> أداة الاستخراج:</span> <strong style="color:var(--text)">${escapeHtml(extractionMethod)}</strong></div>
                        <div style="display:flex;justify-content:space-between;"><span><i class="fas fa-network-wired" style="margin-left:6px;"></i> خادم الويب (IP):</span> <strong style="color:var(--text)">${escapeHtml(resolvedIp)}</strong></div>
                        <div style="display:flex;justify-content:space-between;"><span><i class="fas fa-shield-halved" style="margin-left:6px;"></i> حالة الحظر (Circuit):</span> <strong style="color:var(--text)">${escapeHtml(cbState)}</strong></div>
                    </div>
                </div>
            `;
        } else {
            metaHTML = Object.entries(metadata)
                .filter(([k, v]) => v !== undefined && v !== null && v !== '')
                .map(([k, v]) => `<tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;font-size:11px;text-align:right;">${escapeHtml(k)}</td><td style="font-family:'JetBrains Mono',monospace;font-size:11px;direction:ltr;text-align:left;word-break:break-all;">${escapeHtml(String(v))}</td></tr>`)
                .join('');
            if (metaHTML) metaHTML = `<table style="width:100%;border-collapse:collapse;margin-top:10px;">${metaHTML}</table>`;
        }
    }

    content.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;border-bottom:1px solid var(--border);padding-bottom:8px;">
            <div style="display:flex;align-items:center;gap:6px;">
                <span class="log-status-dot" style="background:${statusColors[status] || 'var(--text-muted)'};width:8px;height:8px;border-radius:50%;"></span>
                <span style="color:${statusColors[status] || 'var(--text-muted)'};font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;text-transform:uppercase;">${STAGE_LABELS[status] || status}</span>
            </div>
            <span style="color:var(--text-muted);font-size:11px;font-weight:500;">${STAGE_LABELS[stage] || stage}</span>
        </div>
        <h4 style="font-size:13px;font-weight:700;margin-bottom:8px;color:var(--text-primary);text-align:right;line-height:1.4;">${escapeHtml(label)}</h4>
        <div style="font-size:10px;color:var(--text-muted);font-family:'JetBrains Mono',monospace;text-align:right;margin-bottom:8px;">ID: ${escapeHtml(nodeId)}</div>
        ${metaHTML}
    `;
}

function openNodeSheet(nodeId, stage, status, label, metadata) {
    selectInspectorNode(nodeId, stage, status, label, metadata, false);
}

function closeNodeSheet() {
    activeInspectedNodeId = null;
    userClickedInspectorNode = false;
    const placeholder = document.getElementById('inspectorPlaceholder');
    const content = document.getElementById('inspectorContent');
    if (placeholder) placeholder.style.display = 'flex';
    if (content) {
        content.innerHTML = '';
        content.style.display = 'none';
    }
}

function openBottomContentSheet(html) {
    const placeholder = document.getElementById('inspectorPlaceholder');
    const content = document.getElementById('inspectorContent');
    if (!content) return;
    if (placeholder) placeholder.style.display = 'none';
    content.style.display = 'block';
    content.innerHTML = html;
}


function startSSEStream(query, model, attempt = 0) {
    // `streamDone` guards the reconnect logic: once the server has sent `complete`
    // (or a deterministic `error` event), a subsequent transport close is normal
    // and must NOT trigger a reconnect.
    let streamDone = false;
    const MAX_RECONNECTS = 3;
    // Cancel any pending reconnect from a previous attempt of this stream.
    if (window._sseReconnectTimer) { clearTimeout(window._sseReconnectTimer); window._sseReconnectTimer = null; }
    
    // Throttler with trailing edge execution
    function throttle(func, wait) {
        let timeout = null;
        let lastArgs = null;
        let lastRan = 0;
        const throttled = function(...args) {
            const now = Date.now();
            const remaining = wait - (now - lastRan);
            if (remaining <= 0 || remaining > wait) {
                if (timeout) {
                    clearTimeout(timeout);
                    timeout = null;
                }
                lastRan = now;
                func(...args);
            } else {
                lastArgs = args;
                if (!timeout) {
                    timeout = setTimeout(() => {
                        lastRan = Date.now();
                        timeout = null;
                        func(...lastArgs);
                    }, remaining);
                }
            }
        };
        throttled.cancel = () => {
            if (timeout) {
                clearTimeout(timeout);
                timeout = null;
            }
        };
        return throttled;
    }

    const throttledUpdate = throttle((report) => {
        renderResultsList(report);
        renderAnalysis(report);
        renderSemanticVisualPanel(report);
        const isGraphVisible = !document.getElementById('knowledgeGraphContainer').classList.contains('is-hidden');
        if (isGraphVisible) {
            buildKnowledgeGraph(report);
        }
    }, 1500); // Render at most once every 1.5 seconds to keep the UI smooth and responsive

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
            throttledUpdate(report);
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

            throttledUpdate.cancel();

            const report = JSON.parse(e.data);
            currentSearchData = report;

            // Ensure final full UI render
            renderResultsList(report);
            renderAnalysis(report);
            renderSemanticVisualPanel(report);
            buildKnowledgeGraph(report);

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

                // Build sources count only (full sources page is in the Results tab)
                const sources = directAnswer.sources || [];
                const totalSrcs = sources.length || (report.results || []).length;
                let sourcesHtml = '';
                if (totalSrcs > 0) {
                    sourcesHtml = `<div class="da-sources-count">
                        <i class="fas fa-database"></i>
                        <span>استناداً إلى <strong>${totalSrcs}</strong> مصدر موثق</span>
                        <button class="da-view-sources-btn" onclick="switchTab('results')" title="عرض جميع المصادر">
                            <i class="fas fa-list-ul"></i> عرض المصادر
                        </button>
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
            renderSemanticVisualPanel(report);
            renderResultsList(report);
            buildKnowledgeGraph(report);

            setStatusDot('idle', 'Done');
            showToast(`تم العثور على ${formatScaryCount(report.total_results || 0)} مصدر`, 'success');
            
            updateProgressBar(100);
            setTimeout(() => {
                hideProgressBar();
                setSearchButtonLoading(false);
            }, 600);

            // Auto-switch to Sources tab after search completes
            setTimeout(() => {
                renderSourcesPage(report);
                switchTab('sources');
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

// ─── SEMANTIC ANALYSIS VISUAL PANEL ──────────────────────────
/**
 * Builds a rich visual summary inside the semantic_analysis stage body
 * showing: total/filtered/passed counts, credibility tier distribution,
 * and detected content categories. Called once when the final report arrives.
 */
function renderSemanticVisualPanel(report) {
    const body = document.getElementById('stage_body_semantic_analysis');
    if (!body) return;

    // Don't render twice
    if (body.querySelector('.semantic-visual-panel')) return;

    const results    = report?.results || [];
    const categories = report?.categories || {};
    const analysis   = report?.analysis || {};
    const stats      = analysis.statistics || {};
    const total      = results.length;
    if (total === 0) return;

    // Credibility tier counts
    const t1 = results.filter(r => r.metadata?.credibility_weight === 1.0).length;
    const t2 = results.filter(r => r.metadata?.credibility_weight === 0.7).length;
    const t3 = total - t1 - t2;

    // Avg relevance
    const avgRel = total > 0
        ? (results.reduce((s, r) => s + (r.relevance_score || 0), 0) / total)
        : 0;
    const avgPct = Math.round(avgRel * 100);

    // Unique domains
    const uniqueDomains = new Set(results.map(r => {
        try { return new URL(r.url || 'http://x').hostname; } catch { return r.url; }
    })).size;

    // Top categories
    const catEntries = Object.entries(categories)
        .filter(([, v]) => v && v.length > 0)
        .sort((a, b) => b[1].length - a[1].length)
        .slice(0, 6);

    const catIconMap = {
        articles: 'fa-newspaper', videos: 'fa-video', social: 'fa-share-alt',
        academic: 'fa-graduation-cap', news: 'fa-broadcast-tower',
        code: 'fa-code', products: 'fa-shopping-bag', other: 'fa-globe'
    };
    const catNameMap = {
        articles: 'مقالات', videos: 'مرئيات', social: 'اجتماعي',
        academic: 'أبحاث', news: 'أخبار', code: 'برمجة',
        products: 'منتجات', other: 'أخرى'
    };

    const catChips = catEntries.map(([k, v]) => `
        <span class="sv-cat-chip">
            <i class="fas ${catIconMap[k] || 'fa-globe'}"></i>
            ${catNameMap[k] || k}
            <span class="sv-cat-count">${v.length}</span>
        </span>`).join('');

    const panel = document.createElement('div');
    panel.className = 'semantic-visual-panel';
    panel.innerHTML = `
        <div class="sv-stat-card">
            <span class="sv-stat-label">المصادر المحللة</span>
            <span class="sv-stat-value">${total}</span>
            <span class="sv-stat-sub">${uniqueDomains} نطاق فريد</span>
        </div>
        <div class="sv-stat-card">
            <span class="sv-stat-label">متوسط الصلة</span>
            <span class="sv-stat-value">${avgPct}<span style="font-size:12px;font-weight:500">%</span></span>
            <span class="sv-stat-sub">بعد التصفية الدلالية</span>
        </div>
        <div class="sv-stat-card">
            <span class="sv-stat-label">الفئات المكتشفة</span>
            <span class="sv-stat-value">${catEntries.length}</span>
            <span class="sv-stat-sub">تصنيف محتوى ذكي</span>
        </div>
        <div class="sv-cred-bars">
            <div class="sv-cred-bars-title"><i class="fas fa-shield-alt" style="margin-left:4px"></i> توزيع مصداقية المصادر</div>
            <div class="sv-cred-row">
                <span class="sv-cred-row-label">Tier 1 ⭐</span>
                <div class="sv-cred-bar-track"><div class="sv-cred-bar-fill t1" style="width:${total ? (t1/total*100).toFixed(0) : 0}%"></div></div>
                <span class="sv-cred-row-count">${t1}</span>
            </div>
            <div class="sv-cred-row">
                <span class="sv-cred-row-label">Tier 2 ✓</span>
                <div class="sv-cred-bar-track"><div class="sv-cred-bar-fill t2" style="width:${total ? (t2/total*100).toFixed(0) : 0}%"></div></div>
                <span class="sv-cred-row-count">${t2}</span>
            </div>
            <div class="sv-cred-row">
                <span class="sv-cred-row-label">Tier 3 ·</span>
                <div class="sv-cred-bar-track"><div class="sv-cred-bar-fill t3" style="width:${total ? (t3/total*100).toFixed(0) : 0}%"></div></div>
                <span class="sv-cred-row-count">${t3}</span>
            </div>
        </div>
        ${catEntries.length > 0 ? `<div class="sv-categories">${catChips}</div>` : ''}
    `;
    body.appendChild(panel);
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
    const rootbaseEl = document.getElementById('rootbaseContent');
    if (rootbaseEl) {
        const deep = analysis.deep_analysis || analysis.rootbase_analysis || '';
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
        const catCount  = Object.keys(report.categories || {}).length;
        const enginesArr = Object.keys(stats.sources_used || {});
        const searchTimeEl = document.getElementById('searchTime');
        const rows = [
            ['إجمالي المصادر',    (report.total_results || 0) + ' مصدر'],
            ['مصادر فريدة',       (report.total_unique  || 0) + ' مصدر'],
            ['الفئات المعرفية',   catCount  ? catCount + ' فئة'  : '—'],
            ['محركات البحث',      enginesArr.length ? enginesArr.length + ' محرك' : '—'],
            ['زمن البحث',         (searchTimeEl?.textContent || '—') + 'ث'],
            ['الكلمات المحللة',   ((stats.total_words_analyzed || 0).toLocaleString()) + ' كلمة'],
        ];
        statsEl.innerHTML = `<table style="width:100%;border-collapse:collapse">` +
            rows.map(([k, v]) => `<tr>
                <td style="padding:8px 0;color:var(--text-muted);font-size:13px;border-bottom:1px solid var(--border)">${k}</td>
                <td style="padding:8px 0;font-size:13px;font-weight:600;border-bottom:1px solid var(--border);text-align:end">${escapeHtml(String(v))}</td>
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
    const score    = fmtScore(r.relevance_score);
    const src      = (r.source || '').split('|')[0];
    const wc       = r.metadata && r.metadata.word_count ? (r.metadata.word_count.toLocaleString() + ' كلمة') : '';
    const scraped  = !!(r.metadata && r.metadata.scraped);
    const credWt   = r.metadata ? r.metadata.credibility_weight : null;
    const readMin  = (r.metadata && r.metadata.reading_time)
        ? r.metadata.reading_time
        : (r.metadata && r.metadata.word_count ? Math.ceil(r.metadata.word_count / 200) : 0);

    // Credibility badge
    var credBadge = '';
    if (credWt === 1.0) {
        credBadge = '<span class="rc-cred-badge rc-cred-t1" title="مصدر موثوق Tier 1"><i class="fas fa-shield-alt"></i></span>';
    } else if (credWt === 0.7) {
        credBadge = '<span class="rc-cred-badge rc-cred-t2" title="مصدر جيد Tier 2"><i class="fas fa-check-circle"></i></span>';
    }

    // Content-type icon
    const catIcons = {
        articles: 'fa-newspaper', videos: 'fa-video', social: 'fa-share-alt',
        academic: 'fa-graduation-cap', news: 'fa-broadcast-tower', code: 'fa-code',
        products: 'fa-shopping-bag', other: 'fa-globe'
    };
    const ctIcon = catIcons[r.content_type] || 'fa-globe';

    // AI summary vs raw snippet
    const isAISummary = r.summary && r.summary !== r.snippet && !r.summary.includes('Analysis failed');
    const bodyText = isAISummary ? r.summary : (r.snippet || '');
    const bodyHighlighted = highlightTerms(escapeHtml(decodeHtml(bodyText)), currentQuery);

    var snippetHTML = isAISummary
        ? '<div class="rc-ai-summary"><span class="rc-ai-label"><i class="fas fa-sparkles"></i> ملخص الذكاء الاصطناعي</span><p class="result-snippet" style="margin-top:6px">' + bodyHighlighted + '</p></div>'
        : '<p class="result-snippet">' + bodyHighlighted + '</p>';

    var footerMeta = '';
    if (wc) footerMeta += '<span class="result-meta-tag"><i class="fas fa-align-left"></i> ' + wc + '</span>';
    if (readMin) footerMeta += '<span class="result-meta-tag"><i class="fas fa-clock"></i> ' + readMin + ' د قراءة</span>';
    if (scraped) footerMeta += '<span class="rc-scraped-tag"><i class="fas fa-check"></i> مستخرج</span>';

    return '<article class="result-card" data-category="' + (r.content_type || 'other') + '" onclick="openSourceDetailModal(\'' + getUrlId(r.url) + '\')">'
        + '<div class="result-source-row">'
        + '<i class="fas ' + ctIcon + '" style="color:var(--accent);font-size:11px;opacity:0.7"></i> '
        + '<span class="result-source-badge">' + escapeHtml(decodeHtml(src)) + '</span>'
        + credBadge
        + (score ? '<span class="result-score">' + score + '</span>' : '')
        + '</div>'
        + '<h3 class="result-title">'
        + '<a href="' + escapeHtml(r.url) + '" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation();">'
        + escapeHtml(decodeHtml(r.title || 'بدون عنوان'))
        + '</a>'
        + '</h3>'
        + '<div class="result-url">' + escapeHtml(r.url || '') + '</div>'
        + snippetHTML
        + '<div class="result-footer">'
        + footerMeta
        + '<button class="result-open-btn" style="margin-inline-start:auto;" onclick="event.stopPropagation(); openSourceDetailModal(\'' + getUrlId(r.url) + '\')">'
        + '<i class="fas fa-info-circle"></i> تفاصيل</button>'
        + '<a href="' + escapeHtml(r.url) + '" target="_blank" rel="noopener noreferrer" class="result-open-btn" onclick="event.stopPropagation();">'
        + '<i class="fas fa-external-link-alt"></i> فتح</a>'
        + '</div>'
        + '</article>';
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

    const src         = (r.source || '').split('|')[0];
    const score       = fmtScore(r.relevance_score, '—');
    const relPct      = r.relevance_score != null
        ? Math.round(Math.min(1, r.relevance_score) * 100)
        : null;
    const isScraped   = r.metadata?.scraped;
    const wc          = r.metadata?.word_count ? r.metadata.word_count.toLocaleString() : '—';
    const author      = r.metadata?.author || '—';
    const publishDate = r.metadata?.publish_date || r.metadata?.date || '—';
    const language    = r.metadata?.language || '—';
    const credWt      = r.metadata?.credibility_weight;
    const credTier    = r.metadata?.credibility_tier || '';
    const readMin     = r.metadata?.reading_time
        ? r.metadata.reading_time + ' دقيقة'
        : (r.metadata?.word_count ? Math.ceil(r.metadata.word_count / 200) + ' دقيقة' : '—');

    // Credibility badge
    let credColor = '#94a3b8', credBg = 'rgba(148,163,184,0.1)', credLabel = 'مصدر عام';
    if (credWt === 1.0 || credTier === 'Tier 1') {
        credColor = '#f59e0b'; credBg = 'rgba(245,158,11,0.12)'; credLabel = 'Tier 1 — موثوق';
    } else if (credWt === 0.7 || credTier === 'Tier 2') {
        credColor = '#10b981'; credBg = 'rgba(16,185,129,0.1)'; credLabel = 'Tier 2 — جيد';
    }

    // Relevance bar
    const relBarHTML = relPct != null ? `
        <div style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:5px;">
                <span style="color:var(--text-muted)">نسبة الصلة بالاستعلام</span>
                <span style="color:var(--accent);font-weight:700">${relPct}%</span>
            </div>
            <div style="width:100%;height:5px;background:var(--border);border-radius:10px;overflow:hidden;">
                <div style="width:${relPct}%;height:100%;background:linear-gradient(90deg,var(--accent),#a78bfa);border-radius:10px;box-shadow:0 0 8px var(--accent)40;transition:width 0.6s ease;"></div>
            </div>
        </div>` : '';

    // Sentiment
    let sentimentHTML = '';
    if (r.metadata?.sentiment) {
        sentimentHTML = `<div class="metadata-item">
            <span class="metadata-label">النبرة / المشاعر</span>
            <span class="metadata-value">${escapeHtml(decodeHtml(r.metadata.sentiment))}</span>
        </div>`;
    }

    // AI Summary
    let aiSummaryHTML = '';
    if (r.summary && r.summary !== r.snippet && !r.summary.includes('Analysis failed')) {
        aiSummaryHTML = `
            <div class="ai-summary-section">
                <div class="ai-summary-title">
                    <i class="fas fa-sparkles"></i>
                    <span>تلخيص الذكاء الاصطناعي المعرفي</span>
                </div>
                <div class="ai-summary-content">
                    ${DOMPurify.sanitize(marked.parse(decodeHtml(r.summary)))}
                </div>
            </div>
        `;
    }

    // Domain from URL for favicon
    let domainForFavicon = '';
    try { domainForFavicon = new URL(r.url).hostname; } catch(_) {}
    const faviconUrl = domainForFavicon
        ? `https://www.google.com/s2/favicons?domain=${domainForFavicon}&sz=32`
        : '';

    body.innerHTML = `
        <!-- Header row -->
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
            ${faviconUrl ? `<img src="${faviconUrl}" width="20" height="20" style="border-radius:4px;flex-shrink:0;" onerror="this.style.display='none'" alt="">` : ''}
            <span class="result-source-badge" style="font-size:12px;padding:4px 10px;">${escapeHtml(decodeHtml(src))}</span>
            <span style="background:${credBg};color:${credColor};border:1px solid ${credColor}33;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;">${credLabel}</span>
            <span class="result-score" style="font-size:12px;">${score}</span>
            <button onclick="navigator.clipboard.writeText('${escapeHtml(r.url)}').then(()=>showToast('تم نسخ الرابط','success'))" style="margin-inline-start:auto;background:none;border:1px solid var(--border-mid);color:var(--text-muted);border-radius:var(--r-sm);padding:4px 10px;font-size:11px;cursor:pointer;display:flex;align-items:center;gap:5px;" title="نسخ الرابط">
                <i class="fas fa-copy"></i> نسخ
            </button>
        </div>

        <h2 style="font-size:17px;margin-bottom:10px;color:var(--text-primary);line-height:1.5;">${escapeHtml(decodeHtml(r.title || 'بدون عنوان'))}</h2>
        <div style="font-size:11px;color:var(--accent);word-break:break-all;margin-bottom:18px;opacity:0.8;font-family:'JetBrains Mono',monospace;">
            ${escapeHtml(decodeHtml(r.url))}
        </div>

        ${relBarHTML}
        ${aiSummaryHTML}

        <h4 style="font-size:13px;font-weight:600;margin-bottom:10px;color:var(--text-primary);display:flex;align-items:center;gap:6px;">
            <i class="fas fa-info-circle" style="color:var(--accent)"></i> البيانات الوصفية
        </h4>
        <div class="metadata-grid">
            <div class="metadata-item">
                <span class="metadata-label">محرك البحث</span>
                <span class="metadata-value" style="color:var(--accent);">${escapeHtml(src.toUpperCase())}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">استخراج المحتوى</span>
                <span class="metadata-value" style="color:${isScraped ? 'var(--success-text)' : 'var(--text-muted)'};">
                    ${isScraped ? '<i class="fas fa-check-circle"></i> مستخرج' : '<i class="fas fa-times-circle"></i> غير مستخرج'}
                </span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">عدد الكلمات</span>
                <span class="metadata-value">${wc} كلمة</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">زمن القراءة</span>
                <span class="metadata-value">${readMin}</span>
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
                <span class="metadata-value">${escapeHtml(String(language).toUpperCase())}</span>
            </div>
            ${sentimentHTML}
        </div>

        <h4 style="font-size:13px;font-weight:600;margin:18px 0 10px;color:var(--text-primary);display:flex;align-items:center;gap:6px;">
            <i class="fas fa-quote-right" style="color:var(--accent)"></i> مقتطف النص
        </h4>
        <div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--r-md);padding:14px;font-size:13px;line-height:1.75;color:var(--text-secondary);direction:rtl;text-align:right;">
            ${highlightTerms(escapeHtml(decodeHtml(r.snippet || 'لا يوجد مقتطف.')), currentQuery)}
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
    const rawCategories = report.categories || {};
    const categories    = JSON.parse(JSON.stringify(rawCategories));
    const categorizedUrls = new Set();
    Object.values(categories).forEach(arr => {
        if (Array.isArray(arr)) arr.forEach(r => { if (r.url) categorizedUrls.add(r.url); });
    });
    const uncategorized = results.filter(r => !categorizedUrls.has(r.url));
    if (uncategorized.length > 0) {
        const otherKey = 'أخرى (OTHER)';
        if (!categories[otherKey]) categories[otherKey] = [];
        uncategorized.forEach(u => {
            if (!categories[otherKey].some(x => x.url === u.url)) categories[otherKey].push(u);
        });
    }
    const searchPath   = report.search_path || report.live_log || [];
    const deepAnalysis = analysis.deep_analysis || analysis.aggregated_report || '';
    const entities     = analysis.entities || {};
    const topics       = analysis.topics || analysis.clusters || [];

    // ── Separator constants ─────────────────────────────────────────────────────
    const SEP  = '═'.repeat(72);
    const SEP2 = '─'.repeat(72);

    // ── Text cleaning: strips HTML, markdown, URLs, junk chars ──────────────────
    const cleanText = (raw) => {
        if (!raw) return '';
        return String(raw)
            // Decode common HTML entities
            .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
            // Strip markdown bold/italic
            .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1')
            // Strip markdown headers
            .replace(/^#{1,6}\s*/gm, '')
            // Strip inline code
            .replace(/`([^`]+)`/g, '$1')
            // Strip bare URLs (http...)
            .replace(/https?:\/\/\S+/g, '')
            // Strip leftover html tags
            .replace(/<[^>]+>/g, '')
            // Remove binary-looking sequences (non-printable)
            .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
            // Collapse multiple spaces/newlines
            .replace(/[ \t]+/g, ' ')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    };

    // Safe text wrap: breaks on spaces, preserves Arabic direction
    const wrap = (text, prefix, w) => {
        prefix = prefix || '  ';
        w = w || 70;
        const cleaned = cleanText(text);
        if (!cleaned) return '';
        // Split into paragraphs first, then wrap each
        const paragraphs = cleaned.split(/\n\n+/);
        let out = '';
        for (const para of paragraphs) {
            const words = para.replace(/\n/g, ' ').split(' ').filter(Boolean);
            let line = '';
            for (const word of words) {
                if (line && (line.length + word.length + 1) > w) {
                    out += prefix + line.trimEnd() + '\n';
                    line = word + ' ';
                } else {
                    line += word + ' ';
                }
            }
            if (line.trim()) out += prefix + line.trimEnd() + '\n';
            out += '\n'; // blank line between paragraphs
        }
        return out.trimEnd() + '\n';
    };

    const sec = (num, label) =>
        '\n' + SEP + '\n  [' + num + ']  ' + label + '\n' + SEP + '\n';

    const subSec = (label) =>
        '\n  ── ' + label + ' ──\n  ' + SEP2 + '\n';

    const fmtScore = (val, fallback) => {
        if (val == null || isNaN(val)) return fallback || '—';
        const n = Number(val);
        return (n <= 1.0 ? (n * 100).toFixed(0) : n.toFixed(1)) + '%';
    };

    // Simple ASCII bar, no Arabic strings inside calculations
    const bar = (val) => {
        const pct = Math.max(0, Math.min(100, Math.round((val || 0) * 100)));
        const filled = Math.round(pct / 10);
        return '[' + '█'.repeat(filled) + '░'.repeat(10 - filled) + '] ' + pct + '%';
    };


    // ── Key data ───────────────────────────────────────────────────────────────
    const queryStr   = report.query || '—';
    const totalRes   = results.length;
    const uniqueRes  = new Set(results.map(r => r.url)).size;
    const searchTime = report.elapsed_time || report.search_time || '—';
    const modelName  = report.model === 'fathom_max'
        ? 'Fathom Max — التنقيب العميق'
        : 'Fathom S1  — البحث البرقي';
    const timestamp  = new Date(report.timestamp || Date.now()).toLocaleString('ar-EG', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
    const enginesUsed = [...new Set(results.map(r => r.source).filter(Boolean))];
    const _rawAvg = stats.average_relevance
        || (results.length > 0
            ? results.reduce((s, r) => s + (r.relevance_score || 0), 0) / results.length
            : null);
    const avgRel = _rawAvg == null ? '—'
        : (_rawAvg <= 1.0 ? (_rawAvg * 100).toFixed(1) + '%' : _rawAvg.toFixed(4));
    const totalWords = stats.total_words_analyzed || 0;

    let text = '';

    // ══ HEADER ════════════════════════════════════════════════════════════════
    text += SEP + '\n';
    text += '  ROOTSEARCH — نظام البحث والتحليل المعرفي العميق\n';
    text += '  Deep Cognitive Search & Analysis System — Demo 1 T\n';
    text += SEP + '\n\n';

    // ══ SECTION 1: SEARCH METRICS ═════════════════════════════════════════════
    text += sec('١', 'البيانات المرجعية ومقاييس البحث');
    text += '  الاستعلام         : ' + queryStr + '\n';
    text += '  تاريخ التقرير     : ' + timestamp + '\n';
    text += '  نموذج البحث       : ' + modelName + '\n';
    text += '  ' + SEP2 + '\n';
    text += '  إجمالي المصادر    : ' + totalRes + ' مصدر  |  فريد: ' + uniqueRes + '\n';
    text += '  محركات البحث      : ' + (enginesUsed.join(' • ') || '—') + '\n';
    text += '  زمن البحث         : ' + searchTime + 'ث\n';
    text += '  متوسط درجة الصلة  : ' + avgRel + '\n';
    text += '  إجمالي الكلمات    : ' + totalWords.toLocaleString() + ' كلمة\n\n';

    // ══ SECTION 2: AI QUICK ANSWER ════════════════════════════════════════════
    text += sec('٢', 'الملخص التنفيذي — إجابة الذكاء الاصطناعي');
    const aiAnswer   = analysis.quick_answer || analysis.ai_answer
        || (analysis.direct_answer && analysis.direct_answer.answer) || null;
    const summaryTxt = analysis.summary || analysis.executive_summary || '';
    if (aiAnswer) {
        text += '  [إجابة مباشرة]\n';
        text += wrap(aiAnswer);
        text += '\n';
    }
    if (summaryTxt && summaryTxt !== aiAnswer) {
        text += '  [الملخص الشامل]\n';
        text += wrap(summaryTxt);
    }
    if (!aiAnswer && !summaryTxt) {
        text += '  لم يتوفر ملخص لهذا البحث.\n';
    }
    text += '\n';

    // ══ SECTION 3: DEEP ANALYSIS ══════════════════════════════════════════════
    text += sec('٣', 'التحليل المعرفي العميق — ROOTBASE');
    if (deepAnalysis && deepAnalysis.trim().length > 50) {
        const cleaned = deepAnalysis
            .replace(/#{1,6}\s*/g, '')
            .replace(/\*\*(.+?)\*\*/g, '[$1]')
            .replace(/\*(.+?)\*/g, '$1')
            .replace(/>\s*/g, '  >> ')
            .replace(/\n{3,}/g, '\n\n');
        text += wrap(cleaned.trim());
    } else {
        const catKF = Object.keys(categories).filter(c => categories[c] && categories[c].length > 0);
        if (catKF.length > 0) {
            catKF.forEach(cat => {
                text += '\n  ◄ فئة [' + cat + ']:\n';
                categories[cat].slice(0, 2).forEach((src, i) => {
                    const summary = src.ai_summary || src.summary || src.snippet || '';
                    text += '    (' + (i + 1) + ') ' + (src.title || src.url) + '\n';
                    if (summary.trim()) text += wrap(summary.trim(), '        ');
                });
            });
        } else {
            text += '  لا توجد بيانات تحليل معرفي متوفرة.\n';
        }
    }
    text += '\n';

    // Topics
    if (topics && topics.length > 0) {
        text += subSec('المحاور الموضوعية المكتشفة');
        topics.forEach((t, i) => {
            const label = t.label || t.topic || ('محور ' + (i + 1));
            const count = t.count || t.size || 0;
            text += '  [' + (i + 1) + '] ' + label + '  (' + count + ' مصدر)\n';
            if (t.description || t.summary) text += wrap(t.description || t.summary, '      ');
        });
        text += '\n';
    }

    // Named entities
    const entryTypes = {
        persons: 'الأشخاص', organizations: 'المنظمات',
        locations: 'الأماكن', dates: 'التواريخ'
    };
    const hasEnts = Object.keys(entryTypes).some(k => entities[k] && entities[k].length > 0);
    if (hasEnts) {
        text += subSec('الكيانات المستخرجة');
        for (const key of Object.keys(entryTypes)) {
            const list = entities[key] || [];
            if (list.length > 0) {
                text += '  ' + entryTypes[key] + ': ' + list.slice(0, 15).join(' • ') + '\n';
            }
        }
        text += '\n';
    }

    // ══ SECTION 4: SENTIMENT ══════════════════════════════════════════════════
    text += sec('٤', 'تحليل المشاعر والنبرة الوجدانية');
    if (sentiment && sentiment.overall) {
        const obj  = sentiment.objectivity  || 0;
        const subj = sentiment.subjectivity || 0;
        const pos  = sentiment.positive     || 0;
        const neg  = sentiment.negative     || 0;
        const neu  = sentiment.neutral      || 0;
        text += '  النبرة السائدة     : ' + sentiment.overall + '\n';
        text += '  الموضوعية          : ' + bar(obj) + '\n';
        text += '  الذاتية            : ' + bar(subj) + '\n';
        if (pos || neg || neu) {
            text += '  إيجابي             : ' + bar(pos) + '\n';
            text += '  سلبي               : ' + bar(neg) + '\n';
            text += '  محايد              : ' + bar(neu) + '\n';
        }
        const emoMap = {
            trust: 'الثقة', joy: 'الرضا', anticipation: 'التوقع',
            surprise: 'المفاجأة', anger: 'الغضب', fear: 'الخوف',
            sadness: 'الحزن', disgust: 'الاشمئزاز'
        };
        const emos = sentiment.emotions || {};
        const foundEmos = Object.keys(emoMap).filter(k => emos[k] > 0);
        if (foundEmos.length > 0) {
            text += '  ' + SEP2 + '\n  المشاعر الأساسية:\n';
            foundEmos.forEach(k => {
                text += '  ' + emoMap[k] + ': ' + bar(emos[k]) + '\n';
            });
        }
        text += '\n';
    } else {
        text += '  لم يتوفر تحليل وجداني للمصادر.\n\n';
    }

    // ══ SECTION 5: KEYWORDS TABLE ═════════════════════════════════════════════
    text += sec('٥', 'الكلمات المفتاحية والمفاهيم الإحصائية');
    if (keywords.length > 0) {
        text += '  #    المفهوم                          التكرار    المصادر    الكثافة\n';
        text += '  ' + SEP2 + '\n';
        keywords.forEach((kw, idx) => {
            const isObj = typeof kw === 'object' && kw !== null;
            const word  = isObj ? (kw.word  || '—') : String(kw);
            const freq  = isObj ? (kw.frequency   || '—') : '—';
            const sites = isObj ? (kw.sites_count || '—') : '—';
            const dens  = isObj ? (kw.density     || '—') : '—';
            const num   = String(idx + 1);
            text += '  ' + num + '    ' + word + '\n';
            text += '       التكرار: ' + freq + '  |  المصادر: ' + sites + '  |  الكثافة: ' + dens + '\n';
        });
        text += '\n';
    } else {
        text += '  لم يتم رصد كلمات مفتاحية كافية.\n\n';
    }

    // ══ SECTION 6: KEYWORD CONTEXT DISTRIBUTION ════════════════════════════════
    text += sec('٦', 'التوزيع السياقي للمفاهيم');
    const kwWithCtx = keywords.filter(k => typeof k === 'object' && k !== null &&
        ((k.distribution && k.distribution.length > 0) || (k.contexts && k.contexts.length > 0)));
    if (kwWithCtx.length > 0) {
        kwWithCtx.forEach((kw, idx) => {
            text += '\n  [' + (idx + 1) + '] "' + kw.word + '"  —  '
                + (kw.frequency || 0) + ' تكرار، ' + (kw.sites_count || 0) + ' مصدر\n';
            if (kw.distribution && kw.distribution.length > 0) {
                text += '  توزيع المصادر:\n';
                kw.distribution.slice(0, 6).forEach(d => {
                    text += '    • ' + (d.site || '—') + ' — ' + d.count + ' ظهور\n';
                });
            }
            if (kw.contexts && kw.contexts.length > 0) {
                text += '  سياقات دلالية:\n';
                kw.contexts.slice(0, 3).forEach(c => {
                    text += wrap('"...' + c.trim() + '..."', '    ');
                });
            }
            text += '  ' + SEP3 + '\n';
        });
    } else {
        text += '  لا توجد بيانات توزيع سياقي.\n\n';
    }

    // ══ SECTION 7: CATEGORIES TREE ════════════════════════════════════════════
    text += sec('٧', 'تصنيف المصادر حسب الفئة');
    const catEntries = Object.entries(categories).filter(function(e) {
        return Array.isArray(e[1]) && e[1].length > 0;
    });
    if (catEntries.length > 0) {
        catEntries.forEach(function(entry) {
            const catName = entry[0];
            const catResults = entry[1];
            text += '\n  [' + catName + ']  —  ' + catResults.length + ' مصدر\n';
            catResults.forEach((r, idx) => {
                const isLast = idx === catResults.length - 1;
                const branch = isLast ? '  └── ' : '  ├── ';
                const indent = isLast ? '       ' : '  │    ';
                const relPct = fmtScore(r.relevance_score, '—');
                text += branch + (r.title || r.url) + '  [صلة: ' + relPct + ']\n';
                text += indent + (r.url || '—') + '\n';
            });
        });
        text += '\n';
    } else {
        text += '  لا توجد مصادر مصنفة.\n\n';
    }

    // ══ SECTION 8: SOURCES COUNT ONLY ════════════════════════════════════════
    text += sec('٨', 'المراجع والمصادر');
    text += '  إجمالي المصادر المتتبعة : ' + results.length + ' مصدر\n';
    text += '  المصادر الفريدة         : ' + uniqueRes + ' مصدر\n';
    text += '  للاطلاع على قائمة المصادر الكاملة، استخدم خيار تصدير JSON.\n';
    // Top 5 sources only
    if (results.length > 0) {
        text += '\n  أبرز المصادر (أعلى 5 بالصلة):\n';
        const top5 = [...results].sort((a,b) => (b.relevance_score||0)-(a.relevance_score||0)).slice(0,5);
        top5.forEach((r, i) => {
            const relPct = fmtScore(r.relevance_score, '—');
            const domain = (r.url || '').replace(/https?:\/\//, '').split('/')[0];
            text += '  [' + (i + 1) + '] ' + (r.title || domain || '—').slice(0, 60) + '\n';
            text += '       ' + (domain || '—') + '  |  صلة: ' + relPct + '\n';
        });
    }

    // ══ SECTION 9: LIVE SEARCH LOG ════════════════════════════════════════════
    text += sec('٩', 'سجل مسار البحث الحي');
    if (searchPath.length > 0) {
        searchPath.forEach((step, i) => {
            const msg  = typeof step === 'string' ? step
                : (step.message || step.msg || JSON.stringify(step));
            const time = typeof step === 'object' ? (step.time || step.timestamp || '') : '';
            text += '  [' + String(i + 1).padStart(3) + '] '
                + (time ? '[' + time + ']  ' : '') + msg + '\n';
        });
    } else {
        text += '  لا توجد سجلات متوفرة.\n';
    }
    text += '\n';

    // ══ SECTION 10: AI SEMANTIC ANALYSIS SUMMARY ══════════════════════════════
    text += sec('١٠', 'ملخص التحليل الدلالي والشبكة المعرفية');

    // Category summary
    const catKeys = Object.keys(categories).filter(c => categories[c] && categories[c].length > 0);
    if (catKeys.length > 0) {
        text += subSec('الفئات المعرفية المكتشفة');
        catKeys.forEach(cat => {
            text += '  • ' + cat + '  (' + categories[cat].length + ' مصدر)\n';
        });
        text += '\n';
    }

    // Top keywords
    if (keywords.length > 0) {
        text += subSec('أبرز المفاهيم الدلالية');
        keywords.slice(0, 15).forEach((kw, i) => {
            const word = typeof kw === 'object' ? kw.word : String(kw);
            const freq = typeof kw === 'object' ? (kw.frequency || 1) : 1;
            text += '  ' + String(i + 1).padStart(2) + '. ' + word + '  (' + freq + ' تكرار)\n';
        });
        text += '\n';
    }

    // Sentiment wrap-up
    if (sentiment.overall) {
        text += subSec('الانطباع العام للمصادر');
        text += '  النبرة: ' + sentiment.overall + '\n';
        if (sentiment.objectivity != null) {
            text += '  الموضوعية: ' + (sentiment.objectivity * 100).toFixed(0) + '%'
                + '  |  الذاتية: ' + ((sentiment.subjectivity || 0) * 100).toFixed(0) + '%\n';
        }
        text += '\n';
    }

    // ══ FOOTER ════════════════════════════════════════════════════════════════
    text += '\n' + SEP + '\n';
    text += '  تم إصدار هذا التقرير بواسطة محرك ROOTSEARCH\n';
    text += '  الاستعلام: "' + queryStr + '"\n';
    text += '  ' + timestamp + '\n';
    text += SEP + '\n';

    const blob = new Blob(['\uFEFF' + text], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, 'rootsearch_report_' + queryStr.replace(/\s+/g, '_').slice(0, 40) + '_' + Date.now() + '.txt');
    showToast('تم تصدير التقرير بنجاح', 'success');
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

// ─── FATHOM LANDING PAGE HELPERS ───────────────────────────────────

function initCountUpCounters() {
    const counters = document.querySelectorAll('.stat-num');
    counters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-target'), 10);
        if (isNaN(target)) return;
        
        let start = 0;
        const duration = 1200; // Animation duration in ms
        const increment = target / (duration / 16); // ~60fps
        
        const updateCount = () => {
            start += increment;
            if (start < target) {
                counter.textContent = Math.floor(start);
                requestAnimationFrame(updateCount);
            } else {
                counter.textContent = target + (target === 600 || target === 1000 ? '+' : '');
            }
        };
        
        // Start animation
        updateCount();
    });
}

function runQuickQuery(queryText, modelName) {
    const input = document.getElementById('searchInput');
    if (!input) return;
    input.value = queryText;
    
    // Select the model
    selectDropdownModel(modelName);
    
    // Trigger input event to update submit state (like enabling the clear button)
    const inputEvent = new Event('input', { bubbles: true });
    input.dispatchEvent(inputEvent);
    
    // Call handleSearch with a mock event
    const mockEvent = {
        preventDefault: () => {}
    };
    handleSearch(mockEvent);
}