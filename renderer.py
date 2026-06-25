import os
import re
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import markdown
from pygments.formatters import HtmlFormatter
from premailer import transform

logger = logging.getLogger(__name__)

class MarkdownRenderer:
    """Markdown 解析、样式行内化、以及本地图片提取与替换服务"""
    
    def __init__(self, css_path=None, pygments_style="monokai"):
        """
        :param css_path: 外部样式表路径，若为 None 则查找当前目录 styles/default.css
        :param pygments_style: Pygments 代码高亮主题名称 (如 monokai, default, github)
        """
        self.pygments_style = pygments_style
        
        # 查找默认 CSS 文件路径
        if css_path is None:
            # 默认为当前脚本同级目录下的 styles/default.css
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.css_path = os.path.join(current_dir, "styles", "default.css")
        else:
            self.css_path = css_path

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
            # 生成适用于 .codehilite 容器的代码样式
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
        # 排除网络图片及 Base64 编码图片
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
        
        :param md_path: Markdown 文件的本地路径
        :param client: WeChatClient 实例
        :return: 适用于微信草稿箱的 HTML 字符串 (行内样式)
        """
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"未找到 Markdown 文件: {md_path}")

        md_dir = os.path.dirname(os.path.abspath(md_path))
        
        # 1. 读取 Markdown 文件内容
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 2. Markdown 转换为 HTML
        # 启用 fenced_code (代码块), tables (表格), toc (目录), codehilite (代码高亮) 扩展
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
            # cssutils_logging_level 设置为 logging.ERROR 避免打印大量不必要的 CSS 语法警告
            inlined_html = transform(
                full_html, 
                include_star_selectors=True,
                cssutils_logging_level=logging.ERROR
            )
        except Exception as e:
            raise RuntimeError(f"CSS 行内化失败: {e}")

        # 5. 用 BeautifulSoup 解析，处理并上传本地图片，提取最终所需的 body 内容
        soup = BeautifulSoup(inlined_html, "html.parser")
        
        # 微信公众号只接收 body 内的实际内容
        content_div = soup.find("div", class_="markdown-body")
        if not content_div:
            # 容错：如果找不到 div，取整个 body 内部
            content_div = soup.body if soup.body else soup
            
        # 查找所有图片标签
        images = content_div.find_all("img")
        logger.info(f"解析到正文共包含 {len(images)} 张图片")
        
        for img in images:
            src = img.get("src")
            if self.is_local_image(src):
                # 拼接本地图片的绝对路径
                # 支持相对路径如 images/test.png -> /path/to/markdown/images/test.png
                local_img_path = os.path.normpath(os.path.join(md_dir, src))
                
                if not os.path.exists(local_img_path):
                    # 如果找不到图片，打印警告，且为了草稿健壮性可以选择抛出异常或跳过
                    # 这里抛出异常，防止用户排版完发布才发现图丢了
                    raise FileNotFoundError(
                        f"正文中的本地图片未找到: '{src}' (解析为: {local_img_path})，请检查路径是否正确。"
                    )
                
                try:
                    # 上传至微信服务器获取 CDN URL
                    cdn_url = client.upload_body_image(local_img_path)
                    img["src"] = cdn_url
                    
                    # 额外处理微信图片的展示属性
                    # 微信建议图片宽度自适应，去除可能硬编码的 width/height 样式，以确保移动端排版美观
                    if img.get("style"):
                        # 如果 style 里有 width/height，建议保留 max-width: 100% 即可
                        style_str = img["style"]
                        # 确保有 max-width: 100%; display: block; margin: 1.8em auto;
                        if "max-width" not in style_str:
                            img["style"] = style_str + "; max-width: 100%; display: block; margin: 1.8em auto;"
                    else:
                        img["style"] = "max-width: 100%; display: block; margin: 1.8em auto; border-radius: 8px;"
                        
                except Exception as e:
                    raise RuntimeError(f"上传并替换图片 '{src}' 时发生错误: {e}")
            else:
                logger.info(f"外部图片或在线链接，保持原样: {src}")

        # 微信编辑器中为了兼容和防过滤，一般最好把 div.markdown-body 本身的样式也内联
        # 我们返回 div 容器的外部 HTML (包含包裹它的 div 标签及其 style 属性)
        # 微信公众号后台不支持完整的 html/head 结构，必须是干净的 html 片段
        final_html = str(content_div)
        
        # 微信公众号平台不支持 HTML 注释，清除可能存在的注释
        final_html = re.sub(r'<!--.*?-->', '', final_html, flags=re.DOTALL)
        
        logger.info("Markdown 解析与样式处理完毕。")
        return final_html
