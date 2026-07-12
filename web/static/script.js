/* =============================================
   FUCKEN SEARCH - المحرك الخارق
   JavaScript - سكربتات الواجهة
   ============================================= */

// ===== المتغيرات العامة للشبكة التفاعلية =====
let visNetworkInstance = null;
let visNetworkData = null;
let isGraphPhysicsEnabled = true;

// ===== تهيئة الصفحة =====
document.addEventListener('DOMContentLoaded', function() {
    initTypingEffect();
    initParticles();
    initSearchInput();
    loadSystemStatus();
});

// ===== إشعارات Toast =====
function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
        error: 'fa-exclamation-circle',
        success: 'fa-check-circle',
        info: 'fa-info-circle',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}" aria-hidden="true"></i><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-8px)';
        toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        setTimeout(() => toast.remove(), 280);
    }, duration);
}

// ===== تحميل حالة النظام =====
async function loadSystemStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        const engineCount = document.getElementById('engineCount');
        const aiStatus = document.getElementById('aiStatus');
        if (engineCount && data.engines) {
            engineCount.textContent = data.engines.length;
        }
        if (aiStatus) {
            aiStatus.textContent = data.deep_analysis ? 'AI نشط' : 'AI معطل';
            aiStatus.style.color = data.deep_analysis ? 'var(--accent-4)' : 'var(--text-secondary)';
        }
    } catch (_) {
        // تجاهل — الواجهة تعمل بدون الحالة
    }
}

// ===== إدارة التبويبات (Tabs Layout) =====
const TAB_PANELS = {
    tree: 'searchTreeContainer',
    graph: 'knowledgeGraphContainer',
    analysis: 'analysisPanel',
    results: 'resultsListWrapper',
};

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('is-hidden');
    });

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
    });

    const panelId = TAB_PANELS[tabId];
    const panel = panelId ? document.getElementById(panelId) : null;
    if (panel) panel.classList.remove('is-hidden');

    const activeBtn = document.getElementById(`tab_${tabId}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.setAttribute('aria-selected', 'true');
    }

    if (tabId === 'graph' && visNetworkInstance) {
        setTimeout(() => visNetworkInstance.fit(), 120);
    }
}

// ===== تصفير البحث وبدء استعلام جديد (Reset Search) =====
function resetSearch() {
    // 1. مسح حقل الإدخال
    const input = document.getElementById('searchInput');
    if (input) {
        input.value = '';
    }
    
    // 2. إخفاء زر المسح
    const clearBtn = document.getElementById('clearBtn');
    if (clearBtn) {
        clearBtn.classList.remove('visible');
    }
    
    // 3. إخفاء قسم النتائج بالكامل
    const resultsSection = document.getElementById('resultsSection');
    if (resultsSection) {
        resultsSection.style.display = 'none';
    }
    
    // 4. إظهار قسم الرائج (إذا كان موجوداً بالصفحة الرئيسية)
    const trendingSection = document.getElementById('trendingSection');
    const searchSection = document.getElementById('searchSection');
    if (trendingSection) {
        trendingSection.style.display = 'block';
    }
    if (searchSection) {
        searchSection.classList.remove('is-sticky');
    }
    
    // 5. إخفاء زر "بحث جديد" نفسه
    const newSearchBtn = document.getElementById('newSearchBtn');
    if (newSearchBtn) {
        newSearchBtn.style.display = 'none';
    }
    
    // 6. تدمير كائن الشبكة التفاعلية لتفريغ الذاكرة
    if (visNetworkInstance) {
        visNetworkInstance.destroy();
        visNetworkInstance = null;
    }
    visNetworkData = null;
    
    // 7. تحديث الرابط بالمتصفح أو التوجيه للرئيسية
    const isSearchPage = window.location.pathname.includes('/search');
    if (isSearchPage) {
        window.location.href = '/';
    } else {
        window.history.pushState(null, "", "/");
        if (input) input.focus();
    }
}

// ===== تأثير الكتابة =====
function initTypingEffect() {
    const phrases = [
        'اكتشف كل شيء...',
        'ابحث في أعماق الإنترنت...',
        'لا شيء يخفى عنا...',
        'القوة الخارقة للبحث...',
        'Deep Search Without Limits...',
        'Analyze Everything...',
        'Find The Truth...',
        'Fucken Search Is Here...'
    ];
    
    const element = document.querySelector('.typing-text');
    if (!element) return;
    
    let phraseIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let isPaused = false;
    
    function typeEffect() {
        if (isPaused) {
            setTimeout(typeEffect, 2000);
            isPaused = false;
            return;
        }
        
        const currentPhrase = phrases[phraseIndex];
        
        if (isDeleting) {
            element.textContent = currentPhrase.substring(0, charIndex - 1);
            charIndex--;
        } else {
            element.textContent = currentPhrase.substring(0, charIndex + 1);
            charIndex++;
        }
        
        if (!isDeleting && charIndex === currentPhrase.length) {
            isPaused = true;
            isDeleting = true;
            setTimeout(typeEffect, 3000);
            return;
        }
        
        if (isDeleting && charIndex === 0) {
            isDeleting = false;
            phraseIndex = (phraseIndex + 1) % phrases.length;
        }
        
        const speed = isDeleting ? 30 : 80;
        setTimeout(typeEffect, speed);
    }
    
    typeEffect();
}

// ===== جزيئات الخلفية =====
function initParticles() {
    const container = document.getElementById('particles');
    if (!container) return;
    
    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: fixed;
            width: ${Math.random() * 3 + 1}px;
            height: ${Math.random() * 3 + 1}px;
            background: ${['#ff3366', '#00d4ff', '#7c3aed', '#10b981'][Math.floor(Math.random() * 4)]};
            border-radius: 50%;
            pointer-events: none;
            left: ${Math.random() * 100}vw;
            top: ${Math.random() * 100}vh;
            opacity: ${Math.random() * 0.5 + 0.1};
            animation: float-particle ${Math.random() * 10 + 10}s linear infinite;
            animation-delay: ${Math.random() * 5}s;
        `;
        container.appendChild(particle);
    }
}

// ===== إضافة CSS للجزيئات =====
const particleStyle = document.createElement('style');
particleStyle.textContent = `
    @keyframes float-particle {
        0% { transform: translateY(0) translateX(0); opacity: 0; }
        10% { opacity: ${Math.random() * 0.5 + 0.1}; }
        90% { opacity: ${Math.random() * 0.5 + 0.1}; }
        100% { transform: translateY(-100vh) translateX(${Math.random() * 100 - 50}px); opacity: 0; }
    }
`;
document.head.appendChild(particleStyle);

// ===== إدارة حقل البحث =====
function initSearchInput() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    
    if (!input) return;
    
    input.addEventListener('input', function() {
        if (clearBtn) {
            clearBtn.classList.toggle('visible', this.value.length > 0);
        }
    });
    
    // اختصارات لوحة المفاتيح
    document.addEventListener('keydown', function(e) {
        // Ctrl+K للتركيز على البحث
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            input.focus();
        }
        // Escape لمسح البحث
        if (e.key === 'Escape' && document.activeElement === input) {
            clearSearch();
            input.blur();
        }
    });
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    if (input) {
        input.value = '';
        input.focus();
    }
    if (clearBtn) {
        clearBtn.classList.remove('visible');
    }
}

function searchQuery(query) {
    const input = document.getElementById('searchInput');
    if (input) {
        input.value = query;
        handleSearch(new Event('submit'));
    }
}

// ===== معالجة البحث الرئيسي =====
let currentEventSource = null;

// دالة تظليل الكلمات المستعلم عنها
function highlightKeywords(text, query) {
    if (!text || !query) return text || '';
    
    const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 1);
    if (terms.length === 0) return text;
    
    const escapeRegex = (s) => s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    
    let highlighted = text;
    terms.forEach(term => {
        const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        highlighted = highlighted.replace(regex, '<span class="search-highlight">$1</span>');
    });
    
    return highlighted;
}

// دالة الانتقال السلس إلى بطاقة النتيجة للموقع
function scrollToSource(url) {
    if (!url) return;
    const cards = document.querySelectorAll('.result-card');
    let foundCard = null;
    
    const normUrl = url.toLowerCase().replace(/\/$/, '');
    
    for (let card of cards) {
        const cardUrl = card.querySelector('.result-url')?.textContent?.trim()?.toLowerCase()?.replace(/\/$/, '');
        if (cardUrl && (cardUrl === normUrl || cardUrl.includes(normUrl) || normUrl.includes(cardUrl))) {
            foundCard = card;
            break;
        }
    }
    
    if (foundCard) {
        const content = foundCard.querySelector('.result-content-expanded');
        if (content) {
            content.classList.add('visible');
            const expandBtn = foundCard.querySelector('.result-expand-btn');
            if (expandBtn) expandBtn.innerHTML = '<i class="fas fa-chevron-up"></i> إخفاء';
        }
        
        foundCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        foundCard.classList.remove('pulse-highlight');
        void foundCard.offsetWidth; // Reflow
        foundCard.classList.add('pulse-highlight');
    } else {
        window.open(url, '_blank');
    }
}

// دالة الانتقال إلى أول بطاقة تحتوي الكلمة المفتاحية
function scrollToKeyword(keyword) {
    if (!keyword) return;
    const cards = document.querySelectorAll('.result-card');
    let foundCard = null;
    
    const kwLower = keyword.toLowerCase();
    
    for (let card of cards) {
        const titleText = card.querySelector('.result-title')?.textContent?.toLowerCase() || '';
        const snippetText = card.querySelector('.result-snippet')?.textContent?.toLowerCase() || '';
        const bodyText = card.querySelector('.result-content-expanded')?.textContent?.toLowerCase() || '';
        
        if (titleText.includes(kwLower) || snippetText.includes(kwLower) || bodyText.includes(kwLower)) {
            foundCard = card;
            break;
        }
    }
    
    if (foundCard) {
        const content = foundCard.querySelector('.result-content-expanded');
        if (content) {
            content.classList.add('visible');
            const expandBtn = foundCard.querySelector('.result-expand-btn');
            if (expandBtn) expandBtn.innerHTML = '<i class="fas fa-chevron-up"></i> إخفاء';
        }
        
        foundCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        foundCard.classList.remove('pulse-highlight');
        void foundCard.offsetWidth;
        foundCard.classList.add('pulse-highlight');
    }
}

