import os
import re
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import markdown
from pygments.formatters import HtmlFormatter
from premailer import transform

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

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
        truncated_text = truncated_encoded.decode('utf-8', errors='ignore')
        return truncated_text + "..."
    except Exception as e:
        logger.warning(f"生成自动摘要失败: {e}")
        return "点击阅读全文"

class MarkdownRenderer:
    """Markdown 解析、样式行内化、以及本地图片提取与替换服务"""
    
    def __init__(self, css_path=None, pygments_style="monokai"):
        """
        :param css_path: 外部样式表路径，若为 None 则查找 styles/default.css
        :param pygments_style: Pygments 代码高亮主题名称 (如 monokai, default, github)
        """
        self.pygments_style = pygments_style
        
        if css_path is None:
            self.css_path = os.path.join(PROJECT_ROOT, "styles", "default.css")
        else:
            self.css_path = css_path if os.path.isabs(css_path) else os.path.join(PROJECT_ROOT, css_path)

    def _load_css(self):
        """读取 CSS 文件，并追加 Pygments 生成的高亮样式"""
        css_content = ""
        if os.path.exists(self.css_path):
            try:
                with open(self.css_path, "r", encoding="utf-8") as f:
                    css_content = f.read()
                logger.info(f"成功加载外部样式表: {self.css_path}")
            except Exception as e:
                logger.warning(f"读取外部样式表 {self.css_path} 失败: {e}，将仅使用代码高亮样式")
        else:
            logger.warning(f"未找到样式表文件: {self.css_path}，将仅使用代码高亮样式")

        # 生成 Pygments 代码高亮 CSS
        try:
            formatter = HtmlFormatter(style=self.pygments_style)
            pygments_css = formatter.get_style_defs(".codehilite")
            css_content += "\n/* Pygments Highlighting Style */\n" + pygments_css
            logger.info(f"生成 Pygments 代码高亮样式 (主题: {self.pygments_style})")
        except Exception as e:
            logger.warning(f"生成代码高亮样式失败: {e}")

        return css_content

    @staticmethod
    def is_local_image(src):
        """判断图片路径是否为本地路径"""
        if not src:
            return False
        parsed = urlparse(src)
        if parsed.scheme in ('http', 'https') or src.startswith('data:'):
            return False
        return True

    def render(self, md_path, client):
        """
        渲染主流程：
        1. 读取并解析 Markdown
        2. 应用 CSS 样式，并将其行内化
        3. 解析所有图片，如果是本地路径则上传至微信，并替换为微信 CDN URL
        """
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"未找到 Markdown 文件: {md_path}")

        md_dir = os.path.dirname(os.path.abspath(md_path))
        
        # 1. 读取 Markdown 文件内容
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 2. Markdown 转换为 HTML
        extensions = [
            'markdown.extensions.fenced_code',
            'markdown.extensions.tables',
            'markdown.extensions.toc',
            'markdown.extensions.codehilite'
        ]
        extension_configs = {
            'markdown.extensions.codehilite': {
                'css_class': 'codehilite',
                'guess_lang': False,
                'use_pygments': True
            }
        }
        
        logger.info("将 Markdown 转换为 HTML 结构...")
        body_html = markdown.markdown(
            md_content, 
            extensions=extensions, 
            extension_config=extension_configs
        )

        # 3. 构造完整 HTML 文件，注入 CSS，以方便 premailer 行内化
        css_content = self._load_css()
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
    {css_content}
    </style>
</head>
<body>
    <div class="markdown-body">
        {body_html}
    </div>
</body>
</html>"""

        # 4. 使用 premailer 将 CSS 样式属性注入到各标签中
        logger.info("正在执行 CSS 样式自动行内化 (Inlining)...")
        try:
            inlined_html = transform(
                full_html, 
                include_star_selectors=True,
                cssutils_logging_level=logging.ERROR
            )
        except Exception as e:
            raise RuntimeError(f"CSS 行内化失败: {e}")

        # 5. 用 BeautifulSoup 解析，处理并上传本地图片，提取最终所需的 body 内容
        soup = BeautifulSoup(inlined_html, "html.parser")
        
        content_div = soup.find("div", class_="markdown-body")
        if not content_div:
            content_div = soup.body if soup.body else soup
            
        images = content_div.find_all("img")
        logger.info(f"解析到正文共包含 {len(images)} 张图片")
        
        for img in images:
            src = img.get("src")
            if self.is_local_image(src):
                local_img_path = os.path.normpath(os.path.join(md_dir, src))
                
                # 若直接相对路径找不到，尝试在 assets/ 目录下查找
                if not os.path.exists(local_img_path):
                    alt_path = os.path.normpath(os.path.join(PROJECT_ROOT, "assets", src))
                    if os.path.exists(alt_path):
                        local_img_path = alt_path

                if not os.path.exists(local_img_path):
                    raise FileNotFoundError(
                        f"正文中的本地图片未找到: '{src}' (解析为: {local_img_path})，请检查路径是否正确。"
                    )
                
                try:
                    cdn_url = client.upload_body_image(local_img_path)
                    img["src"] = cdn_url
                    
                    if img.get("style"):
                        style_str = img["style"]
                        if "max-width" not in style_str:
                            img["style"] = style_str + "; max-width: 100%; display: block; margin: 1.8em auto;"
                    else:
                        img["style"] = "max-width: 100%; display: block; margin: 1.8em auto; border-radius: 8px;"
                        
                except Exception as e:
                    raise RuntimeError(f"上传并替换图片 '{src}' 时发生错误: {e}")
            else:
                logger.info(f"外部图片或在线链接，保持原样: {src}")

        final_html = str(content_div)
        final_html = re.sub(r'<!--.*?-->', '', final_html, flags=re.DOTALL)
        
        logger.info("Markdown 解析与样式处理完毕。")
        return final_html
