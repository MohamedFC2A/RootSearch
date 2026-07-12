/* ═══════════════════════════════════════════════════════════════
   RootSearch v3 — Complete JavaScript Engine
   Live Search Tree · SSE Consumer · Vis.js Graph · Export Utils
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ─── GLOBALS ─────────────────────────────────────────────────
let visNetworkInstance = null;
let visNetworkData     = null;
let isGraphPhysicsEnabled = true;
let currentSearchData  = null;
let currentQuery       = '';
let activeSSE          = null;
let searchStartTime    = 0;

// Live Tree state
const treeNodes = new Map();  // nodeId → DOM element

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initSearchInput();
    loadSystemStatus();
    // Keyboard shortcut Ctrl+K
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('searchInput')?.focus();
        }
    });
});

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

// ─── SYSTEM STATUS ────────────────────────────────────────────
async function loadSystemStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        const ec = document.getElementById('engineCount');
        if (ec && data.engines) ec.textContent = data.engines.length;
        setStatusDot('idle');
    } catch (_) { /* silent */ }
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
    if (tabId === 'graph' && visNetworkInstance) setTimeout(() => visNetworkInstance.fit(), 150);
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
    if (activeSSE) { activeSSE.close(); activeSSE = null; }
    document.getElementById('searchInput').value = '';
    document.getElementById('clearBtn').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('heroSection').style.display = '';
    treeNodes.clear();
    setStatusDot('idle', 'Ready');
}

// ─── HANDLE SEARCH ────────────────────────────────────────────
function handleSearch(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('searchInput');
    const query = input?.value?.trim();
    if (!query) { showToast('الرجاء إدخال استعلام البحث', 'error'); return false; }

    currentQuery = query;
    searchStartTime = Date.now();

    // Cancel any in-progress SSE
    if (activeSSE) { activeSSE.close(); activeSSE = null; }

    // Transition UI
    const heroSection = document.getElementById('heroSection');
    const resultsSection = document.getElementById('resultsSection');
    if (heroSection) heroSection.style.display = 'none';
    resultsSection.style.display = '';

    // Reset tree
    resetLiveTree();

    // Show tree tab immediately
    switchTab('tree');

    // Start SSE stream
    const deep = document.getElementById('deepSearch')?.checked ? 'true' : 'false';
    startSSEStream(query, deep);

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
    pending:    'PENDING',
    fetching:   'FETCHING',
    processing: 'PROCESSING',
    success:    'SUCCESS',
    failed:     'FAILED',
    rerouted:   'REROUTED',
};

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

function createTreeNode(nodeId, stage, status, label, metadata) {
    const col = document.getElementById(`col_${stage}`);
    if (!col) return null;

    const node = document.createElement('div');
    node.className = 'tree-node';
    node.dataset.nodeId = nodeId;
    node.dataset.status = status;
    node.dataset.stage = stage;

    const iconClass = STAGE_ICONS[stage] || 'fas fa-circle';

    node.innerHTML = `
        <div class="node-status-row">
            <span class="node-status-dot"></span>
            <span class="node-status-tag">${STAGE_LABELS[status] || status}</span>
        </div>
        <div class="node-label">${escapeHtml(label)}</div>
        <div class="node-microcopy" id="micro_${nodeId}">—</div>
    `;

    // Click opens bottom sheet
    node.addEventListener('click', () => openNodeSheet(nodeId, stage, status, label, metadata));

    col.appendChild(node);
    treeNodes.set(nodeId, node);

    activateStageHeader(stage);
    return node;
}

