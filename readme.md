# WeChat Markdown Sync Tool (微信公众号 Markdown 自动排版与草稿同步工具)

本项目是一个专为微信公众号创作者设计的 Python 自动化排版与草稿同步工具。支持 **本地命令行（CLI）** 与 **图形化网页（Web UI）** 双模运行。

它可以将本地编写的 Markdown 文章自动解析为 HTML，将自定义的 CSS 样式 100% 行内化（Inlining）注入标签，自动上传并替换文中的本地图片至微信 CDN，并一键同步到微信公众号的草稿箱。

---

## 🌟 核心特性

1. **高颜值 Web 图形化操作台 (NEW)**
   * 提供精致的深黛青（Elegant Teal）现代暗黑主题界面。
   * 支持本地工作区 Markdown 与图片文件的**智能扫描下拉选取**，告别繁琐的文件路径输入。
   * 采用 **IFrame 双栏隔离**设计，提供 100% 还原手机端微信排版效果的实时渲染预览。
   * 提供无刷新配置管理器，可直接在页面上编辑并保存 AppID 与 Secret。
   * 搭载动态控制台日志，同步进度与接口异常一目了然。
2. **Access Token 智能缓存与自动刷新**
   * 本地维护 `.wechat_token.json` 缓存，到期自动刷新，避免触发微信 API 频次限制。
3. **CSS 样式 100% 自动行内化 (Critical)**
   * 微信编辑器会过滤所有 `<style>` 标签及外部/页头样式。
   * 工具基于 `premailer` 与 `beautifulsoup4`，将样式表定义的 CSS 规则深度渲染并注入到 HTML 中每一个标签的 `style` 属性中，确保排版样式 100% 还原。
4. **服务端代码块语法高亮**
   * 内建 **Pygments** 高亮引擎，支持 `monokai`, `github`, `dracula` 等多种高亮配色，语法配色同样会被完全注入为行内 style 属性。
5. **媒体资源全自动托管替换**
   * 自动解析 Markdown 中的本地图片路径。
   * 自动调用微信接口上传封面图获取 `thumb_media_id`，上传正文插图获取微信 CDN `url`，并自动完成 HTML 内图片路径替换。
6. **智能图文要素提取与安全截断**
   * **标题提取**：未指定标题时，智能提取 Markdown 文件的第一个 `# H1`，若无则使用文件名兜底。
   * **摘要安全截断**：未提供摘要时自动提取正文，并针对微信草稿箱严格的 **120字节（约40个汉字）** 限制进行按字节的安全截断，彻底规避微信 API `45004` (description size out of limit) 报错。
7. **健壮的错误捕获与 IP 加白指引**
   * 特别捕获微信经典的 `40164` (IP 未加白名单) 报错，自动获取您当前的公网请求 IP，并给出详细的公众号后台配置引导。

---

## 📂 项目结构

```text
auto-gzh/
├── config.yaml            # 本地配置文件（存放凭证，已被 git 忽略）
├── config.yaml.example    # 配置文件模板
├── requirements.txt       # 依赖文件
├── wechat_client.py       # 微信公众平台 API 客户端封装
├── renderer.py            # Markdown 转换、CSS 行内化与图片处理服务
├── web_server.py          # 轻量级 Flask 网页 UI 后端服务
├── ui/                    # 网页 UI 前端资源目录
│   ├── templates/
│   │   └── index.html     # 图形化界面主 HTML
│   └── static/
│       ├── style.css      # 主题 CSS 样式
│       └── app.js         # 前端异步交互 JS 脚本
├── styles/
│   └── default.css        # 微信专用的精美 Elegant Teal 排版样式表
├── test.md                # 本地排版测试 Markdown 样本
├── test_render.py         # 本地免 API 密钥排版渲染测试脚本
└── main.py                # 项目启动主入口
```

---

## 🛠️ 快速开始

### 1. 安装依赖环境
本项目推荐使用 Python 3.8+。在项目根目录下执行以下命令安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 配置微信公众平台凭证
您可以选择直接在 Web UI 界面中填写，也可以手动配置：
1. 复制模版文件 `config.yaml.example` 并命名为 `config.yaml`。
2. 用编辑器打开 `config.yaml`，填入您的微信公众号 AppID 和 AppSecret：
   ```yaml
   wechat:
     appid: "你的微信公众号AppID"
     secret: "你的微信公众号AppSecret"
   ```
3. **关键步骤**：首次运行时，若微信返回 `40164` 错误，请根据命令行（或 Web UI 终端日志）输出中的公网 IP，登录「微信公众平台 -> 开发 -> 基本配置 -> IP白名单」，将该 IP 添加进去。

### 3. 运行项目

#### 【方式 A】使用图形化网页界面 (推荐)
直接运行以下命令：
```bash
python main.py --ui
```
系统会拉起本地 Web 服务，并在 1 秒后**自动用您的默认浏览器打开** `http://127.0.0.1:5000` 进入操作台。

#### 【方式 B】使用命令行模式
运行以下命令直接执行同步：
```bash
python main.py --md test.md --cover cover.png
```
输出成功后，您可直接前往「微信公众平台 -> 内容分析 -> 草稿箱」预览或群发。

---

## ⚙️ 进阶参数

支持通过命令行参数对发布流程进行微调：

| 选项 (长/短) | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--ui` | **启动图形化 Web UI 界面模式**（此模式下无需传 md 与 cover 参数） | - |
| `-m, --md` | 本地 Markdown 文件路径 (命令行模式下必填) | - |
| `-c, --cover` | 封面图片路径 (本地图片，命令行模式下必填) | - |
| `-t, --title` | 图文标题 | 自动提取 Markdown 中第一个 `# H1`，或使用文件名 |
| `-a, --author` | 作者 | 默认读取 `config.yaml` 中的默认作者 |
| `-d, --digest` | 文章摘要 | 默认从正文截取前 120 字节（规避 45004 报错） |
| `--config` | 配置文件路径 | `config.yaml` |
| `--style` | 自定义排版样式表路径 | `styles/default.css` |
| `--pygments-style` | 代码块语法高亮主题 | `monokai` (可选 `github`, `dracula`, `default` 等) |
| `--content-source-url` | 原文链接（即“阅读原文”超链接） | 无 |

---

## 🧪 本地效果测试

在正式向微信平台请求接口前，如果您想在命令行环境下单独生成 HTML 确认排版样式：
```bash
python test_render.py
```
这将在本地生成一个 **`output_test.html`**。您也可以指定渲染其他文件，如 `python test_render.py aaa.md`。

---

## 📝 许可证

本项目采用 [MIT License](LICENSE) 授权许可。
