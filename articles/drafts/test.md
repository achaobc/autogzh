# 这是一篇用于测试微信同步的 Markdown 文章

这是一段普通的正文内容，用来测试段落的排版样式。微信编辑器会过滤所有的外联样式和 style 标签，所以我们的工具必须将所有的 CSS 样式渲染并**注入到每个标签的行内**。

## 1. 列表与字体样式测试

这里是无序列表：
- **粗体文本** 用来强调核心词汇。
- *斜体文本* 可以用于一些专有名词或翻译。
- `行内代码` 用于展示简短的命令或变量名，比如 `pip install requests`。

这里是有序列表：
1. 第一步：填写 `config.yaml` 配置文件中的 `appid` 和 `secret`。
2. 第二步：准备好你的本地文章 `test.md` 和一张封面图。
3. 第三步：运行同步工具，将文章一键上传至公众号。

---

## 2. 引用块与代码高亮测试

> 这是一个引用块（blockquote）。常用于引用名言、参考资料或者进行补充说明。它的左侧会有一条漂亮的灰色/青色竖线。

下面是 Python 代码块，我们会使用 **Pygments** 在服务端进行语法高亮，并通过 **Premailer** 将高亮样式完全注入到 HTML 中，这样即使在微信中也依然能保持极具美感的配色：

```python
import os
import requests

def hello_wechat(appid):
    """
    这是一个用来向微信打招呼的测试函数
    """
    print(f"Hello, WeChat! AppID is: {appid}")
    
    # 模拟一个简单的 API 调用
    url = f"https://api.weixin.qq.com/cgi-bin/token?appid={appid}"
    return url
```

---

## 3. 表格与图片测试

下面是一个排版整齐的表格：

| 功能模块 | 对应依赖库 | 作用说明 |
| :--- | :--- | :--- |
| Markdown 解析 | `markdown` | 将 Markdown 标记语言渲染为标准 HTML |
| 样式行内化 | `premailer` | 解析 CSS 规则并逐个注入到 HTML 标签的 style 属性 |
| 网页元素解析 | `beautifulsoup4` | 用于提取本地图片路径，进行 CDN 替换 |
| 网络请求 | `requests` | 负责与微信公众平台 API 进行安全通信 |

下面是图片排版测试。这是一张测试正文插图：

![测试正文插图](images/test_body.png)

以上就是全部的排版测试。请在转换后检查生成的 HTML 文件，验证其是否已 100% 转换为行内样式。
