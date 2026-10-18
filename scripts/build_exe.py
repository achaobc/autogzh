import os
import sys
import shutil
import subprocess

def build_exe():
    print("==========================================================")
    print(" 开始打包 AutoGZH 微信公众号排版与同步工具桌面 EXE 软件 ")
    print("==========================================================")

    # 脚本位于 scripts/ 目录，向上回退一级即为项目根目录
    project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    
    # 清理旧构建目录
    for folder in ["build", "dist"]:
        folder_path = os.path.join(project_root, folder)
        if os.path.exists(folder_path):
            print(f"正在清理旧目录: {folder_path}...")
            shutil.rmtree(folder_path, ignore_errors=True)

    # 确定打包分隔符 (Windows 使用 ';'，Linux/Mac 使用 ':')
    sep = ";" if sys.platform.startswith("win") else ":"

    icon_path = os.path.join(project_root, "assets", "app.ico")

    # 构建 PyInstaller 命令
    cmd = [
        "pyinstaller",
        "-y",
        "--name=AutoGZH",
        "--onedir",
        "--noconsole",
        f"--icon={icon_path}",
        
        # 挂载静态资源和配置文件
        f"--add-data={os.path.join(project_root, 'ui')}{sep}ui",
        f"--add-data={os.path.join(project_root, 'styles')}{sep}styles",
        f"--add-data={os.path.join(project_root, 'assets')}{sep}assets",
        f"--add-data={os.path.join(project_root, 'config.yaml.example')}{sep}.",

        # 隐藏依赖显式导入
        "--hidden-import=autogzh",
        "--hidden-import=autogzh.client",
        "--hidden-import=autogzh.renderer",
        "--hidden-import=autogzh.server",
        "--hidden-import=autogzh.gui",
        "--hidden-import=clr",
        "--hidden-import=pythonnet",
        "--hidden-import=bottle",
        "--hidden-import=engineio.async_drivers.threading",
        "--hidden-import=pygments.styles.monokai",
        "--hidden-import=pygments.styles.default",
        "--hidden-import=pygments.styles.github",
        "--hidden-import=pygments.styles.dracula",
        "--hidden-import=markdown.extensions.fenced_code",
        "--hidden-import=markdown.extensions.tables",
        "--hidden-import=markdown.extensions.toc",
        "--hidden-import=markdown.extensions.codehilite",

        # 入口文件
        os.path.join(project_root, "main.py")
    ]

    print("\n执行 PyInstaller 构建指令:")
    print(" ".join(cmd))
    print("\n打包过程中，请稍候...")

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        dist_dir = os.path.join(project_root, "dist", "AutoGZH")
        exe_path = os.path.join(dist_dir, "AutoGZH.exe")
        
        # 复制一份 config.yaml 到打包目录，方便用户直接修改
        config_src = os.path.join(project_root, "config.yaml")
        if os.path.exists(config_src):
            shutil.copy(config_src, dist_dir)
        else:
            example_src = os.path.join(project_root, "config.yaml.example")
            if os.path.exists(example_src):
                shutil.copy(example_src, os.path.join(dist_dir, "config.yaml"))

        print("\n" + "=" * 60)
        print("[SUCCESS] 打包成功完成！")
        print("-" * 60)
        print(f"输出目录路径: {dist_dir}")
        print(f"可执行文件:   {exe_path}")
        print("提示: 您只需进入 dist/AutoGZH 目录，直接双击 AutoGZH.exe 即可使用！")
        print("=" * 60 + "\n")
    else:
        print("\n[ERROR] 打包失败，请检查报错日志！")

if __name__ == "__main__":
    build_exe()
