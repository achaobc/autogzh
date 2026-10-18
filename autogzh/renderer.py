import os
import re
import yaml
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import markdown
from pygments.formatters import HtmlFormatter
from premailer import transform
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

def parse_markdown_frontmatter(md_content):
    """
    解析 Markdown 开头的 YAML Frontmatter 元数据
    返回 (frontmatter_dict, clean_markdown_body)
    """
    if not md_content:
        return {}, ""
        
    # 检测是否以 --- 开头
    if md_content.startswith("---"):
        parts = md_content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].lstrip("\r\n")
            try:
                data = yaml.safe_load(fm_text)
                if isinstance(data, dict):
                    return data, body
            except Exception as e:
                logger.warning(f"解析 YAML Frontmatter 失败: {e}")
                
    return {}, md_content

def extract_frontmatter_from_file(md_path):
    """从本地 Markdown 文件中提取 Frontmatter 元数据和纯正文"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        return parse_markdown_frontmatter(content)
    except Exception as e:
        logger.warning(f"读取 Markdown 文件解析 Frontmatter 失败: {e}")
        return {}, ""

def extract_title_from_md(md_path):
    """尝试从 Markdown 内容中提取标题，优先读取 Frontmatter，其次提取第一个一级标题"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        frontmatter, body = parse_markdown_frontmatter(content)
        if frontmatter.get("title"):
            return str(frontmatter["title"]).strip()

        for line in body.splitlines():
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
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
        # 移除代码块与文末脚注，避免影响摘要观感
        for pre in soup.find_all("pre"):
            pre.decompose()
        for code in soup.find_all("code"):
            code.decompose()
        for fn in soup.find_all("div", class_="footnotes-box"):
            fn.decompose()
            
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
    """Markdown 解析、样式行内化、外链转脚注、以及本地图片并发上传与替换服务"""
    
    def __init__(self, css_path=None, pygments_style="monokai", enable_footnotes=True):
        """
        :param css_path: 外部样式表路径，或内置主题名称 (default, tech, minimal, warm)
        :param pygments_style: Pygments 代码高亮主题名称 (如 monokai, default, github)
        :param enable_footnotes: 是否将外部链接自动转换为文末脚注 (微信正文规范)
        """
        self.pygments_style = pygments_style
        self.enable_footnotes = enable_footnotes
        self.css_path = self._resolve_css_path(css_path)

    @staticmethod
    def _resolve_css_path(css_input):
        """解析样式表路径，支持主题别名或文件相对/绝对路径"""
        if not css_input:
            return os.path.join(PROJECT_ROOT, "styles", "default.css")
            
        # 1. 优先检查 styles/ 下的内置主题名 (如 default, tech, minimal, warm)
        theme_candidate = os.path.join(PROJECT_ROOT, "styles", f"{css_input}.css" if not css_input.endswith(".css") else css_input)
        if os.path.exists(theme_candidate):
            return theme_candidate
            
        # 2. 检查传入的实际路径
        custom_candidate = css_input if os.path.isabs(css_input) else os.path.join(PROJECT_ROOT, css_input)
        if os.path.exists(custom_candidate):
            return custom_candidate
            
        logger.warning(f"指定的样式表 {css_input} 不存在，将自动使用默认 default.css")
        return os.path.join(PROJECT_ROOT, "styles", "default.css")

    def _load_css(self):
        """读取 CSS 文件，并追加 Pygments 生成的高亮样式"""
        css_content = ""
        if os.path.exists(self.css_path):
            try:
                with open(self.css_path, "r", encoding="utf-8") as f:
                    css_content = f.read()
                logger.info(f"成功加载排版样式表: {os.path.basename(self.css_path)}")
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

    @staticmethod
    def process_links_to_footnotes(container_soup):
        """
        将正文容器中的外部超链接自动转换为文末参考资料脚注
        微信普通公众号正文无法直接点击外部超链接，转换为脚注为业内最佳实践
        """
        links = container_soup.find_all("a")
        footnotes = []
        index = 1
        
        for a in links:
            href = a.get("href", "").strip()
            # 过滤内部锚点、javascript伪链接与邮箱链接
            if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
                
            link_text = a.get_text().strip() or href
            footnotes.append((index, link_text, href))
            
            # 创建上标标记 <sup>[1]</sup>
            sup = container_soup.new_tag("sup")
            sup["style"] = "color: inherit; opacity: 0.85; font-weight: bold; font-size: 0.72em; margin-left: 2px; vertical-align: super;"
            sup.string = f"[{index}]"
            a.insert_after(sup)
            
            # 增强链接的辨识度样式
            existing_style = a.get("style", "")
            a["style"] = f"{existing_style}; text-decoration: none; border-bottom: 1px dashed currentColor;".strip("; ")
            index += 1
            
        if footnotes:
            footnotes_box = container_soup.new_tag("div")
            footnotes_box["class"] = "footnotes-box"
            footnotes_box["style"] = "margin-top: 2.5em; padding-top: 1.2em; border-top: 1px dashed #cbd5e1; font-size: 0.85em; color: #64748b;"
            
            heading = container_soup.new_tag("h4")
            heading["style"] = "margin: 0 0 0.8em 0; font-size: 1.05em; color: #334155; font-weight: bold;"
            heading.string = "引用链接"
            footnotes_box.append(heading)
            
            ul = container_soup.new_tag("ul")
            ul["style"] = "list-style: none; padding-left: 0; margin: 0;"
            
            for idx, text, href in footnotes:
                li = container_soup.new_tag("li")
                li["style"] = "margin: 0.4em 0; line-height: 1.6; word-break: break-all;"
                
                label_span = container_soup.new_tag("span")
                label_span["style"] = "font-weight: 500; color: #475569;"
                label_span.string = f"[{idx}] {text}: "
                li.append(label_span)
                
                url_span = container_soup.new_tag("span")
                url_span["style"] = "opacity: 0.9;"
                url_span.string = href
                li.append(url_span)
                
                ul.append(li)
                
            footnotes_box.append(ul)
            container_soup.append(footnotes_box)
            logger.info(f"已自动将正文 {len(footnotes)} 个外部超链接转换为文末参考链接脚注")

    def render(self, md_path, client):
        """
        渲染主流程：
        1. 读取并解析 Markdown (自动识别 Frontmatter)
        2. Markdown 转换为 HTML
        3. 应用 CSS 样式，并将其行内化
        4. 解析外部链接转为文末脚注
        5. 并发解析与上传本地图片，并替换为微信 CDN URL
        """
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"未找到 Markdown 文件: {md_path}")

        md_dir = os.path.dirname(os.path.abspath(md_path))
        
        # 1. 读取 Markdown 文件内容并提取 Frontmatter
        with open(md_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        frontmatter, md_content = parse_markdown_frontmatter(raw_content)

        # 检查 frontmatter 中是否配置了脚注开关
        if "enable_footnotes" in frontmatter and isinstance(frontmatter["enable_footnotes"], bool):
            self.enable_footnotes = frontmatter["enable_footnotes"]

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

        # 5. 用 BeautifulSoup 解析
        soup = BeautifulSoup(inlined_html, "html.parser")
        
        content_div = soup.find("div", class_="markdown-body")
        if not content_div:
            content_div = soup.body if soup.body else soup

        # 6. 外链转文末脚注
        if self.enable_footnotes:
            self.process_links_to_footnotes(content_div)
            
        # 7. 处理正文图片：并发上传并替换为微信 CDN URL
        images = content_div.find_all("img")
        logger.info(f"解析到正文共包含 {len(images)} 张图片")
        
        img_tasks = []
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
                img_tasks.append((img, local_img_path, src))
            else:
                logger.info(f"外部图片或在线链接，保持原样: {src}")

        if img_tasks:
            logger.info(f"开始处理 {len(img_tasks)} 张本地正文图片上传与 CDN 替换...")
            def _upload_worker(task):
                img_tag, local_path, original_src = task
                cdn_url = client.upload_body_image(local_path)
                return (img_tag, cdn_url)

            max_workers = min(len(img_tasks), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(_upload_worker, img_tasks))
                for img_tag, cdn_url in results:
                    img_tag["src"] = cdn_url
                    if img_tag.get("style"):
                        style_str = img_tag["style"]
                        if "max-width" not in style_str:
                            img_tag["style"] = style_str + "; max-width: 100%; display: block; margin: 1.8em auto;"
                    else:
                        img_tag["style"] = "max-width: 100%; display: block; margin: 1.8em auto; border-radius: 8px;"

        final_html = str(content_div)
        final_html = re.sub(r'<!--.*?-->', '', final_html, flags=re.DOTALL)
        
        logger.info("Markdown 解析与样式处理完毕。")
        return final_html
