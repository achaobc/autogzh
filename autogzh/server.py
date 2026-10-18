import os
import sys
import logging
import webbrowser
import yaml
from flask import Flask, request, jsonify, render_template, send_from_directory

from .client import WeChatClient, WeChatAPIError, WeChatIPWhitelistError
from .renderer import MarkdownRenderer, extract_title_from_md, extract_digest_from_html, extract_frontmatter_from_file

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

# 初始化 Flask
app = Flask(
    __name__,
    static_url_path="/ui/static",
    static_folder=os.path.join(PROJECT_ROOT, "ui", "static"),
    template_folder=os.path.join(PROJECT_ROOT, "ui", "templates")
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WORKSPACE_DIR = PROJECT_ROOT
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

def get_config():
    """读取 config.yaml"""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"读取配置失败: {e}")
        return {}

def save_config(config_data):
    """保存到 config.yaml"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"写入配置失败: {e}")
        return False

def scan_workspace_files():
    """扫描工作区中的 Markdown 文件和图片文件，排除系统与输出目录"""
    md_files = []
    img_files = []
    
    exclude_dirs = {'.git', 'venv', '__pycache__', '.agents', '.gemini', 'styles', 'build', 'dist', 'autogzh', 'scripts', '.github', 'output'}
    exclude_files = {'requirements.txt', 'commit_msg.txt', 'app.ico'}
    
    for root, dirs, files in os.walk(WORKSPACE_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file in exclude_files:
                continue
                
            rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
            rel_path_unix = rel_path.replace("\\", "/")
            
            if file.endswith(".md"):
                md_files.append(rel_path_unix)
            elif file.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                img_files.append(rel_path_unix)
                
    return {
        "markdown_files": sorted(md_files),
        "image_files": sorted(img_files)
    }

@app.route("/")
def index():
    """首页"""
    return render_template("index.html")

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取配置接口"""
    config = get_config()
    wechat = config.get("wechat", {})
    defaults = config.get("draft_defaults", {})
    
    return jsonify({
        "appid": wechat.get("appid", ""),
        "secret": wechat.get("secret", ""),
        "author": defaults.get("author", "默认作者"),
        "show_cover_pic": defaults.get("show_cover_pic", 1),
        "need_open_comment": defaults.get("need_open_comment", 0),
        "only_less_tags": defaults.get("only_less_tags", 0)
    })

@app.route("/api/config", methods=["POST"])
def api_post_config():
    """更新配置接口"""
    data = request.json or {}
    
    config = {
        "wechat": {
            "appid": data.get("appid", "").strip(),
            "secret": data.get("secret", "").strip()
        },
        "draft_defaults": {
            "author": data.get("author", "").strip(),
            "show_cover_pic": int(data.get("show_cover_pic", 1)),
            "need_open_comment": int(data.get("need_open_comment", 0)),
            "only_less_tags": int(data.get("only_less_tags", 0))
        }
    }
    
    if save_config(config):
        return jsonify({"success": True, "message": "配置保存成功"})
    else:
        return jsonify({"success": False, "message": "配置保存失败"}), 500

@app.route("/api/themes", methods=["GET"])
def api_get_themes():
    """获取所有可用排版样式主题"""
    themes = [
        {"id": "default", "name": "优雅茶青 (Elegant Teal - 默认)"},
        {"id": "tech", "name": "深邃科技蓝 (Tech Blue)"},
        {"id": "minimal", "name": "极简冷灰 (Minimalist Gray)"},
        {"id": "warm", "name": "暖意秋橙 (Warm Autumn)"}
    ]
    styles_dir = os.path.join(WORKSPACE_DIR, "styles")
    if os.path.exists(styles_dir):
        known_ids = {t["id"] for t in themes}
        for f in sorted(os.listdir(styles_dir)):
            if f.endswith(".css"):
                theme_id = os.path.splitext(f)[0]
                if theme_id not in known_ids:
                    themes.append({"id": theme_id, "name": f"自定义样式 ({f})"})
    return jsonify(themes)

@app.route("/api/parse-frontmatter", methods=["POST"])
def api_parse_frontmatter():
    """解析 Markdown 文件的 Frontmatter 元数据"""
    data = request.json or {}
    md_path_input = data.get("md_path", "").strip()
    if not md_path_input:
        return jsonify({"success": False, "message": "缺少文件路径"}), 400
        
    abs_md_path = os.path.abspath(md_path_input if os.path.isabs(md_path_input) else os.path.join(WORKSPACE_DIR, md_path_input))
    if not os.path.exists(abs_md_path):
        return jsonify({"success": False, "message": "文件不存在"}), 404
        
    frontmatter, _ = extract_frontmatter_from_file(abs_md_path)
    return jsonify({
        "success": True,
        "has_frontmatter": bool(frontmatter),
        "frontmatter": frontmatter
    })