async function handleSearch(event, isPageLoad = false) {
    if (event) event.preventDefault();
    
    const input = document.getElementById('searchInput');
    if (!input) return;
    const query = input.value.trim();
    
    if (!query) return;
    
    const deepSearch = document.getElementById('deepSearch')?.checked ?? true;
    
    // 1. إبقاء الرابط كالصفحة الرئيسية لتسهيل عملية الريفرش النظيف دون التعليق على استعلامات سابقة
    window.history.pushState(null, "", "/");
    
    if (currentEventSource) {
        currentEventSource.close();
    }
    
    // 3. تدمير كائنات الرسوم البيانية والشبكة وتصفيرها بالكامل لمنع التداخل والتعليق
    if (visNetworkInstance) {
        visNetworkInstance.destroy();
        visNetworkInstance = null;
    }
    visNetworkData = null;
    const canvas = document.getElementById('knowledgeGraphCanvas');
    if (canvas) canvas.innerHTML = '';
    resetGraphSidebar();
    
    // 4. تصفير وتنظيف لوحات التحليل والفئات وتأثيرات التحميل
    const summaryContent = document.getElementById('summaryContent');
    const keywordsContent = document.getElementById('keywordsContent');
    const sentimentContent = document.getElementById('sentimentContent');
    const statsContent = document.getElementById('statsContent');
    
    if (summaryContent) summaryContent.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
    if (keywordsContent) keywordsContent.innerHTML = '';
    if (sentimentContent) sentimentContent.innerHTML = '';
    if (statsContent) statsContent.innerHTML = '';
    
    const categoriesNav = document.getElementById('categoriesNav');
    if (categoriesNav) {
        categoriesNav.innerHTML = '';
        categoriesNav.style.display = 'none';
    }
    
    const pagination = document.getElementById('pagination');
    if (pagination) pagination.innerHTML = '';
    
    const resultsSection = document.getElementById('resultsSection');
    const searchSection = document.getElementById('searchSection');
    const trendingSection = document.getElementById('trendingSection');
    const resultsList = document.getElementById('resultsList');
    const treeStatus = document.getElementById('treeStatus');
    const tree = document.getElementById('searchTree');
    
    resultsSection.style.display = 'block';
    if (searchSection) searchSection.classList.add('is-sticky');
    if (trendingSection) trendingSection.style.display = 'none';
    
    // إخفاء زر البحث الجديد أثناء العملية
    const newSearchBtn = document.getElementById('newSearchBtn');
    if (newSearchBtn) newSearchBtn.style.display = 'none';

    // إعادة بناء عنصر التحميل وتنظيف قائمة النتائج لمنع أخطاء العناصر المفقودة (DOM healing)
    if (resultsList) {
        resultsList.innerHTML = `
            <div class="loading-state" id="loadingState" style="display: block;">
                <div class="loader">
                    <div class="loader-circle"></div>
                    <div class="loader-circle"></div>
                    <div class="loader-circle"></div>
                </div>
                <p>جاري البحث في أعماق الإنترنت...</p>
                <div class="search-progress">
                    <div class="progress-item"><i class="fas fa-search"></i> البحث في المحركات...</div>
                    <div class="progress-item"><i class="fas fa-spider"></i> تسليق المواقع...</div>
                    <div class="progress-item"><i class="fas fa-brain"></i> تحليل النتائج...</div>
                </div>
            </div>
        `;
    }
    
    // تفعيل تبويب مسار البحث الحي تلقائياً عند بدء البحث
    switchTab('tree');
    if (treeStatus) treeStatus.textContent = 'تهيئة الاتصال بالمحرك الخارق لبدء البحث...';
    if (tree) tree.innerHTML = '';
    
    // بناء الهيكل الشجري المتفرع بالـ CSS
    tree.innerHTML = `
        <div class="tree-root-node"><i class="fas fa-search"></i> استعلام الاستكشاف: "${escapeHtml(query)}"</div>
        
        <div class="tree-categories-wrapper">
            
            <!-- الفئة الأولى: محركات البحث العامة -->
            <div class="tree-category-branch">
                <div class="tree-category-node"><i class="fas fa-search-plus"></i> محركات البحث العامة</div>
                <div class="tree-engines-wrapper">
                    <div class="tree-branch" id="branch_google">
                        <div class="tree-engine-node" id="node_google">
                            <span class="tree-node-icon"><i class="fab fa-google"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">Google</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_google"></div>
                    </div>
                    <div class="tree-branch" id="branch_bing">
                        <div class="tree-engine-node" id="node_bing">
                            <span class="tree-node-icon"><i class="fab fa-microsoft"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">Bing</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_bing"></div>
                    </div>
                    <div class="tree-branch" id="branch_duckduckgo">
                        <div class="tree-engine-node" id="node_duckduckgo">
                            <span class="tree-node-icon"><i class="fas fa-search"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">DuckDuckGo</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_duckduckgo"></div>
                    </div>
                    <div class="tree-branch" id="branch_brave">
                        <div class="tree-engine-node" id="node_brave">
                            <span class="tree-node-icon"><i class="fab fa-brave-reverse"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">Brave</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_brave"></div>
                    </div>
                </div>
            </div>

            <!-- الفئة الثانية: مصادر المعرفة والموسوعات -->
            <div class="tree-category-branch">
                <div class="tree-category-node"><i class="fas fa-book"></i> مصادر المعرفة والموسوعات</div>
                <div class="tree-engines-wrapper">
                    <div class="tree-branch" id="branch_wikipedia">
                        <div class="tree-engine-node" id="node_wikipedia">
                            <span class="tree-node-icon"><i class="fas fa-book-open"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">Wikipedia</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_wikipedia"></div>
                    </div>
                </div>
            </div>

            <!-- الفئة الثالثة: خوادم البحث الموزعة والخصوصية -->
            <div class="tree-category-branch">
                <div class="tree-category-node"><i class="fas fa-server"></i> خوادم البحث والخصوصية</div>
                <div class="tree-engines-wrapper">
                    <div class="tree-branch" id="branch_searx">
                        <div class="tree-engine-node" id="node_searx">
                            <span class="tree-node-icon"><i class="fas fa-server"></i></span>
                            <div class="tree-node-text">
                                <span class="tree-node-title">SearXNG</span>
                                <span class="tree-node-meta">انتظار...</span>
                            </div>
                        </div>
                        <div class="tree-leaves-container" id="leaves_searx"></div>
                    </div>
                </div>
            </div>

        </div>
    `;
    
    const startTime = Date.now();
    const url = `/api/search/stream?q=${encodeURIComponent(query)}&deep=${deepSearch}&nocache=${!isPageLoad}`;
    currentEventSource = new EventSource(url);
    
    currentEventSource.addEventListener('progress', function(e) {
        const data = JSON.parse(e.data);
        treeStatus.textContent = data.message;
        
        if (data.status === 'start' || data.status === 'searching') {
            document.querySelectorAll('.tree-engine-node').forEach(n => n.classList.add('active'));
        } 
        else if (data.status === 'engine_done') {
            const eng = data.engine;
            const count = data.count;
            const node = document.getElementById(`node_${eng}`);
            if (node) {
                node.classList.remove('active');
                if (count > 0) {
                    node.classList.add('success');
                    node.querySelector('.tree-node-meta').textContent = `تم جلب (${count})`;
                } else {
                    node.classList.add('failed');
                    node.querySelector('.tree-node-meta').textContent = 'محجوب / فارغ';
                }
            }
        }
        else if (data.status === 'search_done') {
            const sources = data.sources || {};
            const engines = ['google', 'bing', 'duckduckgo', 'wikipedia', 'brave', 'searx'];
            
            engines.forEach(eng => {
                const node = document.getElementById(`node_${eng}`);
                if (node) {
                    node.classList.remove('active');
                    
                    let hasResults = false;
                    let count = 0;
                    
                    if (eng === 'searx') {
                        const searxKeys = Object.keys(sources).filter(k => k.startsWith('searx_'));
                        if (searxKeys.length > 0) {
                            hasResults = true;
                            count = searxKeys.reduce((acc, k) => acc + sources[k], 0);
                        }
                    } else if (eng === 'wikipedia') {
                        const wikiKeys = Object.keys(sources).filter(k => k.startsWith('wikipedia_'));
                        if (wikiKeys.length > 0) {
                            hasResults = true;
                            count = wikiKeys.reduce((acc, k) => acc + sources[k], 0);
                        }
                    } else if (sources[eng]) {
                        hasResults = true;
                        count = sources[eng];
                    }
                    
                    if (hasResults) {
                        node.classList.add('success');
                        node.querySelector('.tree-node-meta').textContent = `تم جلب (${count})`;
                    } else {
                        node.classList.add('failed');
                        node.querySelector('.tree-node-meta').textContent = 'محجوب / فارغ';
                    }
                }
            });
        } 
        else if (data.status === 'scraping_progress') {
            let targetEng = 'searx';
            const src = data.source || '';
            if (src.startsWith('google')) targetEng = 'google';
            else if (src.startsWith('bing')) targetEng = 'bing';
            else if (src.startsWith('wikipedia')) targetEng = 'wikipedia';
            else if (src.startsWith('duckduckgo')) targetEng = 'duckduckgo';
            else if (src.startsWith('brave')) targetEng = 'brave';
            
            const leavesContainer = document.getElementById(`leaves_${targetEng}`);
            if (leavesContainer) {
                const successClass = data.success ? 'success' : 'failed';
                let iconHtml = '';
                
                if (data.success) {
                    try {
                        const domain = new URL(data.url).hostname;
                        iconHtml = `<img src="https://www.google.com/s2/favicons?sz=32&domain=${domain}" class="tree-node-favicon" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-block';" style="width: 14px; height: 14px; border-radius: 2px; margin-left: 4px; vertical-align: middle; display: inline-block;" /><i class="fas fa-check-circle" style="display: none;"></i>`;
                    } catch(err) {
                        iconHtml = `<i class="fas fa-check-circle"></i>`;
                    }
                } else {
                    iconHtml = `<i class="fas fa-times-circle" style="color: #ff3366;"></i>`;
                }
                
                const titleSafe = data.title ? data.title.substring(0, 20) : data.url.replace('https://', '').replace('http://', '').substring(0, 15);
                const meta = data.success ? `${data.word_count} كلمة` : 'فشل المسح';
                
                const nodeHtml = `
                    <div class="tree-leaf-node ${successClass}" title="${escapeHtml(data.title || data.url)}" onclick="scrollToSource(this.dataset.url)" data-url="${escapeHtml(data.url)}">
                        <span class="tree-node-icon">${iconHtml}</span>
                        <div class="tree-node-text">
                            <span class="tree-node-title">${escapeHtml(titleSafe)}...</span>
                            <span class="tree-node-meta">${meta}</span>
                        </div>
                    </div>
                `;
                leavesContainer.insertAdjacentHTML('beforeend', nodeHtml);
            }
        }
    });
    
    currentEventSource.addEventListener('complete', function(e) {
        currentEventSource.close();
        currentEventSource = null;
        
        const report = JSON.parse(e.data);
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        document.getElementById('searchTime').textContent = elapsed;
        
        treeStatus.innerHTML = `<span style="color: #ffffff; font-weight: bold;"><i class="fas fa-check-circle"></i> اكتملت عملية الميكنة والبحث بنجاح في ${elapsed} ثانية!</span>`;
        
        showToast(`اكتمل البحث — ${report.total_results || 0} نتيجة في ${elapsed} ثانية`, 'success', 3500);
        displayResults(report, elapsed);
    });
    
    currentEventSource.addEventListener('error', function() {
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        const message = 'فشل الاتصال بالخادم أو انقطع بث الأحداث الحية للبحث.';
        showToast(message, 'error');
        showError(message);
    });
}

