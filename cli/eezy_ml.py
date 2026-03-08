import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
import shutil


TEMPLATE_LIBRARIES = [
    "scikit-learn==1.6.1",
    "datasets==4.0.0",
    "flask==3.1.3",
]


def cmd_init(target_dir, use_venv=True):
    repo_url = "https://github.com/not-ekalabya/eezy-ml.git"

    print("The following libraries will be available in the project:")
    for lib in TEMPLATE_LIBRARIES:
        print(f"  - {lib}")
    print()
    print(f"Cloning /template from {repo_url} into {target_dir}...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        result = subprocess.run(["git", "clone", "--no-checkout", repo_url, tmp])
        if result.returncode != 0:
            print("Error: git clone failed.", file=sys.stderr)
            sys.exit(result.returncode)

        subprocess.run(["git", "-C", tmp, "config", "core.sparseCheckout", "true"], check=True)
        (tmp_path / ".git" / "info" / "sparse-checkout").write_text("template/\n")
        subprocess.run(["git", "-C", tmp, "checkout"], check=True)

        template_src = tmp_path / "template"
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        for item in template_src.iterdir():
            dest = target_path / item.name
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)

    print(f"Project initialized in ./{target_dir}")

    if use_venv:
        venv_path = Path(target_dir) / ".venv"
        print(f"\nCreating virtual environment at {venv_path}...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

        pip = venv_path / "Scripts" / "pip.exe"
        requirements = Path(target_dir) / "requirements.txt"
        if requirements.exists():
            print("Installing dependencies...")
            subprocess.run([str(pip), "install", "-r", str(requirements)], check=True)

        print(f"Virtual environment ready. Activate with: {venv_path}\\Scripts\\activate")


def main():
    parser = argparse.ArgumentParser(prog="eezy")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a new eezy-ml project")
    init_parser.add_argument("target_dir", help="Target directory name")
    init_parser.add_argument("--no-venv", action="store_true", help="Skip virtual environment creation")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args.target_dir, use_venv=not args.no_venv)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()