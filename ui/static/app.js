// ==========================================================================
// AutoGZH Enterprise SaaS UI - Ant Design / Element Plus 交互控制引擎
// ==========================================================================

// 全局响应式状态
const state = {
    // 视图导航: 'library' (文章管理与排期) | 'workspace' (极速排版与创作)
    activeView: "library",
    
    // 数据模型
    articles: [],
    filteredArticles: [],
    stats: { total: 0, draft: 0, scheduled: 0, synced: 0 },
    
    // 表格多选集合 (存储选中的 relative_path)
    selectedPaths: new Set(),
    
    // 分页系统
    pagination: {
        page: 1,
        pageSize: 10,
        totalPages: 1
    },
    
    // 内联表单筛选状态
    filters: {
        search: "",
        status: "all",
        style: "all"
    },
    
    // 工作台状态
    activeFileTab: "workspace",
    activeCoverTab: "workspace"
};

const STYLE_NAME_MAP = {
    "story": "硬核实战橙",
    "tech": "深邃科技蓝",
    "default": "优雅茶青",
    "minimal": "极简冷灰",
    "warm": "暖意秋橙"
};

// 页面加载就绪后初始化
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

function initApp() {
    loadConfig();
    loadThemes();
    loadWorkspaceFiles();
    loadArticlesCatalog();
    setupEventListeners();
}

// ==========================================================================
// 1. 数据加载与同步
// ==========================================================================

// 加载可用排版主题
async function loadThemes() {
    try {
        const response = await fetch("/api/themes");
        if (!response.ok) return;
        const themes = await response.json();
        
        // 工作台下拉框
        const wsSelect = document.getElementById("theme-style");
        if (wsSelect && Array.isArray(themes)) {
            wsSelect.innerHTML = "";
            themes.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = t.name;
                wsSelect.appendChild(opt);
            });
        }
        
        // 顶部筛选主题下拉框
        const filterSelect = document.getElementById("filter-style");
        if (filterSelect && Array.isArray(themes)) {
            filterSelect.innerHTML = '<option value="all">全部风格</option>';
            themes.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = STYLE_NAME_MAP[t.id] || t.name;
                filterSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn("加载主题失败:", e);
    }
}

// 加载微信配置
async function loadConfig() {
    try {
        const response = await fetch("/api/config");
        if (!response.ok) throw new Error("获取配置失败");
        const data = await response.json();
        
        document.getElementById("appid").value = data.appid || "";
        document.getElementById("secret").value = data.secret || "";
        document.getElementById("author").value = data.author || "";
        document.getElementById("show_cover_pic").checked = data.show_cover_pic === 1;
        document.getElementById("need_open_comment").checked = data.need_open_comment === 1;
        document.getElementById("only_less_tags").checked = data.only_less_tags === 1;
    } catch (error) {
        showToast("加载微信配置失败: " + error.message, "error");
    }
}