// ===== عرض النتائج =====
function displayResults(data, elapsed) {
    const loadingState = document.getElementById('loadingState');
    const resultsList = document.getElementById('resultsList');
    
    if (loadingState) loadingState.style.display = 'none';
    
    // إظهار زر البحث الجديد لإمكانية البدء من جديد
    const newSearchBtn = document.getElementById('newSearchBtn');
    if (newSearchBtn) newSearchBtn.style.display = 'block';
    
    // عدد النتائج
    document.getElementById('resultsCount').textContent = data.total_results || 0;
    
    // عرض التحليل
    if (data.analysis) {
        displayAnalysis(data.analysis);
    }
    
    // عرض التصنيفات
    displayCategories(data.categories);
    
    // عرض النتائج
    if (data.results && data.results.length > 0) {
        resultsList.innerHTML = '';
        
        data.results.forEach((result, index) => {
            const card = createResultCard(result, index);
            resultsList.appendChild(card);
        });
    } else {
        showNoResults(document.getElementById('searchInput')?.value || '');
    }
    
    // التحويل التلقائي لتبويب الشبكة المعرفية أولاً لتأمين أبعاد الحاوية الفعلية للرسم ومنع عيوب الأبعاد الصفرية
    switchTab('graph');
    
    // تأجيل تهيئة الشبكة والتمرير قليلاً لتمكين المتصفح من حساب الأبعاد الحقيقية للمنطقة وعرضها بالكامل
    setTimeout(() => {
        initKnowledgeGraph(data);
        
        const graphContainer = document.getElementById('knowledgeGraphContainer');
        if (graphContainer) {
            graphContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, 150);
}

// ===== عرض التحليل =====
function displayAnalysis(analysis) {
    const summaryContent = document.getElementById('summaryContent');
    if (analysis.overall_summary) {
        if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
            const rawMarkup = marked.parse(analysis.overall_summary);
            const cleanMarkup = DOMPurify.sanitize(rawMarkup);
            summaryContent.innerHTML = `<div class="markdown-body">${cleanMarkup}</div>`;
        } else {
            summaryContent.innerHTML = `<p>${escapeHtml(analysis.overall_summary).replace(/\\n/g, '<br>')}</p>`;
        }
    } else {
        summaryContent.innerHTML = '<p style="color: var(--text-secondary); opacity: 0.6;">لا يوجد تلخيص متاح</p>';
    }
    
    // الكلمات المفتاحية
    const keywordsContent = document.getElementById('keywordsContent');
    if (analysis.keywords && analysis.keywords.length > 0) {
         keywordsContent.innerHTML = analysis.keywords.map(kw => 
            `<span class="keyword-tag" onclick="openKeywordModal(this.dataset.keyword)" data-keyword="${escapeHtml(kw)}">${escapeHtml(kw)}</span>`
        ).join('');
    } else {
        keywordsContent.innerHTML = '<p style="color: var(--text-secondary); opacity: 0.6;">لا توجد كلمات مفتاحية</p>';
    }
    
    // FUCKENBASE - التحليلات الفائقة والسرية
    const fuckenbaseContent = document.getElementById('fuckenbaseContent');
    if (fuckenbaseContent && analysis.sentiment_overview) {
        const sent = analysis.sentiment_overview;
        const query = analysis.query || document.getElementById('searchInput')?.value || '';
        const entropy = calculateEntropy(query);
        
        // تحديد مستوى مؤشر التعقب
        const queryLower = query.toLowerCase();
        let survLevel = 'low';
        let survLabel = 'آمن / طبيعي (LOW)';
        let survPercent = 15;
        if (queryLower.includes('hack') || queryLower.includes('security') || queryLower.includes('أمن') || queryLower.includes('اختراق') || queryLower.includes('spy') || queryLower.includes('vpn')) {
            survLevel = 'critical';
            survLabel = 'مراقب بشدة / خطر عالي (CRITICAL)';
            survPercent = 92;
        } else if (queryLower.length > 15) {
            survLevel = 'medium';
            survLabel = 'اشتباه متوسط (MEDIUM)';
            survPercent = 54;
        }
        
        // عقد Tor وهمية
        const mockTorRelays = [
            { ip: '185.220.101.5', port: 9001, country: 'DE (Germany)', exit: true },
            { ip: '45.12.99.102', port: 443, country: 'IS (Iceland)', exit: false },
            { ip: '109.201.154.23', port: 9002, country: 'US (United States)', exit: true }
        ];
        
        // نصوص الجليتش السرية للمصفوفة
        const matrixLogs = [
            `> INITIALIZING DEEP SCAN FOR "${query.toUpperCase()}"`,
            `> COHERENCE ENTROPY H(X): ${entropy}`,
            `> QUANTUM FLUX ITERATIONS: 8,429 SYNAPSES`,
            `> CIA WATCHDOG LEVEL: ${survLevel.toUpperCase()}`,
            `> TOR PROXY ROUTING: ACTIVE [3 NODES]`,
            `> SYSTEM STATUS: FUCKENBASE ENCRYPTED`,
            `> ACCESS GRANTED. WELCOME TO LAYER 2.`
        ].join('\n');

        const sentimentClass = sent.overall === 'إيجابي' ? 'sentiment-positive' : 
                              sent.overall === 'سلبي' ? 'sentiment-negative' : 'sentiment-neutral';
                              
        const emotions = sent.emotions || { trust: 0.4, anger: 0.1, fear: 0.1, joy: 0.2, sadness: 0.2 };
        
        fuckenbaseContent.innerHTML = `
            <div class="fuckenbase-layout">
                <div class="fuckenbase-tabs">
                    <button class="fb-tab-btn active" onclick="switchFbTab(this, 'fb_sentiment')"><i class="fas fa-heart-beat"></i> التحليل النفسي والعاطفي</button>
                    <button class="fb-tab-btn" onclick="switchFbTab(this, 'fb_secret')"><i class="fas fa-user-secret"></i> السجلات السرية والتعقب</button>
                    <button class="fb-tab-btn" onclick="switchFbTab(this, 'fb_quantum')"><i class="fas fa-atom"></i> الغرائب الكمومية والـ Tor</button>
                </div>
                
                <!-- Tab 1: Sentiment & Emotions -->
                <div id="fb_sentiment" class="fb-tab-content active">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                        <span style="font-size: 0.9rem; color: #888888;">التوجه النفسي العام للمصادر:</span>
                        <div class="sentiment-badge ${sentimentClass}" style="margin: 0; padding: 4px 12px; border-radius: 12px;">
                            <i class="fas ${sent.overall === 'إيجابي' ? 'fa-smile' : sent.overall === 'سلبي' ? 'fa-frown' : 'fa-meh'}"></i>
                            ${sent.overall}
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 12px;">
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">الموضوعية</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(sent.objectivity * 100).toFixed(0)}%; background: #60a5fa;"></div>
                            </div>
                            <span class="emotion-percent">${(sent.objectivity * 100).toFixed(0)}%</span>
                        </div>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">الذاتية</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(sent.subjectivity * 100).toFixed(0)}%; background: #f43f5e;"></div>
                            </div>
                            <span class="emotion-percent">${(sent.subjectivity * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                    
                    <div>
                        <h5 style="font-size: 0.8rem; color: #888888; margin-bottom: 8px;"><i class="fas fa-sliders-h"></i> التوزيع العاطفي الدقيق للنصوص:</h5>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">الثقة والأمان</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(emotions.trust * 100).toFixed(0)}%; background: #10b981;"></div>
                            </div>
                            <span class="emotion-percent">${(emotions.trust * 100).toFixed(0)}%</span>
                        </div>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">البهجة والأمل</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(emotions.joy * 100).toFixed(0)}%; background: #facc15;"></div>
                            </div>
                            <span class="emotion-percent">${(emotions.joy * 100).toFixed(0)}%</span>
                        </div>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">الحزن والأسف</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(emotions.sadness * 100).toFixed(0)}%; background: #6b7280;"></div>
                            </div>
                            <span class="emotion-percent">${(emotions.sadness * 100).toFixed(0)}%</span>
                        </div>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">التوجس والخوف</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(emotions.fear * 100).toFixed(0)}%; background: #a855f7;"></div>
                            </div>
                            <span class="emotion-percent">${(emotions.fear * 100).toFixed(0)}%</span>
                        </div>
                        <div class="emotion-progress-bar">
                            <span class="emotion-label">الغضب والرفض</span>
                            <div class="emotion-value-bar">
                                <div class="emotion-value-fill" style="width: ${(emotions.anger * 100).toFixed(0)}%; background: #ef4444;"></div>
                            </div>
                            <span class="emotion-percent">${(emotions.anger * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                </div>
                
                <!-- Tab 2: Secret Records -->
                <div id="fb_secret" class="fb-tab-content">
                    <div class="fb-surveillance-meter">
                        <div class="surv-level-header">
                            <span style="color: #888888;">مستوى تتبع ورقابة الأجهزة الأمنية:</span>
                            <span style="font-weight: bold; color: ${survLevel === 'critical' ? '#ff3366' : survLevel === 'medium' ? '#f59e0b' : '#34d399'};">${survLabel}</span>
                        </div>
                        <div class="surv-progress-bar">
                            <div class="surv-progress-fill ${survLevel}" style="width: ${survPercent}%;"></div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <h5 style="font-size: 0.8rem; color: #888888; margin-bottom: 6px;"><i class="fas fa-code-branch"></i> اتصالات NSA/CIA النشطة المعترضة للطلب (محاكاة):</h5>
                        <div class="matrix-glitch-text">
                            ${matrixLogs.replace(/\n/g, '<br>')}
                        </div>
                    </div>
                </div>
                
                <!-- Tab 3: Quantum & Tor -->
                <div id="fb_quantum" class="fb-tab-content">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">
                        <div style="background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                            <span style="font-size: 0.75rem; color: #888888; display: block;">مستوى التسلل في الويب العميق</span>
                            <span style="font-size: 1.15rem; font-weight: bold; color: #60a5fa;">${(45 + Math.random() * 30).toFixed(1)}%</span>
                        </div>
                        <div style="background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                            <span style="font-size: 0.75rem; color: #888888; display: block;">إنتروبيا ترميز الأحرف (Entropy)</span>
                            <span style="font-size: 1.15rem; font-weight: bold; color: #facc15;">H = ${entropy} bits</span>
                        </div>
                    </div>
                    
                    <div>
                        <h5 style="font-size: 0.8rem; color: #888888; margin-bottom: 6px;"><i class="fas fa-mask"></i> عقد عبور Tor المشفرة المستعملة للطلب الحالي:</h5>
                        <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); padding: 8px; border-radius: 6px;">
                            ${mockTorRelays.map((relay, idx) => `
                                <div class="tor-relay-item">
                                    <span>[NODE ${idx+1}] ${relay.ip}:${relay.port} (${relay.country}) ${relay.exit ? '➔ EXIT' : ''}</span>
                                    <span class="status-ok">✔ ACTIVE</span>
                                </div>
                            `).join('')}
                        </div>
                        <p style="font-size: 0.7rem; color: #666666; margin-top: 6px; text-align: center;"><i class="fas fa-info-circle"></i> يتم توليد وتوزيع مسارات Tor ديناميكياً لتأمين الخصوصية والمسح الخفي للمواقع.</p>
                    </div>
                </div>
            </div>
        `;
    } else {
        if (fuckenbaseContent) fuckenbaseContent.innerHTML = '<p style="color: var(--text-secondary); opacity: 0.6;">التحليلات والمعلومات غير متوفرة حالياً.</p>';
    }
    
    // الإحصائيات
    const statsContent = document.getElementById('statsContent');
    if (analysis.statistics) {
        const stats = analysis.statistics;
        statsContent.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">إجمالي النتائج</span>
                <span class="stat-value">${stats.total_results || 0}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">كلمات محللة</span>
                <span class="stat-value">${(stats.total_words_analyzed || 0).toLocaleString()}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">محركات البحث</span>
                <span class="stat-value">${stats.engines_count || 0}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">متوسط الأهمية</span>
                <span class="stat-value">${(stats.average_relevance * 100).toFixed(1) || 0}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">المصادر</span>
                <span class="stat-value">${Object.keys(stats.sources_used || {}).join('، ')}</span>
            </div>
        `;
    }
}

// ===== عرض التصنيفات =====
function displayCategories(categories) {
    const nav = document.getElementById('categoriesNav');
    if (!categories || Object.keys(categories).length === 0) {
        nav.style.display = 'none';
        return;
    }
    
    nav.style.display = 'flex';
    nav.innerHTML = '';
    
    const allBtn = document.createElement('button');
    allBtn.className = 'category-btn active';
    allBtn.textContent = 'الكل';
    allBtn.onclick = () => filterResults('all');
    nav.appendChild(allBtn);
    
    Object.entries(categories).forEach(([key, results]) => {
        const btn = document.createElement('button');
        btn.className = 'category-btn';
        btn.innerHTML = `${getCategoryIcon(key)} ${key} <span class="count">(${results.length})</span>`;
        btn.onclick = () => filterResults(key);
        btn.dataset.category = key;
        nav.appendChild(btn);
    });
}

function getCategoryIcon(category) {
    const icons = {
        'articles': '<i class="fas fa-newspaper"></i>',
        'videos': '<i class="fas fa-video"></i>',
        'social': '<i class="fas fa-share-alt"></i>',
        'academic': '<i class="fas fa-graduation-cap"></i>',
        'news': '<i class="fas fa-clock"></i>',
        'code': '<i class="fas fa-code"></i>',
        'products': '<i class="fas fa-shopping-cart"></i>',
        'other': '<i class="fas fa-globe"></i>',
    };
    return icons[category] || '<i class="fas fa-link"></i>';
}

function filterResults(category) {
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.toggle('active', 
            category === 'all' ? btn.textContent.trim() === 'الكل' : 
            btn.dataset.category === category
        );
    });
    
    document.querySelectorAll('.result-card').forEach(card => {
        if (category === 'all') {
            card.style.display = 'block';
        } else {
            card.style.display = card.dataset.category === category ? 'block' : 'none';
        }
    });
}

// ===== إنشاء بطاقة نتيجة =====
function createResultCard(result, index) {
    const card = document.createElement('div');
    card.className = 'result-card';
    card.dataset.category = result.content_type || 'other';
    card.style.animationDelay = `${index * 0.05}s`;
    
    const sourceIcon = result.source.startsWith('google') ? '<i class="fab fa-google"></i>' :
                       result.source.startsWith('bing') ? '<i class="fab fa-microsoft"></i>' :
                       result.source.startsWith('duckduckgo') ? '<i class="fas fa-search"></i>' :
                       result.source.startsWith('wikipedia') ? '<i class="fas fa-book-open"></i>' :
                       result.source.startsWith('brave') ? '<i class="fab fa-brave-reverse"></i>' :
                       result.source.startsWith('searx') ? '<i class="fas fa-server"></i>' :
                       '<i class="fas fa-globe"></i>';
    
    const snippet = result.snippet || '';
    const relevancePercent = (result.relevance_score * 100).toFixed(1);
    const queryInput = document.getElementById('searchInput')?.value || '';
    
    const highlightedTitle = highlightKeywords(escapeHtml(result.title || 'بدون عنوان'), queryInput);
    const highlightedSnippet = highlightKeywords(escapeHtml(snippet), queryInput);
    const highlightedPreview = highlightKeywords(escapeHtml(result.content_preview || ''), queryInput);
    
    const metadata = result.metadata || {};
    const ipAddress = metadata.resolved_ip || 'Resolved via Tor Node';
    const cardId = `card_ip_${index}`;
    
    card.innerHTML = `
        <div class="result-title">
            <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener" class="scramble-hover">
                ${highlightedTitle}
            </a>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
            <div class="result-url" onclick="scrollToSource(this.dataset.url)" data-url="${escapeHtml(result.url)}" style="cursor: pointer; text-decoration: underline; margin-bottom: 0;">${escapeHtml(result.url)}</div>
            <span class="hacker-ip-badge" onclick="toggleTraceroute('${cardId}', this.dataset.ip, this.dataset.url)" data-ip="${escapeHtml(ipAddress)}" data-url="${escapeHtml(result.url)}" title="انقر لعرض مسار الاتصال المشفر (Traceroute)">
                <i class="fas fa-network-wired"></i> IP: ${escapeHtml(ipAddress)}
            </span>
        </div>
        <div class="result-snippet">${highlightedSnippet || 'لا يوجد وصف'}</div>
        
        <!-- Traceroute Box -->
        <div id="${cardId}" class="hacker-traceroute-box" style="display: none;">
            <div class="traceroute-title"><i class="fas fa-terminal"></i> ROUTE TRACE TO ${escapeHtml(ipAddress)} [ESTABLISHING HOPS...]</div>
            <div class="traceroute-hops" id="hops_${cardId}"></div>
        </div>

        <div class="result-meta">
            <span class="result-source">${sourceIcon} ${result.source}</span>
            <span class="result-score">⭐ ${relevancePercent}%</span>
            ${result.content_length ? `<span>📄 ${(result.content_length / 1000).toFixed(1)}K</span>` : ''}
            <button class="result-expand-btn" onclick="toggleContent(this)">
                <i class="fas fa-chevron-down"></i> عرض المزيد
            </button>
            <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener" class="action-btn" style="width: auto; padding: 0 10px; font-size: 0.75rem; border-radius: 4px; display: inline-flex; text-decoration: none; height: 24px; align-items: center; gap: 4px;" title="زيارة الرابط">
                <i class="fas fa-external-link-alt"></i> فتح الرابط
            </a>
        </div>
        <div class="result-content-expanded">
            ${highlightedPreview || 'لا يوجد محتوى إضافي'}
        </div>
    `;
    
    return card;
}

function toggleContent(btn) {
    const content = btn.closest('.result-card').querySelector('.result-content-expanded');
    const isVisible = content.classList.toggle('visible');
    btn.innerHTML = isVisible ? 
        '<i class="fas fa-chevron-up"></i> إخفاء' : 
        '<i class="fas fa-chevron-down"></i> عرض المزيد';
}

// ===== تصدير النتائج =====
function exportAsJSON() {
    const resultsList = document.getElementById('resultsList');
    const cards = resultsList.querySelectorAll('.result-card');
    
    const results = Array.from(cards).map(card => {
        return {
            title: card.querySelector('.result-title')?.textContent?.trim() || '',
            url: card.querySelector('.result-url')?.textContent?.trim() || '',
            snippet: card.querySelector('.result-snippet')?.textContent?.trim() || '',
            source: card.querySelector('.result-source')?.textContent?.trim() || '',
            score: card.querySelector('.result-score')?.textContent?.trim() || '',
        };
    });
    
    const data = {
        query: document.getElementById('searchInput')?.value || '',
        timestamp: new Date().toISOString(),
        total: results.length,
        results: results,
    };
    
    downloadFile(JSON.stringify(data, null, 2), 'fucken-search-results.json', 'application/json');
}


function exportAsText() {
    const query = document.getElementById('searchInput')?.value || '';
    const summary = document.getElementById('summaryContent')?.textContent?.trim() || '';
    const resultsList = document.getElementById('resultsList');
    const cards = resultsList.querySelectorAll('.result-card');
    
    let text = `==================================================\n`;
    text += `          DEEP SEARCH RESULTS - DEEPSEARCH ENGINE\n`;
    text += `==================================================\n`;
    text += `الاستعلام (Query): ${query}\n`;
    text += `التاريخ (Date): ${new Date().toLocaleString()}\n`;
    text += `إجمالي النتائج (Total Results): ${cards.length}\n`;
    text += `==================================================\n\n`;
    
    if (summary && !summary.includes("جاري") && !summary.includes("Loading")) {
        text += `=== التلخيص الشامل للنتائج (Executive Summary) ===\n`;
        text += `${summary}\n`;
        text += `--------------------------------------------------\n\n`;
    }
    
    text += `=== تفاصيل نتائج البحث (Detailed Results) ===\n\n`;
    
    const sources = [];
    
    cards.forEach((card, i) => {
        const title = card.querySelector('.result-title')?.textContent?.trim() || 'بدون عنوان';
        const url = card.querySelector('.result-url')?.textContent?.trim() || 'N/A';
        const source = card.querySelector('.result-source')?.textContent?.trim() || 'N/A';
        const score = card.querySelector('.result-score')?.textContent?.trim() || 'N/A';
        const snippet = card.querySelector('.result-snippet')?.textContent?.trim() || '';
        const preview = card.querySelector('.result-content-expanded')?.textContent?.trim() || '';
        
        text += `[${i + 1}] العنوان (Title): ${title}\n`;
        text += `    المصدر (Source): ${source} | التوافق (Relevance): ${score}\n`;
        text += `    الوصف (Snippet): ${snippet}\n`;
        if (preview && !preview.includes("لا يوجد محتوى")) {
            const previewTrimmed = preview.length > 350 ? preview.substring(0, 350) + '...' : preview;
            text += `    المحتوى المرصود (Scraped Content):\n    ${previewTrimmed.split('\n').join('\n    ')}\n`;
        }
        text += `\n`;
        
        if (url && url !== 'N/A') {
            sources.push({ title, url });
        }
    });
    
    text += `==================================================\n`;
    text += `=== قائمة المصادر والمراجع المرقّمة (Sources Index) ===\n`;
    text += `==================================================\n`;
    
    if (sources.length > 0) {
        sources.forEach((src, idx) => {
            text += `${idx + 1}. [${src.title}] ➔ ${src.url}\n`;
        });
    } else {
        text += `لا توجد روابط مصادر خارجية متوفرة.\n`;
    }
    
    text += `\n==================================================\n`;
    text += `تم التصدير بنجاح بواسطة محرك DeepSearch Engine\n`;
    text += `==================================================\n`;
    
    downloadFile(text, `search-results-${query.replace(/\s+/g, '-')}.txt`, 'text/plain');
}

async function exportAsHTMLReport() {
    const query = document.getElementById('searchInput')?.value || '';
    if (!visNetworkData) {
        alert('يرجى الانتظار حتى اكتمال البحث لتصدير الشبكة المصدرية.');
        return;
    }
    
    let cssText = '';
    try {
        const response = await fetch('/static/style.css');
        if (response.ok) {
            cssText = await response.text();
        }
    } catch(err) {
        console.error("Failed to fetch stylesheet", err);
    }
    
    const treeContainer = document.getElementById('searchTreeContainer');
    const analysisPanel = document.getElementById('analysisPanel');
    const resultsList = document.getElementById('resultsList');
    
    const treeHtml = treeContainer ? treeContainer.outerHTML : '';
    const analysisHtml = analysisPanel ? analysisPanel.outerHTML : '';
    const resultsHtml = resultsList ? resultsList.outerHTML : '';
    
    let html = `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>DeepSearch Interactive Report - ${query}</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <!-- Vis.js CDN for Interactive Network Graph -->
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {
            background: #050505 !important;
            padding-top: 30px !important;
            color: #ffffff;
            font-family: 'Cairo', sans-serif;
            direction: rtl;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        /* Styles from original app */
        ${cssText}
        
        /* Offline overrides */
        .tab-content.is-hidden {
            display: none !important;
        }
        #knowledgeGraphContainer {
            display: block;
        }
        header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 25px;
        }
        header h1 {
            font-size: 2rem;
            margin: 0;
            color: #ffffff;
            font-weight: 700;
        }
        header p {
            color: #888888;
            margin: 10px 0 0 0;
            font-size: 0.95rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><i class="fas fa-project-diagram" style="margin-left: 10px;"></i> الشبكة المصدرية والمعرفية التفاعلية لتقرير البحث</h1>
            <p>الاستعلام (Query): <strong>"${query}"</strong> | تاريخ الاستخراج (Date): ${new Date().toLocaleString()}</p>
        </header>
        
        <!-- تبويبات عصرية للنتائج -->
        <div class="results-tabs">
            <button class="tab-btn active" id="tab_graph" onclick="switchTab('graph')">
                <i class="fas fa-project-diagram"></i> الشبكة المصدرية التفاعلية
            </button>
            <button class="tab-btn" id="tab_tree" onclick="switchTab('tree')">
                <i class="fas fa-stream"></i> مسار جلب المصادر
            </button>
            <button class="tab-btn" id="tab_analysis" onclick="switchTab('analysis')">
                <i class="fas fa-brain"></i> التلخيص والتحليلات
            </button>
            <button class="tab-btn" id="tab_results" onclick="switchTab('results')">
                <i class="fas fa-list-ul"></i> قائمة النتائج بالتفصيل
            </button>
        </div>

        <!-- شبكة المصادر التفاعلية الخارقة -->
        <div id="knowledgeGraphContainer" class="graph-section-wrapper tab-content">
            <div class="graph-header-controls">
                <div class="graph-title-desc">
                    <h3><i class="fas fa-project-diagram"></i> شبكة العلاقات المعرفية والمصادر</h3>
                    <p>خريطة ذهنية تفاعلية بالفيزياء تربط بين موضوع البحث، والمواقع، والكلمات المفتاحية المستخرجة بالذكاء الاصطناعي</p>
                </div>
                <div class="graph-control-buttons">
                    <button class="graph-ctrl-btn" onclick="toggleGraphPhysics()" id="physicsBtn" title="تجميد/تشغيل محاكاة الفيزياء">
                        <i class="fas fa-pause"></i> تجميد الشبكة
                    </button>
                    <button class="graph-ctrl-btn" onclick="resetGraphView()" title="توسيط وعرض كل العقد">
                        <i class="fas fa-expand"></i> توسيط
                    </button>
                </div>
            </div>
            <div class="graph-layout-grid">
                <div class="graph-canvas-container">
                    <div id="knowledgeGraphCanvas"></div>
                </div>
                <div class="graph-sidebar" id="graphSidebar">
                    <div class="sidebar-default-msg">
                        <i class="fas fa-mouse-pointer"></i>
                        <h4>استكشف الشبكة المصدرية</h4>
                        <p>انقر على أي عقدة (الموقع، الكلمة المفتاحية، أو الاستعلام) لعرض التحليل التفصيلي والروابط المعرفية هنا</p>
                    </div>
                    <div class="sidebar-details-content" style="display: none;"></div>
                </div>
            </div>
        </div>

        <!-- شجرة البحث التفاعلية الحية -->
        <div id="searchTreeContainer" class="search-tree-container tab-content">
            <div class="tree-header">
                <h3><i class="fas fa-network-wired"></i> مسار جلب وتحليل مصادر البيانات (شجرة البحث)</h3>
            </div>
            <div class="tree-wrapper">
                ${treeHtml ? treeHtml.replace(/id="searchTreeContainer"/g, '').replace(/class="[^"]*tab-content[^"]*"/g, '') : ''}
            </div>
        </div>

        <!-- لوحة التلخيص والتحليلات -->
        <div class="analysis-panel tab-content" id="analysisPanel">
            ${analysisHtml ? analysisHtml.replace(/class="[^"]*tab-content[^"]*"/g, '') : ''}
        </div>

        <!-- قائمة النتائج بالتفصيل -->
        <div id="resultsListWrapper" class="tab-content">
            <div class="results-list" id="resultsList">
                ${resultsHtml}
            </div>
        </div>
    <!-- نافذة تفاصيل المفهوم المعرفي الخارقة (Keyword Details Modal) -->
    <div id="keywordModal" class="fucken-modal" style="display: none;">
        <div class="fucken-modal-content">
            <div class="fucken-modal-header">
                <h3 id="modalKeywordTitle"><i class="fas fa-tag"></i> تفاصيل المفهوم: <span id="modalKeywordName" style="color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.3);"></span></h3>
                <span class="fucken-modal-close" onclick="closeKeywordModal()">&times;</span>
            </div>
            <div class="fucken-modal-body">
                <div class="modal-stats-grid">
                    <div class="m-stat-card">
                        <span class="m-stat-label">التكرار الإجمالي</span>
                        <span class="m-stat-value" id="modalKeywordFreq">0</span>
                    </div>
                    <div class="m-stat-card">
                        <span class="m-stat-label">المواقع التي ذكرته</span>
                        <span class="m-stat-value" id="modalKeywordSites">0</span>
                    </div>
                    <div class="m-stat-card">
                        <span class="m-stat-label">معدل الكثافة العام</span>
                        <span class="m-stat-value" id="modalKeywordDensity">0%</span>
                    </div>
                </div>
                
                <div class="modal-section">
                    <h4><i class="fas fa-chart-pie"></i> توزيع التكرار عبر المواقع والمصادر</h4>
                    <div id="modalKeywordDistribution" class="modal-dist-list">
                        <!-- سيتم تعبئتها ديناميكياً -->
                    </div>
                </div>
                
                <div class="modal-section">
                    <h4><i class="fas fa-quote-right"></i> السياقات النصية المكتشفة</h4>
                    <div id="modalKeywordContexts" class="modal-contexts-list">
                        <!-- سيتم تعبئتها ديناميكياً -->
                    </div>
                </div>
            </div>
            <div class="fucken-modal-footer">
                <button class="modal-btn btn-secondary" onclick="closeKeywordModal()">إغلاق</button>
                <button class="modal-btn btn-primary" id="modalScrollBtn"><i class="fas fa-chevron-down"></i> الانتقال لأول نتيجة</button>
                <button class="modal-btn btn-success" id="modalFilterBtn"><i class="fas fa-filter"></i> تصفية النتائج بهذا المفهوم</button>
            </div>
        </div>
    </div>
    </div>
    
    <script>
        // البيانات المدمجة بالكامل للعمل دون اتصال
        const visNetworkData = ${JSON.stringify(visNetworkData)};
        let visNetworkInstance = null;
        let isGraphPhysicsEnabled = true;

        // إدارة التبويبات بالتقرير المستقل
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => {
                el.classList.add('is-hidden');
            });
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
                btn.setAttribute('aria-selected', 'false');
            });
            
            const panels = { tree: 'searchTreeContainer', graph: 'knowledgeGraphContainer', analysis: 'analysisPanel', results: 'resultsListWrapper' };
            const panel = document.getElementById(panels[tabId]);
            if (panel) panel.classList.remove('is-hidden');
            
            const btn = document.getElementById('tab_' + tabId);
            if (btn) {
                btn.classList.add('active');
                btn.setAttribute('aria-selected', 'true');
            }
        }

        // تهيئة الشبكة عند تحميل التقرير
        document.addEventListener('DOMContentLoaded', function() {
            // إخفاء التحميل وعمل التنسيقات الأولية
            const actions = document.querySelectorAll('.results-actions, .save-network-btn, .new-search-btn, .pagination');
            actions.forEach(el => el.style.display = 'none');
            
            initKnowledgeGraph(visNetworkData);
            switchTab('graph');
        });

        // دمج دوال الشبكة للتأكد من عملها بدون إنترنت
        ${initKnowledgeGraph.toString()}
        ${showNodeDetails.toString()}
        ${resetGraphSidebar.toString()}
        ${toggleGraphPhysics.toString()}
        ${resetGraphView.toString()}
        ${scrollToSource.toString()}
        ${scrollToKeyword.toString()}
        ${toggleContent.toString()}
        ${escapeHtml.toString()}
        ${openKeywordModal.toString()}
        ${closeKeywordModal.toString()}
        ${switchFbTab.toString()}
        ${calculateEntropy.toString()}
        ${toggleTraceroute.toString()}
        ${scrambleText.toString()}
    <\/script>
