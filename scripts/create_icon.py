from PIL import Image, ImageDraw
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
default_icon_path = os.path.join(project_root, "assets", "app.ico")

def create_app_icon(output_path=default_icon_path):
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 32
    radius = 96
    
    box = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(box, radius=radius, fill=(13, 148, 136, 255)) # Teal #0d9488
    
    inner_margin = 48
    inner_box = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    draw.rounded_rectangle(inner_box, radius=radius-12, outline=(15, 23, 42, 100), width=6)

    px1, py1, px2, py2 = 136, 110, 376, 402
    draw.rounded_rectangle([px1, py1, px2, py2], radius=24, fill=(248, 250, 252, 240)) # #f8fafc

    draw.rounded_rectangle([176, 160, 336, 178], radius=6, fill=(13, 148, 136, 255))
    draw.rounded_rectangle([176, 204, 336, 218], radius=4, fill=(100, 116, 139, 255))
    draw.rounded_rectangle([176, 240, 290, 254], radius=4, fill=(100, 116, 139, 255))

    cx, cy, cr = 356, 346, 54
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(16, 185, 129, 255), outline=(255, 255, 255, 255), width=8)

    draw.ellipse([cx - 24, cy - 10, cx - 8, cy + 6], fill=(255, 255, 255, 255))
    draw.ellipse([cx + 6, cy - 10, cx + 22, cy + 6], fill=(255, 255, 255, 255))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(output_path, format="ICO", sizes=sizes)
    print(f"Successfully generated icon at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    create_app_icon()
