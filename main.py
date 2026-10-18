import os
import sys
import yaml
import argparse
import logging

from autogzh.client import WeChatClient, WeChatAPIError
from autogzh.renderer import MarkdownRenderer, extract_title_from_md, extract_digest_from_html, extract_frontmatter_from_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def load_config(config_path):
    """加载配置文件"""
    abs_config_path = config_path if os.path.isabs(config_path) else os.path.join(PROJECT_ROOT, config_path)
    if not os.path.exists(abs_config_path):
        example_path = os.path.join(PROJECT_ROOT, "config.yaml.example")
        print(f"\n[ERROR] 未找到配置文件: {abs_config_path}")
        if os.path.exists(example_path):
            print(f"请复制模板文件 {example_path} 并命名为 config.yaml，然后填写微信 AppID 和 AppSecret。")
        else:
            print(f"请在项目根目录创建一个 config.yaml 配置文件。")
        sys.exit(1)

    try:
        with open(abs_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        logger.error(f"解析配置文件失败: {e}")
        sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Markdown 自动排版并同步至微信公众号草稿箱工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-m", "--md", help="Markdown 文件路径 (命令行模式下必填)")
    parser.add_argument("-c", "--cover", help="封面图片路径 (本地图片，命令行模式下必填)")
    parser.add_argument("-t", "--title", help="图文标题 (如果不指定，将自动提取 Markdown 中的第一个 H1，或使用文件名)")
    parser.add_argument("-a", "--author", help="作者 (如果不指定，使用 config.yaml 中的默认配置)")
    parser.add_argument("-d", "--digest", help="摘要 (如果不指定，使用 config.yaml 中的配置，或从文章中提取前 120 字节)")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径 (默认: config.yaml)")
    parser.add_argument("--style", default="default", help="排版样式表主题 (可选 default, tech, minimal, warm 或自定义 CSS 路径)")
    parser.add_argument("--pygments-style", default="monokai", help="代码块高亮主题 (默认: monokai)")
    parser.add_argument("--no-footnotes", action="store_true", help="禁用外链自动转换为文末脚注功能")
    parser.add_argument("--content-source-url", help="原文链接 (可选，即阅读原文链接)")
    parser.add_argument("--ui", action="store_true", help="启动图形化 Web UI 界面模式 (默认浏览器中打开)")
    parser.add_argument("--gui", action="store_true", help="启动原生图形化 GUI 桌面应用窗口模式")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 如果指定了 --gui，或者未传任何命令行参数 (如直接双击 EXE 或直接 python main.py)
    if args.gui or len(sys.argv) == 1:
        from autogzh.gui import start_gui
        start_gui()
        sys.exit(0)

    # 如果指定了 --ui，则启动 Web 界面
    if args.ui:
        from autogzh.server import start_server
        start_server()
        sys.exit(0)
        
    # 命令行模式：解析 Frontmatter 辅助补全缺省要素
    frontmatter = {}
    if args.md and os.path.exists(args.md):
        frontmatter, _ = extract_frontmatter_from_file(args.md)

    cover_path = args.cover or frontmatter.get("cover")
    if not args.md or not cover_path:
        print("\n[ERROR] 命令行模式下，--md (-m) 和 --cover (-c) 为必填参数（或在 Markdown Frontmatter 中定义 cover）。")
        print("👉 您也可以使用 `python main.py --ui` 启动浏览器控制台，或 `python main.py --gui` 启动桌面应用。")
        sys.exit(1)
        
    # 1. 加载配置
    config = load_config(args.config)
    wechat_conf = config.get("wechat", {})
    defaults_conf = config.get("draft_defaults", {})
    
    appid = wechat_conf.get("appid")
    secret = wechat_conf.get("secret")
    
    if not appid or appid == "YOUR_APPID" or not secret or secret == "YOUR_APPSECRET":
        print("\n[ERROR] 未配置有效的 AppID 或 AppSecret！")
        print(f"请检查配置文件 {args.config}，填写您微信公众号的凭证信息。")
        sys.exit(1)
        
    # 2. 初始化微信客户端
    try:
        client = WeChatClient(appid=appid, secret=secret)
        client.get_access_token()
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"初始化微信客户端或获取 Token 发生异常: {e}")
        sys.exit(1)

    # 3. 处理图文要素：标题、作者、样式
    title = args.title or frontmatter.get("title")
    if not title:
        title = extract_title_from_md(args.md)
        logger.info(f"未指定标题，自动从 Markdown 提取标题: 「{title}」")
        
    author = args.author or frontmatter.get("author") or defaults_conf.get("author", "")
    need_open_comment = defaults_conf.get("need_open_comment", 0)
    only_less_tags = defaults_conf.get("only_less_tags", 0)
    
    style = args.style if args.style != "default" else (frontmatter.get("style") or "default")
    pygments_style = args.pygments_style if args.pygments_style != "monokai" else (frontmatter.get("pygments_style") or "monokai")
    enable_footnotes = not args.no_footnotes
    if "enable_footnotes" in frontmatter and isinstance(frontmatter["enable_footnotes"], bool):
        enable_footnotes = frontmatter["enable_footnotes"]
    content_source_url = args.content_source_url or frontmatter.get("content_source_url")

    # 4. 上传封面图片，获取 media_id
    try:
        cover_media_id = client.upload_cover_image(cover_path)
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"上传封面图片失败: {e}")
        sys.exit(1)

    # 5. 渲染 Markdown 并处理正文图片 (支持 MD5 秒传与并发上传)
    try:
        renderer = MarkdownRenderer(
            css_path=style, 
            pygments_style=pygments_style,
            enable_footnotes=enable_footnotes
        )
        html_content = renderer.render(args.md, client)
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"处理 HTML 渲染与正文图片上传发生异常: {e}")
        sys.exit(1)

    # 6. 处理摘要
    digest = args.digest or frontmatter.get("digest")
    if not digest:
        digest = defaults_conf.get("digest")
        if not digest:
            digest = extract_digest_from_html(html_content)
            logger.info("未提供摘要，已根据文章正文自动生成。")
            
    # 强制进行字节长度截取，确保最终发送给微信的 digest 绝不超过 120 字节，规避 45004 错误
    if digest:
        encoded_digest = digest.encode('utf-8')
        if len(encoded_digest) > 120:
            digest = encoded_digest[:117].decode('utf-8', errors='ignore') + "..."
            logger.info("摘要长度超过 120 字节，已自动截断以适配微信限制。")
            
    logger.info(f"文章要素摘要:")
    logger.info(f"  - 标题: {title}")
    logger.info(f"  - 作者: {author or '未设置'}")
    logger.info(f"  - 主题: {style} (代码高亮: {pygments_style})")
    logger.info(f"  - 摘要: {digest[:40]}...")

    # 7. 提交微信草稿箱
    try:
        draft_media_id = client.create_draft(
            title=title,
            content=html_content,
            thumb_media_id=cover_media_id,
            author=author,
            digest=digest,
            content_source_url=content_source_url,
            need_open_comment=need_open_comment,
            only_less_tags=only_less_tags
        )
        
        print("\n" + "=" * 60)
        print("微信图文草稿同步成功！")
        print("-" * 60)
        print(f"草稿 Media ID: {draft_media_id}")
        print("请前往「微信公众平台」->「内容分析/草稿箱」查看、预览或群发您的图文！")
        print("=" * 60 + "\n")
        
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"新建微信草稿箱任务失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