// 保存微信配置
async function saveConfig(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById("save-config-btn");
    btn.disabled = true;
    btn.textContent = "保存中...";
    
    const payload = {
        appid: document.getElementById("appid").value.trim(),
        secret: document.getElementById("secret").value.trim(),
        author: document.getElementById("author").value.trim(),
        show_cover_pic: document.getElementById("show_cover_pic").checked ? 1 : 0,
        need_open_comment: document.getElementById("need_open_comment").checked ? 1 : 0,
        only_less_tags: document.getElementById("only_less_tags").checked ? 1 : 0
    };
    
    try {
        const response = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (data.success) {
            showToast("微信配置保存成功！", "success");
            closeConfigModal();
            appendLog("系统配置已更新并写入本地 config.yaml。", "success");
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("保存配置失败: " + error.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "保存配置";
    }
}

// 加载工作区文件
async function loadWorkspaceFiles() {
    try {
        const response = await fetch("/api/files");
        if (!response.ok) throw new Error("获取文件列表失败");
        const data = await response.json();
        
        const mdSelect = document.getElementById("md-file-select");
        if (mdSelect) {
            mdSelect.innerHTML = '<option value="">-- 请选择工作区内的 Markdown 文件 --</option>';
            data.markdown_files.forEach(file => {
                const opt = document.createElement("option");
                opt.value = file;
                opt.textContent = file;
                mdSelect.appendChild(opt);
            });
        }
        
        const coverSelect = document.getElementById("cover-file-select");
        if (coverSelect) {
            coverSelect.innerHTML = '<option value="">-- 请选择封面图片 --</option>';
            data.image_files.forEach(file => {
                const opt = document.createElement("option");
                opt.value = file;
                opt.textContent = file;
                coverSelect.appendChild(opt);
            });
        }
    } catch (error) {
        console.warn("加载工作区文件异常:", error);
    }
}

// 加载文章库完整元数据并驱动表格渲染
async function loadArticlesCatalog() {
    try {
        const response = await fetch("/api/articles");
        if (!response.ok) throw new Error("获取文章库数据失败");
        const data = await response.json();
        
        state.articles = data.articles || [];
        state.stats = data.stats || { total: 0, draft: 0, scheduled: 0, synced: 0 };
        
        // 更新指标条与菜单角标
        document.getElementById("count-all").textContent = state.stats.total;
        document.getElementById("count-draft").textContent = state.stats.draft;
        document.getElementById("count-scheduled").textContent = state.stats.scheduled;
        document.getElementById("count-synced").textContent = state.stats.synced;
        document.getElementById("side-library-badge").textContent = state.stats.total;
        
        // 清理不存在的已选项
        const existingPaths = new Set(state.articles.map(a => a.path));
        state.selectedPaths.forEach(p => {
            if (!existingPaths.has(p)) state.selectedPaths.delete(p);
        });
        
        applyFiltersAndRenderTable();
    } catch (error) {
        showToast("加载文章数据失败: " + error.message, "error");
    }
}

// ==========================================================================
// 2. 筛选、分页与 Ant Data Table 渲染引擎
// ==========================================================================

function handleFilterSearch() {
    const searchVal = document.getElementById("filter-search").value.trim().toLowerCase();
    const statusVal = document.getElementById("filter-status").value;
    const styleVal = document.getElementById("filter-style").value;
    
    state.filters.search = searchVal;
    state.filters.status = statusVal;
    state.filters.style = styleVal;
    
    state.pagination.page = 1; // 检索时重置到第1页
    applyFiltersAndRenderTable();
}

function handleFilterReset() {
    document.getElementById("filter-search").value = "";
    document.getElementById("filter-status").value = "all";
    document.getElementById("filter-style").value = "all";
    
    state.filters = { search: "", status: "all", style: "all" };
    state.pagination.page = 1;
    applyFiltersAndRenderTable();
}

function applyFiltersAndRenderTable() {
    const { search, status, style } = state.filters;
    
    state.filteredArticles = state.articles.filter(item => {
        // 状态筛选
        if (status !== "all" && item.status !== status) {
            return false;
        }
        // 风格筛选
        if (style !== "all" && item.style !== style) {
            return false;
        }
        // 搜索关键词 (标题 / 作者 / 摘要 / 标签)
        if (search) {
            const titleMatch = (item.title || "").toLowerCase().includes(search);
            const authorMatch = (item.author || "").toLowerCase().includes(search);
            const digestMatch = (item.digest || "").toLowerCase().includes(search);
            const tagsMatch = Array.isArray(item.tags) && item.tags.some(t => String(t).toLowerCase().includes(search));
            if (!titleMatch && !authorMatch && !digestMatch && !tagsMatch) {
                return false;
            }
        }
        return true;
    });
    
    renderArticlesTable();
}

function renderArticlesTable() {
    const tbody = document.getElementById("articles-table-body");
    if (!tbody) return;
    
    const total = state.filteredArticles.length;
    const { page, pageSize } = state.pagination;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    state.pagination.totalPages = totalPages;
    
    // 如果当前页超出范围则修正
    if (page > totalPages) {
        state.pagination.page = totalPages;
    }
    
    const startIndex = (state.pagination.page - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, total);
    const currentPageItems = state.filteredArticles.slice(startIndex, endIndex);
    
    // 更新分页器显示
    document.getElementById("pagination-total").textContent = total;
    document.getElementById("page-number-display").textContent = `第 ${state.pagination.page} / ${totalPages} 页`;
    document.getElementById("page-prev-btn").disabled = state.pagination.page <= 1;
    document.getElementById("page-next-btn").disabled = state.pagination.page >= totalPages;
    
    // 空数据展示
    if (currentPageItems.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-slate-400 py-12">
                    <div class="text-2xl mb-1.5">📂</div>
                    <div class="text-xs">暂无符合筛选条件的文章数据</div>
                </td>
            </tr>
        `;
        updateSelectionToolbar();
        return;
    }
    
    let html = "";
    currentPageItems.forEach(item => {
        const isSelected = state.selectedPaths.has(item.path);
        const styleText = STYLE_NAME_MAP[item.style] || item.style || "默认风格";
        const wordCountText = item.word_count ? item.word_count.toLocaleString() : "--";
        
        // 状态徽标与状态文本
        let dotClass = "bg-amber-500";
        let textClass = "text-amber-700";
        let statusLabel = "待审核";
        if (item.status === "synced") {
            dotClass = "bg-emerald-500";
            textClass = "text-emerald-700";
            statusLabel = "已入库草稿";
        } else if (item.status === "scheduled") {
            dotClass = "bg-blue-500";
            textClass = "text-blue-700";
            statusLabel = "已排期";
        }
        
        // 封面缩略图
        const coverImgSrc = item.cover_url || "/api/local-image/assets/cover.png";
        
        html += `
            <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors ${isSelected ? 'bg-blue-50/60' : ''}" data-path="${escapeHtml(item.path)}">
                <td class="w-10 py-2 px-3 text-center">
                    <input type="checkbox" class="rounded-sm border-slate-300 text-blue-600 focus:ring-0 cursor-pointer" ${isSelected ? 'checked' : ''} onchange="handleRowSelect('${escapeHtml(item.path)}', this.checked)">
                </td>
                <td class="w-12 py-2 px-2">
                    <img src="${coverImgSrc}" alt="thumb" class="w-10 h-7 object-cover rounded-sm border border-slate-200" onerror="this.onerror=null;this.src='/ui/static/style.css'">
                </td>
                <td class="py-2 px-3">
                    <div class="font-medium text-slate-900 truncate max-w-xs md:max-w-md" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                    <div class="text-[11px] text-slate-400 truncate max-w-xs md:max-w-md mt-0.5" title="${escapeHtml(item.digest || '')}">${escapeHtml(item.digest || '暂无摘要描述')}</div>
                </td>
                <td class="w-28 py-2 px-3">
                    <span class="inline-block px-1.5 py-0.5 text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200 rounded-sm">${escapeHtml(styleText)}</span>
                </td>
                <td class="w-20 py-2 px-3 text-right font-mono text-slate-600 text-xs">
                    ${wordCountText}
                </td>
                <td class="w-32 py-2 px-3">
                    <input type="date" class="h-6 px-1.5 text-[11px] border border-slate-300 rounded-sm text-slate-700 bg-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" value="${escapeHtml(item.scheduled_date || '')}" onchange="setArticleSchedule('${escapeHtml(item.path)}', this.value)" title="选择发文排期">
                </td>
                <td class="w-24 py-2 px-3">
                    <span class="inline-flex items-center gap-1.5">
                        <span class="w-1.5 h-1.5 rounded-full ${dotClass}"></span>
                        <span class="${textClass} text-xs font-medium">${statusLabel}</span>
                    </span>
                </td>
                <td class="w-40 py-2 px-3 text-center">
                    <div class="flex items-center justify-center gap-1.5 text-xs">
                        <button class="text-blue-600 hover:text-blue-800 hover:underline font-medium" onclick="previewFromCatalog('${escapeHtml(item.path)}')">预览</button>
                        <span class="text-slate-300">|</span>
                        <button class="text-blue-600 hover:text-blue-800 hover:underline font-medium" onclick="promptSchedule('${escapeHtml(item.path)}', '${escapeHtml(item.scheduled_date || '')}')">排期</button>
                        <span class="text-slate-300">|</span>
                        <button class="text-blue-600 hover:text-blue-800 hover:underline font-medium" onclick="syncSingleArticle('${escapeHtml(item.path)}', this)">${item.status === 'synced' ? '重推' : '入库'}</button>
                        <span class="text-slate-300">|</span>
                        <button class="text-red-500 hover:text-red-700 hover:underline font-medium" onclick="deleteArticle('${escapeHtml(item.path)}')">删除</button>
                    </div>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    updateSelectionToolbar();
}

// 分页翻页
function changePage(delta) {
    const newPage = state.pagination.page + delta;
    if (newPage >= 1 && newPage <= state.pagination.totalPages) {
        state.pagination.page = newPage;
        renderArticlesTable();
    }
}

// 切换每页容量
function changePageSize(size) {
    state.pagination.pageSize = parseInt(size, 10) || 10;
    state.pagination.page = 1;
    renderArticlesTable();
}

// ==========================================================================
// 3. 表格勾选与批量操作 (Batch Operations)
// ==========================================================================

function handleRowSelect(path, checked) {
    if (checked) {
        state.selectedPaths.add(path);
    } else {
        state.selectedPaths.delete(path);
    }
    updateSelectionToolbar();
    
    // 更新当前行背景
    const row = document.querySelector(`tr[data-path="${path}"]`);
    if (row) {
        if (checked) {
            row.classList.add("bg-blue-50/60");
        } else {
            row.classList.remove("bg-blue-50/60");
        }
    }
}

function handleSelectAllChange(checked) {
    const { page, pageSize } = state.pagination;
    const startIndex = (page - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, state.filteredArticles.length);
    const currentPageItems = state.filteredArticles.slice(startIndex, endIndex);
    
    currentPageItems.forEach(item => {
        if (checked) {
            state.selectedPaths.add(item.path);
        } else {
            state.selectedPaths.delete(item.path);
        }
    });
    
    renderArticlesTable();
}

function updateSelectionToolbar() {
    const count = state.selectedPaths.size;
    document.getElementById("selected-count").textContent = count;
    
    const btnSync = document.getElementById("btn-batch-sync");
    const btnSchedule = document.getElementById("btn-batch-schedule");
    const btnDelete = document.getElementById("btn-batch-delete");
    
    const disabled = count === 0;
    btnSync.disabled = disabled;
    btnSchedule.disabled = disabled;
    btnDelete.disabled = disabled;
    
    // 全选复选框状态判定
    const selectAllBox = document.getElementById("select-all-checkbox");
    if (!selectAllBox) return;
    
    const { page, pageSize } = state.pagination;
    const startIndex = (page - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, state.filteredArticles.length);
    const currentPageItems = state.filteredArticles.slice(startIndex, endIndex);
    
    if (currentPageItems.length === 0) {
        selectAllBox.checked = false;
        selectAllBox.indeterminate = false;
    } else {
        const selectedOnPage = currentPageItems.filter(item => state.selectedPaths.has(item.path)).length;
        selectAllBox.checked = selectedOnPage === currentPageItems.length;
        selectAllBox.indeterminate = selectedOnPage > 0 && selectedOnPage < currentPageItems.length;
    }
}

// 批量入库微信
async function handleBatchSync() {
    const paths = Array.from(state.selectedPaths);
    if (paths.length === 0) return;
    
    const btn = document.getElementById("btn-batch-sync");
    btn.disabled = true;
    btn.textContent = `⏳ 正在推送 (${paths.length})...`;
    
    showToast(`正在批量入库 ${paths.length} 篇文章至微信草稿箱...`, "info");
    
    try {
        const response = await fetch("/api/articles/batch-sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paths: paths })
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(`批量入库成功: 成功 ${data.success_count} 篇，失败 ${data.fail_count} 篇`, data.fail_count === 0 ? "success" : "warning");
            appendLog(`批量同步微信草稿完成: 成功 ${data.success_count} / 失败 ${data.fail_count}`, "success");
            state.selectedPaths.clear();
            await loadArticlesCatalog();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast("批量入库异常: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "🚀 批量入库微信";
    }
}

// 批量排期
async function handleBatchSchedulePrompt() {
    const paths = Array.from(state.selectedPaths);
    if (paths.length === 0) return;
    
    const todayStr = new Date().toISOString().split("T")[0];
    const targetDate = prompt(`请为选中的 ${paths.length} 篇文章设定发文日期 (格式 YYYY-MM-DD，留空则清空排期):`, todayStr);
    if (targetDate === null) return;
    
    try {
        const response = await fetch("/api/articles/batch-schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                paths: paths,
                scheduled_date: targetDate.trim()
            })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message, "success");
            state.selectedPaths.clear();
            await loadArticlesCatalog();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast("批量排期失败: " + e.message, "error");
    }
}

// 批量删除
async function handleBatchDelete() {
    const paths = Array.from(state.selectedPaths);
    if (paths.length === 0) return;
    
    if (!confirm(`警告：确定要从工作区批量删除选中的 ${paths.length} 篇 Markdown 草稿吗？此操作不可逆。`)) {
        return;
    }
    
    try {
        const response = await fetch("/api/articles/batch-delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paths: paths })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message, "success");
            state.selectedPaths.clear();
            await loadArticlesCatalog();
            await loadWorkspaceFiles();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast("批量删除失败: " + e.message, "error");
    }
}

// ==========================================================================
// 4. 单行操作与工作台联动
// ==========================================================================

// 设定单篇文章排期
async function setArticleSchedule(path, dateVal) {
    const newStatus = dateVal ? "scheduled" : "draft";
    try {
        const res = await fetch("/api/articles/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                path: path,
                scheduled_date: dateVal,
                status: newStatus
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(dateVal ? `已排期: ${dateVal}` : "已恢复待审核状态", "success");
            await loadArticlesCatalog();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast("更新排期失败: " + e.message, "error");
    }
}

// 快捷弹窗改期
function promptSchedule(path, currentDate) {
    const newDate = prompt(`请为文章指定排期发文日期 (格式 YYYY-MM-DD，清空则重置为待审核):`, currentDate || "");
    if (newDate === null) return;
    setArticleSchedule(path, newDate.trim());
}

// 单篇直连同步草稿箱
async function syncSingleArticle(path, btnEl) {
    if (btnEl) {
        btnEl.disabled = true;
        btnEl.textContent = "同步中...";
    }
    
    showToast(`正在推送文章至微信草稿箱...`, "info");
    
    try {
        const res = await fetch("/api/articles/sync-one", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        
        if (res.status === 403 && data.error_type === "IP_WHITELIST") {
            showToast("同步失败：IP 未加白名单 (" + data.ip + ")", "error");
            appendLog(`❌ 微信报错 40164: IP [${data.ip}] 未加白名单`, "error");
        } else if (data.success) {
            showToast(`《${data.title}》已成功推送到微信草稿箱！`, "success");
            appendLog(`🎉 文章入库成功: ${data.title} | MediaID: ${data.media_id}`, "success");
            await loadArticlesCatalog();
        } else {
            throw new Error(data.message || "微信 API 异常");
        }
    } catch (e) {
        showToast("同步失败: " + e.message, "error");
    } finally {
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.textContent = "入库";
        }
    }
}

// 单篇删除
async function deleteArticle(path) {
    if (!confirm(`确定要删除草稿文件 '${path}' 吗？此操作无法撤销。`)) {
        return;
    }
    try {
        const res = await fetch("/api/articles/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.success) {
            showToast("文章已删除", "info");
            state.selectedPaths.delete(path);
            await loadArticlesCatalog();
            await loadWorkspaceFiles();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast("删除异常: " + e.message, "error");
    }
}

// 从表格点「预览」：秒切工作台并自动装载编译
async function previewFromCatalog(path) {
    switchMainView('workspace');
    
    const mdSelect = document.getElementById("md-file-select");
    let foundInSelect = false;
    for (let i = 0; i < mdSelect.options.length; i++) {
        if (mdSelect.options[i].value === path) {
            mdSelect.selectedIndex = i;
            foundInSelect = true;
            break;
        }
    }
    
    if (foundInSelect) {
        switchFileTab('workspace');
    } else {
        document.getElementById("md-path-manual").value = path;
        switchFileTab('manual');
    }
    
    await checkMdFrontmatter(path);
    await triggerPreview();
}

// ==========================================================================
// 5. 视图切换与模态框
// ==========================================================================

function switchMainView(viewName) {
    state.activeView = viewName;
    
    const sideLib = document.getElementById("side-nav-library");
    const sideWs = document.getElementById("side-nav-workspace");
    const viewLib = document.getElementById("library-view");
    const viewWs = document.getElementById("workspace-view");
    const breadcrumbCurrent = document.getElementById("breadcrumb-current");
    
    const activeNavClass = "w-full h-9 px-2.5 rounded text-xs font-medium flex items-center gap-2 bg-blue-50 text-blue-700 border-l-2 border-blue-600 transition-colors";
    const inactiveNavClass = "w-full h-9 px-2.5 rounded text-xs font-medium flex items-center gap-2 text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-l-2 border-transparent transition-colors";
    
    if (viewName === "library") {
        if (sideLib) sideLib.className = activeNavClass;
        if (sideWs) sideWs.className = inactiveNavClass;
        if (viewLib) viewLib.classList.remove("hidden");
        if (viewWs) viewWs.classList.add("hidden");
        if (breadcrumbCurrent) breadcrumbCurrent.textContent = "文章管理与排期";
        loadArticlesCatalog();
    } else {
        if (sideLib) sideLib.className = inactiveNavClass;
        if (sideWs) sideWs.className = activeNavClass;
        if (viewLib) viewLib.classList.add("hidden");
        if (viewWs) viewWs.classList.remove("hidden");
        if (breadcrumbCurrent) breadcrumbCurrent.textContent = "极速排版与创作";
    }
}

function openConfigModal() {
    document.getElementById("config-modal").classList.remove("hidden");
}

function closeConfigModal() {
    document.getElementById("config-modal").classList.add("hidden");
}

// 选项卡切换
function switchFileTab(tab) {
    state.activeFileTab = tab;
    const wsTab = document.getElementById("workspace-tab");
    const mnTab = document.getElementById("manual-tab");
    const btnWs = document.getElementById("tab-btn-file-ws");
    const btnMn = document.getElementById("tab-btn-file-manual");
    
    const activeTabClass = "tab-selector-btn text-blue-600 border-b-2 border-blue-600 font-medium px-1.5 py-0.5";
    const inactiveTabClass = "tab-selector-btn text-slate-500 hover:text-slate-800 px-1.5 py-0.5";
    
    if (tab === "workspace") {
        if (btnWs) btnWs.className = activeTabClass;
        if (btnMn) btnMn.className = inactiveTabClass;
        if (wsTab) wsTab.classList.remove("hidden");
        if (mnTab) mnTab.classList.add("hidden");
    } else {
        if (btnWs) btnWs.className = inactiveTabClass;
        if (btnMn) btnMn.className = activeTabClass;
        if (wsTab) wsTab.classList.add("hidden");
        if (mnTab) mnTab.classList.remove("hidden");
    }
}

function switchCoverTab(tab) {
    state.activeCoverTab = tab;
    const wsTab = document.getElementById("cover-workspace-tab");
    const mnTab = document.getElementById("cover-manual-tab");
    const btnWs = document.getElementById("tab-btn-cover-ws");
    const btnMn = document.getElementById("tab-btn-cover-manual");
    
    const activeTabClass = "tab-selector-btn text-blue-600 border-b-2 border-blue-600 font-medium px-1.5 py-0.5";
    const inactiveTabClass = "tab-selector-btn text-slate-500 hover:text-slate-800 px-1.5 py-0.5";
    
    if (tab === "workspace") {
        if (btnWs) btnWs.className = activeTabClass;
        if (btnMn) btnMn.className = inactiveTabClass;
        if (wsTab) wsTab.classList.remove("hidden");
        if (mnTab) mnTab.classList.add("hidden");
    } else {
        if (btnWs) btnWs.className = inactiveTabClass;
        if (btnMn) btnMn.className = activeTabClass;
        if (wsTab) wsTab.classList.add("hidden");
        if (mnTab) mnTab.classList.remove("hidden");
    }
}

// 原生文件选择对话框
async function browseFile(fileType) {
    const isMd = fileType === 'md';
    const manualInput = isMd ? document.getElementById("md-path-manual") : document.getElementById("cover-path-manual");
    
    try {
        const response = await fetch("/api/select-file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file_type: fileType })
        });
        const data = await response.json();
        if (data.success && data.file_path) {
            manualInput.value = data.file_path;
            if (isMd) {
                switchFileTab('manual');
                checkMdFrontmatter(data.file_path);
            } else {
                switchCoverTab('manual');
            }
            showToast("已选择文件: " + data.file_path.split("/").pop(), "success");
        }
    } catch (e) {
        showToast("选择文件异常: " + e.message, "error");
    }
}

// Frontmatter 智能读取
async function checkMdFrontmatter(mdPath) {
    if (!mdPath || !mdPath.trim()) return;
    try {
        const response = await fetch("/api/parse-frontmatter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ md_path: mdPath.trim() })
        });
        const data = await response.json();
        if (data.success && data.has_frontmatter) {
            const fm = data.frontmatter;
            if (fm.title) document.getElementById("article-title").value = fm.title;
            if (fm.digest) document.getElementById("article-digest").value = fm.digest;
            if (fm.content_source_url) document.getElementById("content-source-url").value = fm.content_source_url;
            if (fm.style) document.getElementById("theme-style").value = fm.style;
            if (fm.pygments_style) document.getElementById("pygments-style").value = fm.pygments_style;
            if (typeof fm.enable_footnotes === "boolean") document.getElementById("enable-footnotes").checked = fm.enable_footnotes;
            if (fm.cover) {
                document.getElementById("cover-path-manual").value = fm.cover;
                switchCoverTab("manual");
            }
        }
    } catch (e) {
        console.warn("Frontmatter 解析失败:", e);
    }
}

// 执行本地排版预览
async function triggerPreview() {
    const mdPath = getSelectedMdPath();
    const styleTheme = document.getElementById("pygments-style").value;
    const themeStyle = document.getElementById("theme-style").value;
    const enableFootnotes = document.getElementById("enable-footnotes").checked;
    
    if (!mdPath) {
        showToast("请先选择 Markdown 文件", "error");
        return;
    }
    
    const previewBtn = document.getElementById("preview-btn");
    previewBtn.disabled = true;
    previewBtn.textContent = "编译中...";
    appendLog(`开始解析编译 Markdown: ${mdPath} [样式: ${themeStyle}]`, "info");
    
    try {
        const response = await fetch("/api/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                md_path: mdPath,
                style: themeStyle,
                pygments_style: styleTheme,
                enable_footnotes: enableFootnotes
            })
        });
        const data = await response.json();
        if (data.success) {
            renderHtmlInIframe(data.html);
            appendLog("排版编译成功！CSS 样式及高亮代码已完全行内化注入。", "success");
            showToast("本地排版渲染成功！", "success");
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("编译失败: " + error.message, "error");
        appendLog("编译排版失败: " + error.message, "error");
    } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = "👁️ 编译排版并预览";
    }
}

// 工作台单篇同步草稿箱
async function triggerSync() {
    const mdPath = getSelectedMdPath();
    const coverPath = getSelectedCoverPath();
    const themeStyle = document.getElementById("theme-style").value;
    const enableFootnotes = document.getElementById("enable-footnotes").checked;
    
    if (!mdPath) {
        showToast("请选择 Markdown 文件", "error");
        return;
    }
    
    const syncBtn = document.getElementById("sync-btn");
    syncBtn.disabled = true;
    syncBtn.textContent = "正在同步微信...";
    
    appendLog("触发微信草稿箱同步任务...", "info");
    
    const payload = {
        md_path: mdPath,
        cover_path: coverPath,
        title: document.getElementById("article-title").value,
        author: document.getElementById("author").value,
        digest: document.getElementById("article-digest").value,
        style: themeStyle,
        pygments_style: document.getElementById("pygments-style").value,
        enable_footnotes: enableFootnotes,
        content_source_url: document.getElementById("content-source-url").value
    };
    
    try {
        const response = await fetch("/api/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (response.status === 403 && data.error_type === "IP_WHITELIST") {
            appendLog(`❌ 微信 API 报错: 40164 (IP 白名单错误: ${data.ip})`, "error");
            showToast("同步失败：当前 IP 未加白名单 (" + data.ip + ")", "error");
        } else if (data.success) {
            appendLog(`🎉 微信草稿箱同步成功！Media ID: ${data.media_id}`, "success");
            showToast("已成功同步至微信公众平台草稿箱！", "success");
            loadArticlesCatalog();
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("微信同步失败: " + error.message, "error");
        appendLog("微信同步失败: " + error.message, "error");
    } finally {
        syncBtn.disabled = false;
        syncBtn.textContent = "🚀 一键同步草稿箱";
    }
}

function getSelectedMdPath() {
    const manualVal = document.getElementById("md-path-manual").value.trim();
    const selectVal = document.getElementById("md-file-select").value;
    return state.activeFileTab === "manual" ? (manualVal || selectVal) : (selectVal || manualVal);
}

function getSelectedCoverPath() {
    const manualVal = document.getElementById("cover-path-manual").value.trim();
    const selectVal = document.getElementById("cover-file-select").value;
    return state.activeCoverTab === "manual" ? (manualVal || selectVal) : (selectVal || manualVal);
}

function renderHtmlInIframe(htmlContent) {
    const iframe = document.getElementById("preview-frame");
    const placeholder = document.getElementById("preview-placeholder");
    placeholder.classList.add("hidden");
    
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open();
    doc.write(htmlContent);
    doc.close();
}

function appendLog(message, type = "info") {
    const container = document.getElementById("console-logs");
    if (!container) return;
    const line = document.createElement("div");
    let colorClass = "text-slate-300";
    if (type === "success") colorClass = "text-emerald-400 font-medium";
    else if (type === "error") colorClass = "text-red-400 font-medium";
    else if (type === "warning") colorClass = "text-amber-400 font-medium";
    else if (type === "info") colorClass = "text-blue-400";
    
    line.className = `leading-tight ${colorClass}`;
    const timeStr = new Date().toLocaleTimeString();
    line.textContent = `[${timeStr}] ${message}`;
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;
}

function clearConsole() {
    document.getElementById("console-logs").innerHTML = "";
}

function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    const icon = document.getElementById("toast-icon");
    const msg = document.getElementById("toast-msg");
    if (!toast) return;
    
    let iconChar = "✓";
    let iconColor = "text-emerald-600";
    let borderClass = "border-slate-200";
    
    if (type === "success") {
        iconChar = "✓";
        iconColor = "text-emerald-600";
        borderClass = "border-emerald-300";
    } else if (type === "error") {
        iconChar = "✕";
        iconColor = "text-red-500";
        borderClass = "border-red-300";
    } else if (type === "warning") {
        iconChar = "⚠";
        iconColor = "text-amber-500";
        borderClass = "border-amber-300";
    } else {
        iconChar = "ℹ️";
        iconColor = "text-blue-500";
        borderClass = "border-blue-300";
    }
    
    icon.textContent = iconChar;
    icon.className = `text-sm font-bold ${iconColor}`;
    msg.textContent = message;
    toast.className = `fixed top-4 left-1/2 -translate-x-1/2 bg-white border ${borderClass} rounded shadow-md px-3.5 py-2 text-xs flex items-center gap-2 z-50 transition-all`;
    toast.classList.remove("hidden");
    
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.classList.add("hidden");
    }, 2800);
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function setupEventListeners() {
    // 监听 Markdown 下拉选择变动
    const mdSelect = document.getElementById("md-file-select");
    if (mdSelect) {
        mdSelect.addEventListener("change", (e) => checkMdFrontmatter(e.target.value));
    }
}
