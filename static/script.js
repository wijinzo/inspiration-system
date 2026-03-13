document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('generateBtn');
    const retryBtn = document.getElementById('retryBtn');
    const retryFromError = document.getElementById('retryFromError');
    const saveBtn = document.getElementById('saveBtn');

    const dashboard = document.getElementById('dashboard');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loaderText');
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');

    const trendList = document.getElementById('trendList');
    const socialList = document.getElementById('socialList');
    const scienceList = document.getElementById('scienceList');
    const surpriseBtn = document.getElementById('surpriseBtn');

    const hookText = document.getElementById('hookText');
    const reasoningText = document.getElementById('reasoningText');
    const saveStatus = document.getElementById('saveStatus');
    const criticBadge = document.getElementById('criticBadge');
    const criticComment = document.getElementById('criticComment');
    const criticBreakdown = document.getElementById('criticBreakdown');
    const qualityWarning = document.getElementById('qualityWarning');
    const keywordsBadge = document.getElementById('keywordsBadge');

    let currentData = null;

    // ─── 卡片渲染 ───

    function createTrendCard(item, index) {
        const mechanism = item.mechanism
            ? `<div class="mechanism-tag trend-mechanism"><i class="fa-solid fa-gears"></i> ${item.mechanism}</div>`
            : '';
        const keywords = item.keywords && item.keywords.length > 0
            ? `<div class="keyword-pills">${item.keywords.map(k => `<span class="pill">${k}</span>`).join('')}</div>`
            : '';
        const heatBadge = item.heat_score > 0
            ? `<span class="heat-badge"><i class="fa-solid fa-fire"></i> ${item.heat_score}</span>`
            : '';

        return `
            <div class="data-card fade-in" style="animation-delay: ${index * 0.1}s">
                <div class="card-header">
                    <h3>${index + 1}. ${item.title}</h3>
                    ${heatBadge}
                </div>
                <p>${item.summary || ''}</p>
                ${mechanism}
                ${keywords}
                ${item.url ? `<a href="${item.url}" target="_blank" class="source-link trend-link">查看來源 <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ''}
            </div>
        `;
    }

    function createSocialCard(item, index) {
        const mechanism = item.mechanism
            ? `<div class="mechanism-tag social-mechanism"><i class="fa-solid fa-sparkles"></i> ${item.mechanism}</div>`
            : '';
        const keywords = item.matched_keywords && item.matched_keywords.length > 0
            ? `<div class="keyword-pills">${item.matched_keywords.map(k => `<span class="pill">${k}</span>`).join('')}</div>`
            : '';
        
        let sourceIcon = 'fa-comment';
        if(item.source.includes('YouTube')) sourceIcon = 'fa-youtube';
        if(item.source.includes('Dcard')) sourceIcon = 'fa-d';

        return `
            <div class="data-card fade-in" style="animation-delay: ${index * 0.1}s">
                <div class="card-header">
                    <h3>${index + 1}. ${item.title}</h3>
                    <span class="pipeline-badge" style="background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.3)"><i class="fa-brands ${sourceIcon}"></i> ${item.source}</span>
                </div>
                <p>${item.summary || ''}</p>
                ${mechanism}
                ${keywords}
                ${item.url ? `<a href="${item.url}" target="_blank" class="source-link trend-link" style="color:#ef4444">查看來源 <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ''}
            </div>
        `;
    }

    function createScienceCard(item, index) {
        const mechanism = item.mechanism
            ? `<div class="mechanism-tag science-mechanism"><i class="fa-solid fa-atom"></i> ${item.mechanism}</div>`
            : '';
        const pipelineBadge = item.pipeline === 'RSS'
            ? '<span class="pipeline-badge rss-badge">RSS</span>'
            : '<span class="pipeline-badge brave-badge">Brave</span>';

        return `
            <div class="data-card fade-in" style="animation-delay: ${index * 0.1}s">
                <div class="card-header">
                    <h3>${index + 1}. ${item.title}</h3>
                    ${pipelineBadge}
                </div>
                <p>${item.summary || ''}</p>
                ${mechanism}
                ${item.url ? `<a href="${item.url}" target="_blank" class="source-link science-link">查看來源 <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ''}
            </div>
        `;
    }

    function getScoreColor(score) {
        if (score >= 8) return '#4ade80';
        if (score >= 6) return '#fbbf24';
        return '#ef4444';
    }

    function renderCriticBadge(score) {
        const color = getScoreColor(score);
        criticBadge.innerHTML = `<span style="background:${color}20;color:${color};border:1px solid ${color}50;padding:0.3rem 0.8rem;border-radius:2rem;font-weight:700;font-size:1rem;">${score}/10</span>`;
    }

    function renderBreakdown(breakdown) {
        if (!breakdown || Object.keys(breakdown).length === 0) {
            criticBreakdown.innerHTML = '';
            return;
        }
        const labels = {
            relevance: '關聯性',
            logic: '邏輯連貫',
            accuracy: '科學正確性',
            appeal: '吸引力',
        };
        criticBreakdown.innerHTML = Object.entries(breakdown)
            .map(([key, val]) => {
                const label = labels[key] || key;
                const color = getScoreColor(val * 4);
                return `<div class="breakdown-item"><span class="breakdown-label">${label}</span><span class="breakdown-score" style="color:${color}">${val}/2.5</span></div>`;
            })
            .join('');
    }

    // ─── 生成主流程 ───

    async function runGeneration() {
        saveStatus.textContent = '';
        dashboard.classList.add('hidden');
        errorBox.classList.add('hidden');
        loader.classList.remove('hidden');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 引擎運轉中...';

        const loaderSteps = [
            "透過 Google Trends 分析台灣熱門話題...",
            "抓取 LTN / PTS 即時新聞 RSS...",
            "交叉比對關鍵字與新聞...",
            "LLM 過濾政治八卦 + 提取底層機制...",
            "檢索國際科學 RSS feeds...",
            "Brave Search 動態擴充科學文獻...",
            "ChromaDB 向量配對中...",
            "Proposer Agent 生成 Hook...",
            "Critic Agent 嚴格審查中...",
            "Multi-Agent Debate 進行中...",
        ];

        let stepCount = 0;
        const loaderInterval = setInterval(() => {
            stepCount = (stepCount + 1) % loaderSteps.length;
            loaderText.textContent = loaderSteps[stepCount];
        }, 3000);

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });

            const data = await response.json();
            clearInterval(loaderInterval);

            if (!response.ok) {
                throw new Error(data.detail || "伺服器錯誤");
            }

            if (data.status === "error") {
                showError(data.message);
                return;
            }

            currentData = data;

            // 渲染趨勢
            trendList.innerHTML = (data.trends || []).map((t, i) => createTrendCard(t, i)).join('');

            // 渲染社群時事
            if (data.social_trends && data.social_trends.length > 0) {
                socialList.innerHTML = data.social_trends.slice(0, 10).map((s, i) => createSocialCard(s, i)).join('');
            } else {
                socialList.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem;text-align:center;margin-top:2rem;">(目前無精準社群話題)</p>';
            }

            // 渲染科學
            scienceList.innerHTML = (data.science || []).slice(0, 10).map((s, i) => createScienceCard(s, i)).join('');

            // Hook
            hookText.innerHTML = (data.hook || '').replace(/\n/g, '<br>');
            reasoningText.textContent = data.reasoning || '';

            // Critic
            renderCriticBadge(data.critic_score || 0);
            criticComment.textContent = data.critic_comment || '';
            renderBreakdown(data.critic_breakdown);

            // Quality Warning
            if (data.quality_warning) {
                qualityWarning.textContent = data.quality_warning;
                qualityWarning.classList.remove('hidden');
            } else {
                qualityWarning.classList.add('hidden');
            }

            // Source Articles
            const sourceBox = document.getElementById('sourceArticles');
            if (sourceBox && data.matched_trend && data.matched_science) {
                sourceBox.innerHTML = `
                    <div class="source-item">
                        <span class="source-tag trend-tag"><i class="fa-solid fa-fire"></i> 時事來源</span>
                        <a href="${data.matched_trend.url || '#'}" target="_blank">${data.matched_trend.title || ''}</a>
                    </div>
                    <div class="source-item">
                        <span class="source-tag science-tag"><i class="fa-solid fa-microscope"></i> 科學來源</span>
                        <a href="${data.matched_science.url || '#'}" target="_blank">${data.matched_science.title || ''}</a>
                    </div>
                `;
            }

            // Google Trends Keywords
            if (data.google_trends_keywords && data.google_trends_keywords.length > 0) {
                keywordsBadge.innerHTML = `<i class="fa-solid fa-chart-line"></i> 今日熱門：${data.google_trends_keywords.slice(0, 5).map(k => `<span class="pill">${k}</span>`).join('')}`;
                keywordsBadge.classList.remove('hidden');
            }

            loader.classList.add('hidden');
            dashboard.classList.remove('hidden');

        } catch (error) {
            clearInterval(loaderInterval);
            loader.classList.add('hidden');
            showError(error.message);
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 啟動配對引擎';
        }
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorBox.classList.remove('hidden');
        loader.classList.add('hidden');
    }

    // ─── 事件綁定 ───

    generateBtn.addEventListener('click', runGeneration);
    
    if(surpriseBtn) {
        surpriseBtn.addEventListener('click', () => {
            surpriseBtn.classList.add('pulse-icon');
            setTimeout(() => surpriseBtn.classList.remove('pulse-icon'), 1500);
            runGeneration();
        });
    }

    retryBtn.addEventListener('click', runGeneration);
    retryFromError.addEventListener('click', () => {
        errorBox.classList.add('hidden');
        runGeneration();
    });

    saveBtn.addEventListener('click', async () => {
        if (!currentData || !currentData.hook) {
            saveStatus.style.color = "#ef4444";
            saveStatus.textContent = "沒有可以儲存的資料！";
            return;
        }

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 儲存中...';

        try {
            const payload = {
                trend_data: JSON.stringify(currentData.trends || []),
                science_data: JSON.stringify(currentData.science || []),
                generated_hook: currentData.hook + "\n\nReasoning: " + (currentData.reasoning || '') + "\n\nCritic Score: " + (currentData.critic_score || 0) + "/10",
            };

            const response = await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const result = await response.json();

            if (response.ok) {
                saveStatus.style.color = "#4ade80";
                saveStatus.textContent = result.message;
            } else {
                throw new Error(result.detail || "儲存失敗");
            }
        } catch (error) {
            saveStatus.style.color = "#ef4444";
            saveStatus.textContent = error.message;
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-save"></i> 儲存此靈感 (CSV)';
        }
    });
});
