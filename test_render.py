import os
import sys
from renderer import MarkdownRenderer

class MockWeChatClient:
    """Mock 微信客户端，用于本地无 API Key 测试图片路径替换与渲染"""
    def upload_body_image(self, local_path):
        filename = os.path.basename(local_path)
        logger_mock_url = f"https://mmbiz.qpic.cn/mock_cdn/{filename}"
        print(f"  [MOCK 上传] 本地图片: {local_path} -> 微信 CDN: {logger_mock_url}")
        return logger_mock_url

def main():
    print("开始本地排版渲染测试...")
    
    # 优先从命令行参数读取 Markdown 路径，未传入则默认使用 test.md
    if len(sys.argv) > 1:
        md_path = sys.argv[1]
    else:
        md_path = "test.md"
        
    # 根据输入文件名生成输出 HTML 文件名
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    output_html_path = f"output_{base_name}.html"
    
    if not os.path.exists(md_path):
        print(f"错误: 未找到 Markdown 文件 {md_path}")
        sys.exit(1)
        
    try:
        # 使用 Monokai 代码高亮，默认 CSS 样式
        renderer = MarkdownRenderer(pygments_style="monokai")
        mock_client = MockWeChatClient()
        
        # 执行渲染
        final_html = renderer.render(md_path, mock_client)
        
        # 将结果写入本地 HTML 进行检查
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
