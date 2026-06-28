// 微信公众号 Markdown 自动排版与同步工具 UI 前端交互逻辑

// 状态管理
const state = {
    selectedMdPath: "",
    selectedCoverPath: "",
    activeFileTab: "workspace", // workspace | manual
    activeCoverTab: "workspace"  // workspace | manual
};

// 页面加载完毕后初始化
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

function initApp() {
    // 1. 加载配置信息
    loadConfig();
    
    // 2. 加载工作区文件列表
    loadWorkspaceFiles();
    
    // 3. 注册事件监听器
    setupEventListeners();
}

// --------------------------------------------------------------------------
// 数据加载方法
// --------------------------------------------------------------------------

// 加载配置
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
        
        appendLog("成功加载微信公众号配置信息。", "info");
    } catch (error) {
        showToast("加载配置失败：" + error.message, "error");
        appendLog("加载公众号配置失败，请检查配置文件格式。", "error");
    }
}

// 保存配置
async function saveConfig(e) {
    e.preventDefault();
    const btn = document.getElementById("save-config-btn");
    btn.disabled = true;
    btn.textContent = "保存中...";
    
    const payload = {
        appid: document.getElementById("appid").value,
        secret: document.getElementById("secret").value,
        author: document.getElementById("author").value,
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
            showToast("配置保存成功！", "success");
            appendLog("系统配置已更新并写入本地 config.yaml。", "success");
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("保存失败：" + error.message, "error");
        appendLog("保存配置失败: " + error.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "保存系统配置";
    }
}

// 加载工作区文件
async function loadWorkspaceFiles() {
    try {
        const response = await fetch("/api/files");
        if (!response.ok) throw new Error("获取文件列表失败");
        const data = await response.json();
        
        // 填充 Markdown 选择框
        const mdSelect = document.getElementById("md-file-select");
        // 保留第一项提示
        mdSelect.innerHTML = '<option value="">-- 请选择工作区内的 Markdown 文件 --</option>';
        data.markdown_files.forEach(file => {
            const opt = document.createElement("option");
            opt.value = file;
            opt.textContent = file;
            mdSelect.appendChild(opt);
        });
        
        // 填充图片选择框
        const coverSelect = document.getElementById("cover-file-select");
        coverSelect.innerHTML = '<option value="">-- 请选择工作区内的封面图片 --</option>';
        data.image_files.forEach(file => {
            const opt = document.createElement("option");
            opt.value = file;
            opt.textContent = file;
            coverSelect.appendChild(opt);
        });
        
        // 提示当前扫描到的工作路径
        document.getElementById("workspace-path").textContent = "auto-gzh";
        appendLog(`工作区扫描完毕: 发现 ${data.markdown_files.length} 个 Markdown 文件, ${data.image_files.length} 张图片。`, "info");
    } catch (error) {
        showToast("加载工作区文件失败", "error");
        appendLog("扫描工作区文件失败，请检查程序运行路径权限。", "error");
    }
}

// --------------------------------------------------------------------------
// 核心操作：预览与同步
// --------------------------------------------------------------------------

// 执行排版编译预览
async function triggerPreview() {
    const mdPath = getSelectedMdPath();
    const styleTheme = document.getElementById("pygments-style").value;
    
    if (!mdPath) {
        showToast("请先选择或输入 Markdown 文件路径", "error");
        appendLog("预览失败: 未选择 Markdown 文件。", "warning");
        return;
    }
    
    const previewBtn = document.getElementById("preview-btn");
    previewBtn.disabled = true;
    previewBtn.textContent = "编译中...";
    
    appendLog(`开始本地排版编译，正在解析 '${mdPath}'...`, "info");
    
    try {
        const response = await fetch("/api/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                md_path: mdPath,
                pygments_style: styleTheme
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            renderHtmlInIframe(data.html);
            appendLog("排版编译成功！CSS 样式及高亮代码已完全行内化注入，已加载到预览视口中。", "success");
            showToast("本地编译预览成功！", "success");
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("编译失败：" + error.message, "error");
        appendLog("编译排版失败: " + error.message, "error");
    } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = "👁️ 编译并本地预览";
    }
}

// 执行微信草稿箱同步
async function triggerSync() {
    const mdPath = getSelectedMdPath();
    const coverPath = getSelectedCoverPath();
    
    if (!mdPath || !coverPath) {
        showToast("Markdown 文件与封面图均为必填项", "error");
        appendLog("同步失败: Markdown 或 封面图路径未填写完整。", "warning");
        return;
    }
    
    const syncBtn = document.getElementById("sync-btn");
    syncBtn.disabled = true;
    syncBtn.textContent = "正在同步微信...";
    
    appendLog("触发微信草稿箱一键同步...", "info");
    appendLog("正在上传封面图素材，上传图文内本地插图，并转换排版 HTML...", "info");
    
    const payload = {
        md_path: mdPath,
        cover_path: coverPath,
        title: document.getElementById("article-title").value,
        author: document.getElementById("author").value,
        digest: document.getElementById("article-digest").value,
        pygments_style: document.getElementById("pygments-style").value,
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
            // 特别捕获 IP 白名单错误，在日志中显示漂亮卡片
            appendLog(`❌ 微信 API 报错: 40164 (IP 白名单错误)`, "error");
            renderIpWhitelistWarning(data.ip);
            showToast("同步失败：当前 IP 未加白", "error");
        } else if (data.success) {
            appendLog(`🎉 微信图文草稿同步成功！`, "success");
            appendLog(`👉 草稿 Media ID: ${data.media_id}`, "success");
            appendLog(`👉 标题: ${data.title} | 作者: ${data.author}`, "info");
            appendLog(`👉 摘要: ${data.digest}`, "info");
            appendLog(`请前往微信公众平台后台 -> 「内容分析/草稿箱」查看、预览并发送您的文章。`, "success");
            showToast("微信草稿箱同步成功！", "success");
        } else {
            throw new Error(data.message);
        }
    } catch (error) {
        showToast("同步失败：" + error.message, "error");
        appendLog("微信同步任务失败: " + error.message, "error");
    } finally {
        syncBtn.disabled = false;
        syncBtn.textContent = "🚀 一键同步草稿箱";
    }
}