</body>
</html>`;
    
    downloadFile(html, `interactive-search-network-${query.replace(/\s+/g, '-')}.html`, 'text/html');
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// ===== عرض الأخطاء =====
function showError(message) {
    const loadingState = document.getElementById('loadingState');
    const resultsList = document.getElementById('resultsList');
    const newSearchBtn = document.getElementById('newSearchBtn');
    const searchSection = document.getElementById('searchSection');
    
    if (loadingState) loadingState.style.display = 'none';
    if (newSearchBtn) newSearchBtn.style.display = 'block';
    if (searchSection) searchSection.classList.add('is-sticky');
    
    switchTab('results');
    
    if (resultsList) {
        resultsList.innerHTML = `
            <div class="no-results">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>حدث خطأ</h3>
                <p>${message}</p>
            </div>
        `;
    }
}

function showNoResults(query) {
    const loadingState = document.getElementById('loadingState');
    const resultsList = document.getElementById('resultsList');
    const newSearchBtn = document.getElementById('newSearchBtn');
    
    if (loadingState) loadingState.style.display = 'none';
    if (newSearchBtn) newSearchBtn.style.display = 'block';
    
    if (resultsList) {
        resultsList.innerHTML = `
            <div class="no-results">
                <i class="fas fa-search"></i>
                <h3>لا توجد نتائج</h3>
                <p>لم نعثر على نتائج لـ "${escapeHtml(query)}"</p>
                <p style="margin-top: 10px; font-size: 0.85rem; opacity: 0.6;">حاول تغيير صياغة الاستعلام أو استخدام كلمات مختلفة</p>
            </div>
        `;
    }
}

// ===== دوال مساعدة ودوال بناء الشبكة المصدرية =====
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// بناء وتصميم الشبكة المعرفية المصدرية بالفيزياء الحركية
function initKnowledgeGraph(report) {
    if (!report) return;
    visNetworkData = report;
    const canvasContainer = document.getElementById('knowledgeGraphCanvas');
    if (!canvasContainer) return;
    
    resetGraphSidebar();
    
    const query = report.query || "";
    const results = report.results || [];
    const analysis = report.analysis || {};
    const keywords = analysis.keywords || [];
    
    const nodes = [];
    const edges = [];
    
    // 1. العقدة المركزية (موضوع البحث)
    nodes.push({
        id: 'root',
        label: `🔍\\n${query.substring(0, 25)}${query.length > 25 ? '...' : ''}`,
        title: `الاستعلام: ${query}`,
        shape: 'dot',
        size: 30,
        color: {
            background: '#7c3aed',
            border: '#ffffff',
            highlight: { background: '#8b5cf6', border: '#ffffff' }
        },
        font: { color: '#ffffff', size: 14, face: 'Cairo', bold: true },
        shadow: { enabled: true, color: 'rgba(124, 58, 237, 0.6)', size: 15 },
        nodeType: 'query',
        data: report
    });
    
    // 2. عقد المصادر (أعلى 12 موقع)
    const topSources = results.slice(0, 12);
    topSources.forEach((src, idx) => {
        const srcId = `src_${idx}`;
        let domain = "";
        try {
            domain = new URL(src.url).hostname.replace('www.', '');
        } catch(e) {
            domain = src.source;
        }
        
        nodes.push({
            id: srcId,
            label: `${src.title.substring(0, 15)}...`,
            title: src.title,
            shape: 'dot',
            size: 18,
            color: {
                background: '#10b981',
                border: '#ffffff',
                highlight: { background: '#059669', border: '#ffffff' }
            },
            font: { color: '#cbd5e1', size: 10, face: 'Cairo' },
            shadow: { enabled: true, color: 'rgba(16, 185, 129, 0.4)', size: 10 },
            nodeType: 'source',
            data: src
        });
        
        // ربط المصدر بالعقدة المركزية
        edges.push({
            from: 'root',
            to: srcId,
            length: 160,
            width: 1.5,
            color: { color: 'rgba(255, 255, 255, 0.1)', highlight: '#10b981' }
        });
    });
    
    // 3. عقد الكلمات المفتاحية المعرفية (أعلى 15 كلمة)
    const topKeywords = keywords.slice(0, 15);
    topKeywords.forEach((kw, kIdx) => {
        const kwId = `kw_${kIdx}`;
        
        // البحث عن المواقع التي تتقاطع في هذه الكلمة
        const connectedSources = [];
        topSources.forEach((src, sIdx) => {
            const sourceText = `${src.title} ${src.snippet} ${src.content || ""}`.toLowerCase();
            if (sourceText.includes(kw.toLowerCase())) {
                connectedSources.push(`src_${sIdx}`);
            }
        });
        
        // لا تضف الكلمة إلا إذا كانت ترتبط بمصدر واحد على الأقل لمنع العقد العائمة
        if (connectedSources.length > 0) {
            nodes.push({
                id: kwId,
                label: kw,
                title: `كلمة مفتاحية: ${kw}`,
                shape: 'dot',
                size: 11,
                color: {
                    background: '#f43f5e',
                    border: '#ffffff',
                    highlight: { background: '#e11d48', border: '#ffffff' }
                },
                font: { color: '#aaaaaa', size: 9, face: 'Cairo' },
                nodeType: 'keyword',
                data: { keyword: kw, sourcesCount: connectedSources.length }
            });
            
            // ربط الكلمة بالمصادر التي تحتويها (ينشئ نسيج شبكي متكامل ورائع)
            connectedSources.forEach(srcId => {
                edges.push({
                    from: srcId,
                    to: kwId,
                    length: 110,
                    width: 0.8,
                    color: { color: 'rgba(244, 63, 94, 0.12)', highlight: '#f43f5e' },
                    dashes: true
                });
            });
        }
    });
    
    // رسم الشبكة بـ Vis
    const graphData = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };
    
    const graphOptions = {
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -60,
                centralGravity: 0.015,
                springLength: 120,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 1.0
            },
            stabilization: {
                enabled: true,
                iterations: 200,
                updateInterval: 25
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 150,
            zoomView: true,
            dragView: true
        }
    };
    
    visNetworkInstance = new vis.Network(canvasContainer, graphData, graphOptions);
    
    // تجميد الشبكة وحفظ تموضع العقد بمجرد الاستقرار لمنع الارتجاج العشوائي والحركة المستمرة
    visNetworkInstance.on("stabilized", function () {
        visNetworkInstance.setOptions({ physics: { enabled: false } });
        isGraphPhysicsEnabled = false;
        const physicsBtn = document.getElementById('physicsBtn');
        if (physicsBtn) {
            physicsBtn.innerHTML = '<i class="fas fa-play"></i> تحريك الشبكة';
        }
    });

    visNetworkInstance.on("stabilizationIterationsDone", function () {
        visNetworkInstance.setOptions({ physics: { enabled: false } });
        isGraphPhysicsEnabled = false;
        const physicsBtn = document.getElementById('physicsBtn');
        if (physicsBtn) {
            physicsBtn.innerHTML = '<i class="fas fa-play"></i> تحريك الشبكة';
        }
    });
    
    // التفاعل عند النقر على عقدة
    visNetworkInstance.on("click", function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const clickedNode = nodes.find(n => n.id === nodeId);
            if (clickedNode) {
                showNodeDetails(clickedNode);
            }
        } else {
            resetGraphSidebar();
        }
    });
}

function resetGraphSidebar() {
    const defaultMsg = document.querySelector('.sidebar-default-msg');
    const detailsContent = document.querySelector('.sidebar-details-content');
    if (defaultMsg) defaultMsg.style.display = 'flex';
    if (detailsContent) {
        detailsContent.style.display = 'none';
        detailsContent.innerHTML = '';
    }
}

function showNodeDetails(node) {
    const defaultMsg = document.querySelector('.sidebar-default-msg');
    const detailsContent = document.querySelector('.sidebar-details-content');
    if (defaultMsg) defaultMsg.style.display = 'none';
    if (!detailsContent) return;
    
    detailsContent.style.display = 'block';
    
    let html = "";
    
    if (node.nodeType === 'query') {
        const stats = node.data.analysis?.statistics || {};
        const sentiment = node.data.analysis?.sentiment_overview || {};
        html = `
            <div class="node-details-title">🔍 موضوع البحث الرئيسي</div>
            <div class="node-details-type type-query">الاستعلام المركزي</div>
            
            <div class="node-details-section">
                <h5>الاستعلام المطلوب</h5>
                <p style="font-weight: bold; font-size: 1.05rem; color: #ffffff;">"${escapeHtml(node.data.query)}"</p>
            </div>
            
            <div class="node-details-section">
                <h5>إحصائيات الشبكة</h5>
                <div class="stat-item">
                    <span class="stat-label">المصادر الفريدة</span>
                    <span class="stat-value" style="color:#10b981;">${node.data.total_results || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">متوسط ملاءمة المحتوى</span>
                    <span class="stat-value" style="color:#60a5fa;">${((stats.average_relevance || 0) * 100).toFixed(1)}%</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">كلمات تم تحليلها</span>
                    <span class="stat-value">${(stats.total_words_analyzed || 0).toLocaleString()}</span>
                </div>
            </div>
            
            <div class="node-details-section">
                <h5>التوجه والمشاعر للمصادر</h5>
                <p style="font-weight: bold; font-size: 0.95rem; color: ${sentiment.overall === 'إيجابي' ? '#34d399' : sentiment.overall === 'سلبي' ? '#fb7185' : '#f59e0b'}">
                    <i class="fas ${sentiment.overall === 'إيجابي' ? 'fa-smile' : sentiment.overall === 'سلبي' ? 'fa-frown' : 'fa-meh'}"></i>
                    ${sentiment.overall || 'محايد'} (${(sentiment.score || 0).toFixed(2)})
                </p>
            </div>
        `;
    } 
    else if (node.nodeType === 'source') {
        const src = node.data;
        const relevancePercent = (src.relevance_score * 100).toFixed(1);
        let domain = "";
        try {
            domain = new URL(src.url).hostname.replace('www.', '');
        } catch(e) {
            domain = src.source;
        }
        
        // جلب الكلمات المرتبطة بهذا الموقع
        const keywords = visNetworkData.analysis?.keywords || [];
        const sourceText = `${src.title} ${src.snippet} ${src.content || ""}`.toLowerCase();
        const srcKeywords = keywords.filter(kw => sourceText.includes(kw.toLowerCase())).slice(0, 6);
        
        html = `
            <div class="node-details-title" title="${escapeHtml(src.title)}">${escapeHtml(src.title.substring(0, 45))}...</div>
            <div class="node-details-type type-source">مصدر / موقع ويب</div>
            
            <div class="node-details-section">
                <h5>المصدر والنطاق</h5>
                <p><a href="${escapeHtml(src.url)}" target="_blank" style="color: #60a5fa; text-decoration: underline; word-break: break-all;">${domain}</a></p>
            </div>
            
            <div class="node-details-section">
                <h5>قوة الملاءمة والصلة</h5>
                <p style="font-size: 1.15rem; font-weight: bold; color: #10b981;">⭐ ${relevancePercent}%</p>
            </div>
            
            <div class="node-details-section">
                <h5>الوصف والمقتطف</h5>
                <p>${escapeHtml(src.snippet || "لا يوجد وصف متوفر.")}</p>
            </div>
            
            ${srcKeywords.length > 0 ? `
            <div class="node-details-section">
                <h5>المفاهيم والكلمات في الموقع</h5>
                <div class="sidebar-keywords-list">
                    ${srcKeywords.map(kw => `<span class="sidebar-kw-badge" onclick="scrollToKeyword(this.dataset.keyword)" data-keyword="${escapeHtml(kw)}">${escapeHtml(kw)}</span>`).join('')}
                </div>
            </div>
            ` : ''}
            
            <button class="sidebar-action-btn" onclick="scrollToSource(this.dataset.url)" data-url="${escapeHtml(src.url)}">
                <i class="fas fa-chevron-down"></i> عرض بطاقة النتيجة كاملة
            </button>
            <a href="${escapeHtml(src.url)}" target="_blank" class="sidebar-action-btn" style="background: transparent; border: 1px solid rgba(255,255,255,0.2); color: #ffffff; text-decoration: none; margin-top: 8px;">
                <i class="fas fa-external-link-alt"></i> فتح الرابط في علامة جديدة
            </a>
        `;
    } 
    else if (node.nodeType === 'keyword') {
        const kw = node.data;
        const results = visNetworkData.results || [];
        const matchingSources = [];
        results.forEach((src, idx) => {
            const text = `${src.title} ${src.snippet} ${src.content || ""}`.toLowerCase();
            if (text.includes(kw.keyword.toLowerCase())) {
                matchingSources.push(src);
            }
        });
        
        html = `
            <div class="node-details-title">🏷️ ${escapeHtml(kw.keyword)}</div>
            <div class="node-details-type type-keyword">مفهوم معرفي</div>
            
            <div class="node-details-section">
                <h5>الصلة في الشبكة</h5>
                <p>يرتبط هذا المفهوم بـ <strong>${kw.sourcesCount}</strong> مصادر مختلفة من المواقع التي تم جلبها.</p>
            </div>
            
            <div class="node-details-section">
                <h5>المواقع المرتبطة بهذا المفهوم</h5>
                <ul style="list-style: none; padding: 0; margin-top: 8px;">
                    ${matchingSources.map(src => {
                        let domain = "";
                        try { domain = new URL(src.url).hostname.replace('www.', ''); } catch(e) { domain = src.source; }
                        return `
                            <li style="margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px;">
                                <a href="javascript:void(0)" onclick="scrollToSource(this.dataset.url)" data-url="${escapeHtml(src.url)}" style="color: #60a5fa; font-size: 0.8rem; font-weight: bold; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    ${escapeHtml(src.title)}
                                </a>
                                <span style="font-size: 0.7rem; color: var(--text-secondary);">${domain} | ⭐ ${(src.relevance_score * 100).toFixed(0)}%</span>
                            </li>
                        `;
                    }).join('')}
                </ul>
            </div>
        `;
    }
    
    detailsContent.innerHTML = html;
}

function toggleGraphPhysics() {
    if (!visNetworkInstance) return;
    isGraphPhysicsEnabled = !isGraphPhysicsEnabled;
    
    visNetworkInstance.setOptions({
        physics: { enabled: isGraphPhysicsEnabled }
    });
    
    const physicsBtn = document.getElementById('physicsBtn');
    if (physicsBtn) {
        if (isGraphPhysicsEnabled) {
            physicsBtn.innerHTML = '<i class="fas fa-pause"></i> تجميد الشبكة';
        } else {
            physicsBtn.innerHTML = '<i class="fas fa-play"></i> تحريك الشبكة';
        }
    }
}

function resetGraphView() {
    if (!visNetworkInstance) return;
    visNetworkInstance.fit({
        animation: {
            duration: 1000,
            easingFunction: 'easeInOutQuad'
        }
    });
}

// ===== دالة حساب الإنتروبيا للاستعلام =====
function calculateEntropy(str) {
    if (!str) return 0;
    const freqs = {};
    for (let char of str) {
        freqs[char] = (freqs[char] || 0) + 1;
    }
    let entropy = 0;
    const len = str.length;
    for (let char in freqs) {
        const p = freqs[char] / len;
        entropy -= p * Math.log2(p);
    }
    return entropy.toFixed(3);
}

// ===== فتح وإعداد نافذة تفاصيل الكلمة المفتاحية (M-Modal) =====
function openKeywordModal(keyword) {
    const modal = document.getElementById('keywordModal');
    const modalName = document.getElementById('modalKeywordName');
    const modalFreq = document.getElementById('modalKeywordFreq');
    const modalSites = document.getElementById('modalKeywordSites');
    const modalDensity = document.getElementById('modalKeywordDensity');
    const modalDist = document.getElementById('modalKeywordDistribution');
    const modalContexts = document.getElementById('modalKeywordContexts');
    
    if (!modal) return;
    
    modalName.textContent = keyword;
    
    // حساب التكرارات واستخراج السياقات
    let totalCount = 0;
    let sitesCount = 0;
    let totalWordsInCorpus = 0;
    const distribution = [];
    const contexts = [];
    
    const results = visNetworkData?.results || [];
    
    results.forEach(res => {
        const title = res.title || '';
        const snippet = res.snippet || '';
        const content = res.content || '';
        const fullText = `${title} \n ${snippet} \n ${content}`;
        
        // حساب الكلمات الإجمالي للموقع
        const wordCount = fullText.split(/\s+/).length;
        totalWordsInCorpus += wordCount;
        
        // البحث عن الكلمة المفتاحية
        const escapedKw = keyword.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp(escapedKw, 'gi');
        const matches = fullText.match(regex);
        const count = matches ? matches.length : 0;
        
        if (count > 0) {
            totalCount += count;
            sitesCount++;
            distribution.push({
                title: res.title,
                url: res.url,
                count: count,
                density: ((count / wordCount) * 100).toFixed(3)
            });
            
            // استخراج جمل السياق
            const sentences = fullText.split(/[.!?؟\n]/);
            sentences.forEach(sentence => {
                const cleanSentence = sentence.trim();
                if (cleanSentence.toLowerCase().includes(keyword.toLowerCase()) && cleanSentence.length > keyword.length + 5 && cleanSentence.length < 250) {
                    if (!contexts.some(c => c.text === cleanSentence)) {
                        contexts.push({
                            text: cleanSentence,
                            source: res.title,
                            url: res.url
                        });
                    }
                }
            });
        }
    });
    
    // تحديث الأرقام الأساسية في المودال
    modalFreq.textContent = totalCount;
    modalSites.textContent = sitesCount;
    const overallDensity = totalWordsInCorpus > 0 ? ((totalCount / totalWordsInCorpus) * 100).toFixed(4) : '0';
    modalDensity.textContent = `${overallDensity}%`;
    
    // رسم توزيع التكرار كأشرطة تقدم رقمية
    if (distribution.length > 0) {
        distribution.sort((a, b) => b.count - a.count);
        const maxSiteCount = distribution[0].count;
        
        modalDist.innerHTML = distribution.slice(0, 5).map(item => {
            const percentage = ((item.count / maxSiteCount) * 100).toFixed(0);
            return `
                <div class="modal-dist-item">
                    <div class="modal-dist-meta">
                        <a href="javascript:void(0)" onclick="closeKeywordModal(); scrollToSource(this.dataset.url);" data-url="${escapeHtml(item.url)}" title="الانتقال للمصدر">${escapeHtml(item.title)}</a>
                        <span><strong>${item.count}</strong> مرات (كثافة: ${item.density}%)</span>
                    </div>
                    <div class="modal-dist-bar-wrapper">
                        <div class="modal-dist-bar-fill" style="width: ${percentage}%;"></div>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        modalDist.innerHTML = '<p style="color: #666; font-size: 0.85rem;">لا توجد تفاصيل توزيع متاحة.</p>';
    }
    
    // عرض جمل السياق
    if (contexts.length > 0) {
        const displayedContexts = contexts.slice(0, 6);
        modalContexts.innerHTML = displayedContexts.map(c => {
            const escapedKw = keyword.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
            const highlightRegex = new RegExp(`(${escapedKw})`, 'gi');
            const highlightedText = escapeHtml(c.text).replace(highlightRegex, '<span class="context-highlight">$1</span>');
            
            return `
                <div class="modal-context-item">
                    <p style="margin-bottom: 5px;">"${highlightedText}"</p>
                    <span style="font-size: 0.75rem; color: #888888; display: block; text-align: left;">المصدر: <a href="javascript:void(0)" onclick="closeKeywordModal(); scrollToSource(this.dataset.url);" data-url="${escapeHtml(c.url)}" style="color: #60a5fa; text-decoration: none;">${escapeHtml(c.source)}</a></span>
                </div>
            `;
        }).join('');
    } else {
        modalContexts.innerHTML = '<p style="color: #666; font-size: 0.85rem;">لا توجد سياقات نصية مباشرة متوفرة.</p>';
    }
    
    // ضبط أزرار التحكم في المودال
    const scrollBtn = document.getElementById('modalScrollBtn');
    const filterBtn = document.getElementById('modalFilterBtn');
    
    scrollBtn.onclick = () => {
        closeKeywordModal();
        scrollToKeyword(keyword);
    };
    
    filterBtn.onclick = () => {
        closeKeywordModal();
        
        // إدخال الكلمة في حقل البحث وتصفية النتائج محلياً
        const catBtn = document.createElement('button');
        catBtn.className = 'category-btn active';
        catBtn.id = 'filter_tag_active';
        catBtn.innerHTML = `<i class="fas fa-filter"></i> تصفية: ${escapeHtml(keyword)} <span class="count" onclick="event.stopPropagation(); filterResults('all'); this.parentNode.remove();" style="margin-right:5px; cursor:pointer;">×</span>`;
        
        const nav = document.getElementById('categoriesNav');
        if (nav) {
            const prev = document.getElementById('filter_tag_active');
            if (prev) prev.remove();
            nav.appendChild(catBtn);
            nav.style.display = 'flex';
        }
        
        document.querySelectorAll('.result-card').forEach(card => {
            const text = card.textContent.toLowerCase();
            if (text.includes(keyword.toLowerCase())) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    };
    
    // جلب وتحديث التفسير والتعريف الذكي للمفهوم أو الشخصية
    const explanationBox = document.getElementById('modalKeywordExplanation');
    if (explanationBox) {
        explanationBox.innerHTML = '<div class="loading-dots" style="padding: 5px 0;"><span></span><span></span><span></span></div>';
        
        const searchQueryVal = visNetworkData?.query || document.getElementById('searchInput')?.value || '';
        
        fetch(`/api/keyword/explain?q=${encodeURIComponent(searchQueryVal)}&kw=${encodeURIComponent(keyword)}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.explanation) {
                    // تأثير فك تشفير هكر عند عرض التوضيح
                    explanationBox.innerHTML = `<span class="explain-text" style="opacity: 0.95; font-weight: 500; font-family: 'Inter', sans-serif;"></span>`;
                    const explainTextSpan = explanationBox.querySelector('.explain-text');
                    scrambleText(explainTextSpan, data.explanation, 600);
                } else {
                    explanationBox.innerHTML = `<span style="color: #888; font-size: 0.8rem;"><i class="fas fa-exclamation-triangle"></i> لم يتم التوصل لتعريف سياقي محدد.</span>`;
                }
            })
            .catch(err => {
                console.error(err);
                explanationBox.innerHTML = `<span style="color: #888; font-size: 0.8rem;"><i class="fas fa-exclamation-triangle"></i> لم يتم التمكن من الاتصال بخدمة التحليل الذكي (خارج نطاق التغطية).</span>`;
            });
    }
    
    modal.style.display = 'flex';
}

function closeKeywordModal() {
    const modal = document.getElementById('keywordModal');
    if (modal) modal.style.display = 'none';
}

// ===== تبديل تبويبات FUCKENBASE =====
function switchFbTab(btn, tabId) {
    const parent = btn.closest('.fuckenbase-layout');
    parent.querySelectorAll('.fb-tab-btn').forEach(b => b.classList.remove('active'));
    parent.querySelectorAll('.fb-tab-content').forEach(c => c.classList.remove('active'));
    
    btn.classList.add('active');
    const content = document.getElementById(tabId);
    if (content) content.classList.add('active');
    
    // تأثير الجليتش البصري البسيط عند التبديل
    content.style.opacity = '0.3';
    setTimeout(() => {
        content.style.opacity = '1';
    }, 80);
}

// ===== تأثير فك التشفير الحركي (Scramble Effect) =====
function scrambleText(element, targetText, duration = 500) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*+-=';
    let start = null;
    const originalText = targetText;
    
    function step(timestamp) {
        if (!start) start = timestamp;
        const progress = timestamp - start;
        const fraction = Math.min(progress / duration, 1);
        
        let currentText = '';
        for (let i = 0; i < originalText.length; i++) {
            if (originalText[i] === ' ' || originalText[i] === '\n') {
                currentText += originalText[i];
                continue;
            }
            if (i / originalText.length < fraction) {
                currentText += originalText[i];
            } else {
                currentText += chars[Math.floor(Math.random() * chars.length)];
            }
        }
        element.textContent = currentText;
        
        if (progress < duration) {
            requestAnimationFrame(step);
        } else {
            element.textContent = targetText;
        }
    }
    requestAnimationFrame(step);
}

// ===== تبديل وعرض مسار الاتصال (Traceroute) =====
function toggleTraceroute(containerId, ip, url) {
    const box = document.getElementById(containerId);
    if (!box) return;
    
    const isVisible = box.style.display === 'block';
    if (isVisible) {
        box.style.display = 'none';
        return;
    }
    
    box.style.display = 'block';
    const hopsContainer = document.getElementById(`hops_${containerId}`);
    hopsContainer.innerHTML = '';
    
    let domain = 'target-host';
    try { domain = new URL(url).hostname; } catch(e) {}
    
    const clientIp = '10.244.8.109';
    const localGateway = '10.244.8.1';
    
    // إنشاء مسارات Tor المشفرة وعقد الاتصال
    const TorEntry = '185.220.101.5 (DE - Tor Entry Node)';
    const TorRelay = '45.12.99.102 (IS - Tor Middle Relay)';
    const TargetNode = `${ip} (${domain})`;
    
    const hops = [
        `[HOP 1] SECURE GATEWAY -> ${clientIp} | ping: 0.8ms`,
        `[HOP 2] LOCAL TUNNEL -> ${localGateway} | ping: 1.2ms`,
        `[HOP 3] TUNNEL ➔ WAN BRIDGE (US Proxy) | ping: 15.4ms`,
        `[HOP 4] WAN BRIDGE ➔ ${TorEntry} | ping: 48.2ms`,
        `[HOP 5] ${TorEntry} ➔ ${TorRelay} | ping: 112.5ms`,
        `[HOP 6] ${TorRelay} ➔ ${TargetNode} | ping: 82.9ms`,
        `[DECIPHER] SHA-256 CHECK: OK. INTEGRITY VERIFIED. PROTOCOL: HTTPS.`
    ];
    
    let currentHopIndex = 0;
    function printHop() {
        if (currentHopIndex >= hops.length) return;
        const line = document.createElement('div');
        line.className = 'traceroute-hop-line';
        if (currentHopIndex === hops.length - 1) {
            line.style.color = '#00ff66';
            line.style.fontWeight = 'bold';
        }
        line.textContent = hops[currentHopIndex];
        hopsContainer.appendChild(line);
        currentHopIndex++;
        setTimeout(printHop, 120);
    }
    printHop();
}

// ===== تهيئة تأثيرات التحويم العالمية للـ Scramble =====
document.addEventListener('mouseover', function(e) {
    const target = e.target;
    if (!target || !target.classList) return;
    if (target.classList.contains('glitch-text')) return;

    if ((target.classList.contains('scramble-hover') || target.classList.contains('keyword-tag') || target.classList.contains('fb-tab-btn')) && !target.dataset.scrambling) {
        target.dataset.scrambling = 'true';
        const originalText = target.textContent.trim();
        scrambleText(target, originalText);
        setTimeout(() => {
            delete target.dataset.scrambling;
        }, 700);
    }
});
