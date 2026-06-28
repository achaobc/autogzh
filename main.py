import os
import sys
import yaml
import argparse
import logging
import re
from bs4 import BeautifulSoup

from wechat_client import WeChatClient, WeChatAPIError
from renderer import MarkdownRenderer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path):
    """加载配置文件"""
    if not os.path.exists(config_path):
        example_path = config_path + ".example" if not config_path.endswith(".example") else "config.yaml.example"
        print(f"\n[ERROR] 未找到配置文件: {config_path}")
        if os.path.exists(example_path):
            print(f"请复制模板文件 {example_path} 并命名为 {config_path}，然后填写微信 AppID 和 AppSecret。")
        else:
            print(f"请在当前目录创建一个 {config_path} 配置文件。")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        logger.error(f"解析配置文件失败: {e}")
        sys.exit(1)

def extract_title_from_md(md_path):
    """尝试从 Markdown 内容中提取第一个一级标题作为文章标题"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    # 过滤可能存在的一些 markdown 加粗等简单标记
                    title = re.sub(r'[*_`]', '', title)
                    return title
    except Exception as e:
        logger.warning(f"读取 Markdown 提取标题失败: {e}")
    
    # 兜底：使用文件名（去除扩展名）
    basename = os.path.basename(md_path)
    title, _ = os.path.splitext(basename)
    return title

def extract_digest_from_html(html_content, max_bytes=120):
    """从生成的 HTML 中剥离文本并按字节截取作为摘要，微信限制摘要最多 120 字节"""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # 移除代码块，避免代码混入摘要中影响观感
        for pre in soup.find_all("pre"):
            pre.decompose()
        for code in soup.find_all("code"):
            code.decompose()
            
        text = soup.get_text()
        # 清理连续空格、制表符和换行
        text = re.sub(r'\s+', ' ', text).strip()
        
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
            
        # 截断时留出 3 字节给省略号 "..."
        target_bytes = max_bytes - 3
        truncated_encoded = encoded[:target_bytes]
        # 避免截断多字节字符产生的 decode 错误
        truncated_text = truncated_encoded.decode('utf-8', errors='ignore')
        return truncated_text + "..."
    except Exception as e:
        logger.warning(f"生成自动摘要失败: {e}")
        return "点击阅读全文"

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
    parser.add_argument("--style", help="自定义 CSS 样式表路径 (默认使用 styles/default.css)")
    parser.add_argument("--pygments-style", default="monokai", help="代码块高亮主题 (默认: monokai)")
    parser.add_argument("--content-source-url", help="原文链接 (可选，即阅读原文链接)")
    parser.add_argument("--ui", action="store_true", help="启动图形化 Web UI 界面模式")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 如果指定了 --ui，则启动 Web 界面
    if args.ui:
        from web_server import start_server
        start_server()
        sys.exit(0)
        
    # 命令行模式，校验必填参数
    if not args.md or not args.cover:
        print("\n[ERROR] 命令行模式下，--md (-m) 和 --cover (-c) 为必填参数。")
        print("👉 您也可以使用 `python main.py --ui` 启动图形化界面。")
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
        # 触发一次获取 Token，提前校验连接和白名单
        client.get_access_token()
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"初始化微信客户端或获取 Token 发生异常: {e}")
        sys.exit(1)

    # 3. 处理图文要素：标题、作者、摘要
    title = args.title
    if not title:
        title = extract_title_from_md(args.md)
        logger.info(f"未指定标题，自动从 Markdown 提取标题: 「{title}」")
        
    author = args.author or defaults_conf.get("author", "")
    show_cover_pic = defaults_conf.get("show_cover_pic", 1)
    need_open_comment = defaults_conf.get("need_open_comment", 0)
    only_less_tags = defaults_conf.get("only_less_tags", 0)
    
    # 4. 上传封面图片，获取 media_id
    try:
        cover_media_id = client.upload_cover_image(args.cover)
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"上传封面图片失败: {e}")
        sys.exit(1)

    # 5. 渲染 Markdown 并处理正文图片
    try:
        renderer = MarkdownRenderer(css_path=args.style, pygments_style=args.pygments_style)
        html_content = renderer.render(args.md, client)
    except WeChatAPIError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"处理 HTML 渲染与正文图片上传发生异常: {e}")
        sys.exit(1)

    # 6. 处理摘要
    digest = args.digest
    if not digest:
        # 如果命令行未提供，优先检查默认配置
        digest = defaults_conf.get("digest")
        if not digest:
            # 自动生成摘要
            digest = extract_digest_from_html(html_content)
            logger.info("未提供摘要，已根据文章正文自动生成。")
            
    # 强制进行字节长度截取，确保最终发送给微信的 digest 绝不超过 120 字节，规避 45004 错误
    if digest:
        encoded_digest = digest.encode('utf-8')
        if len(encoded_digest) > 120:
            # 扣除省略号的 3 字节后截断
            digest = encoded_digest[:117].decode('utf-8', errors='ignore') + "..."
            logger.info("摘要长度超过 120 字节，已自动截断以适配微信限制。")
            
    logger.info(f"文章要素摘要:")
    logger.info(f"  - 标题: {title}")
    logger.info(f"  - 作者: {author or '未设置'}")
    logger.info(f"  - 摘要: {digest[:40]}...")

    # 7. 提交微信草稿箱
    try:
        draft_media_id = client.create_draft(
            title=title,
            content=html_content,
            thumb_media_id=cover_media_id,
            author=author,
            digest=digest,
            content_source_url=args.content_source_url,
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
