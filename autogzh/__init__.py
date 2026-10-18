"""
AutoGZH: 微信公众号 Markdown 自动排版与草稿同步工具
"""

from .client import WeChatClient, WeChatAPIError, WeChatIPWhitelistError
from .renderer import MarkdownRenderer, extract_title_from_md, extract_digest_from_html

__version__ = "1.0.0"
__all__ = [
    "WeChatClient",
    "WeChatAPIError",
    "WeChatIPWhitelistError",
    "MarkdownRenderer",
    "extract_title_from_md",
    "extract_digest_from_html",
]
