import os
import sys

# 将项目根目录加入模块搜索路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from autogzh.renderer import MarkdownRenderer

class MockWeChatClient:
    """Mock 微信客户端，用于本地无 API Key 测试图片路径替换与渲染"""
    def upload_body_image(self, local_path):
        filename = os.path.basename(local_path)
        logger_mock_url = f"https://mmbiz.qpic.cn/mock_cdn/{filename}"
        print(f"  [MOCK 上传] 本地图片: {local_path} -> 微信 CDN: {logger_mock_url}")
        return logger_mock_url

def main():
    print("开始本地排版渲染测试...")
    
    theme = "default"
    if len(sys.argv) > 1:
        md_path = sys.argv[1]
    else:
        md_path = os.path.join(project_root, "articles", "drafts", "test.md")
        
    if len(sys.argv) > 2:
        theme = sys.argv[2]
        
    if not os.path.exists(md_path):
        print(f"错误: 未找到 Markdown 文件 {md_path}")
        sys.exit(1)
        
    # 根据输入文件名生成输出 HTML 文件名，保存到 articles/output/ 目录
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    output_dir = os.path.join(project_root, "articles", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_html_path = os.path.join(output_dir, f"output_{base_name}_{theme}.html")
    
    try:
        renderer = MarkdownRenderer(css_path=theme, pygments_style="monokai")
        mock_client = MockWeChatClient()
        
        final_html = renderer.render(md_path, mock_client)
        
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(final_html)
            
        print(f"\n渲染成功！输出文件已保存至: {os.path.abspath(output_html_path)}")
        print("请用浏览器打开该文件，检查排版效果和行内样式是否正确注入。")
        
    except Exception as e:
        print(f"渲染测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
