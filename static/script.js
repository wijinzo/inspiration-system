// ════════════════════════════════════════════
// 雙軌科普腳本自動化引擎 V3 — Frontend Script
// ════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {

    // ─── Global State ───
    const selectedState = {
        science: null, // { id, title, cardEl, type }
        spice: null,   // { id, title, cardEl, type }
    };

    let currentData = null;

    // ─── Pagination State (for Infinite Scroll) ───
    const PAGE_SIZE = 15;
    const paginationState = {
        science: { page: 1, total: 0, loading: false, done: false },
        social:  { page: 1, total: 0, loading: false, done: false },
        news:    { page: 1, total: 0, loading: false, done: false },
    };

    // ─── DOM Refs ───
    const generateBtn = document.getElementById('generateBtn');
    const surpriseBtn = document.getElementById('surpriseBtn');
    const retryBtn = document.getElementById('retryBtn');
    const retryFromError = document.getElementById('retryFromError');
    const saveBtn = document.getElementById('saveBtn');
    const copyHookBtn = document.getElementById('copyHookBtn');
    const generateScriptBtn = document.getElementById('generateScriptBtn');
    
    const scriptModal = document.getElementById('scriptModal');
    const closeScriptModalBtn = document.getElementById('closeScriptModalBtn');
    const scriptContentArea = document.getElementById('scriptContentArea');
    const exportWordBtn = document.getElementById('exportWordBtn');

    const resultEmpty = document.getElementById('resultEmpty');
    const resultLoader = document.getElementById('resultLoader');
    const resultContent = document.getElementById('resultContent');
    const loaderText = document.getElementById('loaderText');
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');

    const scienceList = document.getElementById('scienceList');
    const socialList = document.getElementById('socialList');
    const newsList = document.getElementById('newsList');
    const keywordsBadge = document.getElementById('keywordsBadge');

    const scienceCoreText = document.getElementById('scienceCoreText');
    const mechanismText = document.getElementById('mechanismText');
    const reasoningText = document.getElementById('reasoningText');
    const criticScoreInline = document.getElementById('criticScoreInline');
    const criticComment = document.getElementById('criticComment');
    const criticBreakdown = document.getElementById('criticBreakdown');
    const sourceArticles = document.getElementById('sourceArticles');

    const historyBtn = document.getElementById('historyBtn');
    const historyDrawer = document.getElementById('historyDrawer');
    const closeHistoryBtn = document.getElementById('closeHistoryBtn');
    const historyList = document.getElementById('historyList');

    // ─── Utility Functions ───

    function formatTimeAgo(dateString) {
        if (!dateString) return '從未更新';
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        if (diffInSeconds < 60) return '剛剛';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} 分鐘前`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} 小時前`;
        return `${Math.floor(diffInSeconds / 86400)} 天前`;
    }

    function getScoreColor(score) {
        if (score >= 8) return '#4ade80';
        if (score >= 6) return '#fbbf24';
        return '#ef4444';
    }

    function getDomainFromUrl(url) {
        try {
            return new URL(url).hostname.replace('www.', '');
        } catch {
            return '';
        }
    }

    // ─── Card Rendering ───

    function getSourceBadge(item) {
        const src = (item.source || item.source_type || '').toLowerCase();

        if (src.includes('youtube') && src.includes('熱門')) {
            return `<span class="pipeline-badge yt-badge"><i class="fa-brands fa-youtube"></i> YouTube 熱門排行</span>`;
        }
        if (src.includes('youtube') || src.includes('yt')) {
            const channelName = item.channel_name || item.source || 'YouTube';
            const shortsTag = item.is_short ? ' <span class="shorts-tag">#Shorts</span>' : '';
            return `<span class="pipeline-badge yt-channel-badge"><i class="fa-brands fa-youtube"></i> ${channelName}</span>${shortsTag}`;
        }
        if (src.includes('ptt')) {
            return `<span class="pipeline-badge ptt-badge"><i class="fa-solid fa-comment"></i> PTT</span>`;
        }
        if (src.includes('瓦特') || src.includes('watt')) {
            return `<span class="pipeline-badge wb-badge"><i class="fa-solid fa-gamepad"></i> 瓦特兄弟</span>`;
        }
        if (src.includes('溫度計') || src.includes('dailyview')) {
            return `<span class="pipeline-badge dv-badge"><i class="fa-solid fa-temperature-half"></i> 網路溫度計</span>`;
        }
        if (src.includes('google trends') || src.includes('google趨勢')) {
            return `<span class="pipeline-badge gt-badge"><i class="fa-brands fa-google"></i> Google 熱搜</span>`;
        }
        if (src.includes('自由時報') || src.includes('公視') || src.includes('news')) {
            const name = item.source || '新聞';
            return `<span class="pipeline-badge news-badge"><i class="fa-solid fa-newspaper"></i> ${name}</span>`;
        }
        return `<span class="pipeline-badge">${item.source || ''}</span>`;
    }

    function getCredibilityBadge(item) {
        if (!item.credibility_score) return '';
        const score = item.credibility_score;
        const domain = getDomainFromUrl(item.url || '');
        const stars = '⭐'.repeat(score);
        const cls = `stars-${score}`;
        return `<span class="credibility-badge ${cls}" title="可信度 ${score}/3">${stars} ${domain}</span>`;
    }

    function renderAnimeMeme(item) {
        if (!item.anime_meme) return '';
        const meme = item.anime_meme;
        const topics = meme.related_topics || [];
        if (topics.length === 0) return '';
        // Only render expandable section for related_topics
        const relatedHtml = topics.map(t => `
            <div class="meme-item">
                <div class="meme-item__title">${t.title || ''}</div>
                <div class="meme-item__summary">${t.description || ''}</div>
            </div>
        `).join('');
        return `
            <div class="anime-meme-section">
                <button class="anime-meme-toggle" onclick="toggleAnimeMeme(event, this)">
                    <i class="fa-solid fa-lightbulb"></i> 相關話題 ▾
                </button>
                <div class="anime-meme-content hidden">
                    ${relatedHtml}
                </div>
            </div>`;
    }

    function renderCard(item, index, cardType) {
        const id = item.url || item.id || `${cardType}-${index}`;
        const title = item.title || '無標題';
        const summary = item.summary || '';
        // Tags: show mechanism if exists, else show anime meme
        let mechanism = '';
        if (item.mechanism) {
            const icon = (cardType === 'science') ? 'fa-atom' : 'fa-brain';
            const cls = (cardType === 'science') ? 'science-mechanism' : 'trend-mechanism';
            mechanism = `<div class="mechanism-tag ${cls}"><i class="fa-solid ${icon}"></i> ${item.mechanism}</div>`;
        } else if (item.anime_meme && item.anime_meme.anime) {
            const memeText = `${item.anime_meme.anime}：${item.anime_meme.meme || ''}`;
            mechanism = `<div class="mechanism-tag trend-mechanism"><i class="fa-solid fa-masks-theater"></i> ${memeText}</div>`;
        }

        // Keywords
        const keywords = (item.keywords || item.matched_keywords || []);
        const keywordHtml = keywords.length > 0
            ? `<div class="keyword-pills">${keywords.map(k => `<span class="pill">${k}</span>`).join('')}</div>`
            : '';

        // Badges
        let badgeHtml = '';
        if (cardType === 'science') {
            const pipelineBadge = item.pipeline === 'RSS'
                ? '<span class="pipeline-badge rss-badge"><i class="fa-solid fa-rss"></i> RSS</span>'
                : '<span class="pipeline-badge brave-badge"><i class="fa-solid fa-shield"></i> Brave</span>';
            badgeHtml = pipelineBadge + getCredibilityBadge(item);
        } else {
            badgeHtml = getSourceBadge(item);
            // Add Category Badge if specific
            if (item.category && item.category !== 'social_trend' && item.category !== 'trend') {
                const catLabels = { 
                    'gaming_meme': '遊戲迷因', 
                    'anime': '動漫相關', 
                    'meme': '網路梗圖'
                };
                const catLabel = catLabels[item.category] || item.category;
                badgeHtml += `<span class="pipeline-badge category-badge">${catLabel}</span>`;
            }
        }

        // Source link
        const linkClass = cardType === 'science' ? 'source-link-science' : '';
        const linkText = cardType === 'science' ? '查看論文' : '查看來源';
        const sourceLink = item.url
            ? `<a href="${item.url}" target="_blank" class="source-link ${linkClass}" onclick="event.stopPropagation()">${linkText} <i class="fa-solid fa-arrow-up-right-from-square"></i></a>`
            : '';

        // Anime meme — only render expandable section for related_topics now
        const animeMeme = renderAnimeMeme(item);

        // Thumbnail
        const thumbnail = item.thumbnail
            ? `<img class="card-thumbnail" src="${item.thumbnail}" alt="" loading="lazy">`
            : '';

        // Description expand toggle
        const isLong = summary.length > 80;

        return `
            <div class="data-card fade-in" data-id="${id}" data-type="${cardType}"
                 onclick="selectCard(this, '${cardType}')" style="animation-delay: ${index * 0.05}s">
                ${thumbnail}
                <div class="card-header">
                    <h3 class="card-title">${title}</h3>
                    <div class="card-badges">${badgeHtml}</div>
                </div>
                <p class="card-description${isLong ? '' : ' expanded'}">${summary}</p>
                ${isLong ? '<button class="expand-toggle" onclick="toggleExpand(event, this)">展開 ▾</button>' : ''}
                ${mechanism}
                ${keywordHtml}
                ${animeMeme}
                ${sourceLink}
            </div>
        `;
    }

    // ─── Card Selection ───

    window.selectCard = function (cardEl, cardType) {
        const id = cardEl.dataset.id;
        const titleEl = cardEl.querySelector('.card-title');
        const title = titleEl ? titleEl.textContent.trim() : '';

        const slotType = (cardType === 'science') ? 'science' : 'spice';

        // Already selected same card → deselect
        if (selectedState[slotType]?.id === id) {
            deselectCard(slotType);
            return;
        }

        // Deselect previous in same slot
        if (selectedState[slotType]) {
            const oldCard = selectedState[slotType].cardEl;
            oldCard.classList.remove('selected', 'selected-science');
        }

        // Mark new selection
        const selectedClass = slotType === 'science' ? 'selected-science' : 'selected';
        cardEl.classList.add(selectedClass);

        selectedState[slotType] = { id, title, cardEl, type: cardType };

        updateSelectionBar(slotType, title);
        updateGenerateBtn();

        // Dynamic feedback for science
        if (slotType === 'science') {
            const emptyMsg = document.querySelector('#resultEmpty p');
            const emptySub = document.querySelector('#resultEmpty .result-empty__sub');
            if (emptyMsg) emptyMsg.innerHTML = '✨ 核心定錨完畢！';
            if (emptySub) emptySub.innerHTML = '可直接點擊「啟動生成」，或去左側尋找時事加味';
        }
    };

    function deselectCard(slotType) {
        if (!selectedState[slotType]) return;
        const selectedClass = slotType === 'science' ? 'selected-science' : 'selected';
        selectedState[slotType].cardEl.classList.remove(selectedClass);
        selectedState[slotType] = null;
        updateSelectionBar(slotType, null);
        updateGenerateBtn();

        // Reset empty state text
        if (slotType === 'science') {
            const emptyMsg = document.querySelector('#resultEmpty p');
            const emptySub = document.querySelector('#resultEmpty .result-empty__sub');
            if (emptyMsg) emptyMsg.innerHTML = '選取科學文章後啟動生成';
            if (emptySub) emptySub.innerHTML = '可加選社群梗或時事以提升配對精度';
        }
    }

    window.clearSlot = function (slotType) {
        deselectCard(slotType);
    };

    // ─── Selection Bar Update ───

    function updateSelectionBar(slotType, title) {
        const slotMap = {
            science: {
                valEl: 'slotScienceVal', slotEl: 'slotScience', clearEl: null,
                emptyText: '請選擇科學文章（必選）',
                filledClass: 'sel-slot--filled-science', requiredClass: 'sel-slot--required'
            },
            spice: {
                valEl: 'slotSpiceVal', slotEl: 'slotSpice', clearEl: 'slotSpiceClear',
                emptyText: '選擇社群梗或新聞（可選）', filledClass: 'sel-slot--filled'
            },
        };

        const cfg = slotMap[slotType];
        const valEl = document.getElementById(cfg.valEl);
        const slotEl = document.getElementById(cfg.slotEl);
        const clearEl = cfg.clearEl ? document.getElementById(cfg.clearEl) : null;

        if (title) {
            valEl.textContent = title;
            if (cfg.requiredClass) slotEl.classList.remove(cfg.requiredClass);
            slotEl.classList.add(cfg.filledClass);
            if (clearEl) clearEl.classList.remove('hidden');
            if (slotType === 'science') {
                const hint = document.getElementById('scienceHint');
                if (hint) hint.classList.add('hidden');
            }
        } else {
            valEl.textContent = cfg.emptyText;
            slotEl.classList.remove(cfg.filledClass);
            if (cfg.requiredClass) slotEl.classList.add(cfg.requiredClass);
            if (clearEl) clearEl.classList.add('hidden');
            if (slotType === 'science') {
                const hint = document.getElementById('scienceHint');
                if (hint) hint.classList.remove('hidden');
            }
        }
    }

    function updateGenerateBtn() {
        generateBtn.disabled = !selectedState.science;
    }

    // ─── Expand / Collapse Toggles ───

    window.toggleExpand = function (event, btn) {
        event.stopPropagation();
        const desc = btn.previousElementSibling;
        const isExpanded = desc.classList.toggle('expanded');
        btn.textContent = isExpanded ? '收起 ▴' : '展開 ▾';
    };

    window.toggleAnimeMeme = function (event, btn) {
        event.stopPropagation();
        const content = btn.nextElementSibling;
        const isHidden = content.classList.toggle('hidden');
        btn.innerHTML = isHidden
            ? '<i class="fa-solid fa-masks-theater"></i> 相關話題梗 ▾'
            : '<i class="fa-solid fa-masks-theater"></i> 相關話題梗 ▴';
    };

    // ─── Tab Switching (Left Panel) ───

    function initTabs() {
        document.querySelectorAll('.panel-tabs .tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const target = btn.dataset.tab;
                // Update tab buttons
                document.querySelectorAll('.panel-tabs .tab-btn').forEach(b => b.classList.remove('tab-btn--active'));
                btn.classList.add('tab-btn--active');
                // Switch panels
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
                const panelId = `tab${target.charAt(0).toUpperCase() + target.slice(1)}`;
                const panel = document.getElementById(panelId);
                if (panel) panel.classList.remove('hidden');
            });
        });
    }

    // ─── Hook Tab Switching (Right Panel) ───

    function initHookTabs() {
        document.querySelectorAll('.hook-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = btn.dataset.hook;
                document.querySelectorAll('.hook-tab-btn').forEach(b => b.classList.remove('hook-tab-btn--active'));
                btn.classList.add('hook-tab-btn--active');
                document.querySelectorAll('.hook-quote').forEach(q => q.classList.add('hidden'));
                const hookEl = document.getElementById(`hookTab${idx}`);
                if (hookEl) hookEl.classList.remove('hidden');
            });
        });
    }

    // ─── Data Loading (Paginated) ───

    async function loadPage(type, page) {
        const apiMap = {
            science: '/api/data/science',
            social:  '/api/data/social',
            news:    '/api/data/trends',
        };
        const listMap = {
            science: scienceList,
            social:  socialList,
            news:    newsList,
        };
        const cardTypeMap = {
            science: 'science',
            social:  'social',
            news:    'trend',
        };

        const state = paginationState[type];
        if (state.loading || state.done) return;
        state.loading = true;

        // Show a small loading indicator at the bottom
        const listEl = listMap[type];
        const loaderEl = document.createElement('div');
        loaderEl.className = 'scroll-loader';
        loaderEl.innerHTML = '<div class="spinner" style="width:24px;height:24px;"></div>';
        listEl.parentElement.querySelector('.scroll-anchor')?.before(loaderEl);

        try {
            const res = await fetch(`${apiMap[type]}?page=${page}&limit=${PAGE_SIZE}`);
            const result = await res.json();
            const items = result.data || [];
            state.total = result.total || 0;

            if (items.length === 0 || (page - 1) * PAGE_SIZE + items.length >= state.total) {
                state.done = true;
            }

            const existingCount = listEl.querySelectorAll('.data-card').length;
            const html = items.map((item, i) => renderCard(item, existingCount + i, cardTypeMap[type])).join('');
            listEl.insertAdjacentHTML('beforeend', html);

            state.page = page + 1;
        } catch (err) {
            console.error(`載入 ${type} 第 ${page} 頁失敗:`, err);
        } finally {
            loaderEl.remove();
            state.loading = false;
        }
    }

    async function loadCachedData() {
        // Reset pagination
        for (const key of Object.keys(paginationState)) {
            paginationState[key] = { page: 1, total: 0, loading: false, done: false };
        }
        scienceList.innerHTML = '';
        socialList.innerHTML = '';
        newsList.innerHTML = '';

        // Load first page for each
        await Promise.all([
            loadPage('science', 1),
            loadPage('social', 1),
            loadPage('news', 1),
        ]);

        // Load keywords
        loadKeywords();

        // Reset selection state
        selectedState.science = null;
        selectedState.spice = null;
        updateSelectionBar('science', null);
        updateSelectionBar('spice', null);
        updateGenerateBtn();
    }

    async function loadKeywords() {
        try {
            const res = await fetch('/api/data/trends');
            const data = await res.json();
            // Extract unique keywords from all trends
            const allKeywords = new Set();
            (data.data || []).forEach(item => {
                (item.keywords || []).forEach(k => allKeywords.add(k));
            });
            if (allKeywords.size > 0) {
                keywordsBadge.innerHTML = [...allKeywords].slice(0, 10)
                    .map(k => `<span class="pill">${k}</span>`).join('');
            }
        } catch (err) {
            console.error('載入關鍵字失敗:', err);
        }
    }

    // ─── Generation ───

    function showLoader(text) {
        resultEmpty.classList.add('hidden');
        resultContent.classList.add('hidden');
        errorBox.classList.add('hidden');
        resultLoader.classList.remove('hidden');
        loaderText.textContent = text || 'Multi-Agent Debate 進行中...';
    }

    function hideLoader() {
        resultLoader.classList.add('hidden');
    }

    function showError(message) {
        hideLoader();
        resultEmpty.classList.add('hidden');
        resultContent.classList.add('hidden');
        errorMessage.textContent = message;
        errorBox.classList.remove('hidden');
    }

    async function doGenerate() {
        if (!selectedState.science) return;

        showLoader('Multi-Agent Debate 進行中...');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 引擎運轉中...';

        const loaderSteps = [
            "載入選定卡片配對要求...",
            "Proposer Phase 1: 提煉科普核心...",
            "分析機制延伸潛力...",
            "ChromaDB 向量配對中...",
            "Proposer Phase 2: 三角度 Hook 生成...",
            "生成【時事生活 / 動漫機制 / 懸疑對比】文案...",
            "Critic Agent 嚴格審查中...",
            "執行代換測試 (Substitution Test)...",
            "Multi-Agent Debate 進行中...",
        ];

        let stepCount = 0;
        const loaderInterval = setInterval(() => {
            stepCount = (stepCount + 1) % loaderSteps.length;
            loaderText.textContent = loaderSteps[stepCount];
        }, 3000);

        try {
            const payload = {
                locked_items: {
                    science_url: selectedState.science?.id || null,
                    social_url: selectedState.spice?.type === 'social' ? selectedState.spice.id : null,
                    trend_url: selectedState.spice?.type === 'trend' ? selectedState.spice.id : null,
                }
            };

            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            clearInterval(loaderInterval);

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || '伺服器錯誤');
            }

            const data = await res.json();

            if (data.status === 'error') {
                showError(data.message);
                return;
            }

            currentData = data;
            renderResult(data);

        } catch (err) {
            clearInterval(loaderInterval);
            showError(err.message);
        } finally {
            generateBtn.disabled = !selectedState.science;
            generateBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 啟動生成';
        }
    }

    function renderResult(data) {
        hideLoader();
        resultEmpty.classList.add('hidden');
        errorBox.classList.add('hidden');
        resultContent.classList.remove('hidden');

        // Science Core
        scienceCoreText.textContent = data.science_core || '';
        mechanismText.textContent = data.mechanism || '';

        // Hook Tabs
        const hooks = data.hooks || [data.hook_humor || '', data.hook_anime || '', data.hook_mystery || ''];
        document.getElementById('hookTab0').innerHTML = (hooks[0] || '').replace(/\n/g, '<br>');
        document.getElementById('hookTab1').innerHTML = (hooks[1] || '').replace(/\n/g, '<br>');
        document.getElementById('hookTab2').innerHTML = (hooks[2] || '').replace(/\n/g, '<br>');

        // Reset hook tabs to first
        document.querySelectorAll('.hook-tab-btn').forEach((b, i) => {
            b.classList.toggle('hook-tab-btn--active', i === 0);
        });
        document.querySelectorAll('.hook-quote').forEach((q, i) => {
            q.classList.toggle('hidden', i !== 0);
        });

        // Critic Score
        const score = data.critic_score || 0;
        criticScoreInline.textContent = `${score}/10`;
        const scoreColor = getScoreColor(score);
        criticScoreInline.style.color = scoreColor;
        criticScoreInline.style.borderColor = scoreColor + '50';
        criticScoreInline.style.background = scoreColor + '20';

        // Critic Comment
        criticComment.textContent = data.critic_comment || '';

        // Critic Breakdown
        renderCriticBreakdown(data.critic_breakdown);

        // Reasoning
        reasoningText.textContent = data.reasoning || '';

        // Source articles
        renderSourceArticles(data);
    }

    function renderCriticBreakdown(breakdown) {
        if (!breakdown || Object.keys(breakdown).length === 0) {
            criticBreakdown.innerHTML = '';
            return;
        }
        const labels = {
            science_first_score: '科學先決 (Substitution Test)',
            hook_appeal_score: 'Hook 吸引力 (幽默/迷因/懸疑)',
            format_score: '正確性 (3 組 Hook 完整度)',
            // 舊版備用
            science_core_completeness: '科普核心完整度',
            mechanism_clarity: '機制說明清晰度',
            social_integration: '時事整合自然度',
            anti_common_sense: '反常識衝擊力',
            taiwan_resonance: '台灣受眾共鳴',
        };

        criticBreakdown.innerHTML = Object.entries(breakdown)
            .map(([key, val]) => {
                const label = labels[key] || key;
                // 優先判定 Science 為 4 分，其餘設為 3 分
                let maxScore = 3;
                const lowerKey = key.toLowerCase();
                if (lowerKey.includes('science') || lowerKey.includes('first')) {
                    maxScore = 4;
                }

                const normalizedScore = (val / maxScore) * 10;
                const color = getScoreColor(normalizedScore);
                return `<div class="breakdown-item">
                            <span class="breakdown-label">${label}</span>
                            <span class="breakdown-score" style="color:${color}">${val}/${maxScore}</span>
                        </div>`;
            })
            .join('');
    }

    function renderSourceArticles(data) {
        const items = [];
        const trend = data.matched_trend || data.source_trend;
        const science = data.matched_science || data.source_science;
        const social = data.matched_social;

        if (trend && trend.title) {
            items.push(`
                <div class="source-item">
                    <span class="source-tag trend-tag"><i class="fa-solid fa-fire"></i> 時事</span>
                    <a href="${trend.url || '#'}" target="_blank">${trend.title}</a>
                </div>`);
        }
        if (science && science.title) {
            items.push(`
                <div class="source-item">
                    <span class="source-tag science-tag"><i class="fa-solid fa-microscope"></i> 科學</span>
                    <a href="${science.url || '#'}" target="_blank">${science.title}</a>
                </div>`);
        }
        if (social && social.title) {
            items.push(`
                <div class="source-item">
                    <span class="source-tag" style="background:rgba(168,85,247,0.2);color:#c084fc;border:1px solid rgba(168,85,247,0.3)"><i class="fa-solid fa-fire"></i> 社群</span>
                    <a href="${social.url || '#'}" target="_blank">${social.title}</a>
                </div>`);
        }

        sourceArticles.innerHTML = items.length > 0 ? items.join('') : '';
        sourceArticles.style.display = items.length > 0 ? '' : 'none';
    }

    // ─── Surprise Me ───

    async function doSurprise() {
        showLoader('隨機碰撞靈感中...');
        generateBtn.disabled = true;

        try {
            const res = await fetch('/api/surprise', { method: 'POST' });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || '隨機生成失敗');
            }
            const data = await res.json();

            if (data.status === 'error') {
                showError(data.message);
                return;
            }

            // Clear existing selections
            deselectCard('science');
            deselectCard('spice');

            currentData = data;
            renderResult(data);

        } catch (err) {
            showError(err.message);
        } finally {
            generateBtn.disabled = !selectedState.science;
        }
    }

    // ─── Copy Hook ───

    function copyCurrentHook() {
        const activeQuote = document.querySelector('.hook-quote:not(.hidden)');
        if (activeQuote && activeQuote.textContent.trim()) {
            navigator.clipboard.writeText(activeQuote.textContent.trim()).then(() => {
                const btn = copyHookBtn;
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-check"></i> 已複製！';
                setTimeout(() => { btn.innerHTML = original; }, 1500);
            });
        }
    }

    // ─── Save ───

    async function doSave() {
        if (!currentData) return;

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 儲存中...';

        try {
            const hooks = currentData.hooks || [];
            const payload = {
                science_core: currentData.science_core || '',
                mechanism: currentData.mechanism || '',
                hooks_json: JSON.stringify(hooks),
                critic_score: currentData.critic_score || 0,
                critic_breakdown_json: currentData.critic_breakdown ? JSON.stringify(currentData.critic_breakdown) : '{}',
                matched_trend_url: currentData.matched_trend?.url || '',
                matched_science_url: currentData.matched_science?.url || '',
            };

            const res = await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const result = await res.json();
            if (res.ok) {
                saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> 已儲存';
                setTimeout(() => {
                    saveBtn.innerHTML = '<i class="fa-solid fa-save"></i> 儲存 CSV';
                }, 2000);
            } else {
                throw new Error(result.detail || '儲存失敗');
            }
        } catch (err) {
            alert('儲存失敗: ' + err.message);
        } finally {
            saveBtn.disabled = false;
        }
    }

    // ─── History Drawer ───

    async function loadHistory() {
        historyList.innerHTML = '<div class="loader-container" style="height:100px;"><div class="spinner" style="width:30px;height:30px;"></div></div>';
        try {
            const resp = await fetch('/api/history');
            const data = await resp.json();

            if (!data.history || data.history.length === 0) {
                historyList.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">無歷史紀錄</p>';
                return;
            }

            historyList.innerHTML = data.history.map(item => `
                <div class="history-item">
                    <div class="history-item-date">${new Date(item.created_at).toLocaleString()}</div>
                    <div class="history-item-mechanisms">
                        <span class="mechanism-tag science-mechanism"><i class="fa-solid fa-atom"></i> ${item.mechanism || '—'}</span>
                    </div>
                    <div class="history-item-hook">${item.science_core || '舊版紀錄'}</div>
                    <div style="font-size:0.75rem;color:#4ade80;margin-top:0.4rem;">
                        <i class="fa-solid fa-check"></i> Critic Score: ${item.critic_score || '—'}/10
                    </div>
                </div>
            `).join('');
        } catch (err) {
            historyList.innerHTML = `<p style="color:#ef4444;text-align:center;padding:2rem;">載入失敗: ${err.message}</p>`;
        }
    }

    // ─── Event Bindings ───

    generateBtn.addEventListener('click', doGenerate);
    surpriseBtn.addEventListener('click', doSurprise);
    retryBtn.addEventListener('click', doGenerate);
    retryFromError.addEventListener('click', () => {
        errorBox.classList.add('hidden');
        doGenerate();
    });
    saveBtn.addEventListener('click', doSave);
    if (copyHookBtn) copyHookBtn.addEventListener('click', copyCurrentHook);
    if (generateScriptBtn) generateScriptBtn.addEventListener('click', doGenerateScript);
    
    if (closeScriptModalBtn) {
        closeScriptModalBtn.addEventListener('click', () => scriptModal.classList.add('hidden'));
    }
    if (exportWordBtn) exportWordBtn.addEventListener('click', doExportWord);

    let generatedMarkdownCache = "";

    async function doGenerateScript() {
        if (!selectedState.science) {
            alert("請先選擇一筆科學文獻！");
            return;
        }

        const activeQuote = document.querySelector('.hook-quote:not(.hidden)');
        const hookText = activeQuote ? activeQuote.textContent.trim() : '';
        if (!hookText) {
            alert("目前沒有可以使用的 Hook，請先生成！");
            return;
        }

        showLoader('正在抓取全文與融合比喻 (這需要約 30 秒，請耐心等候)...');

        try {
            const payload = {
                science_url: selectedState.science.id,
                social_url: selectedState.spice && selectedState.spice.type === 'social' ? selectedState.spice.id : null,
                hook_text: hookText
            };

            const res = await fetch('/api/build_script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || '腳本生成失敗');
            }

            const data = await res.json();
            
            generatedMarkdownCache = data.script;

            if (typeof marked !== 'undefined') {
                scriptContentArea.innerHTML = marked.parse(generatedMarkdownCache);
            } else {
                scriptContentArea.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${generatedMarkdownCache}</pre>`;
            }

            resultContent.classList.remove('hidden');
            scriptModal.classList.remove('hidden');

        } catch (err) {
            showError("腳本生成發生錯誤：" + err.message);
        } finally {
            hideLoader();
        }
    }

    async function doExportWord() {
        if (!generatedMarkdownCache) return;

        exportWordBtn.disabled = true;
        exportWordBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 處理中...';

        try {
            const res = await fetch('/api/export_docx', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ markdown_text: generatedMarkdownCache })
            });

            if (!res.ok) throw new Error("匯出 Word 失敗");

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "Pansci_Script_Generated.docx";
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (err) {
            alert(err.message);
        } finally {
            exportWordBtn.disabled = false;
            exportWordBtn.innerHTML = '<i class="fa-solid fa-file-word"></i> 匯出至 Word (.docx)';
        }
    }

    // History drawer
    if (historyBtn) {
        historyBtn.addEventListener('click', () => {
            historyDrawer.classList.add('open');
            historyDrawer.classList.remove('hidden');
            loadHistory();
        });
    }
    if (closeHistoryBtn) {
        closeHistoryBtn.addEventListener('click', () => {
            historyDrawer.classList.remove('open');
        });
    }

    // ─── Slot click-to-deselect ───

    function initSlotClicks() {
        const slotScience = document.getElementById('slotScience');
        const slotSpice = document.getElementById('slotSpice');

        if (slotScience) {
            slotScience.addEventListener('click', (e) => {
                // Only deselect if currently filled
                if (selectedState.science && !e.target.closest('.sel-slot__clear')) {
                    clearSlot('science');
                }
            });
        }
        if (slotSpice) {
            slotSpice.addEventListener('click', (e) => {
                if (selectedState.spice && !e.target.closest('.sel-slot__clear')) {
                    clearSlot('spice');
                }
            });
        }
    }

    /* ═══════════════════════════════════════════
   圖片放大燈箱 (Lightbox) 邏輯
   ═══════════════════════════════════════════ */

    // 1. 使用事件委派監聽全域點擊 (確保未來 AI 動態生成的卡片圖片也能點)
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('card-thumbnail')) {
            // ⚡ 關鍵：阻止事件冒泡，避免觸發卡片的 selectCard()
            e.stopPropagation();
            openImageModal(e.target.src);
        }
    });

    // 2. 開啟燈箱
    function openImageModal(src) {
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        modalImg.src = src;
        modal.classList.remove('hidden');
    }

    // 3. 關閉燈箱
    function closeImageModal() {
        const modal = document.getElementById('imageModal');
        modal.classList.add('hidden');
        // 稍微延遲清空圖片來源，避免關閉動畫卡頓
        setTimeout(() => {
            document.getElementById('modalImage').src = '';
        }, 300);
    }

    // 4. 點擊燈箱「背景」也能自動關閉
    document.getElementById('imageModal')?.addEventListener('click', function (e) {
        // 確保點擊的是背景，而不是圖片本身
        if (e.target === this) {
            closeImageModal();
        }
    });

    // ─── Infinite Scroll (Intersection Observer) ───

    function initInfiniteScroll() {
        const observerOptions = { root: null, rootMargin: '200px', threshold: 0 };

        const anchors = {
            science: document.getElementById('scienceAnchor'),
            social:  document.getElementById('socialAnchor'),
            news:    document.getElementById('newsAnchor'),
        };

        for (const [type, anchor] of Object.entries(anchors)) {
            if (!anchor) continue;
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const state = paginationState[type];
                        if (!state.loading && !state.done) {
                            loadPage(type, state.page);
                        }
                    }
                });
            }, observerOptions);
            observer.observe(anchor);
        }
    }

    // ─── Sync Button ───

    const syncBtn = document.getElementById('syncBtn');
    if (syncBtn) {
        syncBtn.addEventListener('click', async () => {
            const overlay = document.getElementById('syncOverlay');
            const statusText = document.getElementById('syncStatusText');
            const progressFill = document.getElementById('syncProgressFill');

            overlay.classList.remove('hidden');
            syncBtn.disabled = true;
            syncBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 同步中...';

            const steps = [
                { api: '/api/crawl/trends',  label: '正在爬取新聞資料...', pct: '33%' },
                { api: '/api/crawl/social',   label: '正在爬取社群資料...', pct: '66%' },
                { api: '/api/crawl/science',  label: '正在爬取科學文獻...', pct: '90%' },
            ];

            try {
                for (const step of steps) {
                    statusText.textContent = step.label;
                    progressFill.style.width = step.pct;
                    await fetch(step.api, { method: 'POST' });
                }
                statusText.textContent = '同步完成！正在重新載入畫面...';
                progressFill.style.width = '100%';
                await loadCachedData();
            } catch (err) {
                statusText.textContent = `同步失敗：${err.message}`;
            } finally {
                setTimeout(() => {
                    overlay.classList.add('hidden');
                    progressFill.style.width = '0%';
                    syncBtn.disabled = false;
                    syncBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> 同步資料';
                }, 800);
            }
        });
    }

    // ─── DB Viewer Modal ───

    const dbBtn = document.getElementById('dbBtn');
    const dbModal = document.getElementById('dbModal');
    let dbDataCache = { science: [], social: [], trends: [] };

    window.closeDbModal = function () {
        dbModal.classList.add('hidden');
    };

    if (dbBtn) {
        dbBtn.addEventListener('click', async () => {
            dbModal.classList.remove('hidden');
            await loadDbData();
        });
    }

    // DB Tab switching
    document.querySelectorAll('.db-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.db-tab-btn').forEach(b => b.classList.remove('db-tab-btn--active'));
            btn.classList.add('db-tab-btn--active');
            const target = btn.dataset.dbtab;
            document.querySelectorAll('.db-panel').forEach(p => p.classList.add('hidden'));
            const panelMap = {
                'db-science': 'dbPanelScience',
                'db-social':  'dbPanelSocial',
                'db-trends':  'dbPanelTrends',
            };
            document.getElementById(panelMap[target])?.classList.remove('hidden');
        });
    });

    async function loadDbData() {
        try {
            const [sciRes, socRes, trnRes] = await Promise.all([
                fetch('/api/data/science?page=1&limit=500').then(r => r.json()),
                fetch('/api/data/social?page=1&limit=500').then(r => r.json()),
                fetch('/api/data/trends?page=1&limit=500').then(r => r.json()),
            ]);

            dbDataCache.science = sciRes.data || [];
            dbDataCache.social = socRes.data || [];
            dbDataCache.trends = trnRes.data || [];

            document.getElementById('dbCountScience').textContent = sciRes.total || dbDataCache.science.length;
            document.getElementById('dbCountSocial').textContent = socRes.total || dbDataCache.social.length;
            document.getElementById('dbCountTrends').textContent = trnRes.total || dbDataCache.trends.length;

            renderDbTable('science', dbDataCache.science);
            renderDbTable('social', dbDataCache.social);
            renderDbTable('trends', dbDataCache.trends);
        } catch (err) {
            console.error('DB Viewer 載入失敗:', err);
        }
    }

    function renderDbTable(type, items) {
        const bodyMap = {
            science: 'dbBodyScience',
            social:  'dbBodySocial',
            trends:  'dbBodyTrends',
        };
        const tbody = document.getElementById(bodyMap[type]);
        if (!tbody) return;

        tbody.innerHTML = items.map((item, i) => {
            const title = item.title || '無標題';
            const source = item.source || item.pipeline || '—';
            const col3 = type === 'social' ? (item.category || '—') : (item.mechanism || '—');
            const time = item.created_at ? new Date(item.created_at).toLocaleDateString('zh-TW') : '—';
            const link = item.url
                ? `<a href="${item.url}" target="_blank" class="db-link"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>`
                : '—';
            return `<tr>
                <td>${i + 1}</td>
                <td class="db-cell-title" title="${title}">${title}</td>
                <td>${source}</td>
                <td>${col3}</td>
                <td>${time}</td>
                <td>${link}</td>
            </tr>`;
        }).join('');
    }

    // DB Search filter
    const dbSearchInput = document.getElementById('dbSearchInput');
    if (dbSearchInput) {
        dbSearchInput.addEventListener('input', () => {
            const q = dbSearchInput.value.trim().toLowerCase();
            for (const type of ['science', 'social', 'trends']) {
                const filtered = q
                    ? dbDataCache[type].filter(item => (item.title || '').toLowerCase().includes(q))
                    : dbDataCache[type];
                renderDbTable(type, filtered);
            }
        });
    }

    // ─── Init ───

    initTabs();
    initHookTabs();
    initSlotClicks();
    initInfiniteScroll();
    loadCachedData();

});