@app.route("/api/files", methods=["GET"])
def api_get_files():
    """获取工作区文件列表"""
    try:
        files = scan_workspace_files()
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/select-file", methods=["POST"])
def api_select_file():
    """打开系统原生文件选择对话框"""
    data = request.json or {}
    file_type = data.get("file_type", "md")
    
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        
        if file_type == "image":
            title = "选择封面图片"
            filetypes = [("图片文件 (*.png;*.jpg;*.jpeg;*.gif;*.webp)", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.PNG;*.JPG;*.JPEG;*.GIF;*.WEBP"), ("所有文件 (*.*)", "*.*")]
        else:
            title = "选择 Markdown 文件"
            filetypes = [("Markdown 文件 (*.md)", "*.md;*.MD"), ("所有文件 (*.*)", "*.*")]
            
        file_path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes
        )
        root.destroy()
        
        if file_path:
            file_path_clean = file_path.replace("\\", "/")
            logger.info(f"用户选择了本地文件: {file_path_clean}")
            return jsonify({"success": True, "file_path": file_path_clean})
        else:
            return jsonify({"success": False, "cancelled": True, "message": "用户取消选择"})
    except Exception as e:
        logger.error(f"调用系统文件选择窗口异常: {e}")
        return jsonify({"success": False, "message": f"无法打开文件选择框: {str(e)}"}), 500

@app.route("/api/preview", methods=["POST"])
def api_post_preview():
    """本地预览排版编译"""
    data = request.json or {}
    md_path_input = data.get("md_path", "").strip()
    pygments_style = data.get("pygments_style", "monokai")
    style_input = data.get("style", "default")
    enable_footnotes = bool(data.get("enable_footnotes", True))
    
    if not md_path_input:
        return jsonify({"success": False, "message": "请选择或输入 Markdown 文件路径"}), 400
        
    abs_md_path = os.path.abspath(md_path_input if os.path.isabs(md_path_input) else os.path.join(WORKSPACE_DIR, md_path_input))
    if not os.path.exists(abs_md_path):
        return jsonify({"success": False, "message": f"未找到 Markdown 文件: {md_path_input}"}), 404
        
    try:
        from urllib.parse import quote
        class MockWeChatClient:
            def upload_body_image(self, local_path):
                encoded_path = quote(local_path)
                return f"/api/local-image-file?path={encoded_path}"
                
        renderer = MarkdownRenderer(
            css_path=style_input, 
            pygments_style=pygments_style,
            enable_footnotes=enable_footnotes
        )
        html_content = renderer.render(abs_md_path, MockWeChatClient())
        
        return jsonify({"success": True, "html": html_content})
    except Exception as e:
        logger.error(f"本地编译渲染失败: {e}")
        return jsonify({"success": False, "message": f"排版编译失败: {str(e)}"}), 500

@app.route("/api/local-image-file")
def serve_local_image_file():
    """提供任意绝对路径的本地图片服务"""
    from urllib.parse import unquote
    from flask import send_file
    raw_path = request.args.get("path", "")
    if not raw_path:
        return "Missing path", 400
    abs_path = unquote(raw_path)
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        return send_file(abs_path)
    return "File not found", 404

@app.route("/api/local-image/<path:filepath>")
def serve_local_image(filepath):
    """为预览提供本地相对路径图片服务"""
    abs_path = os.path.join(WORKSPACE_DIR, filepath)
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    return send_from_directory(directory, filename)

@app.route("/api/sync", methods=["POST"])
def api_post_sync():
    """同步到微信草稿箱"""
    data = request.json or {}
    md_path_input = data.get("md_path", "").strip()
    cover_path_input = data.get("cover_path", "").strip()
    title_input = data.get("title", "").strip()
    author_input = data.get("author", "").strip()
    digest_input = data.get("digest", "").strip()
    style_input = data.get("style", "default")
    pygments_style = data.get("pygments_style", "monokai")
    content_source_url = data.get("content_source_url", "").strip()
    enable_footnotes = bool(data.get("enable_footnotes", True))
    
    if not md_path_input:
        return jsonify({"success": False, "message": "Markdown 文件路径不能为空"}), 400
        
    abs_md_path = os.path.abspath(md_path_input if os.path.isabs(md_path_input) else os.path.join(WORKSPACE_DIR, md_path_input))
    if not os.path.exists(abs_md_path):
        return jsonify({"success": False, "message": f"未找到 Markdown 文件: {md_path_input}"}), 404

    # 优先解析 Frontmatter 辅助补全缺省要素
    frontmatter, _ = extract_frontmatter_from_file(abs_md_path)
    
    if not cover_path_input and frontmatter.get("cover"):
        cover_path_input = str(frontmatter.get("cover")).strip()
        
    if not cover_path_input:
        return jsonify({"success": False, "message": "封面图路径不能为空，请选择封面图片或在 Markdown Frontmatter 中指定 cover"}), 400
        
    abs_cover_path = os.path.abspath(cover_path_input if os.path.isabs(cover_path_input) else os.path.join(WORKSPACE_DIR, cover_path_input))
    if not os.path.exists(abs_cover_path):
        return jsonify({"success": False, "message": f"未找到封面图片文件: {cover_path_input}"}), 404
        
    config = get_config()
    wechat_conf = config.get("wechat", {})
    defaults_conf = config.get("draft_defaults", {})
    
    appid = wechat_conf.get("appid")
    secret = wechat_conf.get("secret")
    
    if not appid or not secret or appid == "YOUR_APPID" or secret == "YOUR_APPSECRET":
        return jsonify({"success": False, "message": "未配置有效的公众号 AppID 或 AppSecret，请先在配置面板中填写"}), 400
        
    try:
        client = WeChatClient(appid=appid, secret=secret)
        
        # 确定文章标题 (优先前端传参 -> 其次 Frontmatter -> 再次提取首个 H1)
        title = title_input or frontmatter.get("title")
        if not title:
            title = extract_title_from_md(abs_md_path)
            
        # 确定作者
        author = author_input or frontmatter.get("author") or defaults_conf.get("author", "")
        
        # 确定样式与高亮主题
        final_style = style_input or frontmatter.get("style", "default")
        final_pygments = pygments_style or frontmatter.get("pygments_style", "monokai")
        if "enable_footnotes" in frontmatter and isinstance(frontmatter["enable_footnotes"], bool):
            enable_footnotes = frontmatter["enable_footnotes"]

        if not content_source_url and frontmatter.get("content_source_url"):
            content_source_url = str(frontmatter.get("content_source_url")).strip()

        # 上传封面图片
        cover_media_id = client.upload_cover_image(abs_cover_path)
        
        # 渲染 HTML 并上传/替换正文图片 (支持 MD5 秒传与并发上传)
        renderer = MarkdownRenderer(
            css_path=final_style, 
            pygments_style=final_pygments,
            enable_footnotes=enable_footnotes
        )
        html_content = renderer.render(abs_md_path, client)
        
        # 处理摘要 (优先前端 -> 其次 Frontmatter -> 再次配置 -> 自动提取)
        digest = digest_input or frontmatter.get("digest")
        if not digest:
            digest = defaults_conf.get("digest")
            if not digest:
                digest = extract_digest_from_html(html_content)
                
        # 摘要 120 字节限额截断
        if digest:
            encoded_digest = digest.encode('utf-8')
            if len(encoded_digest) > 120:
                digest = encoded_digest[:117].decode('utf-8', errors='ignore') + "..."
                
        # 提交微信草稿箱
        draft_media_id = client.create_draft(
            title=title,
            content=html_content,
            thumb_media_id=cover_media_id,
            author=author,
            digest=digest,
            content_source_url=content_source_url,
            need_open_comment=int(defaults_conf.get("need_open_comment", 0)),
            only_less_tags=int(defaults_conf.get("only_less_tags", 0))
        )
        
        return jsonify({
            "success": True,
            "media_id": draft_media_id,
            "title": title,
            "author": author,
            "digest": digest
        })
        
    except WeChatIPWhitelistError as e:
        return jsonify({
            "success": False,
            "error_type": "IP_WHITELIST",
            "message": str(e),
            "ip": e.ip
        }), 403
    except WeChatAPIError as e:
        return jsonify({
            "success": False,
            "message": f"微信 API 错误 [代码 {e.errcode}]: {e.errmsg}"
        }), 500
    except Exception as e:
        logger.error(f"同步失败: {e}")
        return jsonify({
            "success": False,
            "message": f"同步失败，发生系统异常: {str(e)}"
        }), 500

def start_server(port=5000, open_browser=True):
    """启动 Flask 服务"""
    if open_browser:
        import threading
        def open_url():
            import time
            time.sleep(1.0)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=open_url, daemon=True).start()
        
    logger.info(f"正在启动本地 Web 服务，访问地址: http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    start_server()
