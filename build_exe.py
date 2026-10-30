"""Build and verify a standalone Windows executable in an isolated environment."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import venv
import zipfile


ROOT = Path(__file__).resolve().parent
APP_NAME = "NRCImageCrawler"


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description="打包独立 Windows exe 并验证")
    parser.add_argument("--skip-install", action="store_true",
                        help="复用已安装的打包依赖，无需联网（首次打包不要使用）")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("请在 Windows 上打包 Windows .exe。")
    environment = ROOT / ".venv-build"
    python = environment / "Scripts" / "python.exe"
    if not python.is_file():
        print("创建隔离的打包环境…", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    if not args.skip_install:
        run(python, "-m", "pip", "install", "-r", ROOT / "requirements-build.txt")
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "pyinstaller-cache")
    run(python, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--windowed", "--name", APP_NAME, "--distpath", ROOT / "dist",
        "--workpath", ROOT / "build" / "pyinstaller", "--specpath", ROOT / "build",
        ROOT / "launcher.py")
    executable = ROOT / "dist" / f"{APP_NAME}.exe"
    print("验证独立程序：Tk 界面、图片读写、网页解析、HTTPS 证书和输出目录…", flush=True)
    result = subprocess.run([str(executable), "--smoke-test"], cwd=ROOT, timeout=120)
    if result.returncode:
        raise RuntimeError(f"独立程序检查失败，退出码 {result.returncode}；请勿发布此次构建。")
    archive = ROOT / "dist" / f"{APP_NAME}-windows-{os.environ.get('PROCESSOR_ARCHITECTURE', 'unknown').lower()}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(executable, executable.name)
        bundle.write(ROOT / "LICENSE", "LICENSE")
        bundle.write(ROOT / "使用说明.txt", "使用说明.txt")
    print(f"\n打包与验证完成：\n{executable}\n{archive}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
