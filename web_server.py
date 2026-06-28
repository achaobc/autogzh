import os
import sys
import logging
import webbrowser
import yaml
from flask import Flask, request, jsonify, render_template, send_from_directory

# 引入原有的业务模块
from wechat_client import WeChatClient, WeChatAPIError, WeChatIPWhitelistError
from renderer import MarkdownRenderer

# 初始化 Flask
# 挂载相对于当前文件的 ui/static 和 ui/templates 目录
current_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_url_path="/ui/static",
    static_folder=os.path.join(current_dir, "ui", "static"),
    template_folder=os.path.join(current_dir, "ui", "templates")
)

# 禁用 Werkzeug 默认的日志，使用自定义日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WORKSPACE_DIR = os.path.abspath(current_dir)
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "config.yaml")

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
    """扫描工作区中的 Markdown 文件和图片文件，排除不必要目录"""
    md_files = []
    img_files = []
    
    exclude_dirs = {'.git', 'venv', '__pycache__', '.agents', '.gemini', 'styles'}
    exclude_files = {'requirements.txt', 'commit_msg.txt'}
    
    for root, dirs, files in os.walk(WORKSPACE_DIR):
        # 排除特定目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file in exclude_files:
                continue
                
            rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
            # 使用正斜杠统一格式
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

@app.route("/api/files", methods=["GET"])
def api_get_files():
    """获取工作区文件列表"""
    try:
        files = scan_workspace_files()
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/preview", methods=["POST"])
def api_post_preview():
    """本地预览排版编译"""
    data = request.json or {}
    md_path_input = data.get("md_path", "").strip()
    pygments_style = data.get("pygments_style", "monokai")
    
    if not md_path_input:
        return jsonify({"success": False, "message": "请选择或输入 Markdown 文件路径"}), 400
        
    # 解析为绝对路径
    abs_md_path = os.path.abspath(os.path.join(WORKSPACE_DIR, md_path_input))
    if not os.path.exists(abs_md_path):
        return jsonify({"success": False, "message": f"未找到 Markdown 文件: {md_path_input}"}), 404
        
    try:
        # Mock 客户端用于本地预览，无需真实 API Key
        class MockWeChatClient:
            def upload_body_image(self, local_path):
                # 返回本地相对路径，以便前端可以通过后端静态路由直接加载并显示图片！
                filename = os.path.basename(local_path)
                # 微信 CDN Mock 地址，这里为了本地能在预览框里显示出图片，我们返回服务器静态资源路由
                rel_img_path = os.path.relpath(local_path, WORKSPACE_DIR).replace("\\", "/")
                return f"/api/local-image/{rel_img_path}"
                
        renderer = MarkdownRenderer(pygments_style=pygments_style)
        html_content = renderer.render(abs_md_path, MockWeChatClient())
        
        return jsonify({"success": True, "html": html_content})
    except Exception as e:
        logger.error(f"本地编译渲染失败: {e}")
        return jsonify({"success": False, "message": f"排版编译失败: {str(e)}"}), 500

@app.route("/api/local-image/<path:filepath>")
def serve_local_image(filepath):
    """为预览提供本地图片服务，防止图片跨域或无法加载"""
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
    pygments_style = data.get("pygments_style", "monokai")
    content_source_url = data.get("content_source_url", "").strip()
    
    if not md_path_input or not cover_path_input:
        return jsonify({"success": False, "message": "Markdown 文件路径和封面图路径均不能为空"}), 400
        
    abs_md_path = os.path.abspath(os.path.join(WORKSPACE_DIR, md_path_input))
    abs_cover_path = os.path.abspath(os.path.join(WORKSPACE_DIR, cover_path_input))
    
    if not os.path.exists(abs_md_path):
        return jsonify({"success": False, "message": f"未找到 Markdown 文件: {md_path_input}"}), 404
    if not os.path.exists(abs_cover_path):
        return jsonify({"success": False, "message": f"未找到封面图片文件: {cover_path_input}"}), 404
        
    # 读取配置
    config = get_config()
    wechat_conf = config.get("wechat", {})
    defaults_conf = config.get("draft_defaults", {})
    
    appid = wechat_conf.get("appid")
    secret = wechat_conf.get("secret")
    
    if not appid or not secret or appid == "YOUR_APPID" or secret == "YOUR_APPSECRET":
        return jsonify({"success": False, "message": "未配置有效的公众号 AppID 或 AppSecret，请先在配置面板中填写"}), 400
        
    try:
        # 1. 初始化客户端
        client = WeChatClient(appid=appid, secret=secret)
        
        # 2. 确定文章标题
        title = title_input
        if not title:
            # 自动提取标题
            from main import extract_title_from_md
            title = extract_title_from_md(abs_md_path)
            
        # 3. 确定作者
        author = author_input or defaults_conf.get("author", "")
        
        # 4. 上传封面图片
        cover_media_id = client.upload_cover_image(abs_cover_path)
        
        # 5. 渲染 HTML 并上传/替换正文图片
        renderer = MarkdownRenderer(pygments_style=pygments_style)
        html_content = renderer.render(abs_md_path, client)
        
        # 6. 处理摘要
        digest = digest_input
        if not digest:
            digest = defaults_conf.get("digest")
            if not digest:
                from main import extract_digest_from_html
                digest = extract_digest_from_html(html_content)
                
        # 再次进行摘要字节截断，确保 120 字节限额
        if digest:
            encoded_digest = digest.encode('utf-8')
            if len(encoded_digest) > 120:
                digest = encoded_digest[:117].decode('utf-8', errors='ignore') + "..."
                
        # 7. 提交微信草稿箱
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
        # 捕获 IP 白名单错误，把定制的中文提示发给前端
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
        # 延迟打开浏览器，确保 Flask 已经启动
        import threading
        def open_url():
            import time
            time.sleep(1.0)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=open_url, daemon=True).start()
        
    logger.info(f"正在启动本地 Web 服务，访问地址: http://127.0.0.1:{port}")
    # 允许局域网访问，方便其他设备测试
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    start_server()