function updateTreeNode(nodeId, status, label, metadata) {
    let node = treeNodes.get(nodeId);
    if (!node) return;

    node.dataset.status = status;

    const statusTag = node.querySelector('.node-status-tag');
    if (statusTag) statusTag.textContent = STAGE_LABELS[status] || status;

    const labelEl = node.querySelector('.node-label');
    if (labelEl) labelEl.textContent = label;

    const micro = node.querySelector('.node-microcopy');
    if (micro && metadata) {
        const parts = [];
        if (metadata.words)   parts.push(`${metadata.words.toLocaleString()} words`);
        if (metadata.count !== undefined) parts.push(`${metadata.count} results`);
        if (metadata.method)  parts.push(metadata.method);
        if (metadata.cb_state && metadata.cb_state !== 'closed') parts.push(`CB: ${metadata.cb_state}`);
        micro.textContent = parts.join(' · ') || '—';
    } else if (micro) {
        micro.textContent = label.length > 40 ? label.slice(0, 40) + '…' : label;
    }

    // Add retry button on failed nodes with can_retry
    if (status === 'failed' && metadata?.can_retry) {
        if (!node.querySelector('.node-retry-btn')) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'node-retry-btn';
            retryBtn.innerHTML = '<i class="fas fa-redo-alt"></i> Retry';
            retryBtn.addEventListener('click', e => {
                e.stopPropagation();
                showToast('Retry triggered — restarting search...', 'info');
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

// ─── SSE STREAM CONSUMER ──────────────────────────────────────
function startSSEStream(query, deep) {
    const url = `/api/search/stream?q=${encodeURIComponent(query)}&deep=${deep}`;
    const sse = new EventSource(url);
    activeSSE = sse;

    setStatusDot('live', 'Searching...');
    document.getElementById('treeStatus').textContent = 'Pipeline starting...';

    // tree_node: create a new node
    sse.addEventListener('tree_node', e => {
        try {
            const d = JSON.parse(e.data);
            if (!treeNodes.has(d.nodeId)) {
                createTreeNode(d.nodeId, d.stage, d.status, d.label, d.metadata);
            } else {
                updateTreeNode(d.nodeId, d.status, d.label, d.metadata);
            }
        } catch (_) { /* ignore parse errors */ }
    });

    // node_status_update: update existing node
    sse.addEventListener('node_status_update', e => {
        try {
            const d = JSON.parse(e.data);
            if (!treeNodes.has(d.nodeId)) {
                // node may not exist yet on rapid events; skip
                return;
            }
            updateTreeNode(d.nodeId, d.status, d.label, d.metadata);
            // update status line with last interesting message
            if (['fetching','processing','success'].includes(d.status)) {
                document.getElementById('treeStatus').textContent = d.label;
            }
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
                document.getElementById('resultsCount').textContent = d.count;
            }
        } catch (_) {}
    });

    // complete: final report arrived
    sse.addEventListener('complete', e => {
        try {
            const report = JSON.parse(e.data);
            currentSearchData = report;

            const elapsed = ((Date.now() - searchStartTime) / 1000).toFixed(1);
            document.getElementById('searchTime').textContent = elapsed;
            document.getElementById('resultsCount').textContent = report.total_results || 0;
            document.getElementById('treeStatus').textContent =
                `Pipeline complete — ${report.total_results || 0} results in ${elapsed}s`;

            // Mark verification node done
            updateTreeNode('verification', 'success', 'Report ready ✓', null);

            // Populate all panels
            renderAnalysis(report);
            renderResultsList(report);
            buildKnowledgeGraph(report);

            setStatusDot('idle', 'Done');
            showToast(`تم العثور على ${report.total_results || 0} نتيجة`, 'success');

            // Auto-switch to analysis after 1.5s
            setTimeout(() => {
                if (report.analysis?.summary) switchTab('analysis');
            }, 1500);

        } catch(err) {
            console.error('complete parse error', err);
        } finally {
            sse.close();
            activeSSE = null;
        }
    });

    // error
    sse.addEventListener('error', e => {
        try {
            const d = JSON.parse(e.data);
            showToast(d.message || 'حدث خطأ', 'error');
            document.getElementById('treeStatus').textContent = `Error: ${d.message || 'Unknown'}`;
        } catch (_) {
            // connection error
            if (sse.readyState === EventSource.CLOSED) {
                setStatusDot('error', 'Disconnected');
            }
        }
    });

    sse.onerror = () => {
        if (sse.readyState === EventSource.CLOSED) {
            setStatusDot('error', 'Connection lost');
            activeSSE = null;
        }
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
        rootbaseEl.innerHTML = deep
            ? DOMPurify.sanitize(marked.parse(deep))
            : '<p style="color:var(--text-muted)">لا يوجد تحليل عميق متاح.</p>';
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

    // Build category nav
    const catNav = document.getElementById('categoriesNav');
    const cats = report.categories || {};
    if (catNav && Object.keys(cats).length) {
        catNav.innerHTML =
            `<button class="category-filter-btn active" onclick="filterByCategory('all', this)">
                <i class="fas fa-globe"></i> الكل (${results.length})
            </button>` +
            Object.entries(cats).map(([k, v]) =>
                `<button class="category-filter-btn" onclick="filterByCategory('${k}', this)">
                    ${categoryIcon(k)} ${k} (${v.length})
                </button>`
            ).join('');
    }

    // Render cards
    list.innerHTML = results.map((r, i) => resultCardHTML(r, i)).join('');
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

function resultCardHTML(r, idx) {
    const score = r.relevance_score ? (r.relevance_score * 100).toFixed(0) + '%' : '';
    const src = (r.source || '').split('|')[0];
    const wc = r.metadata?.word_count ? `${r.metadata.word_count.toLocaleString()} كلمة` : '';
    const scraped = r.metadata?.scraped ? '<i class="fas fa-check" style="color:var(--success-text)"></i> تم استخراجه' : '';
    const snippetHighlighted = highlightTerms(escapeHtml(r.snippet || ''), currentQuery);

    return `
    <article class="result-card" data-category="${r.content_type || 'other'}">
        <div class="result-source-row">
            <span class="result-source-badge">${escapeHtml(src)}</span>
            ${score ? `<span class="result-score">${score}</span>` : ''}
        </div>
        <h3 class="result-title">
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">
                ${escapeHtml(r.title || 'بدون عنوان')}
            </a>
        </h3>
        <div class="result-url">${escapeHtml(r.url || '')}</div>
        <p class="result-snippet">${snippetHighlighted}</p>
        <div class="result-footer">
            ${wc ? `<span class="result-meta-tag"><i class="fas fa-file-word"></i> ${wc}</span>` : ''}
            ${scraped}
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" class="result-open-btn">
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
    document.querySelectorAll('.category-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const list = document.getElementById('resultsList');
    if (!currentSearchData) return;

    const results = cat === 'all'
        ? currentSearchData.results || []
        : (currentSearchData.categories || {})[cat] || [];
    list.innerHTML = results.map((r, i) => resultCardHTML(r, i)).join('');
}

// ─── KNOWLEDGE GRAPH ──────────────────────────────────────────
function buildKnowledgeGraph(report) {
    const container = document.getElementById('knowledgeGraphCanvas');
    if (!container || typeof vis === 'undefined') return;

    if (visNetworkInstance) { visNetworkInstance.destroy(); visNetworkInstance = null; }

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();
    const results = report.results || [];
    const analysis = report.analysis || {};
    const kws = (analysis.keywords || analysis.top_keywords || []).slice(0, 15);

    // Center node
    nodes.add({ id: 'query', label: escapeHtml(report.query || ''), shape: 'box',
        color: { background: '#1A1E26', border: '#4A6CF7', highlight: { background: '#1A1E26', border: '#4A6CF7' } },
        font: { color: '#E2E6EF', size: 14 }, borderWidth: 2 });

    // Source nodes
    results.slice(0, 20).forEach((r, i) => {
        const id = `r${i}`;
        const dom = (r.url || '').replace(/https?:\/\//, '').split('/')[0];
        nodes.add({ id, label: escapeHtml(dom || r.title?.slice(0,20) || `Result ${i+1}`),
            shape: 'box', size: 12,
            color: { background: r.metadata?.scraped ? '#0A1F14' : '#12151A',
                     border: r.metadata?.scraped ? '#2A6B48' : '#2E3344' },
            font: { color: '#8892A4', size: 11 } });
        edges.add({ from: 'query', to: id, color: { color: '#222630' } });
    });

    // Keyword nodes
    kws.forEach((kw, i) => {
        const word = typeof kw === 'string' ? kw : (kw.word || '');
        if (!word) return;
        const id = `kw${i}`;
        nodes.add({ id, label: escapeHtml(word), shape: 'ellipse', size: 10,
            color: { background: '#0F1A40', border: '#2A4ABF' },
            font: { color: '#7E8799', size: 10 } });
        edges.add({ from: 'query', to: id, color: { color: '#1E2330' }, dashes: true });
    });

    const graphData = { nodes, edges };
    visNetworkData = graphData;

    const opts = {
        physics: { enabled: true, stabilization: { iterations: 80 },
            barnesHut: { gravitationalConstant: -6000, springLength: 180 } },
        interaction: { hover: true, tooltipDelay: 200 },
        layout: { improvedLayout: true },
        edges: { smooth: { type: 'cubicBezier' }, arrows: { to: { enabled: true, scaleFactor: 0.4 } } },
    };

    visNetworkInstance = new vis.Network(container, graphData, opts);

    visNetworkInstance.on('click', params => {
        if (!params.nodes.length) return;
        const id = params.nodes[0];
        const sidebar = document.getElementById('graphSidebar');
        const empty = sidebar?.querySelector('.sidebar-empty');
        const details = sidebar?.querySelector('.sidebar-details');
        if (empty) empty.style.display = 'none';
        if (details) {
            details.style.display = '';
            const r = id.startsWith('r') ? results[parseInt(id.slice(1))] : null;
            if (r) {
                details.innerHTML = `
                    <h4 style="font-size:14px;margin-bottom:8px">${escapeHtml(r.title || '')}</h4>
                    <a href="${escapeHtml(r.url)}" target="_blank" style="font-size:11px;color:var(--accent);word-break:break-all">${escapeHtml(r.url)}</a>
                    <p style="margin-top:10px;font-size:12px;color:var(--text-secondary)">${escapeHtml((r.snippet || '').slice(0, 200))}</p>
                `;
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
        fetch(`/api/keyword/explain?q=${encodeURIComponent(currentQuery)}&kw=${encodeURIComponent(kw)}`)
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
        distEl.innerHTML = dist.length
            ? dist.slice(0, 8).map(d => `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
                <span>${escapeHtml(d.site || d.url || '—')}</span>
                <span style="color:var(--text-muted)">${d.count || ''}</span>
              </div>`).join('')
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

// Close modal on backdrop click
document.addEventListener('click', e => {
    const modal = document.getElementById('keywordModal');
    if (modal && e.target === modal) closeKeywordModal();
});

// ─── EXPORT ───────────────────────────────────────────────────
function exportAsJSON() {
    if (!currentSearchData) { showToast('لا توجد نتائج للتصدير', 'error'); return; }
    const blob = new Blob([JSON.stringify(currentSearchData, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `rootsearch_${Date.now()}.json`);
    showToast('تم تصدير JSON', 'success');
}

function exportAsText() {
    if (!currentSearchData) { showToast('لا توجد نتائج للتصدير', 'error'); return; }
    const lines = (currentSearchData.results || []).map((r, i) =>
        `[${i+1}] ${r.title}\n${r.url}\n${r.snippet}\n`
    );
    const blob = new Blob([lines.join('\n---\n')], { type: 'text/plain' });
    downloadBlob(blob, `rootsearch_${Date.now()}.txt`);
    showToast('تم تصدير النص', 'success');
}

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
        </head><body><h1>RootSearch Report: ${escapeHtml(currentQuery)}</h1><p>${currentSearchData.total_results} نتيجة</p>${cards}</body></html>`;
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