// --------------------------------------------------------------------------
// 辅助交互与 UI 操作方法
// --------------------------------------------------------------------------

// 切换文件选择方式 Tab
function setupEventListeners() {
    // 监听表单配置保存
    document.getElementById("config-form").addEventListener("submit", saveConfig);
    
    // 绑定按钮点击
    document.getElementById("preview-btn").addEventListener("click", triggerPreview);
    document.getElementById("sync-btn").addEventListener("click", triggerSync);
    document.getElementById("clear-console-btn").addEventListener("click", clearConsole);
}

window.switchFileTab = function(tabName) {
    state.activeFileTab = tabName;
    
    const wsBtn = document.querySelectorAll(".tab-btn")[0];
    const mnBtn = document.querySelectorAll(".tab-btn")[1];
    
    const wsTab = document.getElementById("workspace-tab");
    const mnTab = document.getElementById("manual-tab");
    
    if (tabName === "workspace") {
        wsBtn.classList.add("active");
        mnBtn.classList.remove("active");
        wsTab.classList.remove("hidden");
        mnTab.classList.add("hidden");
    } else {
        wsBtn.classList.remove("active");
        mnBtn.classList.add("active");
        wsTab.classList.add("hidden");
        mnTab.classList.remove("hidden");
    }
};

window.switchCoverTab = function(tabName) {
    state.activeCoverTab = tabName;
    
    const wsBtn = document.querySelectorAll(".tab-btn")[2];
    const mnBtn = document.querySelectorAll(".tab-btn")[3];
    
    const wsTab = document.getElementById("cover-workspace-tab");
    const mnTab = document.getElementById("cover-manual-tab");
    
    if (tabName === "workspace") {
        wsBtn.classList.add("active");
        mnBtn.classList.remove("active");
        wsTab.classList.remove("hidden");
        mnTab.classList.add("hidden");
    } else {
        wsBtn.classList.remove("active");
        mnBtn.classList.add("active");
        wsTab.classList.add("hidden");
        mnTab.classList.remove("hidden");
    }
};

// 密码框明文/暗文切换
window.togglePasswordVisibility = function(id) {
    const input = document.getElementById(id);
    const trigger = input.nextElementSibling;
    if (input.type === "password") {
        input.type = "text";
        trigger.textContent = "🔒";
    } else {
        input.type = "password";
        trigger.textContent = "👁️";
    }
};

// 获取最终选定的文件路径
function getSelectedMdPath() {
    if (state.activeFileTab === "workspace") {
        return document.getElementById("md-file-select").value;
    } else {
        return document.getElementById("md-path-manual").value.stripOrEmpty();
    }
}

function getSelectedCoverPath() {
    if (state.activeCoverTab === "workspace") {
        return document.getElementById("cover-file-select").value;
    } else {
        return document.getElementById("cover-path-manual").value.stripOrEmpty();
    }
}

String.prototype.stripOrEmpty = function() {
    return this.trim();
};

// 在 Iframe 中载入编译完毕的 HTML
function renderHtmlInIframe(htmlContent) {
    const iframe = document.getElementById("preview-frame");
    const placeholder = document.getElementById("preview-placeholder");
    
    // 隐藏占位区
    placeholder.classList.add("hidden");
    
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open();
    doc.write(htmlContent);
    doc.close();
}

// 写入控制台日志
function appendLog(message, type = "info") {
    const logsContainer = document.getElementById("console-logs");
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    
    const timeStr = new Date().toLocaleTimeString();
    line.textContent = `[${timeStr}] ${message}`;
    
    logsContainer.appendChild(line);
    // 滚动条自动置底
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// 清理控制台
function clearConsole() {
    document.getElementById("console-logs").innerHTML = "";
    appendLog("控制台已清空。", "info");
}

// 显示 Toast 浮窗提示
function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.classList.remove("hidden");
    
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}

// 渲染漂亮的 IP 加白引导卡片
function renderIpWhitelistWarning(ip) {
    const logsContainer = document.getElementById("console-logs");
    
    const card = document.createElement("div");
    card.className = "ip-warning-card";
    card.innerHTML = `
        <h4>❌ IP 未加白名单错误</h4>
        <p>您当前运行此工具的公网 IP <code>${ip}</code> 未加入微信公众号的 IP 白名单配置中。</p>
        <p><strong>解决方案：</strong></p>
        <p>1. 登录<strong>「微信公众平台」</strong>(mp.weixin.qq.com)<br>
           2. 进入左侧菜单: <strong>「设置与开发」 -> 「基本配置」</strong><br>
           3. 找到<strong>「IP白名单」</strong>配置项，点击「修改」<br>
           4. 将当前公网 IP 地址 【 <code>${ip}</code> 】 添加到列表中保存即可。</p>
    `;
    
    logsContainer.appendChild(card);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}
