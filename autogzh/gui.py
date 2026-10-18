import os
import sys
import time
import socket
import threading
import logging

from .server import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

def find_free_port():
    """查找本地可用端口，优先尝试 5000"""
    for port in (5000, 5001, 5002, 5003, 5004, 5005):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_flask(port):
    """后台守护线程运行 Flask Web 服务"""
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

def start_gui(port=None):
    """启动独立 GUI 桌面窗口"""
    try:
        import webview
    except ImportError:
        logger.warning("未检测到 pywebview 依赖，正在自动降级使用浏览器 Web 界面模式...")
        from .server import start_server
        start_server(port=port or 5000, open_browser=True)
        return

    if port is None:
        port = find_free_port()

    logger.info(f"正在后台启动 Web 服务引擎，分配端口: {port}")
    flask_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    flask_thread.start()

    time.sleep(0.5)

    target_url = f"http://127.0.0.1:{port}"
    
    # 查找 App 图标路径
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', PROJECT_ROOT)
    else:
        base_dir = PROJECT_ROOT
        
    icon_path = os.path.join(base_dir, "assets", "app.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "app.ico")
        if not os.path.exists(icon_path):
            icon_path = None

    logger.info("正在拉起原生 GUI 桌面应用窗口...")
    window = webview.create_window(
        title="微信公众号 Markdown 自动排版与草稿同步工具 - AutoGZH",
        url=target_url,
        width=1280,
        height=820,
        min_size=(960, 640),
        resizable=True
    )

    webview.start(icon=icon_path)

if __name__ == "__main__":
    start_gui()
